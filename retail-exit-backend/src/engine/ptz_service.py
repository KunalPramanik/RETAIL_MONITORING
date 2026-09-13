"""PTZ (Pan-Tilt-Zoom) Camera Service & ONVIF Protocol Controller

Provides continuous, relative, and preset movement controls for PTZ-capable cameras
while cleanly rejecting commands on fixed cameras with 422 Unprocessable Entity.
Zero database schema changes: relies on camera attributes and runtime capability registry.
"""

from typing import Dict, Any, Optional, Tuple
import asyncio
import time
import logging

logger = logging.getLogger("secops.ptz")


class PTZNotSupportedError(ValueError):
    """Raised when a PTZ command is issued to a non-PTZ fixed camera."""
    pass


class PTZCameraState:
    """Represents the real-time physical/simulated position and status of a PTZ camera."""

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.pan: float = 0.0      # -1.0 (full left) to +1.0 (full right)
        self.tilt: float = 0.0     # -1.0 (full down) to +1.0 (full up)
        self.zoom: float = 1.0     # 1.0 (wide) to 10.0 (max optical zoom)
        self.is_moving: bool = False
        self.last_command_ts: float = time.time()
        self.active_preset_id: Optional[int] = None
        self.presets: Dict[int, Dict[str, Any]] = {
            1: {"name": "Lane Overhead Full View", "pan": 0.0, "tilt": -0.3, "zoom": 1.0},
            2: {"name": "Pedestal/Turnstile Close-Up", "pan": 0.2, "tilt": -0.6, "zoom": 2.5},
            3: {"name": "Conveyor Face / ID Angle", "pan": -0.4, "tilt": -0.2, "zoom": 3.0},
            4: {"name": "Ambient Wide", "pan": 0.0, "tilt": 0.0, "zoom": 1.0},
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cameraId": self.camera_id,
            "pan": round(self.pan, 3),
            "tilt": round(self.tilt, 3),
            "zoom": round(self.zoom, 2),
            "isMoving": self.is_moving,
            "activePresetId": self.active_preset_id,
            "availablePresets": [
                {"presetId": pid, "name": p["name"], "pan": p["pan"], "tilt": p["tilt"], "zoom": p["zoom"]}
                for pid, p in self.presets.items()
            ],
        }


