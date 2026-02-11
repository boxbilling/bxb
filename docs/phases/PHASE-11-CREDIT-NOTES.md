# Phase 11: Credit Notes

> **Priority:** MEDIUM | **Complexity:** Medium | **Est. Time:** 1 week

## Overview

Credit notes handle refunds, credits, and invoice voids. Essential for billing corrections.

## Lago Reference

**Source:** `lago-api/app/models/credit_note.rb`

```ruby
REASONS = %i[duplicated_charge product_unsatisfactory order_change order_cancellation fraudulent_charge other].freeze
CREDIT_STATUS = %i[available consumed voided].freeze
REFUND_STATUS = %i[pending succeeded failed].freeze
```

---

## Implementation Plan

### Step 1: Models

```python
# app/models/credit_note.py
class CreditNoteReason(str, Enum):
    DUPLICATED_CHARGE = "duplicated_charge"
    PRODUCT_UNSATISFACTORY = "product_unsatisfactory"
    ORDER_CHANGE = "order_change"
    ORDER_CANCELLATION = "order_cancellation"
    FRAUDULENT_CHARGE = "fraudulent_charge"
    OTHER = "other"

class CreditStatus(str, Enum):
    AVAILABLE = "available"   # Can be applied to future invoices
    CONSUMED = "consumed"     # Fully used
    VOIDED = "voided"

class RefundStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class CreditNote(Base):
    __tablename__ = "credit_notes"

    id = Column(UUIDType, primary_key=True)
    sequential_id = Column(Integer, nullable=False)  # CN-001, CN-002...
    number = Column(String(50), unique=True)
    
    invoice_id = Column(UUIDType, ForeignKey("invoices.id"))
    customer_id = Column(UUIDType, ForeignKey("customers.id"))
    
    # Reason
    reason = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    
    # Amounts
    total_amount_cents = Column(BigInteger, nullable=False)
    taxes_amount_cents = Column(BigInteger, default=0)
    sub_total_excluding_taxes_cents = Column(BigInteger, default=0)
    
    # Credit portion (balance for future invoices)
    credit_amount_cents = Column(BigInteger, default=0)
    balance_amount_cents = Column(BigInteger, default=0)  # Remaining credit
    credit_status = Column(String(20), default="available")
    
    # Refund portion (money back to customer)
    refund_amount_cents = Column(BigInteger, default=0)
    refund_status = Column(String(20), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(String(20), default="draft")  # draft, finalized, voided
    
    currency = Column(String(3), nullable=False)
    issuing_date = Column(Date, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# app/models/credit_note_item.py
class CreditNoteItem(Base):
    """Line items in a credit note."""
    __tablename__ = "credit_note_items"

    id = Column(UUIDType, primary_key=True)
    credit_note_id = Column(UUIDType, ForeignKey("credit_notes.id"))
    fee_id = Column(UUIDType, ForeignKey("fees.id"), nullable=True)
    
    amount_cents = Column(BigInteger, nullable=False)
    amount_currency = Column(String(3))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### Step 2: Credit Note Service

```python
# app/services/credit_note_service.py
class CreditNoteService:
    def create(
        self,
        invoice_id: UUID,
        reason: CreditNoteReason,
        items: list[dict],
        credit_amount_cents: int = 0,
        refund_amount_cents: int = 0,
        description: str | None = None,
    ) -> CreditNote:
        """Create a credit note for an invoice."""
        invoice = self.db.query(Invoice).get(invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        if invoice.status not in ["finalized"]:
            raise ValueError("Can only credit finalized invoices")
        
        # Generate number
        count = self.db.query(CreditNote).filter(
            CreditNote.customer_id == invoice.customer_id
        ).count()
        number = f"CN-{count + 1:05d}"
        
        total = sum(item["amount_cents"] for item in items)
        
        credit_note = CreditNote(
            number=number,
            sequential_id=count + 1,
            invoice_id=invoice_id,
            customer_id=invoice.customer_id,
            reason=reason.value,
            description=description,
            total_amount_cents=total,
            credit_amount_cents=credit_amount_cents,
            balance_amount_cents=credit_amount_cents,
            refund_amount_cents=refund_amount_cents,
            currency=invoice.currency,
            issuing_date=date.today(),
        )
        self.db.add(credit_note)
        self.db.flush()
        
        # Create items
        for item in items:
            cn_item = CreditNoteItem(
                credit_note_id=credit_note.id,
                fee_id=item.get("fee_id"),
                amount_cents=item["amount_cents"],
                amount_currency=invoice.currency,
            )
            self.db.add(cn_item)
        
        self.db.commit()
        return credit_note
    
    def finalize(self, credit_note_id: UUID) -> CreditNote:
        """Finalize a credit note."""
        cn = self.db.query(CreditNote).get(credit_note_id)
        cn.status = "finalized"
        
        # Process refund if needed
        if cn.refund_amount_cents > 0:
            cn.refund_status = RefundStatus.PENDING.value
            # TODO: Trigger refund via payment provider
        
        self.db.commit()
        return cn
    
    def apply_credit(
        self,
        customer_id: UUID,
        invoice_id: UUID,
        amount_cents: int
    ) -> int:
        """Apply available credits to an invoice. Returns amount applied."""
        credit_notes = self.db.query(CreditNote).filter(
            CreditNote.customer_id == customer_id,
            CreditNote.credit_status == CreditStatus.AVAILABLE.value,
            CreditNote.balance_amount_cents > 0,
        ).order_by(CreditNote.created_at).all()
        
        applied = 0
        remaining = amount_cents
        
        for cn in credit_notes:
            if remaining <= 0:
                break
            
            use = min(cn.balance_amount_cents, remaining)
            cn.balance_amount_cents -= use
            
            if cn.balance_amount_cents <= 0:
                cn.credit_status = CreditStatus.CONSUMED.value
            
            applied += use
            remaining -= use
        
        self.db.commit()
        return applied
    
    def void(self, credit_note_id: UUID) -> CreditNote:
        """Void a credit note."""
        cn = self.db.query(CreditNote).get(credit_note_id)
        if cn.status == "voided":
            raise ValueError("Already voided")
        
        cn.status = "voided"
        cn.credit_status = CreditStatus.VOIDED.value
        cn.balance_amount_cents = 0
        
        self.db.commit()
        return cn
```

### Step 3: API Endpoints

```python
# app/routers/credit_notes.py
@router.post("/", response_model=CreditNoteResponse)
async def create_credit_note(data: CreditNoteCreate):
    """Create a credit note."""

@router.get("/", response_model=list[CreditNoteResponse])
async def list_credit_notes(customer_id: UUID = None, invoice_id: UUID = None):
    """List credit notes."""

@router.get("/{id}", response_model=CreditNoteResponse)
async def get_credit_note(id: UUID):
    """Get a credit note."""

@router.post("/{id}/finalize", response_model=CreditNoteResponse)
async def finalize_credit_note(id: UUID):
    """Finalize a credit note."""

@router.post("/{id}/void", response_model=CreditNoteResponse)
async def void_credit_note(id: UUID):
    """Void a credit note."""

@router.get("/{id}/download")
async def download_credit_note(id: UUID):
    """Download credit note PDF."""
```

### Step 4: Invoice Integration

```python
# In invoice generation, apply available credits
def generate_invoice(...):
    ...
    # After calculating total
    cn_service = CreditNoteService(db)
    credits_applied = cn_service.apply_credit(
        customer_id=customer.id,
        invoice_id=invoice.id,
        amount_cents=invoice.total_amount_cents
    )
    invoice.credit_notes_amount_cents = credits_applied
    invoice.total_amount_cents -= credits_applied
```

---

## Database Migrations

```sql
CREATE TABLE credit_notes (
    id UUID PRIMARY KEY,
    sequential_id INTEGER NOT NULL,
    number VARCHAR(50) UNIQUE,
    invoice_id UUID REFERENCES invoices(id),
    customer_id UUID REFERENCES customers(id),
    reason VARCHAR(50) NOT NULL,
    description TEXT,
    total_amount_cents BIGINT NOT NULL,
    taxes_amount_cents BIGINT DEFAULT 0,
    sub_total_excluding_taxes_cents BIGINT DEFAULT 0,
    credit_amount_cents BIGINT DEFAULT 0,
    balance_amount_cents BIGINT DEFAULT 0,
    credit_status VARCHAR(20) DEFAULT 'available',
    refund_amount_cents BIGINT DEFAULT 0,
    refund_status VARCHAR(20),
    refunded_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'draft',
    currency VARCHAR(3) NOT NULL,
    issuing_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE credit_note_items (
    id UUID PRIMARY KEY,
    credit_note_id UUID REFERENCES credit_notes(id),
    fee_id UUID REFERENCES fees(id),
    amount_cents BIGINT NOT NULL,
    amount_currency VARCHAR(3),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `app/models/credit_note.py` | Create |
| `app/models/credit_note_item.py` | Create |
| `app/services/credit_note_service.py` | Create |
| `app/routers/credit_notes.py` | Create |
| `app/schemas/credit_note.py` | Create |
| `app/services/invoice_generation.py` | Modify |
| `tests/test_credit_notes.py` | Create |

---

## Acceptance Criteria

- [ ] Credit note CRUD API
- [ ] Multiple reasons (order change, cancellation, etc.)
- [ ] Credit vs refund split
- [ ] Apply credits to future invoices
- [ ] Void credit notes
- [ ] Sequential numbering
- [ ] 100% test coverage
