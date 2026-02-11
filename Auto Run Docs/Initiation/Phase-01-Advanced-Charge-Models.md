# Phase 01: Advanced Charge Models

This phase implements the 5 remaining charge models (graduated, volume, package, percentage, graduated_percentage) beyond the existing "standard" model. This is the highest-priority feature — it transforms bxb from a basic billing system into a flexible, production-grade pricing engine capable of handling real-world SaaS, API, and marketplace billing scenarios. The existing `ChargeModel` enum already includes `graduated`, `volume`, `package`, and `percentage`; this phase adds `graduated_percentage`, creates dedicated calculator services for each model, integrates them into invoice generation via a factory pattern, and ensures 100% test coverage.

## Context

- **Codebase**: Python 3.12+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2
- **Existing code**: `backend/app/models/charge.py` has `ChargeModel` enum with STANDARD, GRADUATED, VOLUME, PACKAGE, PERCENTAGE
- **Existing logic**: `backend/app/services/invoice_generation.py` has inline calculation for all 5 models in `_calculate_charge()`, plus `_calculate_tiered_amount()` and `_calculate_volume_amount()` helpers
- **Test command**: `cd backend && uv run pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100`
- **Lint command**: `cd backend && uv run ruff check app/ tests/ && cd backend && uv run ruff format app/ tests/`
- **Pattern**: Repository → Service → Router → Schema (Pydantic v2 `model_config = {"from_attributes": True}`)
- **Coverage**: 100% enforced, `app/worker.py` and `app/alembic/*` excluded

## Tasks

- [x] Add `GRADUATED_PERCENTAGE` to the `ChargeModel` enum in `backend/app/models/charge.py`:
  - Add `GRADUATED_PERCENTAGE = "graduated_percentage"` to the existing enum
  - The other 5 values (STANDARD, GRADUATED, VOLUME, PACKAGE, PERCENTAGE) already exist — do not duplicate them
  - **Note:** Also widened `charge_model` column from `String(20)` to `String(30)` in both model and migration to accommodate the 22-char value `"graduated_percentage"`

- [x] Create the charge model calculator services directory and all calculator modules. Each module should have a single `calculate()` function:
  - `backend/app/services/charge_models/__init__.py` (empty)
  - `backend/app/services/charge_models/standard.py` — `calculate(units: Decimal, properties: dict) -> Decimal`: returns `units * amount` where `amount` comes from `properties["amount"]` or `properties.get("unit_price", 0)`. Support both keys for backward compatibility with existing charges
  - `backend/app/services/charge_models/graduated.py` — `calculate(units: Decimal, properties: dict) -> Decimal`: tiered pricing where different tiers have different per-unit prices. Support two property formats: (a) Lago-style `graduated_ranges` with `from_value`, `to_value`, `per_unit_amount`, `flat_amount` and (b) existing bxb format `tiers` with `up_to`, `unit_price`. Iterate tiers in order, consuming units per tier, accumulating `(units_in_tier * per_unit) + flat_amount`
  - `backend/app/services/charge_models/volume.py` — `calculate(units: Decimal, properties: dict) -> Decimal`: ALL units priced at the single tier the total falls into. Support both `volume_ranges` (Lago-style) and `tiers` (existing bxb format). Find the tier containing total units, return `units * per_unit + flat_amount`
  - `backend/app/services/charge_models/package.py` — `calculate(units: Decimal, properties: dict) -> Decimal`: charge per package of units. Read `amount` (or `unit_price`), `package_size`, `free_units` from properties. Calculate `billable = max(0, units - free_units)`, `packages = ceil(billable / package_size)`, return `packages * amount`
  - `backend/app/services/charge_models/percentage.py` — `calculate(units: Decimal, properties: dict, total_amount: Decimal = Decimal("0"), event_count: int = 0) -> Decimal`: percentage of transaction amount. Read `rate` (or `percentage`), `fixed_amount`, `free_units_per_events`, `per_transaction_min_amount`, `per_transaction_max_amount` from properties. Calculate: `billable_events = max(0, event_count - free_events)`, `percentage_fee = total_amount * (rate/100)`, `fixed_fees = billable_events * fixed_amount`, apply min/max per-transaction bounds
  - `backend/app/services/charge_models/graduated_percentage.py` — `calculate(total_amount: Decimal, properties: dict) -> Decimal`: different percentage rate per tier of the total amount. Read `graduated_percentage_ranges` with `from_value`, `to_value`, `rate`, `flat_amount`. Iterate tiers, applying each rate to the portion of amount in that tier
  - `backend/app/services/charge_models/factory.py` — `get_charge_calculator(model: ChargeModel)` function that returns the appropriate calculate function from a dict mapping

