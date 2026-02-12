"""Tests for Wallet model, schema, repository, and CRUD operations."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.wallet import Wallet, WalletStatus
from app.repositories.customer_repository import CustomerRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.customer import CustomerCreate
from app.schemas.wallet import WalletCreate, WalletUpdate


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
            external_id=f"wallet_test_cust_{uuid4()}",
            name="Wallet Test Customer",
            email="wallet@test.com",
        )
    )


@pytest.fixture
def customer2(db_session):
    """Create a second test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"wallet_test_cust2_{uuid4()}",
            name="Wallet Test Customer 2",
        )
    )


@pytest.fixture
def wallet(db_session, customer):
    """Create a test wallet."""
    repo = WalletRepository(db_session)
    return repo.create(
        WalletCreate(
            customer_id=customer.id,
            name="Test Wallet",
            code="test-wallet",
            rate_amount=Decimal("1.0000"),
            currency="USD",
            priority=1,
        )
    )


class TestWalletModel:
    """Tests for Wallet SQLAlchemy model."""

    def test_wallet_defaults(self, db_session, customer):
        """Test Wallet model default values."""
        wallet = Wallet(customer_id=customer.id)
        db_session.add(wallet)
        db_session.commit()
        db_session.refresh(wallet)

        assert wallet.id is not None
        assert wallet.customer_id == customer.id
        assert wallet.name is None
        assert wallet.code is None
        assert wallet.status == WalletStatus.ACTIVE.value
        assert wallet.balance_cents == 0
        assert wallet.credits_balance == 0
        assert wallet.consumed_amount_cents == 0
        assert wallet.consumed_credits == 0
        assert wallet.rate_amount == 1
        assert wallet.currency == "USD"
        assert wallet.expiration_at is None
        assert wallet.priority == 1
        assert wallet.created_at is not None
        assert wallet.updated_at is not None

    def test_wallet_with_all_fields(self, db_session, customer):
        """Test Wallet model with all fields populated."""
        expiry = datetime.now(UTC) + timedelta(days=30)
        wallet = Wallet(
            customer_id=customer.id,
            name="Premium Wallet",
            code="premium-001",
            status=WalletStatus.ACTIVE.value,
            balance_cents=Decimal("50000.0000"),
            credits_balance=Decimal("500.0000"),
            consumed_amount_cents=Decimal("10000.0000"),
            consumed_credits=Decimal("100.0000"),
            rate_amount=Decimal("100.0000"),
            currency="EUR",
            expiration_at=expiry,
            priority=5,
        )
        db_session.add(wallet)
        db_session.commit()
        db_session.refresh(wallet)

        assert wallet.name == "Premium Wallet"
        assert wallet.code == "premium-001"
        assert wallet.currency == "EUR"
        assert wallet.priority == 5
        assert wallet.balance_cents == Decimal("50000.0000")
        assert wallet.credits_balance == Decimal("500.0000")

    def test_wallet_status_enum(self):
        """Test WalletStatus enum values."""
        assert WalletStatus.ACTIVE.value == "active"
        assert WalletStatus.TERMINATED.value == "terminated"


