"""
Database queries for ai_service_gemini.

Adapted for the PetPooja schema:
  - menu_items + menu_variants + menu_categories  (read)
  - menu_combos + combo_items                      (read)
  - menu_addons                                    (read)
  - orders + order_items + kot + kot_items          (write)

Rules:
 - Every query is pre-written — no dynamic SQL from LLM output.
 - Integer PKs (SERIAL), NOT UUIDs.
 - This service writes ONLY to: orders, order_items, kot, kot_items.
"""

from __future__ import annotations

from fastapi import HTTPException

from services.database.connection import get_pool


# ─── READ — Menu ──────────────────────────────────────────────────────────────

async def fetch_active_menu() -> list[dict]:
    """
    Return every available menu item with its default variant and full
    variants list.  Each entry uses ``product_id`` (= item_id as str) for
    backward-compat with the rest of the pipeline.
    """
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    rows = await pool.fetch("""
        SELECT
            mi.item_id,
            mi.name,
            mi.description,
            mi.is_veg,
            mi.is_jain,
            mc.name          AS category_name,
            mv.variant_id,
            mv.variant_name,
            mv.selling_price,
            mv.food_cost,
            mv.gst_pct
        FROM menu_items mi
        JOIN menu_categories mc ON mi.category_id = mc.category_id
        JOIN menu_variants  mv ON mv.item_id     = mi.item_id
        WHERE mi.is_available = TRUE
          AND mv.is_available = TRUE
          AND mc.is_active    = TRUE
        ORDER BY mc.display_order, mi.display_order, mv.variant_id
    """)

    # Group by item_id → pick first variant as default, attach all variants
    items_map: dict[int, dict] = {}
    for r in rows:
        iid = r["item_id"]
        variant = {
            "variant_id":   r["variant_id"],
            "variant_name": r["variant_name"],
            "price":        float(r["selling_price"]),
            "gst_pct":      float(r["gst_pct"]),
            "food_cost":    float(r["food_cost"]),
        }
        if iid not in items_map:
            items_map[iid] = {
                "product_id":    str(iid),
                "item_id":       iid,
                "name":          r["name"],
                "description":   r["description"] or "",
                "is_veg":        r["is_veg"],
                "is_jain":       r["is_jain"],
                "category_name": r["category_name"],
                "price":         float(r["selling_price"]),
                "tax":           float(r["gst_pct"]),
                "variant_id":    r["variant_id"],
                "variant_name":  r["variant_name"],
                "food_cost":     float(r["food_cost"]),
                "variants":      [],
            }
        items_map[iid]["variants"].append(variant)

    return list(items_map.values())


# ─── READ — Combos ────────────────────────────────────────────────────────────

async def fetch_active_combos() -> list[dict]:
    """Return active combos with their constituent items."""
    pool = get_pool()
    if pool is None:
        return []

    rows = await pool.fetch("""
        SELECT
            mc.combo_id,
            mc.combo_name,
            mc.description,
            mc.selling_price,
            mc.food_cost,
            ci.item_id,
            mi.name AS item_name,
            ci.variant_id,
            mv.variant_name,
            mv.selling_price AS variant_price
        FROM menu_combos mc
        JOIN combo_items  ci ON ci.combo_id  = mc.combo_id
        JOIN menu_items   mi ON mi.item_id   = ci.item_id
        LEFT JOIN menu_variants mv ON mv.variant_id = ci.variant_id
        WHERE mc.is_active = TRUE
          AND (mc.valid_from IS NULL OR mc.valid_from <= CURRENT_DATE)
          AND (mc.valid_to   IS NULL OR mc.valid_to   >= CURRENT_DATE)
        ORDER BY mc.combo_id, ci.combo_item_id
    """)

    combos_map: dict[int, dict] = {}
    for r in rows:
        cid = r["combo_id"]
        if cid not in combos_map:
            combos_map[cid] = {
                "combo_id":      cid,
                "name":          r["combo_name"],
                "description":   r["description"] or "",
                "selling_price": float(r["selling_price"]),
                "food_cost":     float(r["food_cost"]),
                "items":         [],
            }
        combos_map[cid]["items"].append({
            "item_id":      r["item_id"],
            "item_name":    r["item_name"],
            "variant_id":   r["variant_id"],
            "variant_name": r["variant_name"],
            "variant_price": float(r["variant_price"]) if r["variant_price"] else None,
        })

    # Compute saving: sum of individual variant prices − combo selling_price
    for combo in combos_map.values():
        individual_total = sum(
            i["variant_price"] for i in combo["items"] if i["variant_price"]
        )
        combo["saving"] = max(0, round(individual_total - combo["selling_price"], 2))

    return list(combos_map.values())


# ─── READ — Addons ────────────────────────────────────────────────────────────

async def fetch_addons() -> list[dict]:
    """Return available add-ons grouped by item_id."""
    pool = get_pool()
    if pool is None:
        return []

    rows = await pool.fetch("""
        SELECT addon_id, item_id, addon_name, extra_price
        FROM menu_addons
        WHERE is_available = TRUE
        ORDER BY item_id, addon_id
    """)
    return [dict(r) for r in rows]


# ─── WRITE — Orders ──────────────────────────────────────────────────────────

async def insert_order(
    cart: list[dict],
    subtotal: float,
    tax: float,
    total: float,
    channel: str = "dine_in",
) -> int:
    """
    Write a confirmed voice order into orders → order_items → kot → kot_items.
    Returns the new order_id.
    """
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Insert order
            order_id: int = await conn.fetchval("""
                INSERT INTO orders (
                    restaurant_id, customer_id, placed_by, channel,
                    status, placed_at,
                    subtotal, discount_amt, tax_amt, total, payment_status
                ) VALUES (
                    1, NULL, 'voice_copilot', $1,
                    'placed', NOW(),
                    $2, 0, $3, $4, 'pending'
                )
                RETURNING order_id
            """, channel, subtotal, tax, total)

            # 2. Insert order_items
            for item in cart:
                item_id    = int(item.get("item_id") or item["product_id"])
                variant_id = int(item["variant_id"]) if item.get("variant_id") else None
                qty        = int(item.get("quantity", 1))
                unit_price = float(item["unit_price"])
                gst_pct    = float(item.get("tax_rate", 5.0))
                revenue    = unit_price * qty
                food_cost  = float(item.get("food_cost", 0)) * qty
                gst_amt    = revenue * gst_pct / 100
                notes      = item.get("notes") or None

                await conn.execute("""
                    INSERT INTO order_items (
                        order_id, item_id, variant_id, qty,
                        unit_price, discount_pct, revenue, food_cost,
                        gst_amt, special_instructions
                    ) VALUES ($1, $2, $3, $4, $5, 0, $6, $7, $8, $9)
                """, order_id, item_id, variant_id, qty,
                    unit_price, revenue, food_cost, gst_amt, notes)

            # 3. Create KOT
            kot_id: int = await conn.fetchval("""
                INSERT INTO kot (order_id, status, priority, created_at)
                VALUES ($1, 'pending', 'normal', NOW())
                RETURNING kot_id
            """, order_id)

            # 4. Insert kot_items
            for item in cart:
                item_id    = int(item.get("item_id") or item["product_id"])
                variant_id = int(item["variant_id"]) if item.get("variant_id") else None
                qty        = int(item.get("quantity", 1))
                notes      = item.get("notes") or None

                await conn.execute("""
                    INSERT INTO kot_items (
                        kot_id, item_id, variant_id, qty,
                        special_instructions, status
                    ) VALUES ($1, $2, $3, $4, $5, 'pending')
                """, kot_id, item_id, variant_id, qty, notes)

    return order_id
