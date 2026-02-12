"""Unit tests for charge model calculators."""

from decimal import Decimal

from app.models.charge import ChargeModel
from app.services.charge_models import (
    custom,
    dynamic,
    graduated,
    graduated_percentage,
    package,
    percentage,
    standard,
    volume,
)
from app.services.charge_models.factory import get_charge_calculator


class TestStandardCalculator:
    def test_basic_multiplication(self):
        """Test standard calculation: units * amount."""
        result = standard.calculate(Decimal("10"), {"amount": "5"})
        assert result == Decimal("50")

    def test_zero_units(self):
        """Test with zero units returns zero."""
        result = standard.calculate(Decimal("0"), {"amount": "100"})
        assert result == Decimal("0")

    def test_zero_price(self):
        """Test with zero price returns zero."""
        result = standard.calculate(Decimal("100"), {"amount": "0"})
        assert result == Decimal("0")

    def test_amount_property_key(self):
        """Test using 'amount' property key."""
        result = standard.calculate(Decimal("3"), {"amount": "10.50"})
        assert result == Decimal("31.50")

    def test_unit_price_property_key(self):
        """Test using 'unit_price' property key."""
        result = standard.calculate(Decimal("3"), {"unit_price": "10.50"})
        assert result == Decimal("31.50")

    def test_amount_takes_precedence_over_unit_price(self):
        """Test that 'amount' key takes precedence when both are present."""
        result = standard.calculate(Decimal("1"), {"amount": "5", "unit_price": "10"})
        assert result == Decimal("5")

    def test_no_price_key_defaults_to_zero(self):
        """Test with no price key defaults to 0."""
        result = standard.calculate(Decimal("100"), {})
        assert result == Decimal("0")

    def test_decimal_precision(self):
        """Test decimal precision is maintained."""
        result = standard.calculate(Decimal("7"), {"amount": "0.0033"})
        assert result == Decimal("0.0231")


