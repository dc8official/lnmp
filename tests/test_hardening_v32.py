from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.models.flow_rollup import (
    FlowDailyRollup,
    FlowHourlyRollup,
    FlowMinuteRollup,
)
from app.routers.auth import get_current_user, require_admin
from app.routers.bandwidth import (
    _select_rollup_model_and_bucket_seconds,
    get_flow_redis,
    router as bandwidth_router,
)
from app.routers.endpoints import CreateEndpointRequest, create_endpoint
from monitoring.flow.aggregator import FlowAggregator
from monitoring.flow.collector import FlowCollector, STREAM_NETFLOW_RAW


@pytest.mark.anyio
async def test_flow_aggregator_no_data_loss_on_db_error():
    """
    Verifies that FlowAggregator does NOT clear its accumulator or xack Redis
    messages if a database error occurs during flush.
    """
    mock_redis = AsyncMock()
    mock_correlator = MagicMock()
    mock_correlator.correlate.return_value = (None, None, None)

    # Failing DB session
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB connection dropped")

    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__.return_value = mock_session
    mock_db_factory.return_value.__aexit__.return_value = None

    aggregator = FlowAggregator(
        redis_client=mock_redis,
        correlator=mock_correlator,
        db_session_factory=mock_db_factory,
    )

    # Accumulate a flow
    aggregator.accumulate_flow(
        exporter_ip="10.0.0.1",
        src_ip="192.168.1.10",
        dst_ip="8.8.8.8",
        src_port=12345,
        dst_port=53,
        protocol=17,
        flow_bytes=500,
        flow_packets=2,
        start_time_unix=1700000000.0,
    )
    aggregator._pending_msg_ids.append("1700000000000-0")

    assert len(aggregator._accumulator) == 1
    assert len(aggregator._pending_msg_ids) == 1

    # Attempt flush - should catch exception and retain accumulator and pending IDs
    await aggregator.flush_to_timescaledb()

    assert len(aggregator._accumulator) == 1
    assert len(aggregator._pending_msg_ids) == 1
    mock_redis.xack.assert_not_called()

    # Now make DB succeed
    mock_session.execute.side_effect = None
    mock_session.commit = AsyncMock()

    await aggregator.flush_to_timescaledb()

    # Accumulator should now be cleared and xack should have been called
    assert len(aggregator._accumulator) == 0
    assert len(aggregator._pending_msg_ids) == 0
    mock_redis.xack.assert_called_once()
    assert "1700000000000-0" in mock_redis.xack.call_args[0]


def test_flow_aggregator_insert_sql_bindparams():
    """
    Verifies that the insert_sql in FlowAggregator correctly parses all 11 bind parameters,
    specifically ensuring that CAST(:src_ip AS inet) and CAST(:dst_ip AS inet) are recognized
    as parameters rather than skipped due to double-colon escaping.
    """
    import inspect
    import re
    from sqlalchemy import text
    from monitoring.flow import aggregator

    # Extract insert_sql definition from source
    src = inspect.getsource(aggregator.FlowAggregator.flush_to_timescaledb)
    m = re.search(r'insert_sql\s*=\s*text\(\s*"""(.*?)"""\s*\)', src, re.DOTALL)
    assert m is not None, "Could not find insert_sql in flush_to_timescaledb"
    sql_text = text(m.group(1))

    compiled_params = set(sql_text.compile().params.keys())
    expected_params = {
        "bucket",
        "exporter_id",
        "src_endpoint_id",
        "dst_endpoint_id",
        "src_ip",
        "dst_ip",
        "protocol",
        "dst_port",
        "bytes",
        "packets",
        "flow_count",
    }
    assert compiled_params == expected_params, f"Missing or incorrect params: {expected_params - compiled_params}"


