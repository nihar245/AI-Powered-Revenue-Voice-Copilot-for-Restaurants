from enum import Enum
from typing import Optional

from pydantic import BaseModel


# ─── Enums ────────────────────────────────────────────────────────────────────

class Language(str, Enum):
    EN = "en"
    HI = "hi"
    GU = "gu"


class Intent(str, Enum):
    GREETING             = "greeting"
    ADD_ITEM             = "add_item"
    REMOVE_ITEM          = "remove_item"
    MODIFY_ITEM          = "modify_item"
    VIEW_MENU            = "view_menu"
    VIEW_CART            = "view_cart"
    DONE_ORDERING        = "done_ordering"   # customer says "that's all / no more"
    CONFIRM_ORDER        = "confirm_order"   # customer confirms send-to-kitchen
    CANCEL_ORDER         = "cancel_order"
    ENQUIRE_PRICE        = "enquire_price"
    UPSELL_RESPONSE      = "upsell_response"
    CLARIFY              = "clarify"
    UNKNOWN              = "unknown"


class DialogueState(str, Enum):
    GREETING                 = "greeting"
    TAKING_ORDER             = "taking_order"
    AWAITING_KITCHEN_CONFIRM = "awaiting_kitchen_confirm"  # cart read back, waiting yes/no
    CONFIRMING               = "confirming"
    PLACING_ORDER            = "placing_order"
    DONE                     = "done"


# ─── Cart item ────────────────────────────────────────────────────────────────

class Modifiers(BaseModel):
    size:        Optional[str]       = None
    spice_level: Optional[str]       = None
    add_ons:     Optional[list[str]] = None
    notes:       Optional[str]       = None


class CartItem(BaseModel):
    product_id:   str
    name:         str
    quantity:     int
    unit_price:   float
    tax_rate:     float
    variant_id:   Optional[str]      = None
    variant_name: Optional[str]      = None
    notes:        Optional[str]      = None
    modifiers:    Optional[Modifiers] = None


class UpsellRecommendation(BaseModel):
    text:    str       # Human-readable suggestion e.g. "Add Mango Lassi for ₹80?"
    item:    str       # Item name being suggested
    trigger: str       # Item in cart that triggered the suggestion


# ─── API Request / Response ───────────────────────────────────────────────────

class VoiceOrderResponse(BaseModel):
    audio_base64:          str
    transcript:            str
    language:              Language
    intent:                Intent
    dialogue_state:        DialogueState
    cart:                  list[CartItem]
    response_text:         str
    session_id:            str
    upsell_suggestion:     Optional[str]                   = None
    upsell_chips:          Optional[list[dict]]            = None
    pending_clarification: Optional[str]                   = None
    active_combos:         Optional[list[dict]]            = None


class ResetRequest(BaseModel):
    session_id: str


class ResetResponse(BaseModel):
    success: bool
    message: str


class HealthResponse(BaseModel):
    status:     str
    components: dict
