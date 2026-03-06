# PetPooja — Voice Integration Context

> **Purpose**: This document provides the full context of the PetPooja codebase so your AI agent can understand the architecture, database schema, existing APIs, and the current voice scaffolding — then build/extend the voice features seamlessly.

---

## 1. Project Overview

**PetPooja** is an AI-powered restaurant management platform with:
- Dashboard, Orders, Products, Analytics, Revenue Intelligence, Inventory, Customers, Kitchen Display (KOT), and **Voice Ordering**
- Backend API (Node.js/Express) on **port 3000**
- Frontend (React + Vite + Tailwind CSS) on **port 5173**
- ML Service (FastAPI — Python) on **port 8000**
- PostgreSQL database (18 tables)

---

## 2. Tech Stack

| Layer | Technology | Port |
|-------|-----------|------|
| Frontend | React 18 + Vite 5 + Tailwind CSS + lucide-react icons | 5173 |
| Backend | Express.js 4.21 + pg (node-postgres) | 3000 |
| ML Service | FastAPI + uvicorn (serves pre-trained model outputs) | 8000 |
| Database | PostgreSQL 18 | 5432 |
| Auth | JWT (jsonwebtoken) + bcryptjs |  |

---

## 3. Folder Structure

```
Petpooja/
├── backend/
│   ├── .env                           # DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, JWT_SECRET, NODE_PORT, ML_SERVICE_URL
│   ├── package.json
│   └── src/
│       ├── app.js                     # Express app — mounts all routes, helmet, CORS, rate-limit
│       ├── config/
│       │   └── db.js                  # pg Pool using env vars
│       ├── middleware/
│       │   └── auth.js                # JWT Bearer token middleware — sets req.user
│       ├── controllers/
│       │   ├── authController.js      # signup, login
│       │   ├── menuController.js      # getItems, getVariants, getAddons, getCombos
│       │   ├── orderController.js     # list, today, create (auth), updateStatus (auth)
│       │   ├── dashboardController.js # kpis, hourlyOrders, topItems, weeklyRevenue
│       │   ├── revenueController.js   # contributionMargin, menuEngineering, topCombos, aov, priceRecommendations, anomalies, demandForecast, upsellRecommendations, upsellStats
│       │   ├── analyticsController.js # menuProfitability, comboRecommendations, underperformingItems, popularityScoring, hiddenStars, riskDetection, menuOptimization
│       │   ├── inventoryController.js # performanceSignals, alerts, log, stock, restock, addIngredient, updateIngredient
│       │   ├── customerController.js  # create, recalculateSegments, search, list, churnRisk, segments, getById
│       │   ├── kotController.js       # pending, updateKotStatus
│       │   ├── productsController.js  # list, get, categories, ingredients, create, update, remove
│       │   └── voiceController.js     # ⬅ EXISTING — transcribe, intent, processTurn, confirmOrder, getSession
│       ├── routes/
│       │   ├── auth.js, menu.js, orders.js, dashboard.js, revenue.js
│       │   ├── analytics.js, inventory.js, customers.js, kot.js, products.js
│       │   └── voice.js              # ⬅ EXISTING voice routes
│       └── services/
│           └── mlService.js           # axios wrapper: get(path) / post(path, body) → ML_SERVICE_URL
│
├── frontend/Frontend_mined/
│   ├── src/
│   │   ├── App.jsx                    # Routes (all under /dashboard)
│   │   ├── config.js                  # API_URL + apiFetch(path, options) helper
│   │   ├── components/
│   │   │   ├── AppLayout.jsx          # Layout wrapper with <Navbar> + <Outlet>
│   │   │   └── Navbar.jsx             # Sidebar nav — includes "Voice Ordering" link → /dashboard/voice
│   │   ├── context/
│   │   │   └── POSContext.jsx         # (wraps entire app)
│   │   └── pages/
│   │       ├── Dashboard.jsx, Orders.jsx, Products.jsx, Analytics.jsx
│   │       ├── Revenue.jsx, Inventory.jsx, Customers.jsx, KitchenDisplay.jsx
│   │       ├── Landing.jsx, Login.jsx, Signup.jsx
│   │       └── VoiceOrder.jsx         # ⬅ EXISTING — currently a DEMO-only page (hardcoded steps)
│
├── ml_service/
│   ├── main.py                        # FastAPI app — /health, /predict/anomalies, /predict/churn, /predict/demand, /predict/menu-optimization
│   ├── train.py                       # Training scripts
│   └── models/                        # Pre-trained .pkl files
│
├── schema.sql                         # Full DB schema (18 tables, 13 indexes)
├── final_static_seed.sql              # Seed data (menu, orders, customers, ingredients, recipes, etc.)
└── migrate_ingredients_recipes.sql    # One-time migration for ingredients + recipes
```

