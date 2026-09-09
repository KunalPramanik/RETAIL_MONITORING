"""Unit & Integration Tests for Hard Copy Bill Upload and OCR Ingestion"""

import io
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.main import app
from src.db.session import get_db
from src.db.models import Base
from src.db.seed import seed_database


@pytest.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await seed_database(session)
        yield session


import glob
import os


@pytest.fixture
async def client(test_session):
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

    # Clean up any uploaded test bills
    for f in glob.glob("uploads/invoices/bill_*.jpg"):
        try:
            os.remove(f)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_upload_hard_copy_bill(client):
    """Test uploading a hard-copy bill file via multipart/form-data."""
    dummy_image = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00")
    dummy_image.name = "sample_invoice.jpg"

    files = {"file": ("sample_invoice.jpg", dummy_image, "image/jpeg")}
    data = {
        "invoiceNumber": "BOL-TEST-9988",
        "carrierName": "BlueDart Express Freight",
        "storeDestination": "Store #402 - Metro Central",
    }

    resp = await client.post("/api/invoices/upload", files=files, data=data)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["invoiceNumber"] == "BOL-TEST-9988"
    assert body["carrierName"] == "BlueDart Express Freight"
    assert body["storeDestination"] == "Store #402 - Metro Central"
    assert body["ocrConfidence"] > 80.0
    assert body["declaredTotalUnits"] > 0
    assert len(body["lineItems"]) > 0
    assert "rawFileUrl" in body


@pytest.mark.asyncio
async def test_list_invoices_after_upload(client):
    """Test uploaded invoice persists in database and appears in list endpoint."""
    dummy_image = io.BytesIO(b"fake image bytes")
    files = {"file": ("bill_001.jpg", dummy_image, "image/jpeg")}
    data = {
        "invoiceNumber": "BOL-PERSIST-101",
        "carrierName": "Delhivery Freight",
    }

    upload_resp = await client.post("/api/invoices/upload", files=files, data=data)
    assert upload_resp.status_code == 200

    list_resp = await client.get("/api/invoices")
    assert list_resp.status_code == 200
    invoices = list_resp.json()
    numbers = [inv["invoiceNumber"] for inv in invoices]
    assert "BOL-PERSIST-101" in numbers


@pytest.mark.asyncio
async def test_upload_invoice_with_real_paddleocr(client):
    """Test uploading an invoice image with text parsed by deep-learning PaddleOCR."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (600, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "INVOICE: BOL-REAL-8899", fill=(0, 0, 0))
    draw.text((20, 60), "CARRIER: BLUEDART LOGISTICS", fill=(0, 0, 0))
    draw.text((20, 110), "SKU-WTR-500-24 3 CS PACK 24", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    buf.name = "real_bill.jpg"

    files = {"file": ("real_bill.jpg", buf, "image/jpeg")}
    resp = await client.post("/api/invoices/upload", files=files)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "BOL-REAL-8899" in body["invoiceNumber"]
    assert "BLUEDART" in body["carrierName"].upper()
    assert body["declaredTotalUnits"] == 72
    assert body["ocrConfidence"] > 70.0
    assert len(body["lineItems"]) >= 1
    assert body["lineItems"][0]["skuCode"] == "SKU-WTR-500-24"
    assert body["lineItems"][0]["casesDeclared"] == 3
    assert body["lineItems"][0]["unitsPerCase"] == 24
    assert body["lineItems"][0]["totalUnits"] == 72