- [ ] Refactor `backend/app/services/invoice_generation.py` to use the charge model factory instead of inline calculations:
  - Import `get_charge_calculator` from `app.services.charge_models.factory`
  - Replace the inline `if/elif` chain in `_calculate_charge()` with a call to the factory
  - For STANDARD: call `calculator(units=usage, properties=properties)` — also pass any `unit_price`/`amount` normalization
  - For GRADUATED: call `calculator(units=usage, properties=properties)` — replaces `_calculate_tiered_amount()`
  - For VOLUME: call `calculator(units=usage, properties=properties)` — replaces `_calculate_volume_amount()`
  - For PACKAGE: call `calculator(units=usage, properties=properties)`
  - For PERCENTAGE: call `calculator(units=usage, properties=properties, total_amount=..., event_count=...)`
  - For GRADUATED_PERCENTAGE: call `calculator(total_amount=usage_amount, properties=properties)`
  - Remove `_calculate_tiered_amount()` and `_calculate_volume_amount()` helper methods after migrating their logic to the dedicated modules
  - Keep the existing min_price/max_price logic for STANDARD model
  - Ensure the line item description, quantity, unit_price, and amount fields are still set correctly

- [ ] Write comprehensive unit tests for all charge model calculators in `backend/tests/test_charge_models.py`:
  - **Standard**: test basic multiplication, test zero units, test zero price, test both `amount` and `unit_price` property keys
  - **Graduated**: test single tier, test multiple tiers, test flat fees per tier, test open-ended final tier (to_value=None), test zero units, test both property formats (graduated_ranges and tiers)
  - **Volume**: test falls in first tier, test falls in middle tier, test falls in last tier, test flat amount per tier, test both property formats
  - **Package**: test exact package boundary, test partial package (rounds up), test free units, test zero usage, test package_size=1
  - **Percentage**: test basic rate, test with fixed_amount per transaction, test free_units_per_events, test min/max per-transaction bounds, test zero amount
  - **Graduated Percentage**: test single tier, test multiple tiers, test flat fees per tier, test open-ended final tier
  - **Factory**: test returns correct calculator for each ChargeModel enum value, test returns None for unknown model
  - Follow existing test patterns: use `pytest`, `TestClient(app)`, fixtures with `Base.metadata.create_all/drop_all`

- [ ] Run tests and fix any failures to maintain 100% coverage:
  - Run `cd backend && uv run pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100`
  - If any existing tests break due to the refactor, fix them
  - Ensure all new charge model code paths are covered
  - Run `cd backend && uv run ruff check app/ tests/` and `cd backend && uv run ruff format app/ tests/` to fix lint issues

- [ ] Write integration tests that verify end-to-end invoice generation with each charge model in `backend/tests/test_charge_model_integration.py`:
  - Create a plan with a graduated charge, subscribe a customer, send events, generate invoice, verify fee calculation matches expected graduated pricing
  - Create a plan with a volume charge, repeat flow, verify all units priced at the correct tier
  - Create a plan with a package charge, repeat flow, verify package rounding
  - Create a plan with a percentage charge, repeat flow, verify percentage + fixed fees
  - Create a plan with a graduated_percentage charge, verify tiered percentages
  - Use existing test helpers and fixtures from other test files as reference

- [ ] Run full test suite with coverage and lint one final time:
  - `cd backend && uv run ruff format app/ tests/`
  - `cd backend && uv run ruff check app/ tests/`
  - `cd backend && uv run pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100`
  - All 7 charge models (standard + 5 new + graduated_percentage) working end-to-end
