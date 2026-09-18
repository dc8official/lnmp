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
