# Phase 9: Wallets & Prepaid Credits

> **Priority:** MEDIUM | **Complexity:** High | **Est. Time:** 2 weeks

## Overview

Wallets allow customers to prepay for usage with credits. Credits can be purchased, granted, or auto-topped-up.

## Lago Reference

**Models:**
- `lago-api/app/models/wallet.rb` — Wallet with balance
- `lago-api/app/models/wallet_transaction.rb` — Credit additions/deductions

**Services:** `lago-api/app/services/wallets/`
```
wallets/
├── create_service.rb
├── update_service.rb
├── terminate_service.rb
├── balance/
│   ├── decrease_service.rb
│   ├── increase_service.rb
│   └── refresh_ongoing_service.rb
├── recurring_transaction_rules/
│   └── ...
└── ...
```

**Key Lago Features:**
- Multiple wallets per customer (with priority)
- Credit rate (e.g., 1 credit = $1, or 1 credit = $0.10)
- Expiration dates
- Auto top-up rules (when balance falls below threshold)
- Paid vs granted credits

---

## Implementation Plan

### Step 1: Models

#### Wallet Model
```python
# app/models/wallet.py
class WalletStatus(str, Enum):
    ACTIVE = "active"
    TERMINATED = "terminated"

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False)
    
    # Identification
    name = Column(String(255), nullable=True)
    external_id = Column(String(255), nullable=True)
    
    # Balance
    balance_cents = Column(BigInteger, default=0)  # Current balance in cents
    credits_balance = Column(Numeric(24, 8), default=0)  # Credits balance
    consumed_credits = Column(Numeric(24, 8), default=0)  # Total consumed
    
    # Credit rate
    rate_amount = Column(Numeric(24, 8), nullable=False)  # e.g., 1.0 (1 credit = $1)
    currency = Column(String(3), default="USD")
    
    # Settings
    priority = Column(Integer, default=1)  # Lower = used first
    
    # Expiration
    expiration_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(String(20), default=WalletStatus.ACTIVE.value)
    terminated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    customer = relationship("Customer", back_populates="wallets")
    transactions = relationship("WalletTransaction", back_populates="wallet")

    @property
    def credits_ongoing_balance(self) -> Decimal:
        """Balance minus pending usage."""
        return self.credits_balance - self.credits_ongoing_usage
```

#### WalletTransaction Model
```python
# app/models/wallet_transaction.py
class TransactionType(str, Enum):
    INBOUND = "inbound"   # Credit added
    OUTBOUND = "outbound" # Credit consumed

class TransactionStatus(str, Enum):
    PENDING = "pending"
    SETTLED = "settled"

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    wallet_id = Column(UUIDType, ForeignKey("wallets.id"), nullable=False)
    invoice_id = Column(UUIDType, ForeignKey("invoices.id"), nullable=True)
    
    # Transaction details
    transaction_type = Column(String(20), nullable=False)  # inbound/outbound
    status = Column(String(20), default=TransactionStatus.PENDING.value)
    
    # Amounts
    amount = Column(Numeric(24, 8), nullable=False)  # Credit amount
    credit_amount = Column(Numeric(24, 8), nullable=False)  # Same as amount
    
    # Source
    source = Column(String(50), nullable=True)  # 'manual', 'purchase', 'usage', 'interval'
    
    # For purchases
    invoice_requires_successful_payment = Column(Boolean, default=False)
    
    # Timestamps
    transaction_at = Column(DateTime(timezone=True), server_default=func.now())
    settled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    wallet = relationship("Wallet", back_populates="transactions")
```

