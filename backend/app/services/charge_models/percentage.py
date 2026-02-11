from decimal import Decimal


def calculate(
    units: Decimal,
    properties: dict,
    total_amount: Decimal = Decimal("0"),
    event_count: int = 0,
) -> Decimal:
    rate = Decimal(str(properties.get("rate", properties.get("percentage", 0))))
    fixed_amount = Decimal(str(properties.get("fixed_amount", 0)))
    free_events = int(properties.get("free_units_per_events", 0))
    per_tx_min = properties.get("per_transaction_min_amount")
    per_tx_max = properties.get("per_transaction_max_amount")

    # Calculate percentage fee on total amount
    percentage_fee = total_amount * (rate / Decimal(100))

    # Calculate fixed fees for billable events
    billable_events = max(0, event_count - free_events)
    fixed_fees = Decimal(str(billable_events)) * fixed_amount

    total = percentage_fee + fixed_fees

    # Apply per-transaction min/max bounds
    if per_tx_min is not None:
        min_amount = Decimal(str(per_tx_min))
        if total < min_amount:
            total = min_amount

    if per_tx_max is not None:
        max_amount = Decimal(str(per_tx_max))
        if total > max_amount:
            total = max_amount

    return total
