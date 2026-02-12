"""Tests for WalletTransaction model, schema, repository, and CRUD operations."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.wallet_transaction import (
    TransactionSource,
    TransactionStatus,
    TransactionTransactionStatus,
    TransactionType,
    WalletTransaction,
)
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.wallet_repository import WalletRepository
from app.repositories.wallet_transaction_repository import WalletTransactionRepository
from app.schemas.customer import CustomerCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
from app.schemas.wallet import WalletCreate
from app.schemas.wallet_transaction import TransactionSource as SchemaTransactionSource
from app.schemas.wallet_transaction import TransactionStatus as SchemaTransactionStatus
from app.schemas.wallet_transaction import (
    TransactionTransactionStatus as SchemaTransactionTransactionStatus,
)
from app.schemas.wallet_transaction import TransactionType as SchemaTransactionType
from app.schemas.wallet_transaction import (
    WalletTransactionCreate,
    WalletTransactionResponse,
)
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Create a database session for direct repository testing."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def customer(db_session):
    """Create a test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"wt_test_cust_{uuid4()}",
            name="WalletTxn Test Customer",
            email="wallettxn@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def customer2(db_session):
    """Create a second test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"wt_test_cust2_{uuid4()}",
            name="WalletTxn Test Customer 2",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def wallet(db_session, customer):
    """Create a test wallet."""
    repo = WalletRepository(db_session)
    return repo.create(
        WalletCreate(
            customer_id=customer.id,
            name="Test Wallet",
            code="test-wallet-txn",
            rate_amount=Decimal("1.0000"),
            currency="USD",
            priority=1,
        )
    )


@pytest.fixture
def wallet2(db_session, customer):
    """Create a second test wallet for the same customer."""
    repo = WalletRepository(db_session)
    return repo.create(
        WalletCreate(
            customer_id=customer.id,
            name="Test Wallet 2",
            code="test-wallet-txn-2",
            rate_amount=Decimal("2.0000"),
            currency="USD",
            priority=2,
        )
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(code=f"wt_test_plan_{uuid4()}", name="WT Test Plan", interval="monthly"),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def subscription(db_session, customer, plan):
    """Create a test subscription."""
    repo = SubscriptionRepository(db_session)
    return repo.create(
        SubscriptionCreate(
            external_id=f"wt_test_sub_{uuid4()}",
            customer_id=customer.id,
            plan_id=plan.id,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def invoice(db_session, customer, subscription):
    """Create a test invoice."""
    repo = InvoiceRepository(db_session)
    now = datetime.now(UTC)
    return repo.create(
        InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=now,
            billing_period_end=now + timedelta(days=30),
            line_items=[
                InvoiceLineItem(
                    description="Test charge",
                    unit_price=Decimal("10000.0000"),
                    amount=Decimal("10000.0000"),
                    quantity=Decimal("1"),
                )
            ],
        )
    )


class TestWalletTransactionModel:
    """Tests for WalletTransaction SQLAlchemy model."""

    def test_transaction_defaults(self, db_session, wallet, customer):
        """Test WalletTransaction model default values."""
        txn = WalletTransaction(
            wallet_id=wallet.id,
            customer_id=customer.id,
            transaction_type=TransactionType.INBOUND.value,
        )
        db_session.add(txn)
        db_session.commit()
        db_session.refresh(txn)

        assert txn.id is not None
        assert txn.wallet_id == wallet.id
        assert txn.customer_id == customer.id
        assert txn.transaction_type == "inbound"
        assert txn.transaction_status == TransactionTransactionStatus.GRANTED.value
        assert txn.source == TransactionSource.MANUAL.value
        assert txn.status == TransactionStatus.PENDING.value
        assert txn.amount == 0
        assert txn.credit_amount == 0
        assert txn.invoice_id is None
        assert txn.created_at is not None
        assert txn.updated_at is not None

    def test_transaction_with_all_fields(self, db_session, wallet, customer, invoice):
        """Test WalletTransaction model with all fields populated."""
        txn = WalletTransaction(
            wallet_id=wallet.id,
            customer_id=customer.id,
            transaction_type=TransactionType.OUTBOUND.value,
            transaction_status=TransactionTransactionStatus.INVOICED.value,
            source=TransactionSource.THRESHOLD.value,
            status=TransactionStatus.SETTLED.value,
            amount=Decimal("50.0000"),
            credit_amount=Decimal("5000.0000"),
            invoice_id=invoice.id,
        )
        db_session.add(txn)
        db_session.commit()
        db_session.refresh(txn)

        assert txn.transaction_type == "outbound"
        assert txn.transaction_status == "invoiced"
        assert txn.source == "threshold"
        assert txn.status == "settled"
        assert txn.amount == Decimal("50.0000")
        assert txn.credit_amount == Decimal("5000.0000")
        assert txn.invoice_id == invoice.id

    def test_transaction_type_enum(self):
        """Test TransactionType enum values."""
        assert TransactionType.INBOUND.value == "inbound"
        assert TransactionType.OUTBOUND.value == "outbound"

    def test_transaction_status_enum(self):
        """Test TransactionStatus enum values."""
        assert TransactionStatus.PENDING.value == "pending"
        assert TransactionStatus.SETTLED.value == "settled"
        assert TransactionStatus.FAILED.value == "failed"

    def test_transaction_transaction_status_enum(self):
        """Test TransactionTransactionStatus enum values."""
        assert TransactionTransactionStatus.PURCHASED.value == "purchased"
        assert TransactionTransactionStatus.GRANTED.value == "granted"
        assert TransactionTransactionStatus.VOIDED.value == "voided"
        assert TransactionTransactionStatus.INVOICED.value == "invoiced"

    def test_transaction_source_enum(self):
        """Test TransactionSource enum values."""
        assert TransactionSource.MANUAL.value == "manual"
        assert TransactionSource.INTERVAL.value == "interval"
        assert TransactionSource.THRESHOLD.value == "threshold"


class TestWalletTransactionRepository:
    """Tests for WalletTransactionRepository CRUD and query methods."""

    def test_create_inbound_transaction(self, db_session, wallet, customer):
        """Test creating an inbound wallet transaction."""
        repo = WalletTransactionRepository(db_session)
        txn = repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                transaction_status=SchemaTransactionTransactionStatus.GRANTED,
                source=SchemaTransactionSource.MANUAL,
                status=SchemaTransactionStatus.SETTLED,
                amount=Decimal("100.0000"),
                credit_amount=Decimal("10000.0000"),
            )
        )
        assert txn.id is not None
        assert txn.wallet_id == wallet.id
        assert txn.customer_id == customer.id
        assert txn.transaction_type == "inbound"
        assert txn.transaction_status == "granted"
        assert txn.source == "manual"
        assert txn.status == "settled"
        assert txn.amount == Decimal("100.0000")
        assert txn.credit_amount == Decimal("10000.0000")
        assert txn.invoice_id is None

    def test_create_outbound_transaction_with_invoice(self, db_session, wallet, customer, invoice):
        """Test creating an outbound wallet transaction linked to an invoice."""
        repo = WalletTransactionRepository(db_session)
        txn = repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.OUTBOUND,
                transaction_status=SchemaTransactionTransactionStatus.INVOICED,
                source=SchemaTransactionSource.MANUAL,
                status=SchemaTransactionStatus.SETTLED,
                amount=Decimal("25.0000"),
                credit_amount=Decimal("2500.0000"),
                invoice_id=invoice.id,
            )
        )
        assert txn.transaction_type == "outbound"
        assert txn.transaction_status == "invoiced"
        assert txn.invoice_id == invoice.id

    def test_create_transaction_with_defaults(self, db_session, wallet, customer):
        """Test creating a transaction with minimal fields (defaults applied)."""
        repo = WalletTransactionRepository(db_session)
        txn = repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
            )
        )
        assert txn.transaction_status == "granted"
        assert txn.source == "manual"
        assert txn.status == "pending"
        assert txn.amount == Decimal("0")
        assert txn.credit_amount == Decimal("0")
        assert txn.invoice_id is None

    def test_get_by_id(self, db_session, wallet, customer):
        """Test getting a transaction by ID."""
        repo = WalletTransactionRepository(db_session)
        txn = repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("50.0000"),
                credit_amount=Decimal("5000.0000"),
            )
        )
        fetched = repo.get_by_id(txn.id)
        assert fetched is not None
        assert fetched.id == txn.id
        assert fetched.amount == Decimal("50.0000")

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent transaction."""
        repo = WalletTransactionRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_wallet_id(self, db_session, wallet, customer):
        """Test getting all transactions for a wallet."""
        repo = WalletTransactionRepository(db_session)
        txn1 = repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("100.0000"),
                credit_amount=Decimal("10000.0000"),
            )
        )
        txn2 = repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.OUTBOUND,
                amount=Decimal("30.0000"),
                credit_amount=Decimal("3000.0000"),
            )
        )

        txns = repo.get_by_wallet_id(wallet.id)
        assert len(txns) == 2
        # Ordered by created_at desc, so most recent first
        txn_ids = [t.id for t in txns]
        assert txn1.id in txn_ids
        assert txn2.id in txn_ids

    def test_get_by_wallet_id_empty(self, db_session, wallet):
        """Test getting transactions for a wallet with no transactions."""
        repo = WalletTransactionRepository(db_session)
        txns = repo.get_by_wallet_id(wallet.id)
        assert len(txns) == 0

    def test_get_by_wallet_id_pagination(self, db_session, wallet, customer):
        """Test pagination for get_by_wallet_id."""
        repo = WalletTransactionRepository(db_session)
        for i in range(5):
            repo.create(
                WalletTransactionCreate(
                    wallet_id=wallet.id,
                    customer_id=customer.id,
                    transaction_type=SchemaTransactionType.INBOUND,
                    amount=Decimal(str(i * 10)),
                    credit_amount=Decimal(str(i * 1000)),
                )
            )

        txns = repo.get_by_wallet_id(wallet.id, skip=2, limit=2)
        assert len(txns) == 2

    def test_get_by_customer_id(self, db_session, wallet, wallet2, customer):
        """Test getting all transactions for a customer across wallets."""
        repo = WalletTransactionRepository(db_session)
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("100.0000"),
                credit_amount=Decimal("10000.0000"),
            )
        )
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet2.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("200.0000"),
                credit_amount=Decimal("20000.0000"),
            )
        )

        txns = repo.get_by_customer_id(customer.id)
        assert len(txns) == 2

    def test_get_by_customer_id_isolation(self, db_session, wallet, customer, customer2):
        """Test that customer transactions are isolated."""
        repo = WalletTransactionRepository(db_session)
        wallet_repo = WalletRepository(db_session)

        # Create a wallet for customer2
        wallet_c2 = wallet_repo.create(
            WalletCreate(
                customer_id=customer2.id,
                name="Customer 2 Wallet",
                code="c2-wallet",
            )
        )

        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("100.0000"),
                credit_amount=Decimal("10000.0000"),
            )
        )
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet_c2.id,
                customer_id=customer2.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("200.0000"),
                credit_amount=Decimal("20000.0000"),
            )
        )

        c1_txns = repo.get_by_customer_id(customer.id)
        assert len(c1_txns) == 1
        assert c1_txns[0].amount == Decimal("100.0000")

        c2_txns = repo.get_by_customer_id(customer2.id)
        assert len(c2_txns) == 1
        assert c2_txns[0].amount == Decimal("200.0000")

    def test_get_by_customer_id_pagination(self, db_session, wallet, customer):
        """Test pagination for get_by_customer_id."""
        repo = WalletTransactionRepository(db_session)
        for i in range(5):
            repo.create(
                WalletTransactionCreate(
                    wallet_id=wallet.id,
                    customer_id=customer.id,
                    transaction_type=SchemaTransactionType.INBOUND,
                    amount=Decimal(str(i * 10)),
                    credit_amount=Decimal(str(i * 1000)),
                )
            )

        txns = repo.get_by_customer_id(customer.id, skip=1, limit=2)
        assert len(txns) == 2

    def test_get_inbound_by_wallet_id(self, db_session, wallet, customer):
        """Test filtering only inbound transactions for a wallet."""
        repo = WalletTransactionRepository(db_session)
        # Create mixed transactions
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("100.0000"),
                credit_amount=Decimal("10000.0000"),
            )
        )
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.OUTBOUND,
                amount=Decimal("30.0000"),
                credit_amount=Decimal("3000.0000"),
            )
        )
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("50.0000"),
                credit_amount=Decimal("5000.0000"),
            )
        )

        inbound = repo.get_inbound_by_wallet_id(wallet.id)
        assert len(inbound) == 2
        for txn in inbound:
            assert txn.transaction_type == "inbound"

    def test_get_inbound_by_wallet_id_pagination(self, db_session, wallet, customer):
        """Test pagination for get_inbound_by_wallet_id."""
        repo = WalletTransactionRepository(db_session)
        for _ in range(5):
            repo.create(
                WalletTransactionCreate(
                    wallet_id=wallet.id,
                    customer_id=customer.id,
                    transaction_type=SchemaTransactionType.INBOUND,
                    amount=Decimal("10.0000"),
                    credit_amount=Decimal("1000.0000"),
                )
            )

        inbound = repo.get_inbound_by_wallet_id(wallet.id, skip=1, limit=2)
        assert len(inbound) == 2

    def test_get_outbound_by_wallet_id(self, db_session, wallet, customer):
        """Test filtering only outbound transactions for a wallet."""
        repo = WalletTransactionRepository(db_session)
        # Create mixed transactions
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("100.0000"),
                credit_amount=Decimal("10000.0000"),
            )
        )
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.OUTBOUND,
                amount=Decimal("30.0000"),
                credit_amount=Decimal("3000.0000"),
            )
        )
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.OUTBOUND,
                amount=Decimal("20.0000"),
                credit_amount=Decimal("2000.0000"),
            )
        )

        outbound = repo.get_outbound_by_wallet_id(wallet.id)
        assert len(outbound) == 2
        for txn in outbound:
            assert txn.transaction_type == "outbound"

    def test_get_outbound_by_wallet_id_pagination(self, db_session, wallet, customer):
        """Test pagination for get_outbound_by_wallet_id."""
        repo = WalletTransactionRepository(db_session)
        for _ in range(5):
            repo.create(
                WalletTransactionCreate(
                    wallet_id=wallet.id,
                    customer_id=customer.id,
                    transaction_type=SchemaTransactionType.OUTBOUND,
                    amount=Decimal("10.0000"),
                    credit_amount=Decimal("1000.0000"),
                )
            )

        outbound = repo.get_outbound_by_wallet_id(wallet.id, skip=1, limit=2)
        assert len(outbound) == 2

    def test_get_outbound_by_wallet_id_empty(self, db_session, wallet, customer):
        """Test outbound filtering when only inbound transactions exist."""
        repo = WalletTransactionRepository(db_session)
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("100.0000"),
                credit_amount=Decimal("10000.0000"),
            )
        )

        outbound = repo.get_outbound_by_wallet_id(wallet.id)
        assert len(outbound) == 0

    def test_get_inbound_by_wallet_id_empty(self, db_session, wallet, customer):
        """Test inbound filtering when only outbound transactions exist."""
        repo = WalletTransactionRepository(db_session)
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.OUTBOUND,
                amount=Decimal("30.0000"),
                credit_amount=Decimal("3000.0000"),
            )
        )

        inbound = repo.get_inbound_by_wallet_id(wallet.id)
        assert len(inbound) == 0

    def test_transactions_across_different_wallets(self, db_session, wallet, wallet2, customer):
        """Test that transactions are correctly isolated by wallet."""
        repo = WalletTransactionRepository(db_session)
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("100.0000"),
                credit_amount=Decimal("10000.0000"),
            )
        )
        repo.create(
            WalletTransactionCreate(
                wallet_id=wallet2.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("200.0000"),
                credit_amount=Decimal("20000.0000"),
            )
        )

        w1_txns = repo.get_by_wallet_id(wallet.id)
        assert len(w1_txns) == 1
        assert w1_txns[0].amount == Decimal("100.0000")

        w2_txns = repo.get_by_wallet_id(wallet2.id)
        assert len(w2_txns) == 1
        assert w2_txns[0].amount == Decimal("200.0000")

    def test_various_transaction_statuses(self, db_session, wallet, customer):
        """Test creating transactions with all status values."""
        repo = WalletTransactionRepository(db_session)

        for ts in SchemaTransactionTransactionStatus:
            txn = repo.create(
                WalletTransactionCreate(
                    wallet_id=wallet.id,
                    customer_id=customer.id,
                    transaction_type=SchemaTransactionType.INBOUND,
                    transaction_status=ts,
                    amount=Decimal("10.0000"),
                    credit_amount=Decimal("1000.0000"),
                )
            )
            assert txn.transaction_status == ts.value

    def test_various_sources(self, db_session, wallet, customer):
        """Test creating transactions with all source values."""
        repo = WalletTransactionRepository(db_session)

        for source in SchemaTransactionSource:
            txn = repo.create(
                WalletTransactionCreate(
                    wallet_id=wallet.id,
                    customer_id=customer.id,
                    transaction_type=SchemaTransactionType.INBOUND,
                    source=source,
                    amount=Decimal("10.0000"),
                    credit_amount=Decimal("1000.0000"),
                )
            )
            assert txn.source == source.value

    def test_large_amount_precision(self, db_session, wallet, customer):
        """Test that large amounts maintain decimal precision."""
        repo = WalletTransactionRepository(db_session)
        txn = repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("99999999.9999"),
                credit_amount=Decimal("99999999.9999"),
            )
        )
        assert txn.amount == Decimal("99999999.9999")
        assert txn.credit_amount == Decimal("99999999.9999")

    def test_zero_amounts(self, db_session, wallet, customer):
        """Test transaction with zero amounts."""
        repo = WalletTransactionRepository(db_session)
        txn = repo.create(
            WalletTransactionCreate(
                wallet_id=wallet.id,
                customer_id=customer.id,
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("0"),
                credit_amount=Decimal("0"),
            )
        )
        assert txn.amount == Decimal("0")
        assert txn.credit_amount == Decimal("0")

    def test_get_by_customer_id_empty(self, db_session, customer):
        """Test getting transactions for customer with no transactions."""
        repo = WalletTransactionRepository(db_session)
        txns = repo.get_by_customer_id(customer.id)
        assert len(txns) == 0


