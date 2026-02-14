"""Tests for EmailService – email composition, SMTP sending, and no-op behavior."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.email_service import EmailService, _format_amount, _format_date

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_organization(**overrides):  # type: ignore[no-untyped-def]
    defaults = {"name": "Acme Corp"}
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_customer(**overrides):  # type: ignore[no-untyped-def]
    defaults = {"id": "cust-001", "name": "Jane Doe", "email": "jane@example.com"}
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_invoice(**overrides):  # type: ignore[no-untyped-def]
    defaults = {
        "invoice_number": "INV-001",
        "total": Decimal("100.0000"),
        "currency": "USD",
        "due_date": "2025-02-14",
        "status": "finalized",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_credit_note(**overrides):  # type: ignore[no-untyped-def]
    defaults = {
        "number": "CN-001",
        "total_amount_cents": Decimal("5000.0000"),
        "currency": "USD",
        "status": "finalized",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Tests for helper functions
# ---------------------------------------------------------------------------


class TestFormatAmount:
    def test_none_returns_zero(self) -> None:
        assert _format_amount(None) == "0.00"

    def test_decimal(self) -> None:
        assert _format_amount(Decimal("123.4567")) == "123.46"

    def test_int(self) -> None:
        assert _format_amount(0) == "0.00"


class TestFormatDate:
    def test_none_returns_empty(self) -> None:
        assert _format_date(None) == ""

    def test_string(self) -> None:
        assert _format_date("2025-06-01T00:00:00") == "2025-06-01"


# ---------------------------------------------------------------------------
# Tests for EmailService.send_email – no-op mode (SMTP not configured)
# ---------------------------------------------------------------------------


class TestSendEmailNoOp:
    """When SMTP_HOST is empty, send_email should log and return True."""

    @pytest.mark.asyncio
    async def test_returns_true_when_smtp_unconfigured(self) -> None:
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_HOST = ""
            service = EmailService()
            result = await service.send_email(
                to="test@example.com",
                subject="Test",
                html_body="<p>Hello</p>",
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_noop_with_attachments(self) -> None:
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SMTP_HOST = ""
            service = EmailService()
            result = await service.send_email(
                to="test@example.com",
                subject="Test",
                html_body="<p>Hello</p>",
                attachments=[("file.pdf", b"data", "application/pdf")],
            )
        assert result is True


# ---------------------------------------------------------------------------
# Tests for EmailService.send_email – SMTP configured
# ---------------------------------------------------------------------------


class TestSendEmailSmtp:
    """When SMTP_HOST is set, send_email should call aiosmtplib.send."""

    @pytest.mark.asyncio
    async def test_sends_email_via_smtp(self) -> None:
        mock_send = AsyncMock()
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch("aiosmtplib.send", mock_send),
        ):
            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "user"
            mock_settings.SMTP_PASSWORD = "pass"
            mock_settings.SMTP_FROM_EMAIL = "billing@example.com"
            mock_settings.SMTP_FROM_NAME = "Billing"
            mock_settings.SMTP_USE_TLS = True

            service = EmailService()
            result = await service.send_email(
                to="test@example.com",
                subject="Test Subject",
                html_body="<p>Hello</p>",
            )

        assert result is True
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["hostname"] == "smtp.example.com"
        assert call_kwargs["port"] == 587
        assert call_kwargs["username"] == "user"
        assert call_kwargs["password"] == "pass"
        assert call_kwargs["start_tls"] is True

    @pytest.mark.asyncio
    async def test_sends_email_with_attachments(self) -> None:
        mock_send = AsyncMock()
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch("aiosmtplib.send", mock_send),
        ):
            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = ""
            mock_settings.SMTP_PASSWORD = ""
            mock_settings.SMTP_FROM_EMAIL = "billing@example.com"
            mock_settings.SMTP_FROM_NAME = "Billing"
            mock_settings.SMTP_USE_TLS = False

            service = EmailService()
            result = await service.send_email(
                to="test@example.com",
                subject="Invoice",
                html_body="<p>Invoice attached</p>",
                attachments=[("invoice.pdf", b"%PDF-data", "application/pdf")],
            )

        assert result is True
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        # Email should contain the attachment
        payloads = msg.get_payload()
        # The message has multiple parts: text, html alternative, and attachment
        assert len(payloads) >= 2

    @pytest.mark.asyncio
    async def test_sends_email_with_empty_credentials(self) -> None:
        """When SMTP_USERNAME/PASSWORD are empty, None should be passed."""
        mock_send = AsyncMock()
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch("aiosmtplib.send", mock_send),
        ):
            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.SMTP_PORT = 25
            mock_settings.SMTP_USERNAME = ""
            mock_settings.SMTP_PASSWORD = ""
            mock_settings.SMTP_FROM_EMAIL = "noreply@example.com"
            mock_settings.SMTP_FROM_NAME = "System"
            mock_settings.SMTP_USE_TLS = False

            service = EmailService()
            await service.send_email(
                to="user@example.com",
                subject="Test",
                html_body="<p>Hi</p>",
            )

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["username"] is None
        assert call_kwargs["password"] is None

    @pytest.mark.asyncio
    async def test_email_message_headers(self) -> None:
        """Verify email headers (From, To, Subject) are set correctly."""
        mock_send = AsyncMock()
        with (
            patch("app.services.email_service.settings") as mock_settings,
            patch("aiosmtplib.send", mock_send),
        ):
            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USERNAME = "user"
            mock_settings.SMTP_PASSWORD = "pass"
            mock_settings.SMTP_FROM_EMAIL = "billing@acme.com"
            mock_settings.SMTP_FROM_NAME = "Acme Billing"
            mock_settings.SMTP_USE_TLS = True

            service = EmailService()
            await service.send_email(
                to="customer@example.com",
                subject="Your Invoice",
                html_body="<p>Invoice</p>",
            )

        msg = mock_send.call_args[0][0]
        assert msg["From"] == "Acme Billing <billing@acme.com>"
        assert msg["To"] == "customer@example.com"
        assert msg["Subject"] == "Your Invoice"


# ---------------------------------------------------------------------------
# Tests for EmailService.send_invoice_email
# ---------------------------------------------------------------------------


class TestSendInvoiceEmail:
    @pytest.mark.asyncio
    async def test_composes_invoice_email(self) -> None:
        service = EmailService()
        service.send_email = AsyncMock(return_value=True)  # type: ignore[method-assign]

        result = await service.send_invoice_email(
            invoice=_make_invoice(invoice_number="INV-042"),
            customer=_make_customer(email="jane@example.com"),
            organization=_make_organization(name="TestOrg"),
        )

        assert result is True
        service.send_email.assert_called_once()
        call_kwargs = service.send_email.call_args[1]
        assert call_kwargs["to"] == "jane@example.com"
        assert "INV-042" in call_kwargs["subject"]
        assert "TestOrg" in call_kwargs["subject"]
        assert "INV-042" in call_kwargs["html_body"]
        assert "100.00" in call_kwargs["html_body"]
        assert call_kwargs["attachments"] is None

    @pytest.mark.asyncio
    async def test_invoice_email_with_pdf_attachment(self) -> None:
        service = EmailService()
        service.send_email = AsyncMock(return_value=True)  # type: ignore[method-assign]
        pdf_bytes = b"%PDF-fake"

        result = await service.send_invoice_email(
            invoice=_make_invoice(invoice_number="INV-100"),
            customer=_make_customer(),
            organization=_make_organization(),
            pdf_bytes=pdf_bytes,
        )

        assert result is True
        call_kwargs = service.send_email.call_args[1]
        assert call_kwargs["attachments"] is not None
        assert len(call_kwargs["attachments"]) == 1
        filename, content, mime = call_kwargs["attachments"][0]
        assert "INV-100" in filename
        assert content == pdf_bytes
        assert mime == "application/pdf"

    @pytest.mark.asyncio
    async def test_invoice_email_no_customer_email(self) -> None:
        service = EmailService()
        service.send_email = AsyncMock(return_value=True)  # type: ignore[method-assign]

        result = await service.send_invoice_email(
            invoice=_make_invoice(),
            customer=_make_customer(email=None),
            organization=_make_organization(),
        )

        assert result is False
        service.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_invoice_email_empty_customer_email(self) -> None:
        service = EmailService()
        service.send_email = AsyncMock(return_value=True)  # type: ignore[method-assign]

        result = await service.send_invoice_email(
            invoice=_make_invoice(),
            customer=_make_customer(email=""),
            organization=_make_organization(),
        )

        assert result is False
        service.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_invoice_email_html_contains_details(self) -> None:
        service = EmailService()
        service.send_email = AsyncMock(return_value=True)  # type: ignore[method-assign]

        await service.send_invoice_email(
            invoice=_make_invoice(
                invoice_number="INV-007",
                total=Decimal("250.0000"),
                currency="EUR",
                status="paid",
            ),
            customer=_make_customer(name="Bob", email="bob@test.com"),
            organization=_make_organization(name="Euro Corp"),
        )

        call_kwargs = service.send_email.call_args[1]
        html = call_kwargs["html_body"]
        assert "INV-007" in html
        assert "250.00" in html
        assert "EUR" in html
        assert "paid" in html
        assert "Bob" in html


# ---------------------------------------------------------------------------
# Tests for EmailService.send_credit_note_email
# ---------------------------------------------------------------------------


class TestSendCreditNoteEmail:
    @pytest.mark.asyncio
    async def test_composes_credit_note_email(self) -> None:
        service = EmailService()
        service.send_email = AsyncMock(return_value=True)  # type: ignore[method-assign]

        result = await service.send_credit_note_email(
            credit_note=_make_credit_note(number="CN-042"),
            customer=_make_customer(email="jane@example.com"),
            organization=_make_organization(name="TestOrg"),
        )

        assert result is True
        service.send_email.assert_called_once()
        call_kwargs = service.send_email.call_args[1]
        assert call_kwargs["to"] == "jane@example.com"
        assert "CN-042" in call_kwargs["subject"]
        assert "TestOrg" in call_kwargs["subject"]
        assert "CN-042" in call_kwargs["html_body"]
        assert "5000.00" in call_kwargs["html_body"]
        assert call_kwargs["attachments"] is None

    @pytest.mark.asyncio
    async def test_credit_note_email_with_pdf_attachment(self) -> None:
        service = EmailService()
        service.send_email = AsyncMock(return_value=True)  # type: ignore[method-assign]
        pdf_bytes = b"%PDF-credit-note"

        result = await service.send_credit_note_email(
            credit_note=_make_credit_note(number="CN-100"),
            customer=_make_customer(),
            organization=_make_organization(),
            pdf_bytes=pdf_bytes,
        )

        assert result is True
        call_kwargs = service.send_email.call_args[1]
        assert call_kwargs["attachments"] is not None
        assert len(call_kwargs["attachments"]) == 1
        filename, content, mime = call_kwargs["attachments"][0]
        assert "CN-100" in filename
        assert content == pdf_bytes
        assert mime == "application/pdf"

    @pytest.mark.asyncio
    async def test_credit_note_email_no_customer_email(self) -> None:
        service = EmailService()
        service.send_email = AsyncMock(return_value=True)  # type: ignore[method-assign]

        result = await service.send_credit_note_email(
            credit_note=_make_credit_note(),
            customer=_make_customer(email=None),
            organization=_make_organization(),
        )

        assert result is False
        service.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_credit_note_email_empty_customer_email(self) -> None:
        service = EmailService()
        service.send_email = AsyncMock(return_value=True)  # type: ignore[method-assign]

        result = await service.send_credit_note_email(
            credit_note=_make_credit_note(),
            customer=_make_customer(email=""),
            organization=_make_organization(),
        )

        assert result is False
        service.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_credit_note_email_html_contains_details(self) -> None:
        service = EmailService()
        service.send_email = AsyncMock(return_value=True)  # type: ignore[method-assign]

        await service.send_credit_note_email(
            credit_note=_make_credit_note(
                number="CN-007",
                total_amount_cents=Decimal("1500.0000"),
                currency="GBP",
                status="finalized",
            ),
            customer=_make_customer(name="Alice", email="alice@test.com"),
            organization=_make_organization(name="UK Corp"),
        )

        call_kwargs = service.send_email.call_args[1]
        html = call_kwargs["html_body"]
        assert "CN-007" in html
        assert "1500.00" in html
        assert "GBP" in html
        assert "finalized" in html
        assert "Alice" in html
