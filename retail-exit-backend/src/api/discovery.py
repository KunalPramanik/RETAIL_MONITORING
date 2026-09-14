"""Hardware Auto-Discovery & Auto-Connect API Endpoints

Provides RESTful access for:
- Continuous LAN/WiFi auto-discovered cameras & RFID readers.
- One-Tap Lane Confirmation ("This is [Lane X] -> Confirm").
- USB scale & webcam auto-detected ports and unrecognized device management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from src.db.session import get_db
from src.engine.discovery_service import discovery_service, DiscoveredDevice
from src.hardware.usb_detector import usb_service, UsbDeviceRecord
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/discovery", tags=["Hardware Auto-Discovery"])


class ConfirmLaneRequest(BaseModel):
    discoveryId: str = Field(..., description="Unique ID of auto-discovered device")
    laneId: str = Field(..., description="Target exit lane ID to bind this camera/sensor to")
    label: Optional[str] = Field(None, description="Optional custom label for the camera")


class ConfigureUsbRequest(BaseModel):
    port: str = Field(..., description="COM port or serial device path (e.g. COM3 or /dev/ttyUSB0)")
    deviceType: str = Field(..., description="Device type: 'WEIGHT_SCALE' or 'WEBCAM'")
    laneId: Optional[str] = Field("LANE-01", description="Associated lane ID")
    customModel: Optional[str] = Field(None, description="Friendly model description")


class SimulateDiscoveryRequest(BaseModel):
    deviceType: str = Field("CAMERA", description="'CAMERA', 'RFID_GATE', or 'USB'")
    ipAddress: Optional[str] = Field("192.168.1.188", description="IP address for LAN devices")
    port: Optional[str] = Field("COM3", description="Port for USB devices")
    vid: Optional[str] = Field("0403", description="USB Vendor ID")
    pid: Optional[str] = Field("6001", description="USB Product ID")
    manufacturer: Optional[str] = Field("Hikvision", description="Manufacturer")
    model: Optional[str] = Field("DS-2CD2143G0-I", description="Model")
    suggestedLaneId: Optional[str] = Field("LANE-01", description="Suggested lane ID")


@router.get("/devices")
async def list_discovered_devices():
    """Returns all newly auto-discovered network devices awaiting 1-tap lane confirmation."""
    devices = await discovery_service.scan_network()
    return [d.to_dict() for d in devices]


@router.post("/confirm-lane")
async def confirm_lane(
    req: ConfirmLaneRequest,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """The single one-tap confirmation: binds discovered camera/sensor to a physical exit lane."""
    try:
        res = await discovery_service.confirm_lane_assignment(
            session=session,
            discovery_id=req.discoveryId,
            lane_id=req.laneId,
            label=req.label,
        )
        return res
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/usb")
async def list_usb_devices():
    """Returns detected USB hardware (scales, webcams, and unrecognized devices)."""
    devices = usb_service.scan_ports()
    return {
        "activeScalePort": usb_service.active_scale_port,
        "devices": [d.to_dict() for d in devices],
    }


@router.post("/usb/configure")
async def configure_usb(
    req: ConfigureUsbRequest,
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Allows manual configuration of an unrecognized USB device."""
    try:
        dev = usb_service.configure_unrecognized_device(
            port=req.port,
            device_type=req.deviceType,
            lane_id=req.laneId or "LANE-01",
            custom_model=req.customModel,
        )
        return dev.to_dict()
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/scan-now")
async def trigger_scan_now():
    """Triggers an immediate sweep across LAN and USB interfaces."""
    lan_devices = await discovery_service.scan_network()
    usb_devices = usb_service.scan_ports()
    return {
        "lanDevicesDiscovered": len(lan_devices),
        "usbDevicesConnected": len(usb_devices),
        "lanDevices": [d.to_dict() for d in lan_devices],
        "usbDevices": [d.to_dict() for d in usb_devices],
    }


@router.post("/simulate")
async def simulate_discovery(req: SimulateDiscoveryRequest):
    """Simulation helper for automated tests and dev setups."""
    if req.deviceType == "USB":
        dev = usb_service.simulate_usb_event(
            action="ATTACH",
            vid=req.vid or "0403",
            pid=req.pid or "6001",
            port=req.port or "COM3",
            description=req.model or "Simulated USB Scale",
            lane_id=req.suggestedLaneId or "LANE-01",
        )
        return dev.to_dict()
    else:
        dev = discovery_service.simulate_discovered_device(
            ip_address=req.ipAddress or "192.168.1.188",
            manufacturer=req.manufacturer or "Hikvision",
            model=req.model or "1080p Dome Camera",
            device_type=req.deviceType,
            suggested_lane_id=req.suggestedLaneId,
        )
        return dev.to_dict()
