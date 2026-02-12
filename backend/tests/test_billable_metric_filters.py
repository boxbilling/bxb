"""Tests for BillableMetricFilter, ChargeFilter, and ChargeFilterValue models, schemas, and repositories."""

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models.billable_metric import AggregationType, BillableMetric
from app.models.billable_metric_filter import BillableMetricFilter
from app.models.charge import Charge, ChargeModel
from app.models.charge_filter import ChargeFilter
from app.models.charge_filter_value import ChargeFilterValue
from app.models.plan import Plan, PlanInterval
from app.repositories.billable_metric_filter_repository import BillableMetricFilterRepository
from app.repositories.charge_filter_repository import ChargeFilterRepository
from app.schemas.billable_metric_filter import (
    BillableMetricFilterCreate,
    BillableMetricFilterResponse,
)
from app.schemas.charge_filter import (
    ChargeFilterCreate,
    ChargeFilterResponse,
    ChargeFilterValueCreate,
    ChargeFilterValueResponse,
)


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
def sample_metric(db_session):
    """Create a sample billable metric."""
    metric = BillableMetric(
        code="api_calls",
        name="API Calls",
        aggregation_type=AggregationType.COUNT.value,
    )
    db_session.add(metric)
    db_session.commit()
    db_session.refresh(metric)
    return metric


