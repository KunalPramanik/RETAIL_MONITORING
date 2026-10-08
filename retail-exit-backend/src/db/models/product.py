from .base import *
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, CheckConstraint, Index, JSON
from sqlalchemy.orm import relationship

class Product(Base):
    __tablename__ = "product"

    product_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    sku_code: Any = Column(String(64), unique=True, nullable=False, index=True)
    name: Any = Column(String(255), nullable=False)
    category: Any = Column(String(128), nullable=False)
    pack_size: Any = Column(Integer, nullable=False)  # units per sealed case
    unit_price: Any = Column(Numeric(12, 2), nullable=False)
    case_price: Any = Column(Numeric(12, 2), nullable=False)
    reorder_threshold: Any = Column(Integer, nullable=False, default=0)
    rfid_epc_prefix: Any = Column(String(64), nullable=True)
    avg_unit_weight_g: Any = Column(Numeric(10, 2), nullable=True)
    vision_class_id: Any = Column(Integer, nullable=True, index=True) # Dynamically links YOLOX output to Product
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        CheckConstraint("pack_size > 0", name="chk_product_pack_size_pos"),
    )

    line_items = relationship("ExitEventLineItem", back_populates="product")
    vision_detections = relationship("VisionDetection", back_populates="product")


class InitialStockVerification(Base):
    """First-time inventory baseline verification workflow entity.
    
    Preserves both AI_PROPOSED_COUNT and VERIFIED_COUNT with operator attribution,
    correction reason, camera reference, model version, and evidence snapshot.
    Enforces Section 5 & 6 of the V8 Master Prompt Addendum.
    """
    __tablename__ = "initial_stock_verification"

    verification_id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    product_id: Any = Column(String(36), ForeignKey("product.product_id", ondelete="CASCADE"), nullable=False, index=True)
    sku_code: Any = Column(String(64), nullable=False, index=True)
    product_name: Any = Column(String(255), nullable=False)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id"), nullable=True, index=True)
    ai_proposed_count: Any = Column(Integer, nullable=False)
    verified_count: Any = Column(Integer, nullable=True)
    difference: Any = Column(Integer, nullable=True)
    status: Any = Column(String(32), nullable=False, default="PENDING_VERIFICATION")  # PENDING_VERIFICATION, VERIFIED_ACCURATE, CORRECTED, REJECTED
    verified_by: Any = Column(String(128), nullable=True)
    correction_reason: Any = Column(String(255), nullable=True)
    snapshot_url: Any = Column(Text, nullable=True)
    model_version: Any = Column(String(64), nullable=True, default="yolox_retail_v8")
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    verified_at: Any = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_VERIFICATION', 'VERIFIED_ACCURATE', 'CORRECTED', 'REJECTED')",
            name="chk_stock_verif_status",
        ),
        Index("idx_stock_verif_prod_status", "product_id", "status"),
    )

    product = relationship("Product")
    camera = relationship("Camera")