class TestWalletTransactionSchema:
    """Tests for WalletTransaction Pydantic schemas."""

    def test_create_defaults(self):
        """Test WalletTransactionCreate default values."""
        schema = WalletTransactionCreate(
            wallet_id=uuid4(),
            customer_id=uuid4(),
            transaction_type=SchemaTransactionType.INBOUND,
        )
        assert schema.transaction_status == SchemaTransactionTransactionStatus.GRANTED
        assert schema.source == SchemaTransactionSource.MANUAL
        assert schema.status == SchemaTransactionStatus.PENDING
        assert schema.amount == Decimal("0")
        assert schema.credit_amount == Decimal("0")
        assert schema.invoice_id is None

    def test_create_full(self):
        """Test WalletTransactionCreate with all fields."""
        wid = uuid4()
        cid = uuid4()
        iid = uuid4()
        schema = WalletTransactionCreate(
            wallet_id=wid,
            customer_id=cid,
            transaction_type=SchemaTransactionType.OUTBOUND,
            transaction_status=SchemaTransactionTransactionStatus.INVOICED,
            source=SchemaTransactionSource.THRESHOLD,
            status=SchemaTransactionStatus.SETTLED,
            amount=Decimal("50.0000"),
            credit_amount=Decimal("5000.0000"),
            invoice_id=iid,
        )
        assert schema.wallet_id == wid
        assert schema.customer_id == cid
        assert schema.transaction_type == SchemaTransactionType.OUTBOUND
        assert schema.transaction_status == SchemaTransactionTransactionStatus.INVOICED
        assert schema.source == SchemaTransactionSource.THRESHOLD
        assert schema.status == SchemaTransactionStatus.SETTLED
        assert schema.amount == Decimal("50.0000")
        assert schema.credit_amount == Decimal("5000.0000")
        assert schema.invoice_id == iid

    def test_create_negative_amount_rejected(self):
        """Test that negative amounts are rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            WalletTransactionCreate(
                wallet_id=uuid4(),
                customer_id=uuid4(),
                transaction_type=SchemaTransactionType.INBOUND,
                amount=Decimal("-1"),
            )

    def test_create_negative_credit_amount_rejected(self):
        """Test that negative credit_amount is rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            WalletTransactionCreate(
                wallet_id=uuid4(),
                customer_id=uuid4(),
                transaction_type=SchemaTransactionType.INBOUND,
                credit_amount=Decimal("-1"),
            )

    def test_response_from_attributes(self, db_session, wallet, customer):
        """Test WalletTransactionResponse can serialize from ORM object."""
        txn = WalletTransaction(
            wallet_id=wallet.id,
            customer_id=customer.id,
            transaction_type=TransactionType.INBOUND.value,
            amount=Decimal("75.0000"),
            credit_amount=Decimal("7500.0000"),
        )
        db_session.add(txn)
        db_session.commit()
        db_session.refresh(txn)

        response = WalletTransactionResponse.model_validate(txn)
        assert response.id == txn.id
        assert response.wallet_id == wallet.id
        assert response.customer_id == customer.id
        assert response.transaction_type == "inbound"
        assert response.amount == Decimal("75.0000")
        assert response.credit_amount == Decimal("7500.0000")
        assert response.invoice_id is None
        assert response.created_at is not None
        assert response.updated_at is not None

    def test_response_with_invoice_id(self, db_session, wallet, customer, invoice):
        """Test WalletTransactionResponse serialization with invoice_id."""
        txn = WalletTransaction(
            wallet_id=wallet.id,
            customer_id=customer.id,
            transaction_type=TransactionType.OUTBOUND.value,
            invoice_id=invoice.id,
            amount=Decimal("25.0000"),
            credit_amount=Decimal("2500.0000"),
        )
        db_session.add(txn)
        db_session.commit()
        db_session.refresh(txn)

        response = WalletTransactionResponse.model_validate(txn)
        assert response.invoice_id == invoice.id

    def test_schema_enum_values(self):
        """Test schema enum values match expected strings."""
        assert SchemaTransactionType.INBOUND.value == "inbound"
        assert SchemaTransactionType.OUTBOUND.value == "outbound"

        assert SchemaTransactionStatus.PENDING.value == "pending"
        assert SchemaTransactionStatus.SETTLED.value == "settled"
        assert SchemaTransactionStatus.FAILED.value == "failed"

        assert SchemaTransactionTransactionStatus.PURCHASED.value == "purchased"
        assert SchemaTransactionTransactionStatus.GRANTED.value == "granted"
        assert SchemaTransactionTransactionStatus.VOIDED.value == "voided"
        assert SchemaTransactionTransactionStatus.INVOICED.value == "invoiced"

        assert SchemaTransactionSource.MANUAL.value == "manual"
        assert SchemaTransactionSource.INTERVAL.value == "interval"
        assert SchemaTransactionSource.THRESHOLD.value == "threshold"