#### RecurringTransactionRule Model
```python
# app/models/recurring_transaction_rule.py
class RuleTrigger(str, Enum):
    THRESHOLD = "threshold"  # Balance falls below X
    INTERVAL = "interval"    # Time-based (monthly, etc.)

class RecurringTransactionRule(Base):
    __tablename__ = "recurring_transaction_rules"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    wallet_id = Column(UUIDType, ForeignKey("wallets.id"), nullable=False)
    
    # Trigger type
    trigger = Column(String(20), nullable=False)
    
    # Threshold trigger
    threshold_credits = Column(Numeric(24, 8), nullable=True)  # Trigger when balance < X
    
    # Interval trigger
    interval = Column(String(20), nullable=True)  # weekly, monthly, quarterly, yearly
    
    # Credits to add
    paid_credits = Column(Numeric(24, 8), nullable=True)
    granted_credits = Column(Numeric(24, 8), nullable=True)
    
    # Status
    started_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### Step 2: Wallet Service

```python
# app/services/wallet_service.py
class WalletService:
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        customer_id: UUID,
        name: str | None = None,
        rate_amount: Decimal = Decimal("1.0"),
        currency: str = "USD",
        paid_credits: Decimal | None = None,
        granted_credits: Decimal | None = None,
        expiration_at: datetime | None = None,
    ) -> Wallet:
        """Create a wallet for a customer."""
        wallet = Wallet(
            customer_id=customer_id,
            name=name,
            rate_amount=rate_amount,
            currency=currency,
            expiration_at=expiration_at,
        )
        self.db.add(wallet)
        self.db.flush()
        
        # Add initial credits
        if paid_credits:
            self._add_credits(wallet, paid_credits, source="purchase")
        if granted_credits:
            self._add_credits(wallet, granted_credits, source="manual")
        
        self.db.commit()
        return wallet
    
    def _add_credits(
        self,
        wallet: Wallet,
        amount: Decimal,
        source: str = "manual"
    ) -> WalletTransaction:
        """Add credits to wallet."""
        transaction = WalletTransaction(
            wallet_id=wallet.id,
            transaction_type=TransactionType.INBOUND.value,
            status=TransactionStatus.SETTLED.value,
            amount=amount,
            credit_amount=amount,
            source=source,
            settled_at=datetime.utcnow(),
        )
        self.db.add(transaction)
        
        # Update balance
        wallet.credits_balance += amount
        wallet.balance_cents += int(amount * wallet.rate_amount * 100)
        
        return transaction
    
    def consume_credits(
        self,
        customer_id: UUID,
        amount: Decimal,
        invoice_id: UUID | None = None
    ) -> list[WalletTransaction]:
        """Consume credits from customer's wallets (respecting priority)."""
        wallets = self.db.query(Wallet).filter(
            Wallet.customer_id == customer_id,
            Wallet.status == WalletStatus.ACTIVE.value,
            Wallet.credits_balance > 0,
        ).order_by(Wallet.priority, Wallet.created_at).all()
        
        transactions = []
        remaining = amount
        
        for wallet in wallets:
            if remaining <= 0:
                break
            
            # Check expiration
            if wallet.expiration_at and wallet.expiration_at < datetime.utcnow():
                continue
            
            consume_amount = min(remaining, wallet.credits_balance)
            
            transaction = WalletTransaction(
                wallet_id=wallet.id,
                invoice_id=invoice_id,
                transaction_type=TransactionType.OUTBOUND.value,
                status=TransactionStatus.SETTLED.value,
                amount=consume_amount,
                credit_amount=consume_amount,
                source="usage",
                settled_at=datetime.utcnow(),
            )
            self.db.add(transaction)
            
            wallet.credits_balance -= consume_amount
            wallet.consumed_credits += consume_amount
            wallet.balance_cents = int(wallet.credits_balance * wallet.rate_amount * 100)
            
            transactions.append(transaction)
            remaining -= consume_amount
            
            # Check auto top-up rules
            self._check_threshold_rules(wallet)
        
        self.db.commit()
        return transactions
    
    def _check_threshold_rules(self, wallet: Wallet):
        """Check if threshold rules should trigger."""
        rules = self.db.query(RecurringTransactionRule).filter(
            RecurringTransactionRule.wallet_id == wallet.id,
            RecurringTransactionRule.trigger == RuleTrigger.THRESHOLD.value,
        ).all()
        
        for rule in rules:
            if wallet.credits_balance < rule.threshold_credits:
                # Trigger auto top-up
                if rule.paid_credits:
                    # Create invoice for purchase
                    pass  # TODO: Implement paid top-up invoice
                if rule.granted_credits:
                    self._add_credits(wallet, rule.granted_credits, source="interval")
    
    def terminate(self, wallet_id: UUID):
        """Terminate a wallet."""
        wallet = self.db.query(Wallet).get(wallet_id)
        if wallet:
            wallet.status = WalletStatus.TERMINATED.value
            wallet.terminated_at = datetime.utcnow()
            self.db.commit()
        return wallet
```

### Step 3: Invoice Integration

Update invoice generation to use wallet credits:

```python
# app/services/invoice_generation.py (modification)
def generate_invoice(...):
    invoice = create_invoice(...)
    
    # After calculating total
    if invoice.total_amount_cents > 0:
        # Apply wallet credits
        credit_amount = Decimal(invoice.total_amount_cents) / 100
        
        wallet_service = WalletService(db)
        transactions = wallet_service.consume_credits(
            customer_id=invoice.customer_id,
            amount=credit_amount,
            invoice_id=invoice.id
        )
        
        # Reduce invoice amount by credits used
        credits_used = sum(t.amount for t in transactions)
        invoice.prepaid_credit_amount_cents = int(credits_used * 100)
        invoice.total_amount_cents -= invoice.prepaid_credit_amount_cents
```

### Step 4: API Endpoints

```python
# app/routers/wallets.py
router = APIRouter()

