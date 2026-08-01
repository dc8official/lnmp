from __future__ import annotations

import re
import pytest
from app.services.auth_service import generate_readable_password
from app.routers.reports import telemetry_router


def test_readable_password_format():
    password = generate_readable_password()
    assert re.match(r"^[A-Z][a-z]+-\d{3}$", password), f"Unexpected format: {password}"


def test_telemetry_router_prefix():
    assert telemetry_router.prefix == "/api/v1/telemetry"
