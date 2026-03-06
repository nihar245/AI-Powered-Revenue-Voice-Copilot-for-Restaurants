from services.nlu.intent_classifier import find_best_menu_match_async

_MATCH_THRESHOLD = 0.50   # minimum cosine similarity to accept a menu match


async def add_to_cart(
    cart: list[dict],
    raw_query: str,
    quantity: int,
    menu_items: list[dict],
) -> tuple[list[dict], dict | None, bool]:
    """
    Finds the best matching menu item for `raw_query` and adds it to the cart.

    Returns:
        (updated_cart, matched_item_or_None, needs_clarification)
    """
    if not menu_items:
        return cart, None, True

    names = [item["name"] for item in menu_items]
    idx, score = await find_best_menu_match_async(raw_query, names)

    if score < _MATCH_THRESHOLD:
        return cart, None, True   # unclear — ask again

    matched = menu_items[idx]

    # Increment quantity if already in cart
    for item in cart:
        if item["product_id"] == matched["product_id"]:
            item["quantity"] += quantity
            return cart, matched, False

    cart.append({
        "product_id":   str(matched["product_id"]),
        "name":         matched["name"],
        "quantity":     quantity,
        "unit_price":   float(matched["price"]),
        "tax_rate":     float(matched.get("tax", 5.0)),
        "variant_id":   None,
        "variant_name": None,
        "notes":        None,
    })
    return cart, matched, False


async def remove_from_cart(
    cart: list[dict],
    raw_query: str,
    menu_items: list[dict],
) -> tuple[list[dict], bool]:
    """
    Removes the best-matching item from the cart.

    Returns:
        (updated_cart, was_removed)
    """
    if not menu_items or not cart:
        return cart, False

    names = [item["name"] for item in menu_items]
    idx, score = await find_best_menu_match_async(raw_query, names)

    if score < _MATCH_THRESHOLD:
        return cart, False

    matched_id   = str(menu_items[idx]["product_id"])
    original_len = len(cart)
    cart         = [item for item in cart if item["product_id"] != matched_id]
    return cart, len(cart) < original_len


def get_cart_total(cart: list[dict]) -> tuple[float, float, float]:
    """
    Returns (subtotal, tax_amount, grand_total).
    """
    subtotal = sum(item["unit_price"] * item["quantity"] for item in cart)
    tax      = sum(
        item["unit_price"] * item["quantity"] * item["tax_rate"] / 100
        for item in cart
    )
    return subtotal, tax, subtotal + tax
