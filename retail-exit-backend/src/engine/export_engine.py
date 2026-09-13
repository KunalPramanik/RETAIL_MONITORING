"""Multi-Tab Excel (.xlsx) & CSV Audit Export Engine

Generates fully dynamic, multi-tab Excel workbooks and flat CSV exports
directly from live database records matching operator filter criteria.
Applies frozen header rows, typography formatting, auto-fit columns,
and logs an immutable entry to audit_log for compliance.
"""

import io
import csv
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.db.models import (
    ExitEvent,
    Alert,
    Product,
    Invoice,
    AuditLog,
    Lane,
    Employee,
    get_utc_now,
)
from src.db.audit import log_audit_entry

logger = logging.getLogger("secops.engine.export")

# Styling Tokens matching SEC-OPS 2.0 Design System
HEADER_FILL = PatternFill(start_color="1A1E26", end_color="1A1E26", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
ZEBRA_FILL = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")
BORDER_THIN = Border(
    left=Side(style="thin", color="DCDAD3"),
    right=Side(style="thin", color="DCDAD3"),
    top=Side(style="thin", color="DCDAD3"),
    bottom=Side(style="thin", color="DCDAD3"),
)


def _style_headers(worksheet, headers: List[str]) -> None:
    """Applies frozen header styling, navy theme background, and white bold text."""
    worksheet.append(headers)
    worksheet.freeze_panes = "A2"
    for col_idx in range(1, len(headers) + 1):
        cell = worksheet.cell(row=1, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER_THIN


def _autofit_columns(worksheet) -> None:
    """Auto-fits column widths based on maximum string length with safety padding."""
    for col in worksheet.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)


class AuditExportEngine:
    """Enterprise Loss-Prevention Export Engine generating formatted multi-tab spreadsheets."""

    @classmethod
    async def generate_multi_tab_excel(
        cls,
        session: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        lane_id: Optional[str] = None,
        severity: Optional[str] = None,
        actor_id: Optional[str] = "OPERATOR",
    ) -> io.BytesIO:
        """Queries live database records and compiles a 5-tab formatted Excel workbook."""
        wb = openpyxl.Workbook()

        # ── 1. Tab: Exit Events ──
        ws_events = wb.active
        ws_events.title = "Exit Events"
        _style_headers(
            ws_events,
            [
                "Event ID",
                "Timestamp (UTC)",
                "Portal / Lane",
                "Carrier / Employee ID",
                "Cases Detected",
                "Consensus Units",
                "Declared Units",
                "Delta Units (Δ)",
                "Verdict",
                "Severity",
                "Notes",
            ],
        )

        query_events = select(ExitEvent).order_by(desc(ExitEvent.ts))
        if lane_id and lane_id != "ALL":
            query_events = query_events.where(ExitEvent.lane_id == lane_id)
        if severity and severity != "ALL":
            query_events = query_events.where(ExitEvent.severity == severity)

        res_events = await session.execute(query_events)
        events_list = res_events.scalars().all()

        for ev in events_list:
            ws_events.append(
                [
                    str(ev.event_id),
                    ev.ts.strftime("%Y-%m-%d %H:%M:%S") if ev.ts else "N/A",
                    str(ev.lane_id),
                    str(ev.employee_id) if ev.employee_id else "Unassigned",
                    int(ev.cases_detected or 0),
                    int(ev.consensus_units or 0),
                    int(ev.declared_units or 0),
                    int(ev.delta_units or 0),
                    str(ev.verdict),
                    str(ev.severity),
                    str(ev.notes or ""),
                ]
            )
        _autofit_columns(ws_events)

        # ── 2. Tab: Alerts & Violations ──
        ws_alerts = wb.create_sheet(title="Alerts & Discrepancies")
        _style_headers(
            ws_alerts,
            [
                "Alert ID",
                "Created At (UTC)",
                "Type",
                "Severity",
                "Status",
                "Event ID",
                "Camera ID",
                "Delta Units (Δ)",
                "Resolved By",
                "Resolved At",
                "Resolution Note",
            ],
        )

        query_alerts = select(Alert).order_by(desc(Alert.created_at))
        if severity and severity != "ALL":
            query_alerts = query_alerts.where(Alert.severity == severity)

        res_alerts = await session.execute(query_alerts)
        alerts_list = res_alerts.scalars().all()

        for a in alerts_list:
            ws_alerts.append(
                [
                    str(a.alert_id),
                    a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "N/A",
                    str(a.alert_type),
                    str(a.severity),
                    str(a.status),
                    str(a.event_id or "N/A"),
                    str(a.camera_id or "N/A"),
                    int(a.delta_units or 0),
                    str(a.resolved_by or "—"),
                    a.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if a.resolved_at else "—",
                    str(a.resolution_note or ""),
                ]
            )
        _autofit_columns(ws_alerts)

        # ── 3. Tab: Product Catalog ──
        ws_products = wb.create_sheet(title="Product Catalog")
        _style_headers(
            ws_products,
            [
                "Product ID",
                "SKU Code",
                "Product Name",
                "Category",
                "Unit Price (INR)",
                "Units Per Case (Pack Size)",
                "Unit Weight (kg)",
                "Status",
            ],
        )

        res_products = await session.execute(select(Product).order_by(Product.name))
        products_list = res_products.scalars().all()

        for p in products_list:
            ws_products.append(
                [
                    str(p.product_id),
                    str(p.sku_code),
                    str(p.name),
                    str(p.category or "General"),
                    float(p.unit_price or 0.0),
                    int(p.pack_size or 1),
                    round(float(p.avg_unit_weight_g or 0) / 1000.0, 3),
                    "ACTIVE",
                ]
            )
        _autofit_columns(ws_products)

        # ── 4. Tab: Invoices & PO Manifests ──
        ws_invoices = wb.create_sheet(title="Invoices & Manifests")
        _style_headers(
            ws_invoices,
            [
                "Invoice ID",
                "Invoice Number",
                "Carrier Name",
                "Store Destination",
                "Declared Total Units",
                "Source Channel",
                "OCR Confidence",
                "Created At (UTC)",
            ],
        )

        res_invoices = await session.execute(select(Invoice).order_by(desc(Invoice.created_at)))
        invoices_list = res_invoices.scalars().all()

        for inv in invoices_list:
            ws_invoices.append(
                [
                    str(inv.invoice_id),
                    str(inv.invoice_number or "N/A"),
                    str(inv.carrier_name or "N/A"),
                    str(inv.store_destination or "N/A"),
                    int(inv.declared_total_units or 0),
                    str(inv.source),
                    f"{float(inv.extraction_confidence or 0.0) * 100:.1f}%",
                    inv.created_at.strftime("%Y-%m-%d %H:%M:%S") if inv.created_at else "N/A",
                ]
            )
        _autofit_columns(ws_invoices)

        # ── 5. Tab: Security Audit Log ──
        ws_audit = wb.create_sheet(title="Security Audit Log")
        _style_headers(
            ws_audit,
            [
                "Audit ID",
                "Timestamp (UTC)",
                "Entity Type",
                "Entity ID",
                "Action Taken",
                "Actor ID",
                "Actor Type",
            ],
        )

        res_audit = await session.execute(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(200))
        audit_list = res_audit.scalars().all()

        for aud in audit_list:
            ws_audit.append(
                [
                    aud.audit_id,
                    aud.created_at.strftime("%Y-%m-%d %H:%M:%S") if aud.created_at else "N/A",
                    str(aud.entity_type),
                    str(aud.entity_id),
                    str(aud.action),
                    str(aud.actor_id or "—"),
                    str(aud.actor_type),
                ]
            )
        _autofit_columns(ws_audit)

        # Record this export in the database audit log for compliance
        now_utc = get_utc_now()
        await log_audit_entry(
            session=session,
            entity_type="EXPORT",
            entity_id=f"EXP-{int(now_utc.timestamp())}",
            action="EXPORT_XLSX",
            actor_id=actor_id or "OPERATOR",
            actor_type="USER",
            after_state={
                "format": "xlsx",
                "tabs": ["Exit Events", "Alerts & Discrepancies", "Product Catalog", "Invoices & Manifests", "Security Audit Log"],
                "totalEventsExported": len(events_list),
                "totalAlertsExported": len(alerts_list),
                "laneFilter": lane_id,
                "severityFilter": severity,
            },
        )
        await session.commit()

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    @classmethod
    async def generate_flat_csv(
        cls,
        session: AsyncSession,
        dataset: str = "events",
        lane_id: Optional[str] = None,
        severity: Optional[str] = None,
        actor_id: Optional[str] = "OPERATOR",
    ) -> str:
        """Generates a flat CSV string for a specific dataset with audit logging."""
        output = io.StringIO()
        writer = csv.writer(output)

        if dataset.lower() == "alerts":
            writer.writerow(["Alert ID", "Created At", "Type", "Severity", "Status", "Event ID", "Camera ID", "Delta Units", "Resolved By", "Resolved At", "Resolution Note"])
            res = await session.execute(select(Alert).order_by(desc(Alert.created_at)))
            for a in res.scalars().all():
                writer.writerow([
                    a.alert_id,
                    a.created_at.isoformat() if a.created_at else "",
                    a.alert_type,
                    a.severity,
                    a.status,
                    a.event_id or "",
                    a.camera_id or "",
                    a.delta_units or 0,
                    a.resolved_by or "",
                    a.resolved_at.isoformat() if a.resolved_at else "",
                    a.resolution_note or "",
                ])
        elif dataset.lower() == "products":
            writer.writerow(["Product ID", "SKU Code", "Name", "Category", "Unit Price", "Pack Size", "Avg Unit Weight (g)"])
            res = await session.execute(select(Product).order_by(Product.name))
            for p in res.scalars().all():
                writer.writerow([p.product_id, p.sku_code, p.name, p.category, float(p.unit_price or 0.0), p.pack_size, float(p.avg_unit_weight_g or 0.0)])
        else:  # default events
            writer.writerow(["Event ID", "Timestamp", "Lane ID", "Employee ID", "Cases", "Consensus Units", "Declared Units", "Delta Units", "Verdict", "Severity"])
            query = select(ExitEvent).order_by(desc(ExitEvent.ts))
            if lane_id and lane_id != "ALL":
                query = query.where(ExitEvent.lane_id == lane_id)
            if severity and severity != "ALL":
                query = query.where(ExitEvent.severity == severity)
            res = await session.execute(query)
            for ev in res.scalars().all():
                writer.writerow([
                    ev.event_id,
                    ev.ts.isoformat() if ev.ts else "",
                    ev.lane_id,
                    ev.employee_id or "",
                    ev.cases_detected,
                    ev.consensus_units,
                    ev.declared_units,
                    ev.delta_units,
                    ev.verdict,
                    ev.severity,
                ])

        # Write audit entry
        now_utc = get_utc_now()
        await log_audit_entry(
            session=session,
            entity_type="EXPORT",
            entity_id=f"EXP-{int(now_utc.timestamp())}",
            action="EXPORT_CSV",
            actor_id=actor_id or "OPERATOR",
            actor_type="USER",
            after_state={"format": "csv", "dataset": dataset},
        )
        await session.commit()

        return output.getvalue()