@router.post("/", response_model=WalletResponse)
async def create_wallet(data: WalletCreate, db: Session = Depends(get_db)):
    """Create a wallet for a customer."""
    service = WalletService(db)
    wallet = service.create(
        customer_id=data.customer_id,
        name=data.name,
        rate_amount=data.rate_amount,
        currency=data.currency,
        paid_credits=data.paid_credits,
        granted_credits=data.granted_credits,
        expiration_at=data.expiration_at,
    )
    return wallet

@router.get("/{wallet_id}", response_model=WalletResponse)
async def get_wallet(wallet_id: UUID, db: Session = Depends(get_db)):
    """Get a wallet."""
    ...

@router.put("/{wallet_id}", response_model=WalletResponse)
async def update_wallet(wallet_id: UUID, data: WalletUpdate, db: Session = Depends(get_db)):
    """Update wallet settings."""
    ...

@router.delete("/{wallet_id}", status_code=204)
async def terminate_wallet(wallet_id: UUID, db: Session = Depends(get_db)):
    """Terminate a wallet."""
    ...

# Wallet transactions
@router.post("/{wallet_id}/transactions", response_model=WalletTransactionResponse)
async def create_transaction(wallet_id: UUID, data: WalletTransactionCreate, db: Session = Depends(get_db)):
    """Add or consume credits."""
    ...

@router.get("/{wallet_id}/transactions", response_model=list[WalletTransactionResponse])
async def list_transactions(wallet_id: UUID, db: Session = Depends(get_db)):
    """List wallet transactions."""
    ...

# Recurring rules
@router.post("/{wallet_id}/recurring_transaction_rules", response_model=RecurringRuleResponse)
async def create_recurring_rule(wallet_id: UUID, data: RecurringRuleCreate, db: Session = Depends(get_db)):
    """Create auto top-up rule."""
    ...
```

---

## Database Migrations

```sql
CREATE TABLE wallets (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(id),
    name VARCHAR(255),
    external_id VARCHAR(255),
    balance_cents BIGINT DEFAULT 0,
    credits_balance NUMERIC(24, 8) DEFAULT 0,
    consumed_credits NUMERIC(24, 8) DEFAULT 0,
    rate_amount NUMERIC(24, 8) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    priority INTEGER DEFAULT 1,
    expiration_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'active',
    terminated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE wallet_transactions (
    id UUID PRIMARY KEY,
    wallet_id UUID NOT NULL REFERENCES wallets(id),
    invoice_id UUID REFERENCES invoices(id),
    transaction_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    amount NUMERIC(24, 8) NOT NULL,
    credit_amount NUMERIC(24, 8) NOT NULL,
    source VARCHAR(50),
    invoice_requires_successful_payment BOOLEAN DEFAULT FALSE,
    transaction_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    settled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE recurring_transaction_rules (
    id UUID PRIMARY KEY,
    wallet_id UUID NOT NULL REFERENCES wallets(id),
    trigger VARCHAR(20) NOT NULL,
    threshold_credits NUMERIC(24, 8),
    interval VARCHAR(20),
    paid_credits NUMERIC(24, 8),
    granted_credits NUMERIC(24, 8),
    started_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_wallets_customer ON wallets(customer_id);
CREATE INDEX idx_wallets_status ON wallets(status) WHERE status = 'active';
CREATE INDEX idx_wallet_transactions_wallet ON wallet_transactions(wallet_id);
```

---

## Test Plan

```python
class TestWalletService:
    def test_create_wallet_with_granted_credits(self):
        """Create wallet with initial free credits."""
    
    def test_create_wallet_with_paid_credits(self):
        """Create wallet with purchased credits."""
    
    def test_consume_credits_single_wallet(self):
        """Consume from single wallet."""
    
    def test_consume_credits_multiple_wallets_priority(self):
        """Consume respects wallet priority order."""
    
    def test_consume_partial(self):
        """Consume part of balance."""
    
    def test_expired_wallet_skipped(self):
        """Expired wallets not used."""
    
    def test_threshold_rule_triggers_topup(self):
        """Auto top-up when balance < threshold."""

class TestInvoiceWithWallet:
    def test_invoice_uses_wallet_credits(self):
        """Invoice total reduced by wallet credits."""
    
    def test_invoice_partial_wallet(self):
        """Invoice uses partial wallet + payment."""
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `app/models/wallet.py` | Create |
| `app/models/wallet_transaction.py` | Create |
| `app/models/recurring_transaction_rule.py` | Create |
| `app/services/wallet_service.py` | Create |
| `app/routers/wallets.py` | Create |
| `app/schemas/wallet.py` | Create |
| `app/services/invoice_generation.py` | Modify |
| `tests/test_wallets.py` | Create |

---

## Acceptance Criteria

- [ ] Wallet CRUD API
- [ ] Multiple wallets per customer with priority
- [ ] Credit top-up (manual & purchased)
- [ ] Credit consumption on invoice
- [ ] Wallet expiration
- [ ] Auto top-up rules (threshold-based)
- [ ] Wallet transaction history
- [ ] 100% test coverage
