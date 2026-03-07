"""
Database queries for ai_service_gemini.

Rules:
 - Every query is pre-written here — no dynamic SQL from LLM output.
 - This service writes ONLY to: orders, order_items, kot, kot_items.
 - All other tables are read-only.

Schema: uses the PetPooja restaurant schema (menu_items / menu_variants /
menu_categories — NOT the old cafe-odoo products/categories schema).
"""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException

from services.database.connection import get_pool

logger = logging.getLogger(__name__)

_LOG  = lambda *a: logger.info("[DB/queries] " + a[0], *a[1:])
_ERR  = lambda *a: logger.error("[DB/queries][ERROR] " + a[0], *a[1:])


# ─── READ — Menu ─────────────────────────────────────────────────────────────

async def fetch_active_menu() -> list[dict]:
    """
    Returns every active menu item with all variants and addons.

    Shape per item:
      product_id    : str(item_id)   — used as product_id throughout the app
      name          : str
      price         : float          — default (first/cheapest) variant price
      tax           : float          — default variant gst_pct
      category_name : str
      is_veg        : bool
      tags          : list[str]
      variants      : [{variant_id, variant_name, price, gst_pct, food_cost}]
      addons        : [{addon_id, addon_name, price}]
    """
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Fetch items+variants in one query
    rows = await pool.fetch("""
        SELECT
            mi.item_id,
            mi.name,
            mi.description,
            mi.is_veg,
            mi.tags,
            mc.name AS category_name,
            mv.variant_id,
            mv.variant_name,
            mv.selling_price,
            mv.gst_pct,
            mv.food_cost AS variant_food_cost
        FROM menu_items mi
        JOIN menu_categories mc ON mi.category_id = mc.category_id
        LEFT JOIN menu_variants mv
               ON mv.item_id = mi.item_id AND mv.is_available = TRUE
        WHERE mi.is_available = TRUE AND mc.is_active = TRUE
        ORDER BY mc.display_order, mi.display_order, mi.name, mv.selling_price
    """)

    # Group variants per item (preserve insertion order → cheapest first)
    items: dict[int, dict] = {}
    for r in rows:
        iid = r["item_id"]
        if iid not in items:
            items[iid] = {
                "product_id":    str(iid),
                "name":          r["name"],
                "description":   r["description"] or "",
                "is_veg":        r["is_veg"],
                "tags":          list(r["tags"] or []),
                "category_name": r["category_name"],
                "variants":      [],
                "price":         0.0,
                "tax":           5.0,
            }
        if r["variant_id"] is not None:
            items[iid]["variants"].append({
                "variant_id":   r["variant_id"],
                "variant_name": r["variant_name"],
                "price":        float(r["selling_price"]),
                "gst_pct":      float(r["gst_pct"]),
                "food_cost":    float(r["variant_food_cost"]),
            })

    result = list(items.values())
    # Default price/tax = cheapest available variant
    for item in result:
        if item["variants"]:
            item["price"] = item["variants"][0]["price"]
            item["tax"]   = item["variants"][0]["gst_pct"]

    # Fetch addons in one query and attach
    addon_rows = await pool.fetch("""
        SELECT item_id, addon_id, addon_name, extra_price
        FROM menu_addons
        WHERE is_available = TRUE
        ORDER BY addon_name
    """)
    addon_map: dict[int, list] = {}
    for a in addon_rows:
        addon_map.setdefault(a["item_id"], []).append({
            "addon_id":   a["addon_id"],
            "addon_name": a["addon_name"],
            "price":      float(a["extra_price"]),
        })
    for item in result:
        item["addons"] = addon_map.get(int(item["product_id"]), [])

    return result


# ─── READ — Tables ────────────────────────────────────────────────────────────

async def fetch_tables() -> list[dict]:
    """
    This schema has no dedicated 'tables' table.
    Returns empty list — seating capacity is on the restaurants row.
    """
    return []


# ─── WRITE — Orders ──────────────────────────────────────────────────────────

async def generate_order_number() -> str:
    pool = get_pool()
    if pool is None:
        return f"VO-{uuid.uuid4().hex[:6].upper()}"
    row = await pool.fetchrow("SELECT COUNT(*)::int AS cnt FROM orders")
    count = (row["cnt"] or 0) + 1
    return f"VO-{count:04d}"


