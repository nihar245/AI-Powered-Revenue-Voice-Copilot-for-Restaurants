# PetPooja — AI-Powered Revenue & Voice Copilot
> Context file for GitHub Copilot / Claude in VS Code
> Read this fully before generating any code

---

## 1. Project Overview

**Hackathon Problem Statement:**
Build an AI-powered revenue intelligence engine and voice ordering copilot for restaurants using PetPooja's POS ecosystem.

**Two Core Modules:**
- **Module 1 — Revenue Intelligence Engine**: Analyses POS data to give actionable profitability insights, menu optimization, demand forecasting and anomaly detection
- **Module 2 — AI Voice Ordering Copilot**: Accepts voice input from customers, understands intent, maps to menu, handles modifiers, suggests upsells and generates a structured KOT (Kitchen Order Ticket)

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL (pgAdmin, local) |
| Backend API | Node.js + Express.js |
| ML Service | Python + FastAPI |
| ML Models | LightGBM, XGBoost, Isolation Forest, DistilBERT, Sentence Transformers, FAISS |
| Voice STT | OpenAI Whisper (local, open source) |
| Voice TTS | gTTS |
| ORM / DB Client | pg (node-postgres) |
| Language | Node.js (backend), Python 3.10 (ML service) |

---

## 3. Database Schema — 18 Tables (PostgreSQL)

### Static Tables (menu + config — never truncated)
```
restaurants         — single restaurant record
menu_categories     — Starter, Main, Bread, Rice, Drink, Dessert
menu_items          — 30 items with tags (bestseller, spicy, chef_special)
menu_variants       — Half/Full, Small/Large, Single per item (52 variants total)
menu_addons         — extra cheese, extra gravy etc per item (15 addons)
menu_combos         — 8 meal deals / combo offers
combo_items         — items inside each combo
ingredients         — 25 raw ingredients with stock levels
recipes             — ingredient qty per item/variant (BOM)
offers              — 10 offers: flat, pct, bogo, happy_hour
```

### Transactional Tables (generated synthetic data)
```
customers           — 500 customers with segment, churn_risk, favourite_item
orders              — ~30,000 orders (1 year, 2024)
order_items         — ~75,000 line items with revenue, food_cost, gst_amt
order_addons        — ~15,000 addon records
order_payments      — ~32,000 payment records (cash/upi/card/wallet)
kot                 — Kitchen Order Tickets (1 per order)
kot_items           — KOT line items
offer_redemptions   — ~3,000 offer usages
feedback            — ~9,000 ratings (1-5) with sentiment
inventory_log       — consumed/restock/wasted entries
```

### Key Relationships
```
orders → customers (customer_id, nullable — walk-ins allowed)
orders → order_items → menu_items → menu_variants
order_items → order_addons → menu_addons
orders → kot → kot_items
orders → order_payments
orders → offer_redemptions → offers
orders → feedback
order_items → recipes → ingredients → inventory_log
```

### Important Field Notes
- `orders.channel` — dine_in / takeaway / zomato / swiggy / phone
- `menu_variants.food_cost` — cost to make (used for contribution margin)
- `customers.churn_risk_score` — 0.0 to 1.0
- `customers.segment` — VIP / Regular / Occasional / Lost / New
- `feedback.sentiment` — positive / neutral / negative
- `kot.priority` — normal / urgent
- All monetary values in INR (₹)
- GST rate is 5% on all food items

---

## 4. Project Folder Structure

```
petpooja/
├── backend/                    ← Node.js Express API
│   ├── src/
│   │   ├── config/
│   │   │   └── db.js           ← PostgreSQL pool connection
│   │   ├── routes/
│   │   │   ├── revenue.js      ← Module 1 endpoints
│   │   │   ├── voice.js        ← Module 2 endpoints
│   │   │   ├── menu.js         ← Menu CRUD
│   │   │   ├── orders.js       ← Order management
│   │   │   └── inventory.js    ← Inventory alerts
│   │   ├── controllers/
│   │   │   ├── revenueController.js
│   │   │   ├── voiceController.js
│   │   │   ├── menuController.js
│   │   │   ├── orderController.js
│   │   │   └── inventoryController.js
│   │   ├── services/
│   │   │   └── mlService.js    ← axios calls to Python FastAPI
│   │   └── app.js
│   ├── .env
│   └── package.json
│
├── ml_service/                 ← Python FastAPI ML service
│   ├── models/                 ← saved .pkl / .keras model files
│   ├── routers/
│   │   ├── revenue.py          ← demand forecast, anomaly, churn
│   │   └── voice.py            ← intent, item extractor, upsell
│   ├── services/
│   │   ├── demand_forecast.py
│   │   ├── anomaly_detection.py
│   │   ├── churn_prediction.py
│   │   ├── intent_classifier.py
│   │   ├── item_extractor.py
│   │   └── upsell_engine.py
│   ├── db.py                   ← SQLAlchemy connection to PostgreSQL
│   └── main.py
│
├── data/
│   ├── 01_schema.sql
│   ├── 02_seed_static.sql
│   └── generate_data_final.py
│
└── PROJECT_CONTEXT.md          ← this file
```

---

## 5. API Endpoints

### Module 1 — Revenue Intelligence
```
GET  /api/revenue/contribution-margin        → item-level margin analysis
GET  /api/revenue/menu-engineering           → Stars/Puzzles/Plowhorses/Dogs matrix
GET  /api/revenue/top-combos                 → association rules based combos
GET  /api/revenue/aov                        → avg order value by channel/time
GET  /api/revenue/anomalies                  → daily revenue anomaly flags
GET  /api/revenue/demand-forecast            → next 7 days item demand
GET  /api/revenue/price-recommendations      → suggested price changes
GET  /api/inventory/alerts                   → low stock warnings
GET  /api/customers/churn-risk               → customers likely to churn
```