@pytest.fixture
def sample_plan(db_session):
    """Create a sample plan."""
    plan = Plan(
        code="basic",
        name="Basic Plan",
        interval=PlanInterval.MONTHLY.value,
        amount_cents=1000,
        currency="USD",
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


@pytest.fixture
def sample_charge(db_session, sample_plan, sample_metric):
    """Create a sample charge."""
    charge = Charge(
        plan_id=sample_plan.id,
        billable_metric_id=sample_metric.id,
        charge_model=ChargeModel.STANDARD.value,
        properties={"amount": "10"},
    )
    db_session.add(charge)
    db_session.commit()
    db_session.refresh(charge)
    return charge


@pytest.fixture
def sample_metric_filter(db_session, sample_metric):
    """Create a sample billable metric filter."""
    metric_filter = BillableMetricFilter(
        billable_metric_id=sample_metric.id,
        key="region",
        values=["us-east", "eu-west", "ap-south"],
    )
    db_session.add(metric_filter)
    db_session.commit()
    db_session.refresh(metric_filter)
    return metric_filter


class TestBillableMetricFilterModel:
    def test_create_filter(self, db_session, sample_metric):
        """Test creating a billable metric filter."""
        metric_filter = BillableMetricFilter(
            billable_metric_id=sample_metric.id,
            key="region",
            values=["us-east", "eu-west"],
        )
        db_session.add(metric_filter)
        db_session.commit()
        db_session.refresh(metric_filter)

        assert metric_filter.id is not None
        assert metric_filter.billable_metric_id == sample_metric.id
        assert metric_filter.key == "region"
        assert metric_filter.values == ["us-east", "eu-west"]
        assert metric_filter.created_at is not None
        assert metric_filter.updated_at is not None

    def test_default_values(self, db_session, sample_metric):
        """Test default values for filter."""
        metric_filter = BillableMetricFilter(
            billable_metric_id=sample_metric.id,
            key="tier",
        )
        db_session.add(metric_filter)
        db_session.commit()
        db_session.refresh(metric_filter)

        assert metric_filter.id is not None
        assert metric_filter.created_at is not None

    def test_unique_constraint_metric_key(self, db_session, sample_metric):
        """Test composite unique constraint on (billable_metric_id, key)."""
        f1 = BillableMetricFilter(
            billable_metric_id=sample_metric.id,
            key="region",
            values=["us-east"],
        )
        db_session.add(f1)
        db_session.commit()

        f2 = BillableMetricFilter(
            billable_metric_id=sample_metric.id,
            key="region",
            values=["eu-west"],
        )
        db_session.add(f2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_different_keys_same_metric(self, db_session, sample_metric):
        """Test that different keys on the same metric are allowed."""
        f1 = BillableMetricFilter(
            billable_metric_id=sample_metric.id,
            key="region",
            values=["us-east"],
        )
        f2 = BillableMetricFilter(
            billable_metric_id=sample_metric.id,
            key="tier",
            values=["free", "pro"],
        )
        db_session.add_all([f1, f2])
        db_session.commit()

        filters = (
            db_session.query(BillableMetricFilter)
            .filter(BillableMetricFilter.billable_metric_id == sample_metric.id)
            .all()
        )
        assert len(filters) == 2

    def test_foreign_key_to_metric(self, db_session, sample_metric):
        """Test that the filter references its parent metric correctly."""
        metric_filter = BillableMetricFilter(
            billable_metric_id=sample_metric.id,
            key="region",
            values=["us-east"],
        )
        db_session.add(metric_filter)
        db_session.commit()
        db_session.refresh(metric_filter)

        assert metric_filter.billable_metric_id == sample_metric.id


class TestChargeFilterModel:
    def test_create_charge_filter(self, db_session, sample_charge):
        """Test creating a charge filter."""
        cf = ChargeFilter(
            charge_id=sample_charge.id,
            properties={"amount": "20"},
            invoice_display_name="US East API Calls",
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        assert cf.id is not None
        assert cf.charge_id == sample_charge.id
        assert cf.properties == {"amount": "20"}
        assert cf.invoice_display_name == "US East API Calls"
        assert cf.created_at is not None
        assert cf.updated_at is not None

    def test_nullable_invoice_display_name(self, db_session, sample_charge):
        """Test that invoice_display_name is nullable."""
        cf = ChargeFilter(
            charge_id=sample_charge.id,
            properties={"amount": "15"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        assert cf.invoice_display_name is None

    def test_multiple_filters_per_charge(self, db_session, sample_charge):
        """Test that multiple filters can be associated with a charge."""
        cf1 = ChargeFilter(
            charge_id=sample_charge.id,
            properties={"amount": "20"},
            invoice_display_name="Filter 1",
        )
        cf2 = ChargeFilter(
            charge_id=sample_charge.id,
            properties={"amount": "30"},
            invoice_display_name="Filter 2",
        )
        db_session.add_all([cf1, cf2])
        db_session.commit()

        filters = (
            db_session.query(ChargeFilter).filter(ChargeFilter.charge_id == sample_charge.id).all()
        )
        assert len(filters) == 2


class TestChargeFilterValueModel:
    def test_create_charge_filter_value(self, db_session, sample_charge, sample_metric_filter):
        """Test creating a charge filter value."""
        cf = ChargeFilter(
            charge_id=sample_charge.id,
            properties={"amount": "20"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=sample_metric_filter.id,
            value="us-east",
        )
        db_session.add(cfv)
        db_session.commit()
        db_session.refresh(cfv)

        assert cfv.id is not None
        assert cfv.charge_filter_id == cf.id
        assert cfv.billable_metric_filter_id == sample_metric_filter.id
        assert cfv.value == "us-east"
        assert cfv.created_at is not None

    def test_unique_constraint(self, db_session, sample_charge, sample_metric_filter):
        """Test unique constraint on (charge_filter_id, billable_metric_filter_id)."""
        cf = ChargeFilter(
            charge_id=sample_charge.id,
            properties={"amount": "20"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv1 = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=sample_metric_filter.id,
            value="us-east",
        )
        db_session.add(cfv1)
        db_session.commit()

        cfv2 = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=sample_metric_filter.id,
            value="eu-west",
        )
        db_session.add(cfv2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_foreign_key_references(self, db_session, sample_charge, sample_metric_filter):
        """Test that charge filter value correctly references both parents."""
        cf = ChargeFilter(
            charge_id=sample_charge.id,
            properties={"amount": "20"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=sample_metric_filter.id,
            value="us-east",
        )
        db_session.add(cfv)
        db_session.commit()
        db_session.refresh(cfv)

        assert cfv.charge_filter_id == cf.id
        assert cfv.billable_metric_filter_id == sample_metric_filter.id


class TestBillableMetricFilterSchema:
    def test_create_schema(self):
        """Test BillableMetricFilterCreate schema."""
        schema = BillableMetricFilterCreate(
            key="region",
            values=["us-east", "eu-west"],
        )
        assert schema.key == "region"
        assert schema.values == ["us-east", "eu-west"]

    def test_create_schema_default_values(self):
        """Test BillableMetricFilterCreate with default values list."""
        schema = BillableMetricFilterCreate(key="tier")
        assert schema.values == []

    def test_create_schema_empty_key_rejected(self):
        """Test that empty key is rejected."""
        with pytest.raises(ValidationError):
            BillableMetricFilterCreate(key="")

    def test_response_schema(self):
        """Test BillableMetricFilterResponse schema."""
        data = {
            "id": uuid.uuid4(),
            "billable_metric_id": uuid.uuid4(),
            "key": "region",
            "values": ["us-east"],
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        response = BillableMetricFilterResponse(**data)
        assert response.key == "region"
        assert response.values == ["us-east"]

    def test_response_schema_from_attributes(self, db_session, sample_metric):
        """Test BillableMetricFilterResponse with from_attributes."""
        metric_filter = BillableMetricFilter(
            billable_metric_id=sample_metric.id,
            key="region",
            values=["us-east", "eu-west"],
        )
        db_session.add(metric_filter)
        db_session.commit()
        db_session.refresh(metric_filter)

        response = BillableMetricFilterResponse.model_validate(metric_filter)
        assert response.key == "region"
        assert response.billable_metric_id == sample_metric.id


class TestChargeFilterSchema:
    def test_create_schema(self):
        """Test ChargeFilterCreate schema."""
        schema = ChargeFilterCreate(
            properties={"amount": "20"},
            invoice_display_name="US East",
            values=[
                ChargeFilterValueCreate(
                    billable_metric_filter_id=uuid.uuid4(),
                    value="us-east",
                )
            ],
        )
        assert schema.properties == {"amount": "20"}
        assert schema.invoice_display_name == "US East"
        assert len(schema.values) == 1

    def test_create_schema_defaults(self):
        """Test ChargeFilterCreate defaults."""
        schema = ChargeFilterCreate()
        assert schema.properties == {}
        assert schema.invoice_display_name is None
        assert schema.values == []

    def test_value_create_schema(self):
        """Test ChargeFilterValueCreate schema."""
        filter_id = uuid.uuid4()
        schema = ChargeFilterValueCreate(
            billable_metric_filter_id=filter_id,
            value="us-east",
        )
        assert schema.billable_metric_filter_id == filter_id
        assert schema.value == "us-east"

    def test_value_create_empty_value_rejected(self):
        """Test that empty value is rejected."""
        with pytest.raises(ValidationError):
            ChargeFilterValueCreate(
                billable_metric_filter_id=uuid.uuid4(),
                value="",
            )

    def test_response_schema(self):
        """Test ChargeFilterResponse schema."""
        data = {
            "id": uuid.uuid4(),
            "charge_id": uuid.uuid4(),
            "properties": {"amount": "20"},
            "invoice_display_name": "US East",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        response = ChargeFilterResponse(**data)
        assert response.properties == {"amount": "20"}
        assert response.invoice_display_name == "US East"

    def test_response_schema_from_attributes(self, db_session, sample_charge):
        """Test ChargeFilterResponse with from_attributes."""
        cf = ChargeFilter(
            charge_id=sample_charge.id,
            properties={"amount": "20"},
            invoice_display_name="Test",
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        response = ChargeFilterResponse.model_validate(cf)
        assert response.charge_id == sample_charge.id
        assert response.invoice_display_name == "Test"

    def test_value_response_schema(self):
        """Test ChargeFilterValueResponse schema."""
        data = {
            "id": uuid.uuid4(),
            "charge_filter_id": uuid.uuid4(),
            "billable_metric_filter_id": uuid.uuid4(),
            "value": "us-east",
            "created_at": "2026-01-01T00:00:00",
        }
        response = ChargeFilterValueResponse(**data)
        assert response.value == "us-east"

    def test_value_response_schema_from_attributes(
        self, db_session, sample_charge, sample_metric_filter
    ):
        """Test ChargeFilterValueResponse with from_attributes."""
        cf = ChargeFilter(
            charge_id=sample_charge.id,
            properties={"amount": "20"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=sample_metric_filter.id,
            value="us-east",
        )
        db_session.add(cfv)
        db_session.commit()
        db_session.refresh(cfv)

        response = ChargeFilterValueResponse.model_validate(cfv)
        assert response.value == "us-east"
        assert response.charge_filter_id == cf.id


class TestBillableMetricFilterRepository:
    def test_create(self, db_session, sample_metric):
        """Test creating a filter via repository."""
        repo = BillableMetricFilterRepository(db_session)
        data = BillableMetricFilterCreate(
            key="region",
            values=["us-east", "eu-west"],
        )
        result = repo.create(sample_metric.id, data)

        assert result.id is not None
        assert result.billable_metric_id == sample_metric.id
        assert result.key == "region"
        assert result.values == ["us-east", "eu-west"]

    def test_get_by_id(self, db_session, sample_metric):
        """Test getting a filter by ID."""
        repo = BillableMetricFilterRepository(db_session)
        data = BillableMetricFilterCreate(key="region", values=["us-east"])
        created = repo.create(sample_metric.id, data)

        found = repo.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id
        assert found.key == "region"

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent filter returns None."""
        repo = BillableMetricFilterRepository(db_session)
        result = repo.get_by_id(uuid.uuid4())
        assert result is None

    def test_get_by_metric_id(self, db_session, sample_metric):
        """Test getting filters by metric ID."""
        repo = BillableMetricFilterRepository(db_session)
        repo.create(sample_metric.id, BillableMetricFilterCreate(key="region", values=["us-east"]))
        repo.create(
            sample_metric.id, BillableMetricFilterCreate(key="tier", values=["free", "pro"])
        )

        filters = repo.get_by_metric_id(sample_metric.id)
        assert len(filters) == 2
        keys = {f.key for f in filters}
        assert keys == {"region", "tier"}

    def test_get_by_metric_id_empty(self, db_session):
        """Test getting filters for a metric with none."""
        repo = BillableMetricFilterRepository(db_session)
        filters = repo.get_by_metric_id(uuid.uuid4())
        assert filters == []

    def test_delete(self, db_session, sample_metric):
        """Test deleting a filter."""
        repo = BillableMetricFilterRepository(db_session)
        data = BillableMetricFilterCreate(key="region", values=["us-east"])
        created = repo.create(sample_metric.id, data)

        result = repo.delete(created.id)
        assert result is True

        found = repo.get_by_id(created.id)
        assert found is None

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent filter."""
        repo = BillableMetricFilterRepository(db_session)
        result = repo.delete(uuid.uuid4())
        assert result is False


class TestChargeFilterRepository:
    def test_create(self, db_session, sample_charge, sample_metric_filter):
        """Test creating a charge filter with values."""
        repo = ChargeFilterRepository(db_session)
        data = ChargeFilterCreate(
            properties={"amount": "20"},
            invoice_display_name="US East",
            values=[
                ChargeFilterValueCreate(
                    billable_metric_filter_id=sample_metric_filter.id,
                    value="us-east",
                )
            ],
        )
        result = repo.create(sample_charge.id, data)

        assert result.id is not None
        assert result.charge_id == sample_charge.id
        assert result.properties == {"amount": "20"}
        assert result.invoice_display_name == "US East"

        # Verify filter values were created
        values = repo.get_filter_values(result.id)
        assert len(values) == 1
        assert values[0].value == "us-east"

    def test_create_without_values(self, db_session, sample_charge):
        """Test creating a charge filter without values."""
        repo = ChargeFilterRepository(db_session)
        data = ChargeFilterCreate(
            properties={"amount": "15"},
        )
        result = repo.create(sample_charge.id, data)

        assert result.id is not None
        values = repo.get_filter_values(result.id)
        assert len(values) == 0

    def test_get_by_id(self, db_session, sample_charge):
        """Test getting a charge filter by ID."""
        repo = ChargeFilterRepository(db_session)
        data = ChargeFilterCreate(properties={"amount": "20"})
        created = repo.create(sample_charge.id, data)

        found = repo.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent charge filter."""
        repo = ChargeFilterRepository(db_session)
        result = repo.get_by_id(uuid.uuid4())
        assert result is None

    def test_get_by_charge_id(self, db_session, sample_charge):
        """Test getting charge filters by charge ID."""
        repo = ChargeFilterRepository(db_session)
        repo.create(sample_charge.id, ChargeFilterCreate(properties={"amount": "20"}))
        repo.create(sample_charge.id, ChargeFilterCreate(properties={"amount": "30"}))

        filters = repo.get_by_charge_id(sample_charge.id)
        assert len(filters) == 2

    def test_get_by_charge_id_empty(self, db_session):
        """Test getting charge filters for a charge with none."""
        repo = ChargeFilterRepository(db_session)
        filters = repo.get_by_charge_id(uuid.uuid4())
        assert filters == []

    def test_get_filter_values(self, db_session, sample_charge, sample_metric_filter):
        """Test getting filter values for a charge filter."""
        repo = ChargeFilterRepository(db_session)
        data = ChargeFilterCreate(
            properties={"amount": "20"},
            values=[
                ChargeFilterValueCreate(
                    billable_metric_filter_id=sample_metric_filter.id,
                    value="us-east",
                )
            ],
        )
        created = repo.create(sample_charge.id, data)

        values = repo.get_filter_values(created.id)
        assert len(values) == 1
        assert values[0].billable_metric_filter_id == sample_metric_filter.id
        assert values[0].value == "us-east"

    def test_get_matching_filter(self, db_session, sample_charge, sample_metric_filter):
        """Test finding a matching charge filter based on event properties."""
        repo = ChargeFilterRepository(db_session)

        # Create charge filter for us-east region
        data = ChargeFilterCreate(
            properties={"amount": "20"},
            values=[
                ChargeFilterValueCreate(
                    billable_metric_filter_id=sample_metric_filter.id,
                    value="us-east",
                )
            ],
        )
        repo.create(sample_charge.id, data)

        # Match event properties
        result = repo.get_matching_filter(sample_charge.id, {"region": "us-east"})
        assert result is not None
        assert result.properties == {"amount": "20"}

    def test_get_matching_filter_no_match(self, db_session, sample_charge, sample_metric_filter):
        """Test that non-matching event properties return None."""
        repo = ChargeFilterRepository(db_session)

        data = ChargeFilterCreate(
            properties={"amount": "20"},
            values=[
                ChargeFilterValueCreate(
                    billable_metric_filter_id=sample_metric_filter.id,
                    value="us-east",
                )
            ],
        )
        repo.create(sample_charge.id, data)

        result = repo.get_matching_filter(sample_charge.id, {"region": "eu-west"})
        assert result is None

    def test_get_matching_filter_no_filters(self, db_session, sample_charge):
        """Test matching when charge has no filters."""
        repo = ChargeFilterRepository(db_session)
        result = repo.get_matching_filter(sample_charge.id, {"region": "us-east"})
        assert result is None

    def test_get_matching_filter_empty_values(self, db_session, sample_charge):
        """Test matching when charge filter has no values."""
        repo = ChargeFilterRepository(db_session)
        # Create a filter with no values
        repo.create(sample_charge.id, ChargeFilterCreate(properties={"amount": "20"}))

        result = repo.get_matching_filter(sample_charge.id, {"region": "us-east"})
        assert result is None

    def test_get_matching_filter_missing_property(
        self, db_session, sample_charge, sample_metric_filter
    ):
        """Test matching when event is missing the required property."""
        repo = ChargeFilterRepository(db_session)

        data = ChargeFilterCreate(
            properties={"amount": "20"},
            values=[
                ChargeFilterValueCreate(
                    billable_metric_filter_id=sample_metric_filter.id,
                    value="us-east",
                )
            ],
        )
        repo.create(sample_charge.id, data)

        result = repo.get_matching_filter(sample_charge.id, {"tier": "pro"})
        assert result is None

    def test_delete(self, db_session, sample_charge, sample_metric_filter):
        """Test deleting a charge filter and its values."""
        repo = ChargeFilterRepository(db_session)
        data = ChargeFilterCreate(
            properties={"amount": "20"},
            values=[
                ChargeFilterValueCreate(
                    billable_metric_filter_id=sample_metric_filter.id,
                    value="us-east",
                )
            ],
        )
        created = repo.create(sample_charge.id, data)

        result = repo.delete(created.id)
        assert result is True

        # Verify filter is gone
        assert repo.get_by_id(created.id) is None

        # Verify values are gone
        remaining_values = db_session.query(ChargeFilterValue).all()
        assert len(remaining_values) == 0

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent charge filter."""
        repo = ChargeFilterRepository(db_session)
        result = repo.delete(uuid.uuid4())
        assert result is False

    def test_multiple_filters_matching(self, db_session, sample_metric):
        """Test with multiple metric filters and charge filters."""
        # Create a second metric filter for tier
        tier_filter = BillableMetricFilter(
            billable_metric_id=sample_metric.id,
            key="tier",
            values=["free", "pro"],
        )
        db_session.add(tier_filter)
        db_session.commit()
        db_session.refresh(tier_filter)

        region_filter = BillableMetricFilter(
            billable_metric_id=sample_metric.id,
            key="region",
            values=["us-east", "eu-west"],
        )
        db_session.add(region_filter)
        db_session.commit()
        db_session.refresh(region_filter)

        # Create plan and charge
        plan = Plan(
            code="multi_filter",
            name="Multi Filter Plan",
            interval=PlanInterval.MONTHLY.value,
            amount_cents=2000,
            currency="USD",
        )
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=sample_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        repo = ChargeFilterRepository(db_session)

        # Create charge filter matching us-east + pro
        data = ChargeFilterCreate(
            properties={"amount": "25"},
            values=[
                ChargeFilterValueCreate(
                    billable_metric_filter_id=region_filter.id,
                    value="us-east",
                ),
                ChargeFilterValueCreate(
                    billable_metric_filter_id=tier_filter.id,
                    value="pro",
                ),
            ],
        )
        repo.create(charge.id, data)

        # Match with both properties
        result = repo.get_matching_filter(charge.id, {"region": "us-east", "tier": "pro"})
        assert result is not None
        assert result.properties == {"amount": "25"}

        # Partial match should fail (missing tier)
        result = repo.get_matching_filter(charge.id, {"region": "us-east"})
        assert result is None

    def test_get_matching_filter_orphaned_metric_filter(
        self, db_session, sample_charge, sample_metric_filter
    ):
        """Test matching when the BillableMetricFilter has been deleted (orphaned reference)."""
        repo = ChargeFilterRepository(db_session)

        # Create a charge filter referencing the metric filter
        data = ChargeFilterCreate(
            properties={"amount": "20"},
            values=[
                ChargeFilterValueCreate(
                    billable_metric_filter_id=sample_metric_filter.id,
                    value="us-east",
                )
            ],
        )
        repo.create(sample_charge.id, data)

        # Delete the BillableMetricFilter directly, orphaning the ChargeFilterValue reference
        db_session.delete(sample_metric_filter)
        db_session.commit()

        # Matching should fail because the referenced BillableMetricFilter no longer exists
        result = repo.get_matching_filter(sample_charge.id, {"region": "us-east"})
        assert result is None
