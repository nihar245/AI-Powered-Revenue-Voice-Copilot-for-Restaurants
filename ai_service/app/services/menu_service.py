"""
Menu service module.

Provides menu data for the AI pipeline.

Priority order for menu data:
  1. PostgreSQL (direct asyncpg connection) — live data, refreshed every 60s
  2. Backend API (localhost:3000/api/menu/items) — fallback
  3. Hardcoded seed data                       — last resort fallback
"""

import logging
import asyncio
import time
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

# Backend API URL for fetching live menu
_BACKEND_URL = "http://localhost:3000/api"

# PostgreSQL connection string — matches backend/.env
_DB_URL = "postgresql://postgres:12345678@localhost:5432/postgres"

# Menu cache (refreshed from DB every 60 seconds)
_menu_cache_ts: float = 0.0
_MENU_TTL = 60.0

# ---------------------------------------------------------------------------
# Menu data matching the DB seed (final_static_seed.sql)
# Prices are the "Full" variant selling_price where available
# ---------------------------------------------------------------------------

_MENU_ITEMS: list[dict] = [
    # Starters (category_id=1)
    {"id": 1,  "name": "Paneer Tikka",      "price": 380.0, "category": "Starter",  "available": True, "is_veg": True,  "variants": "Half ₹220, Full ₹380"},
    {"id": 2,  "name": "Dal Shorba",         "price": 140.0, "category": "Starter",  "available": True, "is_veg": True,  "variants": "Small ₹80, Large ₹140"},
    {"id": 3,  "name": "Seekh Kebab",        "price": 450.0, "category": "Starter",  "available": True, "is_veg": False, "variants": "Half ₹260, Full ₹450"},
    {"id": 4,  "name": "Veg Shammi Kebab",   "price": 320.0, "category": "Starter",  "available": True, "is_veg": True,  "variants": "Half ₹180, Full ₹320"},
    {"id": 5,  "name": "Chicken 65",         "price": 420.0, "category": "Starter",  "available": True, "is_veg": False, "variants": "Half ₹240, Full ₹420"},
    # Mains (category_id=2)
    {"id": 6,  "name": "Butter Chicken",     "price": 380.0, "category": "Main",     "available": True, "is_veg": False, "variants": "Half ₹220, Full ₹380"},
    {"id": 7,  "name": "Dal Makhani",        "price": 280.0, "category": "Main",     "available": True, "is_veg": True,  "variants": "Half ₹160, Full ₹280"},
    {"id": 8,  "name": "Shahi Paneer",       "price": 350.0, "category": "Main",     "available": True, "is_veg": True,  "variants": "Half ₹200, Full ₹350"},
    {"id": 9,  "name": "Palak Paneer",       "price": 320.0, "category": "Main",     "available": True, "is_veg": True,  "variants": "Half ₹180, Full ₹320"},
    {"id": 10, "name": "Mutton Rogan Josh",  "price": 480.0, "category": "Main",     "available": True, "is_veg": False, "variants": "Half ₹280, Full ₹480"},
    {"id": 11, "name": "Chicken Kadai",      "price": 360.0, "category": "Main",     "available": True, "is_veg": False, "variants": "Half ₹200, Full ₹360"},
    {"id": 12, "name": "Rajma Masala",       "price": 240.0, "category": "Main",     "available": True, "is_veg": True,  "variants": "Half ₹140, Full ₹240"},
    {"id": 13, "name": "Chana Masala",       "price": 220.0, "category": "Main",     "available": True, "is_veg": True,  "variants": "Half ₹130, Full ₹220"},
    # Breads (category_id=3)
    {"id": 14, "name": "Butter Naan",        "price": 45.0,  "category": "Bread",    "available": True, "is_veg": True,  "variants": "Single ₹45"},
    {"id": 15, "name": "Tandoori Roti",      "price": 30.0,  "category": "Bread",    "available": True, "is_veg": True,  "variants": "Single ₹30"},
    {"id": 16, "name": "Garlic Naan",        "price": 55.0,  "category": "Bread",    "available": True, "is_veg": True,  "variants": "Single ₹55"},
    {"id": 17, "name": "Paratha",            "price": 40.0,  "category": "Bread",    "available": True, "is_veg": True,  "variants": "Single ₹40"},
    # Rice (category_id=4)
    {"id": 18, "name": "Chicken Biryani",    "price": 380.0, "category": "Rice",     "available": True, "is_veg": False, "variants": "Half ₹220, Full ₹380"},
    {"id": 19, "name": "Veg Biryani",        "price": 280.0, "category": "Rice",     "available": True, "is_veg": True,  "variants": "Half ₹160, Full ₹280"},
    {"id": 20, "name": "Mutton Biryani",     "price": 480.0, "category": "Rice",     "available": True, "is_veg": False, "variants": "Half ₹280, Full ₹480"},
    {"id": 21, "name": "Jeera Rice",         "price": 120.0, "category": "Rice",     "available": True, "is_veg": True,  "variants": "Half ₹70, Full ₹120"},
    # Drinks (category_id=5)
    {"id": 22, "name": "Sweet Lassi",        "price": 80.0,  "category": "Drink",    "available": True, "is_veg": True,  "variants": "Small ₹80, Large ₹130"},
    {"id": 23, "name": "Masala Chai",        "price": 30.0,  "category": "Drink",    "available": True, "is_veg": True,  "variants": "Single ₹30"},
    {"id": 24, "name": "Fresh Lime Soda",    "price": 60.0,  "category": "Drink",    "available": True, "is_veg": True,  "variants": "Single ₹60"},
    {"id": 25, "name": "Mango Lassi",        "price": 160.0, "category": "Drink",    "available": True, "is_veg": True,  "variants": "Small ₹100, Large ₹160"},
    # Desserts (category_id=6)
    {"id": 26, "name": "Gulab Jamun",        "price": 110.0, "category": "Dessert",  "available": True, "is_veg": True,  "variants": "2 Pieces ₹60, 4 Pieces ₹110"},
    {"id": 27, "name": "Rasgulla",           "price": 100.0, "category": "Dessert",  "available": True, "is_veg": True,  "variants": "2 Pieces ₹55, 4 Pieces ₹100"},
    {"id": 28, "name": "Kheer",              "price": 140.0, "category": "Dessert",  "available": True, "is_veg": True,  "variants": "Small ₹80, Large ₹140"},
    {"id": 29, "name": "Gajar Halwa",        "price": 160.0, "category": "Dessert",  "available": True, "is_veg": True,  "variants": "Small ₹90, Large ₹160"},
    {"id": 30, "name": "Raita",              "price": 50.0,  "category": "Dessert",  "available": True, "is_veg": True,  "variants": "Single ₹50"},
]

