"""Email service for sending transactional emails via SMTP."""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.invoice import Invoice
    from app.models.organization import Organization

logger = logging.getLogger(__name__)


def _format_amount(value: object) -> str:
    """Format a monetary amount to two decimal places."""
    if value is None:
        return "0.00"
    from decimal import Decimal

    return f"{Decimal(str(value)):.2f}"


def _format_date(dt: object) -> str:
    """Format a datetime to YYYY-MM-DD, or return empty string if None."""
    if dt is None:
        return ""
    return str(dt)[:10]


class EmailService:
    """Service for sending transactional emails via SMTP."""

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        attachments: list[tuple[str, bytes, str]] | None = None,
    ) -> bool:
        """Send an email via SMTP.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            html_body: HTML content of the email.
            attachments: Optional list of (filename, content_bytes, mime_type) tuples.

        Returns:
            True if sent successfully (or no-op when SMTP unconfigured).
        """
        if not settings.SMTP_HOST:
            logger.info("SMTP not configured, skipping email to %s: %s", to, subject)
            return True

        import aiosmtplib

        msg = EmailMessage()
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content("Please view this email in an HTML-capable client.")
        msg.add_alternative(html_body, subtype="html")

        if attachments:
            for filename, content, mime_type in attachments:
                maintype, _, subtype = mime_type.partition("/")
                msg.add_attachment(
                    content,
                    maintype=maintype,
                    subtype=subtype or "octet-stream",
                    filename=filename,
                )

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_USE_TLS,
        )
        logger.info("Email sent to %s: %s", to, subject)
        return True

    async def send_invoice_email(
        self,
        invoice: Invoice,
        customer: Customer,
        organization: Organization,
        pdf_bytes: bytes | None = None,
    ) -> bool:
        """Send an invoice notification email.

        Args:
            invoice: The invoice to notify about.
            customer: The customer to email.
            organization: The issuing organization.
            pdf_bytes: Optional PDF attachment bytes.

        Returns:
            True if sent successfully.
        """
        if not customer.email:
            logger.warning("Customer %s has no email, skipping invoice email", customer.id)
            return False

        org_name = str(organization.name or "")
        subject = f"Invoice {invoice.invoice_number} from {org_name}"

        html_body = (
            f"<h2>Invoice {invoice.invoice_number}</h2>"
            f"<p>Dear {customer.name or 'Customer'},</p>"
            f"<p>Please find below a summary of your invoice from {org_name}.</p>"
            f"<table>"
            f"<tr><td><strong>Invoice #:</strong></td><td>{invoice.invoice_number}</td></tr>"
            f"<tr><td><strong>Amount:</strong></td>"
            f"<td>{_format_amount(invoice.total)} {invoice.currency}</td></tr>"
            f"<tr><td><strong>Due Date:</strong></td>"
            f"<td>{_format_date(invoice.due_date)}</td></tr>"
            f"<tr><td><strong>Status:</strong></td><td>{invoice.status}</td></tr>"
            f"</table>"
            f"<p>Thank you for your business.</p>"
        )

        attachments: list[tuple[str, bytes, str]] | None = None
        if pdf_bytes is not None:
            attachments = [(f"invoice-{invoice.invoice_number}.pdf", pdf_bytes, "application/pdf")]

        return await self.send_email(
            to=str(customer.email),
            subject=subject,
            html_body=html_body,
            attachments=attachments,
        )

    async def send_credit_note_email(
        self,
        credit_note: object,
        customer: Customer,
        organization: Organization,
        pdf_bytes: bytes | None = None,
    ) -> bool:
        """Send a credit note notification email.

        Args:
            credit_note: The credit note to notify about.
            customer: The customer to email.
            organization: The issuing organization.
            pdf_bytes: Optional PDF attachment bytes.

        Returns:
            True if sent successfully.
        """
        if not customer.email:
            logger.warning("Customer %s has no email, skipping credit note email", customer.id)
            return False

        org_name = str(organization.name or "")
        number = getattr(credit_note, "number", "")
        total = getattr(credit_note, "total_amount_cents", 0)
        currency = getattr(credit_note, "currency", "USD")
        status = getattr(credit_note, "status", "")

        subject = f"Credit Note {number} from {org_name}"

        html_body = (
            f"<h2>Credit Note {number}</h2>"
            f"<p>Dear {customer.name or 'Customer'},</p>"
            f"<p>A credit note has been issued on your account from {org_name}.</p>"
            f"<table>"
            f"<tr><td><strong>Credit Note #:</strong></td><td>{number}</td></tr>"
            f"<tr><td><strong>Amount:</strong></td>"
            f"<td>{_format_amount(total)} {currency}</td></tr>"
            f"<tr><td><strong>Status:</strong></td><td>{status}</td></tr>"
            f"</table>"
            f"<p>Thank you for your business.</p>"
        )

        attachments: list[tuple[str, bytes, str]] | None = None
        if pdf_bytes is not None:
            attachments = [(f"credit-note-{number}.pdf", pdf_bytes, "application/pdf")]

        return await self.send_email(
            to=str(customer.email),
            subject=subject,
            html_body=html_body,
            attachments=attachments,
        )
