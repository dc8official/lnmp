from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Default static baseline values for fallback & grace period (< 7 days of historical data)
DEFAULT_MEAN_MS: float = 50.0
DEFAULT_STDDEV_MS: float = 15.0
DEFAULT_K_MULTIPLIER: float = 3.0
GRACE_PERIOD_DAYS: int = 7


class BaselineCache:
    """
    In-memory baseline cache storing historical latency statistics per endpoint and time bucket.

    Structure:
        baseline_cache[endpoint_id][(day_of_week, hour_of_day)] -> (mean, stddev)

    Where:
        - endpoint_id: UUID
        - day_of_week: int (0 = Sunday, ..., 6 = Saturday)
        - hour_of_day: int (0 .. 23)
        - mean: float (AVG of latency in ms)
        - stddev: float (STDDEV of latency in ms)
    """

    def __init__(self) -> None:
        self._cache: Dict[UUID, Dict[Tuple[int, int], Tuple[float, float]]] = {}
        self._onboarded_dates: Dict[UUID, datetime] = {}
        self._lock = asyncio.Lock()

    async def refresh_from_db(self, db: AsyncSession) -> None:
        """
        Asynchronously queries node_historical_baselines continuous aggregate
        and endpoints table to populate the in-memory baseline lookup map.
        """
        try:
            # Step 1: Query endpoints creation time to enforce grace period rules
            endpoints_query = text("SELECT id, created_at FROM endpoints WHERE endpoint_status != 'DELETED'")
            ep_result = await db.execute(endpoints_query)
            onboarded: Dict[UUID, datetime] = {}
            for row in ep_result.fetchall():
                onboarded[UUID(str(row.id))] = row.created_at

            # Step 2: Query continuous aggregate view node_historical_baselines
            baseline_query = text("""
                SELECT
                    endpoint_id,
                    day_of_week,
                    hour_of_day,
                    historical_mean,
                    historical_stddev
                FROM node_historical_baselines
            """)
            bl_result = await db.execute(baseline_query)

            new_cache: Dict[UUID, Dict[Tuple[int, int], Tuple[float, float]]] = {}
            for row in bl_result.fetchall():
                ep_id = UUID(str(row.endpoint_id))
                dow = int(row.day_of_week)
                hour = int(row.hour_of_day)
                mean = float(row.historical_mean) if row.historical_mean is not None else DEFAULT_MEAN_MS
                stddev = float(row.historical_stddev) if row.historical_stddev is not None else DEFAULT_STDDEV_MS

                if ep_id not in new_cache:
                    new_cache[ep_id] = {}
                new_cache[ep_id][(dow, hour)] = (mean, stddev)

            async with self._lock:
                self._cache = new_cache
                self._onboarded_dates = onboarded

            logger.info(
                "BaselineCache updated successfully: %d endpoints cached.",
                len(new_cache),
            )

        except Exception as e:
            logger.error(
                "Failed to refresh baseline cache from database: %s: %s",
                type(e).__name__,
                e,
            )

    def get_baseline(
        self,
        endpoint_id: UUID,
        dt: Optional[datetime] = None,
    ) -> Tuple[float, float]:
        """
        Retrieves the (mean, stddev) baseline for an endpoint at a specific datetime.

        Applies fallback logic:
        1. If the endpoint is newly onboarded (< 7 days of records), returns default baseline.
        2. If no aggregated bucket exists for (day_of_week, hour_of_day), returns default baseline.
        """
        if dt is None:
            dt = datetime.now(timezone.utc)

        # Fallback 1: Grace period check (< 7 days of onboarding)
        created_at = self._onboarded_dates.get(endpoint_id)
        if created_at is not None:
            # Ensure timezones match for comparison
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_days = (dt - created_at).total_seconds() / 86400.0
            if age_days < GRACE_PERIOD_DAYS:
                return (DEFAULT_MEAN_MS, DEFAULT_STDDEV_MS)

        # Extract PostgreSQL-compatible day of week (0 = Sunday, 1 = Monday, ..., 6 = Saturday)
        # Python weekday(): Monday=0, Tuesday=1, ..., Sunday=6
        day_of_week = (dt.weekday() + 1) % 7
        hour_of_day = dt.hour

        endpoint_baselines = self._cache.get(endpoint_id)
        if not endpoint_baselines:
            return (DEFAULT_MEAN_MS, DEFAULT_STDDEV_MS)

        bucket_baseline = endpoint_baselines.get((day_of_week, hour_of_day))
        if bucket_baseline is None:
            return (DEFAULT_MEAN_MS, DEFAULT_STDDEV_MS)

        mean, stddev = bucket_baseline
        # Fallback for uniform data or 0 stddev
        effective_stddev = stddev if (stddev is not None and stddev > 0) else DEFAULT_STDDEV_MS
        return (mean, effective_stddev)


# Global singleton instance of BaselineCache
baseline_cache = BaselineCache()


def calculate_z_score(
    latency_ms: float,
    mean_ms: float,
    stddev_ms: float,
) -> float:
    """
    Computes the Z-score for a given latency reading.
    Guarantees DivisionByZero protection when stddev <= 0 or None.
    """
    safe_stddev = stddev_ms if (stddev_ms is not None and stddev_ms > 0) else DEFAULT_STDDEV_MS
    return (latency_ms - mean_ms) / safe_stddev


def is_latency_degraded(
    latency_ms: Optional[float],
    mean_ms: float,
    stddev_ms: float,
    k: float = DEFAULT_K_MULTIPLIER,
) -> bool:
    """
    Evaluates whether a latency reading exceeds the dynamic baseline threshold (mean + k * stddev).
    Returns False if latency_ms is None (e.g. timeout / dropped packet).
    """
    if latency_ms is None:
        return False

    safe_stddev = stddev_ms if (stddev_ms is not None and stddev_ms > 0) else DEFAULT_STDDEV_MS
    threshold = mean_ms + (k * safe_stddev)
    return latency_ms > threshold


async def start_baseline_refresh_task(
    db_session_factory,
    interval_seconds: int = 3600,
) -> asyncio.Task:
    """
    Spawns an async background loop to periodically refresh baseline_cache hourly.
    """

    async def _refresh_loop():
        while True:
            try:
                async with db_session_factory() as db:
                    await baseline_cache.refresh_from_db(db)
            except Exception as e:
                logger.error("Error in baseline refresh background loop: %s", e)
            await asyncio.sleep(interval_seconds)

    task = asyncio.create_task(_refresh_loop())
    return task
