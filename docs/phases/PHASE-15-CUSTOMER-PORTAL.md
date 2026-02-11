# Phase 15: Customer Portal

> **Priority:** LOW | **Complexity:** High | **Est. Time:** 2 weeks

## Overview

Self-service portal for customers to view invoices, usage, and manage subscriptions.

## Lago Reference

**Source:** `lago-api/app/services/customer_portal/`

---

## Implementation Plan

### Authentication

```python
# Customer portal uses JWT tokens with limited scope
# Tokens are generated via customer-specific URLs

# app/services/customer_portal_service.py
class CustomerPortalService:
    def generate_portal_url(self, customer_id: UUID) -> str:
        """Generate a secure portal URL for a customer."""
        token = jwt.encode(
            {
                "customer_id": str(customer_id),
                "exp": datetime.utcnow() + timedelta(hours=24),
                "scope": "customer_portal"
            },
            settings.SECRET_KEY,
            algorithm="HS256"
        )
        return f"{settings.PORTAL_URL}?token={token}"
```

### Portal Endpoints

```python
# app/routers/customer_portal.py
# These endpoints require customer portal JWT

@router.get("/me", response_model=PortalCustomerResponse)
async def get_portal_customer(customer: Customer = Depends(get_portal_customer)):
    """Get current customer info."""

@router.get("/subscriptions", response_model=list[PortalSubscriptionResponse])
async def get_portal_subscriptions(customer: Customer = Depends(get_portal_customer)):
    """List customer's subscriptions."""

@router.get("/invoices", response_model=list[PortalInvoiceResponse])
async def get_portal_invoices(customer: Customer = Depends(get_portal_customer)):
    """List customer's invoices."""

@router.get("/invoices/{invoice_id}/download")
async def download_portal_invoice(invoice_id: UUID, customer: Customer = Depends(get_portal_customer)):
    """Download invoice PDF."""

@router.get("/usage", response_model=PortalUsageResponse)
async def get_portal_usage(customer: Customer = Depends(get_portal_customer)):
    """Get current period usage."""

@router.get("/wallets", response_model=list[PortalWalletResponse])
async def get_portal_wallets(customer: Customer = Depends(get_portal_customer)):
    """List customer's wallets."""
```

### Restricted Data

Portal responses should exclude sensitive data:
- No internal IDs exposed
- No financial details beyond their own
- No webhook configurations
- No payment method details (only last 4 digits)

---

## Frontend (Optional)

A basic React portal can be added to `frontend/portal/`:
- Login via token URL
- Dashboard with current usage
- Invoice list with download
- Subscription details
- Wallet balance

---

## Files to Create

| File | Action |
|------|--------|
| `app/services/customer_portal_service.py` | Create |
| `app/routers/customer_portal.py` | Create |
| `app/schemas/portal.py` | Create |
| `app/core/portal_auth.py` | Create |
| `tests/test_customer_portal.py` | Create |

---

## Acceptance Criteria

- [ ] Secure token-based portal URLs
- [ ] Customer can view their subscriptions
- [ ] Customer can view/download invoices
- [ ] Customer can view current usage
- [ ] Customer can view wallet balance
- [ ] Proper data scoping (no cross-customer access)
- [ ] 100% test coverage
