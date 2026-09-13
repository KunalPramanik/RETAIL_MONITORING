"""Product Master CRUD Endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional, Any

from src.db.session import get_db
from src.db.models import Product, get_utc_now
from src.db.audit import log_audit_entry
from src.schemas.products import ProductResponse, ProductCreate, ProductUpdate
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


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreate,
    session: AsyncSession = Depends(get_db),
    _role: str = Depends(require_roles(["ADMIN", "SUPERVISOR"])),
):
    """Creates a new product with case pack configuration."""
    # Check if SKU exists
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
    """Updates product details or case pack multiplier."""
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

