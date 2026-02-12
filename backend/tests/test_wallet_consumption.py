"""Tests for priority-based wallet consumption algorithm.

This file focuses on the consume_credits() logic: single wallet, multiple wallets
with priorities, partial consumption, expired wallet skipping, terminated wallet
skipping, zero-balance wallet skipping, and edge cases.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.database import get_db
from app.repositories.customer_repository import CustomerRepository
from app.repositories.wallet_repository import WalletRepository
from app.repositories.wallet_transaction_repository import WalletTransactionRepository
from app.schemas.customer import CustomerCreate
from app.services.wallet_service import ConsumptionResult, WalletService


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
            external_id=f"consume_test_{uuid4()}",
            name="Consumption Test Customer",
            email="consume@test.com",
        )
    )


@pytest.fixture
def customer2(db_session):
    """Create a second test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"consume_test2_{uuid4()}",
            name="Consumption Test Customer 2",
        )
    )


@pytest.fixture
def wallet_service(db_session):
    """Create a WalletService instance."""
    return WalletService(db_session)


@pytest.fixture
def wallet_repo(db_session):
    """Create a WalletRepository instance."""
    return WalletRepository(db_session)


@pytest.fixture
def txn_repo(db_session):
    """Create a WalletTransactionRepository instance."""
    return WalletTransactionRepository(db_session)


class TestSingleWalletConsumption:
    """Tests for consuming credits from a single wallet."""

    def test_full_coverage(self, wallet_service, customer):
        """Test consuming less than available balance fully covers amount."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Full Coverage",
            code="fc",
            initial_granted_credits=Decimal("100"),
        )
        result = wallet_service.consume_credits(customer.id, Decimal("60"))
        assert result.total_consumed == Decimal("60")
        assert result.remaining_amount == Decimal("0")

    def test_partial_coverage(self, wallet_service, customer):
        """Test consuming more than available balance leaves remainder."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Partial Coverage",
            code="pc",
            initial_granted_credits=Decimal("30"),
        )
        result = wallet_service.consume_credits(customer.id, Decimal("50"))
        assert result.total_consumed == Decimal("30")
        assert result.remaining_amount == Decimal("20")

    def test_exact_balance_consumption(self, wallet_service, customer):
        """Test consuming exactly the wallet balance."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Exact",
            code="exact",
            initial_granted_credits=Decimal("75"),
        )
        result = wallet_service.consume_credits(customer.id, Decimal("75"))
        assert result.total_consumed == Decimal("75")
        assert result.remaining_amount == Decimal("0")

    def test_zero_amount_consumption(self, wallet_service, customer):
        """Test consuming zero amount returns immediately."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Zero",
            code="zero",
            initial_granted_credits=Decimal("100"),
        )
        result = wallet_service.consume_credits(customer.id, Decimal("0"))
        assert result.total_consumed == Decimal("0")
        assert result.remaining_amount == Decimal("0")

    def test_wallet_balance_updated_after_consumption(self, wallet_service, customer, wallet_repo):
        """Test that wallet balance and consumed amounts are updated."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Balance Check",
            code="bal-chk",
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.consume_credits(customer.id, Decimal("40"))

        updated = wallet_repo.get_by_id(wallet.id)
        assert updated.balance_cents == Decimal("60.0000")
        assert updated.credits_balance == Decimal("60.0000")
        assert updated.consumed_amount_cents == Decimal("40.0000")
        assert updated.consumed_credits == Decimal("40.0000")

    def test_multiple_consumptions_accumulate(self, wallet_service, customer, wallet_repo):
        """Test that multiple consumptions accumulate correctly."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Accumulate",
            code="accum",
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.consume_credits(customer.id, Decimal("20"))
        wallet_service.consume_credits(customer.id, Decimal("30"))
        wallet_service.consume_credits(customer.id, Decimal("10"))

        updated = wallet_repo.get_by_id(wallet.id)
        assert updated.consumed_credits == Decimal("60.0000")
        assert updated.consumed_amount_cents == Decimal("60.0000")
        assert updated.credits_balance == Decimal("40.0000")
        assert updated.balance_cents == Decimal("40.0000")


