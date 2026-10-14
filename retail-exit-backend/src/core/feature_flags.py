"""Per-Tenant Dynamic Feature Flag Service.

Enforces Section 1 (P4) and Section 4.1 (A20) of the SEC-OPS V8 Master Prompt:
- Per-tenant flags with safe defaults
- Biometrics default OFF (requires legal review per D7)
- Auto-accept of initial stock default OFF (requires human audit per D5)
- Negative inventory balances default OFF (append-only ledger protection per A15)
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class TenantFeatureFlags(BaseModel):
    """Strongly typed feature flags per company/store tenant."""
    biometrics_enabled: bool = Field(
        default=False,
        description="Facial recognition and biometric matching (strict default OFF per D7)",
    )
    auto_initial_stock_accept: bool = Field(
        default=False,
        description="Automatic acceptance of AI proposed baseline counts (strict default OFF per D5)",
    )
    negative_stock_allowed: bool = Field(
        default=False,
        description="Permit ledger to post negative stock balances (strict default OFF per A15)",
    )
    turnstile_auto_lock_on_high: bool = Field(
        default=True,
        description="Automatically trigger turnstile barrier lock on high-severity exit alarm",
    )
    physical_siren_enabled: bool = Field(
        default=True,
        description="Dispatch physical siren/strobe alarms on confirmed violations",
    )
    dense_shelf_counting_enabled: bool = Field(
        default=True,
        description="Enable multi-layer visual segmentation for stacked material dispatch",
    )
    anti_spoof_poster_suppression: bool = Field(
        default=True,
        description="Suppress false positive detections from static pictures and posters on walls",
    )


class FeatureFlagService:
    """Manages cached feature flags per tenant with database override support."""

    _flags_cache: Dict[str, TenantFeatureFlags] = {}

    @classmethod
    def get_flags(cls, tenant_id: str, overrides: Optional[Dict[str, Any]] = None) -> TenantFeatureFlags:
        """Retrieves active flags for a tenant, applying any custom overrides."""
        if tenant_id not in cls._flags_cache:
            cls._flags_cache[tenant_id] = TenantFeatureFlags()

        current = cls._flags_cache[tenant_id]
        if overrides:
            updated_dict = current.model_dump()
            updated_dict.update({k: v for k, v in overrides.items() if k in updated_dict})
            current = TenantFeatureFlags(**updated_dict)
            cls._flags_cache[tenant_id] = current

        return current

    @classmethod
    def set_flag(cls, tenant_id: str, flag_name: str, value: bool) -> TenantFeatureFlags:
        """Updates a specific feature flag for a tenant."""
        flags = cls.get_flags(tenant_id)
        if hasattr(flags, flag_name):
            data = flags.model_dump()
            data[flag_name] = value
            cls._flags_cache[tenant_id] = TenantFeatureFlags(**data)
        return cls._flags_cache[tenant_id]

    @classmethod
    def clear_cache(cls) -> None:
        """Clears in-memory flags cache."""
        cls._flags_cache.clear()

