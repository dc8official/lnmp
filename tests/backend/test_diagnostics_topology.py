from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.diagnostics import run_traceroute


class TestDiagnosticsAndTopology(unittest.TestCase):

    @patch("asyncio.create_subprocess_exec")
    def test_run_traceroute_parsing(self, mock_exec: MagicMock) -> None:
        sample_output = (
            "traceroute to 10.0.0.5 (10.0.0.5), 30 hops max, 60 byte packets\n"
            " 1  192.168.1.1  1.123 ms  1.045 ms  0.980 ms\n"
            " 2  10.254.0.1  12.450 ms  11.890 ms  12.100 ms\n"
            " 3  * * *\n"
            " 4  10.0.0.5  25.600 ms  24.800 ms  25.100 ms\n"
        )

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (sample_output.encode("utf-8"), b"")
        mock_exec.return_value = mock_proc

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_traceroute("10.0.0.5"))
        loop.close()

        self.assertEqual(result["target_ip"], "10.0.0.5")
        hops = result["hops"]
        self.assertEqual(len(hops), 4)

        # Hop 1
        self.assertEqual(hops[0]["hop"], 1)
        self.assertEqual(hops[0]["ip"], "192.168.1.1")
        self.assertAlmostEqual(hops[0]["rtt_ms"], 1.049, places=2)

        # Hop 2
        self.assertEqual(hops[1]["hop"], 2)
        self.assertEqual(hops[1]["ip"], "10.254.0.1")

        # Hop 3 (Unresponsive)
        self.assertEqual(hops[2]["hop"], 3)
        self.assertIsNone(hops[2]["ip"])
        self.assertIsNone(hops[2]["rtt_ms"])

        # Hop 4
        self.assertEqual(hops[3]["hop"], 4)
        self.assertEqual(hops[3]["ip"], "10.0.0.5")

    def test_inferred_down_rca_logic(self) -> None:
        # Test topology tree logic where transit node has 100% downstream monitored nodes DOWN
        from app.services.topology import get_topology_graph

        # Mock DB session returns 1 transit node and 2 monitored endpoints downstream that are both DOWN
        ep1_id = uuid4()
        ep2_id = uuid4()

        ep_rows = [
            MagicMock(
                id=ep1_id,
                hostname="node-1",
                ip_address="10.0.0.1",
                device_type="SERVER",
                location="DC1",
                endpoint_status="ACTIVE",
                allow_topology_discovery=True,
                manual_parent_id=None,
                operational_state="DOWN",
                detailed_state="DOWN",
            ),
            MagicMock(
                id=ep2_id,
                hostname="node-2",
                ip_address="10.0.0.2",
                device_type="SERVER",
                location="DC1",
                endpoint_status="ACTIVE",
                allow_topology_discovery=True,
                manual_parent_id=None,
                operational_state="DOWN",
                detailed_state="DOWN",
            ),
        ]

        trace_data = {
            "target_ip": "10.0.0.1",
            "hops": [
                {"hop": 1, "ip": "192.168.100.1", "rtt_ms": 2.0},  # Transit
                {"hop": 2, "ip": "10.0.0.1", "rtt_ms": 5.0},
            ],
        }

        mock_db = AsyncMock()
        ep_result = MagicMock()
        ep_result.fetchall.return_value = ep_rows

        tr_result = MagicMock()
        tr_result.fetchall.return_value = [
            MagicMock(endpoint_id=ep1_id, trace_data=trace_data),
            MagicMock(endpoint_id=ep2_id, trace_data=trace_data),
        ]

        mock_db.execute.side_effect = [ep_result, tr_result]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        graph = loop.run_until_complete(get_topology_graph(mock_db))
        loop.close()

        nodes = {n["id"]: n for n in graph["nodes"]}
        self.assertIn("transit:192.168.100.1", nodes)
        transit_node = nodes["transit:192.168.100.1"]

        # Since 100% of downstream monitored nodes (node-1 and node-2) are DOWN, transit node must be INFERRED_DOWN
        self.assertEqual(transit_node["status"], "INFERRED_DOWN")
        self.assertEqual(transit_node["node_type"], "transit")


if __name__ == "__main__":
    unittest.main()
