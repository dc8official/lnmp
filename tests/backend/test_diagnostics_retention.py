from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock
from app.services.diagnostics import cleanup_old_diagnostic_traces


class TestDiagnosticsRetention(unittest.IsolatedAsyncioTestCase):
    async def test_run_database_retention_cleanup_uses_audit_log_created_at(self) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db.execute.return_value = mock_result

        # Run retention cleanup
        purged = await cleanup_old_diagnostic_traces(
            mock_db, retention_days=30, audit_retention_days=90
        )

        self.assertEqual(purged, 15)  # 5 traces + 5 audit logs + 5 rca incidents
        self.assertEqual(mock_db.execute.call_count, 3)

        # Inspect the queries executed
        calls = mock_db.execute.call_args_list
        stmt_audit = calls[1][0][0]
        # Verify the where clause targets created_at on audit_logs
        compiled_sql = str(stmt_audit)
        self.assertIn("audit_logs.created_at", compiled_sql)
