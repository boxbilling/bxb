"""PDF generation service for invoices and credit notes."""

from __future__ import annotations

from decimal import Decimal
from string import Template
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.fee import Fee
    from app.models.invoice import Invoice
    from app.models.organization import Organization

_INVOICE_TEMPLATE = Template("""\
<!DOCTYPE html>
<html>
<head>
<style>
  body { font-family: Helvetica, Arial, sans-serif; font-size: 12px; color: #333; margin: 40px; }
  h1 { font-size: 24px; margin-bottom: 4px; }
  .header { display: flex; justify-content: space-between; margin-bottom: 30px; }
  .header-left, .header-right { width: 48%; }
  .meta { margin-bottom: 20px; }
  .meta td { padding: 2px 8px 2px 0; }
  table.items { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
  table.items th { text-align: left; border-bottom: 2px solid #333; padding: 6px 8px; }
  table.items td { padding: 6px 8px; border-bottom: 1px solid #ddd; }
  table.items .right { text-align: right; }
  .totals { width: 300px; margin-left: auto; }
  .totals td { padding: 4px 8px; }
  .totals .label { text-align: right; }
  .totals .total-row { font-weight: bold; border-top: 2px solid #333; }
  .status { display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: bold;
             text-transform: uppercase; font-size: 11px; }
  .status-finalized { background: #e8f0fe; color: #1a73e8; }
  .status-paid { background: #e6f4ea; color: #137333; }
  .status-draft { background: #fce8e6; color: #c5221f; }
  .status-voided { background: #f1f3f4; color: #5f6368; }
</style>
</head>
<body>
<div class="header">
  <div class="header-left">
    <h1>${org_name}</h1>
    <p>${org_address}</p>
  </div>
  <div class="header-right" style="text-align: right;">
    <h1>INVOICE</h1>
    <span class="status status-${status}">${status}</span>
  </div>
</div>
<table class="meta">
  <tr><td><strong>Invoice #:</strong></td><td>${invoice_number}</td></tr>
  <tr><td><strong>Issued:</strong></td><td>${issued_at}</td></tr>
  <tr><td><strong>Due:</strong></td><td>${due_date}</td></tr>
  <tr><td><strong>Billing Period:</strong></td><td>${billing_period}</td></tr>
</table>
<table class="meta">
  <tr><td><strong>Bill To:</strong></td></tr>
  <tr><td>${customer_name}</td></tr>
  <tr><td>${customer_email}</td></tr>
</table>
<table class="items">
  <thead>
    <tr>
      <th>Description</th>
      <th class="right">Units</th>
      <th class="right">Unit Price</th>
      <th class="right">Amount</th>
    </tr>
  </thead>
  <tbody>
    ${fee_rows}
  </tbody>
</table>
<table class="totals">
  <tr><td class="label">Subtotal:</td><td class="right">${subtotal}</td></tr>
  <tr><td class="label">Coupon Discount:</td><td class="right">-${coupons_amount}</td></tr>
  <tr><td class="label">Tax:</td><td class="right">${tax_amount}</td></tr>
  <tr><td class="label">Prepaid Credits:</td><td class="right">-${prepaid_credit_amount}</td></tr>
  <tr><td class="label">Progressive Billing Credits:</td>\
<td class="right">-${progressive_billing_credits}</td></tr>
  <tr class="total-row"><td class="label">Total:</td><td class="right">${total}</td></tr>
</table>
</body>
</html>
""")

_FEE_ROW_TEMPLATE = Template(
    '<tr><td>${description}</td><td class="right">${units}</td>'
    '<td class="right">${unit_price}</td><td class="right">${amount}</td></tr>'
)


def _format_amount(value: object) -> str:
    """Format a monetary amount to two decimal places."""
    if value is None:
        return "0.00"
    return f"{Decimal(str(value)):.2f}"


def _format_date(dt: object) -> str:
    """Format a datetime to YYYY-MM-DD, or return empty string if None."""
    if dt is None:
        return ""
    return str(dt)[:10]


def _build_org_address(organization: Organization) -> str:
    """Build a multi-line address string from organization fields."""
    parts: list[str] = []
    if organization.address_line1:
        parts.append(str(organization.address_line1))
    if organization.address_line2:
        parts.append(str(organization.address_line2))
    city_state_zip: list[str] = []
    if organization.city:
        city_state_zip.append(str(organization.city))
    if organization.state:
        city_state_zip.append(str(organization.state))
    if organization.zipcode:
        city_state_zip.append(str(organization.zipcode))
    if city_state_zip:
        parts.append(", ".join(city_state_zip))
    if organization.country:
        parts.append(str(organization.country))
    if organization.email:
        parts.append(str(organization.email))
    return "<br>".join(parts)


class PdfService:
    """Service for generating PDF documents."""

    def generate_invoice_pdf(
        self,
        invoice: Invoice,
        fees: list[Fee],
        customer: Customer,
        organization: Organization,
    ) -> bytes:
        """Generate a PDF for an invoice.

        Args:
            invoice: The invoice to render.
            fees: Line-item fees associated with the invoice.
            customer: The customer billed.
            organization: The issuing organization.

        Returns:
            Raw PDF bytes.
        """
        fee_rows = "\n    ".join(
            _FEE_ROW_TEMPLATE.substitute(
                description=fee.description or "",
                units=_format_amount(fee.units),
                unit_price=_format_amount(fee.unit_amount_cents),
                amount=_format_amount(fee.amount_cents),
            )
            for fee in fees
        )

        billing_period = (
            f"{_format_date(invoice.billing_period_start)}"
            f" to {_format_date(invoice.billing_period_end)}"
        )

        html = _INVOICE_TEMPLATE.substitute(
            org_name=organization.name or "",
            org_address=_build_org_address(organization),
            invoice_number=invoice.invoice_number or "",
            status=str(invoice.status or ""),
            issued_at=_format_date(invoice.issued_at),
            due_date=_format_date(invoice.due_date),
            billing_period=billing_period,
            customer_name=customer.name or "",
            customer_email=customer.email or "",
            fee_rows=fee_rows,
            subtotal=_format_amount(invoice.subtotal),
            coupons_amount=_format_amount(invoice.coupons_amount_cents),
            tax_amount=_format_amount(invoice.tax_amount),
            prepaid_credit_amount=_format_amount(invoice.prepaid_credit_amount),
            progressive_billing_credits=_format_amount(
                invoice.progressive_billing_credit_amount_cents
            ),
            total=_format_amount(invoice.total),
        )

        import weasyprint

        pdf_bytes: bytes = weasyprint.HTML(string=html).write_pdf()
        return pdf_bytes
