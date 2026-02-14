"""Tests for PdfService – invoice PDF generation."""

import sys
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.pdf_service import (
    PdfService,
    _build_org_address,
    _format_amount,
    _format_date,
)

# ---------------------------------------------------------------------------
# Helpers to build lightweight stand-ins for SQLAlchemy model instances
# ---------------------------------------------------------------------------


def _make_organization(**overrides):  # type: ignore[no-untyped-def]
    defaults = {
        "name": "Acme Corp",
        "address_line1": "123 Main St",
        "address_line2": "Suite 100",
        "city": "San Francisco",
        "state": "CA",
        "zipcode": "94105",
        "country": "US",
        "email": "billing@acme.com",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_customer(**overrides):  # type: ignore[no-untyped-def]
    defaults = {
        "name": "Jane Doe",
        "email": "jane@example.com",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_invoice(**overrides):  # type: ignore[no-untyped-def]
    defaults = {
        "invoice_number": "INV-001",
        "status": "finalized",
        "issued_at": datetime(2025, 1, 15, tzinfo=UTC),
        "due_date": datetime(2025, 2, 14, tzinfo=UTC),
        "billing_period_start": datetime(2025, 1, 1, tzinfo=UTC),
        "billing_period_end": datetime(2025, 1, 31, tzinfo=UTC),
        "subtotal": Decimal("100.0000"),
        "coupons_amount_cents": Decimal("10.0000"),
        "tax_amount": Decimal("5.0000"),
        "prepaid_credit_amount": Decimal("0.0000"),
        "progressive_billing_credit_amount_cents": Decimal("0.0000"),
        "total": Decimal("95.0000"),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_fee(**overrides):  # type: ignore[no-untyped-def]
    defaults = {
        "description": "API calls",
        "units": Decimal("1000.0000"),
        "unit_amount_cents": Decimal("0.0100"),
        "amount_cents": Decimal("10.0000"),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _patch_weasyprint():  # type: ignore[no-untyped-def]
    """Create a mock weasyprint module and patch it into sys.modules."""
    mock_weasyprint = MagicMock()
    mock_doc = MagicMock()
    mock_doc.write_pdf.return_value = b"%PDF-1.4 fake"
    mock_weasyprint.HTML.return_value = mock_doc
    return patch.dict(sys.modules, {"weasyprint": mock_weasyprint}), mock_weasyprint, mock_doc


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

    def test_float(self) -> None:
        assert _format_amount(99.9) == "99.90"


class TestFormatDate:
    def test_none_returns_empty(self) -> None:
        assert _format_date(None) == ""

    def test_datetime(self) -> None:
        dt = datetime(2025, 3, 15, 10, 30, tzinfo=UTC)
        assert _format_date(dt) == "2025-03-15"

    def test_string_passthrough(self) -> None:
        assert _format_date("2025-06-01T00:00:00") == "2025-06-01"


class TestBuildOrgAddress:
    def test_full_address(self) -> None:
        org = _make_organization()
        result = _build_org_address(org)
        assert "123 Main St" in result
        assert "Suite 100" in result
        assert "San Francisco" in result
        assert "CA" in result
        assert "94105" in result
        assert "US" in result
        assert "billing@acme.com" in result

    def test_minimal_address(self) -> None:
        org = _make_organization(
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            zipcode=None,
            country=None,
            email=None,
        )
        result = _build_org_address(org)
        assert result == ""

    def test_partial_city_state(self) -> None:
        org = _make_organization(
            address_line1=None,
            address_line2=None,
            city="Denver",
            state=None,
            zipcode=None,
            country=None,
            email=None,
        )
        result = _build_org_address(org)
        assert result == "Denver"


# ---------------------------------------------------------------------------
# Tests for PdfService.generate_invoice_pdf
# ---------------------------------------------------------------------------


class TestGenerateInvoicePdf:
    def test_returns_pdf_bytes(self) -> None:
        patcher, mock_wp, mock_doc = _patch_weasyprint()
        with patcher:
            service = PdfService()
            result = service.generate_invoice_pdf(
                invoice=_make_invoice(),
                fees=[_make_fee()],
                customer=_make_customer(),
                organization=_make_organization(),
            )

        assert result == b"%PDF-1.4 fake"
        mock_wp.HTML.assert_called_once()
        mock_doc.write_pdf.assert_called_once()

    def test_html_contains_org_info(self) -> None:
        patcher, mock_wp, _mock_doc = _patch_weasyprint()
        with patcher:
            service = PdfService()
            service.generate_invoice_pdf(
                invoice=_make_invoice(),
                fees=[],
                customer=_make_customer(),
                organization=_make_organization(name="TestOrg Inc"),
            )

        html_arg = mock_wp.HTML.call_args[1]["string"]
        assert "TestOrg Inc" in html_arg
        assert "123 Main St" in html_arg

    def test_html_contains_customer_info(self) -> None:
        patcher, mock_wp, _mock_doc = _patch_weasyprint()
        with patcher:
            service = PdfService()
            service.generate_invoice_pdf(
                invoice=_make_invoice(),
                fees=[],
                customer=_make_customer(name="Bob Smith", email="bob@test.com"),
                organization=_make_organization(),
            )

        html_arg = mock_wp.HTML.call_args[1]["string"]
        assert "Bob Smith" in html_arg
        assert "bob@test.com" in html_arg

    def test_html_contains_invoice_details(self) -> None:
        patcher, mock_wp, _mock_doc = _patch_weasyprint()
        with patcher:
            service = PdfService()
            service.generate_invoice_pdf(
                invoice=_make_invoice(
                    invoice_number="INV-2025-042",
                    status="paid",
                    subtotal=Decimal("200.0000"),
                    total=Decimal("180.0000"),
                ),
                fees=[],
                customer=_make_customer(),
                organization=_make_organization(),
            )

        html_arg = mock_wp.HTML.call_args[1]["string"]
        assert "INV-2025-042" in html_arg
        assert "paid" in html_arg
        assert "200.00" in html_arg
        assert "180.00" in html_arg

    def test_html_contains_fee_rows(self) -> None:
        patcher, mock_wp, _mock_doc = _patch_weasyprint()
        fees = [
            _make_fee(description="Base plan", units=Decimal("1.0000"), unit_amount_cents=Decimal("50.0000"), amount_cents=Decimal("50.0000")),
            _make_fee(description="API overage", units=Decimal("500.0000"), unit_amount_cents=Decimal("0.0200"), amount_cents=Decimal("10.0000")),
        ]

        with patcher:
            service = PdfService()
            service.generate_invoice_pdf(
                invoice=_make_invoice(),
                fees=fees,
                customer=_make_customer(),
                organization=_make_organization(),
            )

        html_arg = mock_wp.HTML.call_args[1]["string"]
        assert "Base plan" in html_arg
        assert "API overage" in html_arg
        assert "50.00" in html_arg
        assert "500.00" in html_arg

    def test_html_contains_billing_period(self) -> None:
        patcher, mock_wp, _mock_doc = _patch_weasyprint()
        with patcher:
            service = PdfService()
            service.generate_invoice_pdf(
                invoice=_make_invoice(
                    billing_period_start=datetime(2025, 6, 1, tzinfo=UTC),
                    billing_period_end=datetime(2025, 6, 30, tzinfo=UTC),
                ),
                fees=[],
                customer=_make_customer(),
                organization=_make_organization(),
            )

        html_arg = mock_wp.HTML.call_args[1]["string"]
        assert "2025-06-01" in html_arg
        assert "2025-06-30" in html_arg

    def test_html_contains_discount_and_credit_amounts(self) -> None:
        patcher, mock_wp, _mock_doc = _patch_weasyprint()
        with patcher:
            service = PdfService()
            service.generate_invoice_pdf(
                invoice=_make_invoice(
                    coupons_amount_cents=Decimal("15.5000"),
                    prepaid_credit_amount=Decimal("20.0000"),
                    progressive_billing_credit_amount_cents=Decimal("5.0000"),
                    tax_amount=Decimal("8.2500"),
                ),
                fees=[],
                customer=_make_customer(),
                organization=_make_organization(),
            )

        html_arg = mock_wp.HTML.call_args[1]["string"]
        assert "15.50" in html_arg
        assert "20.00" in html_arg
        assert "5.00" in html_arg
        assert "8.25" in html_arg

    def test_empty_fees_list(self) -> None:
        patcher, _mock_wp, _mock_doc = _patch_weasyprint()
        with patcher:
            service = PdfService()
            result = service.generate_invoice_pdf(
                invoice=_make_invoice(),
                fees=[],
                customer=_make_customer(),
                organization=_make_organization(),
            )

        assert result == b"%PDF-1.4 fake"

    def test_fee_with_none_description(self) -> None:
        patcher, mock_wp, _mock_doc = _patch_weasyprint()
        with patcher:
            service = PdfService()
            service.generate_invoice_pdf(
                invoice=_make_invoice(),
                fees=[_make_fee(description=None)],
                customer=_make_customer(),
                organization=_make_organization(),
            )

        html_arg = mock_wp.HTML.call_args[1]["string"]
        # Should not raise; the empty description is handled gracefully
        assert "<td></td>" in html_arg

    def test_invoice_with_none_dates(self) -> None:
        patcher, _mock_wp, mock_doc = _patch_weasyprint()
        with patcher:
            service = PdfService()
            service.generate_invoice_pdf(
                invoice=_make_invoice(issued_at=None, due_date=None),
                fees=[],
                customer=_make_customer(),
                organization=_make_organization(),
            )

        # Should not raise – None dates are handled
        mock_doc.write_pdf.assert_called_once()
