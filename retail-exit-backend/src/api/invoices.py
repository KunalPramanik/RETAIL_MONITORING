"""OCR Invoices and Waybill Manifest Endpoints"""

import os
import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from src.db.session import get_db
from src.db.models import Invoice, Product, ExitEvent, get_utc_now
from src.db.audit import log_audit_entry
from src.schemas.invoices import InvoiceResponse, InvoiceLineItemSchema, InvoiceCreateSchema
from src.ml.ocr_service import OcrService
from src.realtime.hub import ws_hub

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def serialize_invoice(inv: Any) -> InvoiceResponse:
    raw_items = getattr(inv, "extracted_json", None) or []
    line_items = [
        InvoiceLineItemSchema(
            skuCode=item.get("skuCode", item.get("sku_code", "SKU-UNKNOWN")),
            description=item.get("description", "Item"),
            casesDeclared=item.get("casesDeclared", item.get("cases_qty", 0)),
            unitsPerCase=item.get("unitsPerCase", item.get("pack_size", 1)),
            totalUnits=item.get("totalUnits", 0),
            status=item.get("status", "MATCHED"),
        )
        for item in raw_items
    ]
    raw_conf = getattr(inv, "extraction_confidence", 0.0)
    conf_val = float(str(raw_conf)) * 100.0 if raw_conf is not None else 0.0
    created = getattr(inv, "created_at", None)
    ts_str = created.isoformat() if created is not None else ""
    decl_units = getattr(inv, "declared_total_units", 0)
    decl_int = int(decl_units) if decl_units is not None else 0
    inv_id = str(inv.invoice_id)
    inv_num = str(inv.invoice_number)
    carrier = str(inv.carrier_name)
    destination = str(inv.store_destination)
    linked_event = str(inv.linked_event_id) if getattr(inv, "linked_event_id", None) else None
    raw_file = str(inv.raw_file_url) if getattr(inv, "raw_file_url", None) else None

    return InvoiceResponse(
        invoiceId=inv_id,
        invoiceNumber=inv_num,
        carrierName=carrier,
        storeDestination=destination,
        ocrConfidence=conf_val,
        scanTimestamp=ts_str,
        declaredTotalUnits=decl_int,
        linkedEventId=linked_event,
        lineItems=line_items,
        rawOcrText=(
            f"BILL OF LADING / MANIFEST: {inv_num}\n"
            f"CARRIER: {carrier}\n"
            f"DESTINATION: {destination}\n"
            f"OCR CONFIDENCE: {conf_val:.1f}%\n"
            f"STATUS: PARSED & VALIDATED"
        ),
        rawFileUrl=raw_file,
    )


