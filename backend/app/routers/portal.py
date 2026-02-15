"""Customer self-service portal API endpoints."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_portal_customer
from app.core.database import get_db
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.payment_method import PaymentMethod
from app.models.subscription import Subscription
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction as WalletTransactionModel
from app.repositories.add_on_repository import AddOnRepository
from app.repositories.applied_add_on_repository import AppliedAddOnRepository
from app.repositories.applied_coupon_repository import AppliedCouponRepository
from app.repositories.coupon_repository import CouponRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.entitlement_repository import EntitlementRepository
from app.repositories.feature_repository import FeatureRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.wallet_repository import WalletRepository
from app.repositories.wallet_transaction_repository import WalletTransactionRepository
from app.schemas.add_on import (
    PortalAddOnResponse,
    PortalPurchaseAddOnResponse,
    PortalPurchasedAddOnResponse,
)
from app.schemas.coupon import (
    PortalAppliedCouponResponse,
    PortalRedeemCouponRequest,
)
from app.schemas.customer import CustomerResponse, PortalProfileUpdate
from app.schemas.invoice import InvoiceResponse
from app.schemas.organization import PortalBrandingResponse
from app.schemas.payment import PaymentResponse
from app.schemas.payment_method import PaymentMethodCreate, PaymentMethodResponse
from app.schemas.portal import (
    PortalDashboardSummaryResponse,
    PortalNextBillingInfo,
    PortalQuickActions,
    PortalUpcomingCharge,
    PortalUsageProgress,
)
from app.schemas.subscription import (
    ChangePlanPreviewResponse,
    PlanSummary,
    PortalChangePlanRequest,
    PortalPlanResponse,
    PortalSubscriptionResponse,
    ProrationDetail,
    SubscriptionResponse,
)
from app.schemas.usage import CurrentUsageResponse
from app.schemas.wallet import (
    BalanceTimelineResponse,
    PortalTopUpRequest,
    PortalTopUpResponse,
    WalletResponse,
)
from app.schemas.wallet_transaction import WalletTransactionResponse
from app.services.add_on_service import AddOnService
from app.services.coupon_service import CouponApplicationService
from app.services.pdf_service import PdfService
from app.services.subscription_lifecycle import SubscriptionLifecycleService
from app.services.usage_query_service import UsageQueryService
from app.services.wallet_service import WalletService

router = APIRouter()


# ── Dashboard Summary ─────────────────────────────────────────────────


@router.get(
    "/dashboard_summary",
    response_model=PortalDashboardSummaryResponse,
    summary="Get portal dashboard summary",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def get_portal_dashboard_summary(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> PortalDashboardSummaryResponse:
    """Aggregated dashboard: billing, charges, usage, actions."""
    customer_id, organization_id = portal_auth

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    sub_repo = SubscriptionRepository(db)
    plan_repo = PlanRepository(db)
    invoice_repo = InvoiceRepository(db)
    wallet_repo = WalletRepository(db)
    entitlement_repo = EntitlementRepository(db)
    feature_repo = FeatureRepository(db)

    subscriptions = sub_repo.get_by_customer_id(customer_id, organization_id)
    active_subs = [s for s in subscriptions if s.status in ("active", "pending")]

    now = datetime.now(UTC)

    # ── Next billing dates ──
    next_billing: list[PortalNextBillingInfo] = []
    for sub in active_subs:
        plan = plan_repo.get_by_id(UUID(str(sub.plan_id)), organization_id)
        if not plan:
            continue  # pragma: no cover
        interval_str = str(plan.interval)
        total_days = _PORTAL_INTERVAL_DAYS.get(interval_str, 30)

        period_anchor = sub.started_at or sub.created_at
        if period_anchor:
            anchor = period_anchor if period_anchor.tzinfo else period_anchor.replace(tzinfo=UTC)
        else:  # pragma: no cover
            anchor = now

        if anchor > now:
            nbd = anchor
            days_until = (anchor - now).days
        else:
            elapsed_days = (now - anchor).days
            periods_elapsed = elapsed_days // total_days
            nbd = anchor + timedelta(days=(periods_elapsed + 1) * total_days)
            days_until = (nbd - now).days

        next_billing.append(
            PortalNextBillingInfo(
                subscription_id=sub.id,  # type: ignore[arg-type]
                subscription_external_id=str(sub.external_id),
                plan_name=str(plan.name),
                plan_interval=interval_str,
                next_billing_date=nbd,  # type: ignore[arg-type]
                days_until_next_billing=days_until,
                amount_cents=int(plan.amount_cents),
                currency=str(plan.currency),
            )
        )

    # ── Upcoming charges estimate ──
    upcoming_charges: list[PortalUpcomingCharge] = []
    usage_service = UsageQueryService(db)
    for sub in active_subs:
        plan = plan_repo.get_by_id(UUID(str(sub.plan_id)), organization_id)
        if not plan:
            continue  # pragma: no cover
        base_amount = int(plan.amount_cents)

        usage_amount = 0
        try:
            usage = usage_service.get_current_usage(
                subscription_id=UUID(str(sub.id)),
                external_customer_id=str(customer.external_id),
            )
            usage_amount = int(usage.amount_cents)
        except Exception:
            pass  # If usage calculation fails, default to 0

        upcoming_charges.append(
            PortalUpcomingCharge(
                subscription_id=sub.id,  # type: ignore[arg-type]
                subscription_external_id=str(sub.external_id),
                plan_name=str(plan.name),
                base_amount_cents=base_amount,
                usage_amount_cents=usage_amount,
                total_estimated_cents=base_amount + usage_amount,
                currency=str(plan.currency),
            )
        )

    # ── Usage progress vs. plan limits ──
    usage_progress: list[PortalUsageProgress] = []
    seen_features: set[UUID] = set()
    for sub in active_subs:
        plan_id = UUID(str(sub.plan_id))
        entitlements = entitlement_repo.get_by_plan_id(plan_id, organization_id)
        for ent in entitlements:
            feature_id = UUID(str(ent.feature_id))
            if feature_id in seen_features:
                continue
            seen_features.add(feature_id)
            feature = feature_repo.get_by_id(feature_id, organization_id)
            if not feature:
                continue  # pragma: no cover

            current_usage = None
            usage_pct = None
            if str(feature.feature_type) == "quantity":
                try:
                    limit_val = float(str(ent.value))
                    if limit_val > 0:
                        # Try to get current usage for this subscription
                        usage_resp = usage_service.get_current_usage(
                            subscription_id=UUID(str(sub.id)),
                            external_customer_id=str(customer.external_id),
                        )
                        # Sum up usage for charges whose metric code matches feature code
                        feature_code = str(feature.code)
                        total_units = sum(
                            float(c.units) for c in usage_resp.charges
                            if c.billable_metric.code == feature_code
                        )
                        current_usage = Decimal(str(total_units))
                        usage_pct = min(100.0, (total_units / limit_val) * 100)
                except (ValueError, Exception):
                    pass  # Non-numeric entitlement or usage query failure

            usage_progress.append(
                PortalUsageProgress(
                    feature_name=str(feature.name),
                    feature_code=str(feature.code),
                    feature_type=str(feature.feature_type),
                    entitlement_value=str(ent.value),
                    current_usage=current_usage,
                    usage_percentage=usage_pct,
                )
            )

    # ── Quick actions ──
    invoices = invoice_repo.get_all(
        organization_id=organization_id,
        customer_id=customer_id,
        status=InvoiceStatus.FINALIZED,
        limit=1000,
    )
    outstanding_total = sum(int(inv.total) for inv in invoices)

    wallets = wallet_repo.get_by_customer_id(customer_id)
    active_wallets = [w for w in wallets if str(w.status) == "active"]
    wallet_balance = sum(int(w.balance_cents) for w in active_wallets)

    currency = str(customer.currency) if customer.currency else "USD"

    quick_actions = PortalQuickActions(
        outstanding_invoice_count=len(invoices),
        outstanding_amount_cents=outstanding_total,
        has_wallet=len(active_wallets) > 0,
        wallet_balance_cents=wallet_balance,
        has_active_subscription=len(active_subs) > 0,
        currency=currency,
    )

    return PortalDashboardSummaryResponse(
        next_billing=next_billing,
        upcoming_charges=upcoming_charges,
        usage_progress=usage_progress,
        quick_actions=quick_actions,
    )


_PORTAL_INTERVAL_DAYS = {
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
    "yearly": 365,
}


@router.get(
    "/customer",
    response_model=CustomerResponse,
    summary="Get customer profile",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Customer not found"},
    },
)
async def get_portal_customer_profile(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> Customer:
    """Get the authenticated customer's profile information."""
    customer_id, organization_id = portal_auth
    repo = CustomerRepository(db)
    customer = repo.get_by_id(customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.patch(
    "/profile",
    response_model=CustomerResponse,
    summary="Update customer profile",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Customer not found"},
        422: {"description": "Validation error"},
    },
)
async def update_portal_profile(
    data: PortalProfileUpdate,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> Customer:
    """Update the authenticated customer's profile (name, email, timezone)."""
    customer_id, organization_id = portal_auth
    repo = CustomerRepository(db)
    customer = repo.get_by_id(customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.get(
    "/branding",
    response_model=PortalBrandingResponse,
    summary="Get organization branding for portal",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Organization not found"},
    },
)
async def get_portal_branding(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> PortalBrandingResponse:
    """Get the organization's branding information for portal display."""
    _customer_id, organization_id = portal_auth
    repo = OrganizationRepository(db)
    org = repo.get_by_id(organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return PortalBrandingResponse(
        name=org.name,  # type: ignore[arg-type]
        logo_url=org.logo_url,  # type: ignore[arg-type]
        accent_color=org.portal_accent_color,  # type: ignore[arg-type]
        welcome_message=org.portal_welcome_message,  # type: ignore[arg-type]
    )


@router.get(
    "/invoices",
    response_model=list[InvoiceResponse],
    summary="List customer invoices",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def list_portal_invoices(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[Invoice]:
    """List invoices for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = InvoiceRepository(db)
    return repo.get_all(
        organization_id=organization_id,
        customer_id=customer_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get invoice detail",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Invoice not found"},
    },
)
async def get_portal_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> Invoice:
    """Get a specific invoice for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = InvoiceRepository(db)
    invoice = repo.get_by_id(invoice_id, organization_id)
    if not invoice or UUID(str(invoice.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get(
    "/invoices/{invoice_id}/download_pdf",
    summary="Download invoice PDF",
    responses={
        400: {"description": "Invoice must be finalized or paid to generate PDF"},
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Invoice not found"},
    },
)
async def download_portal_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> Response:
    """Download a PDF for a finalized or paid invoice."""
    customer_id, organization_id = portal_auth
    invoice_repo = InvoiceRepository(db)
    invoice = invoice_repo.get_by_id(invoice_id, organization_id)
    if not invoice or UUID(str(invoice.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status not in (InvoiceStatus.FINALIZED.value, InvoiceStatus.PAID.value):
        raise HTTPException(
            status_code=400,
            detail="Invoice must be finalized or paid to generate PDF",
        )

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(customer_id)

    org_repo = OrganizationRepository(db)
    organization = org_repo.get_by_id(organization_id)

    fee_repo = FeeRepository(db)
    fees = fee_repo.get_by_invoice_id(invoice_id)

    pdf_service = PdfService()
    pdf_bytes = pdf_service.generate_invoice_pdf(
        invoice=invoice,
        fees=fees,
        customer=customer,  # type: ignore[arg-type]
        organization=organization,  # type: ignore[arg-type]
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        },
    )


@router.get(
    "/current_usage",
    response_model=CurrentUsageResponse,
    summary="Get current usage",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Subscription not found"},
    },
)
async def get_portal_current_usage(
    subscription_id: UUID = Query(...),
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> CurrentUsageResponse:
    """Get current usage for the authenticated customer's subscription."""
    customer_id, organization_id = portal_auth

    from app.repositories.subscription_repository import SubscriptionRepository

    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(subscription_id, organization_id)
    if not subscription or UUID(str(subscription.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(customer_id)
    if not customer:  # pragma: no cover – FK guarantees existence
        raise HTTPException(status_code=404, detail="Customer not found")

    service = UsageQueryService(db)
    return service.get_current_usage(
        subscription_id=subscription_id,
        external_customer_id=str(customer.external_id),
    )


@router.get(
    "/payments",
    response_model=list[PaymentResponse],
    summary="List customer payments",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def list_portal_payments(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[Payment]:
    """List payments for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = PaymentRepository(db)
    return repo.get_all(
        organization_id=organization_id,
        customer_id=customer_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/wallet",
    response_model=list[WalletResponse],
    summary="Get wallet balance and transactions",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def get_portal_wallet(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[Wallet]:
    """Get wallet balance and recent transactions for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = WalletRepository(db)
    return repo.get_all(
        organization_id=organization_id,
        customer_id=customer_id,
    )


@router.get(
    "/wallet/{wallet_id}/transactions",
    response_model=list[WalletTransactionResponse],
    summary="List wallet transactions",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Wallet not found"},
    },
)
async def list_portal_wallet_transactions(
    wallet_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list["WalletTransactionModel"]:
    """List transactions for a customer's wallet."""
    customer_id, organization_id = portal_auth
    wallet_repo = WalletRepository(db)
    wallet = wallet_repo.get_by_id(wallet_id, organization_id)
    if not wallet or UUID(str(wallet.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Wallet not found")
    txn_repo = WalletTransactionRepository(db)
    return txn_repo.get_by_wallet_id(wallet_id, skip=skip, limit=limit)


@router.get(
    "/wallet/{wallet_id}/balance_timeline",
    response_model=BalanceTimelineResponse,
    summary="Get wallet balance timeline",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Wallet not found"},
    },
)
async def get_portal_wallet_balance_timeline(
    wallet_id: UUID,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> BalanceTimelineResponse:
    """Get daily balance timeline for a customer's wallet."""
    customer_id, organization_id = portal_auth
    wallet_repo = WalletRepository(db)
    wallet = wallet_repo.get_by_id(wallet_id, organization_id)
    if not wallet or UUID(str(wallet.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Wallet not found")
    txn_repo = WalletTransactionRepository(db)
    raw_points = txn_repo.daily_balance_timeline(wallet_id)
    from app.schemas.wallet import BalanceTimelinePoint

    running_balance = Decimal("0")
    points: list[BalanceTimelinePoint] = []
    for row in raw_points:
        inbound = Decimal(str(row["inbound"]))
        outbound = Decimal(str(row["outbound"]))
        running_balance += inbound - outbound
        points.append(
            BalanceTimelinePoint(
                date=str(row["date"]),
                inbound=inbound,
                outbound=outbound,
                balance=running_balance,
            )
        )
    return BalanceTimelineResponse(wallet_id=wallet_id, points=points)


@router.post(
    "/wallet/{wallet_id}/top_up",
    response_model=PortalTopUpResponse,
    summary="Request a wallet top-up",
    responses={
        400: {"description": "Wallet is not active or invalid credits"},
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Wallet not found"},
    },
)
async def portal_wallet_top_up(
    wallet_id: UUID,
    data: PortalTopUpRequest,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> PortalTopUpResponse:
    """Top up a customer's wallet with credits."""
    customer_id, organization_id = portal_auth
    wallet_repo = WalletRepository(db)
    wallet = wallet_repo.get_by_id(wallet_id, organization_id)
    if not wallet or UUID(str(wallet.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Wallet not found")
    if str(wallet.status) != "active":
        raise HTTPException(status_code=400, detail="Wallet is not active")
    service = WalletService(db)
    try:
        updated = service.top_up_wallet(
            wallet_id=wallet_id,
            credits=data.credits,
            source="manual",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if not updated:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Top-up failed")
    return PortalTopUpResponse(
        wallet_id=wallet_id,
        credits_added=data.credits,
        new_balance_cents=Decimal(str(updated.balance_cents)),
        new_credits_balance=Decimal(str(updated.credits_balance)),
    )


@router.get(
    "/payment_methods",
    response_model=list[PaymentMethodResponse],
    summary="List customer payment methods",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def list_portal_payment_methods(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[PaymentMethod]:
    """List payment methods for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = PaymentMethodRepository(db)
    return repo.get_by_customer_id(customer_id, organization_id)


@router.post(
    "/payment_methods",
    response_model=PaymentMethodResponse,
    status_code=201,
    summary="Add a payment method",
    responses={
        401: {"description": "Invalid or expired portal token"},
        422: {"description": "Validation error"},
    },
)
async def add_portal_payment_method(
    data: PaymentMethodCreate,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> PaymentMethod:
    """Add a new payment method for the authenticated customer."""
    customer_id, organization_id = portal_auth
    if data.customer_id != customer_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot add payment method for another customer",
        )
    repo = PaymentMethodRepository(db)
    return repo.create(data, organization_id)


@router.delete(
    "/payment_methods/{payment_method_id}",
    status_code=204,
    summary="Remove a payment method",
    responses={
        400: {"description": "Cannot delete default payment method"},
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Payment method not found"},
    },
)
async def remove_portal_payment_method(
    payment_method_id: UUID,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> None:
    """Remove a payment method. Cannot remove the default payment method."""
    customer_id, organization_id = portal_auth
    repo = PaymentMethodRepository(db)
    pm = repo.get_by_id(payment_method_id, organization_id)
    if not pm or UUID(str(pm.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Payment method not found")
    if pm.is_default:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the default payment method",
        )
    repo.delete(payment_method_id, organization_id)


@router.post(
    "/payment_methods/{payment_method_id}/set_default",
    response_model=PaymentMethodResponse,
    summary="Set default payment method",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Payment method not found"},
    },
)
async def set_portal_default_payment_method(
    payment_method_id: UUID,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> PaymentMethod:
    """Set a payment method as the default for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = PaymentMethodRepository(db)
    pm = repo.get_by_id(payment_method_id, organization_id)
    if not pm or UUID(str(pm.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Payment method not found")
    result = repo.set_default(payment_method_id)
    if not result:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Payment method not found")
    return result


# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------

INTERVAL_DAYS = {
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
    "yearly": 365,
}


def _build_portal_subscription(
    subscription: Subscription,
    plan_repo: PlanRepository,
    organization_id: UUID,
) -> PortalSubscriptionResponse:
    """Build a PortalSubscriptionResponse from a Subscription ORM object."""
    plan = plan_repo.get_by_id(UUID(str(subscription.plan_id)), organization_id)
    plan_summary = PlanSummary(
        id=plan.id,  # type: ignore[union-attr, arg-type]
        name=str(plan.name),  # type: ignore[union-attr]
        code=str(plan.code),  # type: ignore[union-attr]
        interval=str(plan.interval),  # type: ignore[union-attr]
        amount_cents=int(plan.amount_cents),  # type: ignore[union-attr]
        currency=str(plan.currency),  # type: ignore[union-attr]
    )

    pending_downgrade_plan: PlanSummary | None = None
    if subscription.downgraded_at and subscription.previous_plan_id:
        target_plan = plan_repo.get_by_id(
            UUID(str(subscription.previous_plan_id)),
            organization_id,
        )
        if target_plan:  # pragma: no branch – FK guarantees plan exists
            pending_downgrade_plan = PlanSummary(
                id=target_plan.id,  # type: ignore[arg-type]
                name=str(target_plan.name),
                code=str(target_plan.code),
                interval=str(target_plan.interval),
                amount_cents=int(target_plan.amount_cents),
                currency=str(target_plan.currency),
            )

    return PortalSubscriptionResponse(
        id=subscription.id,  # type: ignore[arg-type]
        external_id=str(subscription.external_id),
        status=subscription.status,  # type: ignore[arg-type]
        started_at=subscription.started_at,  # type: ignore[arg-type]
        canceled_at=subscription.canceled_at,  # type: ignore[arg-type]
        paused_at=subscription.paused_at,  # type: ignore[arg-type]
        downgraded_at=subscription.downgraded_at,  # type: ignore[arg-type]
        created_at=subscription.created_at,  # type: ignore[arg-type]
        plan=plan_summary,
        pending_downgrade_plan=pending_downgrade_plan,
    )


@router.get(
    "/subscriptions",
    response_model=list[PortalSubscriptionResponse],
    summary="List customer subscriptions",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def list_portal_subscriptions(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[PortalSubscriptionResponse]:
    """List subscriptions for the authenticated customer with plan details."""
    customer_id, organization_id = portal_auth
    sub_repo = SubscriptionRepository(db)
    plan_repo = PlanRepository(db)
    subscriptions = sub_repo.get_by_customer_id(customer_id, organization_id)
    return [
        _build_portal_subscription(s, plan_repo, organization_id)
        for s in subscriptions
    ]


@router.get(
    "/subscriptions/{subscription_id}",
    response_model=PortalSubscriptionResponse,
    summary="Get subscription detail",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Subscription not found"},
    },
)
async def get_portal_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> PortalSubscriptionResponse:
    """Get a specific subscription for the authenticated customer."""
    customer_id, organization_id = portal_auth
    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(subscription_id, organization_id)
    if not subscription or UUID(str(subscription.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    plan_repo = PlanRepository(db)
    return _build_portal_subscription(subscription, plan_repo, organization_id)


@router.get(
    "/plans",
    response_model=list[PortalPlanResponse],
    summary="List available plans",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def list_portal_plans(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[PortalPlanResponse]:
    """List all available plans for the organization."""
    _customer_id, organization_id = portal_auth
    plan_repo = PlanRepository(db)
    plans = plan_repo.get_all(organization_id)
    return [
        PortalPlanResponse(
            id=p.id,  # type: ignore[arg-type]
            name=str(p.name),
            code=str(p.code),
            description=p.description,  # type: ignore[arg-type]
            interval=str(p.interval),
            amount_cents=int(p.amount_cents),
            currency=str(p.currency),
        )
        for p in plans
    ]


@router.post(
    "/subscriptions/{subscription_id}/change_plan_preview",
    response_model=ChangePlanPreviewResponse,
    summary="Preview plan change with proration",
    responses={
        400: {"description": "Invalid plan or same plan"},
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Subscription or plan not found"},
    },
)
async def portal_change_plan_preview(
    subscription_id: UUID,
    data: PortalChangePlanRequest,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> ChangePlanPreviewResponse:
    """Preview a plan change showing price comparison and proration details."""
    customer_id, organization_id = portal_auth
    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(subscription_id, organization_id)
    if not subscription or UUID(str(subscription.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    plan_repo = PlanRepository(db)
    current_plan = plan_repo.get_by_id(UUID(str(subscription.plan_id)), organization_id)
    if not current_plan:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Current plan not found")

    new_plan = plan_repo.get_by_id(data.new_plan_id, organization_id)
    if not new_plan:
        raise HTTPException(status_code=404, detail="New plan not found")

    if str(subscription.plan_id) == str(data.new_plan_id):
        raise HTTPException(status_code=400, detail="New plan must be different from current plan")

    effective = datetime.now(UTC)
    interval_str = str(current_plan.interval)
    total_days = INTERVAL_DAYS.get(interval_str, 30)

    period_anchor = subscription.started_at or subscription.created_at
    if period_anchor:
        anchor = period_anchor if period_anchor.tzinfo else period_anchor.replace(tzinfo=UTC)
        elapsed = (effective - anchor).days % total_days
        days_remaining = max(total_days - elapsed, 0)
    else:  # pragma: no cover — created_at always set by DB
        days_remaining = total_days

    current_amount: int = current_plan.amount_cents  # type: ignore[assignment]
    new_amount: int = new_plan.amount_cents  # type: ignore[assignment]
    credit_cents = int(current_amount * days_remaining / total_days)
    charge_cents = int(new_amount * days_remaining / total_days)
    net_cents = charge_cents - credit_cents

    return ChangePlanPreviewResponse(
        current_plan=PlanSummary(
            id=current_plan.id,  # type: ignore[arg-type]
            name=str(current_plan.name),
            code=str(current_plan.code),
            interval=interval_str,
            amount_cents=current_amount,
            currency=str(current_plan.currency),
        ),
        new_plan=PlanSummary(
            id=new_plan.id,  # type: ignore[arg-type]
            name=str(new_plan.name),
            code=str(new_plan.code),
            interval=str(new_plan.interval),
            amount_cents=new_amount,
            currency=str(new_plan.currency),
        ),
        effective_date=effective,
        proration=ProrationDetail(
            days_remaining=days_remaining,
            total_days=total_days,
            current_plan_credit_cents=credit_cents,
            new_plan_charge_cents=charge_cents,
            net_amount_cents=net_cents,
        ),
    )


@router.post(
    "/subscriptions/{subscription_id}/change_plan",
    response_model=SubscriptionResponse,
    summary="Change subscription plan",
    responses={
        400: {"description": "Invalid plan change"},
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Subscription not found"},
    },
)
async def portal_change_plan(
    subscription_id: UUID,
    data: PortalChangePlanRequest,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> SubscriptionResponse:
    """Change a subscription's plan (upgrade or downgrade)."""
    customer_id, organization_id = portal_auth
    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(subscription_id, organization_id)
    if not subscription or UUID(str(subscription.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if subscription.status != "active":
        raise HTTPException(status_code=400, detail="Can only change plan for active subscriptions")

    if str(subscription.plan_id) == str(data.new_plan_id):
        raise HTTPException(status_code=400, detail="New plan must be different from current plan")

    plan_repo = PlanRepository(db)
    new_plan = plan_repo.get_by_id(data.new_plan_id, organization_id)
    if not new_plan:
        raise HTTPException(status_code=404, detail="New plan not found")

    current_plan = plan_repo.get_by_id(UUID(str(subscription.plan_id)), organization_id)
    current_amount = int(current_plan.amount_cents) if current_plan else 0
    new_amount = int(new_plan.amount_cents)

    lifecycle = SubscriptionLifecycleService(db)
    if new_amount >= current_amount:
        lifecycle.upgrade_plan(subscription_id, data.new_plan_id)
    else:
        lifecycle.downgrade_plan(subscription_id, data.new_plan_id, effective_at="immediate")

    db.refresh(subscription)
    return SubscriptionResponse.model_validate(subscription)


# ── Add-ons ──────────────────────────────────────────────────────────────


@router.get(
    "/add_ons",
    response_model=list[PortalAddOnResponse],
    summary="List available add-ons",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def list_portal_add_ons(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[PortalAddOnResponse]:
    """List all add-ons available for purchase."""
    _customer_id, organization_id = portal_auth
    add_on_repo = AddOnRepository(db)
    add_ons = add_on_repo.get_all(organization_id)
    return [
        PortalAddOnResponse(
            id=a.id,  # type: ignore[arg-type]
            code=str(a.code),
            name=str(a.name),
            description=a.description,  # type: ignore[arg-type]
            amount_cents=a.amount_cents,  # type: ignore[arg-type]
            amount_currency=str(a.amount_currency),
        )
        for a in add_ons
    ]


@router.get(
    "/add_ons/purchased",
    response_model=list[PortalPurchasedAddOnResponse],
    summary="List purchased add-ons",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def list_portal_purchased_add_ons(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[PortalPurchasedAddOnResponse]:
    """List all add-ons the customer has purchased."""
    customer_id, _organization_id = portal_auth
    applied_repo = AppliedAddOnRepository(db)
    add_on_repo = AddOnRepository(db)
    applied = applied_repo.get_by_customer_id(customer_id)
    result: list[PortalPurchasedAddOnResponse] = []
    for app_addon in applied:
        addon = add_on_repo.get_by_id(UUID(str(app_addon.add_on_id)))
        result.append(
            PortalPurchasedAddOnResponse(
                id=app_addon.id,  # type: ignore[arg-type]
                add_on_id=app_addon.add_on_id,  # type: ignore[arg-type]
                add_on_name=str(addon.name) if addon else "Unknown",
                add_on_code=str(addon.code) if addon else "unknown",
                amount_cents=app_addon.amount_cents,  # type: ignore[arg-type]
                amount_currency=str(app_addon.amount_currency),
                created_at=app_addon.created_at,  # type: ignore[arg-type]
            )
        )
    return result


@router.post(
    "/add_ons/{add_on_id}/purchase",
    response_model=PortalPurchaseAddOnResponse,
    status_code=201,
    summary="Purchase an add-on",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Add-on not found"},
    },
)
async def portal_purchase_add_on(
    add_on_id: UUID,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> PortalPurchaseAddOnResponse:
    """Purchase an add-on. Creates an applied add-on record and a one-off invoice."""
    customer_id, organization_id = portal_auth
    add_on_repo = AddOnRepository(db)
    add_on = add_on_repo.get_by_id(add_on_id, organization_id)
    if not add_on:
        raise HTTPException(status_code=404, detail="Add-on not found")

    service = AddOnService(db)
    try:
        applied, invoice = service.apply_add_on(
            add_on_code=str(add_on.code),
            customer_id=customer_id,
            organization_id=organization_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return PortalPurchaseAddOnResponse(
        applied_add_on_id=applied.id,  # type: ignore[arg-type]
        invoice_id=invoice.id,  # type: ignore[arg-type]
        add_on_name=str(add_on.name),
        amount_cents=add_on.amount_cents,  # type: ignore[arg-type]
        amount_currency=str(add_on.amount_currency),
    )


# ── Coupons ──────────────────────────────────────────────────────────────


@router.get(
    "/coupons",
    response_model=list[PortalAppliedCouponResponse],
    summary="List applied coupons",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def list_portal_coupons(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[PortalAppliedCouponResponse]:
    """List all coupons applied to the authenticated customer."""
    customer_id, organization_id = portal_auth
    applied_repo = AppliedCouponRepository(db)
    coupon_repo = CouponRepository(db)
    applied_coupons = applied_repo.get_active_by_customer_id(customer_id)
    result: list[PortalAppliedCouponResponse] = []
    for ac in applied_coupons:
        coupon = coupon_repo.get_by_id(UUID(str(ac.coupon_id)))
        result.append(
            PortalAppliedCouponResponse(
                id=ac.id,  # type: ignore[arg-type]
                coupon_code=str(coupon.code) if coupon else "unknown",
                coupon_name=str(coupon.name) if coupon else "Unknown",
                coupon_type=str(coupon.coupon_type) if coupon else "unknown",
                amount_cents=ac.amount_cents,  # type: ignore[arg-type]
                amount_currency=ac.amount_currency,  # type: ignore[arg-type]
                percentage_rate=ac.percentage_rate,  # type: ignore[arg-type]
                frequency=str(ac.frequency),
                frequency_duration=ac.frequency_duration,  # type: ignore[arg-type]
                frequency_duration_remaining=ac.frequency_duration_remaining,  # type: ignore[arg-type]
                status=str(ac.status),
                created_at=ac.created_at,  # type: ignore[arg-type]
            )
        )
    return result


@router.post(
    "/coupons/redeem",
    response_model=PortalAppliedCouponResponse,
    status_code=201,
    summary="Redeem a coupon code",
    responses={
        400: {"description": "Coupon is not active, expired, or already applied"},
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Coupon not found"},
    },
)
async def portal_redeem_coupon(
    data: PortalRedeemCouponRequest,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> PortalAppliedCouponResponse:
    """Redeem a coupon code for the authenticated customer."""
    customer_id, organization_id = portal_auth
    service = CouponApplicationService(db)
    try:
        applied = service.apply_coupon_to_customer(
            coupon_code=data.coupon_code,
            customer_id=customer_id,
            organization_id=organization_id,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from None
        raise HTTPException(status_code=400, detail=msg) from None

    coupon_repo = CouponRepository(db)
    coupon = coupon_repo.get_by_id(UUID(str(applied.coupon_id)))
    return PortalAppliedCouponResponse(
        id=applied.id,  # type: ignore[arg-type]
        coupon_code=str(coupon.code) if coupon else "unknown",
        coupon_name=str(coupon.name) if coupon else "Unknown",
        coupon_type=str(coupon.coupon_type) if coupon else "unknown",
        amount_cents=applied.amount_cents,  # type: ignore[arg-type]
        amount_currency=applied.amount_currency,  # type: ignore[arg-type]
        percentage_rate=applied.percentage_rate,  # type: ignore[arg-type]
        frequency=str(applied.frequency),
        frequency_duration=applied.frequency_duration,  # type: ignore[arg-type]
        frequency_duration_remaining=applied.frequency_duration_remaining,  # type: ignore[arg-type]
        status=str(applied.status),
        created_at=applied.created_at,  # type: ignore[arg-type]
    )
