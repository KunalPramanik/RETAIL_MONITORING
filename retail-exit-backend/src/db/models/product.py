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

