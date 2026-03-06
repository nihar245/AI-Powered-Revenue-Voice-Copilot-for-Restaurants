# PetPooja Backend — Coverage Gap Analysis
_Last updated: Module 1 complete_

---

## Endpoint Coverage Summary

### ✅ Frontend-Connected Endpoints

| Endpoint | Frontend Page | Status |
|----------|--------------|--------|
| `POST /api/auth/signup` | Signup.jsx | ✅ Done — frontend still uses setTimeout mock; real endpoint ready |
| `POST /api/auth/login` | Login.jsx | ✅ Done — frontend still uses setTimeout mock; real endpoint ready |
| `GET /api/menu/items` | Orders.jsx | ✅ Done |
| `GET /api/orders` | Orders.jsx | ✅ Done |
| `POST /api/orders` | Orders.jsx | ✅ Done |
| `PUT /api/orders/:id/status` | Orders.jsx | ✅ Done |
| `GET /api/dashboard/kpis` | Dashboard.jsx | ✅ Done |
| `GET /api/dashboard/hourly-orders` | Dashboard.jsx | ✅ Done |
| `GET /api/dashboard/top-items` | Dashboard.jsx | ✅ Done |
| `GET /api/dashboard/weekly-revenue` | Dashboard.jsx | ✅ Done |
| `GET /api/analytics/menu-profitability` | Analytics.jsx | ✅ Done |
| `GET /api/analytics/combo-recommendations` | Analytics.jsx | ✅ Done |
| `GET /api/analytics/underperforming-items` | Analytics.jsx | ✅ Done |
| `GET /api/analytics/popularity-scoring` | Analytics.jsx (Popularity tab) | ✅ Done — Module 1 |
| `GET /api/analytics/hidden-stars` | Analytics.jsx (Hidden Stars tab) | ✅ Done — Module 1 |
| `GET /api/analytics/risk-detection` | Analytics.jsx (Risk tab) | ✅ Done — Module 1 |
| `GET /api/revenue/contribution-margin` | Revenue.jsx | ✅ Done — Module 1 |
| `GET /api/revenue/price-recommendations` | Revenue.jsx | ✅ Done — Module 1 |
| `GET /api/revenue/aov` | Revenue.jsx (AOV tab) | ✅ Done — Module 1 (byChannel, byDay, byHour, byPaymentMethod, byWeekType) |
| `GET /api/inventory/performance-signals` | Inventory.jsx | ✅ Done — Module 1 |
| `GET /api/inventory/alerts` | Inventory.jsx | ✅ Done |
| `GET /api/inventory/stock` | Inventory.jsx | ✅ Done |
| `GET /api/customers/churn-risk` | Customers.jsx | ✅ Done |
| `GET /api/customers/segments` | Customers.jsx | ✅ Done |
| `POST /api/voice/transcribe` | VoiceOrder.jsx | ✅ Done (proxy to ML — returns 503 when ML offline) |
| `POST /api/voice/process-turn` | VoiceOrder.jsx | ✅ Done (proxy to ML — returns session with "ML unavailable") |

---

### ⚠️ Backend-Only Endpoints (endpoint done, no frontend page yet)

| Endpoint | Purpose | Gap |
|----------|---------|-----|
| `GET /api/revenue/menu-engineering` | Raw Star/Puzzle/Plowhorse/Dog data | Frontend uses `/price-recommendations` which wraps same logic; raw endpoint unused by UI |
| `GET /api/revenue/top-combos` | Co-occurrence combo list | Frontend uses `/analytics/combo-recommendations`; this duplicate endpoint is not wired |
| `GET /api/revenue/anomalies` | Daily revenue anomaly detection | ✅ Done — wired to Revenue.jsx Anomalies tab |
| `GET /api/revenue/demand-forecast` | 7-day demand prediction | ✅ Done — wired to Revenue.jsx Demand Forecast tab |
| `GET /api/revenue/upsell-recommendations` | Co-occurrence upsell suggestions | ✅ Done — wired to Revenue.jsx Upsell tab |
| `GET /api/inventory/log` | Inventory change history | ✅ Done — wired to Inventory.jsx Activity Log tab |
| `GET /api/customers/:id` | Single customer detail | No customer drill-down page |
| `GET /api/kot/pending` | Pending KOTs | ✅ Done — wired to KitchenDisplay.jsx page with nav + route |
| `GET /api/orders/today` | Today's order summary | Dashboard uses `/dashboard/kpis` instead |
| `GET /api/menu/variants/:item_id` | Item variants | Orders.jsx may not fully use — check modifier flow |
| `GET /api/menu/addons/:item_id` | Item addons | Orders.jsx may not fully use |
| `GET /api/menu/combos` | Active combos | Not connected to Orders page |

