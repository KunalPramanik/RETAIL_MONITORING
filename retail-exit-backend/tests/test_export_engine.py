"""Tests for Multi-Tab Excel (.xlsx) & CSV Audit Export Engine"""

import pytest
import io
import openpyxl
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.main import app
from src.db.session import get_db
from src.db.models import Base, AuditLog
from src.db.seed import seed_database
from src.engine.export_engine import AuditExportEngine


@pytest.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await seed_database(session)
        yield session


@pytest.fixture
async def client(test_session):
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_multi_tab_excel_structure(test_session: AsyncSession):
    """Verify that export engine creates a valid .xlsx workbook with all 5 required tabs and frozen headers."""
    excel_stream = await AuditExportEngine.generate_multi_tab_excel(
        session=test_session,
        lane_id="ALL",
        severity="ALL",
        actor_id="TEST_SUPERVISOR",
    )

    assert isinstance(excel_stream, io.BytesIO)
    excel_stream.seek(0)

    # Load with openpyxl to verify sheet names and formatting
    wb = openpyxl.load_workbook(excel_stream)
    sheet_names = wb.sheetnames

    # Check 5 tabs
    assert "Exit Events" in sheet_names
    assert "Alerts & Discrepancies" in sheet_names
    assert "Product Catalog" in sheet_names
    assert "Invoices & Manifests" in sheet_names
    assert "Security Audit Log" in sheet_names

    # Check frozen panes on primary sheet
    ws_events = wb["Exit Events"]
    assert ws_events.freeze_panes == "A2"

    # Verify audit trail was recorded
    res_audit = await test_session.execute(
        select(AuditLog).where(AuditLog.action == "EXPORT_XLSX")
    )
    audit_entry = res_audit.scalar_one_or_none()
    assert audit_entry is not None
    assert audit_entry.actor_id == "TEST_SUPERVISOR"
    assert audit_entry.after_state["format"] == "xlsx"


@pytest.mark.asyncio
async def test_generate_flat_csv(test_session: AsyncSession):
    """Verify flat CSV export generation and audit recording."""
    csv_text = await AuditExportEngine.generate_flat_csv(
        session=test_session,
        dataset="events",
        actor_id="TEST_SUPERVISOR",
    )

    assert isinstance(csv_text, str)
    lines = csv_text.strip().split("\n")
    assert len(lines) >= 1
    header = lines[0]
    assert "Event ID" in header
    assert "Consensus Units" in header

    # Verify audit trail was recorded
    res_audit = await test_session.execute(
        select(AuditLog).where(AuditLog.action == "EXPORT_CSV")
    )
    audit_entry = res_audit.scalar_one_or_none()
    assert audit_entry is not None
    assert audit_entry.after_state["format"] == "csv"


@pytest.mark.asyncio
async def test_http_export_endpoints(client: AsyncClient):
    """Verify HTTP GET /api/reports/export/xlsx and /api/reports/export/csv streaming."""
    # 1. Test Excel Export HTTP
    res_xlsx = await client.get("/api/reports/export/xlsx")
    assert res_xlsx.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res_xlsx.headers["content-type"]
    assert "attachment; filename=secops_audit_export_" in res_xlsx.headers["content-disposition"]
    assert len(res_xlsx.content) > 1000

    # 2. Test CSV Export HTTP
    res_csv = await client.get("/api/reports/export/csv?dataset=events")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Event ID" in res_csv.text

