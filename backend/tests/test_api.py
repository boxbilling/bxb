"""API tests for bxb."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db, init_db
from app.main import app
from app.repositories.item_repository import ItemRepository


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
        # Exhaust the generator to trigger cleanup
        for _ in gen:
            pass


class TestDashboardEndpoints:
    def test_get_stats(self, client: TestClient):
        response = client.get("/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_customers"] == 0
        assert data["active_subscriptions"] == 0
        assert data["monthly_recurring_revenue"] == 0.0
        assert data["total_invoiced"] == 0.0
        assert data["currency"] == "USD"

    def test_get_activity_empty(self, client: TestClient):
        response = client.get("/dashboard/activity")
        assert response.status_code == 200
        assert response.json() == []


class TestItemsAPI:
    def test_list_items_empty(self, client: TestClient):
        response = client.get("/items/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_item(self, client: TestClient):
        response = client.post(
            "/items/",
            json={"name": "Test Item", "price": 9.99, "quantity": 10},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Item"
        assert data["price"] == 9.99
        assert data["quantity"] == 10
        assert data["description"] is None
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_item_with_description(self, client: TestClient):
        response = client.post(
            "/items/",
            json={
                "name": "Described Item",
                "description": "A nice description",
                "price": 19.99,
                "quantity": 5,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["description"] == "A nice description"

    def test_get_item(self, client: TestClient):
        # Create item first
        create_response = client.post(
            "/items/",
            json={"name": "Get Test", "price": 5.00, "quantity": 1},
        )
        item_id = create_response.json()["id"]

        # Get the item
        response = client.get(f"/items/{item_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item_id
        assert data["name"] == "Get Test"

    def test_get_item_not_found(self, client: TestClient):
        response = client.get("/items/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Item not found"

    def test_update_item(self, client: TestClient):
        # Create item first
        create_response = client.post(
            "/items/",
            json={"name": "Update Test", "price": 10.00, "quantity": 1},
        )
        item_id = create_response.json()["id"]

        # Update the item
        response = client.put(
            f"/items/{item_id}",
            json={"name": "Updated Name", "price": 15.00},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["price"] == 15.00
        assert data["quantity"] == 1  # Unchanged

    def test_update_item_partial(self, client: TestClient):
        # Create item first
        create_response = client.post(
            "/items/",
            json={"name": "Partial Update", "price": 20.00, "quantity": 10},
        )
        item_id = create_response.json()["id"]

        # Update only quantity
        response = client.put(f"/items/{item_id}", json={"quantity": 50})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Partial Update"  # Unchanged
        assert data["price"] == 20.00  # Unchanged
        assert data["quantity"] == 50  # Updated

    def test_update_item_not_found(self, client: TestClient):
        response = client.put("/items/99999", json={"name": "Ghost"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Item not found"

    def test_delete_item(self, client: TestClient):
        # Create item first
        create_response = client.post(
            "/items/",
            json={"name": "Delete Test", "price": 1.00, "quantity": 1},
        )
        item_id = create_response.json()["id"]

        # Delete the item
        response = client.delete(f"/items/{item_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/items/{item_id}")
        assert get_response.status_code == 404

    def test_delete_item_not_found(self, client: TestClient):
        response = client.delete("/items/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Item not found"

    def test_list_items_pagination(self, client: TestClient):
        # Create multiple items
        for i in range(5):
            client.post(
                "/items/",
                json={"name": f"Item {i}", "price": float(i), "quantity": i},
            )

        # Test pagination
        response = client.get("/items/?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_enqueue_update_prices(self, client: TestClient):
        """Test the enqueue_update_prices endpoint with mocked arq."""
        mock_job = MagicMock()
        mock_job.job_id = "test-job-123"

        with patch("app.routers.items.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = mock_job

            response = client.post("/items/update-prices")
            assert response.status_code == 202
            data = response.json()
            assert data["job_id"] == "test-job-123"
            mock_enqueue.assert_called_once_with("update_item_prices")


class TestItemRepository:
    def test_apply_bulk_discount(self, db_session):
        """Test apply_bulk_discount method."""
        repo = ItemRepository(db_session)

        # Create items with different quantities
        from app.schemas.item import ItemCreate

        repo.create(ItemCreate(name="Low Qty", price=100.0, quantity=50))
        repo.create(ItemCreate(name="High Qty 1", price=100.0, quantity=150))
        repo.create(ItemCreate(name="High Qty 2", price=200.0, quantity=200))

        # Apply 10% discount to items with quantity > 100
        count = repo.apply_bulk_discount(min_quantity=100, discount=0.1)

        assert count == 2

        # Verify prices were updated
        items = repo.get_all()
        low_qty = next(i for i in items if i.name == "Low Qty")
        high_qty_1 = next(i for i in items if i.name == "High Qty 1")
        high_qty_2 = next(i for i in items if i.name == "High Qty 2")

        assert low_qty.price == 100.0  # Unchanged
        assert high_qty_1.price == 90.0  # 10% off
        assert high_qty_2.price == 180.0  # 10% off

    def test_apply_bulk_discount_no_matches(self, db_session):
        """Test apply_bulk_discount when no items match criteria."""
        repo = ItemRepository(db_session)

        from app.schemas.item import ItemCreate

        repo.create(ItemCreate(name="Low Qty", price=100.0, quantity=50))

        count = repo.apply_bulk_discount(min_quantity=100, discount=0.1)
        assert count == 0


class TestDatabase:
    def test_init_db(self):
        """Test init_db function creates tables idempotently."""
        from sqlalchemy import inspect

        from app.core.database import engine

        # Call init_db (tables already exist from fixture — verifies idempotency)
        init_db()

        # Verify tables exist
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "items" in tables
