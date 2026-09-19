from __future__ import annotations

import asyncio
import collections
import datetime
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text

logger = logging.getLogger(__name__)

STREAM_KEY = "stream:netflow:raw"
GROUP_NAME = "flow_agg_group"
CONSUMER_NAME = "aggregator_worker_1"
SENTINEL_UUID = UUID("00000000-0000-0000-0000-000000000000")


def normalize_service_port(src_port: int, dst_port: int) -> int:
    """
    Normalizes service ports to protect index cardinality from ephemeral client ports (1024-65535).
    """
    if src_port < 1024 and dst_port >= 1024:
        return src_port
    if src_port in (8080, 8443, 3306, 5432, 6379, 9200) and dst_port > 10000:
        return src_port
    return dst_port


class FlowAggregator:
    """
    Redis Stream consumer and TimescaleDB 1-minute hypertable micro-batch aggregator.
    """

    def __init__(
        self,
        redis_client: Any,
        correlator: Any,
        db_session_factory: Any,
        flush_interval_seconds: float = 10.0,
    ):
        self.redis = redis_client
        self.correlator = correlator
        self.db_factory = db_session_factory
        self.flush_interval = flush_interval_seconds

        # (bucket, exporter_id, src_endpoint_id, dst_endpoint_id, src_ip, dst_ip, protocol, dst_port) -> [bytes, packets, flow_count]
        self._accumulator: Dict[
            Tuple[datetime.datetime, UUID, Optional[UUID], Optional[UUID], str, str, int, int],
            List[int],
        ] = collections.defaultdict(lambda: [0, 0, 0]) if "collections" in globals() else {}
        self._pending_msg_ids: List[str] = []

        self._running = False
        self._consume_task: Optional[asyncio.Task] = None
        self._flush_task: Optional[asyncio.Task] = None
        self._trim_task: Optional[asyncio.Task] = None

    async def _setup_consumer_group(self) -> None:
        if not self.redis:
            return
        try:
            await self.redis.xgroup_create(STREAM_KEY, GROUP_NAME, id="0", mkstream=True)
            logger.info("Created consumer group '%s' on '%s'.", GROUP_NAME, STREAM_KEY)
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.warning("Error creating consumer group: %s", e)

    async def _check_circuit_breaker(self) -> bool:
        """Returns True if memory usage is within safe bounds (<85%), False if tripped."""
        if not self.redis:
            return True
        try:
            info = await self.redis.info("memory")
            used = int(info.get("used_memory", 0))
            maxmem = int(info.get("maxmemory", 0))
            if maxmem > 0 and (used / maxmem) > 0.85:
                logger.error(
                    "Circuit Breaker TRIPPED: Redis memory utilization at %.1f%% (>85%%). Dropping buffer.",
                    (used / maxmem) * 100.0,
                )
                return False
        except Exception:
            pass
        return True

    def accumulate_flow(
        self,
        exporter_ip: str,
        src_ip: str,
        dst_ip: str,
        src_port: int,
        dst_port: int,
        protocol: int,
        flow_bytes: int,
        flow_packets: int,
        start_time_unix: float,
    ) -> None:
        exporter_id, src_ep_id, dst_ep_id = self.correlator.correlate(
            exporter_ip, src_ip, dst_ip
        )
        resolved_exporter = exporter_id if exporter_id is not None else SENTINEL_UUID

        # Truncate start_time to 1-minute bucket (UTC)
        dt = datetime.datetime.fromtimestamp(start_time_unix, tz=datetime.timezone.utc)
        bucket = dt.replace(second=0, microsecond=0)

        normalized_port = normalize_service_port(src_port, dst_port)
        key = (
            bucket,
            resolved_exporter,
            src_ep_id,
            dst_ep_id,
            src_ip,
            dst_ip,
            protocol,
            normalized_port,
        )

        if key not in self._accumulator:
            self._accumulator[key] = [flow_bytes, flow_packets, 1]
        else:
            entry = self._accumulator[key]
            entry[0] += flow_bytes
            entry[1] += flow_packets
            entry[2] += 1

    async def flush_to_timescaledb(self) -> None:
        if not self._accumulator and not self._pending_msg_ids:
            return

        # Snapshot current accumulator entries and pending stream IDs
        snapshot = {k: list(v) for k, v in self._accumulator.items()}
        pending_ack = list(self._pending_msg_ids)

        if snapshot:
            logger.debug("Flushing %d aggregated rollup entries to TimescaleDB...", len(snapshot))

            # Build parameterized bulk insert query
            rows = []
            for key, vals in snapshot.items():
                bucket, exp_id, src_ep_id, dst_ep_id, src_ip, dst_ip, proto, d_port = key
                bytes_val, pkts_val, count_val = vals
                rows.append(
                    {
                        "bucket": bucket,
                        "exporter_id": exp_id,
                        "src_endpoint_id": src_ep_id,
                        "dst_endpoint_id": dst_ep_id,
                        "src_ip": src_ip,
                        "dst_ip": dst_ip,
                        "protocol": proto,
                        "dst_port": d_port,
                        "bytes": bytes_val,
                        "packets": pkts_val,
                        "flow_count": count_val,
                    }
                )

            insert_sql = text("""
                INSERT INTO flow_minute_rollups (
                    bucket, exporter_id, src_endpoint_id, dst_endpoint_id,
                    src_ip, dst_ip, protocol, dst_port,
                    bytes, packets, flow_count
                ) VALUES (
                    :bucket, :exporter_id, :src_endpoint_id, :dst_endpoint_id,
                    CAST(:src_ip AS inet), CAST(:dst_ip AS inet), :protocol, :dst_port,
                    :bytes, :packets, :flow_count
                )
                ON CONFLICT (bucket, exporter_id, src_ip, dst_ip, protocol, dst_port)
                DO UPDATE SET
                    bytes = flow_minute_rollups.bytes + EXCLUDED.bytes,
                    packets = flow_minute_rollups.packets + EXCLUDED.packets,
                    flow_count = flow_minute_rollups.flow_count + EXCLUDED.flow_count;
            """)

            try:
                async with self.db_factory() as session:
                    # Execute in batches of 1000
                    batch_size = 1000
                    for i in range(0, len(rows), batch_size):
                        chunk = rows[i : i + batch_size]
                        await session.execute(insert_sql, chunk)
                    await session.commit()
                logger.info("Successfully persisted %d flow rollup records to TimescaleDB.", len(rows))
            except Exception as e:
                logger.error("Failed to commit flow rollup micro-batch to DB: %s", e)
                # Keep accumulator intact and do not ack messages on failure
                return

            # Only deduct committed quantities from accumulator on successful DB commit
            for k, flushed_vals in snapshot.items():
                if k in self._accumulator:
                    self._accumulator[k][0] -= flushed_vals[0]
                    self._accumulator[k][1] -= flushed_vals[1]
                    self._accumulator[k][2] -= flushed_vals[2]
                    if self._accumulator[k][2] <= 0:
                        del self._accumulator[k]

        # Acknowledge stream messages in Redis only after successful DB persistence
        if pending_ack and self.redis:
            try:
                batch_ack = 500
                for i in range(0, len(pending_ack), batch_ack):
                    ack_chunk = pending_ack[i : i + batch_ack]
                    await self.redis.xack(STREAM_KEY, GROUP_NAME, *ack_chunk)
                self._pending_msg_ids = self._pending_msg_ids[len(pending_ack):]
            except Exception as ack_err:
                logger.warning("Failed to xack stream messages in Redis: %s", ack_err)

    async def _consume_stream(self) -> None:
        await self._setup_consumer_group()

        while self._running:
            if not self.redis:
                await asyncio.sleep(1.0)
                continue

            # Circuit breaker check
            if not await self._check_circuit_breaker():
                await asyncio.sleep(5.0)
                continue

            try:
                # Read up to 2000 messages with 1s timeout
                entries = await self.redis.xreadgroup(
                    GROUP_NAME,
                    CONSUMER_NAME,
                    {STREAM_KEY: ">"},
                    count=2000,
                    block=1000,
                )

                if not entries:
                    continue

                for _, message_list in entries:
                    for msg_id, fields in message_list:
                        raw_id = msg_id.decode("utf-8") if isinstance(msg_id, bytes) else str(msg_id)
                        self._pending_msg_ids.append(raw_id)
                        try:
                            exp_ip = fields.get("exp", "")
                            src_ip = fields.get("src", "")
                            dst_ip = fields.get("dst", "")
                            sport = int(fields.get("sport", 0))
                            dport = int(fields.get("dport", 0))
                            proto = int(fields.get("proto", 0))
                            f_bytes = int(fields.get("b", 0))
                            f_pkts = int(fields.get("p", 0))
                            ts_start = float(fields.get("ts_start", time.time()))

                            self.accumulate_flow(
                                exporter_ip=exp_ip,
                                src_ip=src_ip,
                                dst_ip=dst_ip,
                                src_port=sport,
                                dst_port=dport,
                                protocol=proto,
                                flow_bytes=f_bytes,
                                flow_packets=f_pkts,
                                start_time_unix=ts_start,
                            )
                        except Exception as parse_err:
                            logger.debug("Corrupted stream message %s: %s", msg_id, parse_err)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Error consuming from Redis Stream: %s", exc)
                await asyncio.sleep(1.0)

    async def _flush_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush_to_timescaledb()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Aggregator flush loop error: %s", e)

    async def _stream_trim_loop(self) -> None:
        """Prunes Redis Stream entries older than 2 hours every 5 minutes."""
        while self._running:
            try:
                await asyncio.sleep(300.0)
                if self.redis:
                    # 2 hours ago in ms
                    cutoff_ms = int((time.time() - 7200.0) * 1000)
                    await self.redis.xtrim(STREAM_KEY, minid=str(cutoff_ms), approximate=True)
                    logger.debug("Trimmed stream '%s' older than 2 hours (minid=%d).", STREAM_KEY, cutoff_ms)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Stream trim error: %s", e)

    async def start(self) -> None:
        self._running = True
        self._consume_task = asyncio.create_task(self._consume_stream())
        self._flush_task = asyncio.create_task(self._flush_loop())
        self._trim_task = asyncio.create_task(self._stream_trim_loop())
        logger.info("FlowAggregator started.")

    async def stop(self) -> None:
        self._running = False
        if self._consume_task:
            self._consume_task.cancel()
        if self._flush_task:
            self._flush_task.cancel()
        if self._trim_task:
            self._trim_task.cancel()
        await self.flush_to_timescaledb()
        logger.info("FlowAggregator stopped.")
