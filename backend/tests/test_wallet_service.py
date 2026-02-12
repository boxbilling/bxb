"""Tests for WalletService business logic."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.database import get_db
from app.models.wallet import WalletStatus
from app.repositories.customer_repository import CustomerRepository
from app.repositories.wallet_repository import WalletRepository
from app.repositories.wallet_transaction_repository import WalletTransactionRepository
from app.schemas.customer import CustomerCreate
from app.services.wallet_service import ConsumptionResult, WalletService
from tests.conftest import DEFAULT_ORG_ID


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
            external_id=f"ws_test_cust_{uuid4()}",
            name="WalletService Test Customer",
            email="walletservice@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def customer2(db_session):
    """Create a second test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"ws_test_cust2_{uuid4()}",
            name="WalletService Test Customer 2",
        ),
        DEFAULT_ORG_ID,
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


class TestCreateWallet:
    """Tests for WalletService.create_wallet()."""

    def test_create_wallet_basic(self, wallet_service, customer):
        """Test creating a basic wallet."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Basic Wallet",
            code="basic",
        )
        assert wallet is not None
        assert wallet.customer_id == customer.id
        assert wallet.name == "Basic Wallet"
        assert wallet.code == "basic"
        assert wallet.status == WalletStatus.ACTIVE.value
        assert wallet.balance_cents == 0
        assert wallet.credits_balance == 0

    def test_create_wallet_with_all_params(self, wallet_service, customer):
        """Test creating a wallet with all parameters."""
        expiry = datetime.now(UTC) + timedelta(days=30)
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Full Wallet",
            code="full",
            rate_amount=Decimal("2.5"),
            currency="EUR",
            expiration_at=expiry,
            priority=5,
        )
        assert wallet.rate_amount == Decimal("2.5000")
        assert wallet.currency == "EUR"
        assert wallet.priority == 5
        assert wallet.expiration_at is not None

    def test_create_wallet_with_initial_credits(self, wallet_service, customer, txn_repo):
        """Test creating a wallet with initial granted credits."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Funded Wallet",
            code="funded",
            rate_amount=Decimal("100"),
            initial_granted_credits=Decimal("50"),
        )
        assert wallet.credits_balance == Decimal("50.0000")
        assert wallet.balance_cents == Decimal("5000.0000")  # 50 credits * 100 rate

        # Verify transaction was created
        txns = txn_repo.get_by_wallet_id(wallet.id)
        assert len(txns) == 1
        assert txns[0].transaction_type == "inbound"
        assert txns[0].status == "settled"
        assert txns[0].amount == Decimal("50.0000")
        assert txns[0].credit_amount == Decimal("5000.0000")

    def test_create_wallet_with_zero_initial_credits(self, wallet_service, customer, txn_repo):
        """Test creating a wallet with zero initial credits creates no transaction."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Zero Wallet",
            code="zero",
            initial_granted_credits=Decimal("0"),
        )
        assert wallet.credits_balance == 0
        assert wallet.balance_cents == 0

        txns = txn_repo.get_by_wallet_id(wallet.id)
        assert len(txns) == 0

    def test_create_wallet_with_none_initial_credits(self, wallet_service, customer, txn_repo):
        """Test creating a wallet with None initial credits creates no transaction."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="None Wallet",
            code="none",
            initial_granted_credits=None,
        )
        assert wallet.credits_balance == 0

        txns = txn_repo.get_by_wallet_id(wallet.id)
        assert len(txns) == 0

    def test_create_wallet_duplicate_code(self, wallet_service, customer):
        """Test creating a wallet with duplicate code raises ValueError."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="First",
            code="duplicate",
        )
        with pytest.raises(ValueError, match="already exists"):
            wallet_service.create_wallet(
                customer_id=customer.id,
                name="Second",
                code="duplicate",
            )

    def test_create_wallet_defaults(self, wallet_service, customer):
        """Test creating a wallet with default values."""
        wallet = wallet_service.create_wallet(customer_id=customer.id)
        assert wallet.name is None
        assert wallet.code is None
        assert wallet.rate_amount == Decimal("1")
        assert wallet.currency == "USD"
        assert wallet.expiration_at is None
        assert wallet.priority == 1


class TestTerminateWallet:
    """Tests for WalletService.terminate_wallet()."""

    def test_terminate_wallet(self, wallet_service, customer):
        """Test terminating an active wallet."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="To Terminate",
            code="terminate",
        )
        terminated = wallet_service.terminate_wallet(wallet.id)
        assert terminated.status == WalletStatus.TERMINATED.value

    def test_terminate_wallet_not_found(self, wallet_service):
        """Test terminating a non-existent wallet raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            wallet_service.terminate_wallet(uuid4())

    def test_terminate_already_terminated(self, wallet_service, customer):
        """Test terminating an already terminated wallet raises ValueError."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Already Terminated",
            code="already-term",
        )
        wallet_service.terminate_wallet(wallet.id)

        with pytest.raises(ValueError, match="already terminated"):
            wallet_service.terminate_wallet(wallet.id)


