from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.baseline_service import (
    DEFAULT_MEAN_MS,
    DEFAULT_STDDEV_MS,
    BaselineCache,
    calculate_z_score,
    is_latency_degraded,
)
from monitoring.ping import PingResult, classify_ping_result


class TestHybridAdaptiveBaseline(unittest.TestCase):

    def setUp(self) -> None:
        self.cache = BaselineCache()
        self.endpoint_id = uuid4()
        self.now = datetime.now(timezone.utc)

    def test_default_fallback_for_uncached_endpoint(self) -> None:
        mean, stddev = self.cache.get_baseline(self.endpoint_id, self.now)
        self.assertEqual(mean, DEFAULT_MEAN_MS)
        self.assertEqual(stddev, DEFAULT_STDDEV_MS)

    def test_grace_period_fallback_for_new_endpoint(self) -> None:
        # Endpoint onboarded 2 days ago (< 7 days)
        onboarded_time = self.now - timedelta(days=2)
        self.cache._onboarded_dates[self.endpoint_id] = onboarded_time

        # Populate cache with custom baseline
        dow = (self.now.weekday() + 1) % 7
        hour = self.now.hour
        self.cache._cache[self.endpoint_id] = {(dow, hour): (20.0, 5.0)}

        # Should still return default baseline due to 7-day grace period rule
        mean, stddev = self.cache.get_baseline(self.endpoint_id, self.now)
        self.assertEqual(mean, DEFAULT_MEAN_MS)
        self.assertEqual(stddev, DEFAULT_STDDEV_MS)

    def test_baseline_lookup_after_grace_period(self) -> None:
        # Endpoint onboarded 10 days ago (> 7 days)
        onboarded_time = self.now - timedelta(days=10)
        self.cache._onboarded_dates[self.endpoint_id] = onboarded_time

        dow = (self.now.weekday() + 1) % 7
        hour = self.now.hour
        expected_mean, expected_stddev = 25.5, 4.2
        self.cache._cache[self.endpoint_id] = {(dow, hour): (expected_mean, expected_stddev)}

        mean, stddev = self.cache.get_baseline(self.endpoint_id, self.now)
        self.assertEqual(mean, expected_mean)
        self.assertEqual(stddev, expected_stddev)

    def test_z_score_calculation(self) -> None:
        # mean = 50, stddev = 10, reading = 80 -> z = (80 - 50) / 10 = 3.0
        z = calculate_z_score(latency_ms=80.0, mean_ms=50.0, stddev_ms=10.0)
        self.assertAlmostEqual(z, 3.0)

    def test_division_by_zero_protection(self) -> None:
        # Zero stddev must not raise DivisionByZero
        z_zero_stddev = calculate_z_score(latency_ms=100.0, mean_ms=50.0, stddev_ms=0.0)
        self.assertIsInstance(z_zero_stddev, float)

        # None stddev must not raise Exception
        z_none_stddev = calculate_z_score(latency_ms=100.0, mean_ms=50.0, stddev_ms=None)  # type: ignore
        self.assertIsInstance(z_none_stddev, float)

    def test_is_latency_degraded(self) -> None:
        mean, stddev = 30.0, 10.0
        # Threshold = 30 + 3 * 10 = 60.0
        self.assertFalse(is_latency_degraded(latency_ms=50.0, mean_ms=mean, stddev_ms=stddev, k=3.0))
        self.assertFalse(is_latency_degraded(latency_ms=60.0, mean_ms=mean, stddev_ms=stddev, k=3.0))
        self.assertTrue(is_latency_degraded(latency_ms=60.1, mean_ms=mean, stddev_ms=stddev, k=3.0))
        self.assertTrue(is_latency_degraded(latency_ms=100.0, mean_ms=mean, stddev_ms=stddev, k=3.0))

    def test_classify_ping_result_dynamic_baseline(self) -> None:
        # 100% successful ping, but latency = 120ms (baseline mean=30ms, stddev=10ms)
        # Threshold = 30 + 3*10 = 60ms. 120ms > 60ms -> UP, UP-UNSTABLE
        result = PingResult(success_count=10, failed_count=0, avg_rtt_ms=120.0)
        op_state, det_state = classify_ping_result(
            result, baseline_mean=30.0, baseline_stddev=10.0, k=3.0
        )
        self.assertEqual(op_state, "UP")
        self.assertEqual(det_state, "UP-UNSTABLE")

        # Latency within normal bounds (40ms <= 60ms) -> UP, UP
        result_normal = PingResult(success_count=10, failed_count=0, avg_rtt_ms=40.0)
        op_state_n, det_state_n = classify_ping_result(
            result_normal, baseline_mean=30.0, baseline_stddev=10.0, k=3.0
        )
        self.assertEqual(op_state_n, "UP")
        self.assertEqual(det_state_n, "UP")


if __name__ == "__main__":
    unittest.main()
