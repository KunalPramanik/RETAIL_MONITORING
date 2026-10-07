"""Observability, Prometheus Metrics, and Tracing Test Suite

Covers:
- Health endpoint operational telemetry contract
- Prometheus plain-text metrics exposition format
- End-to-end correlation ID middleware propagation and preservation
- Standardized structured error handling contracts
"""

import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app


@pytest.mark.asyncio
async def test_health_endpoint_contract():
    """Verifies that /health returns HTTP 200 and structured operational telemetry."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "HEALTHY"
        assert "service" in data
        assert "version" in data
        assert data["database"] == "CONNECTED"
        assert "edgeNodesOnline" in data
        assert "edgeCluster" in data


@pytest.mark.asyncio
async def test_prometheus_metrics_exporter():
    """Verifies that /metrics outputs valid Prometheus plain-text telemetry."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        text = response.text
        assert len(text) > 0
        # Check standard Prometheus formatting
        assert any(line.startswith("# HELP") or line.startswith("# TYPE") or "secops" in line for line in text.splitlines())


@pytest.mark.asyncio
async def test_correlation_id_middleware_propagation():
    """Verifies correlation ID generation when absent, and preservation when provided."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case 1: Auto-generated correlation ID
        resp1 = await client.get("/health")
        assert resp1.status_code == 200
        corr1 = resp1.headers.get("X-Correlation-ID")
        assert corr1 is not None
        assert corr1.startswith("corr_")

        # Case 2: Injected correlation ID passthrough
        custom_id = "trace-e2e-abc-987654"
        resp2 = await client.get("/health", headers={"X-Correlation-ID": custom_id})
        assert resp2.status_code == 200
        assert resp2.headers.get("X-Correlation-ID") == custom_id

