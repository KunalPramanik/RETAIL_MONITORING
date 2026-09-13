"""Tests for Turnstile GPIO Hardware Driver & API"""

import pytest
import asyncio
from src.hardware.turnstile_driver import TurnstileRelayDriver, turnstile_driver


@pytest.mark.asyncio
async def test_turnstile_safety_defaults():
    """Verify that driver initializes in fail-open UNLOCKED state."""
    driver = TurnstileRelayDriver(relay_pin=17, readback_pin=27, auto_unlock_sec=1.0)
    status = driver.get_status()

    assert status["status"] == "UNLOCKED"
    assert status["safetyDefault"] == "UNLOCKED_FAIL_OPEN"
    assert status["physicalReadbackLocked"] is False
    assert status["relayPin"] == 17
    assert status["readbackPin"] == 27


@pytest.mark.asyncio
async def test_turnstile_lock_and_unlock_cycle():
    """Verify locking with readback confirmation and manual unlock."""
    driver = TurnstileRelayDriver(relay_pin=17, readback_pin=27, auto_unlock_sec=10.0)

    # 1. Lock command
    lock_res = await driver.lock(duration_sec=5.0)
    assert lock_res["success"] is True
    assert lock_res["status"] == "LOCKED"
    assert lock_res["readbackConfirmed"] is True

    status = driver.get_status()
    assert status["status"] == "LOCKED"

    # 2. Unlock command
    unlock_res = await driver.unlock()
    assert unlock_res["success"] is True
    assert unlock_res["status"] == "UNLOCKED"

    status_after = driver.get_status()
    assert status_after["status"] == "UNLOCKED"


@pytest.mark.asyncio
async def test_turnstile_auto_unlock_safety_timer():
    """Verify that driver automatically reverts to UNLOCKED after hold duration expires."""
    driver = TurnstileRelayDriver(relay_pin=17, readback_pin=27, auto_unlock_sec=0.2)

    # Lock with 0.2s duration
    await driver.lock(duration_sec=0.2)
    assert driver.get_status()["status"] == "LOCKED"

    # Wait for auto-unlock timeout
    await asyncio.sleep(0.35)

    assert driver.get_status()["status"] == "UNLOCKED"


@pytest.mark.asyncio
async def test_turnstile_cleanup_on_shutdown():
    """Verify that cleanup() safely de-energizes pins into fail-open state."""
    driver = TurnstileRelayDriver(relay_pin=17, readback_pin=27)
    await driver.lock()
    assert driver.get_status()["status"] == "LOCKED"

    driver.cleanup()
    assert driver.get_status()["status"] == "UNLOCKED"

