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


class PendingProductIdentification(Base):
    """Visual class detection without an active catalog mapping awaiting human assignment.
    
    Enforces Section 5.1 of the SEC-OPS V8 Master Prompt:
    Captures unmapped visual detections with snapshot, confidence, and timestamp,
    prompting operators to assign to an existing SKU or create a new product entry.
    """
    __tablename__ = "pending_product_identification"

    id: Any = Column(String(36), primary_key=True, default=generate_uuid)
    camera_id: Any = Column(String(36), ForeignKey("camera.camera_id"), nullable=True, index=True)
    vision_class_id: Any = Column(Integer, nullable=False, index=True)
    detected_label: Any = Column(String(128), nullable=False)
    confidence: Any = Column(Numeric(5, 4), nullable=False, default=0.5000)
    snapshot_url: Any = Column(Text, nullable=True)
    status: Any = Column(String(32), nullable=False, default="PENDING_MAPPING")  # PENDING_MAPPING, MAPPED_TO_SKU, CREATED_NEW_PRODUCT, IGNORED
    mapped_sku: Any = Column(String(64), nullable=True)
    mapped_product_id: Any = Column(String(36), ForeignKey("product.product_id", ondelete="SET NULL"), nullable=True)
    reviewed_by: Any = Column(String(128), nullable=True)
    reviewed_at: Any = Column(DateTime(timezone=True), nullable=True)
    created_at: Any = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_MAPPING', 'MAPPED_TO_SKU', 'CREATED_NEW_PRODUCT', 'IGNORED')",
            name="chk_pending_prod_id_status",
        ),
        Index("idx_pending_prod_status", "status"),
    )

    camera = relationship("Camera")
    mapped_product = relationship("Product")