---

### ❌ Not Implemented (Module 2 / future)

| Endpoint | Reason |
|----------|--------|
| `POST /api/voice/intent` | Module 2 — DistilBERT intent classifier not built |
| `POST /api/voice/confirm-order` | Module 2 — voice order confirmation flow |
| `GET /api/voice/session/:session_id` | Module 2 — voice session state management |

---

### 🤖 ML-Dependent Endpoints

| Endpoint | Specified Model | What's Built | Status |
|----------|----------------|-------------|--------|
| `GET /api/revenue/anomalies` | Isolation Forest (contamination=0.05) | ✅ Isolation Forest notebook (`models/anomaly_detection.ipynb`) + SQL z-score fallback | ✅ Done — notebook + frontend tab |
| `GET /api/revenue/demand-forecast` | LightGBM with lag/rolling features | ✅ LightGBM primary + Prophet secondary (`models/demand_forecast.ipynb`) | ✅ Done — notebook + frontend tab |
| `GET /api/customers/churn-risk` | XGBoost | ✅ XGBClassifier notebook (`models/churn_prediction.ipynb`) | ✅ Done — notebook fixed |
| `POST /api/voice/transcribe` | Whisper STT | Proxy only | ❌ Returns 503 (ML not running) |
| `POST /api/voice/intent` | DistilBERT | Not built | ❌ Not implemented |
| `POST /api/voice/process-turn` | Full pipeline | Proxy only | ⚠️ Returns "ML unavailable" |

---

## Frontend Changes Needed to Connect to Backend

### 1. Add API base URL config
```javascript
// src/config.js (new file)
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api';
```

### 2. Replace mock auth (Login.jsx / Signup.jsx)
- Replace `setTimeout` delay with `fetch(API_URL + '/auth/signup', { method: 'POST', ... })`
- Store returned JWT in localStorage
- Add `Authorization: Bearer <token>` header to subsequent requests

### 3. Replace POSContext.jsx
- Remove local `orders` state and computed KPIs
- Fetch orders from `GET /api/orders`
- Fetch KPIs from `GET /api/dashboard/kpis`
- Replace `addOrder()` with `POST /api/orders`
- Replace `updateOrderStatus()` with `PUT /api/orders/:id/status`

### 4. Replace mockData.js imports
| Import | Replace with |
|--------|-------------|
| `mockOrders` | `GET /api/orders` |
| `hourlyOrders` | `GET /api/dashboard/hourly-orders` |
| `topItems` | `GET /api/dashboard/top-items` |
| `weeklyRevenue` | `GET /api/dashboard/weekly-revenue` |
| `menuProfitability` | `GET /api/analytics/menu-profitability` |
| `comboRecommendations` | `GET /api/analytics/combo-recommendations` |
| `underperformingItems` | `GET /api/analytics/underperforming-items` |
| `upsellRecommendations` | `GET /api/revenue/top-combos` |

### 5. Replace hardcoded MENU_ITEMS in Orders.jsx
- Fetch from `GET /api/menu/items` on mount
- Build variant/addon selectors from real data

### 6. Replace mock voice pipeline in VoiceOrder.jsx
- Send audio to `POST /api/voice/transcribe`
- Send transcript to `POST /api/voice/process-turn`
- Display real detected items from ML response
- Confirm with `POST /api/voice/confirm-order`

---

## Backend File Structure (created)

```
backend/
├── .env
├── package.json
├── migrations/
│   └── 001_users.sql
└── src/
    ├── app.js
    ├── config/
    │   └── db.js
    ├── middleware/
    │   └── auth.js
    ├── services/
    │   └── mlService.js
    ├── routes/
    │   ├── auth.js
    │   ├── menu.js
    │   ├── orders.js
    │   ├── dashboard.js
    │   ├── revenue.js
    │   ├── analytics.js
    │   ├── inventory.js
    │   ├── customers.js
    │   ├── voice.js
    │   └── kot.js
    └── controllers/
        ├── authController.js
        ├── menuController.js
        ├── orderController.js
        ├── dashboardController.js
        ├── revenueController.js
        ├── analyticsController.js
        ├── inventoryController.js
        ├── customerController.js
        ├── voiceController.js
        └── kotController.js
```

## How to Run

```bash
cd backend
npm install
# Update .env with your DB password if different from 'postgres'
node src/app.js
# Server starts on http://localhost:3000
# Users table auto-created on first run
```

## Test with synthetic data
All dashboard/analytics endpoints accept `?date=YYYY-MM-DD` (default: today).
Since synthetic data is for 2024, use e.g.:
```
GET http://localhost:3000/api/dashboard/kpis?date=2024-06-15
GET http://localhost:3000/api/dashboard/hourly-orders?date=2024-06-15
```

