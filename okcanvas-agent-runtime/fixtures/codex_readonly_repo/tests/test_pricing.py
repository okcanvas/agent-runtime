from inventory.pricing import calculate_total


def test_quantity_is_applied_to_each_line() -> None:
    lines = [
        {"unit_price": 10_000, "quantity": 2},
        {"unit_price": 5_000, "quantity": 1},
    ]
    assert calculate_total(lines) == 25_000