# Combo meals from the database
_COMBOS: list[dict] = [
    {"name": "Butter Chicken Meal", "price": 480.0, "items": "Butter Chicken + Butter Naan + Sweet Lassi"},
    {"name": "Biryani Special", "price": 450.0, "items": "Chicken Biryani + Raita + Sweet Lassi"},
    {"name": "Veg Delight", "price": 520.0, "items": "Dal Makhani + Shahi Paneer + Butter Naan + Raita"},
    {"name": "Lunch Thali", "price": 350.0, "items": "Dal Makhani + Tandoori Roti + Jeera Rice + Raita"},
    {"name": "Kebab Platter", "price": 420.0, "items": "Paneer Tikka + Seekh Kebab"},
    {"name": "Mutton Feast", "price": 680.0, "items": "Mutton Rogan Josh + Mutton Biryani + Raita"},
    {"name": "Happy Hour Snack", "price": 220.0, "items": "Paneer Tikka + Masala Chai"},
    {"name": "Sweet Ending", "price": 150.0, "items": "Gulab Jamun + Kheer + Masala Chai"},
]

_COMBO_RULES: dict[str, str] = {
    "Paneer Tikka": "Sweet Lassi",
    "Chicken Biryani": "Raita",
    "Butter Chicken": "Butter Naan",
    "Dal Makhani": "Garlic Naan",
    "Mutton Rogan Josh": "Jeera Rice",
    "Chicken Kadai": "Butter Naan",
    "Shahi Paneer": "Garlic Naan",
    "Seekh Kebab": "Masala Chai",
    "Veg Biryani": "Raita",
    "Mutton Biryani": "Raita",
    "Chicken 65": "Fresh Lime Soda",
    "Palak Paneer": "Tandoori Roti",
    "Rajma Masala": "Jeera Rice",
    "Chana Masala": "Paratha",
}


async def fetch_menu_from_backend() -> bool:
    """
    Fetch live menu from the backend API and update the in-memory menu.
    Returns True if successful, False otherwise.
    """
    global _MENU_ITEMS
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{_BACKEND_URL}/menu/items")
            if resp.status_code == 200:
                rows = resp.json()
                new_items = []
                for row in rows:
                    # Get the highest-priced variant as default price
                    variants = row.get("variants", [])
                    price = 0
                    if variants:
                        prices = [float(v["selling_price"]) for v in variants if v.get("is_available")]
                        price = max(prices) if prices else 0
                    new_items.append({
                        "id": row["item_id"],
                        "name": row["name"],
                        "price": price,
                        "category": row.get("category", ""),
                        "available": row.get("is_available", True),
                    })
                if new_items:
                    _MENU_ITEMS = new_items
                    logger.info("Menu updated from backend API: %d items", len(new_items))
                    return True
    except Exception as e:
        logger.warning("Could not fetch menu from backend: %s (using fallback)", e)
    return False


