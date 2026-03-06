"""Cart math helpers — no ML dependencies."""

from __future__ import annotations


def get_cart_total(cart: list[dict]) -> tuple[float, float, float]:
    """Returns (subtotal, tax, grand_total) for the current cart."""
    subtotal = sum(i["unit_price"] * i["quantity"] for i in cart)
    tax      = sum(
        i["unit_price"] * i["quantity"] * i.get("tax_rate", 5.0) / 100
        for i in cart
    )
    return subtotal, tax, round(subtotal + tax, 2)


def format_cart_total(cart: list[dict]) -> str:
    _, _, total = get_cart_total(cart)
    return f"₹{total:.0f}"