class PTZService:
    """Manages PTZ operations, ONVIF communication, and state tracking for the camera fleet."""

    def __init__(self):
        self._camera_states: Dict[str, PTZCameraState] = {}
        self._ptz_capable_ids: set[str] = set()
        self._motion_tasks: Dict[str, asyncio.Task] = {}

    def register_ptz_capability(self, camera_id: str, is_capable: bool = True):
        """Explicitly registers or unregisters a camera's PTZ capability at runtime."""
        if is_capable:
            self._ptz_capable_ids.add(camera_id)
            if camera_id not in self._camera_states:
                self._camera_states[camera_id] = PTZCameraState(camera_id)
        else:
            self._ptz_capable_ids.discard(camera_id)
            self._camera_states.pop(camera_id, None)

    def is_ptz_capable(self, camera: Any) -> bool:
        """Determines if a camera supports PTZ based on label, RTSP path, or explicit registration.
        
        Zero DB change: uses existing camera.label and camera.rtsp_path fields.
        """
        if not camera:
            return False

        cam_id = str(getattr(camera, "camera_id", ""))
        if cam_id in self._ptz_capable_ids:
            return True

        label = str(getattr(camera, "label", "")).lower()
        rtsp = str(getattr(camera, "rtsp_path", "")).lower()

        # Keywords indicating PTZ capability
        ptz_keywords = ["ptz", "dome", "speed dome", "pan-tilt", "pantilt", "overhead-zoom", "hand-off"]
        for kw in ptz_keywords:
            if kw in label or kw in rtsp:
                # Auto-register state
                self._ptz_capable_ids.add(cam_id)
                if cam_id not in self._camera_states:
                    self._camera_states[cam_id] = PTZCameraState(cam_id)
                return True

        return False

    def _get_state(self, camera_id: str) -> PTZCameraState:
        if camera_id not in self._camera_states:
            self._camera_states[camera_id] = PTZCameraState(camera_id)
        return self._camera_states[camera_id]

    async def continuous_move(
        self,
        camera: Any,
        pan_velocity: float = 0.0,
        tilt_velocity: float = 0.0,
        zoom_velocity: float = 0.0,
        duration_sec: float = 0.5,
    ) -> Dict[str, Any]:
        """Executes an ONVIF-compatible ContinuousMove command.
        
        Raises PTZNotSupportedError if camera is fixed.
        """
        if not self.is_ptz_capable(camera):
            raise PTZNotSupportedError("Camera is fixed, does not support PTZ")

        cam_id = str(camera.camera_id)
        state = self._get_state(cam_id)

        # Cancel any ongoing motion task
        if cam_id in self._motion_tasks and not self._motion_tasks[cam_id].done():
            self._motion_tasks[cam_id].cancel()

        state.is_moving = True
        state.last_command_ts = time.time()
        state.active_preset_id = None

        # Clamp and apply velocity delta
        state.pan = max(-1.0, min(1.0, state.pan + pan_velocity * 0.2))
        state.tilt = max(-1.0, min(1.0, state.tilt + tilt_velocity * 0.2))
        state.zoom = max(1.0, min(10.0, state.zoom + zoom_velocity * 0.5))

        async def _finish_motion():
            try:
                await asyncio.sleep(duration_sec)
                state.is_moving = False
            except asyncio.CancelledError:
                pass

        self._motion_tasks[cam_id] = asyncio.create_task(_finish_motion())

        logger.info(
            f"PTZ Move on {cam_id}: pan={state.pan:.2f}, tilt={state.tilt:.2f}, zoom={state.zoom:.1f} (is_moving={state.is_moving})"
        )
        return state.to_dict()

    async def stop(self, camera: Any) -> Dict[str, Any]:
        """Stops ongoing PTZ motion."""
        if not self.is_ptz_capable(camera):
            raise PTZNotSupportedError("Camera is fixed, does not support PTZ")

        cam_id = str(camera.camera_id)
        state = self._get_state(cam_id)

        if cam_id in self._motion_tasks and not self._motion_tasks[cam_id].done():
            self._motion_tasks[cam_id].cancel()

        state.is_moving = False
        logger.info(f"PTZ Stop on {cam_id}")
        return state.to_dict()

    async def goto_preset(self, camera: Any, preset_id: int) -> Dict[str, Any]:
        """Moves PTZ to a defined preset location (1..4)."""
        if not self.is_ptz_capable(camera):
            raise PTZNotSupportedError("Camera is fixed, does not support PTZ")

        cam_id = str(camera.camera_id)
        state = self._get_state(cam_id)

        if preset_id not in state.presets:
            raise ValueError(f"Preset {preset_id} does not exist. Available: {list(state.presets.keys())}")

        target = state.presets[preset_id]
        state.is_moving = True
        state.active_preset_id = preset_id

        # Smooth transition simulation
        state.pan = target["pan"]
        state.tilt = target["tilt"]
        state.zoom = target["zoom"]

        async def _finish_preset_motion():
            try:
                await asyncio.sleep(0.4)
                state.is_moving = False
            except asyncio.CancelledError:
                pass

        self._motion_tasks[cam_id] = asyncio.create_task(_finish_preset_motion())

        logger.info(f"PTZ GotoPreset {preset_id} ({target['name']}) on {cam_id}")
        return state.to_dict()

    async def set_preset(self, camera: Any, preset_id: int, name: Optional[str] = None) -> Dict[str, Any]:
        """Saves current PTZ position as a preset."""
        if not self.is_ptz_capable(camera):
            raise PTZNotSupportedError("Camera is fixed, does not support PTZ")

        cam_id = str(camera.camera_id)
        state = self._get_state(cam_id)

        preset_name = name or f"Preset {preset_id}"
        state.presets[preset_id] = {
            "name": preset_name,
            "pan": state.pan,
            "tilt": state.tilt,
            "zoom": state.zoom,
        }
        state.active_preset_id = preset_id
        return state.to_dict()

    def get_status(self, camera: Any) -> Dict[str, Any]:
        """Returns the current PTZ coordinates, moving state, and capabilities."""
        is_capable = self.is_ptz_capable(camera)
        cam_id = str(getattr(camera, "camera_id", ""))
        if not is_capable:
            return {
                "cameraId": cam_id,
                "isPtzCapable": False,
                "isMoving": False,
                "pan": 0.0,
                "tilt": 0.0,
                "zoom": 1.0,
                "availablePresets": [],
            }

        state = self._get_state(cam_id)
        res = state.to_dict()
        res["isPtzCapable"] = True
        return res


# Global singleton
ptz_service = PTZService()