class TestTopUpWallet:
    """Tests for WalletService.top_up_wallet()."""

    def test_top_up_wallet(self, wallet_service, customer, txn_repo):
        """Test topping up a wallet with credits."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Top Up Wallet",
            code="topup",
            rate_amount=Decimal("10"),
        )
        updated = wallet_service.top_up_wallet(wallet.id, Decimal("100"))
        assert updated.credits_balance == Decimal("100.0000")
        assert updated.balance_cents == Decimal("1000.0000")  # 100 credits * 10 rate

        # Verify transaction
        txns = txn_repo.get_by_wallet_id(wallet.id)
        assert len(txns) == 1
        assert txns[0].transaction_type == "inbound"
        assert txns[0].transaction_status == "granted"
        assert txns[0].source == "manual"
        assert txns[0].status == "settled"

    def test_top_up_wallet_multiple_times(self, wallet_service, customer, txn_repo):
        """Test multiple top-ups accumulate balance."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Multi Top Up",
            code="multi-topup",
        )
        wallet_service.top_up_wallet(wallet.id, Decimal("50"))
        updated = wallet_service.top_up_wallet(wallet.id, Decimal("30"))

        assert updated.credits_balance == Decimal("80.0000")
        assert updated.balance_cents == Decimal("80.0000")  # rate=1

        txns = txn_repo.get_by_wallet_id(wallet.id)
        assert len(txns) == 2

    def test_top_up_wallet_with_source(self, wallet_service, customer, txn_repo):
        """Test topping up with different sources."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Source Wallet",
            code="source",
        )
        wallet_service.top_up_wallet(wallet.id, Decimal("10"), source="interval")

        txns = txn_repo.get_by_wallet_id(wallet.id)
        assert txns[0].source == "interval"

    def test_top_up_wallet_threshold_source(self, wallet_service, customer, txn_repo):
        """Test topping up with threshold source."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Threshold Wallet",
            code="threshold",
        )
        wallet_service.top_up_wallet(wallet.id, Decimal("10"), source="threshold")

        txns = txn_repo.get_by_wallet_id(wallet.id)
        assert txns[0].source == "threshold"

    def test_top_up_terminated_wallet(self, wallet_service, customer):
        """Test that topping up a terminated wallet raises ValueError."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Terminated",
            code="terminated-topup",
        )
        wallet_service.terminate_wallet(wallet.id)

        with pytest.raises(ValueError, match="terminated"):
            wallet_service.top_up_wallet(wallet.id, Decimal("100"))

    def test_top_up_wallet_not_found(self, wallet_service):
        """Test topping up a non-existent wallet raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            wallet_service.top_up_wallet(uuid4(), Decimal("100"))

    def test_top_up_zero_credits(self, wallet_service, customer):
        """Test that topping up with zero credits raises ValueError."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Zero Topup",
            code="zero-topup",
        )
        with pytest.raises(ValueError, match="positive"):
            wallet_service.top_up_wallet(wallet.id, Decimal("0"))

    def test_top_up_negative_credits(self, wallet_service, customer):
        """Test that topping up with negative credits raises ValueError."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Neg Topup",
            code="neg-topup",
        )
        with pytest.raises(ValueError, match="positive"):
            wallet_service.top_up_wallet(wallet.id, Decimal("-5"))


