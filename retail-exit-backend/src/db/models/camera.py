from .base import *
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON
from sqlalchemy.orm import relationship

class Lane(Base):
    __tablename__ = "lane"

    lane_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    label: Any = Column(String(128), nullable=False)
    store_id: Any = Column(String(36), ForeignKey("store.store_id"), nullable=False)
    camera_ids: Any = Column(JSONType, nullable=False, default=list)  # list of camera IDs/IPs
    rfid_antenna_id: Any = Column(String(128), nullable=True)
    weight_sensor_id: Any = Column(String(128), nullable=True)
    turnstile_ctrl_id: Any = Column(String(128), nullable=True)
    status: Any = Column(String(32), nullable=False, default="ONLINE")
    last_heartbeat_at: Any = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('ONLINE', 'OFFLINE', 'DEGRADED')", name="chk_lane_status"),
    )

    store = relationship("Store", back_populates="lanes")
    exit_events = relationship("ExitEvent", back_populates="lane")
    cameras = relationship("Camera", back_populates="lane")

class Camera(Base):
    __tablename__ = "camera"

    camera_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    label: Any = Column(String(255), nullable=False)  # e.g. "Exit Lane 3 — North"
    lane_id: Any = Column(String(36), ForeignKey("lane.lane_id"), nullable=True)
    ip_address: Any = Column(String(64), nullable=False)
    rtsp_path: Any = Column(String(255), nullable=False)
    sub_stream_path: Any = Column(String(255), nullable=True)
    credentials_ref: Any = Column(String(128), nullable=True)  # pointer into secrets manager
    stream_url: Any = Column(Text, nullable=True)  # media-server WebRTC/HLS URL
    pairing_method: Any = Column(String(32), nullable=False, default="MANUAL")
    resolution: Any = Column(String(32), nullable=True, default="1920x1080")
    fps: Any = Column(Integer, nullable=True, default=30)
    pipeline_mode: Any = Column(String(64), nullable=False, default="STANDARD_DETECTION")
    roi_polygon: Any = Column(JSONType, nullable=True)  # Dynamic Region of Interest (e.g. [[x,y], ...])
    ignored_classes: Any = Column(JSONType, nullable=True)  # Classes to ignore (e.g. ["STORAGE_SHELF"])
    status: Any = Column(String(32), nullable=False, default="PENDING_SETUP")
    last_heartbeat_at: Any = Column(DateTime(timezone=True), nullable=True)
    offline_since: Any = Column(DateTime(timezone=True), nullable=True)
    added_by: Any = Column(String(36), ForeignKey("app_user.user_id"), nullable=True)
    added_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    removed_at: Any = Column(DateTime(timezone=True), nullable=True)  # Soft delete

    __table_args__ = (
        CheckConstraint("status IN ('ONLINE', 'OFFLINE', 'DEGRADED', 'PENDING_SETUP')", name="chk_camera_status"),
        CheckConstraint("pairing_method IN ('MANUAL', 'QR_CAMERA_DISPLAYED', 'QR_APP_GENERATED')", name="chk_camera_pairing_method"),
        CheckConstraint("pipeline_mode IN ('STANDARD_DETECTION', 'MATERIAL_SEGMENTATION', 'PERIMETER_TRIPWIRE_GATE')", name="chk_camera_pipeline_mode"),
        Index("idx_camera_lane", "lane_id"),
    )

    lane = relationship("Lane", back_populates="cameras")
    static_image_detections = relationship("StaticImageDetection", back_populates="camera", cascade="all, delete-orphan")
    virtual_tripwires = relationship("VirtualTripwireConfig", back_populates="camera", cascade="all, delete-orphan")
    heartbeats = relationship("CameraHeartbeat", back_populates="camera", cascade="all, delete-orphan")
    vision_detections = relationship("VisionDetection", back_populates="camera")
    alerts = relationship("Alert", back_populates="camera")

class CameraPairingToken(Base):
    __tablename__ = "camera_pairing_token"

    token_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    token_value: Any = Column(String(128), unique=True, nullable=False, index=True)
    store_id: Any = Column(String(36), ForeignKey("store.store_id"), nullable=False)
    lane_id: Any = Column(String(36), ForeignKey("lane.lane_id"), nullable=True)
    created_by: Any = Column(String(36), ForeignKey("app_user.user_id"), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    expires_at: Any = Column(DateTime(timezone=True), nullable=False)
    used_at: Any = Column(DateTime(timezone=True), nullable=True)
    used_by_camera_id: Any = Column(String(36), ForeignKey("camera.camera_id"), nullable=True)
    qr_payload: Any = Column(Text, nullable=True)

    store = relationship("Store")
    lane = relationship("Lane")
    camera = relationship("Camera", foreign_keys=[used_by_camera_id])

class CameraHeartbeat(Base):
    __tablename__ = "camera_heartbeat"

    heartbeat_id: Any = Column(Integer, primary_key=True, autoincrement=True)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id", ondelete="CASCADE"), nullable=False, index=True)
    received_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)
    fps_observed: Any = Column(Numeric(6, 2), nullable=True)
    bitrate_kbps: Any = Column(Numeric(10, 2), nullable=True)
    dropped_frames: Any = Column(Integer, nullable=True, default=0)

    camera = relationship("Camera", back_populates="heartbeats")

