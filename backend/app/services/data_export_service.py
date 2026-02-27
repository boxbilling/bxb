"""Data export service for generating CSV exports."""

import csv
import io
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.credit_note import CreditNote
from app.models.customer import Customer
from app.models.data_export import DataExport, ExportStatus, ExportType
from app.models.event import Event
from app.models.fee import Fee
from app.models.invoice import Invoice
from app.models.subscription import Subscription
from app.repositories.data_export_repository import DataExportRepository
from app.schemas.data_export import DataExportCreate

logger = logging.getLogger(__name__)


class DataExportService:
    """Service for creating and processing CSV data exports."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = DataExportRepository(db)

    def estimate_count(
        self,
        organization_id: UUID,
        export_type: ExportType,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Estimate the number of records that would be exported."""
        counters = {
            ExportType.INVOICES.value: self._count_invoices,
            ExportType.CUSTOMERS.value: self._count_customers,
            ExportType.SUBSCRIPTIONS.value: self._count_subscriptions,
            ExportType.EVENTS.value: self._count_events,
            ExportType.FEES.value: self._count_fees,
            ExportType.CREDIT_NOTES.value: self._count_credit_notes,
            ExportType.AUDIT_LOGS.value: self._count_audit_logs,
        }
        counter = counters.get(export_type.value)
        if not counter:
            raise ValueError(f"Unknown export type: {export_type.value}")
        return counter(organization_id, filters or {})

    def create_export(
        self,
        organization_id: UUID,
        export_type: ExportType,
        filters: dict[str, Any] | None = None,
    ) -> DataExport:
        """Create a new data export record."""
        data = DataExportCreate(export_type=export_type, filters=filters)
        return self.repo.create(data, organization_id)

    def process_export(self, export_id: UUID) -> DataExport:
        """Process a data export: query data, generate CSV, update record."""
        export = self.repo.get_by_id(export_id)
        if not export:
            raise ValueError(f"DataExport {export_id} not found")

        self.repo.update_status(
            export_id,
            status=ExportStatus.PROCESSING.value,
            started_at=datetime.now(UTC),
            progress=0,
        )

        try:
            org_id = export.organization_id
            export_type = export.export_type
            filters: dict[str, Any] = export.filters or {}  # type: ignore[assignment]

            csv_content, record_count = self._generate_csv(
                str(export_type),
                org_id,  # type: ignore[arg-type]
                filters,
                export_id=export_id,
            )

            # Write CSV to file
            export_dir = os.path.join(settings.APP_DATA_PATH, "exports")
            os.makedirs(export_dir, exist_ok=True)
            file_path = os.path.join(export_dir, f"{export_id}.csv")

            with open(file_path, "w", newline="") as f:
                f.write(csv_content)

            result = self.repo.update_status(
                export_id,
                status=ExportStatus.COMPLETED.value,
                file_path=file_path,
                record_count=record_count,
                completed_at=datetime.now(UTC),
                progress=100,
            )
            return result  # type: ignore[return-value]

        except Exception as e:
            logger.exception("Failed to process export %s", export_id)
            result = self.repo.update_status(
                export_id,
                status=ExportStatus.FAILED.value,
                error_message=str(e),
                completed_at=datetime.now(UTC),
            )
            return result  # type: ignore[return-value]

    def _update_progress(self, export_id: UUID | None, progress: int) -> None:
        """Update export progress percentage."""
        if export_id is not None:
            self.repo.update_status(export_id, progress=progress)

    def _generate_csv(
        self,
        export_type: str,
        organization_id: UUID,
        filters: dict[str, Any],
        export_id: UUID | None = None,
    ) -> tuple[str, int]:
        """Generate CSV content based on export type."""
        generators = {
            ExportType.INVOICES.value: self._generate_csv_invoices,
            ExportType.CUSTOMERS.value: self._generate_csv_customers,
            ExportType.SUBSCRIPTIONS.value: self._generate_csv_subscriptions,
            ExportType.EVENTS.value: self._generate_csv_events,
            ExportType.FEES.value: self._generate_csv_fees,
            ExportType.CREDIT_NOTES.value: self._generate_csv_credit_notes,
            ExportType.AUDIT_LOGS.value: self._generate_csv_audit_logs,
        }
        generator = generators.get(export_type)
        if not generator:
            raise ValueError(f"Unknown export type: {export_type}")
        return generator(organization_id, filters, export_id=export_id)

    def _generate_csv_invoices(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
        export_id: UUID | None = None,
    ) -> tuple[str, int]:
        """Generate CSV for invoices."""
        query = self.db.query(Invoice).filter(Invoice.organization_id == organization_id)
        if filters.get("status"):
            query = query.filter(Invoice.status == filters["status"])
        if filters.get("customer_id"):
            query = query.filter(Invoice.customer_id == filters["customer_id"])

        invoices = query.order_by(Invoice.created_at.desc()).all()
        total = len(invoices)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "number",
                "customer_id",
                "status",
                "subtotal",
                "tax_amount",
                "total",
                "currency",
                "issued_at",
                "due_date",
                "paid_at",
            ]
        )
        for i, inv in enumerate(invoices):
            writer.writerow(
                [
                    inv.invoice_number,
                    str(inv.customer_id),
                    inv.status,
                    str(inv.subtotal_cents),
                    str(inv.tax_amount_cents),
                    str(inv.total_cents),
                    inv.currency,
                    _fmt_dt(inv.issued_at),  # type: ignore[arg-type]
                    _fmt_dt(inv.due_date),  # type: ignore[arg-type]
                    _fmt_dt(inv.paid_at),  # type: ignore[arg-type]
                ]
            )
            self._update_progress(export_id, (i + 1) * 100 // total)
        return output.getvalue(), total

    def _generate_csv_customers(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
        export_id: UUID | None = None,
    ) -> tuple[str, int]:
        """Generate CSV for customers."""
        query = self.db.query(Customer).filter(Customer.organization_id == organization_id)

        customers = query.order_by(Customer.created_at.desc()).all()
        total = len(customers)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "external_id",
                "name",
                "email",
                "currency",
                "timezone",
                "created_at",
            ]
        )
        for i, cust in enumerate(customers):
            writer.writerow(
                [
                    cust.external_id,
                    cust.name,
                    cust.email or "",
                    cust.currency,
                    cust.timezone,
                    _fmt_dt(cust.created_at),  # type: ignore[arg-type]
                ]
            )
            self._update_progress(export_id, (i + 1) * 100 // total)
        return output.getvalue(), total

    def _generate_csv_subscriptions(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
        export_id: UUID | None = None,
    ) -> tuple[str, int]:
        """Generate CSV for subscriptions."""
        query = self.db.query(Subscription).filter(Subscription.organization_id == organization_id)
        if filters.get("status"):
            query = query.filter(Subscription.status == filters["status"])
        if filters.get("customer_id"):
            query = query.filter(Subscription.customer_id == filters["customer_id"])

        subscriptions = query.order_by(Subscription.created_at.desc()).all()
        total = len(subscriptions)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "external_id",
                "customer_id",
                "plan_id",
                "status",
                "billing_time",
                "started_at",
                "canceled_at",
                "created_at",
            ]
        )
        for i, sub in enumerate(subscriptions):
            writer.writerow(
                [
                    sub.external_id,
                    str(sub.customer_id),
                    str(sub.plan_id),
                    sub.status,
                    sub.billing_time,
                    _fmt_dt(sub.started_at),  # type: ignore[arg-type]
                    _fmt_dt(sub.canceled_at),  # type: ignore[arg-type]
                    _fmt_dt(sub.created_at),  # type: ignore[arg-type]
                ]
            )
            self._update_progress(export_id, (i + 1) * 100 // total)
        return output.getvalue(), total

    def _generate_csv_events(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
        export_id: UUID | None = None,
    ) -> tuple[str, int]:
        """Generate CSV for events."""
        query = self.db.query(Event).filter(Event.organization_id == organization_id)
        if filters.get("external_customer_id"):
            query = query.filter(Event.external_customer_id == filters["external_customer_id"])
        if filters.get("code"):
            query = query.filter(Event.code == filters["code"])

        events = query.order_by(Event.timestamp.desc()).all()
        total = len(events)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "transaction_id",
                "external_customer_id",
                "code",
                "timestamp",
                "created_at",
            ]
        )
        for i, evt in enumerate(events):
            writer.writerow(
                [
                    evt.transaction_id,
                    evt.external_customer_id,
                    evt.code,
                    _fmt_dt(evt.timestamp),  # type: ignore[arg-type]
                    _fmt_dt(evt.created_at),  # type: ignore[arg-type]
                ]
            )
            self._update_progress(export_id, (i + 1) * 100 // total)
        return output.getvalue(), total

    def _generate_csv_fees(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
        export_id: UUID | None = None,
    ) -> tuple[str, int]:
        """Generate CSV for fees."""
        query = self.db.query(Fee).filter(Fee.organization_id == organization_id)
        if filters.get("fee_type"):
            query = query.filter(Fee.fee_type == filters["fee_type"])
        if filters.get("invoice_id"):
            query = query.filter(Fee.invoice_id == filters["invoice_id"])

        fees = query.order_by(Fee.created_at.desc()).all()
        total = len(fees)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "invoice_id",
                "fee_type",
                "amount_cents",
                "units",
                "events_count",
                "payment_status",
                "created_at",
            ]
        )
        for i, fee in enumerate(fees):
            writer.writerow(
                [
                    str(fee.id),
                    str(fee.invoice_id) if fee.invoice_id else "",
                    fee.fee_type,
                    str(fee.amount_cents),
                    str(fee.units),
                    str(fee.events_count),
                    fee.payment_status,
                    _fmt_dt(fee.created_at),  # type: ignore[arg-type]
                ]
            )
            self._update_progress(export_id, (i + 1) * 100 // total)
        return output.getvalue(), total

    def _generate_csv_credit_notes(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
        export_id: UUID | None = None,
    ) -> tuple[str, int]:
        """Generate CSV for credit notes."""
        query = self.db.query(CreditNote).filter(CreditNote.organization_id == organization_id)
        if filters.get("status"):
            query = query.filter(CreditNote.status == filters["status"])

        credit_notes = query.order_by(CreditNote.created_at.desc()).all()
        total = len(credit_notes)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "number",
                "invoice_id",
                "customer_id",
                "credit_note_type",
                "status",
                "total_amount_cents",
                "currency",
                "issued_at",
                "created_at",
            ]
        )
        for i, cn in enumerate(credit_notes):
            writer.writerow(
                [
                    cn.number,
                    str(cn.invoice_id),
                    str(cn.customer_id),
                    cn.credit_note_type,
                    cn.status,
                    str(cn.total_amount_cents),
                    cn.currency,
                    _fmt_dt(cn.issued_at),  # type: ignore[arg-type]
                    _fmt_dt(cn.created_at),  # type: ignore[arg-type]
                ]
            )
            self._update_progress(export_id, (i + 1) * 100 // total)
        return output.getvalue(), total

    def _generate_csv_audit_logs(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
        export_id: UUID | None = None,
    ) -> tuple[str, int]:
        """Generate CSV for audit logs."""
        query = self.db.query(AuditLog).filter(AuditLog.organization_id == organization_id)
        if filters.get("resource_type"):
            query = query.filter(AuditLog.resource_type == filters["resource_type"])
        if filters.get("action"):
            query = query.filter(AuditLog.action == filters["action"])
        if filters.get("actor_type"):
            query = query.filter(AuditLog.actor_type == filters["actor_type"])

        audit_logs = query.order_by(AuditLog.created_at.desc()).all()
        total = len(audit_logs)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "resource_type",
                "resource_id",
                "action",
                "actor_type",
                "actor_id",
                "changes",
                "created_at",
            ]
        )
        for i, log in enumerate(audit_logs):
            writer.writerow(
                [
                    str(log.id),
                    log.resource_type,
                    str(log.resource_id),
                    log.action,
                    log.actor_type,
                    log.actor_id or "",
                    _fmt_json(log.changes),
                    _fmt_dt(log.created_at),  # type: ignore[arg-type]
                ]
            )
            self._update_progress(export_id, (i + 1) * 100 // total)
        return output.getvalue(), total

    # --- Count methods for size estimation ---

    def _count_invoices(self, organization_id: UUID, filters: dict[str, Any]) -> int:
        """Count invoices matching filters."""
        query = self.db.query(Invoice).filter(Invoice.organization_id == organization_id)
        if filters.get("status"):
            query = query.filter(Invoice.status == filters["status"])
        if filters.get("customer_id"):
            query = query.filter(Invoice.customer_id == filters["customer_id"])
        return query.count()

    def _count_customers(self, organization_id: UUID, filters: dict[str, Any]) -> int:
        """Count customers matching filters."""
        query = self.db.query(Customer).filter(Customer.organization_id == organization_id)
        return query.count()

    def _count_subscriptions(self, organization_id: UUID, filters: dict[str, Any]) -> int:
        """Count subscriptions matching filters."""
        query = self.db.query(Subscription).filter(Subscription.organization_id == organization_id)
        if filters.get("status"):
            query = query.filter(Subscription.status == filters["status"])
        if filters.get("customer_id"):
            query = query.filter(Subscription.customer_id == filters["customer_id"])
        return query.count()

    def _count_events(self, organization_id: UUID, filters: dict[str, Any]) -> int:
        """Count events matching filters."""
        query = self.db.query(Event).filter(Event.organization_id == organization_id)
        if filters.get("external_customer_id"):
            query = query.filter(Event.external_customer_id == filters["external_customer_id"])
        if filters.get("code"):
            query = query.filter(Event.code == filters["code"])
        return query.count()

    def _count_fees(self, organization_id: UUID, filters: dict[str, Any]) -> int:
        """Count fees matching filters."""
        query = self.db.query(Fee).filter(Fee.organization_id == organization_id)
        if filters.get("fee_type"):
            query = query.filter(Fee.fee_type == filters["fee_type"])
        if filters.get("invoice_id"):
            query = query.filter(Fee.invoice_id == filters["invoice_id"])
        return query.count()

    def _count_credit_notes(self, organization_id: UUID, filters: dict[str, Any]) -> int:
        """Count credit notes matching filters."""
        query = self.db.query(CreditNote).filter(CreditNote.organization_id == organization_id)
        if filters.get("status"):
            query = query.filter(CreditNote.status == filters["status"])
        return query.count()

    def _count_audit_logs(self, organization_id: UUID, filters: dict[str, Any]) -> int:
        """Count audit logs matching filters."""
        query = self.db.query(AuditLog).filter(AuditLog.organization_id == organization_id)
        if filters.get("resource_type"):
            query = query.filter(AuditLog.resource_type == filters["resource_type"])
        if filters.get("action"):
            query = query.filter(AuditLog.action == filters["action"])
        if filters.get("actor_type"):
            query = query.filter(AuditLog.actor_type == filters["actor_type"])
        return query.count()


def _fmt_dt(dt: datetime | None) -> str:
    """Format a datetime for CSV output."""
    if dt is None:
        return ""
    return dt.isoformat()


def _fmt_json(value: Any) -> str:
    """Format a JSON-compatible value for CSV output."""
    if value is None:
        return ""
    return json.dumps(value)
