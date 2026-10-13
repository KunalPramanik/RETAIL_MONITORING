"""Physical & Network Siren Hardware Adapter

Controls audible and visual alarm sirens on edge retail controllers and IoT gateways.
Enforces safety-first defaults: SILENCED / FAIL-SAFE on boot, shutdown, power loss, or crash.
Supports:
1. Physical GPIO Relay (e.g., Raspberry Pi edge controllers)
2. HTTP / REST IoT Siren webhook triggers with rate limiting and timeout safeguards
3. Safe EMULATED mode on standard servers / non-GPIO host operating systems
"""

import os
import sys
import time
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("secops.hardware.siren")

# Configuration via environment variables
DEFAULT_SIREN_RELAY_PIN = int(os.getenv("SIREN_RELAY_PIN", "18"))
DEFAULT_SIREN_DURATION_SEC = float(os.getenv("SIREN_DEFAULT_DURATION_SEC", "10.0"))
DEFAULT_SIREN_MAX_DURATION_SEC = float(os.getenv("SIREN_MAX_DURATION_SEC", "60.0"))
DEFAULT_SIREN_MIN_INTERVAL_SEC = float(os.getenv("SIREN_MIN_INTERVAL_SEC", "5.0"))
SIREN_HTTP_URL = os.getenv("SIREN_HTTP_URL", "")
SIREN_HTTP_AUTH_BEARER = os.getenv("SIREN_HTTP_AUTH_BEARER", "")
SIREN_HTTP_TIMEOUT_SEC = float(os.getenv("SIREN_HTTP_TIMEOUT_SEC", "3.0"))


