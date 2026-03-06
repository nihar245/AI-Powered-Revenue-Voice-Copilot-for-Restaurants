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
    VIEW_MENU            = "view_menu"
    VIEW_CART            = "view_cart"
    CONFIRM_ORDER        = "confirm_order"
    CANCEL_ORDER         = "cancel_order"
    ENQUIRE_PRICE        = "enquire_price"
    ENQUIRE_AVAILABILITY = "enquire_availability"
    UNKNOWN              = "unknown"


class DialogueState(str, Enum):
    GREETING      = "greeting"
    TAKING_ORDER  = "taking_order"
    CLARIFYING    = "clarifying"
    CONFIRMING    = "confirming"
    PLACING_ORDER = "placing_order"
    DONE          = "done"


# ─── Internal types ───────────────────────────────────────────────────────────

class CartItem(BaseModel):
    product_id:   str
    name:         str
    quantity:     int
    unit_price:   float
    tax_rate:     float
    variant_id:   Optional[str] = None
    variant_name: Optional[str] = None
    notes:        Optional[str] = None


class NLUResult(BaseModel):
    intent:     Intent
    entities:   list[dict]
    language:   Language
    raw_text:   str
    confidence: float


# ─── API Request / Response ───────────────────────────────────────────────────

class VoiceOrderResponse(BaseModel):
    audio_base64:   str
    transcript:     str
    language:       Language
    intent:         Intent
    dialogue_state: DialogueState
    cart:           list[CartItem]
    response_text:  str
    session_id:     str


class ResetRequest(BaseModel):
    session_id: str


class ResetResponse(BaseModel):
    success: bool
    message: str


class HealthResponse(BaseModel):
    status:     str           # "ok" | "degraded"
    components: dict[str, str]
