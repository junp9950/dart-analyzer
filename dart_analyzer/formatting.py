from __future__ import annotations


def fmt_amount(v: float | None) -> str:
    if v is None:
        return "-"
    if abs(v) >= 1e8:
        return f"{v/1e8:,.0f}억"
    return f"{v:,.0f}"