@pytest.mark.anyio
async def test_flow_collector_bounded_stream_xadd():
    """
    Verifies that FlowCollector passes maxlen=100000, approximate=True to pipe.xadd.
    """
    mock_redis = AsyncMock()
    mock_pipe = MagicMock()
    mock_pipe.xadd = MagicMock()
    mock_pipe.execute = AsyncMock()
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)

    collector = FlowCollector(redis_client=mock_redis)
    collector._queue.append({
        "version": 5,
        "exporter_ip": "10.0.0.1",
        "src_ip": "192.168.1.10",
        "dst_ip": "8.8.8.8",
        "src_port": 12345,
        "dst_port": 53,
        "protocol": 17,
        "bytes": 500,
        "packets": 2,
        "start_time": 1700000000.0,
        "end_time": 1700000001.0,
    })

    await collector.flush()

    mock_pipe.xadd.assert_called_once()
    args, kwargs = mock_pipe.xadd.call_args
    assert args[0] == STREAM_NETFLOW_RAW
    assert kwargs.get("maxlen") == 100000
    assert kwargs.get("approximate") is True


def test_dynamic_cagg_routing_selection():
    """
    Verifies that _select_rollup_model_and_bucket_seconds selects:
    - 1h / 6h -> FlowMinuteRollup (60s)
    - 24h / 7d -> FlowHourlyRollup (3600s)
    - 30d / 1y -> FlowDailyRollup (86400s) or FlowHourlyRollup if endpoint_id filtered
    """
    model, secs = _select_rollup_model_and_bucket_seconds("1h")
    assert model == FlowMinuteRollup
    assert secs == 60.0

    model, secs = _select_rollup_model_and_bucket_seconds("6h")
    assert model == FlowMinuteRollup
    assert secs == 60.0

    model, secs = _select_rollup_model_and_bucket_seconds("24h")
    assert model == FlowHourlyRollup
    assert secs == 3600.0

    model, secs = _select_rollup_model_and_bucket_seconds("7d")
    assert model == FlowHourlyRollup
    assert secs == 3600.0

    model, secs = _select_rollup_model_and_bucket_seconds("30d")
    assert model == FlowDailyRollup
    assert secs == 86400.0

    # With endpoint_id, 30d must route to FlowHourlyRollup because FlowDailyRollup has no endpoint columns
    ep_uuid = uuid4()
    model, secs = _select_rollup_model_and_bucket_seconds("30d", endpoint_id=ep_uuid)
    assert model == FlowHourlyRollup
    assert secs == 3600.0


@pytest.mark.anyio
async def test_get_flow_redis_decoupled_from_driver_manager():
    """
    Verifies that get_flow_redis() returns an independent Redis instance
    when driver_manager._redis_client is None.
    """
    with patch("app.services.driver_manager.driver_manager._redis_client", None):
        with patch("redis.asyncio.Redis") as mock_aioredis:
            mock_inst = MagicMock()
            mock_aioredis.return_value = mock_inst
            # Reset global pool for testing
            import app.routers.bandwidth as bw
            bw._flow_redis_pool = None

            client = await get_flow_redis()
            assert client == mock_inst
            mock_aioredis.assert_called_once()


@pytest.mark.anyio
async def test_create_endpoint_forwards_flow_exporter_attributes():
    """
    Verifies that create_endpoint passes flow_exporter_ips and flow_interface_aliases
    to the endpoint repository.
    """
    req = CreateEndpointRequest(
        ip_address="192.168.10.1",
        hostname="core-router-01",
        device_type="ROUTER",
        flow_exporter_ips=["10.10.10.1", "10.10.10.2"],
        flow_interface_aliases={"Gi0/0": "WAN-Uplink"},
    )
    current_user = {"sub": str(uuid4()), "role": "ADMIN"}
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    with patch("app.routers.endpoints.EndpointRepository") as mock_repo_cls, \
         patch("app.routers.endpoints.AuthRepository") as mock_auth_cls, \
         patch("app.routers.endpoints._bg_run_initial_discovery"):
        repo_instance = mock_repo_cls.return_value
        repo_instance.get_by_ip = AsyncMock(return_value=None)
        
        mock_ep = MagicMock()
        mock_ep.id = uuid4()
        repo_instance.create_endpoint = AsyncMock(return_value=mock_ep)

        auth_instance = mock_auth_cls.return_value
        auth_instance.create_audit_log = AsyncMock()

        res = await create_endpoint(request=req, current_user=current_user, db=mock_db)
        assert res.data["id"] == str(mock_ep.id)

        # Check create_endpoint kwargs
        repo_instance.create_endpoint.assert_called_once()
        kwargs = repo_instance.create_endpoint.call_args[1]
        assert kwargs["flow_exporter_ips"] == ["10.10.10.1", "10.10.10.2"]
        assert kwargs["flow_interface_aliases"] == {"Gi0/0": "WAN-Uplink"}


