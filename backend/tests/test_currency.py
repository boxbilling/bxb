from app.models.currency import CurrencyCode


class TestCurrencyCode:
    def test_currency_code_is_str_enum(self):
        """Test CurrencyCode members are strings."""
        assert isinstance(CurrencyCode.USD, str)
        assert CurrencyCode.USD == "USD"
        assert CurrencyCode.USD.value == "USD"

    def test_common_currencies(self):
        """Test common currency code values."""
        assert CurrencyCode.EUR.value == "EUR"
        assert CurrencyCode.GBP.value == "GBP"
        assert CurrencyCode.JPY.value == "JPY"
        assert CurrencyCode.CAD.value == "CAD"
        assert CurrencyCode.CHF.value == "CHF"
        assert CurrencyCode.AUD.value == "AUD"
        assert CurrencyCode.CNY.value == "CNY"
        assert CurrencyCode.INR.value == "INR"

    def test_total_currency_count(self):
        """Test the total number of supported currencies."""
        assert len(CurrencyCode) == 138

    def test_all_values_are_three_letter_codes(self):
        """Test all currency codes are 3-letter uppercase strings."""
        for code in CurrencyCode:
            assert len(code.value) == 3
            assert code.value == code.value.upper()
            assert code.value.isalpha()

    def test_name_matches_value(self):
        """Test enum name matches its value for all members."""
        for code in CurrencyCode:
            assert code.name == code.value

    def test_lookup_by_value(self):
        """Test currency codes can be looked up by string value."""
        assert CurrencyCode("USD") == CurrencyCode.USD
        assert CurrencyCode("EUR") == CurrencyCode.EUR

    def test_invalid_currency_raises(self):
        """Test that invalid currency code raises ValueError."""
        import pytest

        with pytest.raises(ValueError):
            CurrencyCode("INVALID")
