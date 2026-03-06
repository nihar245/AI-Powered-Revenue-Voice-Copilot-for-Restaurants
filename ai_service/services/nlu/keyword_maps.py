# ─────────────────────────────────────────────────────────────────────────────
# Keyword maps for EN / HI / GU / Hinglish intent detection
# ─────────────────────────────────────────────────────────────────────────────

GREET_KEYWORDS = {
    "en": ["hello", "hi", "hey", "good morning", "good evening", "good afternoon"],
    "hi": ["namaste", "namaskar", "hello", "hi", "namskar"],
    "gu": ["kem cho", "namaste", "jai shri krishna", "hello"],
}

ADD_KEYWORDS = {
    "en": ["want", "order", "give me", "i'd like", "i would like", "can i have",
           "get me", "add", "bring", "i'll have", "i'll take"],
    "hi": ["chahiye", "dena", "lena", "lao", "laao", "mangwana", "order karna",
           "order chahiye", "milega", "milegi", "de do", "de dena", "dijiye"],
    "gu": ["joie", "apo", "lavo", "mangavi", "khavis", "aaps"],
}

REMOVE_KEYWORDS = {
    "en": ["remove", "cancel", "don't want", "take off", "delete", "not that"],
    "hi": ["nahi chahiye", "hatao", "cancel karo", "wapas karo", "nahi lena", "mat lao"],
    "gu": ["nathi joitu", "hatavo", "cancel karo", "nahi joie"],
}

CONFIRM_KEYWORDS = {
    "en": ["confirm", "yes", "that's all", "done", "place order", "ok", "sure",
           "go ahead", "all good", "i'm done"],
    "hi": ["haan", "ha", "confirm", "theek hai", "ho gaya", "bas", "pakka",
           "bilkul", "kar do", "place karo", "order kar do"],
    "gu": ["ha", "saru che", "confirm", "bas", "thay gyu", "karo", "theek che"],
}

CANCEL_KEYWORDS = {
    "en": ["cancel", "no", "nothing", "forget it", "nevermind", "stop", "quit"],
    "hi": ["nahi", "cancel", "rehne do", "band karo", "mat lao", "chhod do"],
    "gu": ["na", "cancel", "rehva do", "chhod do"],
}

VIEW_MENU_KEYWORDS = {
    "en": ["menu", "what do you have", "what's available", "show menu",
           "what can i order", "what's there"],
    "hi": ["menu", "kya hai", "kya milta", "dikhaao", "options", "kya kya hai",
           "menu dikhao", "kya kya milta hai"],
    "gu": ["menu", "shu che", "shu male", "dekhado", "menu batao"],
}

VIEW_CART_KEYWORDS = {
    "en": ["cart", "what did i order", "my order", "summary", "total", "bill",
           "what have i ordered"],
    "hi": ["cart", "kya order kiya", "mera order", "total", "kitna hua",
           "bata", "order dikhao", "mujhe batao"],
    "gu": ["cart", "shu order karyun", "maro order", "total", "ketlu thayun"],
}

ENQUIRE_PRICE_KEYWORDS = {
    "en": ["price", "cost", "how much", "rate", "how much does"],
    "hi": ["price", "kitne ka", "kitna", "daam", "rate", "paisa", "kitne mein"],
    "gu": ["bhav", "ketla", "keto", "rate", "keto rupiya"],
}

# ─── Number word → digit mapping (EN + HI + GU) ──────────────────────────────
NUMBER_WORDS: dict[str, int] = {
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    # Hindi (Devanagari romanised)
    "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5,
    "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    # Gujarati (romanised)
    "be": 2, "tran": 3, "panch": 5, "chha": 6, "sat": 7,
    "aath": 8, "nav": 9,
}
