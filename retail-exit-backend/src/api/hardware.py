"""Hardware Device Controllers & Edge Driver API Routes"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Dict, Any, Optional

from src.hardware.turnstile_driver import turnstile_driver
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/hardware", tags=["Hardware"])


@router.get("/turnstile/status")
async def get_turnstile_status() -> Dict[str, Any]:
    """Returns live hardware state and readback confirmation of the lane turnstile barrier."""
    return turnstile_driver.get_status()


@router.post("/turnstile/lock")
async def lock_turnstile(
    duration_sec: Optional[float] = Query(30.0, ge=1.0, le=300.0),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
) -> Dict[str, Any]:
    """Commands turnstile drop-arm relay to lock with mechanical readback verification."""
    result = await turnstile_driver.lock(duration_sec=duration_sec)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result)
    return result


@router.post("/turnstile/unlock")
async def unlock_turnstile(
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
) -> Dict[str, Any]:
    """Commands turnstile drop-arm relay to return to safe fail-open unlocked state."""
    result = await turnstile_driver.unlock()
    return result