class TestConsumeCredits:
    """Tests for WalletService.consume_credits() — priority-based consumption."""

    def test_consume_single_wallet_full_coverage(self, wallet_service, customer):
        """Test consuming from a single wallet that fully covers the amount."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Single Wallet",
            code="single",
            rate_amount=Decimal("1"),
            initial_granted_credits=Decimal("100"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("60"))
        assert result.total_consumed == Decimal("60")
        assert result.remaining_amount == Decimal("0")

        # Verify wallet balance decreased
        updated = wallet_service.wallet_repo.get_by_id(wallet.id)
        assert updated.balance_cents == Decimal("40.0000")
        assert updated.credits_balance == Decimal("40.0000")

    def test_consume_single_wallet_partial_coverage(self, wallet_service, customer):
        """Test consuming when wallet can only cover part of the amount."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Partial Wallet",
            code="partial",
            rate_amount=Decimal("1"),
            initial_granted_credits=Decimal("30"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("50"))
        assert result.total_consumed == Decimal("30")
        assert result.remaining_amount == Decimal("20")

    def test_consume_multiple_wallets_priority_order(self, wallet_service, customer, txn_repo):
        """Test that wallets are consumed in priority order (lower priority first)."""
        # Create wallets with different priorities
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Priority 3",
            code="p3",
            priority=3,
            initial_granted_credits=Decimal("50"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Priority 1",
            code="p1",
            priority=1,
            initial_granted_credits=Decimal("50"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Priority 2",
            code="p2",
            priority=2,
            initial_granted_credits=Decimal("50"),
        )

        # Consume 80 — should drain p1 (50) and then take 30 from p2
        result = wallet_service.consume_credits(customer.id, Decimal("80"))
        assert result.total_consumed == Decimal("80")
        assert result.remaining_amount == Decimal("0")

        # Verify priority 1 wallet is drained
        wallets = wallet_service.wallet_repo.get_by_customer_id(customer.id)
        # wallets are ordered by priority ASC
        assert Decimal(str(wallets[0].balance_cents)) == Decimal("0")  # p1 drained
        assert Decimal(str(wallets[1].balance_cents)) == Decimal("20.0000")  # p2 partially consumed
        assert Decimal(str(wallets[2].balance_cents)) == Decimal("50.0000")  # p3 untouched

    def test_consume_no_active_wallets(self, wallet_service, customer):
        """Test consuming when customer has no active wallets."""
        result = wallet_service.consume_credits(customer.id, Decimal("100"))
        assert result.total_consumed == Decimal("0")
        assert result.remaining_amount == Decimal("100")

    def test_consume_zero_balance_wallet_skipped(self, wallet_service, customer):
        """Test that wallets with zero balance are skipped."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Zero Balance",
            code="zero-bal",
            priority=1,
        )
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Has Balance",
            code="has-bal",
            priority=2,
            initial_granted_credits=Decimal("50"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("30"))
        assert result.total_consumed == Decimal("30")
        assert result.remaining_amount == Decimal("0")

    def test_consume_terminated_wallet_skipped(self, wallet_service, customer):
        """Test that terminated wallets are skipped during consumption."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Terminated",
            code="terminated-consume",
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.terminate_wallet(wallet.id)

        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Active",
            code="active-consume",
            initial_granted_credits=Decimal("50"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("70"))
        assert result.total_consumed == Decimal("50")
        assert result.remaining_amount == Decimal("20")

    def test_consume_expired_wallet_skipped(self, wallet_service, customer):
        """Test that expired wallets are skipped during consumption."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Expired",
            code="expired-consume",
            priority=1,
            expiration_at=datetime.now(UTC) - timedelta(days=1),
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Valid",
            code="valid-consume",
            priority=2,
            initial_granted_credits=Decimal("50"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("70"))
        assert result.total_consumed == Decimal("50")
        assert result.remaining_amount == Decimal("20")

    def test_consume_creates_outbound_transactions(self, wallet_service, customer, txn_repo):
        """Test that consumption creates outbound transactions."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Transaction Test",
            code="txn-test",
            initial_granted_credits=Decimal("100"),
        )

        wallet_service.consume_credits(customer.id, Decimal("40"))

        outbound = txn_repo.get_outbound_by_wallet_id(wallet.id)
        assert len(outbound) == 1
        assert outbound[0].transaction_type == "outbound"
        assert outbound[0].transaction_status == "invoiced"
        assert outbound[0].status == "settled"
        assert outbound[0].amount == Decimal("40.0000")
        assert outbound[0].credit_amount == Decimal("40.0000")

    def test_consume_with_invoice_id(self, wallet_service, customer, db_session, txn_repo):
        """Test that invoice_id is recorded on outbound transactions."""
        from app.repositories.invoice_repository import InvoiceRepository
        from app.repositories.plan_repository import PlanRepository
        from app.repositories.subscription_repository import SubscriptionRepository
        from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
        from app.schemas.plan import PlanCreate
        from app.schemas.subscription import SubscriptionCreate

        # Create supporting entities for invoice
        plan_repo = PlanRepository(db_session)
        plan = plan_repo.create(PlanCreate(code=f"ws_plan_{uuid4()}", name="WS Plan", interval="monthly"), DEFAULT_ORG_ID)

        sub_repo = SubscriptionRepository(db_session)
        sub = sub_repo.create(SubscriptionCreate(
            external_id=f"ws_sub_{uuid4()}",
            customer_id=customer.id,
            plan_id=plan.id,
        ),
        DEFAULT_ORG_ID,
        )

        invoice_repo = InvoiceRepository(db_session)
        now = datetime.now(UTC)
        invoice = invoice_repo.create(InvoiceCreate(
            customer_id=customer.id,
            subscription_id=sub.id,
            billing_period_start=now,
            billing_period_end=now + timedelta(days=30),
            line_items=[InvoiceLineItem(
                description="Test",
                unit_price=Decimal("10000"),
                amount=Decimal("10000"),
                quantity=Decimal("1"),
            )],
        ))

        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Invoice Test",
            code="inv-test",
            initial_granted_credits=Decimal("200"),
        )

        wallet_service.consume_credits(customer.id, Decimal("50"), invoice_id=invoice.id)

        txns = txn_repo.get_by_customer_id(customer.id)
        outbound = [t for t in txns if t.transaction_type == "outbound"]
        assert len(outbound) == 1
        assert outbound[0].invoice_id == invoice.id

    def test_consume_across_multiple_wallets_with_invoice(self, wallet_service, customer, txn_repo):
        """Test consumption across multiple wallets creates transactions for each."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Wallet A",
            code="wa",
            priority=1,
            initial_granted_credits=Decimal("30"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Wallet B",
            code="wb",
            priority=2,
            initial_granted_credits=Decimal("30"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("50"))
        assert result.total_consumed == Decimal("50")
        assert result.remaining_amount == Decimal("0")

        # Should have 2 outbound transactions (one per wallet) + 2 inbound (initial credits)
        all_txns = txn_repo.get_by_customer_id(customer.id)
        outbound = [t for t in all_txns if t.transaction_type == "outbound"]
        assert len(outbound) == 2

    def test_consume_with_different_rate_amounts(self, wallet_service, customer, txn_repo):
        """Test consumption with a wallet that has a non-1 rate amount."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Rate Wallet",
            code="rate",
            rate_amount=Decimal("200"),
            initial_granted_credits=Decimal("10"),
        )

        # Wallet has 10 credits * 200 rate = 2000 balance_cents
        result = wallet_service.consume_credits(customer.id, Decimal("1000"))
        assert result.total_consumed == Decimal("1000")
        assert result.remaining_amount == Decimal("0")

        updated = wallet_service.wallet_repo.get_by_id(wallet.id)
        # 1000 / 200 = 5 credits consumed
        assert updated.credits_balance == Decimal("5.0000")
        assert updated.balance_cents == Decimal("1000.0000")

    def test_consume_zero_amount(self, wallet_service, customer):
        """Test consuming zero amount returns immediately."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Zero Consume",
            code="zero-consume",
            initial_granted_credits=Decimal("100"),
        )

        result = wallet_service.consume_credits(customer.id, Decimal("0"))
        assert result.total_consumed == Decimal("0")
        assert result.remaining_amount == Decimal("0")

    def test_consume_exact_wallet_balance(self, wallet_service, customer):
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

    def test_consume_accumulated_consumed(self, wallet_service, customer):
        """Test that consumed amounts accumulate across multiple consumptions."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Accumulate",
            code="accumulate",
            initial_granted_credits=Decimal("100"),
        )

        wallet_service.consume_credits(customer.id, Decimal("20"))
        wallet_service.consume_credits(customer.id, Decimal("30"))

        updated = wallet_service.wallet_repo.get_by_id(wallet.id)
        assert updated.consumed_credits == Decimal("50.0000")
        assert updated.consumed_amount_cents == Decimal("50.0000")
        assert updated.credits_balance == Decimal("50.0000")
        assert updated.balance_cents == Decimal("50.0000")