@pytest.mark.anyio
async def test_ssrf_validator_pins_resolved_ip():
    """
    Verifies that SSRFSafeBackend resolves the host and invokes connect_tcp
    with the resolved target_ip rather than the host string, eliminating TOCTOU DNS rebinding.
    """
    from app.services.ssrf_validator import SSRFSafeBackend

    mock_inner = AsyncMock()
    mock_inner.connect_tcp = AsyncMock(return_value="mock_stream")
    backend = SSRFSafeBackend(mock_inner, allow_private=False)

    fake_addr_info = [
        (2, 1, 6, "", ("93.184.216.34", 443))
    ]
    with patch("socket.getaddrinfo", return_value=fake_addr_info):
        stream = await backend.connect_tcp("example.com", 443)
        assert stream == "mock_stream"
        mock_inner.connect_tcp.assert_called_once()
        call_args = mock_inner.connect_tcp.call_args
        assert call_args[0][0] == "93.184.216.34"
        assert call_args[0][1] == 443


@pytest.mark.anyio
async def test_smtp_private_relay_and_metadata_isolation():
    """
    Verifies that AlertDispatcher._sync_send_smtp allows private RFC1918 and loopback
    relays while strictly blocking cloud metadata (169.254.169.254).
    """
    from app.services.alert_dispatcher import AlertDispatcher

    dispatcher = AlertDispatcher()

    # Cloud metadata IP must be blocked
    cfg_meta = {
        "smtp_host": "169.254.169.254",
        "smtp_port": 25,
        "from_address": "test@corp.com",
        "to_addresses": ["admin@corp.com"],
    }
    with pytest.raises(ValueError, match="SSRF|metadata|forbidden address"):
        dispatcher._sync_send_smtp(cfg_meta, MagicMock())

    # RFC1918 and loopback should be allowed
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value = MagicMock()
        cfg_private = {
            "smtp_host": "10.0.0.25",
            "smtp_port": 25,
            "from_address": "test@corp.com",
            "to_addresses": ["admin@corp.com"],
        }
        dispatcher._sync_send_smtp(cfg_private, MagicMock())
        mock_smtp.assert_called_with("10.0.0.25", 25, timeout=10.0)