---

## 🔍 Logic Audit — Implemented vs module1.md Specification

### ✅ Matches spec exactly

| Feature | Spec | Implemented | Verdict |
|---------|------|-------------|---------|
| Contribution Margin | Pure SQL, `selling_price - food_cost` per variant | `revenueController.contributionMargin` — exact SQL on `menu_variants` | ✅ Correct |
| Menu Engineering | Dynamic median split (no hardcoded thresholds) | Medians computed in JS after DB fetch; Star/Puzzle/Plowhorse/Dog split matches definition | ✅ Correct |
| Price Optimization | Puzzle → ×0.92 (−8%), Plowhorse → ×1.07 (+7%) | `priceRecommendations`: `factor = 0.92` for Puzzle, `factor = 1.07` for Plowhorse | ✅ Exact match |
| AOV Intelligence | Weekends, festivals, payment methods | `aov()` returns `byWeekType` (weekend/weekday), `byPaymentMethod`, `byChannel`, `byDayOfWeek`, `byHour` | ✅ Correct |
| Hidden Stars | Above-median CM + below-median sales velocity | `hiddenStars()` — median split in JS, filters to `cm > medCM && velocity < medSV` | ✅ Correct |
| Risk Detection | Flag Plowhorse (high vol, low CM) with risk_score | `riskDetection()` — `risk_score = volume_norm × margin_gap × 100` | ✅ Good |

---

### ✅ Deviations from spec — ALL FIXED

#### 1. Combo Engine — ✅ FIXED: FP-Growth added to menu_optimization.ipynb
- **Spec says**: _"FP-Growth algorithm runs on actual order baskets"_
- **Fix applied**: Added FP-Growth via `mlxtend` library in `models/menu_optimization.ipynb`. Mines frequent itemsets of any size (2-item, 3-item, 4-item combos) with `min_support=0.02`. Association rules generated with `min_threshold=1.0` lift. Results exported to JSON.

#### 2. Demand Forecasting — ✅ FIXED: LightGBM added as primary model
- **Spec says**: _"LightGBM trained on features: day_of_week, hour, month, is_weekend, is_festival, lag_7d, lag_14d, rolling_7d_avg"_
- **Fix applied**: Added LightGBM training section to `models/demand_forecast.ipynb` with all specified features (`lag_7d`, `lag_14d`, `rolling_7d_avg`, `rolling_14d_avg`, `rev_lag_7d`, `rev_rolling_7d_avg`, `is_weekend`, `is_festival`, `day_of_week`, `month`). LightGBM is now primary, Prophet is secondary. 30-day iterative forecast with rolling lag updates.

#### 3. Anomaly Detection — ✅ FIXED: New Isolation Forest notebook created
- **Spec says**: _"Isolation Forest — unsupervised, contamination=0.05, no hardcoded thresholds"_
- **Fix applied**: Created `models/anomaly_detection.ipynb` with `IsolationForest(contamination=0.05, n_estimators=200)` on `[daily_revenue, daily_orders, avg_order_val]` features. Exports anomaly scores + predictions to JSON. Frontend Anomalies tab added to Revenue.jsx.

#### 4. Churn Prediction — ✅ FIXED: XGBoost replaces GradientBoosting
- **Spec says**: _"XGBoost classifier"_
- **Fix applied**: Replaced `sklearn.ensemble.GradientBoostingClassifier` with `xgboost.XGBClassifier` in `models/churn_prediction.ipynb`. Parameters: `n_estimators=200, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1.0`.

---

### Summary of fixes — ALL COMPLETED ✅

| Priority | Fix | Status |
|----------|-----|--------|
| ✅ Done | Add FP-Growth to menu_optimization.ipynb | Completed — 3 new cells + export updated |
| ✅ Done | Add Isolation Forest anomaly_detection.ipynb | Completed — new 9-cell notebook |
| ✅ Done | Add LightGBM section to demand_forecast.ipynb | Completed — 4 new cells + export updated |
| ✅ Done | Replace GradientBoosting with XGBoost in churn_prediction.ipynb | Completed — 7 cells modified |
| ✅ Done | Wire `/revenue/anomalies` and `/revenue/demand-forecast` to Revenue.jsx | Completed — Anomalies + Forecast tabs |
| ✅ Done | Wire `/revenue/upsell-recommendations` to Revenue.jsx | Completed — Upsell tab |
| ✅ Done | Wire `/inventory/log` to Inventory.jsx | Completed — Activity Log tab |
| ✅ Done | Wire `/kot/pending` to KitchenDisplay.jsx | Completed — new page + nav/route |
