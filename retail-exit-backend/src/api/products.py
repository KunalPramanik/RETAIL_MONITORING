"""Product Master CRUD & Visual Class Mapping Endpoints

Supports dynamic catalog management, visual class ID binding,
and human-in-the-loop PendingProductIdentification review workflows per Section 5.1.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional, Any
import datetime

from src.db.session import get_db
from src.db.models import Product, PendingProductIdentification, get_utc_now
from src.db.audit import log_audit_entry
from src.schemas.products import (
    ProductResponse,
    ProductCreate,
    ProductUpdate,
    PendingProductIdentificationResponse,
    PendingProductMapRequest,
)
from src.cache import cache_service
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/products", tags=["Products"])


def serialize_product(p: Any) -> ProductResponse:
    """Serializes a Product ORM instance to a typed ProductResponse."""
    return ProductResponse(
        productId=str(p.product_id),
        skuCode=str(p.sku_code),
        name=str(p.name),
        category=str(p.category),
        packSize=int(p.pack_size),
        unitPrice=float(p.unit_price),
        casePrice=float(p.case_price),
        reorderThreshold=int(p.reorder_threshold),
        visionClassId=int(p.vision_class_id) if p.vision_class_id is not None else None,
    )


def serialize_pending_identification(item: Any) -> PendingProductIdentificationResponse:
    """Serializes a PendingProductIdentification ORM instance."""
    return PendingProductIdentificationResponse(
        id=str(item.id),
        cameraId=str(item.camera_id) if item.camera_id else None,
        visionClassId=int(item.vision_class_id),
        detectedLabel=str(item.detected_label),
        confidence=float(item.confidence),
        snapshotUrl=str(item.snapshot_url) if item.snapshot_url else None,
        status=str(item.status),
        mappedSku=str(item.mapped_sku) if item.mapped_sku else None,
        mappedProductId=str(item.mapped_product_id) if item.mapped_product_id else None,
        reviewedBy=str(item.reviewed_by) if item.reviewed_by else None,
        reviewedAt=item.reviewed_at.isoformat() if item.reviewed_at else None,
        createdAt=item.created_at.isoformat() if item.created_at else get_utc_now().isoformat(),
    )


@router.get("", response_model=List[ProductResponse])
async def list_products(
    query: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """Lists all registered products and case pack configurations with cached reads."""
    cache_key = "products:all"
    if not query:
        cached = await cache_service.get(cache_key)
        if cached is not None:
            return [ProductResponse(**item) for item in cached]

    stmt = select(Product).order_by(Product.sku_code)
    result = await session.execute(stmt)
    products = result.scalars().all()

    if query:
        q = query.lower()
        products = [
            p for p in products
            if q in str(p.name).lower() or q in str(p.sku_code).lower() or q in str(p.category).lower()
        ]
        return [serialize_product(p) for p in products]

    serialized = [serialize_product(p) for p in products]
    await cache_service.set(cache_key, [p.model_dump() for p in serialized], ttl_seconds=300)
    return serialized


@router.get("/pending-identifications", response_model=List[PendingProductIdentificationResponse])
async def list_pending_identifications(
    status: Optional[str] = Query("PENDING_MAPPING"),
    session: AsyncSession = Depends(get_db),
):
    """Lists unmapped visual class detections awaiting operator review or mapping."""
    stmt = select(PendingProductIdentification).order_by(PendingProductIdentification.created_at.desc())
    if status:
        stmt = stmt.where(PendingProductIdentification.status == status)

    result = await session.execute(stmt)
    items = result.scalars().all()
    return [serialize_pending_identification(it) for it in items]


@router.post("/pending-identifications/{identification_id}/map", response_model=PendingProductIdentificationResponse)
async def map_pending_identification(
    identification_id: str,
    body: PendingProductMapRequest,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Maps an unmapped visual detection to an existing SKU or creates a new Product record."""
    stmt = select(PendingProductIdentification).where(PendingProductIdentification.id == identification_id)
    result = await session.execute(stmt)
    pending_item = result.scalar_one_or_none()

    if not pending_item:
        raise HTTPException(status_code=404, detail=f"Pending identification '{identification_id}' not found")

    p_item: Any = pending_item
    now = get_utc_now()
    p_item.reviewed_by = body.operatorId
    p_item.reviewed_at = now

    if body.action == "MAP_TO_SKU":
        if not body.skuCode:
            raise HTTPException(status_code=400, detail="skuCode is required when action is MAP_TO_SKU")
        prod_res = await session.execute(select(Product).where(Product.sku_code == body.skuCode))
        product = prod_res.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product SKU '{body.skuCode}' not found")

        # Dynamically link the visual class ID to this product
        p_prod: Any = product
        p_prod.vision_class_id = int(p_item.vision_class_id)
        p_prod.updated_at = now

        p_item.status = "MAPPED_TO_SKU"
        p_item.mapped_sku = body.skuCode
        p_item.mapped_product_id = str(product.product_id)

    elif body.action == "CREATE_NEW_PRODUCT":
        if not body.skuCode or not body.newProductName:
            raise HTTPException(status_code=400, detail="skuCode and newProductName are required for CREATE_NEW_PRODUCT")
        existing = await session.execute(select(Product).where(Product.sku_code == body.skuCode))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Product with SKU '{body.skuCode}' already exists")

        new_prod = Product(
            sku_code=body.skuCode,
            name=body.newProductName,
            category=body.category or "GENERAL",
            pack_size=body.packSize or 1,
            unit_price=body.unitPrice or 0.0,
            case_price=body.casePrice or 0.0,
            vision_class_id=int(p_item.vision_class_id),
        )
        session.add(new_prod)
        await session.flush()

        p_item.status = "CREATED_NEW_PRODUCT"
        p_item.mapped_sku = body.skuCode
        p_item.mapped_product_id = str(new_prod.product_id)

    elif body.action == "IGNORE":
        p_item.status = "IGNORED"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action '{body.action}'")

    await log_audit_entry(
        session=session,
        entity_type="PRODUCT_IDENTIFICATION",
        entity_id=identification_id,
        action=f"MAP_PENDING_{body.action}",
        actor_type="USER",
        before_state={"status": "PENDING_MAPPING"},
        after_state={"status": p_item.status, "mapped_sku": p_item.mapped_sku},
    )

    await session.commit()
    await cache_service.invalidate("products")
    return serialize_pending_identification(pending_item)


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreate,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Creates a new product with case pack and optional visual class mapping."""
    existing = await session.execute(select(Product).where(Product.sku_code == body.skuCode))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Product with SKU '{body.skuCode}' already exists")

    product = Product(
        sku_code=body.skuCode,
        name=body.name,
        category=body.category,
        pack_size=body.packSize,
        unit_price=body.unitPrice,
        case_price=body.casePrice,
        reorder_threshold=body.reorderThreshold,
        vision_class_id=body.visionClassId,
    )
    session.add(product)
    await session.flush()

    await log_audit_entry(
        session=session,
        entity_type="PRODUCT",
        entity_id=str(product.product_id),
        action="CREATE_PRODUCT",
        actor_type="USER",
        before_state=None,
        after_state=body.model_dump(),
    )
    await session.commit()
    await cache_service.invalidate("products")

    return serialize_product(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    body: ProductUpdate,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Updates product details, case pack multiplier, or visual class ID."""
    result = await session.execute(select(Product).where(Product.product_id == product_id))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")

    p_any: Any = product
    before_state = {
        "skuCode": str(p_any.sku_code),
        "name": str(p_any.name),
        "packSize": int(p_any.pack_size),
        "unitPrice": float(p_any.unit_price),
        "casePrice": float(p_any.case_price),
        "visionClassId": p_any.vision_class_id,
    }

    if body.skuCode is not None:
        p_any.sku_code = body.skuCode
    if body.name is not None:
        p_any.name = body.name
    if body.category is not None:
        p_any.category = body.category
    if body.packSize is not None:
        p_any.pack_size = body.packSize
    if body.unitPrice is not None:
        p_any.unit_price = body.unitPrice
    if body.casePrice is not None:
        p_any.case_price = body.casePrice
    if body.reorderThreshold is not None:
        p_any.reorder_threshold = body.reorderThreshold
    if body.visionClassId is not None:
        p_any.vision_class_id = body.visionClassId

    p_any.updated_at = get_utc_now()

    await log_audit_entry(
        session=session,
        entity_type="PRODUCT",
        entity_id=str(product.product_id),
        action="UPDATE_PRODUCT",
        actor_type="USER",
        before_state=before_state,
        after_state=body.model_dump(exclude_unset=True),
    )
    await session.commit()
    await cache_service.invalidate("products")

    return serialize_product(product)


@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Deletes a product from the master catalog."""
    result = await session.execute(select(Product).where(Product.product_id == product_id))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")

    await log_audit_entry(
        session=session,
        entity_type="PRODUCT",
        entity_id=str(product.product_id),
        action="DELETE_PRODUCT",
        actor_type="USER",
        before_state={"sku_code": str(product.sku_code), "name": str(product.name)},
        after_state=None,
    )

    await session.delete(product)
    await session.commit()
    await cache_service.invalidate("products")
    return {"status": "DELETED", "productId": product_id}