---

## 4. Environment Variables (backend/.env)

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=postgres
JWT_SECRET=change_this_to_a_strong_random_secret
NODE_PORT=3000
ML_SERVICE_URL=http://localhost:8000
```

---

## 5. Database Schema (All 18 Tables)

### 5.1 restaurants
```sql
CREATE TABLE restaurants (
    restaurant_id  SERIAL PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    address        TEXT,
    city           VARCHAR(50),
    cuisine_type   VARCHAR(50),
    gstin          VARCHAR(15),
    fssai_no       VARCHAR(20),
    opening_time   TIME DEFAULT '08:00:00',
    closing_time   TIME DEFAULT '23:00:00',
    seating_capacity INT DEFAULT 50,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.2 menu_categories
```sql
CREATE TABLE menu_categories (
    category_id   SERIAL PRIMARY KEY,
    name          VARCHAR(50) NOT NULL,
    display_order INT DEFAULT 0,
    is_active     BOOLEAN DEFAULT TRUE,
    meal_time     VARCHAR(20) DEFAULT 'all' CHECK (meal_time IN ('breakfast','lunch','dinner','all'))
);
```

### 5.3 menu_items
```sql
CREATE TABLE menu_items (
    item_id       SERIAL PRIMARY KEY,
    category_id   INT REFERENCES menu_categories(category_id),
    name          VARCHAR(100) NOT NULL,
    description   TEXT,
    is_veg        BOOLEAN DEFAULT TRUE,
    is_jain       BOOLEAN DEFAULT FALSE,
    is_available  BOOLEAN DEFAULT TRUE,
    display_order INT DEFAULT 0,
    tags          TEXT[],       -- {bestseller, spicy, new, chef_special}
    image_url     VARCHAR(255),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.4 menu_variants
```sql
CREATE TABLE menu_variants (
    variant_id     SERIAL PRIMARY KEY,
    item_id        INT REFERENCES menu_items(item_id),
    variant_name   VARCHAR(50) NOT NULL,   -- Half, Full, Small, Medium, Large, Single
    selling_price  NUMERIC(10,2) NOT NULL,
    food_cost      NUMERIC(10,2) NOT NULL,
    gst_pct        NUMERIC(4,2) DEFAULT 5.00 CHECK (gst_pct IN (0, 5, 12, 18)),
    is_available   BOOLEAN DEFAULT TRUE
);
```

### 5.5 menu_addons
```sql
CREATE TABLE menu_addons (
    addon_id      SERIAL PRIMARY KEY,
    item_id       INT REFERENCES menu_items(item_id),
    addon_name    VARCHAR(100) NOT NULL,
    extra_price   NUMERIC(10,2) DEFAULT 0,
    food_cost     NUMERIC(10,2) DEFAULT 0,
    is_available  BOOLEAN DEFAULT TRUE
);
```

### 5.6 menu_combos & combo_items
```sql
CREATE TABLE menu_combos (
    combo_id       SERIAL PRIMARY KEY,
    combo_name     VARCHAR(100) NOT NULL,
    description    TEXT,
    selling_price  NUMERIC(10,2) NOT NULL,
    food_cost      NUMERIC(10,2) NOT NULL,
    valid_from     DATE,
    valid_to       DATE,
    is_active      BOOLEAN DEFAULT TRUE
);

CREATE TABLE combo_items (
    combo_item_id  SERIAL PRIMARY KEY,
    combo_id       INT REFERENCES menu_combos(combo_id),
    item_id        INT REFERENCES menu_items(item_id),
    variant_id     INT REFERENCES menu_variants(variant_id),
    qty            INT DEFAULT 1
);
```

### 5.7 ingredients, recipes, inventory_log
```sql
CREATE TABLE ingredients (
    ing_id           SERIAL PRIMARY KEY,
    name             VARCHAR(100) NOT NULL,
    unit             VARCHAR(20) NOT NULL,   -- kg, litre, pieces, grams
    current_stock    NUMERIC(10,3) DEFAULT 0,
    min_stock        NUMERIC(10,3) DEFAULT 0,
    reorder_qty      NUMERIC(10,3) DEFAULT 0,
    cost_per_unit    NUMERIC(10,2) DEFAULT 0,
    last_restocked_at TIMESTAMP
);

CREATE TABLE recipes (
    recipe_id     SERIAL PRIMARY KEY,
    item_id       INT REFERENCES menu_items(item_id),
    variant_id    INT REFERENCES menu_variants(variant_id),
    ing_id        INT REFERENCES ingredients(ing_id),
    qty_required  NUMERIC(10,4) NOT NULL   -- per serving
);

CREATE TABLE inventory_log (
    log_id       SERIAL PRIMARY KEY,
    ing_id       INT REFERENCES ingredients(ing_id),
    change_type  VARCHAR(20) NOT NULL CHECK (change_type IN ('restock','consumed','wasted','adjusted')),
    qty_changed  NUMERIC(10,3) NOT NULL,
    reason       TEXT,
    logged_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.8 customers
```sql
CREATE TABLE customers (
    customer_id       SERIAL PRIMARY KEY,
    phone             VARCHAR(15) UNIQUE NOT NULL,
    name              VARCHAR(100),
    email             VARCHAR(100),
    dob               DATE,
    anniversary       DATE,
    is_veg            BOOLEAN DEFAULT FALSE,
    is_jain           BOOLEAN DEFAULT FALSE,
    allergies         TEXT[],
    loyalty_points    INT DEFAULT 0,
    total_visits      INT DEFAULT 0,
    total_spent       NUMERIC(12,2) DEFAULT 0,
    avg_order_val     NUMERIC(10,2) DEFAULT 0,
    first_visit       DATE,
    last_visit        DATE,
    favourite_item    VARCHAR(100),
    favourite_payment VARCHAR(20),
    churn_risk_score  NUMERIC(4,3) DEFAULT 0,   -- 0.000 to 1.000
    segment           VARCHAR(20) DEFAULT 'New' CHECK (segment IN ('VIP','Regular','Occasional','Lost','New')),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.9 offers
```sql
CREATE TABLE offers (
    offer_id           SERIAL PRIMARY KEY,
    name               VARCHAR(100) NOT NULL,
    type               VARCHAR(20) NOT NULL CHECK (type IN ('flat','pct','bogo','combo','happy_hour')),
    discount_value     NUMERIC(10,2) NOT NULL,
    min_order_val      NUMERIC(10,2) DEFAULT 0,
    applicable_items   INT[],
    applicable_channels TEXT[],
    valid_from         DATE NOT NULL,
    valid_to           DATE NOT NULL,
    usage_limit        INT DEFAULT 999999,
    used_count         INT DEFAULT 0,
    is_active          BOOLEAN DEFAULT TRUE
);
```

### 5.10 orders & order_items & order_addons & order_payments
```sql
CREATE TABLE orders (
    order_id        SERIAL PRIMARY KEY,
    restaurant_id   INT REFERENCES restaurants(restaurant_id),
    customer_id     INT REFERENCES customers(customer_id),   -- NULL for walk-ins
    placed_by       VARCHAR(100),                             -- staff name or 'voice_copilot'
    channel         VARCHAR(20) NOT NULL CHECK (channel IN ('dine_in','takeaway','zomato','swiggy','phone')),
    status          VARCHAR(20) DEFAULT 'delivered' CHECK (status IN ('placed','preparing','ready','delivered','cancelled')),
    placed_at       TIMESTAMP NOT NULL,
    delivered_at    TIMESTAMP,
    subtotal        NUMERIC(10,2) NOT NULL,
    discount_amt    NUMERIC(10,2) DEFAULT 0,
    tax_amt         NUMERIC(10,2) DEFAULT 0,
    total           NUMERIC(10,2) NOT NULL,
    payment_status  VARCHAR(20) DEFAULT 'paid' CHECK (payment_status IN ('paid','pending','failed','refunded'))
);

CREATE TABLE order_items (
    line_id              SERIAL PRIMARY KEY,
    order_id             INT REFERENCES orders(order_id),
    item_id              INT REFERENCES menu_items(item_id),
    variant_id           INT REFERENCES menu_variants(variant_id),
    qty                  INT NOT NULL DEFAULT 1,
    unit_price           NUMERIC(10,2),
    discount_pct         NUMERIC(5,2) DEFAULT 0,
    revenue              NUMERIC(10,2),
    food_cost            NUMERIC(10,2),
    gst_amt              NUMERIC(10,2),
    special_instructions TEXT
);

CREATE TABLE order_addons (
    addon_line_id  SERIAL PRIMARY KEY,
    line_id        INT REFERENCES order_items(line_id),
    addon_id       INT REFERENCES menu_addons(addon_id),
    qty            INT DEFAULT 1,
    price          NUMERIC(10,2)
);

CREATE TABLE order_payments (
    payment_id      SERIAL PRIMARY KEY,
    order_id        INT REFERENCES orders(order_id),
    method          VARCHAR(20) NOT NULL CHECK (method IN ('cash','card','upi','wallet','split')),
    amount          NUMERIC(10,2) NOT NULL,
    transaction_ref VARCHAR(100),
    paid_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.11 kot & kot_items
```sql
CREATE TABLE kot (
    kot_id        SERIAL PRIMARY KEY,
    order_id      INT REFERENCES orders(order_id),
    status        VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','preparing','ready','completed','cancelled')),
    priority      VARCHAR(10) DEFAULT 'normal' CHECK (priority IN ('low','normal','high','urgent')),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at  TIMESTAMP
);

CREATE TABLE kot_items (
    kot_item_id          SERIAL PRIMARY KEY,
    kot_id               INT REFERENCES kot(kot_id),
    item_id              INT REFERENCES menu_items(item_id),
    variant_id           INT REFERENCES menu_variants(variant_id),
    qty                  INT DEFAULT 1,
    addons               JSONB,
    special_instructions TEXT,
    status               VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','preparing','ready','served','cancelled'))
);
```

### 5.12 offer_redemptions & feedback
```sql
CREATE TABLE offer_redemptions (
    redemption_id    SERIAL PRIMARY KEY,
    offer_id         INT REFERENCES offers(offer_id),
    order_id         INT REFERENCES orders(order_id),
    customer_id      INT REFERENCES customers(customer_id),
    discount_applied NUMERIC(10,2),
    redeemed_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE feedback (
    feedback_id    SERIAL PRIMARY KEY,
    order_id       INT REFERENCES orders(order_id),
    customer_id    INT REFERENCES customers(customer_id),
    overall_rating INT CHECK (overall_rating BETWEEN 1 AND 5),
    food_rating    INT CHECK (food_rating BETWEEN 1 AND 5),
    service_rating INT CHECK (service_rating BETWEEN 1 AND 5),
    comment        TEXT,
    sentiment      VARCHAR(10) CHECK (sentiment IN ('positive','neutral','negative')),
    submitted_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. Complete API Route Map (47 endpoints)

| Route Group | Method | Path | Controller | Auth? |
|------------|--------|------|------------|-------|
| **Auth** | POST | `/api/auth/signup` | authController.signup | No |
| | POST | `/api/auth/login` | authController.login | No |
| **Menu** | GET | `/api/menu/items` | menuController.getItems | No |
| | GET | `/api/menu/variants/:item_id` | menuController.getVariants | No |
| | GET | `/api/menu/addons/:item_id` | menuController.getAddons | No |
| | GET | `/api/menu/combos` | menuController.getCombos | No |
| **Orders** | GET | `/api/orders/` | orderController.list | No |
| | GET | `/api/orders/today` | orderController.today | No |
| | POST | `/api/orders/` | orderController.create | **Yes** |
| | PUT | `/api/orders/:id/status` | orderController.updateStatus | **Yes** |
| **Dashboard** | GET | `/api/dashboard/kpis` | dashboardController.kpis | No |
| | GET | `/api/dashboard/hourly-orders` | dashboardController.hourlyOrders | No |
| | GET | `/api/dashboard/top-items` | dashboardController.topItems | No |
| | GET | `/api/dashboard/weekly-revenue` | dashboardController.weeklyRevenue | No |
| **Revenue** | GET | `/api/revenue/contribution-margin` | revenueController.contributionMargin | No |
| | GET | `/api/revenue/menu-engineering` | revenueController.menuEngineering | No |
| | GET | `/api/revenue/top-combos` | revenueController.topCombos | No |
| | GET | `/api/revenue/aov` | revenueController.aov | No |
| | GET | `/api/revenue/price-recommendations` | revenueController.priceRecommendations | No |
| | GET | `/api/revenue/anomalies` | revenueController.anomalies | No |
| | GET | `/api/revenue/demand-forecast` | revenueController.demandForecast | No |
| | GET | `/api/revenue/upsell-recommendations` | revenueController.upsellRecommendations | No |
| | GET | `/api/revenue/upsell-stats` | revenueController.upsellStats | No |
| **Analytics** | GET | `/api/analytics/menu-profitability` | analyticsController.menuProfitability | No |
| | GET | `/api/analytics/combo-recommendations` | analyticsController.comboRecommendations | No |
| | GET | `/api/analytics/underperforming-items` | analyticsController.underperformingItems | No |
| | GET | `/api/analytics/popularity-scoring` | analyticsController.popularityScoring | No |
| | GET | `/api/analytics/hidden-stars` | analyticsController.hiddenStars | No |
| | GET | `/api/analytics/risk-detection` | analyticsController.riskDetection | No |
| | GET | `/api/analytics/menu-optimization` | analyticsController.menuOptimization | No |
| **Inventory** | GET | `/api/inventory/performance-signals` | inventoryController.performanceSignals | No |
| | GET | `/api/inventory/alerts` | inventoryController.alerts | No |
| | GET | `/api/inventory/log` | inventoryController.log | No |
| | GET | `/api/inventory/stock` | inventoryController.stock | No |
| | POST | `/api/inventory/restock` | inventoryController.restock | No |
| | POST | `/api/inventory/ingredients` | inventoryController.addIngredient | No |
| | PUT | `/api/inventory/ingredients/:id` | inventoryController.updateIngredient | No |
| **Customers** | POST | `/api/customers/` | customerController.create | No |
| | POST | `/api/customers/recalculate-segments` | customerController.recalculateSegments | No |
| | GET | `/api/customers/search` | customerController.search | No |
| | GET | `/api/customers/list` | customerController.list | No |
| | GET | `/api/customers/churn-risk` | customerController.churnRisk | No |
| | GET | `/api/customers/segments` | customerController.segments | No |
| | GET | `/api/customers/:id` | customerController.getById | No |
| **KOT** | GET | `/api/kot/pending` | kotController.pending | No |
| | PUT | `/api/kot/:id/status` | kotController.updateKotStatus | No |
| **Products** | GET | `/api/products/` | productsController.list | No |
| | GET | `/api/products/categories` | productsController.categories | No |
| | GET | `/api/products/ingredients` | productsController.ingredients | No |
| | GET | `/api/products/:id` | productsController.get | No |
| | POST | `/api/products/` | productsController.create | No |
| | PUT | `/api/products/:id` | productsController.update | No |
| | DELETE | `/api/products/:id` | productsController.remove | No |
| **Voice** | POST | `/api/voice/transcribe` | voiceController.transcribe | No |
| | POST | `/api/voice/intent` | voiceController.intent | No |
| | POST | `/api/voice/process-turn` | voiceController.processTurn | No |
| | POST | `/api/voice/confirm-order` | voiceController.confirmOrder | **Yes** |
| | GET | `/api/voice/session/:session_id` | voiceController.getSession | No |
| **Health** | GET | `/api/health` | inline | No |

---

## 7. Existing Voice Backend (voiceController.js) — FULL CODE

The voice controller already has the scaffolding for a complete voice pipeline. It uses an in-memory session map and proxies to the ML service.

```js
const db = require('../config/db');
const mlService = require('../services/mlService');
const crypto = require('crypto');

const sessions = new Map();

// POST /api/voice/transcribe — proxy to ML service
exports.transcribe = async (req, res, next) => {
  try {
    const mlResult = await mlService.post('/voice/transcribe', req.body);
    if (mlResult) return res.json(mlResult);
    res.status(503).json({ error: 'ML service unavailable. Start FastAPI on port 8000.' });
  } catch (err) { next(err); }
};

// POST /api/voice/intent — proxy to ML service for intent detection
exports.intent = async (req, res, next) => {
  try {
    const mlResult = await mlService.post('/predict/intent', req.body);
    if (mlResult) return res.json(mlResult);
    res.status(503).json({ error: 'ML service unavailable. Start FastAPI on port 8000.' });
  } catch (err) { next(err); }
};

// POST /api/voice/process-turn — multi-turn conversation handler
// Accepts: { text, session_id? }
// Returns: { session_id, transcript, intent, items[], message }
exports.processTurn = async (req, res, next) => {
  try {
    const { text, session_id } = req.body;
    const sid = session_id || crypto.randomUUID();
    if (!sessions.has(sid)) {
      sessions.set(sid, { session_id: sid, items: [], created_at: new Date() });
    }
    const session = sessions.get(sid);
    const mlResult = await mlService.post('/voice/process-turn', {
      text, session_id: sid, current_items: session.items,
    });
    if (mlResult) {
      if (mlResult.items) session.items = mlResult.items;
      sessions.set(sid, session);
      return res.json({ ...mlResult, session_id: sid });
    }
    res.json({
      session_id: sid, transcript: text, intent: 'unknown',
      items: session.items, message: 'ML service unavailable — voice pipeline not active',
    });
  } catch (err) { next(err); }
};

// POST /api/voice/confirm-order — converts voice session → real order + KOT
// Requires auth (Bearer token). Body: { session_id, customer_id?, channel? }
// Creates: orders row → order_items rows → kot row → kot_items rows
exports.confirmOrder = async (req, res, next) => {
  const client = await db.pool.connect();
  try {
    const { session_id, customer_id, channel } = req.body;
    const session = sessions.get(session_id);
    if (!session || session.items.length === 0) {
      return res.status(400).json({ error: 'No active voice session or empty cart' });
    }
    await client.query('BEGIN');
    let subtotal = 0, totalTax = 0;
    const resolvedItems = [];
    for (const item of session.items) {
      const vRes = await client.query(
        'SELECT selling_price, food_cost, gst_pct FROM menu_variants WHERE variant_id = $1',
        [item.variant_id]
      );
      if (vRes.rows.length === 0) continue;
      const v = vRes.rows[0];
      const qty = item.qty || 1;
      const lineRevenue = parseFloat(v.selling_price) * qty;
      const lineCost = parseFloat(v.food_cost) * qty;
      const lineGst = lineRevenue * parseFloat(v.gst_pct) / 100;
      subtotal += lineRevenue; totalTax += lineGst;
      resolvedItems.push({
        item_id: item.item_id, variant_id: item.variant_id, qty,
        unit_price: parseFloat(v.selling_price), revenue: lineRevenue,
        food_cost: lineCost, gst_amt: lineGst,
        special_instructions: item.special_instructions || null,
      });
    }
    const total = subtotal + totalTax;
    const orderRes = await client.query(
      `INSERT INTO orders (restaurant_id, customer_id, placed_by, channel, status,
        placed_at, subtotal, discount_amt, tax_amt, total, payment_status)
       VALUES (1, $1, 'voice_copilot', $2, 'placed', NOW(), $3, 0, $4, $5, 'pending')
       RETURNING order_id`,
      [customer_id || null, channel || 'dine_in', subtotal, totalTax, total]
    );
    const orderId = orderRes.rows[0].order_id;
    for (const ri of resolvedItems) {
      await client.query(
        `INSERT INTO order_items (order_id, item_id, variant_id, qty, unit_price,
          discount_pct, revenue, food_cost, gst_amt, special_instructions)
         VALUES ($1,$2,$3,$4,$5,0,$6,$7,$8,$9)`,
        [orderId, ri.item_id, ri.variant_id, ri.qty, ri.unit_price,
         ri.revenue, ri.food_cost, ri.gst_amt, ri.special_instructions]
      );
    }
    const kotRes = await client.query(
      `INSERT INTO kot (order_id, status, priority, created_at) VALUES ($1, 'pending', 'normal', NOW()) RETURNING kot_id`,
      [orderId]
    );
    const kotId = kotRes.rows[0].kot_id;
    for (const ri of resolvedItems) {
      await client.query(
        `INSERT INTO kot_items (kot_id, item_id, variant_id, qty, special_instructions, status)
         VALUES ($1,$2,$3,$4,$5,'pending')`,
        [kotId, ri.item_id, ri.variant_id, ri.qty, ri.special_instructions]
      );
    }
    await client.query('COMMIT');
    sessions.delete(session_id);
    res.status(201).json({ order_id: orderId, kot_id: kotId, total, status: 'placed' });
  } catch (err) {
    await client.query('ROLLBACK');
    next(err);
  } finally { client.release(); }
};

// GET /api/voice/session/:session_id — get current session state
exports.getSession = async (req, res) => {
  const session = sessions.get(req.params.session_id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  res.json(session);
};
```

---

## 8. Existing Voice Routes (voice.js)

```js
const express = require('express');
const router = express.Router();
const vc = require('../controllers/voiceController');
const auth = require('../middleware/auth');

router.post('/transcribe', vc.transcribe);
router.post('/intent', vc.intent);
router.post('/process-turn', vc.processTurn);
router.post('/confirm-order', auth, vc.confirmOrder);
router.get('/session/:session_id', vc.getSession);

module.exports = router;
```

---

## 9. ML Service Proxy (mlService.js)

All ML calls go through this. The voice controller uses `mlService.post()`.

```js
const axios = require('axios');

const ML_URL = process.env.ML_SERVICE_URL || 'http://localhost:8000';
const TIMEOUT = 10000;

async function get(path) {
  try {
    const resp = await axios.get(`${ML_URL}${path}`, { timeout: TIMEOUT });
    return resp.data;
  } catch { return null; }
}

async function post(path, body) {
  try {
    const resp = await axios.post(`${ML_URL}${path}`, body, { timeout: TIMEOUT });
    return resp.data;
  } catch { return null; }
}

module.exports = { get, post };
```

---

## 10. Current ML Service Endpoints (FastAPI — port 8000)

These exist today. Voice endpoints (`/voice/transcribe`, `/voice/process-turn`, `/predict/intent`) are expected by the backend but **NOT yet implemented** in the ML service.

| Endpoint | Method | Status |
|----------|--------|--------|
| `/health` | GET | ✅ Working |
| `/predict/anomalies` | GET | ✅ Working |
| `/predict/churn` | GET | ✅ Working |
| `/predict/demand` | GET | ✅ Working |
| `/predict/menu-optimization` | GET | ✅ Working |
| `/voice/transcribe` | POST | ❌ NOT IMPLEMENTED |
| `/voice/process-turn` | POST | ❌ NOT IMPLEMENTED |
| `/predict/intent` | POST | ❌ NOT IMPLEMENTED |

---

## 11. Frontend VoiceOrder.jsx — Current State

The current `VoiceOrder.jsx` page at `/dashboard/voice` is a **demo-only** page:
- Uses hardcoded `DEMO_STEPS` and `DEMO_ITEMS` with setTimeout timers
- Simulates listening → processing → detected items flow
- Has UI for upsell suggestions (pulls real data from `/api/revenue/top-combos`)
- Has an order summary sidebar with confirm button
- **Does NOT** use the Web Speech API or any real mic input
- **Does NOT** call `/api/voice/process-turn` or `/api/voice/confirm-order`

---

## 12. Frontend API Helper

All API calls use this helper from `frontend/Frontend_mined/src/config.js`:

```js
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api';

export async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('token');
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `API ${res.status}`);
  }
  return res.json();
}
```

**Usage**: `apiFetch('/voice/process-turn', { method: 'POST', body: JSON.stringify({ text, session_id }) })`

---

## 13. Order Creation Flow (How Orders Work)

When a voice order is confirmed via `POST /api/voice/confirm-order`:

1. Reads session items (each has `item_id`, `variant_id`, `qty`, `special_instructions`)
2. Looks up `selling_price`, `food_cost`, `gst_pct` from `menu_variants`
3. Inserts into `orders` (placed_by = 'voice_copilot', status = 'placed')
4. Inserts each item into `order_items`
5. Creates a `kot` row (Kitchen Order Ticket) with status 'pending'
6. Creates `kot_items` rows for kitchen display
7. **Inventory deduction** happens automatically in `orderController.create` (step 7) — queries `recipes` table, deducts `current_stock` from `ingredients`, logs to `inventory_log`

> **Note**: The `confirmOrder` in voiceController does NOT currently deduct inventory. If you want voice orders to also deduct inventory, you should add the same recipe-based deduction logic from `orderController.create`.

---

## 14. Relevant Menu Data Structure

The database has **30 menu items** across **8 categories** with **~50 variants**:

**Categories**: Starters, Soups, Main Course North Indian, Main Course South Indian, Breads, Rice & Biryani, Beverages, Desserts

**Example items with variants**:
- Paneer Tikka → Half (₹220), Full (₹380)
- Butter Chicken → Half (₹220), Full (₹380)
- Chicken Biryani → Half (₹220), Full (₹380)
- Butter Naan → Single (₹45)
- Sweet Lassi → Small (₹80), Large (₹130)
- Gulab Jamun → 2 Pieces (₹60), 4 Pieces (₹110)

---

## 15. What Needs to Be Built (Voice Features)

The backend scaffolding is ready. What's needed:

### ML Service (FastAPI — port 8000)
- `POST /voice/transcribe` — Accept audio/text, return transcript (Hindi/English/regional)
- `POST /voice/process-turn` — Accept `{ text, session_id, current_items }`, return `{ items, intent, message }`
- `POST /predict/intent` — NLU intent classification (add_item, remove_item, modify_qty, confirm, cancel, etc.)

### Frontend (VoiceOrder.jsx)
- Replace demo with real Web Speech API or mic capture
- Call `/api/voice/process-turn` with real transcripts
- Handle multi-turn conversation (add, modify, remove items)
- Call `/api/voice/confirm-order` to place the order
- Real-time cart updates from session state

### Backend (voiceController.js)
- Already functional — may need enhancements for:
  - Inventory deduction on voice order confirm
  - Customer lookup/linking
  - Payment handling
  - Error recovery in conversation flow

---

## 16. How to Run the Project

```bash
# 1. Database — run in pgAdmin:
#    schema.sql → final_static_seed.sql → migrate_ingredients_recipes.sql

# 2. Backend
cd backend
npm install
npm run dev          # starts on port 3000

# 3. ML Service
cd ml_service
pip install fastapi uvicorn    # (or use the .venv)
python main.py                 # starts on port 8000

# 4. Frontend
cd frontend/Frontend_mined
npm install
npm run dev          # starts on port 5173
```

---

## 17. Backend Dependencies (package.json)

```json
{
  "express": "^4.21.0",
  "pg": "^8.13.0",
  "cors": "^2.8.5",
  "dotenv": "^16.4.5",
  "bcryptjs": "^2.4.3",
  "jsonwebtoken": "^9.0.2",
  "helmet": "^8.0.0",
  "express-rate-limit": "^7.4.1",
  "axios": "^1.7.7"
}
```

---

## 18. Key Conventions

- **Controller pattern**: `exports.methodName = async (req, res, next) => { try { ... } catch(err) { next(err) } }`
- **DB queries**: `const { rows } = await db.query('SELECT ...', [params])`
- **Frontend fetch**: `apiFetch('/path')` for GET, `apiFetch('/path', { method: 'POST', body: JSON.stringify(data) })` for POST
- **Auth**: JWT stored in `localStorage.getItem('token')`, sent as `Authorization: Bearer <token>`
- **Styling**: Tailwind CSS with custom classes: `card`, `btn-primary`, `btn-secondary`, `animate-fade-in`, `animate-slide-up`
- **Icons**: lucide-react
- **No TypeScript** — everything is plain JavaScript / JSX
