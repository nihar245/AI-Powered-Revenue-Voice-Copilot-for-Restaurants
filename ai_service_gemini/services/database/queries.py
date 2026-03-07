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
import traceback as _traceback
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


# ─── READ — Combos ────────────────────────────────────────────────────────────

async def fetch_active_combos() -> list[dict]:
    """
    Returns active menu combos with their constituent items.

    Shape per combo:
      combo_id      : int
      name          : str
      description   : str
      selling_price : float
      items         : [{ item_name, qty }]
    """
    pool = get_pool()
    if pool is None:
        return []

    try:
        rows = await pool.fetch("""
            SELECT
                mc.combo_id,
                mc.combo_name,
                mc.description,
                mc.selling_price,
                mi.name  AS item_name,
                ci.qty
            FROM menu_combos mc
            JOIN combo_items ci ON ci.combo_id = mc.combo_id
            JOIN menu_items  mi ON mi.item_id  = ci.item_id
            WHERE mc.is_active = TRUE
              AND (mc.valid_to IS NULL OR mc.valid_to >= CURRENT_DATE)
            ORDER BY mc.combo_id, ci.combo_item_id
        """)
    except Exception as exc:
        _ERR("fetch_active_combos failed: %s", exc)
        return []

    combos: dict[int, dict] = {}
    for r in rows:
        cid = r["combo_id"]
        if cid not in combos:
            combos[cid] = {
                "combo_id":      cid,
                "name":          r["combo_name"],
                "description":   r["description"] or "",
                "selling_price": float(r["selling_price"]),
                "items":         [],
            }
        combos[cid]["items"].append({
            "item_name": r["item_name"],
            "qty":       r["qty"],
        })

    return list(combos.values())


# ─── READ — Offers ────────────────────────────────────────────────────────────

async def fetch_active_offers() -> list[dict]:
    """
    Returns active offers applicable to dine_in or phone channels.

    Shape per offer:
      name           : str
      type           : str   (flat | pct | bogo | combo | happy_hour)
      discount_value : float
      min_order_val  : float
    """
    pool = get_pool()
    if pool is None:
        return []

    try:
        rows = await pool.fetch("""
            SELECT name, type, discount_value, min_order_val
            FROM offers
            WHERE is_active = TRUE
              AND valid_to >= CURRENT_DATE
              AND (
                applicable_channels IS NULL
                OR applicable_channels && ARRAY['dine_in','phone']::TEXT[]
              )
            ORDER BY discount_value DESC
            LIMIT 10
        """)
    except Exception as exc:
        _ERR("fetch_active_offers failed: %s", exc)
        return []

    return [
        {
            "name":           r["name"],
            "type":           r["type"],
            "discount_value": float(r["discount_value"]),
            "min_order_val":  float(r["min_order_val"]),
        }
        for r in rows
    ]


# ─── WRITE — Orders ──────────────────────────────────────────────────────────

async def generate_order_number() -> str:
    pool = get_pool()
    print(f"[DEBUG generate_order_number] pool={pool!r}", flush=True)
    if pool is None:
        _fallback = f"VO-{uuid.uuid4().hex[:6].upper()}"
        print(f"[DEBUG generate_order_number] pool is None — using UUID fallback: {_fallback}", flush=True)
        _ERR("generate_order_number: pool is None — DB not connected, using UUID fallback=%s", _fallback)
        return _fallback
    row = await pool.fetchrow("SELECT COUNT(*)::int AS cnt FROM orders")
    count = (row["cnt"] or 0) + 1
    _num = f"VO-{count:04d}"
    print(f"[DEBUG generate_order_number] generated={_num}  (orders_count={row['cnt']})", flush=True)
    return _num