class TestWalletRepository:
    """Tests for WalletRepository CRUD and query methods."""

    def test_create_wallet(self, db_session, customer):
        """Test creating a wallet."""
        repo = WalletRepository(db_session)
        wallet = repo.create(
            WalletCreate(
                customer_id=customer.id,
                name="My Wallet",
                code="my-wallet",
                rate_amount=Decimal("2.5000"),
                currency="EUR",
                priority=3,
            )
        )
        assert wallet.id is not None
        assert wallet.customer_id == customer.id
        assert wallet.name == "My Wallet"
        assert wallet.code == "my-wallet"
        assert wallet.rate_amount == Decimal("2.5000")
        assert wallet.currency == "EUR"
        assert wallet.priority == 3
        assert wallet.status == WalletStatus.ACTIVE.value
        assert wallet.balance_cents == 0
        assert wallet.credits_balance == 0

    def test_create_wallet_minimal(self, db_session, customer):
        """Test creating a wallet with only required fields."""
        repo = WalletRepository(db_session)
        wallet = repo.create(WalletCreate(customer_id=customer.id))
        assert wallet.id is not None
        assert wallet.customer_id == customer.id
        assert wallet.name is None
        assert wallet.code is None
        assert wallet.rate_amount == Decimal("1")
        assert wallet.currency == "USD"
        assert wallet.priority == 1

    def test_get_by_id(self, db_session, wallet):
        """Test getting a wallet by ID."""
        repo = WalletRepository(db_session)
        fetched = repo.get_by_id(wallet.id)
        assert fetched is not None
        assert fetched.id == wallet.id
        assert fetched.name == "Test Wallet"

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent wallet."""
        repo = WalletRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_customer_id(self, db_session, customer):
        """Test getting wallets by customer ID, ordered by priority then created_at."""
        repo = WalletRepository(db_session)
        # Create wallets with different priorities
        w1 = repo.create(WalletCreate(customer_id=customer.id, name="Priority 3", code="w3", priority=3))
        w2 = repo.create(WalletCreate(customer_id=customer.id, name="Priority 1", code="w1", priority=1))
        w3 = repo.create(WalletCreate(customer_id=customer.id, name="Priority 2", code="w2", priority=2))

        wallets = repo.get_by_customer_id(customer.id)
        assert len(wallets) == 3
        assert wallets[0].id == w2.id  # Priority 1
        assert wallets[1].id == w3.id  # Priority 2
        assert wallets[2].id == w1.id  # Priority 3

    def test_get_active_by_customer_id(self, db_session, customer):
        """Test getting only active, non-expired wallets."""
        repo = WalletRepository(db_session)
        # Active wallet
        active = repo.create(WalletCreate(customer_id=customer.id, name="Active", code="active", priority=1))
        # Terminated wallet
        terminated = repo.create(WalletCreate(customer_id=customer.id, name="Terminated", code="terminated", priority=2))
        repo.terminate(terminated.id)
        # Expired wallet
        expired = repo.create(WalletCreate(
            customer_id=customer.id,
            name="Expired",
            code="expired",
            priority=3,
            expiration_at=datetime.now(UTC) - timedelta(days=1),
        ))
        # Future expiry wallet (still valid)
        future = repo.create(WalletCreate(
            customer_id=customer.id,
            name="Future",
            code="future",
            priority=4,
            expiration_at=datetime.now(UTC) + timedelta(days=30),
        ))

        wallets = repo.get_active_by_customer_id(customer.id)
        wallet_ids = [w.id for w in wallets]
        assert active.id in wallet_ids
        assert future.id in wallet_ids
        assert terminated.id not in wallet_ids
        assert expired.id not in wallet_ids
        assert len(wallets) == 2

    def test_get_active_by_customer_id_priority_ordering(self, db_session, customer):
        """Test that active wallets are returned ordered by priority ASC, created_at ASC."""
        repo = WalletRepository(db_session)
        w_high = repo.create(WalletCreate(customer_id=customer.id, name="High", code="high", priority=10))
        w_low = repo.create(WalletCreate(customer_id=customer.id, name="Low", code="low", priority=1))

        wallets = repo.get_active_by_customer_id(customer.id)
        assert wallets[0].id == w_low.id
        assert wallets[1].id == w_high.id

    def test_get_all(self, db_session, customer):
        """Test getting all wallets with filters."""
        repo = WalletRepository(db_session)
        repo.create(WalletCreate(customer_id=customer.id, name="W1", code="w1"))
        w2 = repo.create(WalletCreate(customer_id=customer.id, name="W2", code="w2"))
        repo.terminate(w2.id)

        # All wallets
        all_wallets = repo.get_all()
        assert len(all_wallets) == 2

        # Filter by customer
        customer_wallets = repo.get_all(customer_id=customer.id)
        assert len(customer_wallets) == 2

        # Filter by status
        active_wallets = repo.get_all(status=WalletStatus.ACTIVE)
        assert len(active_wallets) == 1

        terminated_wallets = repo.get_all(status=WalletStatus.TERMINATED)
        assert len(terminated_wallets) == 1

    def test_get_all_pagination(self, db_session, customer):
        """Test pagination for get_all."""
        repo = WalletRepository(db_session)
        for i in range(5):
            repo.create(WalletCreate(customer_id=customer.id, name=f"W{i}", code=f"w{i}"))

        wallets = repo.get_all(skip=2, limit=2)
        assert len(wallets) == 2

    def test_update(self, db_session, wallet):
        """Test updating a wallet."""
        repo = WalletRepository(db_session)
        new_expiry = datetime.now(UTC) + timedelta(days=60)
        updated = repo.update(
            wallet.id,
            WalletUpdate(name="Updated Wallet", priority=10, expiration_at=new_expiry),
        )
        assert updated is not None
        assert updated.name == "Updated Wallet"
        assert updated.priority == 10
        assert updated.expiration_at is not None

    def test_update_partial(self, db_session, wallet):
        """Test partial update of a wallet."""
        repo = WalletRepository(db_session)
        updated = repo.update(wallet.id, WalletUpdate(name="New Name"))
        assert updated is not None
        assert updated.name == "New Name"
        assert updated.priority == 1  # unchanged

    def test_update_not_found(self, db_session):
        """Test updating a non-existent wallet."""
        repo = WalletRepository(db_session)
        assert repo.update(uuid4(), WalletUpdate(name="nope")) is None

    def test_terminate(self, db_session, wallet):
        """Test terminating a wallet."""
        repo = WalletRepository(db_session)
        terminated = repo.terminate(wallet.id)
        assert terminated is not None
        assert terminated.status == WalletStatus.TERMINATED.value

    def test_terminate_already_terminated(self, db_session, wallet):
        """Test terminating an already terminated wallet."""
        repo = WalletRepository(db_session)
        repo.terminate(wallet.id)
        # Should not raise, just return the wallet
        terminated = repo.terminate(wallet.id)
        assert terminated is not None
        assert terminated.status == WalletStatus.TERMINATED.value

    def test_terminate_not_found(self, db_session):
        """Test terminating a non-existent wallet."""
        repo = WalletRepository(db_session)
        assert repo.terminate(uuid4()) is None

    def test_update_balance(self, db_session, wallet):
        """Test adding credits/balance to a wallet."""
        repo = WalletRepository(db_session)
        updated = repo.update_balance(
            wallet.id,
            credits=Decimal("100.0000"),
            amount_cents=Decimal("10000.0000"),
        )
        assert updated is not None
        assert updated.credits_balance == Decimal("100.0000")
        assert updated.balance_cents == Decimal("10000.0000")

        # Add more
        updated = repo.update_balance(
            wallet.id,
            credits=Decimal("50.0000"),
            amount_cents=Decimal("5000.0000"),
        )
        assert updated.credits_balance == Decimal("150.0000")
        assert updated.balance_cents == Decimal("15000.0000")

    def test_update_balance_not_found(self, db_session):
        """Test updating balance of a non-existent wallet."""
        repo = WalletRepository(db_session)
        assert repo.update_balance(uuid4(), Decimal("100"), Decimal("10000")) is None

    def test_deduct_balance(self, db_session, wallet):
        """Test deducting credits/balance from a wallet."""
        repo = WalletRepository(db_session)
        # First add some credits
        repo.update_balance(wallet.id, Decimal("100.0000"), Decimal("10000.0000"))

        # Now deduct
        updated = repo.deduct_balance(
            wallet.id,
            credits=Decimal("30.0000"),
            amount_cents=Decimal("3000.0000"),
        )
        assert updated is not None
        assert updated.credits_balance == Decimal("70.0000")
        assert updated.balance_cents == Decimal("7000.0000")
        assert updated.consumed_credits == Decimal("30.0000")
        assert updated.consumed_amount_cents == Decimal("3000.0000")

    def test_deduct_balance_accumulates_consumed(self, db_session, wallet):
        """Test that consumed amounts accumulate across multiple deductions."""
        repo = WalletRepository(db_session)
        repo.update_balance(wallet.id, Decimal("200.0000"), Decimal("20000.0000"))

        repo.deduct_balance(wallet.id, Decimal("50.0000"), Decimal("5000.0000"))
        repo.deduct_balance(wallet.id, Decimal("30.0000"), Decimal("3000.0000"))

        fetched = repo.get_by_id(wallet.id)
        assert fetched.consumed_credits == Decimal("80.0000")
        assert fetched.consumed_amount_cents == Decimal("8000.0000")
        assert fetched.credits_balance == Decimal("120.0000")
        assert fetched.balance_cents == Decimal("12000.0000")

    def test_deduct_balance_not_found(self, db_session):
        """Test deducting balance from a non-existent wallet."""
        repo = WalletRepository(db_session)
        assert repo.deduct_balance(uuid4(), Decimal("10"), Decimal("1000")) is None

    def test_get_all_different_customers(self, db_session, customer, customer2):
        """Test filtering wallets by different customers."""
        repo = WalletRepository(db_session)
        repo.create(WalletCreate(customer_id=customer.id, name="C1W1", code="c1w1"))
        repo.create(WalletCreate(customer_id=customer2.id, name="C2W1", code="c2w1"))

        c1_wallets = repo.get_all(customer_id=customer.id)
        assert len(c1_wallets) == 1
        assert c1_wallets[0].name == "C1W1"

        c2_wallets = repo.get_all(customer_id=customer2.id)
        assert len(c2_wallets) == 1
        assert c2_wallets[0].name == "C2W1"


class TestWalletSchema:
    """Tests for Wallet Pydantic schemas."""

    def test_wallet_create_defaults(self):
        """Test WalletCreate default values."""
        schema = WalletCreate(customer_id=uuid4())
        assert schema.name is None
        assert schema.code is None
        assert schema.rate_amount == Decimal("1")
        assert schema.currency == "USD"
        assert schema.expiration_at is None
        assert schema.priority == 1
        assert schema.initial_granted_credits is None

    def test_wallet_create_full(self):
        """Test WalletCreate with all fields."""
        cid = uuid4()
        expiry = datetime.now(UTC) + timedelta(days=30)
        schema = WalletCreate(
            customer_id=cid,
            name="Premium",
            code="premium",
            rate_amount=Decimal("2.5"),
            currency="EUR",
            expiration_at=expiry,
            priority=5,
            initial_granted_credits=Decimal("100"),
        )
        assert schema.customer_id == cid
        assert schema.name == "Premium"
        assert schema.rate_amount == Decimal("2.5")
        assert schema.initial_granted_credits == Decimal("100")

    def test_wallet_create_priority_bounds(self):
        """Test WalletCreate priority validation."""
        from pydantic import ValidationError

        # Valid bounds
        WalletCreate(customer_id=uuid4(), priority=1)
        WalletCreate(customer_id=uuid4(), priority=50)

        # Out of bounds
        with pytest.raises(ValidationError):
            WalletCreate(customer_id=uuid4(), priority=0)
        with pytest.raises(ValidationError):
            WalletCreate(customer_id=uuid4(), priority=51)

    def test_wallet_create_rate_amount_positive(self):
        """Test that rate_amount must be positive."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            WalletCreate(customer_id=uuid4(), rate_amount=Decimal("0"))
        with pytest.raises(ValidationError):
            WalletCreate(customer_id=uuid4(), rate_amount=Decimal("-1"))

    def test_wallet_update_partial(self):
        """Test WalletUpdate with partial data."""
        schema = WalletUpdate(name="Updated")
        dumped = schema.model_dump(exclude_unset=True)
        assert "name" in dumped
        assert "priority" not in dumped
        assert "expiration_at" not in dumped

    def test_wallet_response_from_attributes(self, db_session, customer):
        """Test WalletResponse can serialize from ORM object."""
        from app.schemas.wallet import WalletResponse

        wallet = Wallet(customer_id=customer.id, name="Test")
        db_session.add(wallet)
        db_session.commit()
        db_session.refresh(wallet)

        response = WalletResponse.model_validate(wallet)
        assert response.id == wallet.id
        assert response.name == "Test"
        assert response.status == "active"
        assert response.balance_cents == Decimal("0")

    def test_wallet_top_up_schema_validation(self):
        """Test WalletTopUp schema validation."""
        from pydantic import ValidationError

        from app.schemas.wallet import WalletTopUp

        # Valid
        topup = WalletTopUp(credits=Decimal("10"), source="manual")
        assert topup.credits == Decimal("10")
        assert topup.source == "manual"

        # Valid sources
        WalletTopUp(credits=Decimal("10"), source="interval")
        WalletTopUp(credits=Decimal("10"), source="threshold")

        # Invalid: zero credits
        with pytest.raises(ValidationError):
            WalletTopUp(credits=Decimal("0"))

        # Invalid: negative credits
        with pytest.raises(ValidationError):
            WalletTopUp(credits=Decimal("-5"))

        # Invalid: bad source
        with pytest.raises(ValidationError):
            WalletTopUp(credits=Decimal("10"), source="invalid_source")

    def test_wallet_create_initial_credits_non_negative(self):
        """Test that initial_granted_credits must be non-negative."""
        from pydantic import ValidationError

        # Valid: zero
        WalletCreate(customer_id=uuid4(), initial_granted_credits=Decimal("0"))

        # Invalid: negative
        with pytest.raises(ValidationError):
            WalletCreate(customer_id=uuid4(), initial_granted_credits=Decimal("-1"))