@pytest.mark.anyio
async def test_alert_rate_limiter_none_endpoint_isolation():
    """
    Verifies that AlertDispatcher._evaluate_and_send_channel keys non-endpoint events
    by event type and endpoint name rather than a shared 'None' key.
    """
    from app.services.alert_dispatcher import AlertDispatcher
    from app.models.alert_channel import AlertChannel

    dispatcher = AlertDispatcher()
    channel = AlertChannel(
        id=uuid4(),
        name="Test Rate Limit",
        channel_type="GENERIC_WEBHOOK",
        is_enabled=True,
        config="{}",
        endpoint_ids=[],
        subnet_filters=[],
        severity_filters=["WARNING"],
    )

    mock_db = AsyncMock()
    now = datetime.datetime.now(datetime.timezone.utc)

    with patch.object(dispatcher, "_parse_channel_config", return_value={"url": "https://example.com"}), \
         patch.object(dispatcher, "_send_to_provider", new_callable=AsyncMock) as mock_send, \
         patch.object(dispatcher, "_record_delivery_log", new_callable=AsyncMock):
        mock_send.return_value = ("DELIVERED", 200, "OK")

        await dispatcher._evaluate_and_send_channel(
            db=mock_db,
            channel=channel,
            endpoint_id=None,
            endpoint_name="core-switch",
            ip_address="192.168.1.1",
            event_type="SYSTEM_ALERT",
            severity="WARNING",
            timestamp=now,
            details={"title": "High CPU"},
            is_flapping=False,
        )
        assert mock_send.call_count == 1
        expected_key1 = (str(channel.id), "event:SYSTEM_ALERT:core-switch", "WARNING")
        assert expected_key1 in dispatcher._rate_limits

        # Second event has different event_type, should NOT be throttled
        await dispatcher._evaluate_and_send_channel(
            db=mock_db,
            channel=channel,
            endpoint_id=None,
            endpoint_name="core-switch",
            ip_address="192.168.1.1",
            event_type="BACKUP_FAILURE",
            severity="WARNING",
            timestamp=now,
            details={"title": "Backup failed"},
            is_flapping=False,
        )
        assert mock_send.call_count == 2
        expected_key2 = (str(channel.id), "event:BACKUP_FAILURE:core-switch", "WARNING")
        assert expected_key2 in dispatcher._rate_limits


@pytest.mark.anyio
async def test_subnet_filter_inet_prefix_handling():
    """
    Verifies that _evaluate_and_send_channel cleanly handles endpoint_ip with CIDR prefix
    (e.g., '192.168.1.50/32' or '10.0.0.1/24') without raising ValueError.
    """
    from app.services.alert_dispatcher import AlertDispatcher
    from app.models.alert_channel import AlertChannel

    dispatcher = AlertDispatcher()
    channel = AlertChannel(
        id=uuid4(),
        name="Subnet Channel",
        channel_type="GENERIC_WEBHOOK",
        is_enabled=True,
        config="{}",
        endpoint_ids=[],
        subnet_filters=["192.168.1.0/24"],
        severity_filters=["DOWN"],
    )

    mock_db = AsyncMock()
    now = datetime.datetime.now(datetime.timezone.utc)

    with patch.object(dispatcher, "_parse_channel_config", return_value={"url": "https://example.com"}), \
         patch.object(dispatcher, "_send_to_provider", new_callable=AsyncMock) as mock_send, \
         patch.object(dispatcher, "_record_delivery_log", new_callable=AsyncMock):
        mock_send.return_value = ("DELIVERED", 200, "OK")

        await dispatcher._evaluate_and_send_channel(
            db=mock_db,
            channel=channel,
            endpoint_id=uuid4(),
            endpoint_name="host-1",
            ip_address="192.168.1.50/32",
            event_type="TEST",
            severity="DOWN",
            timestamp=now,
            details={"title": "Host Down"},
            is_flapping=False,
        )
        assert mock_send.call_count == 1


def test_alert_channel_type_enum_validation():
    """
    Verifies that AlertChannelCreate / AlertChannelUpdate validates channel_type against allowed types.
    """
    from app.schemas.alerts import AlertChannelCreate, AlertChannelUpdate
    from pydantic import ValidationError

    # Valid channel types
    for ct in ["TEAMS", "DISCORD", "SLACK", "EMAIL_SMTP", "GENERIC_WEBHOOK"]:
        acc = AlertChannelCreate(
            name="Valid",
            channel_type=ct,
            config={"url": "https://example.com"} if ct != "EMAIL_SMTP" else {
                "smtp_host": "mail.example.com",
                "smtp_port": 25,
                "from_address": "a@b.com",
                "to_addresses": ["c@d.com"],
            },
        )
        assert acc.channel_type == ct

    # Invalid channel types
    with pytest.raises(ValidationError):
        AlertChannelCreate(
            name="Invalid",
            channel_type="PAGERDUTY",
            config={"key": "123"},
        )
    with pytest.raises(ValidationError):
        AlertChannelUpdate(
            channel_type="UNKNOWN_SERVICE",
        )


