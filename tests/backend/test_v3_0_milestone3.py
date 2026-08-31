from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.main import app
from app.routers.events import broadcast_sse_event, sse_event_generator
from app.services.topology import topology_manager
from monitoring.ping import PingResult
from monitoring.state_machine import EndpointState, StateMachine
from monitoring.synthetic import (
    run_http_probe,
    run_ssl_probe,
    run_tcp_probe,
    validate_probe_target,
)


class TestMilestone3SSEStream(unittest.TestCase):
    """Test Server-Sent Events (SSE) telemetry stream and heartbeat."""

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_sse_generator_initial_connection_and_broadcast(self) -> None:
        async def _run():
            mock_request = MagicMock()
            mock_request.is_disconnected = AsyncMock(return_value=False)

            gen = sse_event_generator(mock_request)
            first_event = await gen.asend(None)
            self.assertTrue(first_event.startswith("data: "))
            data = json.loads(first_event.replace("data: ", "").strip())
            self.assertEqual(data["type"], "CONNECTED")

            # Broadcast a state transition
            await broadcast_sse_event("STATE_TRANSITION", {
                "endpoint_id": str(uuid4()),
                "operational_state": "UP",
                "detailed_state": "UP-UNSTABLE",
            })

            second_event = await gen.asend(None)
            self.assertTrue(second_event.startswith("data: "))
            data2 = json.loads(second_event.replace("data: ", "").strip())
            self.assertEqual(data2["type"], "STATE_TRANSITION")
            self.assertEqual(data2["detailed_state"], "UP-UNSTABLE")

            await gen.aclose()

        self.loop.run_until_complete(_run())


class TestMilestone3SyntheticProbes(unittest.TestCase):
    """Test multi-protocol reachability probes (TCP, HTTP, SSL) and SSRF defense."""

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_ssrf_validation_blocks_restricted_ips(self) -> None:
        with self.assertRaises(ValueError):
            validate_probe_target("127.0.0.1")

        with self.assertRaises(ValueError):
            validate_probe_target("169.254.169.254")

        with self.assertRaises(ValueError):
            validate_probe_target("::1")

    def test_tcp_probe_ssrf_rejection(self) -> None:
        async def _run():
            res = await run_tcp_probe("127.0.0.1", 80)
            self.assertFalse(res["success"])
            self.assertIn("SSRF Protection", res["error"])

        self.loop.run_until_complete(_run())

    def test_tcp_probe_mock_success(self) -> None:
        async def _run():
            with patch("asyncio.open_connection") as mock_open:
                mock_reader = AsyncMock()
                mock_writer = MagicMock()
                mock_writer.close = MagicMock()
                mock_writer.wait_closed = AsyncMock()
                mock_open.return_value = (mock_reader, mock_writer)

                res = await run_tcp_probe("8.8.8.8", 53)
                self.assertTrue(res["success"])
                self.assertEqual(res["port"], 53)
                self.assertIsNotNone(res["latency_ms"])

        self.loop.run_until_complete(_run())

    def test_http_probe_mock_success(self) -> None:
        async def _run():
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.getcode.return_value = 200
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp

                res = await run_http_probe("https://example.com", expected_status=200)
                self.assertTrue(res["success"])
                self.assertEqual(res["status_code"], 200)
                self.assertIsNotNone(res["latency_ms"])

        self.loop.run_until_complete(_run())

    def test_http_probe_status_mismatch(self) -> None:
        async def _run():
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_resp = MagicMock()
                mock_resp.getcode.return_value = 404
                mock_resp.__enter__.return_value = mock_resp
                mock_urlopen.return_value = mock_resp

                res = await run_http_probe("https://example.com/missing", expected_status=200)
                self.assertFalse(res["success"])
                self.assertEqual(res["status_code"], 404)
                self.assertIn("Expected status 200, got 404", res["error"])

        self.loop.run_until_complete(_run())

    def test_ssl_probe_mock_success(self) -> None:
        async def _run():
            with patch("socket.create_connection") as mock_sock, \
                 patch("ssl.create_default_context") as mock_ctx:

                mock_ssock = MagicMock()
                mock_ssock.getpeercert.return_value = {
                    "notAfter": "Jan 01 00:00:00 2030 GMT"
                }
                mock_ssock.__enter__.return_value = mock_ssock

                mock_ctx_instance = MagicMock()
                mock_ctx_instance.wrap_socket.return_value = mock_ssock
                mock_ctx.return_value = mock_ctx_instance

                res = await run_ssl_probe("example.com", port=443)
                self.assertTrue(res["success"])
                self.assertGreater(res["days_until_expiry"], 100)
                self.assertIsNotNone(res["expires_at"])

        self.loop.run_until_complete(_run())


class TestMilestone3StateMachineTopologyHooks(unittest.TestCase):
    """Test state machine transition hooks triggering topology manager updates and SSE events."""

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_confirmed_transition_invokes_hooks(self) -> None:
        async def _run():
            sm = StateMachine(confirmation_threshold=2)
            ep_id = uuid4()
            event_id = uuid4()

            init_state = EndpointState(
                endpoint_id=ep_id,
                active_event_id=event_id,
                confirmed_operational_state="UP",
                confirmed_detailed_state="UP",
                pending_detailed_state="DOWN",
                pending_cycle_count=1,
            )

            mock_db = AsyncMock()
            mock_row = MagicMock()
            mock_row.id = uuid4()
            mock_res = MagicMock()
            mock_res.fetchone.return_value = mock_row
            mock_db.execute.return_value = mock_res

            ping_result = PingResult(success_count=0, failed_count=5, avg_rtt_ms=None)

            with patch.object(topology_manager, "update_node_status", new_callable=AsyncMock) as mock_top_update, \
                 patch("app.routers.events.broadcast_sse_event", new_callable=AsyncMock) as mock_broadcast:

                next_state = await sm.process_cycle(init_state, ping_result, mock_db)
                self.assertEqual(next_state.confirmed_operational_state, "DOWN")
                self.assertEqual(next_state.confirmed_detailed_state, "DOWN")

                await asyncio.sleep(0.01)
                mock_top_update.assert_called_with(str(ep_id), "DOWN")
                mock_broadcast.assert_called()

        self.loop.run_until_complete(_run())


if __name__ == "__main__":
    unittest.main()
