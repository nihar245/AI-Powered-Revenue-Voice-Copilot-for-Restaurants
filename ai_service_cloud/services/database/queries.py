"""
All database interactions for ai_service.

Rules:
 - Every query is pre-written here — no dynamic SQL from LLM output.
 - UUIDs are passed as strings; SQL casts them with ::uuid.
 - ai_service writes ONLY to: orders, order_items, kitchen_tickets.
 - All other tables (products, categories, tables, pos_sessions, pos_terminals)
   are read-only from this service.
"""

from __future__ import annotations

import json
import uuid

from fastapi import HTTPException

from services.database.connection import get_pool


# ─────────────────────────────────────────────────────────────────────────────
# READ — Menu
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_active_menu() -> list[dict]:
    """
    Returns every active product with its category name.
    Used by the NLU menu-matcher and the LLM context builder.
    """
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    rows = await pool.fetch("""
        SELECT
            p.product_id::text,
            p.name,
            p.price,
            p.unit,
            p.tax,
            p.description,
            c.name AS category_name
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        WHERE p.active = TRUE
        ORDER BY c.sequence, p.name
    """)
    return [dict(r) for r in rows]


async def fetch_menu_by_category() -> list[dict]:
    """Returns menu grouped by category — used for VIEW_MENU intent."""
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    cat_rows = await pool.fetch("""
        SELECT category_id::text, name, sequence
        FROM categories
        ORDER BY sequence
    """)

    result: list[dict] = []
    for cat in cat_rows:
        item_rows = await pool.fetch("""
            SELECT product_id::text, name, price, unit, tax
            FROM products
            WHERE category_id = $1::uuid AND active = TRUE
            ORDER BY name
        """, cat["category_id"])

        if item_rows:
            result.append({
                "category_id": cat["category_id"],
                "name":        cat["name"],
                "items":       [dict(r) for r in item_rows],
            })

    return result


# ─────────────────────────────────────────────────────────────────────────────
# READ — Tables / Sessions / Terminals
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_table_by_id(table_id: str) -> dict | None:
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    row = await pool.fetchrow("""
        SELECT table_id::text, table_number, seats, status, floor_id::text
        FROM tables
        WHERE table_id = $1::uuid AND active = TRUE
    """, table_id)
    return dict(row) if row else None


async def get_open_session_id(user_id: str) -> str | None:
    """Returns the currently open POS session for the given user, or None."""
    pool = get_pool()
    if pool is None:
        return None

    row = await pool.fetchrow("""
        SELECT session_id::text
        FROM pos_sessions
        WHERE user_id = $1::uuid AND status = 'open'
        LIMIT 1
    """, user_id)
    return row["session_id"] if row else None


async def get_default_terminal_id() -> str | None:
    pool = get_pool()
    if pool is None:
        return None

    row = await pool.fetchrow("""
        SELECT terminal_id::text
        FROM pos_terminals
        WHERE device_identifier = 'default-terminal'
        LIMIT 1
    """)
    return row["terminal_id"] if row else None


# ─────────────────────────────────────────────────────────────────────────────
# WRITE — Orders
# ─────────────────────────────────────────────────────────────────────────────

async def generate_order_number() -> str:
    """Generates a voice-order number like VO-0042."""
    pool = get_pool()
    if pool is None:
        return f"VO-{uuid.uuid4().hex[:6].upper()}"

    row = await pool.fetchrow("""
        SELECT COUNT(*)::int AS cnt
        FROM orders
        WHERE source = 'self_order'
    """)
    count = (row["cnt"] or 0) + 1
    return f"VO-{count:04d}"


async def insert_order(
    order_number: str,
    table_id: str,
    session_id: str,
    terminal_id: str,
    user_id: str,
    cart: list[dict],
    subtotal: float,
    tax: float,
    total: float,
) -> str:
    """
    Atomically inserts:
      1. orders row
      2. order_items rows
      3. kitchen_tickets row
      4. pg_notify('new_order', …) — picked up by Node.js Socket.io

    Returns the new order_id (UUID string).
    """
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Insert order
            order_id: uuid.UUID = await conn.fetchval("""
                INSERT INTO orders (
                    order_number, table_id, session_id, terminal_id, user_id,
                    subtotal, tax, total, status, source
                ) VALUES (
                    $1,
                    $2::uuid, $3::uuid, $4::uuid, $5::uuid,
                    $6, $7, $8,
                    'sent_to_kitchen', 'self_order'
                )
                RETURNING order_id
            """, order_number,
                table_id, session_id, terminal_id, user_id,
                subtotal, tax, total)

            # 2. Insert order items
            for item in cart:
                tax_amount  = item["unit_price"] * item["quantity"] * item["tax_rate"] / 100
                total_price = item["unit_price"] * item["quantity"] + tax_amount

                await conn.execute("""
                    INSERT INTO order_items (
                        order_id, product_id, product_name,
                        quantity, unit_price, tax_rate, tax_amount, total_price
                    ) VALUES (
                        $1, $2::uuid, $3,
                        $4, $5, $6, $7, $8
                    )
                """, order_id,
                    item["product_id"], item["name"],
                    item["quantity"], item["unit_price"],
                    item["tax_rate"], tax_amount, total_price)

            # 3. Insert kitchen ticket
            table_row = await conn.fetchrow("""
                SELECT table_number FROM tables WHERE table_id = $1::uuid
            """, table_id)
            table_number = table_row["table_number"] if table_row else "?"

            await conn.execute("""
                INSERT INTO kitchen_tickets (
                    order_id, order_number, table_number, status
                ) VALUES ($1, $2, $3, 'to_cook')
            """, order_id, order_number, table_number)

            # 4. Notify Node.js backend via pg_notify
            payload = json.dumps({
                "order_id":     str(order_id),
                "order_number": order_number,
                "table_number": table_number,
                "source":       "voice_order",
            })
            await conn.execute("SELECT pg_notify('new_order', $1)", payload)

    return str(order_id)