### Module 2 — Voice Copilot
```
POST /api/voice/transcribe                   → audio file → text (Whisper)
POST /api/voice/intent                       → text → intent label + confidence
POST /api/voice/process-turn                 → full pipeline: text → response + order state
POST /api/voice/confirm-order                → finalise order → create KOT in DB
GET  /api/voice/session/:session_id          → get current order session state
```

### General
```
GET  /api/menu/items                         → all menu items with variants
GET  /api/menu/variants/:item_id             → variants for specific item
GET  /api/orders/today                       → today's orders summary
POST /api/orders                             → create new order
GET  /api/kot/pending                        → pending KOTs for kitchen display
```

---

## 6. ML Models — What Each Does

| Model | Type | Input | Output | Retrain |
|---|---|---|---|---|
| LightGBM Demand | Regression | day, hour, month, lags, festival flags | predicted qty per item | Monthly |
| Isolation Forest | Unsupervised | daily revenue, orders, AOV | anomaly score 0-1 | Monthly |
| XGBoost Churn | Classification | days_since_visit, visits, spend | churn probability | When customer base grows 20% |
| DistilBERT Intent | NLP Classification | voice text (Hindi+English) | intent label | Only if new intents added |
| Sentence Transformer + FAISS | Semantic Search | spoken item name | matched menu_item | On menu change |

### Critical Rule — No Hardcoded Values
```python
# WRONG
BUTTER_CHICKEN_PRICE = 380
HIGH_MARGIN_THRESHOLD = 200

# RIGHT — always read from DB
price = db.query("SELECT selling_price FROM menu_variants WHERE variant_id = %s", [vid])
threshold = df['contribution_margin'].median()  # computed from live data
```

---

## 7. Node ↔ Python Communication

```
Node.js (port 3000)  →  HTTP POST  →  Python FastAPI (port 8000)

Example:
const res = await axios.post('http://localhost:8000/predict/intent', {
  text: 'mujhe butter chicken chahiye'
})
// returns: { intent: 'place_order', confidence: 0.97 }
```

---

## 8. Voice Pipeline Flow

```
Customer speaks
      ↓
Whisper STT  →  transcribed text
      ↓
DistilBERT   →  intent (place_order / add_item / confirm / cancel ...)
      ↓
FAISS Item Extractor  →  matched menu item + variant
      ↓
Modifier Handler  →  spice level, extras, removals
      ↓
Upsell Engine  →  suggest high-margin associated item
      ↓
Order Session State  →  add/remove/modify items
      ↓
confirm_order  →  INSERT into orders + order_items + KOT
      ↓
gTTS  →  spoken response back to customer
```

### Voice Intents (15 total)
```
place_order, add_item, remove_item, modify_item,
ask_price, ask_availability, ask_recommendation,
confirm_order, cancel_order, repeat_order,
ask_combo, ask_time, ask_ingredients,
greeting, goodbye
```

---

## 9. Business Logic Rules

**Menu Engineering Classification:**
```
STAR       → sales_velocity >= median AND cm_per_unit >= median → promote aggressively
PUZZLE     → sales_velocity <  median AND cm_per_unit >= median → improve visibility
PLOWHORSE  → sales_velocity >= median AND cm_per_unit <  median → reprice or cut cost
DOG        → sales_velocity <  median AND cm_per_unit <  median → consider removing
```
*Medians are always computed dynamically from current DB data*

**Price Optimization:**
```
PUZZLE items    → suggest price * 0.92  (8% reduction to boost volume)
PLOWHORSE items → suggest price * 1.07  (7% increase to improve margin)
```

**Upsell Scoring:**
```
combo_score = lift × confidence × consequent_cm_per_unit
Suggest top 2 items not already in cart
```

**Customer Segments:**
```
VIP        → total_spent > 15000 AND total_visits > 20
Regular    → total_visits > 10
Lost       → days_since_last_visit > 90
New        → total_visits <= 2
Occasional → everything else
```

**Churn Risk:**
```
churn_risk_score = min(1.0, days_since_last_visit / 180)
High risk = score > 0.6
```

---

## 10. Environment Variables (.env)

```
# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=petpooja
DB_USER=postgres
DB_PASSWORD=your_password

# Service ports
NODE_PORT=3000
ML_SERVICE_URL=http://localhost:8000

# ML Model paths
MODEL_DIR=../ml_service/models
```

---

## 11. Coding Conventions

- All DB queries use parameterised queries — never string interpolation
- All monetary calculations use `NUMERIC(10,2)` — never floats
- All timestamps stored in UTC
- Node controllers are thin — business logic lives in services
- Python ML functions always accept a `db_conn` parameter — never open their own connection
- Every ML endpoint returns `{ result, confidence, timestamp }` minimum
- Voice session state is in-memory per call — not persisted to DB until confirmed

---

## 12. What Has Already Been Done

- [x] PostgreSQL schema created (18 tables)
- [x] Static seed data inserted (menu, ingredients, recipes, offers)
- [x] Synthetic transactional data generated (~270,000 rows)
- [x] All sequences reset (safe for Express inserts)
- [ ] Node.js backend — to be built
- [ ] Python FastAPI ML service — to be built
- [ ] ML model training — to be done
- [ ] Frontend dashboard — to be built
- [ ] Voice interface — to be built