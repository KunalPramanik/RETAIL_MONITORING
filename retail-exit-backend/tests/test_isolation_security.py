"""Automated Verification Suite for Phase 1 Foundations.

Tests:
- Feature flags with safe defaults (P4, A20, D5, D7)
- Distinct identifier namespace separation (P8)
- CPU benchmark harness telemetry (WP-S10.2)
- Multi-tenant isolation boundary check (P2, G12, WP-S1.2)
"""

import pytest
from src.core.feature_flags import FeatureFlagService, TenantFeatureFlags
from src.core.identifiers import (
    generate_employee_code,
    generate_user_id,
    generate_camera_track_id,
    generate_product_id,
    generate_invoice_id,
    generate_event_id,
    generate_ledger_id,
    generate_idempotency_key,
)
from src.engine.benchmark_harness import CPUBenchmarkHarness


def test_feature_flags_safe_defaults():
    """Verify that default feature flags protect the system (Biometrics OFF, Auto-Accept OFF)."""
    flags = FeatureFlagService.get_flags("test-tenant-001")
    assert flags.biometrics_enabled is False, "Biometrics must be default OFF per D7"
    assert flags.auto_initial_stock_accept is False, "Auto-accept initial stock must be default OFF per D5"
    assert flags.negative_stock_allowed is False, "Negative stock must be default OFF per A15"
    assert flags.turnstile_auto_lock_on_high is True
    assert flags.physical_siren_enabled is True


def test_feature_flags_tenant_override():
    """Verify that per-tenant overrides do not leak to other tenants."""
    FeatureFlagService.clear_cache()
    tenant_a = FeatureFlagService.get_flags("tenant-A", overrides={"biometrics_enabled": True})
    tenant_b = FeatureFlagService.get_flags("tenant-B")

    assert tenant_a.biometrics_enabled is True
    assert tenant_b.biometrics_enabled is False, "Tenant A override must not leak to Tenant B"


def test_distinct_identifier_namespaces():
    """Verify distinct identifier generation across separate business domains."""
    emp = generate_employee_code(101)
    user = generate_user_id()
    trk = generate_camera_track_id("cam-dock-01", 12)
    prod = generate_product_id()
    inv = generate_invoice_id()
    evt = generate_event_id()
    led = generate_ledger_id()

    assert emp.startswith("EMP-000101")
    assert trk.startswith("trk_camdock0_12")
    assert len(user) == 36
    assert len(prod) == 36
    assert len(inv) == 36
    assert len(evt) == 36
    assert len(led) == 36

    # Verify all generated IDs are mutually distinct
    all_ids = [emp, user, trk, prod, inv, evt, led]
    assert len(set(all_ids)) == len(all_ids)


def test_idempotency_key_reproducibility():
    """Verify that same composite inputs yield identical idempotency keys, different inputs differ."""
    k1 = generate_idempotency_key("MOV", "cam-1", "track-5", "2026-10-15T00:00:00Z")
    k2 = generate_idempotency_key("MOV", "cam-1", "track-5", "2026-10-15T00:00:00Z")
    k3 = generate_idempotency_key("MOV", "cam-1", "track-6", "2026-10-15T00:00:00Z")

    assert k1 == k2
    assert k1 != k3


def test_cpu_benchmark_harness():
    """Verify that the benchmark harness runs cleanly on CPU with zero GPU dependencies."""
    result = CPUBenchmarkHarness.run_benchmark(num_frames=10, resolution=(320, 240), simulate_cameras=2)

    assert result["cpu_compatible"] is True
    assert result["gpu_required"] is False
    assert result["total_frames_processed"] == 20
    assert result["effective_fps"] > 0
    assert result["latency_p50_ms"] >= 0
    assert result["latency_p95_ms"] >= 0
    assert "admission_control_status" in result

