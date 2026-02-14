"""Data export service for generating CSV exports."""

import csv
import io
import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
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
        )

        try:
            org_id = export.organization_id
            export_type = export.export_type
            filters: dict[str, Any] = export.filters or {}  # type: ignore[assignment]

            csv_content, record_count = self._generate_csv(
                str(export_type),
                org_id,  # type: ignore[arg-type]
                filters,
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

    def _generate_csv(
        self,
        export_type: str,
        organization_id: UUID,
        filters: dict[str, Any],
    ) -> tuple[str, int]:
        """Generate CSV content based on export type."""
        generators = {
            ExportType.INVOICES.value: self._generate_csv_invoices,
            ExportType.CUSTOMERS.value: self._generate_csv_customers,
            ExportType.SUBSCRIPTIONS.value: self._generate_csv_subscriptions,
            ExportType.EVENTS.value: self._generate_csv_events,
            ExportType.FEES.value: self._generate_csv_fees,
            ExportType.CREDIT_NOTES.value: self._generate_csv_credit_notes,
        }
        generator = generators.get(export_type)
        if not generator:
            raise ValueError(f"Unknown export type: {export_type}")
        return generator(organization_id, filters)

    def _generate_csv_invoices(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
    ) -> tuple[str, int]:
        """Generate CSV for invoices."""
        query = self.db.query(Invoice).filter(Invoice.organization_id == organization_id)
        if filters.get("status"):
            query = query.filter(Invoice.status == filters["status"])
        if filters.get("customer_id"):
            query = query.filter(Invoice.customer_id == filters["customer_id"])

        invoices = query.order_by(Invoice.created_at.desc()).all()

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
        for inv in invoices:
            writer.writerow(
                [
                    inv.invoice_number,
                    str(inv.customer_id),
                    inv.status,
                    str(inv.subtotal),
                    str(inv.tax_amount),
                    str(inv.total),
                    inv.currency,
                    _fmt_dt(inv.issued_at),  # type: ignore[arg-type]
                    _fmt_dt(inv.due_date),  # type: ignore[arg-type]
                    _fmt_dt(inv.paid_at),  # type: ignore[arg-type]
                ]
            )
        return output.getvalue(), len(invoices)

    def _generate_csv_customers(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
    ) -> tuple[str, int]:
        """Generate CSV for customers."""
        query = self.db.query(Customer).filter(Customer.organization_id == organization_id)

        customers = query.order_by(Customer.created_at.desc()).all()

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
        for cust in customers:
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
        return output.getvalue(), len(customers)

    def _generate_csv_subscriptions(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
    ) -> tuple[str, int]:
        """Generate CSV for subscriptions."""
        query = self.db.query(Subscription).filter(Subscription.organization_id == organization_id)
        if filters.get("status"):
            query = query.filter(Subscription.status == filters["status"])
        if filters.get("customer_id"):
            query = query.filter(Subscription.customer_id == filters["customer_id"])

        subscriptions = query.order_by(Subscription.created_at.desc()).all()

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
        for sub in subscriptions:
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
        return output.getvalue(), len(subscriptions)

    def _generate_csv_events(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
    ) -> tuple[str, int]:
        """Generate CSV for events."""
        query = self.db.query(Event).filter(Event.organization_id == organization_id)
        if filters.get("external_customer_id"):
            query = query.filter(Event.external_customer_id == filters["external_customer_id"])
        if filters.get("code"):
            query = query.filter(Event.code == filters["code"])

        events = query.order_by(Event.timestamp.desc()).all()

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
        for evt in events:
            writer.writerow(
                [
                    evt.transaction_id,
                    evt.external_customer_id,
                    evt.code,
                    _fmt_dt(evt.timestamp),  # type: ignore[arg-type]
                    _fmt_dt(evt.created_at),  # type: ignore[arg-type]
                ]
            )
        return output.getvalue(), len(events)

    def _generate_csv_fees(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
    ) -> tuple[str, int]:
        """Generate CSV for fees."""
        query = self.db.query(Fee).filter(Fee.organization_id == organization_id)
        if filters.get("fee_type"):
            query = query.filter(Fee.fee_type == filters["fee_type"])
        if filters.get("invoice_id"):
            query = query.filter(Fee.invoice_id == filters["invoice_id"])

        fees = query.order_by(Fee.created_at.desc()).all()

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
        for fee in fees:
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
        return output.getvalue(), len(fees)

    def _generate_csv_credit_notes(
        self,
        organization_id: UUID,
        filters: dict[str, Any],
    ) -> tuple[str, int]:
        """Generate CSV for credit notes."""
        query = self.db.query(CreditNote).filter(CreditNote.organization_id == organization_id)
        if filters.get("status"):
            query = query.filter(CreditNote.status == filters["status"])

        credit_notes = query.order_by(CreditNote.created_at.desc()).all()

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
        for cn in credit_notes:
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
        return output.getvalue(), len(credit_notes)


def _fmt_dt(dt: datetime | None) -> str:
    """Format a datetime for CSV output."""
    if dt is None:
        return ""
    return dt.isoformat()