class TestWalletAPI:
    """Tests for Wallet API endpoints."""

    def test_create_wallet(self, client, db_session, customer):
        """Test POST /v1/wallets/ creates a wallet."""
        response = client.post("/v1/wallets/", json={
            "customer_id": str(customer.id),
            "name": "API Wallet",
            "code": "api-wallet",
            "rate_amount": "2.5",
            "currency": "EUR",
            "priority": 5,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "API Wallet"
        assert data["code"] == "api-wallet"
        assert data["rate_amount"] == "2.5000"
        assert data["currency"] == "EUR"
        assert data["priority"] == 5
        assert data["status"] == "active"
        assert data["balance_cents"] == "0.0000"
        assert data["credits_balance"] == "0.0000"

    def test_create_wallet_with_initial_credits(self, client, db_session, customer):
        """Test POST /v1/wallets/ with initial granted credits."""
        response = client.post("/v1/wallets/", json={
            "customer_id": str(customer.id),
            "name": "Funded Wallet",
            "code": "funded-api",
            "rate_amount": "100",
            "initial_granted_credits": "50",
        })
        assert response.status_code == 201
        data = response.json()
        assert Decimal(data["credits_balance"]) == Decimal("50.0000")
        assert Decimal(data["balance_cents"]) == Decimal("5000.0000")

    def test_create_wallet_minimal(self, client, db_session, customer):
        """Test POST /v1/wallets/ with only required fields."""
        response = client.post("/v1/wallets/", json={
            "customer_id": str(customer.id),
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] is None
        assert data["code"] is None
        assert data["rate_amount"] == "1.0000"
        assert data["currency"] == "USD"
        assert data["priority"] == 1

    def test_create_wallet_invalid_priority(self, client, db_session, customer):
        """Test POST /v1/wallets/ with invalid priority."""
        response = client.post("/v1/wallets/", json={
            "customer_id": str(customer.id),
            "priority": 0,
        })
        assert response.status_code == 422

        response = client.post("/v1/wallets/", json={
            "customer_id": str(customer.id),
            "priority": 51,
        })
        assert response.status_code == 422

    def test_create_wallet_duplicate_code(self, client, db_session, customer):
        """Test POST /v1/wallets/ returns 400 for duplicate code on same customer."""
        response = client.post("/v1/wallets/", json={
            "customer_id": str(customer.id),
            "name": "First",
            "code": "dup-code",
        })
        assert response.status_code == 201

        response = client.post("/v1/wallets/", json={
            "customer_id": str(customer.id),
            "name": "Second",
            "code": "dup-code",
        })
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_list_wallets(self, client, db_session, customer):
        """Test GET /v1/wallets/ lists wallets."""
        repo = WalletRepository(db_session)
        repo.create(WalletCreate(customer_id=customer.id, name="W1", code="w1"))
        repo.create(WalletCreate(customer_id=customer.id, name="W2", code="w2"))

        response = client.get("/v1/wallets/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_wallets_filter_by_customer(self, client, db_session, customer, customer2):
        """Test GET /v1/wallets/ filtered by customer_id."""
        repo = WalletRepository(db_session)
        repo.create(WalletCreate(customer_id=customer.id, name="C1W", code="c1w"))
        repo.create(WalletCreate(customer_id=customer2.id, name="C2W", code="c2w"))

        response = client.get(f"/v1/wallets/?customer_id={customer.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "C1W"

    def test_list_wallets_filter_by_status(self, client, db_session, customer):
        """Test GET /v1/wallets/ filtered by status."""
        repo = WalletRepository(db_session)
        repo.create(WalletCreate(customer_id=customer.id, name="Active", code="active-f"))
        w2 = repo.create(WalletCreate(customer_id=customer.id, name="Term", code="term-f"))
        repo.terminate(w2.id)

        response = client.get("/v1/wallets/?status=active")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Active"

        response = client.get("/v1/wallets/?status=terminated")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Term"

    def test_list_wallets_empty(self, client):
        """Test GET /v1/wallets/ returns empty list."""
        response = client.get("/v1/wallets/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_wallets_pagination(self, client, db_session, customer):
        """Test GET /v1/wallets/ with pagination."""
        repo = WalletRepository(db_session)
        for i in range(5):
            repo.create(WalletCreate(customer_id=customer.id, name=f"W{i}", code=f"w-pag-{i}"))

        response = client.get("/v1/wallets/?skip=2&limit=2")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_get_wallet(self, client, db_session, wallet):
        """Test GET /v1/wallets/{id} returns wallet details."""
        response = client.get(f"/v1/wallets/{wallet.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(wallet.id)
        assert data["name"] == "Test Wallet"
        assert data["code"] == "test-wallet"
        assert data["status"] == "active"

    def test_get_wallet_not_found(self, client):
        """Test GET /v1/wallets/{id} returns 404 for non-existent wallet."""
        response = client.get(f"/v1/wallets/{uuid4()}")
        assert response.status_code == 404

    def test_update_wallet(self, client, db_session, wallet):
        """Test PUT /v1/wallets/{id} updates wallet."""
        response = client.put(f"/v1/wallets/{wallet.id}", json={
            "name": "Updated Name",
            "priority": 10,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["priority"] == 10

    def test_update_wallet_partial(self, client, db_session, wallet):
        """Test PUT /v1/wallets/{id} with partial update."""
        response = client.put(f"/v1/wallets/{wallet.id}", json={
            "name": "Only Name",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Only Name"
        assert data["priority"] == 1  # unchanged

    def test_update_wallet_not_found(self, client):
        """Test PUT /v1/wallets/{id} returns 404."""
        response = client.put(f"/v1/wallets/{uuid4()}", json={
            "name": "Nope",
        })
        assert response.status_code == 404

    def test_terminate_wallet(self, client, db_session, wallet):
        """Test DELETE /v1/wallets/{id} terminates wallet."""
        response = client.delete(f"/v1/wallets/{wallet.id}")
        assert response.status_code == 204

        # Verify terminated
        get_response = client.get(f"/v1/wallets/{wallet.id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "terminated"

    def test_terminate_wallet_not_found(self, client):
        """Test DELETE /v1/wallets/{id} returns 404."""
        response = client.delete(f"/v1/wallets/{uuid4()}")
        assert response.status_code == 404

    def test_terminate_already_terminated(self, client, db_session, wallet):
        """Test DELETE /v1/wallets/{id} returns 400 when already terminated."""
        client.delete(f"/v1/wallets/{wallet.id}")
        response = client.delete(f"/v1/wallets/{wallet.id}")
        assert response.status_code == 400

    def test_top_up_wallet(self, client, db_session, wallet):
        """Test POST /v1/wallets/{id}/top_up adds credits."""
        response = client.post(f"/v1/wallets/{wallet.id}/top_up", json={
            "credits": "50",
        })
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["credits_balance"]) == Decimal("50.0000")
        assert Decimal(data["balance_cents"]) == Decimal("50.0000")  # rate=1

    def test_top_up_wallet_with_source(self, client, db_session, wallet):
        """Test POST /v1/wallets/{id}/top_up with specific source."""
        response = client.post(f"/v1/wallets/{wallet.id}/top_up", json={
            "credits": "25",
            "source": "interval",
        })
        assert response.status_code == 200
        assert Decimal(response.json()["credits_balance"]) == Decimal("25.0000")

    def test_top_up_wallet_not_found(self, client):
        """Test POST /v1/wallets/{id}/top_up returns 400 for non-existent wallet."""
        response = client.post(f"/v1/wallets/{uuid4()}/top_up", json={
            "credits": "50",
        })
        assert response.status_code == 400

    def test_top_up_terminated_wallet(self, client, db_session, wallet):
        """Test POST /v1/wallets/{id}/top_up returns 400 for terminated wallet."""
        client.delete(f"/v1/wallets/{wallet.id}")
        response = client.post(f"/v1/wallets/{wallet.id}/top_up", json={
            "credits": "50",
        })
        assert response.status_code == 400

    def test_top_up_invalid_credits(self, client, db_session, wallet):
        """Test POST /v1/wallets/{id}/top_up rejects zero/negative credits."""
        response = client.post(f"/v1/wallets/{wallet.id}/top_up", json={
            "credits": "0",
        })
        assert response.status_code == 422

        response = client.post(f"/v1/wallets/{wallet.id}/top_up", json={
            "credits": "-10",
        })
        assert response.status_code == 422

    def test_list_wallet_transactions(self, client, db_session, customer, wallet):
        """Test GET /v1/wallets/{id}/transactions lists transactions."""
        # Top up to generate a transaction
        from app.services.wallet_service import WalletService
        service = WalletService(db_session)
        service.top_up_wallet(wallet.id, Decimal("100"))

        response = client.get(f"/v1/wallets/{wallet.id}/transactions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["transaction_type"] == "inbound"
        assert Decimal(data[0]["amount"]) == Decimal("100.0000")

    def test_list_wallet_transactions_empty(self, client, db_session, wallet):
        """Test GET /v1/wallets/{id}/transactions returns empty list."""
        response = client.get(f"/v1/wallets/{wallet.id}/transactions")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_wallet_transactions_not_found(self, client):
        """Test GET /v1/wallets/{id}/transactions returns 404 for non-existent wallet."""
        response = client.get(f"/v1/wallets/{uuid4()}/transactions")
        assert response.status_code == 404

    def test_list_wallet_transactions_pagination(self, client, db_session, customer, wallet):
        """Test GET /v1/wallets/{id}/transactions with pagination."""
        from app.services.wallet_service import WalletService
        service = WalletService(db_session)
        for _ in range(5):
            service.top_up_wallet(wallet.id, Decimal("10"))

        response = client.get(f"/v1/wallets/{wallet.id}/transactions?skip=1&limit=2")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_wallet_expiration_in_response(self, client, db_session, customer):
        """Test that expiration_at is properly returned in API response."""
        expiry = (datetime.now(UTC) + timedelta(days=30)).isoformat()
        response = client.post("/v1/wallets/", json={
            "customer_id": str(customer.id),
            "name": "Expiring",
            "code": "expiring-api",
            "expiration_at": expiry,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["expiration_at"] is not None

    def test_wallet_priority_ordering_in_list(self, client, db_session, customer):
        """Test that wallets are returned ordered by created_at DESC in list endpoint."""
        repo = WalletRepository(db_session)
        repo.create(WalletCreate(customer_id=customer.id, name="P3", code="p3-api", priority=3))
        repo.create(WalletCreate(customer_id=customer.id, name="P1", code="p1-api", priority=1))
        repo.create(WalletCreate(customer_id=customer.id, name="P2", code="p2-api", priority=2))

        response = client.get(f"/v1/wallets/?customer_id={customer.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