@router.get("", response_model=List[InvoiceResponse])
async def list_invoices(
    query: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """Lists OCR-extracted carrier manifests and bills of lading."""
    stmt = select(Invoice).order_by(desc(Invoice.created_at))
    result = await session.execute(stmt)
    invoices = result.scalars().all()

    if query:
        q = query.lower()
        invoices = [
            inv for inv in invoices
            if q in str(inv.invoice_number).lower()
            or q in str(inv.carrier_name).lower()
            or q in str(inv.store_destination).lower()
        ]

    return [serialize_invoice(inv) for inv in invoices]


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves full OCR extraction detail for a single invoice manifest."""
    result = await session.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
    inv = result.scalar_one_or_none()

    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found")

    return serialize_invoice(inv)


@router.post("/upload", response_model=InvoiceResponse)
async def upload_invoice_bill(
    file: UploadFile = File(...),
    invoiceNumber: Optional[str] = Form(None),
    carrierName: Optional[str] = Form(None),
    storeDestination: Optional[str] = Form(None),
    linkedEventId: Optional[str] = Form(None),
    lineItemsJson: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_db),
):
    """Uploads hard-copy bill or manifest image, runs OCR parsing, saves to database, and broadcasts live."""
    uploads_dir = os.path.join(os.getcwd(), "uploads", "invoices")
    os.makedirs(uploads_dir, exist_ok=True)

    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    unique_name = f"bill_{uuid.uuid4().hex[:8]}{file_ext}"
    saved_path = os.path.join(uploads_dir, unique_name)

    content = await file.read()
    with open(saved_path, "wb") as f:
        f.write(content)

    # Query catalog products for accurate SKU matching and pack size lookup
    prod_res = await session.execute(select(Product))
    catalog_products = [
        {"sku_code": p.sku_code, "name": p.name, "pack_size": p.pack_size}
        for p in prod_res.scalars().all()
    ]
    catalog_skus = [p["sku_code"] for p in catalog_products]

    # Line items parsing or deep-learning OCR extraction
    parsed_items = None
    if lineItemsJson and lineItemsJson.strip():
        try:
            parsed_items = json.loads(lineItemsJson)
        except Exception:
            parsed_items = None

    if parsed_items:
        # Structured manifest passed directly
        inv_num = invoiceNumber.strip().upper() if invoiceNumber and invoiceNumber.strip() else f"BOL-2026-{uuid.uuid4().hex[:6].upper()}"
        carrier = carrierName.strip() if carrierName and carrierName.strip() else "Unassigned Carrier"
        destination = storeDestination.strip() if storeDestination and storeDestination.strip() else "Store Exit Lane"
        ocr_result = OcrService.parse_manifest(
            invoice_number=inv_num,
            carrier_name=carrier,
            line_items_data=parsed_items,
            catalog_skus=catalog_skus,
        )
    else:
        # Deep-learning PaddleOCR text and layout extraction directly from image bytes
        ocr_result = OcrService.extract_from_image(
            image_bytes=content,
            catalog_skus=catalog_skus,
            catalog_products=catalog_products,
            default_invoice_num=invoiceNumber.strip().upper() if invoiceNumber and invoiceNumber.strip() else None,
            default_carrier=carrierName.strip() if carrierName and carrierName.strip() else None,
        )
        inv_num = (
            invoiceNumber.strip().upper() if invoiceNumber and invoiceNumber.strip()
            else (ocr_result.extracted_invoice_number or f"BOL-2026-{uuid.uuid4().hex[:6].upper()}")
        )
        carrier = (
            carrierName.strip() if carrierName and carrierName.strip()
            else (ocr_result.extracted_carrier or "Unassigned Carrier")
        )
        destination = (
            storeDestination.strip() if storeDestination and storeDestination.strip()
            else (ocr_result.extracted_destination or "Store Exit Lane")
        )

    # Ensure invoice number uniqueness
    existing = await session.execute(select(Invoice).where(Invoice.invoice_number == inv_num))
    if existing.scalar_one_or_none():
        inv_num = f"{inv_num}-{uuid.uuid4().hex[:4].upper()}"

    # Insert into database
    new_invoice = Invoice(
        invoice_id=f"INV-{uuid.uuid4().hex[:8].upper()}",
        invoice_number=inv_num,
        carrier_name=carrier,
        store_destination=destination,
        source="SCAN",
        raw_file_url=f"/uploads/invoices/{unique_name}",
        ocr_model_version=ocr_result.model_version,
        extraction_confidence=ocr_result.extraction_confidence,
        extracted_json=[
            {
                "skuCode": item.sku_code,
                "description": item.description,
                "casesDeclared": item.cases_declared,
                "unitsPerCase": item.units_per_case,
                "totalUnits": item.total_units,
                "status": item.status,
            }
            for item in ocr_result.line_items
        ],
        declared_total_units=ocr_result.declared_total_units,
        linked_event_id=linkedEventId if linkedEventId and linkedEventId.strip() else None,
        created_at=get_utc_now(),
    )

    session.add(new_invoice)

    # Link with event if requested
    if linkedEventId and linkedEventId.strip():
        evt_stmt = select(ExitEvent).where(ExitEvent.event_id == linkedEventId.strip())
        evt_res = await session.execute(evt_stmt)
        evt = evt_res.scalar_one_or_none()
        if evt:
            evt.invoice_id = new_invoice.invoice_id
            evt.declared_units = new_invoice.declared_total_units
            evt.delta_units = evt.consensus_units - (evt.declared_units or 0)
            evt.verdict = "MISMATCH" if evt.delta_units != 0 else "PASS"

    await session.commit()
    await session.refresh(new_invoice)

    # Log to audit trail
    await log_audit_entry(
        session=session,
        entity_type="INVOICE",
        entity_id=str(new_invoice.invoice_id),
        action="HARD_COPY_BILL_UPLOADED",
        actor_type="USER",
        after_state={
            "invoiceNumber": str(new_invoice.invoice_number),
            "carrier": str(new_invoice.carrier_name),
            "units": int(str(new_invoice.declared_total_units or 0)),
            "ocrScore": float(str(new_invoice.extraction_confidence or 0.0)) * 100.0,
        },
    )

    # Broadcast WebSocket update
    await ws_hub.broadcast_event("invoice_uploaded", {
        "invoiceId": str(new_invoice.invoice_id),
        "invoiceNumber": str(new_invoice.invoice_number),
        "carrierName": str(new_invoice.carrier_name),
        "declaredTotalUnits": int(str(new_invoice.declared_total_units or 0)),
        "ocrConfidence": float(str(new_invoice.extraction_confidence or 0.0)) * 100.0,
    })

    return serialize_invoice(new_invoice)


@router.post("", response_model=InvoiceResponse)
async def create_invoice(
    payload: InvoiceCreateSchema,
    session: AsyncSession = Depends(get_db),
):
    """Creates an invoice record directly with structured line items and saves to database."""
    inv_num = payload.invoiceNumber.strip().upper() if payload.invoiceNumber else f"BOL-2026-{uuid.uuid4().hex[:6].upper()}"
    
    # Check uniqueness
    existing = await session.execute(select(Invoice).where(Invoice.invoice_number == inv_num))
    if existing.scalar_one_or_none():
        inv_num = f"{inv_num}-{uuid.uuid4().hex[:4].upper()}"

    carrier = payload.carrierName or "Unassigned Carrier"
    destination = payload.storeDestination or "Store Exit Lane"

    items_data = [item.dict() for item in payload.lineItems]
    ocr_result = OcrService.parse_manifest(
        invoice_number=inv_num,
        carrier_name=carrier,
        line_items_data=items_data,
    )

    new_invoice = Invoice(
        invoice_id=f"INV-{uuid.uuid4().hex[:8].upper()}",
        invoice_number=inv_num,
        carrier_name=carrier,
        store_destination=destination,
        source="SCAN",
        raw_file_url=payload.rawFileUrl or "",
        ocr_model_version=ocr_result.model_version,
        extraction_confidence=ocr_result.extraction_confidence,
        extracted_json=[
            {
                "skuCode": item.sku_code,
                "description": item.description,
                "casesDeclared": item.cases_declared,
                "unitsPerCase": item.units_per_case,
                "totalUnits": item.total_units,
                "status": item.status,
            }
            for item in ocr_result.line_items
        ],
        declared_total_units=ocr_result.declared_total_units,
        linked_event_id=payload.linkedEventId,
        created_at=get_utc_now(),
    )

    session.add(new_invoice)
    await session.commit()
    await session.refresh(new_invoice)

    await ws_hub.broadcast_event("invoice_uploaded", {
        "invoiceId": str(new_invoice.invoice_id),
        "invoiceNumber": str(new_invoice.invoice_number),
        "carrierName": str(new_invoice.carrier_name),
        "declaredTotalUnits": int(str(new_invoice.declared_total_units or 0)),
    })

    return serialize_invoice(new_invoice)


