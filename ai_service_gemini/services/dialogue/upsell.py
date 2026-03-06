"""
Upsell & Combo Recommendation Engine

Rule-based engine — no ML required.

When DB is connected, this will additionally query:
  - Popular pairings from order_items history (co-occurrence)
  - Active promotional bundles from a promotions table
  - Revenue-weighted recommendations from a sales_summary view

For now it uses static rules from prompts.UPSELL_MAP and prompts.COMBO_DEALS.
"""

from __future__ import annotations

from services.prompts import COMBO_DEALS, UPSELL_MAP


# ─── Upsell suggestion ────────────────────────────────────────────────────────

def get_upsell_suggestion(
    cart: list[dict],
    already_shown: list[str],
    menu_items: list[dict],
) -> str | None:
    """
    Return a upsell suggestion string, or None if nothing new to suggest.

    Priority:
    1. Combo deal that is partially satisfied and not yet suggested
    2. Single-item pairing from UPSELL_MAP

    Parameters
    ----------
    cart          : current cart (list of cart item dicts)
    already_shown : list of suggestion strings already shown this session
    menu_items    : active menu (to confirm the upsell target exists)
    """
    cart_names = {c["name"].lower() for c in cart}
    menu_names = {m["name"].lower(): m["name"] for m in menu_items}

    # 1. Check combos first (higher value)
    for combo in COMBO_DEALS:
        items_lower = [i.lower() for i in combo["items"]]
        present   = [i for i in items_lower if i in cart_names]
        missing   = [i for i in items_lower if i not in cart_names]
        if present and missing:
            # Suggest the first missing item that is on the menu
            for m in missing:
                canonical = menu_names.get(m)
                if canonical:
                    suggestion = (
                        f"Add {canonical} to complete the '{combo['name']}' "
                        f"and save ₹{combo['saving']}!"
                    )
                    if suggestion not in already_shown:
                        return suggestion

    # 2. Single-item pairings
    for trigger, suggestion_name in UPSELL_MAP:
        if trigger.lower() in cart_names:
            canonical = menu_names.get(suggestion_name.lower())
            if canonical and canonical.lower() not in cart_names:
                suggestion = f"Would you like to add {canonical}? It pairs great with {trigger}!"
                if suggestion not in already_shown:
                    return suggestion

    return None


# ─── Combo detection ──────────────────────────────────────────────────────────

def detect_active_combos(cart: list[dict]) -> list[dict]:
    """
    Return list of combos fully satisfied by the current cart.
    Used to display savings badge in the UI.
    """
    cart_names = {c["name"].lower() for c in cart}
    active = []
    for combo in COMBO_DEALS:
        if all(i.lower() in cart_names for i in combo["items"]):
            active.append({
                "name":        combo["name"],
                "saving":      combo["saving"],
                "description": combo["description"],
            })
    return active


# ─── Order summary ────────────────────────────────────────────────────────────

def build_order_summary(cart: list[dict], subtotal: float, tax: float, total: float) -> dict:
    """
    Build a structured order summary JSON — the final artefact before DB write.

    This is the canonical representation of a confirmed order. When the backend
    is integrated, this dict is what gets sent to the PoS / KOT pipeline.
    """
    combos = detect_active_combos(cart)
    combo_saving = sum(c["saving"] for c in combos)

    line_items = []
    for c in cart:
        mods = c.get("modifiers") or {}
        line_items.append({
            "product_id":   c["product_id"],
            "name":         c["name"],
            "quantity":     c["quantity"],
            "unit_price":   c["unit_price"],
            "tax_rate":     c.get("tax_rate", 5.0),
            "modifiers": {
                "size":        mods.get("size"),
                "spice_level": mods.get("spice_level"),
                "add_ons":     mods.get("add_ons", []),
                "notes":       mods.get("notes"),
            },
            "line_total":   round(c["unit_price"] * c["quantity"], 2),
        })

    return {
        "items":        line_items,
        "combos":       combos,
        "combo_saving": combo_saving,
        "subtotal":     round(subtotal, 2),
        "tax":          round(tax, 2),
        "total":        round(total, 2),
        "item_count":   sum(c["quantity"] for c in cart),
    }


# ─── DB integration stubs (active when asyncpg pool available) ────────────────

async def get_db_upsell_suggestion(
    cart: list[dict],
    already_shown: list[str],
    pool,  # asyncpg.Pool | None
) -> str | None:
    """
    TODO (DB integration): Query co-purchase frequency from order_items and
    return the top-N most frequently paired items not already in cart.

    SQL sketch:
        SELECT oi2.product_name, COUNT(*) AS freq
        FROM order_items oi1
        JOIN order_items oi2 ON oi1.order_id = oi2.order_id
          AND oi1.product_id != oi2.product_id
        WHERE oi1.product_name = ANY($1)
          AND oi2.product_name != ALL($2)
        GROUP BY oi2.product_name
        ORDER BY freq DESC
        LIMIT 3
    """
    # Falls back to rule-based until DB is integrated
    return None
