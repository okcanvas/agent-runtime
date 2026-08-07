from __future__ import annotations

from .pricing import calculate_total


def order_summary(lines: list[dict[str, int]]) -> dict[str, int]:
    return {"line_count": len(lines), "total": calculate_total(lines)}