@pytest.mark.anyio
async def test_postgres_event_broker_payload_limit_protection():
    """
    Verifies that PostgresEventBroker.publish truncates payload if encoded size exceeds 7500 bytes.
    """
    import json
    from app.services.event_broker import PostgresEventBroker

    mock_db_factory = MagicMock()
    mock_session = AsyncMock()
    mock_db_factory.return_value.__aenter__.return_value = mock_session
    mock_db_factory.return_value.__aexit__.return_value = None

    broker = PostgresEventBroker(mock_db_factory)

    large_payload = {
        "event_id": str(uuid4()),
        "event_type": "LARGE_EVENT",
        "symptom_endpoint_ids": [str(uuid4()) for _ in range(300)],
    }

    await broker.publish("test_channel", large_payload)

    mock_session.execute.assert_called_once()
    sql_params = mock_session.execute.call_args[0][1]

    payload_str = sql_params["payload"]
    assert len(payload_str.encode("utf-8")) <= 7500
    parsed = json.loads(payload_str)
    assert parsed.get("truncated") is True
    assert parsed.get("symptom_count") == 300
    assert len(parsed.get("symptom_endpoint_ids")) < 300


def test_aggregator_resilient_to_corrupt_empty_ip():
    """
    Verifies that FlowAggregator.accumulate_flow safely ignores records with empty or corrupt IP addresses.
    """
    mock_correlator = MagicMock()
    mock_correlator.correlate.return_value = (uuid4(), None, None)

    aggregator = FlowAggregator(
        redis_client=AsyncMock(),
        correlator=mock_correlator,
        db_session_factory=MagicMock(),
    )

    # Empty src_ip
    aggregator.accumulate_flow(
        exporter_ip="10.0.0.1",
        src_ip="",
        dst_ip="192.168.1.1",
        src_port=1234,
        dst_port=80,
        protocol=6,
        flow_bytes=100,
        flow_packets=1,
        start_time_unix=1700000000.0,
    )
    assert len(aggregator._accumulator) == 0

    # Corrupt dst_ip
    aggregator.accumulate_flow(
        exporter_ip="10.0.0.1",
        src_ip="192.168.1.1",
        dst_ip="999.999.999.999",
        src_port=1234,
        dst_port=80,
        protocol=6,
        flow_bytes=100,
        flow_packets=1,
        start_time_unix=1700000000.0,
    )
    assert len(aggregator._accumulator) == 0

    # Valid IPs
    aggregator.accumulate_flow(
        exporter_ip="10.0.0.1",
        src_ip="192.168.1.1",
        dst_ip="192.168.1.2",
        src_port=1234,
        dst_port=80,
        protocol=6,
        flow_bytes=100,
        flow_packets=1,
        start_time_unix=1700000000.0,
    )
    assert len(aggregator._accumulator) == 1