async def insert_order(
    order_number: str,
    cart: list[dict],
    subtotal: float,
    tax: float,
    total: float,
    placed_by: str = "voice_order",
    restaurant_id: int | None = None,
) -> int:
    """
    Write a confirmed voice order to orders + order_items + kot + kot_items.
    """
    _LOG("insert_order START  order_number=%s  items=%d  total=%.2f",
         order_number, len(cart), total)
    pool = get_pool()
    if pool is None:
        _ERR("insert_order FAILED — database pool is None (not connected)")
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        async with conn.transaction():
            _LOG("insert_order: BEGIN transaction")  

            order_id: int = await conn.fetchval("""
                INSERT INTO orders (
                    restaurant_id, placed_by, channel, status,
                    placed_at, subtotal, discount_amt, tax_amt, total, payment_status
                ) VALUES (
                    $1, $2, 'dine_in', 'placed',
                    NOW(), $3, 0, $4, $5, 'pending'
                )
                RETURNING order_id
            """, restaurant_id, placed_by, subtotal, tax, total)
            _LOG("insert_order: orders row inserted  order_id=%d", order_id)

            for item in cart:
                item_id    = int(item["product_id"])
                variant_id = item.get("variant_id")
                qty        = int(item.get("quantity", 1))
                unit_price = float(item["unit_price"])
                gst_pct    = float(item.get("tax_rate", 5.0))
                gst_amt    = round(unit_price * qty * gst_pct / 100, 2)
                revenue    = round(unit_price * qty, 2)

                # Look up food_cost from variants table
                food_cost = 0.0
                if variant_id:
                    fc_row = await conn.fetchrow(
                        "SELECT food_cost FROM menu_variants WHERE variant_id = $1",
                        int(variant_id),
                    )
                    if fc_row:
                        food_cost = float(fc_row["food_cost"])
                    else:
                        _ERR("insert_order: variant_id=%s not found in menu_variants", variant_id)

                # Merge notes + modifiers into special_instructions
                notes = item.get("notes") or ""
                mods  = item.get("modifiers")
                if mods:
                    mod_str = ", ".join(f"{k}={v}" for k, v in mods.items() if v)
                    if mod_str:
                        notes = f"{mod_str}. {notes}".strip(". ")

                await conn.execute("""
                    INSERT INTO order_items (
                        order_id, item_id, variant_id, qty,
                        unit_price, discount_pct, revenue, food_cost,
                        gst_amt, special_instructions, is_upsell
                    ) VALUES (
                        $1, $2, $3, $4,
                        $5,  0,  $6, $7,
                        $8,  $9, FALSE
                    )
                """, order_id, item_id,
                    int(variant_id) if variant_id else None,
                    qty, unit_price, revenue, food_cost,
                    gst_amt, notes or None)
                _LOG("insert_order: order_item inserted  order_id=%d  item_id=%d  variant_id=%s  qty=%d",
                     order_id, item_id, variant_id, qty)

            # Create KOT
            _LOG("insert_order: inserting KOT for order_id=%d", order_id)
            kot_id: int = await conn.fetchval("""
                INSERT INTO kot (order_id, status, priority, created_at)
                VALUES ($1, 'pending', 'normal', NOW())
                RETURNING kot_id
            """, order_id)
            _LOG("insert_order: KOT inserted  kot_id=%d  order_id=%d  status=pending", kot_id, order_id)

            for item in cart:
                item_id    = int(item["product_id"])
                variant_id = item.get("variant_id")
                qty        = int(item.get("quantity", 1))
                notes      = item.get("notes") or ""
                mods       = item.get("modifiers")
                addons_str = ""
                if mods:
                    addons_str = ", ".join(f"{k}={v}" for k, v in mods.items() if v)

                await conn.execute("""
                    INSERT INTO kot_items (
                        kot_id, item_id, variant_id, qty,
                        addons, special_instructions, status
                    ) VALUES ($1, $2, $3, $4, $5, $6, 'pending')
                """, kot_id, item_id,
                    int(variant_id) if variant_id else None,
                    qty, addons_str or None, notes or None)
                _LOG("insert_order: kot_item inserted  kot_id=%d  item_id=%d  qty=%d",
                     kot_id, item_id, qty)

    _LOG("insert_order COMPLETE  order_number=%s  order_id=%d  kot_id=%d",
         order_number, order_id, kot_id)
    return order_id