class PhysicalSirenAdapter:
    """Hardware Siren Controller with safety-first defaults, rate limiting, and fail-safe timeouts."""

    _instance: Optional["PhysicalSirenAdapter"] = None

    def __init__(
        self,
        relay_pin: int = DEFAULT_SIREN_RELAY_PIN,
        default_duration_sec: float = DEFAULT_SIREN_DURATION_SEC,
        min_interval_sec: float = DEFAULT_SIREN_MIN_INTERVAL_SEC,
    ):
        self.relay_pin = relay_pin
        self.default_duration_sec = default_duration_sec
        self.min_interval_sec = min_interval_sec

        # State tracking: Always initialize as SILENCED (Safety-first default)
        self.is_active = False
        self.last_triggered_at: Optional[float] = None
        self.last_silenced_at: Optional[float] = None
        self.last_reason: Optional[str] = None
        self.hardware_mode = "UNKNOWN"
        self._auto_silence_task: Optional[asyncio.Task] = None
        self._rpi_gpio = None

        self._init_hardware()

    @classmethod
    def get_instance(cls) -> "PhysicalSirenAdapter":
        """Singleton accessor for the physical siren adapter."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_hardware(self) -> None:
        """Attempts to initialize physical GPIO; falls back gracefully to emulated mode."""
        try:
            import RPi.GPIO as GPIO  # type: ignore

            self._rpi_gpio = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Safety setup: Relay pin set to OUTPUT, initially LOW (de-energized / SILENCED)
            GPIO.setup(self.relay_pin, GPIO.OUT, initial=GPIO.LOW)

            self.hardware_mode = "HARDWARE_RPI_GPIO"
            logger.info(
                f"Physical siren GPIO initialized on BCM relay={self.relay_pin}. Default: SILENCED (fail-safe)."
            )
        except (ImportError, RuntimeError, Exception) as e:
            self._rpi_gpio = None
            if SIREN_HTTP_URL:
                self.hardware_mode = "NETWORK_HTTP_SIREN"
                logger.info(
                    f"Physical GPIO unavailable ({e}). Siren configured via network webhook: {SIREN_HTTP_URL}."
                )
            else:
                self.hardware_mode = "EMULATED_NON_GPIO"
                platform_name = sys.platform
                logger.info(
                    f"Physical GPIO unavailable on {platform_name} ({e}). Running Siren in safe EMULATED mode. Default: SILENCED."
                )

    async def trigger_siren(
        self,
        duration_sec: Optional[float] = None,
        reason: str = "HIGH_SEVERITY_ALERT",
    ) -> Dict[str, Any]:
        """Activates the siren for a bounded duration with safety rate limiting."""
        now_ts = time.time()
        dur = min(
            duration_sec if duration_sec is not None else self.default_duration_sec,
            DEFAULT_SIREN_MAX_DURATION_SEC,
        )

        # Rate limiting check: prevent continuous thrashing
        if self.last_triggered_at and (now_ts - self.last_triggered_at < self.min_interval_sec):
            logger.warning(
                f"Siren trigger rate-limited: requested within {self.min_interval_sec}s of previous trigger."
            )
            return {
                "success": True,
                "status": "RATE_LIMITED",
                "active": self.is_active,
                "hardwareMode": self.hardware_mode,
                "message": f"Siren already engaged or rate-limited ({reason})",
            }

        self.last_triggered_at = now_ts
        self.last_reason = reason
        self.is_active = True

        # Cancel any existing auto-silence countdown
        if self._auto_silence_task and not self._auto_silence_task.done():
            self._auto_silence_task.cancel()

        exec_status = "SUCCESS"
        error_msg = None

        if self.hardware_mode == "HARDWARE_RPI_GPIO" and self._rpi_gpio:
            try:
                self._rpi_gpio.output(self.relay_pin, self._rpi_gpio.HIGH)
                logger.warning(f"PHYSICAL SIREN ENERGIZED on BCM {self.relay_pin} for {dur}s: {reason}")
            except Exception as e:
                exec_status = "ERROR"
                error_msg = str(e)
                logger.error(f"GPIO siren activation failed: {e}")

        elif self.hardware_mode == "NETWORK_HTTP_SIREN" and SIREN_HTTP_URL:
            try:
                import httpx
                headers = {"Content-Type": "application/json"}
                if SIREN_HTTP_AUTH_BEARER:
                    headers["Authorization"] = f"Bearer {SIREN_HTTP_AUTH_BEARER}"

                payload = {
                    "action": "TRIGGER",
                    "durationSec": dur,
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                async with httpx.AsyncClient(timeout=SIREN_HTTP_TIMEOUT_SEC) as client:
                    resp = await client.post(SIREN_HTTP_URL, json=payload, headers=headers)
                    resp.raise_for_status()
                logger.warning(f"NETWORK SIREN TRIGGERED at {SIREN_HTTP_URL} for {dur}s: {reason}")
            except Exception as e:
                exec_status = "NETWORK_ERROR"
                error_msg = str(e)
                logger.error(f"Network siren activation failed: {e}")

        else:
            logger.warning(f"[EMULATED SIREN] Activating audible siren for {dur}s: {reason}")

        # Schedule automatic bounded shutoff
        self._auto_silence_task = asyncio.create_task(self._auto_silence_countdown(dur))

        return {
            "success": exec_status != "ERROR",
            "status": exec_status,
            "active": self.is_active,
            "durationSec": dur,
            "hardwareMode": self.hardware_mode,
            "reason": reason,
            "error": error_msg,
        }

    async def _auto_silence_countdown(self, duration_sec: float) -> None:
        """Background countdown task ensuring siren is de-energized even if caller dies."""
        try:
            await asyncio.sleep(duration_sec)
            await self.silence_siren()
            logger.info(f"Siren auto-silenced after {duration_sec}s timeout.")
        except asyncio.CancelledError:
            pass

    async def silence_siren(self) -> Dict[str, Any]:
        """Immediately de-energizes the siren relay (Fail-safe state)."""
        self.is_active = False
        self.last_silenced_at = time.time()

        if self._auto_silence_task and not self._auto_silence_task.done():
            self._auto_silence_task.cancel()
            self._auto_silence_task = None

        exec_status = "SUCCESS"
        error_msg = None

        if self.hardware_mode == "HARDWARE_RPI_GPIO" and self._rpi_gpio:
            try:
                self._rpi_gpio.output(self.relay_pin, self._rpi_gpio.LOW)
                logger.info(f"PHYSICAL SIREN DE-ENERGIZED (Silenced) on BCM {self.relay_pin}")
            except Exception as e:
                exec_status = "ERROR"
                error_msg = str(e)
                logger.error(f"GPIO siren silence failed: {e}")

        elif self.hardware_mode == "NETWORK_HTTP_SIREN" and SIREN_HTTP_URL:
            try:
                import httpx
                headers = {"Content-Type": "application/json"}
                if SIREN_HTTP_AUTH_BEARER:
                    headers["Authorization"] = f"Bearer {SIREN_HTTP_AUTH_BEARER}"

                payload = {
                    "action": "SILENCE",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                async with httpx.AsyncClient(timeout=SIREN_HTTP_TIMEOUT_SEC) as client:
                    await client.post(SIREN_HTTP_URL, json=payload, headers=headers)
                logger.info(f"NETWORK SIREN SILENCED at {SIREN_HTTP_URL}")
            except Exception as e:
                exec_status = "NETWORK_ERROR"
                error_msg = str(e)
                logger.error(f"Network siren silence failed: {e}")

        else:
            logger.info("[EMULATED SIREN] Siren silenced.")

        return {
            "success": exec_status != "ERROR",
            "status": exec_status,
            "active": False,
            "hardwareMode": self.hardware_mode,
            "error": error_msg,
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns the current operational status of the siren subsystem."""
        return {
            "active": self.is_active,
            "hardwareMode": self.hardware_mode,
            "relayPin": self.relay_pin,
            "defaultDurationSec": self.default_duration_sec,
            "lastTriggeredAt": (
                datetime.fromtimestamp(self.last_triggered_at, tz=timezone.utc).isoformat()
                if self.last_triggered_at
                else None
            ),
            "lastSilencedAt": (
                datetime.fromtimestamp(self.last_silenced_at, tz=timezone.utc).isoformat()
                if self.last_silenced_at
                else None
            ),
            "lastReason": self.last_reason,
        }


# Global Singleton Instance
siren_adapter = PhysicalSirenAdapter.get_instance()

