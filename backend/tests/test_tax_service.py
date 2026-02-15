"""Tests for TaxCalculationService and Tax API router."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.fee import FeeType
from app.repositories.applied_tax_repository import AppliedTaxRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.tax_repository import TaxRepository
from app.schemas.customer import CustomerCreate
from app.schemas.fee import FeeCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.tax import TaxCreate
from app.services.tax_service import TaxCalculationResult, TaxCalculationService
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def tax_service(db_session):
    return TaxCalculationService(db_session)


@pytest.fixture
def customer(db_session):
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"tax_test_cust_{uuid4()}",
            name="Tax Test Customer",
            email="taxtestcust@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def vat_tax(db_session):
    repo = TaxRepository(db_session)
    return repo.create(
        TaxCreate(
            code="VAT_20",
            name="VAT 20%",
            rate=Decimal("0.2000"),
            description="Standard VAT",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def sales_tax(db_session):
    repo = TaxRepository(db_session)
    return repo.create(
        TaxCreate(
            code="SALES_TAX",
            name="Sales Tax 8%",
            rate=Decimal("0.0800"),
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def org_tax(db_session):
    repo = TaxRepository(db_session)
    return repo.create(
        TaxCreate(
            code="ORG_TAX",
            name="Organization Tax",
            rate=Decimal("0.1000"),
            applied_to_organization=True,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def invoice_with_fees(db_session, customer):
    """Create an invoice with fees for testing tax application."""
    invoice_repo = InvoiceRepository(db_session)
    fee_repo = FeeRepository(db_session)

    invoice = invoice_repo.create(
        InvoiceCreate(
            customer_id=customer.id,
            billing_period_start=datetime(2026, 1, 1),
            billing_period_end=datetime(2026, 1, 31),
            line_items=[
                InvoiceLineItem(
                    description="Service A",
                    quantity=Decimal("1"),
                    unit_price=Decimal("10000"),
                    amount=Decimal("10000"),
                ),
            ],
        )
    )

    fee = fee_repo.create(
        FeeCreate(
            invoice_id=invoice.id,
            customer_id=customer.id,
            fee_type=FeeType.CHARGE,
            amount_cents=Decimal("10000"),
            total_amount_cents=Decimal("10000"),
            units=Decimal("1"),
            unit_amount_cents=Decimal("10000"),
            description="Service A",
        )
    )

    return invoice, fee


class TestTaxCalculationService:
    """Tests for TaxCalculationService."""

    def test_get_applicable_taxes_charge_level(
        self, tax_service, db_session, customer, vat_tax, org_tax
    ):
        """Charge-level taxes take priority."""
        charge_id = uuid4()
        applied_repo = AppliedTaxRepository(db_session)
        applied_repo.create(
            tax_id=vat_tax.id,
            taxable_type="charge",
            taxable_id=charge_id,
            tax_rate=Decimal("0.2000"),
        )

        taxes = tax_service.get_applicable_taxes(customer_id=customer.id, charge_id=charge_id)
        assert len(taxes) == 1
        assert taxes[0].code == "VAT_20"

    def test_get_applicable_taxes_plan_level(
        self, tax_service, db_session, customer, vat_tax, org_tax
    ):
        """Plan-level taxes used when no charge-level taxes."""
        plan_id = uuid4()
        applied_repo = AppliedTaxRepository(db_session)
        applied_repo.create(
            tax_id=vat_tax.id,
            taxable_type="plan",
            taxable_id=plan_id,
            tax_rate=Decimal("0.2000"),
        )

        taxes = tax_service.get_applicable_taxes(customer_id=customer.id, plan_id=plan_id)
        assert len(taxes) == 1
        assert taxes[0].code == "VAT_20"

    def test_get_applicable_taxes_customer_level(
        self, tax_service, db_session, customer, sales_tax, org_tax
    ):
        """Customer-level taxes used when no charge or plan taxes."""
        applied_repo = AppliedTaxRepository(db_session)
        applied_repo.create(
            tax_id=sales_tax.id,
            taxable_type="customer",
            taxable_id=customer.id,
            tax_rate=Decimal("0.0800"),
        )

        taxes = tax_service.get_applicable_taxes(customer_id=customer.id)
        assert len(taxes) == 1
        assert taxes[0].code == "SALES_TAX"

    def test_get_applicable_taxes_org_defaults(self, tax_service, customer, org_tax):
        """Organization default taxes used as fallback."""
        taxes = tax_service.get_applicable_taxes(customer_id=customer.id)
        assert len(taxes) == 1
        assert taxes[0].code == "ORG_TAX"

    def test_get_applicable_taxes_empty(self, tax_service, customer):
        """No taxes when nothing configured."""
        taxes = tax_service.get_applicable_taxes(customer_id=customer.id)
        assert taxes == []

    def test_get_applicable_taxes_charge_over_plan(
        self, tax_service, db_session, customer, vat_tax, sales_tax
    ):
        """Charge-level takes priority over plan-level."""
        charge_id = uuid4()
        plan_id = uuid4()
        applied_repo = AppliedTaxRepository(db_session)
        applied_repo.create(
            tax_id=vat_tax.id,
            taxable_type="charge",
            taxable_id=charge_id,
        )
        applied_repo.create(
            tax_id=sales_tax.id,
            taxable_type="plan",
            taxable_id=plan_id,
        )

        taxes = tax_service.get_applicable_taxes(
            customer_id=customer.id, plan_id=plan_id, charge_id=charge_id
        )
        assert len(taxes) == 1
        assert taxes[0].code == "VAT_20"

    def test_get_applicable_taxes_plan_over_customer(
        self, tax_service, db_session, customer, vat_tax, sales_tax
    ):
        """Plan-level takes priority over customer-level."""
        plan_id = uuid4()
        applied_repo = AppliedTaxRepository(db_session)
        applied_repo.create(
            tax_id=vat_tax.id,
            taxable_type="plan",
            taxable_id=plan_id,
        )
        applied_repo.create(
            tax_id=sales_tax.id,
            taxable_type="customer",
            taxable_id=customer.id,
        )

        taxes = tax_service.get_applicable_taxes(customer_id=customer.id, plan_id=plan_id)
        assert len(taxes) == 1
        assert taxes[0].code == "VAT_20"

    def test_get_applicable_taxes_customer_over_org(
        self, tax_service, db_session, customer, sales_tax, org_tax
    ):
        """Customer-level takes priority over org defaults."""
        applied_repo = AppliedTaxRepository(db_session)
        applied_repo.create(
            tax_id=sales_tax.id,
            taxable_type="customer",
            taxable_id=customer.id,
        )

        taxes = tax_service.get_applicable_taxes(customer_id=customer.id)
        assert len(taxes) == 1
        assert taxes[0].code == "SALES_TAX"

    def test_get_applicable_taxes_no_charge_id(self, tax_service, db_session, customer, org_tax):
        """When charge_id is None, skip charge-level check."""
        taxes = tax_service.get_applicable_taxes(customer_id=customer.id, charge_id=None)
        assert len(taxes) == 1
        assert taxes[0].code == "ORG_TAX"

    def test_get_applicable_taxes_no_plan_id(self, tax_service, db_session, customer, org_tax):
        """When plan_id is None, skip plan-level check."""
        taxes = tax_service.get_applicable_taxes(customer_id=customer.id, plan_id=None)
        assert len(taxes) == 1
        assert taxes[0].code == "ORG_TAX"

    def test_get_applicable_taxes_charge_empty_falls_to_plan(
        self, tax_service, db_session, customer, vat_tax
    ):
        """When charge_id is given but has no taxes, falls through to plan."""
        charge_id = uuid4()
        plan_id = uuid4()
        applied_repo = AppliedTaxRepository(db_session)
        applied_repo.create(
            tax_id=vat_tax.id,
            taxable_type="plan",
            taxable_id=plan_id,
        )

        taxes = tax_service.get_applicable_taxes(
            customer_id=customer.id, plan_id=plan_id, charge_id=charge_id
        )
        assert len(taxes) == 1
        assert taxes[0].code == "VAT_20"

    def test_get_applicable_taxes_plan_empty_falls_to_customer(
        self, tax_service, db_session, customer, sales_tax
    ):
        """When plan_id is given but has no taxes, falls through to customer."""
        plan_id = uuid4()
        applied_repo = AppliedTaxRepository(db_session)
        applied_repo.create(
            tax_id=sales_tax.id,
            taxable_type="customer",
            taxable_id=customer.id,
        )

        taxes = tax_service.get_applicable_taxes(customer_id=customer.id, plan_id=plan_id)
        assert len(taxes) == 1
        assert taxes[0].code == "SALES_TAX"

    def test_calculate_tax_single(self, tax_service, vat_tax):
        """Calculate tax with a single tax."""
        result = tax_service.calculate_tax(Decimal("10000"), [vat_tax])
        assert result.taxes_amount_cents == Decimal("2000.0000")

    def test_calculate_tax_multiple(self, tax_service, vat_tax, sales_tax):
        """Calculate tax with multiple taxes (combined rate)."""
        result = tax_service.calculate_tax(Decimal("10000"), [vat_tax, sales_tax])
        # 20% + 8% = 28% of 10000 = 2800
        assert result.taxes_amount_cents == Decimal("2800.0000")

    def test_calculate_tax_empty(self, tax_service):
        """Calculate tax with no taxes returns zero."""
        result = tax_service.calculate_tax(Decimal("10000"), [])
        assert result.taxes_amount_cents == Decimal("0")
        assert result.applied_taxes == []

    def test_calculate_tax_zero_subtotal(self, tax_service, vat_tax):
        """Calculate tax with zero subtotal."""
        result = tax_service.calculate_tax(Decimal("0"), [vat_tax])
        assert result.taxes_amount_cents == Decimal("0.0000")

    def test_apply_taxes_to_fee(self, tax_service, db_session, customer, vat_tax):
        """Apply taxes to a fee updates fee amounts."""
        fee_repo = FeeRepository(db_session)
        fee = fee_repo.create(
            FeeCreate(
                customer_id=customer.id,
                fee_type=FeeType.CHARGE,
                amount_cents=Decimal("10000"),
                total_amount_cents=Decimal("10000"),
                units=Decimal("1"),
                unit_amount_cents=Decimal("10000"),
            )
        )

        applied = tax_service.apply_taxes_to_fee(fee.id, [vat_tax])
        assert len(applied) == 1
        assert applied[0].tax_rate == Decimal("0.2000")
        assert applied[0].tax_amount_cents == Decimal("2000.0000")

        # Check fee was updated
        updated_fee = fee_repo.get_by_id(fee.id)
        assert updated_fee is not None
        assert updated_fee.taxes_amount_cents == Decimal("2000.0000")
        assert updated_fee.total_amount_cents == Decimal("12000.0000")

    def test_apply_taxes_to_fee_multiple(
        self, tax_service, db_session, customer, vat_tax, sales_tax
    ):
        """Apply multiple taxes to a fee."""
        fee_repo = FeeRepository(db_session)
        fee = fee_repo.create(
            FeeCreate(
                customer_id=customer.id,
                fee_type=FeeType.CHARGE,
                amount_cents=Decimal("10000"),
                total_amount_cents=Decimal("10000"),
                units=Decimal("1"),
                unit_amount_cents=Decimal("10000"),
            )
        )

        applied = tax_service.apply_taxes_to_fee(fee.id, [vat_tax, sales_tax])
        assert len(applied) == 2

        # Fee should have combined tax: 20% + 8% = 28% of 10000 = 2800
        updated_fee = fee_repo.get_by_id(fee.id)
        assert updated_fee is not None
        assert updated_fee.taxes_amount_cents == Decimal("2800.0000")
        assert updated_fee.total_amount_cents == Decimal("12800.0000")

    def test_apply_taxes_to_fee_not_found(self, tax_service, vat_tax):
        """Apply taxes to non-existent fee raises ValueError."""
        with pytest.raises(ValueError, match="Fee .* not found"):
            tax_service.apply_taxes_to_fee(uuid4(), [vat_tax])

    def test_apply_taxes_to_fee_no_taxes(self, tax_service, db_session, customer):
        """Apply empty tax list to fee."""
        fee_repo = FeeRepository(db_session)
        fee = fee_repo.create(
            FeeCreate(
                customer_id=customer.id,
                fee_type=FeeType.CHARGE,
                amount_cents=Decimal("10000"),
                total_amount_cents=Decimal("10000"),
                units=Decimal("1"),
                unit_amount_cents=Decimal("10000"),
            )
        )

        applied = tax_service.apply_taxes_to_fee(fee.id, [])
        assert applied == []

        updated_fee = fee_repo.get_by_id(fee.id)
        assert updated_fee is not None
        assert updated_fee.taxes_amount_cents == Decimal("0")
        assert updated_fee.total_amount_cents == Decimal("10000")

    def test_apply_taxes_to_invoice(self, tax_service, db_session, invoice_with_fees, vat_tax):
        """Apply taxes to invoice aggregates fee taxes."""
        invoice, fee = invoice_with_fees

        # First apply taxes to the fee
        tax_service.apply_taxes_to_fee(fee.id, [vat_tax])

        # Then aggregate to invoice
        total_tax = tax_service.apply_taxes_to_invoice(invoice.id)
        assert total_tax == Decimal("2000.0000")

        # Verify invoice was updated
        invoice_repo = InvoiceRepository(db_session)
        updated_invoice = invoice_repo.get_by_id(invoice.id)
        assert updated_invoice is not None
        assert updated_invoice.tax_amount == Decimal("2000.0000")
        assert updated_invoice.total == Decimal("12000.0000")

    def test_apply_taxes_to_invoice_not_found(self, tax_service):
        """Apply taxes to non-existent invoice raises ValueError."""
        with pytest.raises(ValueError, match="Invoice .* not found"):
            tax_service.apply_taxes_to_invoice(uuid4())

    def test_apply_taxes_to_invoice_no_fees(self, tax_service, db_session, customer):
        """Apply taxes to invoice with no fees."""
        invoice_repo = InvoiceRepository(db_session)
        invoice = invoice_repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                billing_period_start=datetime(2026, 1, 1),
                billing_period_end=datetime(2026, 1, 31),
                line_items=[],
            )
        )

        total_tax = tax_service.apply_taxes_to_invoice(invoice.id)
        assert total_tax == Decimal("0")

    def test_apply_taxes_to_invoice_with_coupons(self, tax_service, db_session, customer, vat_tax):
        """Invoice total accounts for coupons and tax."""
        invoice_repo = InvoiceRepository(db_session)
        fee_repo = FeeRepository(db_session)

        invoice = invoice_repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                billing_period_start=datetime(2026, 1, 1),
                billing_period_end=datetime(2026, 1, 31),
                line_items=[
                    InvoiceLineItem(
                        description="Service",
                        quantity=Decimal("1"),
                        unit_price=Decimal("10000"),
                        amount=Decimal("10000"),
                    ),
                ],
            )
        )
        # Simulate coupon applied
        invoice.coupons_amount_cents = Decimal("1000")  # type: ignore[assignment]
        db_session.commit()
        db_session.refresh(invoice)

        fee = fee_repo.create(
            FeeCreate(
                invoice_id=invoice.id,
                customer_id=customer.id,
                fee_type=FeeType.CHARGE,
                amount_cents=Decimal("10000"),
                total_amount_cents=Decimal("10000"),
                units=Decimal("1"),
                unit_amount_cents=Decimal("10000"),
            )
        )

        tax_service.apply_taxes_to_fee(fee.id, [vat_tax])
        tax_service.apply_taxes_to_invoice(invoice.id)

        updated = invoice_repo.get_by_id(invoice.id)
        assert updated is not None
        # total = subtotal(10000) - coupons(1000) + tax(2000) = 11000
        assert updated.total == Decimal("11000.0000")

    def test_apply_tax_to_entity(self, tax_service, vat_tax):
        """Apply tax to an entity by code."""
        entity_id = uuid4()
        applied = tax_service.apply_tax_to_entity("VAT_20", "customer", entity_id)
        assert applied.tax_id == vat_tax.id
        assert applied.taxable_type == "customer"
        assert applied.taxable_id == entity_id
        assert applied.tax_rate == Decimal("0.2000")

    def test_apply_tax_to_entity_not_found(self, tax_service):
        """Apply non-existent tax raises ValueError."""
        with pytest.raises(ValueError, match="Tax .* not found"):
            tax_service.apply_tax_to_entity("NONEXISTENT", "customer", uuid4())

    def test_remove_tax_from_entity(self, tax_service, vat_tax):
        """Remove tax from an entity."""
        entity_id = uuid4()
        tax_service.apply_tax_to_entity("VAT_20", "customer", entity_id)

        result = tax_service.remove_tax_from_entity("VAT_20", "customer", entity_id)
        assert result is True

    def test_remove_tax_from_entity_not_applied(self, tax_service, vat_tax):
        """Remove tax that was not applied returns False."""
        result = tax_service.remove_tax_from_entity("VAT_20", "customer", uuid4())
        assert result is False

    def test_remove_tax_from_entity_different_tax_applied(self, tax_service, vat_tax, sales_tax):
        """Remove tax when entity has different taxes applied returns False."""
        entity_id = uuid4()
        # Apply sales_tax but try to remove vat_tax
        tax_service.apply_tax_to_entity("SALES_TAX", "customer", entity_id)

        result = tax_service.remove_tax_from_entity("VAT_20", "customer", entity_id)
        assert result is False

    def test_remove_tax_from_entity_not_found(self, tax_service):
        """Remove non-existent tax raises ValueError."""
        with pytest.raises(ValueError, match="Tax .* not found"):
            tax_service.remove_tax_from_entity("NONEXISTENT", "customer", uuid4())

    def test_resolve_taxes_with_missing_tax(self, tax_service, db_session, vat_tax):
        """_resolve_taxes handles deleted tax gracefully."""
        applied_repo = AppliedTaxRepository(db_session)
        entity_id = uuid4()
        applied = applied_repo.create(
            tax_id=vat_tax.id,
            taxable_type="customer",
            taxable_id=entity_id,
        )

        # Delete the tax (clear applied taxes first to avoid FK constraint)
        applied_repo.delete_by_id(applied.id)
        tax_repo = TaxRepository(db_session)
        tax_repo.delete("VAT_20", DEFAULT_ORG_ID)

        # Re-create applied tax with a stale tax_id
        stale_applied = applied_repo.create(
            tax_id=vat_tax.id,
            taxable_type="customer",
            taxable_id=entity_id,
        )

        # _resolve_taxes should skip the missing tax (can't resolve)
        # Force the FK check to fail by querying directly
        result = tax_service._resolve_taxes([stale_applied])
        assert result == []

    def test_tax_calculation_result_dataclass(self):
        """Test TaxCalculationResult defaults."""
        result = TaxCalculationResult(taxes_amount_cents=Decimal("100"))
        assert result.taxes_amount_cents == Decimal("100")
        assert result.applied_taxes == []


class TestTaxRouter:
    """Tests for Tax API router."""

    def test_create_tax(self, client):
        """POST /v1/taxes creates a tax."""
        resp = client.post(
            "/v1/taxes/",
            json={
                "code": "VAT_20",
                "name": "VAT 20%",
                "rate": "0.2000",
                "description": "Standard VAT",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == "VAT_20"
        assert data["rate"] == "0.2000"

    def test_create_tax_duplicate(self, client):
        """POST /v1/taxes with duplicate code returns 409."""
        client.post(
            "/v1/taxes/",
            json={"code": "DUP", "name": "Dup", "rate": "0.1000"},
        )
        resp = client.post(
            "/v1/taxes/",
            json={"code": "DUP", "name": "Dup 2", "rate": "0.1500"},
        )
        assert resp.status_code == 409

    def test_list_taxes(self, client):
        """GET /v1/taxes lists all taxes."""
        client.post(
            "/v1/taxes/",
            json={"code": "T1", "name": "Tax 1", "rate": "0.1000"},
        )
        client.post(
            "/v1/taxes/",
            json={"code": "T2", "name": "Tax 2", "rate": "0.2000"},
        )
        resp = client.get("/v1/taxes/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_taxes_pagination(self, client):
        """GET /v1/taxes supports pagination."""
        client.post(
            "/v1/taxes/",
            json={"code": "P1", "name": "Page 1", "rate": "0.1000"},
        )
        client.post(
            "/v1/taxes/",
            json={"code": "P2", "name": "Page 2", "rate": "0.2000"},
        )
        resp = client.get("/v1/taxes/?skip=0&limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_tax(self, client):
        """GET /v1/taxes/{code} returns a tax."""
        client.post(
            "/v1/taxes/",
            json={"code": "GET_TAX", "name": "Get Tax", "rate": "0.1500"},
        )
        resp = client.get("/v1/taxes/GET_TAX")
        assert resp.status_code == 200
        assert resp.json()["code"] == "GET_TAX"

    def test_get_tax_not_found(self, client):
        """GET /v1/taxes/{code} returns 404 for missing tax."""
        resp = client.get("/v1/taxes/MISSING")
        assert resp.status_code == 404

    def test_update_tax(self, client):
        """PUT /v1/taxes/{code} updates a tax."""
        client.post(
            "/v1/taxes/",
            json={"code": "UPD", "name": "Original", "rate": "0.1000"},
        )
        resp = client.put(
            "/v1/taxes/UPD",
            json={"name": "Updated", "rate": "0.1500"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
        assert resp.json()["rate"] == "0.1500"

    def test_update_tax_not_found(self, client):
        """PUT /v1/taxes/{code} returns 404 for missing tax."""
        resp = client.put(
            "/v1/taxes/MISSING",
            json={"name": "X"},
        )
        assert resp.status_code == 404

    def test_delete_tax(self, client):
        """DELETE /v1/taxes/{code} deletes a tax."""
        client.post(
            "/v1/taxes/",
            json={"code": "DEL", "name": "Delete Me", "rate": "0.1000"},
        )
        resp = client.delete("/v1/taxes/DEL")
        assert resp.status_code == 204

        # Verify deleted
        resp = client.get("/v1/taxes/DEL")
        assert resp.status_code == 404

    def test_delete_tax_not_found(self, client):
        """DELETE /v1/taxes/{code} returns 404 for missing tax."""
        resp = client.delete("/v1/taxes/MISSING")
        assert resp.status_code == 404

    def test_apply_tax(self, client):
        """POST /v1/taxes/apply applies a tax to an entity and returns tax name/code."""
        client.post(
            "/v1/taxes/",
            json={"code": "APPLY_TAX", "name": "Apply Tax", "rate": "0.1000"},
        )
        entity_id = str(uuid4())
        resp = client.post(
            "/v1/taxes/apply",
            json={
                "tax_code": "APPLY_TAX",
                "taxable_type": "customer",
                "taxable_id": entity_id,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["taxable_type"] == "customer"
        assert data["taxable_id"] == entity_id
        assert data["tax_name"] == "Apply Tax"
        assert data["tax_code"] == "APPLY_TAX"

    def test_apply_tax_not_found(self, client):
        """POST /v1/taxes/apply with bad code returns 404."""
        resp = client.post(
            "/v1/taxes/apply",
            json={
                "tax_code": "BAD_CODE",
                "taxable_type": "customer",
                "taxable_id": str(uuid4()),
            },
        )
        assert resp.status_code == 404

    def test_remove_applied_tax(self, client):
        """DELETE /v1/taxes/applied/{id} removes an applied tax."""
        # Create tax and apply it
        client.post(
            "/v1/taxes/",
            json={"code": "RM_TAX", "name": "Remove Tax", "rate": "0.1000"},
        )
        entity_id = str(uuid4())
        apply_resp = client.post(
            "/v1/taxes/apply",
            json={
                "tax_code": "RM_TAX",
                "taxable_type": "plan",
                "taxable_id": entity_id,
            },
        )
        applied_id = apply_resp.json()["id"]

        resp = client.delete(f"/v1/taxes/applied/{applied_id}")
        assert resp.status_code == 204

    def test_remove_applied_tax_not_found(self, client):
        """DELETE /v1/taxes/applied/{id} returns 404 for missing applied tax."""
        resp = client.delete(f"/v1/taxes/applied/{uuid4()}")
        assert resp.status_code == 404

    def test_create_tax_with_org_flag(self, client):
        """POST /v1/taxes with applied_to_organization flag."""
        resp = client.post(
            "/v1/taxes/",
            json={
                "code": "ORG",
                "name": "Org Tax",
                "rate": "0.0500",
                "applied_to_organization": True,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["applied_to_organization"] is True

    def test_apply_tax_to_multiple_entity_types(self, client):
        """Apply same tax to different entity types."""
        client.post(
            "/v1/taxes/",
            json={"code": "MULTI", "name": "Multi Tax", "rate": "0.1000"},
        )
        for entity_type in ["customer", "plan", "charge", "fee"]:
            resp = client.post(
                "/v1/taxes/apply",
                json={
                    "tax_code": "MULTI",
                    "taxable_type": entity_type,
                    "taxable_id": str(uuid4()),
                },
            )
            assert resp.status_code == 201
            assert resp.json()["taxable_type"] == entity_type

    def test_list_applied_taxes(self, client):
        """GET /v1/taxes/applied returns applied taxes with tax name and code."""
        client.post(
            "/v1/taxes/",
            json={"code": "LIST_AT", "name": "List AT", "rate": "0.1000"},
        )
        entity_id = str(uuid4())
        client.post(
            "/v1/taxes/apply",
            json={
                "tax_code": "LIST_AT",
                "taxable_type": "customer",
                "taxable_id": entity_id,
            },
        )
        resp = client.get(
            f"/v1/taxes/applied?taxable_type=customer&taxable_id={entity_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["taxable_type"] == "customer"
        assert data[0]["taxable_id"] == entity_id
        assert data[0]["tax_name"] == "List AT"
        assert data[0]["tax_code"] == "LIST_AT"

    def test_list_applied_taxes_empty(self, client):
        """GET /v1/taxes/applied returns empty list when no taxes applied."""
        resp = client.get(
            f"/v1/taxes/applied?taxable_type=customer&taxable_id={uuid4()}"
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_applied_taxes_multiple(self, client):
        """GET /v1/taxes/applied returns multiple applied taxes."""
        client.post(
            "/v1/taxes/",
            json={"code": "LAM1", "name": "LAM Tax 1", "rate": "0.1000"},
        )
        client.post(
            "/v1/taxes/",
            json={"code": "LAM2", "name": "LAM Tax 2", "rate": "0.2000"},
        )
        entity_id = str(uuid4())
        client.post(
            "/v1/taxes/apply",
            json={
                "tax_code": "LAM1",
                "taxable_type": "invoice",
                "taxable_id": entity_id,
            },
        )
        client.post(
            "/v1/taxes/apply",
            json={
                "tax_code": "LAM2",
                "taxable_type": "invoice",
                "taxable_id": entity_id,
            },
        )
        resp = client.get(
            f"/v1/taxes/applied?taxable_type=invoice&taxable_id={entity_id}"
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        names = {item["tax_name"] for item in items}
        codes = {item["tax_code"] for item in items}
        assert names == {"LAM Tax 1", "LAM Tax 2"}
        assert codes == {"LAM1", "LAM2"}