async def refresh_menu_from_db() -> bool:
    """
    Fetch live menu directly from PostgreSQL (asyncpg).

    This is the primary data source — no intermediary backend required.
    Updates _MENU_ITEMS in-place and resets the cache timestamp.
    Returns True if successful, False otherwise.
    """
    global _MENU_ITEMS, _menu_cache_ts
    try:
        import asyncpg  # type: ignore
        conn = await asyncpg.connect(_DB_URL, timeout=5.0)
        try:
            rows = await conn.fetch("""
                SELECT
                    mi.item_id,
                    mi.name,
                    mi.is_veg,
                    mc.name AS category_name,
                    MIN(mv.selling_price) AS price
                FROM menu_items mi
                JOIN menu_categories mc ON mi.category_id = mc.category_id
                LEFT JOIN menu_variants mv
                       ON mv.item_id = mi.item_id AND mv.is_available = TRUE
                WHERE mi.is_available = TRUE AND mc.is_active = TRUE
                GROUP BY mi.item_id, mi.name, mi.is_veg, mc.name, mc.display_order, mi.display_order
                ORDER BY mc.display_order, mi.display_order, mi.name
            """)
            if rows:
                new_items = [
                    {
                        "id":        r["item_id"],
                        "name":      r["name"],
                        "price":     float(r["price"] or 0),
                        "category":  r["category_name"],
                        "available": True,
                        "is_veg":    r["is_veg"],
                        "variants":  "",
                    }
                    for r in rows
                ]
                _MENU_ITEMS    = new_items
                _menu_cache_ts = time.time()
                logger.info("✅ Menu refreshed from DB: %d items", len(new_items))

            # Also refresh combos from DB (regardless of whether menu rows changed)
            combo_rows = await conn.fetch("""
                SELECT mc.combo_name, mc.selling_price,
                       string_agg(
                           mi.name || CASE WHEN ci.qty > 1 THEN ' x' || ci.qty::text ELSE '' END,
                           ' + ' ORDER BY ci.combo_item_id
                       ) AS items
                FROM menu_combos mc
                JOIN combo_items ci ON ci.combo_id = mc.combo_id
                JOIN menu_items mi ON ci.item_id = mi.item_id
                WHERE mc.is_active = TRUE
                GROUP BY mc.combo_id, mc.combo_name, mc.selling_price
                ORDER BY mc.combo_id
            """)
            if combo_rows:
                _COMBOS[:] = [
                    {
                        "name":  r["combo_name"],
                        "price": float(r["selling_price"]),
                        "items": r["items"] or "",
                    }
                    for r in combo_rows
                ]
                logger.info("✅ Combos refreshed from DB: %d combos", len(_COMBOS))

            return bool(rows)
        finally:
            await conn.close()
    except Exception as e:
        logger.warning("Could not fetch menu from DB: %s (using fallback)", e)
    return False


def get_menu_items() -> list[str]:
    """
    Get list of available menu items with prices for LLM context.

    Returns:
        list[str]: Formatted menu item strings with name, price, category, veg/non-veg.
    """
    items = []
    for item in _MENU_ITEMS:
        if not item["available"]:
            continue
        veg_tag = "🟢 Veg" if item.get("is_veg", True) else "🔴 Non-Veg"
        variants = item.get("variants", "")
        line = f"{item['name']} — ₹{item['price']} [{item['category']}] ({veg_tag})"
        if variants:
            line += f" | Variants: {variants}"
        items.append(line)
    return items


def get_combos_for_context() -> list[str]:
    """Get combo meals formatted for LLM context."""
    return [
        f"{c['name']} — ₹{c['price']} ({c['items']})"
        for c in _COMBOS
    ]


def get_menu_items_detailed() -> list[dict]:
    """
    Get detailed menu item information.

    Returns:
        list[dict]: Full menu item records.
    
    TODO: Replace with: SELECT * FROM menu_items WHERE available = true
    """
    return [item for item in _MENU_ITEMS if item["available"]]


def get_menu_item_by_name(name: str) -> Optional[dict]:
    """
    Look up a single menu item by name.

    Args:
        name: The menu item name to find.

    Returns:
        Optional[dict]: The menu item record or None.
    
    TODO: Replace with: SELECT * FROM menu_items WHERE name = %s
    """
    for item in _MENU_ITEMS:
        if item["name"].lower() == name.lower():
            return item
    return None


def get_combo_rules() -> dict[str, str]:
    """
    Get combo/pairing rules for upselling.

    Returns:
        dict[str, str]: Mapping of item -> recommended pairing.
    
    TODO: Replace with: SELECT * FROM combo_rules
    """
    return _COMBO_RULES.copy()


def get_categories() -> list[str]:
    """
    Get list of unique menu categories.

    Returns:
        list[str]: Category names.
    
    TODO: Replace with: SELECT DISTINCT category FROM menu_items
    """
    return list(set(item["category"] for item in _MENU_ITEMS))