async def insert_order(
    order_number: str,
    cart: list[dict],
    subtotal: float,
    tax: float,
    total: float,
    placed_by: str = "voice_order",
    restaurant_id: int | None = None,
    channel: str = "dine_in",
) -> int:
    """
    Write a confirmed voice order to orders + order_items + kot + kot_items.
    """
    print(
        f"\n[DEBUG insert_order] ============================================",
        flush=True,
    )
    print(f"[DEBUG insert_order] order_number  = {order_number}", flush=True)
    print(f"[DEBUG insert_order] placed_by     = {placed_by}", flush=True)
    print(f"[DEBUG insert_order] channel       = {channel}", flush=True)
    print(f"[DEBUG insert_order] restaurant_id = {restaurant_id}", flush=True)
    print(f"[DEBUG insert_order] subtotal      = {subtotal}", flush=True)
    print(f"[DEBUG insert_order] tax           = {tax}", flush=True)
    print(f"[DEBUG insert_order] total         = {total}", flush=True)
    print(f"[DEBUG insert_order] cart ({len(cart)} items):", flush=True)
    for _i, _ci in enumerate(cart):
        print(f"[DEBUG insert_order]   [{_i}] {_ci}", flush=True)
    _LOG("insert_order START  order_number=%s  items=%d  total=%.2f",
         order_number, len(cart), total)
    pool = get_pool()
    print(f"[DEBUG insert_order] pool = {pool!r}", flush=True)
    if pool is None:
        _ERR("insert_order FAILED — database pool is None (not connected)")
        print("[DEBUG insert_order] ❌ ABORTING — pool is None, DB not connected!", flush=True)
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        async with conn.transaction():
            _LOG("insert_order: BEGIN transaction")
            print("[DEBUG insert_order] BEGIN transaction", flush=True)

            try:
                order_id: int = await conn.fetchval("""
                    INSERT INTO orders (
                        restaurant_id, placed_by, channel, status,
                        placed_at, subtotal, discount_amt, tax_amt, total, payment_status
                    ) VALUES (
                        $1, $2, $3, 'placed',
                        NOW(), $4, 0, $5, $6, 'pending'
                    )
                    RETURNING order_id
                """, restaurant_id, placed_by, channel, subtotal, tax, total)
                print(f"[DEBUG insert_order] orders row OK  order_id={order_id}", flush=True)
                _LOG("insert_order: orders row inserted  order_id=%d", order_id)
            except Exception as _exc:
                _tb = _traceback.format_exc()
                print(f"[DEBUG insert_order] ❌ INSERT INTO orders FAILED: {_exc}", flush=True)
                print(f"[DEBUG insert_order] Params: restaurant_id={restaurant_id!r} placed_by={placed_by!r} channel={channel!r} subtotal={subtotal} tax={tax} total={total}", flush=True)
                print(f"[DEBUG insert_order] Traceback:\n{_tb}", flush=True)
                _ERR("INSERT INTO orders FAILED: %s\n%s", _exc, _tb)
                raise

            for _idx, item in enumerate(cart):
                item_id    = int(item["product_id"])
                variant_id = item.get("variant_id")
                qty        = int(item.get("quantity", 1))
                unit_price = float(item["unit_price"])
                gst_pct    = float(item.get("tax_rate", 5.0))
                gst_amt    = round(unit_price * qty * gst_pct / 100, 2)
                revenue    = round(unit_price * qty, 2)
                print(
                    f"[DEBUG insert_order] order_item[{_idx}]  item_id={item_id}  "
                    f"variant_id={variant_id}  qty={qty}  unit_price={unit_price}  "
                    f"gst_pct={gst_pct}  gst_amt={gst_amt}  revenue={revenue}",
                    flush=True,
                )

                # Look up food_cost from variants table
                food_cost = 0.0
                if variant_id:
                    try:
                        fc_row = await conn.fetchrow(
                            "SELECT food_cost FROM menu_variants WHERE variant_id = $1",
                            int(variant_id),
                        )
                        if fc_row:
                            food_cost = float(fc_row["food_cost"])
                            print(f"[DEBUG insert_order]   food_cost from DB = {food_cost}", flush=True)
                        else:
                            print(f"[DEBUG insert_order]   ⚠️ variant_id={variant_id} NOT FOUND in menu_variants, food_cost=0", flush=True)
                            _ERR("insert_order: variant_id=%s not found in menu_variants", variant_id)
                    except Exception as _exc:
                        print(f"[DEBUG insert_order]   ❌ food_cost lookup failed: {_exc}", flush=True)
                        _ERR("insert_order: food_cost lookup error for variant_id=%s: %s", variant_id, _exc)

                # Merge notes + modifiers into special_instructions
                notes = item.get("notes") or ""
                mods  = item.get("modifiers")
                if mods:
                    mod_str = ", ".join(f"{k}={v}" for k, v in mods.items() if v)
                    if mod_str:
                        notes = f"{mod_str}. {notes}".strip(". ")

                try:
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
                    print(f"[DEBUG insert_order]   order_item[{_idx}] inserted OK", flush=True)
                    _LOG("insert_order: order_item inserted  order_id=%d  item_id=%d  variant_id=%s  qty=%d",
                         order_id, item_id, variant_id, qty)
                except Exception as _exc:
                    _tb = _traceback.format_exc()
                    print(f"[DEBUG insert_order]   ❌ INSERT INTO order_items FAILED for item_id={item_id}: {_exc}", flush=True)
                    print(f"[DEBUG insert_order]   Params: order_id={order_id} item_id={item_id} variant_id={variant_id} qty={qty} unit_price={unit_price} revenue={revenue} food_cost={food_cost} gst_amt={gst_amt} notes={notes!r}", flush=True)
                    print(f"[DEBUG insert_order]   Traceback:\n{_tb}", flush=True)
                    _ERR("INSERT INTO order_items FAILED item_id=%s: %s\n%s", item_id, _exc, _tb)
                    raise

            # Create KOT
            _LOG("insert_order: inserting KOT for order_id=%d", order_id)
            print(f"[DEBUG insert_order] Inserting KOT for order_id={order_id}", flush=True)
            try:
                kot_id: int = await conn.fetchval("""
                    INSERT INTO kot (order_id, status, priority, created_at)
                    VALUES ($1, 'pending', 'normal', NOW())
                    RETURNING kot_id
                """, order_id)
                print(f"[DEBUG insert_order] KOT inserted OK  kot_id={kot_id}", flush=True)
                _LOG("insert_order: KOT inserted  kot_id=%d  order_id=%d  status=pending", kot_id, order_id)
            except Exception as _exc:
                _tb = _traceback.format_exc()
                print(f"[DEBUG insert_order] ❌ INSERT INTO kot FAILED: {_exc}", flush=True)
                print(f"[DEBUG insert_order] Traceback:\n{_tb}", flush=True)
                _ERR("INSERT INTO kot FAILED order_id=%s: %s\n%s", order_id, _exc, _tb)
                raise

            for _idx, item in enumerate(cart):
                item_id    = int(item["product_id"])
                variant_id = item.get("variant_id")
                qty        = int(item.get("quantity", 1))
                notes      = item.get("notes") or ""
                mods       = item.get("modifiers")
                addons_str = ""
                if mods:
                    addons_str = ", ".join(f"{k}={v}" for k, v in mods.items() if v)

                try:
                    await conn.execute("""
                        INSERT INTO kot_items (
                            kot_id, item_id, variant_id, qty,
                            addons, special_instructions, status
                        ) VALUES ($1, $2, $3, $4, $5, $6, 'pending')
                    """, kot_id, item_id,
                        int(variant_id) if variant_id else None,
                        qty, addons_str or None, notes or None)
                    print(f"[DEBUG insert_order]   kot_item[{_idx}] inserted OK  kot_id={kot_id}  item_id={item_id}", flush=True)
                    _LOG("insert_order: kot_item inserted  kot_id=%d  item_id=%d  qty=%d",
                         kot_id, item_id, qty)
                except Exception as _exc:
                    _tb = _traceback.format_exc()
                    print(f"[DEBUG insert_order]   ❌ INSERT INTO kot_items FAILED for item_id={item_id}: {_exc}", flush=True)
                    print(f"[DEBUG insert_order]   Params: kot_id={kot_id} item_id={item_id} variant_id={variant_id} qty={qty}", flush=True)
                    print(f"[DEBUG insert_order]   Traceback:\n{_tb}", flush=True)
                    _ERR("INSERT INTO kot_items FAILED item_id=%s: %s\n%s", item_id, _exc, _tb)
                    raise

    print(
        f"[DEBUG insert_order] ✅ COMPLETE  order_number={order_number}  "
        f"order_id={order_id}  kot_id={kot_id}",
        flush=True,
    )
    _LOG("insert_order COMPLETE  order_number=%s  order_id=%d  kot_id=%d",
         order_number, order_id, kot_id)
    return order_id