class TestGraduatedCalculator:
    def test_single_tier_lago_format(self):
        """Test graduated with a single open-ended tier (Lago format)."""
        result = graduated.calculate(
            Decimal("100"),
            {
                "graduated_ranges": [
                    {
                        "from_value": 0,
                        "to_value": None,
                        "per_unit_amount": "1.00",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        assert result == Decimal("100.00")

    def test_multiple_tiers_lago_format(self):
        """Test graduated across multiple tiers (Lago format)."""
        result = graduated.calculate(
            Decimal("150"),
            {
                "graduated_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 100,
                        "per_unit_amount": "1.00",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 100,
                        "to_value": None,
                        "per_unit_amount": "0.50",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        # First 101 units (0-100 inclusive) at $1 = $101, remaining 49 at $0.50 = $24.50
        assert result == Decimal("125.50")

    def test_flat_fees_per_tier_lago_format(self):
        """Test graduated with flat fees per tier (Lago format)."""
        result = graduated.calculate(
            Decimal("150"),
            {
                "graduated_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 100,
                        "per_unit_amount": "1.00",
                        "flat_amount": "10",
                    },
                    {
                        "from_value": 100,
                        "to_value": None,
                        "per_unit_amount": "0.50",
                        "flat_amount": "5",
                    },
                ]
            },
        )
        # First tier: 101 * $1 + $10 = $111, second tier: 49 * $0.50 + $5 = $29.50
        assert result == Decimal("140.50")

    def test_open_ended_final_tier_lago_format(self):
        """Test that open-ended final tier (to_value=None) handles large values."""
        result = graduated.calculate(
            Decimal("10000"),
            {
                "graduated_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 10,
                        "per_unit_amount": "2.00",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 10,
                        "to_value": None,
                        "per_unit_amount": "1.00",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        # First 11 units at $2 = $22, remaining 9989 at $1 = $9989
        assert result == Decimal("10011")

    def test_zero_units(self):
        """Test graduated with zero units."""
        result = graduated.calculate(
            Decimal("0"),
            {
                "graduated_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 100,
                        "per_unit_amount": "1.00",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        assert result == Decimal("0")

    def test_bxb_format_single_tier(self):
        """Test graduated with bxb tiers format - single tier."""
        result = graduated.calculate(
            Decimal("50"),
            {
                "tiers": [
                    {"up_to": 100, "unit_price": "2.00"},
                ]
            },
        )
        assert result == Decimal("100.00")

    def test_bxb_format_multiple_tiers(self):
        """Test graduated with bxb tiers format - multiple tiers."""
        result = graduated.calculate(
            Decimal("150"),
            {
                "tiers": [
                    {"up_to": 100, "unit_price": "1.00"},
                    {"up_to": 500, "unit_price": "0.50"},
                ]
            },
        )
        # First 100 at $1 = $100, next 50 at $0.50 = $25
        assert result == Decimal("125.00")

    def test_empty_properties(self):
        """Test graduated with no tiers returns zero."""
        result = graduated.calculate(Decimal("100"), {})
        assert result == Decimal("0")

    def test_units_in_tier_zero_skip(self):
        """Test that tiers with zero capacity are skipped (Lago format)."""
        result = graduated.calculate(
            Decimal("5"),
            {
                "graduated_ranges": [
                    {"from_value": 0, "to_value": 5, "per_unit_amount": "1.00", "flat_amount": "0"},
                    {
                        "from_value": 5,
                        "to_value": 10,
                        "per_unit_amount": "2.00",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        # First tier: from_value=0, to_value=5, capacity=6, but only 5 units
        assert result == Decimal("5.00")

    def test_lago_format_zero_capacity_tier_continue(self):
        """Test that a tier with zero or negative capacity is skipped via continue."""
        # Create a tier where to_value < from_value, resulting in negative capacity
        result = graduated.calculate(
            Decimal("10"),
            {
                "graduated_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 5,
                        "per_unit_amount": "1.00",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 10,
                        "to_value": 8,
                        "per_unit_amount": "99.00",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 20,
                        "to_value": None,
                        "per_unit_amount": "2.00",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        # First tier: capacity = 5 - 0 + 1 = 6, uses 6 at $1 = $6, remaining = 4
        # Second tier: capacity = 8 - 10 + 1 = -1 → units_in_tier = min(4, -1) = -1 ≤ 0 → continue
        # Third tier: open-ended, uses remaining 4 at $2 = $8
        assert result == Decimal("14.00")

    def test_bxb_format_exact_units_consumed_break(self):
        """Test bxb format where units are exactly consumed triggering remaining<=0 break."""
        result = graduated.calculate(
            Decimal("100"),
            {
                "tiers": [
                    {"up_to": 100, "unit_price": "1.00"},
                    {"up_to": 200, "unit_price": "0.50"},
                ]
            },
        )
        # First 100 at $1 = $100, remaining = 0 → break before second tier
        assert result == Decimal("100.00")

    def test_bxb_format_overlapping_tiers_break(self):
        """Test bxb format where tier_usage <= 0 triggers break."""
        # This can happen when tiers overlap such that up_to - prev_limit <= 0
        result = graduated.calculate(
            Decimal("50"),
            {
                "tiers": [
                    {"up_to": 100, "unit_price": "1.00"},
                    {"up_to": 50, "unit_price": "2.00"},
                ]
            },
        )
        # After sorting: up_to=50 first (price $2), up_to=100 second (price $1)
        # First tier: min(50, 50 - 0) = 50 at $2 = $100, remaining = 0
        # Second tier: remaining <= 0 → break
        assert result == Decimal("100.00")

    def test_bxb_format_duplicate_up_to_tier_usage_zero_break(self):
        """Test bxb format where duplicate up_to values cause tier_usage <= 0 break."""
        result = graduated.calculate(
            Decimal("200"),
            {
                "tiers": [
                    {"up_to": 100, "unit_price": "1.00"},
                    {"up_to": 100, "unit_price": "2.00"},
                    {"up_to": 500, "unit_price": "0.50"},
                ]
            },
        )
        # After sorting: both up_to=100 come first, then up_to=500
        # First tier: min(200, 100 - 0) = 100 at $1 = $100, remaining = 100, prev_limit = 100
        # Second tier: tier_usage = min(100, 100 - 100) = 0 → break
        assert result == Decimal("100.00")


class TestVolumeCalculator:
    def test_falls_in_first_tier_lago_format(self):
        """Test volume when usage falls in the first tier (Lago format)."""
        result = volume.calculate(
            Decimal("50"),
            {
                "volume_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 100,
                        "per_unit_amount": "1.00",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 100,
                        "to_value": None,
                        "per_unit_amount": "0.50",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        assert result == Decimal("50.00")

    def test_falls_in_middle_tier_lago_format(self):
        """Test volume when usage falls in a middle tier (Lago format)."""
        result = volume.calculate(
            Decimal("150"),
            {
                "volume_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 100,
                        "per_unit_amount": "1.00",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 100,
                        "to_value": 500,
                        "per_unit_amount": "0.80",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 500,
                        "to_value": None,
                        "per_unit_amount": "0.50",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        # All 150 units at $0.80 (volume tier 2)
        assert result == Decimal("120.00")

    def test_falls_in_last_tier_lago_format(self):
        """Test volume when usage falls in the last open-ended tier (Lago format)."""
        result = volume.calculate(
            Decimal("1000"),
            {
                "volume_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 100,
                        "per_unit_amount": "1.00",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 100,
                        "to_value": None,
                        "per_unit_amount": "0.50",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        # All 1000 units at $0.50
        assert result == Decimal("500.00")

    def test_flat_amount_per_tier_lago_format(self):
        """Test volume with flat_amount added per tier (Lago format)."""
        result = volume.calculate(
            Decimal("50"),
            {
                "volume_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 100,
                        "per_unit_amount": "1.00",
                        "flat_amount": "10",
                    },
                ]
            },
        )
        # 50 * $1 + $10 flat
        assert result == Decimal("60.00")

    def test_bxb_format_first_tier(self):
        """Test volume with bxb tiers format - falls in first tier."""
        result = volume.calculate(
            Decimal("50"),
            {
                "tiers": [
                    {"up_to": 100, "unit_price": "1.00", "flat_amount": "0"},
                    {"up_to": 500, "unit_price": "0.50", "flat_amount": "0"},
                ]
            },
        )
        assert result == Decimal("50.00")

    def test_bxb_format_second_tier(self):
        """Test volume with bxb tiers format - falls in second tier."""
        result = volume.calculate(
            Decimal("200"),
            {
                "tiers": [
                    {"up_to": 100, "unit_price": "1.00", "flat_amount": "0"},
                    {"up_to": 500, "unit_price": "0.50", "flat_amount": "0"},
                ]
            },
        )
        # All 200 units at $0.50
        assert result == Decimal("100.00")

    def test_exceeds_all_tiers_lago_format(self):
        """Test volume when usage exceeds all defined tiers (Lago format, no open-ended)."""
        result = volume.calculate(
            Decimal("200"),
            {
                "volume_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 50,
                        "per_unit_amount": "2.00",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 50,
                        "to_value": 100,
                        "per_unit_amount": "1.00",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        # Falls through all tiers, last tier used: 200 * $1
        assert result == Decimal("200.00")

    def test_exceeds_all_tiers_bxb_format(self):
        """Test volume when usage exceeds all defined tiers (bxb format)."""
        result = volume.calculate(
            Decimal("200"),
            {
                "tiers": [
                    {"up_to": 50, "unit_price": "2.00", "flat_amount": "0"},
                    {"up_to": 100, "unit_price": "1.00", "flat_amount": "0"},
                ]
            },
        )
        # Falls through all tiers, last tier used: 200 * $1
        assert result == Decimal("200.00")

    def test_empty_properties(self):
        """Test volume with no tiers returns zero."""
        result = volume.calculate(Decimal("100"), {})
        assert result == Decimal("0")

    def test_bxb_format_with_flat_amount(self):
        """Test volume with bxb tiers format including flat_amount."""
        result = volume.calculate(
            Decimal("50"),
            {
                "tiers": [
                    {"up_to": 100, "unit_price": "1.00", "flat_amount": "15"},
                ]
            },
        )
        # 50 * $1 + $15 flat
        assert result == Decimal("65.00")


class TestPackageCalculator:
    def test_exact_package_boundary(self):
        """Test when usage exactly fills packages."""
        result = package.calculate(
            Decimal("100"),
            {"amount": "10", "package_size": "50"},
        )
        # 100 / 50 = 2 packages * $10 = $20
        assert result == Decimal("20")

    def test_partial_package_rounds_up(self):
        """Test that partial packages are rounded up."""
        result = package.calculate(
            Decimal("101"),
            {"amount": "10", "package_size": "50"},
        )
        # ceil(101 / 50) = 3 packages * $10 = $30
        assert result == Decimal("30")

    def test_free_units(self):
        """Test that free_units are subtracted before calculation."""
        result = package.calculate(
            Decimal("150"),
            {"amount": "10", "package_size": "50", "free_units": "100"},
        )
        # billable = 150 - 100 = 50, 50 / 50 = 1 package * $10 = $10
        assert result == Decimal("10")

    def test_zero_usage(self):
        """Test with zero units returns zero."""
        result = package.calculate(
            Decimal("0"),
            {"amount": "10", "package_size": "50"},
        )
        assert result == Decimal("0")

    def test_usage_within_free_units(self):
        """Test when usage is within free units threshold."""
        result = package.calculate(
            Decimal("50"),
            {"amount": "10", "package_size": "100", "free_units": "100"},
        )
        assert result == Decimal("0")

    def test_package_size_one(self):
        """Test with package_size=1 acts like per-unit pricing."""
        result = package.calculate(
            Decimal("7"),
            {"amount": "3", "package_size": "1"},
        )
        # 7 / 1 = 7 packages * $3 = $21
        assert result == Decimal("21")

    def test_unit_price_property_key(self):
        """Test using 'unit_price' property key instead of 'amount'."""
        result = package.calculate(
            Decimal("100"),
            {"unit_price": "5", "package_size": "25"},
        )
        # 100 / 25 = 4 packages * $5 = $20
        assert result == Decimal("20")

    def test_single_unit_partial_package(self):
        """Test that a single unit still counts as one package."""
        result = package.calculate(
            Decimal("1"),
            {"amount": "100", "package_size": "1000"},
        )
        # ceil(1 / 1000) = 1 package * $100 = $100
        assert result == Decimal("100")


class TestPercentageCalculator:
    def test_basic_rate(self):
        """Test basic percentage rate on total amount."""
        result = percentage.calculate(
            Decimal("0"),
            {"rate": "2.5"},
            total_amount=Decimal("1000"),
        )
        # 1000 * 2.5% = $25
        assert result == Decimal("25.0")

    def test_percentage_property_key(self):
        """Test using 'percentage' property key instead of 'rate'."""
        result = percentage.calculate(
            Decimal("0"),
            {"percentage": "3"},
            total_amount=Decimal("500"),
        )
        # 500 * 3% = $15
        assert result == Decimal("15")

    def test_with_fixed_amount_per_transaction(self):
        """Test percentage with fixed_amount per billable event."""
        result = percentage.calculate(
            Decimal("0"),
            {"rate": "2", "fixed_amount": "0.25"},
            total_amount=Decimal("100"),
            event_count=10,
        )
        # percentage_fee = 100 * 2% = $2, fixed_fees = 10 * $0.25 = $2.50
        assert result == Decimal("4.50")

    def test_free_units_per_events(self):
        """Test that free_units_per_events subtracts free events."""
        result = percentage.calculate(
            Decimal("0"),
            {"rate": "0", "fixed_amount": "1", "free_units_per_events": "5"},
            total_amount=Decimal("0"),
            event_count=10,
        )
        # billable_events = 10 - 5 = 5, fixed_fees = 5 * $1 = $5
        assert result == Decimal("5")

    def test_min_per_transaction_bound(self):
        """Test that per_transaction_min_amount is enforced."""
        result = percentage.calculate(
            Decimal("0"),
            {"rate": "1", "per_transaction_min_amount": "50"},
            total_amount=Decimal("100"),
        )
        # percentage_fee = 100 * 1% = $1, min = $50 → $50
        assert result == Decimal("50")

    def test_max_per_transaction_bound(self):
        """Test that per_transaction_max_amount is enforced."""
        result = percentage.calculate(
            Decimal("0"),
            {"rate": "10", "per_transaction_max_amount": "5"},
            total_amount=Decimal("1000"),
        )
        # percentage_fee = 1000 * 10% = $100, max = $5 → $5
        assert result == Decimal("5")

    def test_zero_amount(self):
        """Test with zero total_amount."""
        result = percentage.calculate(
            Decimal("0"),
            {"rate": "5"},
            total_amount=Decimal("0"),
        )
        assert result == Decimal("0")

    def test_min_not_applied_when_above(self):
        """Test min bound is not applied when total is already above it."""
        result = percentage.calculate(
            Decimal("0"),
            {"rate": "10", "per_transaction_min_amount": "5"},
            total_amount=Decimal("1000"),
        )
        # percentage_fee = 1000 * 10% = $100, min = $5 → stays $100
        assert result == Decimal("100")

    def test_max_not_applied_when_below(self):
        """Test max bound is not applied when total is already below it."""
        result = percentage.calculate(
            Decimal("0"),
            {"rate": "1", "per_transaction_max_amount": "500"},
            total_amount=Decimal("100"),
        )
        # percentage_fee = 100 * 1% = $1, max = $500 → stays $1
        assert result == Decimal("1")

    def test_free_events_exceeds_event_count(self):
        """Test when free events exceeds total event count."""
        result = percentage.calculate(
            Decimal("0"),
            {"rate": "0", "fixed_amount": "1", "free_units_per_events": "100"},
            total_amount=Decimal("0"),
            event_count=10,
        )
        # billable_events = max(0, 10 - 100) = 0, fixed_fees = 0
        assert result == Decimal("0")

    def test_both_min_and_max_bounds(self):
        """Test with both min and max bounds, total within range."""
        result = percentage.calculate(
            Decimal("0"),
            {"rate": "5", "per_transaction_min_amount": "10", "per_transaction_max_amount": "100"},
            total_amount=Decimal("1000"),
        )
        # percentage_fee = 1000 * 5% = $50, within [10, 100] → $50
        assert result == Decimal("50")


class TestGraduatedPercentageCalculator:
    def test_single_tier(self):
        """Test graduated percentage with a single open-ended tier."""
        result = graduated_percentage.calculate(
            Decimal("1000"),
            {
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": None, "rate": "2", "flat_amount": "0"},
                ]
            },
        )
        # 1000 * 2% = $20
        assert result == Decimal("20")

    def test_multiple_tiers(self):
        """Test graduated percentage across multiple tiers."""
        result = graduated_percentage.calculate(
            Decimal("1500"),
            {
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 1000, "rate": "2", "flat_amount": "0"},
                    {"from_value": 1000, "to_value": None, "rate": "1", "flat_amount": "0"},
                ]
            },
        )
        # First $1000 at 2% = $20, next $500 at 1% = $5
        assert result == Decimal("25")

    def test_flat_fees_per_tier(self):
        """Test graduated percentage with flat fees on each tier."""
        result = graduated_percentage.calculate(
            Decimal("1500"),
            {
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 1000, "rate": "2", "flat_amount": "5"},
                    {"from_value": 1000, "to_value": None, "rate": "1", "flat_amount": "3"},
                ]
            },
        )
        # First $1000: 1000 * 2% + $5 = $25, next $500: 500 * 1% + $3 = $8
        assert result == Decimal("33")

    def test_open_ended_final_tier(self):
        """Test that open-ended final tier handles large amounts."""
        result = graduated_percentage.calculate(
            Decimal("100000"),
            {
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 1000, "rate": "3", "flat_amount": "0"},
                    {"from_value": 1000, "to_value": 10000, "rate": "2", "flat_amount": "0"},
                    {"from_value": 10000, "to_value": None, "rate": "1", "flat_amount": "0"},
                ]
            },
        )
        # First $1000: 1000 * 3% = $30
        # Next $9000: 9000 * 2% = $180
        # Remaining $90000: 90000 * 1% = $900
        assert result == Decimal("1110")

    def test_empty_ranges(self):
        """Test graduated percentage with no ranges returns zero."""
        result = graduated_percentage.calculate(
            Decimal("1000"),
            {"graduated_percentage_ranges": []},
        )
        assert result == Decimal("0")

    def test_missing_ranges_key(self):
        """Test graduated percentage with missing key returns zero."""
        result = graduated_percentage.calculate(Decimal("1000"), {})
        assert result == Decimal("0")

    def test_zero_amount(self):
        """Test graduated percentage with zero total amount."""
        result = graduated_percentage.calculate(
            Decimal("0"),
            {
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": None, "rate": "5", "flat_amount": "0"},
                ]
            },
        )
        assert result == Decimal("0")

    def test_amount_exactly_at_tier_boundary(self):
        """Test graduated percentage when amount exactly matches tier boundary."""
        result = graduated_percentage.calculate(
            Decimal("1000"),
            {
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 1000, "rate": "2", "flat_amount": "0"},
                    {"from_value": 1000, "to_value": None, "rate": "1", "flat_amount": "0"},
                ]
            },
        )
        # All $1000 at 2% = $20, nothing in second tier
        assert result == Decimal("20")

    def test_zero_capacity_tier_continue(self):
        """Test tier with zero capacity (from_value == to_value) is skipped via continue."""
        result = graduated_percentage.calculate(
            Decimal("500"),
            {
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 100, "rate": "2", "flat_amount": "0"},
                    {
                        "from_value": 100,
                        "to_value": 100,
                        "rate": "5",
                        "flat_amount": "0",
                    },
                    {"from_value": 100, "to_value": None, "rate": "1", "flat_amount": "0"},
                ]
            },
        )
        # First $100: 100 * 2% = $2, remaining = 400
        # Second tier: capacity = 100 - 100 = 0 → portion = 0 → continue
        # Third tier: 400 * 1% = $4
        assert result == Decimal("6")


class TestCustomCalculator:
    def test_custom_amount_fixed(self):
        """Test custom charge with a fixed custom_amount."""
        result = custom.calculate(Decimal("10"), {"custom_amount": "250"})
        assert result == Decimal("250")

    def test_custom_unit_price(self):
        """Test custom charge with per-unit pricing."""
        result = custom.calculate(Decimal("5"), {"unit_price": "10"})
        assert result == Decimal("50")

    def test_custom_no_properties(self):
        """Test custom charge with no relevant properties returns zero."""
        result = custom.calculate(Decimal("100"), {})
        assert result == Decimal("0")

    def test_custom_amount_takes_precedence(self):
        """Test that custom_amount takes precedence over unit_price."""
        result = custom.calculate(
            Decimal("10"), {"custom_amount": "99", "unit_price": "5"}
        )
        assert result == Decimal("99")

    def test_custom_zero_units(self):
        """Test custom charge with zero units and unit_price."""
        result = custom.calculate(Decimal("0"), {"unit_price": "50"})
        assert result == Decimal("0")

    def test_custom_decimal_precision(self):
        """Test custom charge maintains decimal precision."""
        result = custom.calculate(Decimal("3"), {"unit_price": "0.0033"})
        assert result == Decimal("0.0099")


class TestDynamicCalculator:
    def test_basic_dynamic_pricing(self):
        """Test dynamic pricing from event properties."""
        events = [
            {"unit_price": "10", "quantity": "2"},
            {"unit_price": "5", "quantity": "3"},
        ]
        result = dynamic.calculate(events=events, properties={})
        # 10*2 + 5*3 = 20 + 15 = 35
        assert result == Decimal("35")

    def test_custom_field_names(self):
        """Test dynamic pricing with custom field names."""
        events = [
            {"price": "100", "qty": "1"},
            {"price": "50", "qty": "4"},
        ]
        result = dynamic.calculate(
            events=events,
            properties={"price_field": "price", "quantity_field": "qty"},
        )
        # 100*1 + 50*4 = 100 + 200 = 300
        assert result == Decimal("300")

    def test_no_events(self):
        """Test dynamic pricing with no events returns zero."""
        result = dynamic.calculate(events=[], properties={})
        assert result == Decimal("0")

    def test_missing_fields_default_to_zero(self):
        """Test that missing event fields default to zero."""
        events = [
            {"unit_price": "10"},  # missing quantity
            {"quantity": "5"},  # missing unit_price
        ]
        result = dynamic.calculate(events=events, properties={})
        # 10*0 + 0*5 = 0
        assert result == Decimal("0")

    def test_single_event(self):
        """Test dynamic pricing with a single event."""
        events = [{"unit_price": "25.50", "quantity": "2"}]
        result = dynamic.calculate(events=events, properties={})
        assert result == Decimal("51.00")

    def test_decimal_precision(self):
        """Test dynamic pricing maintains decimal precision."""
        events = [{"unit_price": "0.001", "quantity": "1000"}]
        result = dynamic.calculate(events=events, properties={})
        assert result == Decimal("1.000")


class TestFactory:
    def test_returns_standard_calculator(self):
        """Test factory returns correct calculator for STANDARD."""
        calc = get_charge_calculator(ChargeModel.STANDARD)
        assert calc is standard.calculate

    def test_returns_graduated_calculator(self):
        """Test factory returns correct calculator for GRADUATED."""
        calc = get_charge_calculator(ChargeModel.GRADUATED)
        assert calc is graduated.calculate

    def test_returns_volume_calculator(self):
        """Test factory returns correct calculator for VOLUME."""
        calc = get_charge_calculator(ChargeModel.VOLUME)
        assert calc is volume.calculate

    def test_returns_package_calculator(self):
        """Test factory returns correct calculator for PACKAGE."""
        calc = get_charge_calculator(ChargeModel.PACKAGE)
        assert calc is package.calculate

    def test_returns_percentage_calculator(self):
        """Test factory returns correct calculator for PERCENTAGE."""
        calc = get_charge_calculator(ChargeModel.PERCENTAGE)
        assert calc is percentage.calculate

    def test_returns_graduated_percentage_calculator(self):
        """Test factory returns correct calculator for GRADUATED_PERCENTAGE."""
        calc = get_charge_calculator(ChargeModel.GRADUATED_PERCENTAGE)
        assert calc is graduated_percentage.calculate

    def test_returns_custom_calculator(self):
        """Test factory returns correct calculator for CUSTOM."""
        calc = get_charge_calculator(ChargeModel.CUSTOM)
        assert calc is custom.calculate

    def test_returns_dynamic_calculator(self):
        """Test factory returns correct calculator for DYNAMIC."""
        calc = get_charge_calculator(ChargeModel.DYNAMIC)
        assert calc is dynamic.calculate

    def test_returns_none_for_unknown_model(self):
        """Test factory returns None for an unknown model."""
        result = get_charge_calculator("nonexistent_model")
        assert result is None

    def test_calculators_are_callable(self):
        """Test all returned calculators are callable."""
        for model in ChargeModel:
            calc = get_charge_calculator(model)
            assert callable(calc), f"Calculator for {model} is not callable"
