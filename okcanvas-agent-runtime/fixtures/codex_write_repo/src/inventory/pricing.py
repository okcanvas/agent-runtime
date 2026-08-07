from __future__ import annotations


def calculate_total(lines: list[dict[str, int]]) -> int:
    """Return an order total in Korean won."""
    return sum(line["unit_price"] for line in lines)
