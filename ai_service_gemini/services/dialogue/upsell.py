"""
Upsell & Combo Recommendation Engine

Rule-based engine — no ML required.

Priority order for suggestions:
  1. Combo completion  — customer is 1 item away from completing a combo (highest value)
  2. DB upsell rules   — weight-sorted pairings from the upsell_rules table
  3. Combo-derived     — any two items that share a combo (generic fallback)

Uses DB-driven data (from fetch_active_combos / fetch_upsell_rules) passed at
call time. Falls back gracefully to an empty list if no data is available.
"""

from __future__ import annotations


# ─── Upsell suggestion ────────────────────────────────────────────────────────

def get_upsell_suggestion(
    cart: list[dict],
    already_shown: list[str],
    menu_items: list[dict],
    combo_deals: list[dict] | None = None,
    upsell_rules: list[dict] | None = None,
) -> str | None:
    """
    Return a upsell suggestion string, or None if nothing new to suggest.

    Priority
    --------
    1. Combo completion — 1 item missing from a combo the customer almost has
    2. DB upsell rules  — weight-sorted pairs (trigger_item → suggest_item)
    3. Combo-derived    — generic pairing from combo membership (fallback)

    Parameters
    ----------
    cart          : current cart items
    already_shown : suggestion strings already shown this session
    menu_items    : active menu (to confirm the target item exists + exact name)
    combo_deals   : active combos from fetch_active_combos()
    upsell_rules  : active rules from fetch_upsell_rules()
    """
    cart_names  = {c["name"].lower() for c in cart}
    menu_names  = {m["name"].lower(): m["name"] for m in menu_items}
    deals       = combo_deals or []
    rules       = sorted(upsell_rules or [], key=lambda r: -r.get("weight", 5))

    # ── 1. Combo completion (highest value) ───────────────────────────────────
    for combo in deals:
        items_lower = [it["item_name"].lower() for it in combo.get("items", [])]
        present     = [i for i in items_lower if i in cart_names]
        missing     = [i for i in items_lower if i not in cart_names]
        if present and missing:
            for m in missing:
                canonical = menu_names.get(m)
                if canonical:
                    price_hint = (
                        f" (complete the '{combo['name']}' combo at ₹{combo['selling_price']:.0f})"
                        if combo.get("selling_price") else f" (part of the '{combo['name']}' combo)"
                    )
                    suggestion = f"Add {canonical}{price_hint}!"
                    if suggestion not in already_shown:
                        return suggestion

    # ── 2. DB upsell rules (weight-sorted, highest first) ────────────────────
    for rule in rules:
        trigger   = rule["trigger_item"].lower()
        suggest   = rule["suggest_item"].lower()
        if trigger in cart_names and suggest not in cart_names:
            canonical = menu_names.get(suggest)
            if canonical:
                reason     = rule.get("reason") or f"It pairs great with {rule['trigger_item']}"
                suggestion = f"How about {canonical}? {reason}!"
                if suggestion not in already_shown:
                    return suggestion

    # ── 3. Combo-derived pairings (generic fallback) ──────────────────────────
    for combo in deals:
        combo_items = [it["item_name"] for it in combo.get("items", [])]
        for trigger in combo_items:
            if trigger.lower() in cart_names:
                for partner in combo_items:
                    if partner == trigger:
                        continue
                    canonical = menu_names.get(partner.lower())
                    if canonical and canonical.lower() not in cart_names:
                        suggestion = f"Would you like to add {canonical}? It pairs great with {trigger}!"
                        if suggestion not in already_shown:
                            return suggestion

    return None


# ─── Combo detection ──────────────────────────────────────────────────────────

def detect_active_combos(cart: list[dict], combo_deals: list[dict] | None = None) -> list[dict]:
    """
    Return list of combos fully satisfied by the current cart.
    Used to display savings badge in the UI.
    """
    cart_names = {c["name"].lower() for c in cart}
    active = []
    for combo in (combo_deals or []):
        combo_item_names = [it["item_name"].lower() for it in combo.get("items", [])]
        if combo_item_names and all(i in cart_names for i in combo_item_names):
            active.append({
                "name":        combo["name"],
                "description": combo.get("description") or combo["name"],
                "selling_price": combo.get("selling_price", 0),
            })
    return active


# ─── Order summary ────────────────────────────────────────────────────────────

def build_order_summary(cart: list[dict], subtotal: float, tax: float, total: float, combo_deals: list[dict] | None = None) -> dict:
    """
    Build a structured order summary JSON — the final artefact before DB write.
    """
    combos = detect_active_combos(cart, combo_deals)
    combo_saving = sum(c.get("selling_price", 0) for c in combos)

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