@pytest.mark.anyio
async def test_aggregator_pk_deduplication_on_endpoint_remap():
    """
    Verifies that flush_to_timescaledb groups records sharing the same primary key
    (bucket, exporter_id, src_ip, dst_ip, protocol, dst_port) into a single row
    before executing the SQL upsert, preventing duplicate key errors.
    """
    mock_session = AsyncMock()
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__.return_value = mock_session
    mock_db_factory.return_value.__aexit__.return_value = None

    aggregator = FlowAggregator(
        redis_client=AsyncMock(),
        correlator=MagicMock(),
        db_session_factory=mock_db_factory,
    )

    t0 = datetime.datetime(2026, 9, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
    key1 = (t0, "00000000-0000-0000-0000-000000000000", None, None, "10.0.0.1", "10.0.0.2", 6, 80)
    key2 = (t0, "00000000-0000-0000-0000-000000000000", uuid4(), None, "10.0.0.1", "10.0.0.2", 6, 80)

    aggregator._accumulator[key1] = [100, 1, 1]
    aggregator._accumulator[key2] = [200, 2, 1]

    await aggregator.flush_to_timescaledb()

    assert mock_session.execute.called
    params_list = mock_session.execute.call_args[0][1]
    assert len(params_list) == 1
    assert params_list[0]["bytes"] == 300
    assert params_list[0]["packets"] == 3
    assert params_list[0]["flow_count"] == 2


def test_v9_and_ipfix_orphan_not_queued_when_empty_records():
    """
    Verifies that V9 and IPFIX parsers return empty list for template-only packets,
    and collector's 'if parsed is not None' correctly avoids queueing empty records.
    """
    import struct
    from monitoring.flow.v9_parser import (
        V9Parser,
        HEADER_STRUCT as V9_HEADER_STRUCT,
        FLOWSET_HEADER_STRUCT as V9_FS_STRUCT,
    )
    from monitoring.flow.ipfix_parser import (
        IPFIXParser,
        HEADER_STRUCT as IPFIX_HEADER_STRUCT,
        SET_HEADER_STRUCT as IPFIX_SET_STRUCT,
    )

    # Construct v9 template-only packet (count=1, FlowSet ID 0)
    v9_hdr = V9_HEADER_STRUCT.pack(9, 1, 1000, 1700000000, 1, 12345)
    tmpl_data = struct.pack("!HHHHH", 256, 1, 1, 4, 0)
    v9_fs = V9_FS_STRUCT.pack(0, 4 + len(tmpl_data))
    v9_packet = v9_hdr + v9_fs + tmpl_data

    v9_parser = V9Parser()
    res_v9 = v9_parser.parse_packet(v9_packet, "10.0.0.1")
    assert res_v9 is not None
    assert len(res_v9) == 0

    # IPFIX template-only packet (length=16+4+10=30 bytes, set_id=2)
    ipfix_hdr = IPFIX_HEADER_STRUCT.pack(10, 30, 1700000000, 1, 12345)
    ipfix_fs = IPFIX_SET_STRUCT.pack(2, 4 + len(tmpl_data))
    ipfix_packet = ipfix_hdr + ipfix_fs + tmpl_data

    ipfix_parser = IPFIXParser()
    res_ipfix = ipfix_parser.parse_packet(ipfix_packet, "10.0.0.1")
    assert res_ipfix is not None
    assert len(res_ipfix) == 0


@pytest.mark.anyio
async def test_bandwidth_active_exporters_excludes_sentinel():
    """
    Verifies that get_bandwidth_overview filters out SENTINEL_UUID from active exporters.
    """
    from app.routers.bandwidth import get_bandwidth_overview, SENTINEL_UUID

    mock_db = AsyncMock()
    mock_result_scalar = MagicMock()
    # row = [total_bytes, ingress_bytes, egress_bytes, total_flows, active_exporters]
    mock_result_scalar.one_or_none.return_value = [1000, 500, 500, 10, 2]
    mock_db.execute.return_value = mock_result_scalar

    res = await get_bandwidth_overview(current_user={"username": "admin"}, db=mock_db)
    assert res.status == "success"

    queries = [str(call[0][0]) for call in mock_db.execute.call_args_list]
    found_sentinel_exclusion = any(str(SENTINEL_UUID) in q or "exporter_id !=" in q for q in queries)
    assert found_sentinel_exclusion, f"SENTINEL_UUID exclusion not found in queries: {queries}"


@pytest.mark.anyio
async def test_top_talkers_with_endpoint_id_filter():
    """
    Verifies that get_top_talkers applies the endpoint_id filter to both talkers and conversations.
    """
    from app.routers.bandwidth import get_top_talkers

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result

    target_ep_id = uuid4()
    res = await get_top_talkers(
        window="1h",
        limit=10,
        endpoint_id=target_ep_id,
        current_user={"username": "admin"},
        db=mock_db,
    )
    assert res.status == "success"

    queries = [str(call[0][0]) for call in mock_db.execute.call_args_list]
    found_filter = any("src_endpoint_id = :src_endpoint_id" in q or "dst_endpoint_id = :dst_endpoint_id" in q for q in queries)
    assert found_filter, f"Endpoint ID filter not found in queries: {queries}"