class TestGetCustomerBalance:
    """Tests for WalletService.get_customer_balance()."""

    def test_get_balance_single_wallet(self, wallet_service, customer):
        """Test getting balance with one wallet."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Balance Test",
            code="balance",
            initial_granted_credits=Decimal("100"),
        )

        balance = wallet_service.get_customer_balance(customer.id)
        assert balance == Decimal("100.0000")

    def test_get_balance_multiple_wallets(self, wallet_service, customer):
        """Test getting balance across multiple wallets."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="W1",
            code="b1",
            initial_granted_credits=Decimal("50"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="W2",
            code="b2",
            initial_granted_credits=Decimal("75"),
        )

        balance = wallet_service.get_customer_balance(customer.id)
        assert balance == Decimal("125.0000")

    def test_get_balance_no_wallets(self, wallet_service, customer):
        """Test getting balance when customer has no wallets."""
        balance = wallet_service.get_customer_balance(customer.id)
        assert balance == Decimal("0")

    def test_get_balance_excludes_terminated(self, wallet_service, customer):
        """Test that terminated wallets are excluded from balance."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Terminated",
            code="term-bal",
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Active",
            code="active-bal",
            initial_granted_credits=Decimal("50"),
        )
        wallet_service.terminate_wallet(wallet.id)

        balance = wallet_service.get_customer_balance(customer.id)
        assert balance == Decimal("50.0000")

    def test_get_balance_excludes_expired(self, wallet_service, customer):
        """Test that expired wallets are excluded from balance."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Expired",
            code="expired-bal",
            expiration_at=datetime.now(UTC) - timedelta(days=1),
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Valid",
            code="valid-bal",
            initial_granted_credits=Decimal("50"),
        )

        balance = wallet_service.get_customer_balance(customer.id)
        assert balance == Decimal("50.0000")

    def test_get_balance_customer_isolation(self, wallet_service, customer, customer2):
        """Test that balance is isolated between customers."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="C1",
            code="c1-bal",
            initial_granted_credits=Decimal("100"),
        )
        wallet_service.create_wallet(
            customer_id=customer2.id,
            name="C2",
            code="c2-bal",
            initial_granted_credits=Decimal("200"),
        )

        assert wallet_service.get_customer_balance(customer.id) == Decimal("100.0000")
        assert wallet_service.get_customer_balance(customer2.id) == Decimal("200.0000")


class TestCheckExpiredWallets:
    """Tests for WalletService.check_expired_wallets()."""

    def test_terminate_expired_wallets(self, wallet_service, customer, wallet_repo):
        """Test that expired wallets are terminated."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Expired",
            code="expired-check",
            expiration_at=datetime.now(UTC) - timedelta(days=1),
        )
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Valid",
            code="valid-check",
            expiration_at=datetime.now(UTC) + timedelta(days=30),
        )

        terminated_ids = wallet_service.check_expired_wallets()
        assert len(terminated_ids) == 1

        # Verify the expired wallet was terminated
        wallets = wallet_repo.get_all(DEFAULT_ORG_ID, customer_id=customer.id)
        statuses = {w.name: w.status for w in wallets}
        assert statuses["Expired"] == WalletStatus.TERMINATED.value
        assert statuses["Valid"] == WalletStatus.ACTIVE.value

    def test_no_expired_wallets(self, wallet_service, customer):
        """Test that no wallets are terminated when none are expired."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Future",
            code="future-check",
            expiration_at=datetime.now(UTC) + timedelta(days=30),
        )

        terminated_ids = wallet_service.check_expired_wallets()
        assert len(terminated_ids) == 0

    def test_wallets_without_expiration_untouched(self, wallet_service, customer, wallet_repo):
        """Test that wallets without expiration are not terminated."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="No Expiry",
            code="no-expiry",
        )

        terminated_ids = wallet_service.check_expired_wallets()
        assert len(terminated_ids) == 0

        wallet = wallet_repo.get_all(DEFAULT_ORG_ID, customer_id=customer.id)[0]
        assert wallet.status == WalletStatus.ACTIVE.value

    def test_already_terminated_not_reprocessed(self, wallet_service, customer):
        """Test that already terminated wallets are not reprocessed."""
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Already Term",
            code="already-term-check",
            expiration_at=datetime.now(UTC) - timedelta(days=1),
        )
        wallet_service.terminate_wallet(wallet.id)

        terminated_ids = wallet_service.check_expired_wallets()
        assert len(terminated_ids) == 0

    def test_multiple_expired_wallets(self, wallet_service, customer, customer2):
        """Test terminating multiple expired wallets across customers."""
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Expired 1",
            code="exp1",
            expiration_at=datetime.now(UTC) - timedelta(days=1),
        )
        wallet_service.create_wallet(
            customer_id=customer2.id,
            name="Expired 2",
            code="exp2",
            expiration_at=datetime.now(UTC) - timedelta(hours=1),
        )
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Valid",
            code="valid-multi",
            expiration_at=datetime.now(UTC) + timedelta(days=30),
        )

        terminated_ids = wallet_service.check_expired_wallets()
        assert len(terminated_ids) == 2


class TestConsumptionResult:
    """Tests for ConsumptionResult dataclass."""

    def test_consumption_result(self):
        """Test ConsumptionResult creation."""
        result = ConsumptionResult(
            total_consumed=Decimal("50"),
            remaining_amount=Decimal("25"),
        )
        assert result.total_consumed == Decimal("50")
        assert result.remaining_amount == Decimal("25")
