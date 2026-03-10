from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.add_on import AddOn
from app.models.api_key import ApiKey
from app.models.applied_add_on import AppliedAddOn
from app.models.applied_coupon import AppliedCoupon
from app.models.applied_tax import AppliedTax
from app.models.applied_usage_threshold import AppliedUsageThreshold
from app.models.audit_log import AuditLog
from app.models.billable_metric import BillableMetric
from app.models.billing_entity import BillingEntity
from app.models.charge import Charge
from app.models.commitment import Commitment
from app.models.coupon import Coupon
from app.models.credit_note import CreditNote
from app.models.credit_note_item import CreditNoteItem
from app.models.customer import Customer
from app.models.daily_usage import DailyUsage
from app.models.data_export import DataExport
from app.models.dunning_campaign import DunningCampaign
from app.models.entitlement import Entitlement
from app.models.event import Event
from app.models.feature import Feature
from app.models.fee import Fee
from app.models.idempotency_record import IdempotencyRecord
from app.models.integration import Integration
from app.models.invoice import Invoice
from app.models.invoice_settlement import InvoiceSettlement
from app.models.notification import Notification
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.payment import Payment
from app.models.payment_method import PaymentMethod
from app.models.payment_request import PaymentRequest
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.tax import Tax
from app.models.usage_alert import UsageAlert
from app.models.usage_threshold import UsageThreshold
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction
from app.models.webhook import Webhook
from app.models.webhook_endpoint import WebhookEndpoint
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


class OrganizationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[Organization]:
        query = self.db.query(Organization)
        query = apply_order_by(query, Organization, order_by)
        return query.offset(skip).limit(limit).all()

    def get_by_id(self, org_id: UUID) -> Organization | None:
        return self.db.query(Organization).filter(Organization.id == org_id).first()

    def _generate_unique_slug(self, name: str) -> str:
        """Generate a unique slug from the organization name."""
        base_slug = _slugify(name)
        if not base_slug:
            base_slug = "org"
        slug = base_slug
        counter = 1
        while (
            self.db.query(Organization)
            .filter(Organization.slug == slug)
            .first()
            is not None
        ):
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def create(self, data: OrganizationCreate) -> Organization:
        dump = data.model_dump()
        dump["slug"] = self._generate_unique_slug(data.name)
        org = Organization(**dump)
        self.db.add(org)
        self.db.commit()
        self.db.refresh(org)
        return org

    def update(self, org_id: UUID, data: OrganizationUpdate) -> Organization | None:
        org = self.get_by_id(org_id)
        if not org:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(org, key, value)
        self.db.commit()
        self.db.refresh(org)
        return org

    def delete(self, org_id: UUID) -> bool:
        org = self.get_by_id(org_id)
        if not org:
            return False
        self.db.delete(org)
        self.db.commit()
        return True

    def delete_by_organization(self, org_id: UUID) -> bool:
        """Hard-delete an organization and all related records.

        Deletes in dependency order to respect RESTRICT foreign keys.
        All deletes run within a single transaction.
        """
        org = self.get_by_id(org_id)
        if not org:
            return False

        db = self.db

        # --- Models WITHOUT organization_id (subquery filtering) ---

        # 1. CreditNoteItem via CreditNote
        org_credit_notes = select(CreditNote.id).where(CreditNote.organization_id == org_id)
        db.query(CreditNoteItem).filter(
            CreditNoteItem.credit_note_id.in_(org_credit_notes)
        ).delete(synchronize_session=False)

        # 2. InvoiceSettlement via Invoice
        org_invoices = select(Invoice.id).where(Invoice.organization_id == org_id)
        db.query(InvoiceSettlement).filter(
            InvoiceSettlement.invoice_id.in_(org_invoices)
        ).delete(synchronize_session=False)

        # 3. AppliedTax via Tax
        org_taxes = select(Tax.id).where(Tax.organization_id == org_id)
        db.query(AppliedTax).filter(
            AppliedTax.tax_id.in_(org_taxes)
        ).delete(synchronize_session=False)

        # 4. AppliedAddOn via AddOn
        org_add_ons = select(AddOn.id).where(AddOn.organization_id == org_id)
        db.query(AppliedAddOn).filter(
            AppliedAddOn.add_on_id.in_(org_add_ons)
        ).delete(synchronize_session=False)

        # 5. DailyUsage via Subscription
        org_subscriptions = select(Subscription.id).where(Subscription.organization_id == org_id)
        db.query(DailyUsage).filter(
            DailyUsage.subscription_id.in_(org_subscriptions)
        ).delete(synchronize_session=False)

        # 6. Webhook via WebhookEndpoint
        org_webhook_endpoints = select(WebhookEndpoint.id).where(
            WebhookEndpoint.organization_id == org_id
        )
        db.query(Webhook).filter(
            Webhook.webhook_endpoint_id.in_(org_webhook_endpoints)
        ).delete(synchronize_session=False)

        # --- Models WITH organization_id (direct filter) ---

        # 7-17: Various dependent tables
        for model in [
            AppliedUsageThreshold,  # 7
            AppliedCoupon,          # 8
            WalletTransaction,      # 9
            Payment,                # 10
            CreditNote,             # 11
            Fee,                    # 12
            UsageAlert,             # 13 (UsageAlertTrigger auto-CASCADEs)
            Notification,           # 14
            AuditLog,               # 15
            IdempotencyRecord,      # 16
            DataExport,             # 17
        ]:
            db.query(model).filter(
                model.organization_id == org_id  # type: ignore[attr-defined]
            ).delete(synchronize_session=False)

        # 18-26: Mid-level tables
        for model in [
            Invoice,                # 18
            PaymentRequest,         # 19 (PaymentRequestInvoice auto-CASCADEs)
            PaymentMethod,          # 20
            Wallet,                 # 21
            UsageThreshold,         # 22
            Commitment,             # 23
            Entitlement,            # 24
            Charge,                 # 25 (ChargeFilter/ChargeFilterValue auto-CASCADE)
            Subscription,           # 26
        ]:
            db.query(model).filter(
                model.organization_id == org_id  # type: ignore[attr-defined]
            ).delete(synchronize_session=False)

        # 27-39: Core tables
        for model in [
            Event,                  # 27
            Integration,            # 28 (IntegrationCustomer/Mapping/SyncHistory auto-CASCADE)
            Plan,                   # 29
            BillableMetric,         # 30 (BillableMetricFilter auto-CASCADEs)
            Feature,                # 31
            AddOn,                  # 32
            Coupon,                 # 33
            Tax,                    # 34
            DunningCampaign,        # 35 (DunningCampaignThreshold auto-CASCADEs)
            Customer,               # 36
            BillingEntity,          # 37
            WebhookEndpoint,        # 38
            ApiKey,                 # 39
            OrganizationMember,     # 40
        ]:
            db.query(model).filter(
                model.organization_id == org_id  # type: ignore[attr-defined]
            ).delete(synchronize_session=False)

        # 41. Finally delete the organization itself
        db.delete(org)
        db.commit()
        return True