class TestMultiWalletPriorityConsumption:
    """Tests for consuming from multiple wallets with priority ordering."""

    def test_priority_order_lower_first(self, wallet_service, customer, wallet_repo):
        """Test that lower priority wallets are consumed first."""
        wallet_service.create_wallet(
            customer_id=customer.id, name="P3", code="p3",
            priority=3, initial_granted_credits=Decimal("50"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id, name="P1", code="p1",
            priority=1, initial_granted_credits=Decimal("50"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id, name="P2", code="p2",
            priority=2, initial_granted_credits=Decimal("50"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("80"))
        assert result.total_consumed == Decimal("80")
        assert result.remaining_amount == Decimal("0")

        wallets = wallet_repo.get_by_customer_id(customer.id)
        # Ordered by priority ASC: P1 (drained), P2 (partially consumed), P3 (untouched)
        assert Decimal(str(wallets[0].balance_cents)) == Decimal("0")  # P1 fully drained
        assert Decimal(str(wallets[1].balance_cents)) == Decimal("20.0000")  # P2 partially
        assert Decimal(str(wallets[2].balance_cents)) == Decimal("50.0000")  # P3 untouched

    def test_drain_first_wallet_then_second(self, wallet_service, customer, wallet_repo):
        """Test draining first wallet completely then moving to second."""
        wallet_service.create_wallet(
            customer_id=customer.id, name="First", code="first",
            priority=1, initial_granted_credits=Decimal("30"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id, name="Second", code="second",
            priority=2, initial_granted_credits=Decimal("30"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("50"))
        assert result.total_consumed == Decimal("50")
        assert result.remaining_amount == Decimal("0")

        wallets = wallet_repo.get_by_customer_id(customer.id)
        assert Decimal(str(wallets[0].balance_cents)) == Decimal("0")  # First drained
        assert Decimal(str(wallets[1].balance_cents)) == Decimal("10.0000")  # Second used 20

    def test_drain_all_wallets_with_remainder(self, wallet_service, customer):
        """Test when all wallets are drained but amount isn't fully covered."""
        wallet_service.create_wallet(
            customer_id=customer.id, name="W1", code="w1",
            priority=1, initial_granted_credits=Decimal("30"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id, name="W2", code="w2",
            priority=2, initial_granted_credits=Decimal("20"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("100"))
        assert result.total_consumed == Decimal("50")
        assert result.remaining_amount == Decimal("50")

    def test_same_priority_uses_created_at_order(self, wallet_service, customer, wallet_repo):
        """Test that wallets with same priority are consumed by created_at ASC."""
        w1 = wallet_service.create_wallet(
            customer_id=customer.id, name="Older", code="older",
            priority=1, initial_granted_credits=Decimal("30"),
        )
        w2 = wallet_service.create_wallet(
            customer_id=customer.id, name="Newer", code="newer",
            priority=1, initial_granted_credits=Decimal("30"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("40"))
        assert result.total_consumed == Decimal("40")

        # Older wallet should be consumed first (created_at ASC)
        w1_updated = wallet_repo.get_by_id(w1.id)
        w2_updated = wallet_repo.get_by_id(w2.id)
        assert Decimal(str(w1_updated.balance_cents)) == Decimal("0")  # Fully drained
        assert Decimal(str(w2_updated.balance_cents)) == Decimal("20.0000")  # 10 consumed

    def test_outbound_transactions_per_wallet(self, wallet_service, customer, txn_repo):
        """Test that each consumed wallet gets its own outbound transaction."""
        wallet_service.create_wallet(
            customer_id=customer.id, name="WA", code="wa",
            priority=1, initial_granted_credits=Decimal("30"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id, name="WB", code="wb",
            priority=2, initial_granted_credits=Decimal("30"),
        )

        wallet_service.consume_credits(customer.id, Decimal("50"))

        all_txns = txn_repo.get_by_customer_id(customer.id)
        outbound = [t for t in all_txns if t.transaction_type == "outbound"]
        assert len(outbound) == 2

        # Verify amounts
        outbound_amounts = sorted([Decimal(str(t.amount)) for t in outbound])
        assert outbound_amounts == [Decimal("20.0000"), Decimal("30.0000")]


class TestSkippedWalletConsumption:
    """Tests for wallets that should be skipped during consumption."""

    def test_terminated_wallet_skipped(self, wallet_service, customer):
        """Test that terminated wallets are not consumed."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id, name="Term", code="term",
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.terminate_wallet(wallet.id)

        wallet_service.create_wallet(
            customer_id=customer.id, name="Active", code="active",
            initial_granted_credits=Decimal("50"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("70"))
        assert result.total_consumed == Decimal("50")
        assert result.remaining_amount == Decimal("20")

    def test_expired_wallet_skipped(self, wallet_service, customer):
        """Test that expired wallets are not consumed."""
        wallet_service.create_wallet(
            customer_id=customer.id, name="Expired", code="expired",
            priority=1,
            expiration_at=datetime.now(UTC) - timedelta(days=1),
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id, name="Valid", code="valid",
            priority=2, initial_granted_credits=Decimal("50"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("70"))
        assert result.total_consumed == Decimal("50")
        assert result.remaining_amount == Decimal("20")

    def test_zero_balance_wallet_skipped(self, wallet_service, customer, wallet_repo):
        """Test that zero-balance wallets are skipped."""
        wallet_service.create_wallet(
            customer_id=customer.id, name="Empty", code="empty",
            priority=1,
        )
        wallet_service.create_wallet(
            customer_id=customer.id, name="Funded", code="funded",
            priority=2, initial_granted_credits=Decimal("50"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("30"))
        assert result.total_consumed == Decimal("30")
        assert result.remaining_amount == Decimal("0")

        # Verify only the funded wallet was consumed
        wallets = wallet_repo.get_active_by_customer_id(customer.id)
        funded = [w for w in wallets if w.name == "Funded"][0]
        assert Decimal(str(funded.balance_cents)) == Decimal("20.0000")

    def test_no_active_wallets(self, wallet_service, customer):
        """Test consuming when customer has no wallets at all."""
        result = wallet_service.consume_credits(customer.id, Decimal("100"))
        assert result.total_consumed == Decimal("0")
        assert result.remaining_amount == Decimal("100")

    def test_all_wallets_terminated(self, wallet_service, customer):
        """Test consuming when all wallets are terminated."""
        w1 = wallet_service.create_wallet(
            customer_id=customer.id, name="T1", code="t1",
            initial_granted_credits=Decimal("100"),
        )
        w2 = wallet_service.create_wallet(
            customer_id=customer.id, name="T2", code="t2",
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.terminate_wallet(w1.id)
        wallet_service.terminate_wallet(w2.id)

        result = wallet_service.consume_credits(customer.id, Decimal("50"))
        assert result.total_consumed == Decimal("0")
        assert result.remaining_amount == Decimal("50")

    def test_all_wallets_expired(self, wallet_service, customer):
        """Test consuming when all wallets are expired."""
        wallet_service.create_wallet(
            customer_id=customer.id, name="E1", code="e1",
            expiration_at=datetime.now(UTC) - timedelta(days=1),
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id, name="E2", code="e2",
            expiration_at=datetime.now(UTC) - timedelta(hours=1),
            initial_granted_credits=Decimal("100"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("50"))
        assert result.total_consumed == Decimal("0")
        assert result.remaining_amount == Decimal("50")

    def test_mix_of_skippable_wallets(self, wallet_service, customer):
        """Test consumption with a mix of terminated, expired, empty, and active wallets."""
        # Terminated
        w_term = wallet_service.create_wallet(
            customer_id=customer.id, name="Terminated", code="mix-term",
            priority=1, initial_granted_credits=Decimal("100"),
        )
        wallet_service.terminate_wallet(w_term.id)

        # Expired
        wallet_service.create_wallet(
            customer_id=customer.id, name="Expired", code="mix-exp",
            priority=2,
            expiration_at=datetime.now(UTC) - timedelta(days=1),
            initial_granted_credits=Decimal("100"),
        )

        # Empty
        wallet_service.create_wallet(
            customer_id=customer.id, name="Empty", code="mix-empty",
            priority=3,
        )

        # Active with balance (only one that should be consumed)
        wallet_service.create_wallet(
            customer_id=customer.id, name="Active", code="mix-active",
            priority=4, initial_granted_credits=Decimal("40"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("60"))
        assert result.total_consumed == Decimal("40")
        assert result.remaining_amount == Decimal("20")


class TestConsumptionWithRateAmount:
    """Tests for consumption with different rate amounts (credits != currency)."""

    def test_rate_amount_conversion(self, wallet_service, customer, wallet_repo):
        """Test that rate_amount is used to convert between credits and currency."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id, name="Rate", code="rate",
            rate_amount=Decimal("200"),  # 1 credit = 200 cents
            initial_granted_credits=Decimal("10"),  # 10 credits = 2000 cents
        )

        result = wallet_service.consume_credits(customer.id, Decimal("1000"))  # consume 1000 cents
        assert result.total_consumed == Decimal("1000")
        assert result.remaining_amount == Decimal("0")

        updated = wallet_repo.get_by_id(wallet.id)
        # 1000 cents / 200 rate = 5 credits consumed
        assert updated.credits_balance == Decimal("5.0000")
        assert updated.balance_cents == Decimal("1000.0000")

    def test_different_rate_amounts_across_wallets(self, wallet_service, customer, wallet_repo, txn_repo):
        """Test consumption across wallets with different rate amounts."""
        w1 = wallet_service.create_wallet(
            customer_id=customer.id, name="Rate100", code="r100",
            priority=1, rate_amount=Decimal("100"),
            initial_granted_credits=Decimal("5"),  # 500 cents
        )
        w2 = wallet_service.create_wallet(
            customer_id=customer.id, name="Rate50", code="r50",
            priority=2, rate_amount=Decimal("50"),
            initial_granted_credits=Decimal("10"),  # 500 cents
        )

        result = wallet_service.consume_credits(customer.id, Decimal("700"))
        assert result.total_consumed == Decimal("700")
        assert result.remaining_amount == Decimal("0")

        # W1: 500 cents consumed (5 credits drained)
        w1_updated = wallet_repo.get_by_id(w1.id)
        assert Decimal(str(w1_updated.balance_cents)) == Decimal("0")
        assert Decimal(str(w1_updated.credits_balance)) == Decimal("0")

        # W2: 200 cents consumed (4 credits consumed: 200/50)
        w2_updated = wallet_repo.get_by_id(w2.id)
        assert Decimal(str(w2_updated.balance_cents)) == Decimal("300.0000")
        assert Decimal(str(w2_updated.credits_balance)) == Decimal("6.0000")


class TestConsumptionTransactions:
    """Tests for transaction creation during consumption."""

    def test_outbound_transaction_fields(self, wallet_service, customer, txn_repo):
        """Test that outbound transactions have correct field values."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id, name="Txn Fields", code="txn-fields",
            initial_granted_credits=Decimal("100"),
        )

        wallet_service.consume_credits(customer.id, Decimal("40"))

        outbound = txn_repo.get_outbound_by_wallet_id(wallet.id)
        assert len(outbound) == 1
        txn = outbound[0]
        assert txn.transaction_type == "outbound"
        assert txn.transaction_status == "invoiced"
        assert txn.source == "manual"
        assert txn.status == "settled"
        assert Decimal(str(txn.amount)) == Decimal("40.0000")
        assert Decimal(str(txn.credit_amount)) == Decimal("40.0000")
        assert txn.invoice_id is None

    def test_outbound_transaction_with_invoice_id(self, wallet_service, customer, db_session, txn_repo):
        """Test that invoice_id is recorded on outbound transactions."""
        from app.repositories.invoice_repository import InvoiceRepository
        from app.repositories.plan_repository import PlanRepository
        from app.repositories.subscription_repository import SubscriptionRepository
        from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
        from app.schemas.plan import PlanCreate
        from app.schemas.subscription import SubscriptionCreate

        plan = PlanRepository(db_session).create(
            PlanCreate(code=f"wc_plan_{uuid4()}", name="WC Plan", interval="monthly")
        )
        sub = SubscriptionRepository(db_session).create(
            SubscriptionCreate(
                external_id=f"wc_sub_{uuid4()}",
                customer_id=customer.id,
                plan_id=plan.id,
            )
        )
        now = datetime.now(UTC)
        invoice = InvoiceRepository(db_session).create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=sub.id,
                billing_period_start=now,
                billing_period_end=now + timedelta(days=30),
                line_items=[InvoiceLineItem(
                    description="Test", unit_price=Decimal("5000"),
                    amount=Decimal("5000"), quantity=Decimal("1"),
                )],
            )
        )

        wallet_service.create_wallet(
            customer_id=customer.id, name="Invoice Txn", code="inv-txn",
            initial_granted_credits=Decimal("200"),
        )
        wallet_service.consume_credits(customer.id, Decimal("50"), invoice_id=invoice.id)

        all_txns = txn_repo.get_by_customer_id(customer.id)
        outbound = [t for t in all_txns if t.transaction_type == "outbound"]
        assert len(outbound) == 1
        assert outbound[0].invoice_id == invoice.id

    def test_no_transaction_created_for_zero_consumption(self, wallet_service, customer, txn_repo):
        """Test that no outbound transaction is created when nothing is consumed."""
        wallet_service.create_wallet(
            customer_id=customer.id, name="Zero Txn", code="zero-txn",
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.consume_credits(customer.id, Decimal("0"))

        all_txns = txn_repo.get_by_customer_id(customer.id)
        outbound = [t for t in all_txns if t.transaction_type == "outbound"]
        assert len(outbound) == 0

    def test_no_outbound_when_no_wallets(self, wallet_service, customer, txn_repo):
        """Test that no outbound transaction is created when customer has no wallets."""
        wallet_service.consume_credits(customer.id, Decimal("100"))

        txns = txn_repo.get_by_customer_id(customer.id)
        assert len(txns) == 0


class TestConsumptionCustomerIsolation:
    """Tests for customer isolation during consumption."""

    def test_consumption_isolated_between_customers(self, wallet_service, customer, customer2, wallet_repo):
        """Test that consuming from one customer doesn't affect another."""
        wallet_service.create_wallet(
            customer_id=customer.id, name="C1", code="c1",
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.create_wallet(
            customer_id=customer2.id, name="C2", code="c2",
            initial_granted_credits=Decimal("100"),
        )

        wallet_service.consume_credits(customer.id, Decimal("40"))

        # Customer 2's wallet should be untouched
        c2_wallets = wallet_repo.get_active_by_customer_id(customer2.id)
        assert len(c2_wallets) == 1
        assert Decimal(str(c2_wallets[0].balance_cents)) == Decimal("100.0000")

    def test_consumption_result_independent(self, wallet_service, customer, customer2):
        """Test that consumption results are independent per customer."""
        wallet_service.create_wallet(
            customer_id=customer.id, name="C1", code="c1",
            initial_granted_credits=Decimal("50"),
        )
        wallet_service.create_wallet(
            customer_id=customer2.id, name="C2", code="c2",
            initial_granted_credits=Decimal("100"),
        )

        r1 = wallet_service.consume_credits(customer.id, Decimal("80"))
        r2 = wallet_service.consume_credits(customer2.id, Decimal("80"))

        assert r1.total_consumed == Decimal("50")
        assert r1.remaining_amount == Decimal("30")
        assert r2.total_consumed == Decimal("80")
        assert r2.remaining_amount == Decimal("0")


class TestConsumptionResultDataclass:
    """Tests for ConsumptionResult dataclass."""

    def test_creation(self):
        """Test ConsumptionResult creation with values."""
        result = ConsumptionResult(
            total_consumed=Decimal("50"),
            remaining_amount=Decimal("25"),
        )
        assert result.total_consumed == Decimal("50")
        assert result.remaining_amount == Decimal("25")

    def test_zero_values(self):
        """Test ConsumptionResult with zero values."""
        result = ConsumptionResult(
            total_consumed=Decimal("0"),
            remaining_amount=Decimal("0"),
        )
        assert result.total_consumed == Decimal("0")
        assert result.remaining_amount == Decimal("0")
