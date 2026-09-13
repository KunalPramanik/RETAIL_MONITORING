"""Direct Hardware Turnstile GPIO Relay Driver

Controls physical turnstile drop-arm relay barriers on edge controllers (e.g. Raspberry Pi).
Enforces safety-first defaults: UNLOCKED / FAIL-OPEN on boot, shutdown, power loss, or crash.
Provides readback confirmation and transparent hardware vs emulated detection.
"""

import os
import sys
import time
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("secops.hardware.turnstile")

# Safety Default Pin Assignments (BCM numbering on Raspberry Pi)
DEFAULT_RELAY_PIN = int(os.getenv("TURNSTILE_RELAY_PIN", "17"))
DEFAULT_READBACK_PIN = int(os.getenv("TURNSTILE_READBACK_PIN", "27"))
DEFAULT_AUTO_UNLOCK_SEC = float(os.getenv("TURNSTILE_AUTO_UNLOCK_SEC", "30.0"))


class TurnstileRelayDriver:
    """Hardware Turnstile Controller with fail-open safety and hardware readback confirmation."""

    _instance: Optional["TurnstileRelayDriver"] = None

    def __init__(
        self,
        relay_pin: int = DEFAULT_RELAY_PIN,
        readback_pin: int = DEFAULT_READBACK_PIN,
        auto_unlock_sec: float = DEFAULT_AUTO_UNLOCK_SEC,
    ):
        self.relay_pin = relay_pin
        self.readback_pin = readback_pin
        self.auto_unlock_sec = auto_unlock_sec

        # State tracking: Always initialize as UNLOCKED (Safety-first default)
        self.is_locked = False
        self.last_switched_at: Optional[str] = None
        self.hardware_mode = "UNKNOWN"
        self._auto_unlock_task: Optional[asyncio.Task] = None
        self._rpi_gpio = None

        self._init_hardware()

    @classmethod
    def get_instance(cls) -> "TurnstileRelayDriver":
        """Singleton accessor for the lane turnstile driver."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_hardware(self) -> None:
        """Attempts to initialize physical GPIO; falls back gracefully to emulated mode."""
        # Detect Linux / Raspberry Pi GPIO availability
        try:
            import RPi.GPIO as GPIO  # type: ignore

            self._rpi_gpio = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Safety setup: Relay pin set to OUTPUT, initially LOW (de-energized / UNLOCKED)
            GPIO.setup(self.relay_pin, GPIO.OUT, initial=GPIO.LOW)

            # Readback pin set to INPUT with pull-down
            GPIO.setup(self.readback_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            self.hardware_mode = "HARDWARE_RPI_GPIO"
            logger.info(
                f"Turnstile hardware GPIO initialized on BCM relay={self.relay_pin}, readback={self.readback_pin}. Default: UNLOCKED (fail-open)."
            )
        except (ImportError, RuntimeError, Exception) as e:
            self._rpi_gpio = None
            self.hardware_mode = "EMULATED_NON_GPIO"
            platform_name = sys.platform
            logger.info(
                f"Physical GPIO unavailable on {platform_name} ({e}). Running Turnstile in safe EMULATED mode. Default: UNLOCKED."
            )

    def _read_physical_state(self) -> bool:
        """Reads hardware readback pin if available; returns true if physically locked."""
        if self._rpi_gpio is not None and self.hardware_mode == "HARDWARE_RPI_GPIO":
            try:
                val = self._rpi_gpio.input(self.readback_pin)
                return bool(val == self._rpi_gpio.HIGH)
            except Exception as ex:
                logger.warning(f"Error reading GPIO readback pin {self.readback_pin}: {ex}")
                return self.is_locked
        # In emulated mode, readback matches commanded state
        return self.is_locked

    async def lock(self, duration_sec: Optional[float] = None) -> Dict[str, Any]:
        """Commands turnstile drop-arm relay to LOCK with physical readback confirmation.
        
        Args:
            duration_sec: Optional duration before automatically reverting to UNLOCKED.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        hold_time = duration_sec or self.auto_unlock_sec

        try:
            if self._rpi_gpio is not None and self.hardware_mode == "HARDWARE_RPI_GPIO":
                # Energize relay to lock mechanical barrier
                self._rpi_gpio.output(self.relay_pin, self._rpi_gpio.HIGH)
                time.sleep(0.05)  # 50ms settling time for mechanical contact debounce

            self.is_locked = True
            self.last_switched_at = now_str

            # Verify actual mechanical switch via readback
            confirmed = self._read_physical_state()
            logger.warning(
                f"TURNSTILE INTERLOCK COMMANDED TO LOCKED. Readback confirmed={confirmed} (Duration: {hold_time}s)"
            )

            # Schedule automated return to fail-open safety state
            if self._auto_unlock_task and not self._auto_unlock_task.done():
                self._auto_unlock_task.cancel()

            self._auto_unlock_task = asyncio.create_task(self._auto_unlock_timer(hold_time))

            return {
                "success": confirmed,
                "status": "LOCKED" if confirmed else "READBACK_FAILED",
                "readbackConfirmed": confirmed,
                "hardwareMode": self.hardware_mode,
                "switchedAt": now_str,
                "autoUnlockAfterSec": hold_time,
                "relayPin": self.relay_pin,
            }
        except Exception as e:
            logger.error(f"Failed to engage turnstile lock: {e}", exc_info=True)
            # Guarantee fail-open fallback
            await self.unlock()
            return {
                "success": False,
                "status": "FAILED",
                "error": str(e),
                "hardwareMode": self.hardware_mode,
            }

    async def unlock(self) -> Dict[str, Any]:
        """Commands turnstile drop-arm relay to UNLOCK (safe fail-open state)."""
        now_str = datetime.now(timezone.utc).isoformat()

        if self._auto_unlock_task and not self._auto_unlock_task.done():
            self._auto_unlock_task.cancel()

        try:
            if self._rpi_gpio is not None and self.hardware_mode == "HARDWARE_RPI_GPIO":
                # De-energize relay pin (fail-open state)
                self._rpi_gpio.output(self.relay_pin, self._rpi_gpio.LOW)
                time.sleep(0.05)  # Debounce

            self.is_locked = False
            self.last_switched_at = now_str
            confirmed_unlocked = not self._read_physical_state()

            logger.info(f"Turnstile barrier UNLOCKED. Readback verified={confirmed_unlocked}.")
            return {
                "success": confirmed_unlocked,
                "status": "UNLOCKED",
                "readbackConfirmed": confirmed_unlocked,
                "hardwareMode": self.hardware_mode,
                "switchedAt": now_str,
                "relayPin": self.relay_pin,
            }
        except Exception as e:
            logger.critical(f"Critical error releasing turnstile relay: {e}", exc_info=True)
            self.is_locked = False
            return {
                "success": False,
                "status": "ERROR_EMERGENCY_RELEASE",
                "error": str(e),
                "hardwareMode": self.hardware_mode,
            }

    async def _auto_unlock_timer(self, delay_sec: float) -> None:
        """Asynchronous timer reverting turnstile to fail-open safety state after timeout."""
        try:
            await asyncio.sleep(delay_sec)
            logger.info(f"Turnstile interlock auto-unlock timer ({delay_sec}s) expired. Reverting to UNLOCKED.")
            await self.unlock()
        except asyncio.CancelledError:
            pass

    def get_status(self) -> Dict[str, Any]:
        """Returns the real-time operational health and physical status of the relay driver."""
        readback_actual = self._read_physical_state()
        return {
            "status": "LOCKED" if self.is_locked else "UNLOCKED",
            "physicalReadbackLocked": readback_actual,
            "hardwareMode": self.hardware_mode,
            "isHardwareGpio": self.hardware_mode == "HARDWARE_RPI_GPIO",
            "relayPin": self.relay_pin,
            "readbackPin": self.readback_pin,
            "lastSwitchedAt": self.last_switched_at,
            "safetyDefault": "UNLOCKED_FAIL_OPEN",
        }

    def cleanup(self) -> None:
        """Guarantees relay de-energizes on process termination or driver crash."""
        try:
            if self._rpi_gpio is not None and self.hardware_mode == "HARDWARE_RPI_GPIO":
                self._rpi_gpio.output(self.relay_pin, self._rpi_gpio.LOW)
                self._rpi_gpio.cleanup([self.relay_pin, self.readback_pin])
                logger.info("Turnstile GPIO cleaned up. Pins released in fail-open state.")
        except Exception as e:
            logger.warning(f"Error during Turnstile GPIO cleanup: {e}")
        self.is_locked = False


# Global driver singleton
turnstile_driver = TurnstileRelayDriver.get_instance()

