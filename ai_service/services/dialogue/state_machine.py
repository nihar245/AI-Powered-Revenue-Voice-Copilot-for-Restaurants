from models.schemas import DialogueState, Intent

# ─── Valid state transitions ──────────────────────────────────────────────────
_TRANSITIONS: dict[tuple[DialogueState, Intent], DialogueState] = {
    # From GREETING
    (DialogueState.GREETING, Intent.GREETING):          DialogueState.TAKING_ORDER,
    (DialogueState.GREETING, Intent.ADD_ITEM):          DialogueState.TAKING_ORDER,
    (DialogueState.GREETING, Intent.VIEW_MENU):         DialogueState.TAKING_ORDER,
    (DialogueState.GREETING, Intent.UNKNOWN):           DialogueState.TAKING_ORDER,

    # From TAKING_ORDER
    (DialogueState.TAKING_ORDER, Intent.ADD_ITEM):      DialogueState.TAKING_ORDER,
    (DialogueState.TAKING_ORDER, Intent.REMOVE_ITEM):   DialogueState.TAKING_ORDER,
    (DialogueState.TAKING_ORDER, Intent.VIEW_CART):     DialogueState.TAKING_ORDER,
    (DialogueState.TAKING_ORDER, Intent.VIEW_MENU):     DialogueState.TAKING_ORDER,
    (DialogueState.TAKING_ORDER, Intent.ENQUIRE_PRICE): DialogueState.TAKING_ORDER,
    (DialogueState.TAKING_ORDER, Intent.CONFIRM_ORDER): DialogueState.CONFIRMING,
    (DialogueState.TAKING_ORDER, Intent.CANCEL_ORDER):  DialogueState.DONE,

    # From CLARIFYING
    (DialogueState.CLARIFYING, Intent.ADD_ITEM):        DialogueState.TAKING_ORDER,
    (DialogueState.CLARIFYING, Intent.CONFIRM_ORDER):   DialogueState.CONFIRMING,
    (DialogueState.CLARIFYING, Intent.UNKNOWN):         DialogueState.CLARIFYING,

    # From CONFIRMING
    (DialogueState.CONFIRMING, Intent.CONFIRM_ORDER):   DialogueState.PLACING_ORDER,
    (DialogueState.CONFIRMING, Intent.CANCEL_ORDER):    DialogueState.TAKING_ORDER,
    (DialogueState.CONFIRMING, Intent.ADD_ITEM):        DialogueState.TAKING_ORDER,

    # PLACING_ORDER and DONE are terminal — reset resets to GREETING
}


class DialogueSession:
    def __init__(self, session_id: str, table_id: str):
        self.session_id              = session_id
        self.table_id                = table_id
        self.state                   = DialogueState.GREETING
        self.cart:        list[dict] = []
        self.language:    str        = "en"
        self.last_response:    str   = ""
        self.clarification_context: dict = {}

    def transition(self, intent: Intent) -> DialogueState:
        key       = (self.state, intent)
        new_state = _TRANSITIONS.get(key)
        if new_state:
            self.state = new_state
        elif self.state in (DialogueState.DONE, DialogueState.PLACING_ORDER):
            pass  # stay terminal until explicitly reset
        else:
            # Unknown transition — stay in current state
            pass
        return self.state

    def reset(self) -> None:
        self.state                   = DialogueState.GREETING
        self.cart                    = []
        self.language                = "en"
        self.last_response           = ""
        self.clarification_context   = {}


# ─── In-memory session registry (single-process) ─────────────────────────────
_sessions: dict[str, DialogueSession] = {}


def get_or_create_session(session_id: str, table_id: str = "") -> DialogueSession:
    if session_id not in _sessions:
        _sessions[session_id] = DialogueSession(session_id, table_id)
    return _sessions[session_id]


def reset_session(session_id: str) -> None:
    if session_id in _sessions:
        _sessions[session_id].reset()
