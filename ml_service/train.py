"""
Train all ML models from PostgreSQL data and save artifacts to ml_service/models/.
Models:
  1. Isolation Forest   — anomaly detection on daily revenue/orders
  2. XGBoost            — customer churn prediction
  3. LightGBM           — demand forecast (orders + revenue)
  4. Menu Optimization   — BCG + elasticity + FP-Growth (rule-based, saved as JSON)

Run once before starting the FastAPI server.
"""

import os, json, warnings
import pandas as pd
import numpy as np
import joblib
from sqlalchemy import create_engine, text
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb
from mlxtend.frequent_patterns import fpgrowth, association_rules
from sklearn.linear_model import LinearRegression

warnings.filterwarnings("ignore")

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
engine = create_engine(DB_URL)
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
OUT_DIR = os.path.dirname(__file__)
os.makedirs(MODEL_DIR, exist_ok=True)


# ═════════════════════════════════════════════════════════════════════════════
# 1. ANOMALY DETECTION — Isolation Forest
# ═════════════════════════════════════════════════════════════════════════════
def train_anomaly():
    print("[1/4] Training Anomaly Detection (Isolation Forest)...")
    df = pd.read_sql("""
        SELECT placed_at::date AS day,
               COUNT(*)::float AS daily_orders,
               SUM(total)::float AS daily_revenue,
               AVG(total)::float AS avg_order_val
        FROM orders WHERE status != 'cancelled'
        GROUP BY placed_at::date ORDER BY day
    """, engine)
    df["day"] = pd.to_datetime(df["day"])

    FEATURES = ["daily_revenue", "daily_orders", "avg_order_val"]
    X = df[FEATURES].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        contamination=0.05, n_estimators=200,
        max_samples="auto", random_state=42, n_jobs=-1
    )
    df["iso_label"] = model.fit_predict(X_scaled)
    df["is_anomaly"] = df["iso_label"] == -1
    df["anomaly_score"] = -model.decision_function(X_scaled)

    n_anom = int(df["is_anomaly"].sum())
    output = {
        "source": "isolation_forest",
        "model": "isolation_forest",
        "contamination": 0.05,
        "total_days": len(df),
        "anomalies_detected": n_anom,
        "data": [
            {
                "day": str(r["day"].date()),
                "daily_orders": int(r["daily_orders"]),
                "daily_revenue": round(float(r["daily_revenue"]), 2),
                "avg_order_val": round(float(r["avg_order_val"]), 2),
                "anomaly_score": round(float(r["anomaly_score"]), 4),
                "is_anomaly": bool(r["is_anomaly"]),
            }
            for _, r in df.iterrows()
        ],
    }
    with open(os.path.join(OUT_DIR, "anomaly_detection_output.json"), "w") as f:
        json.dump(output, f, indent=2)

    joblib.dump(model, os.path.join(MODEL_DIR, "isolation_forest.pkl"))
    joblib.dump(scaler, os.path.join(MODEL_DIR, "anomaly_scaler.pkl"))
    print(f"  → {len(df)} days, {n_anom} anomalies detected")


# ═════════════════════════════════════════════════════════════════════════════
# 2. CHURN PREDICTION — XGBoost
# ═════════════════════════════════════════════════════════════════════════════
def train_churn():
    print("[2/4] Training Churn Prediction (XGBoost)...")
    df = pd.read_sql("""
        SELECT customer_id, name, phone, segment,
               total_visits, total_spent::float, avg_order_val::float,
               (CURRENT_DATE - last_visit) AS days_since_last_visit,
               churn_risk_score::float, last_visit, favourite_item
        FROM customers WHERE total_visits > 0
    """, engine)

    CHURN_THRESHOLD = 0.6
    df["churned"] = (df["churn_risk_score"] >= CHURN_THRESHOLD).astype(int)

    segment_dummies = pd.get_dummies(df["segment"], prefix="seg")
    feature_cols_base = ["total_visits", "total_spent", "avg_order_val", "days_since_last_visit"]
    features = pd.concat([df[feature_cols_base], segment_dummies], axis=1)

    # Ensure days_since_last_visit is numeric
    features["days_since_last_visit"] = pd.to_numeric(
        features["days_since_last_visit"], errors="coerce"
    ).fillna(0).astype(float)

    X = features
    y = df["churned"]
    feature_cols = list(X.columns)

    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        reg_alpha=0.1, reg_lambda=1.0,
        eval_metric="logloss", random_state=42
    )
    model.fit(X, y)

    # Generate predictions for ALL customers
    all_proba = model.predict_proba(X)[:, 1]
    df["predicted_churn"] = all_proba

    # Build full churn output
    churn_output = {
        "source": "ml",
        "model": "xgboost",
        "threshold": CHURN_THRESHOLD,
        "total_customers": len(df),
        "at_risk": int((all_proba >= CHURN_THRESHOLD).sum()),
        "all_customers": [
            {
                "customer_id": int(r["customer_id"]),
                "name": r["name"],
                "phone": r.get("phone", ""),
                "segment": r["segment"],
                "total_visits": int(r["total_visits"]),
                "total_spent": round(float(r["total_spent"]), 2),
                "avg_order_val": round(float(r["avg_order_val"]), 2),
                "days_since_last_visit": int(r["days_since_last_visit"]),
                "last_visit": str(r["last_visit"]) if r["last_visit"] else None,
                "favourite_item": r.get("favourite_item"),
                "churn_risk_score": round(float(r["predicted_churn"]), 4),
                "original_score": round(float(r["churn_risk_score"]), 4),
            }
            for _, r in df.iterrows()
        ],
    }
    with open(os.path.join(OUT_DIR, "churn_output.json"), "w") as f:
        json.dump(churn_output, f, indent=2)

    joblib.dump(model, os.path.join(MODEL_DIR, "churn_model.pkl"))
    with open(os.path.join(MODEL_DIR, "churn_feature_cols.json"), "w") as f:
        json.dump(feature_cols, f)

    print(f"  → {len(df)} customers, {churn_output['at_risk']} at risk (>={CHURN_THRESHOLD})")


# ═════════════════════════════════════════════════════════════════════════════
# 3. DEMAND FORECAST — LightGBM
# ═════════════════════════════════════════════════════════════════════════════
def train_demand():
    print("[3/4] Training Demand Forecast (LightGBM)...")
    df = pd.read_sql("""
        SELECT placed_at::date AS ds,
               COUNT(*)::float AS order_count,
               SUM(total)::float AS revenue
        FROM orders WHERE status != 'cancelled'
        GROUP BY placed_at::date ORDER BY ds
    """, engine)
    df["ds"] = pd.to_datetime(df["ds"])

    # Calendar & lag features
    df["day_of_week"] = df["ds"].dt.dayofweek
    df["month"] = df["ds"].dt.month
    df["day_of_month"] = df["ds"].dt.day
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["week_of_year"] = df["ds"].dt.isocalendar().week.astype(int)

    festival_dates = pd.to_datetime([
        "2024-01-01", "2024-01-26", "2024-03-25", "2024-04-10",
        "2024-08-15", "2024-10-02", "2024-11-01", "2024-12-25",
    ])
    df["is_festival"] = df["ds"].isin(festival_dates).astype(int)

    df["lag_7d"] = df["order_count"].shift(7)
    df["lag_14d"] = df["order_count"].shift(14)
    df["rolling_7d_avg"] = df["order_count"].rolling(7).mean()
    df["rolling_14d_avg"] = df["order_count"].rolling(14).mean()

    df = df.dropna().reset_index(drop=True)

    FEATURES = [
        "day_of_week", "month", "day_of_month", "is_weekend", "week_of_year",
        "is_festival", "lag_7d", "lag_14d", "rolling_7d_avg", "rolling_14d_avg",
    ]
    X = df[FEATURES]
    y_orders = df["order_count"]
    y_revenue = df["revenue"]

    lgb_orders = lgb.LGBMRegressor(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        num_leaves=31, subsample=0.8, colsample_bytree=0.8,
        random_state=42, verbose=-1
    )
    lgb_orders.fit(X, y_orders)

    lgb_revenue = lgb.LGBMRegressor(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        num_leaves=31, subsample=0.8, colsample_bytree=0.8,
        random_state=42, verbose=-1
    )
    lgb_revenue.fit(X, y_revenue)

    # Generate 30-day forecast iteratively
    last_date = df["ds"].max()
    future_dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=30)
    order_history = df["order_count"].values.tolist()
    rev_history = df["revenue"].values.tolist()

    forecasts = []
    for fdate in future_dates:
        row = {
            "day_of_week": fdate.dayofweek,
            "month": fdate.month,
            "day_of_month": fdate.day,
            "is_weekend": int(fdate.dayofweek in [5, 6]),
            "week_of_year": int(fdate.isocalendar()[1]),
            "is_festival": int(fdate in festival_dates),
            "lag_7d": order_history[-7],
            "lag_14d": order_history[-14],
            "rolling_7d_avg": float(np.mean(order_history[-7:])),
            "rolling_14d_avg": float(np.mean(order_history[-14:])),
        }
        X_fut = pd.DataFrame([row])[FEATURES]
        pred_orders = max(0, round(float(lgb_orders.predict(X_fut)[0])))
        pred_revenue = max(0, round(float(lgb_revenue.predict(X_fut)[0]), 2))
        order_history.append(pred_orders)
        rev_history.append(pred_revenue)
        forecasts.append({
            "date": str(fdate.date()),
            "predicted_orders": pred_orders,
            "predicted_revenue": pred_revenue,
        })

    payload = {
        "source": "ml",
        "model": "lightgbm",
        "generated_at": str(pd.Timestamp.now().date()),
        "horizon_days": 30,
        "forecasts": forecasts,
    }
    with open(os.path.join(OUT_DIR, "demand_forecast_output.json"), "w") as f:
        json.dump(payload, f, indent=2)

    joblib.dump(lgb_orders, os.path.join(MODEL_DIR, "lgb_orders.pkl"))
    joblib.dump(lgb_revenue, os.path.join(MODEL_DIR, "lgb_revenue.pkl"))
    print(f"  → Trained on {len(df)} days, 30-day forecast generated")


# ─────────────────────────────────────────────────────────────────────────────
# Helper: snap to psychologically appealing price
# ─────────────────────────────────────────────────────────────────────────────
def psych_round(price):
    """Return price snapped to a psychologically appealing number."""
    if price <= 0:
        return 0.0
    if price < 100:
        return float(round(price / 10) * 10 - 1)
    if price < 300:
        return float(round(price / 50) * 50 - 1)
    if price < 600:
        return float(round(price / 50) * 50)
    return float(round(price / 100) * 100)


# ═════════════════════════════════════════════════════════════════════════════
# 4. MENU OPTIMIZATION — BCG + New-Item Detection + FP-Growth DB Write
# ═════════════════════════════════════════════════════════════════════════════
def train_menu():
    print("[4/4] Training Menu Optimization (BCG + FP-Growth)...")

    # ── Data window anchored to MAX(placed_at), not NOW() ────────────────────
    max_date_row = pd.read_sql("SELECT MAX(placed_at) AS max_dt FROM orders", engine)
    max_date = max_date_row["max_dt"].iloc[0]
    if pd.isnull(max_date):
        print("  → No order data found, skipping menu optimization")
        return
    window_start = max_date - pd.Timedelta(days=60)

    # ── Ensure migration columns exist (idempotent — safe to run twice) ───────
    with engine.begin() as _conn:
        _conn.execute(text("ALTER TABLE menu_combos ADD COLUMN IF NOT EXISTS combo_size  INT DEFAULT 2"))
        _conn.execute(text("ALTER TABLE menu_combos ADD COLUMN IF NOT EXISTS combo_score NUMERIC(8,4) DEFAULT 0"))
        _conn.execute(text("ALTER TABLE menu_combos ADD COLUMN IF NOT EXISTS lift        NUMERIC(8,4) DEFAULT 1"))
        _conn.execute(text("ALTER TABLE menu_items  ADD COLUMN IF NOT EXISTS first_ordered_at  TIMESTAMPTZ"))
        _conn.execute(text("ALTER TABLE menu_items  ADD COLUMN IF NOT EXISTS total_orders_ever INT DEFAULT 0"))

    # ── Items with orders in the 60-day window ────────────────────────────────
    menu_df = pd.read_sql(f"""
        SELECT
            mi.item_id, mi.name,
            mc.name AS category,
            AVG(mv.selling_price)::float AS price,
            AVG(mv.food_cost)::float     AS food_cost,
            COUNT(oi.line_id)            AS order_count,
            SUM(oi.revenue)::float       AS total_revenue,
            AVG(oi.unit_price)::float    AS avg_selling_price
        FROM menu_items mi
        JOIN menu_variants mv ON mv.item_id = mi.item_id
        JOIN order_items oi ON oi.item_id = mi.item_id
        JOIN orders o ON o.order_id = oi.order_id AND o.status != 'cancelled'
            AND o.placed_at >= '{window_start.date()}'
        LEFT JOIN menu_categories mc ON mi.category_id = mc.category_id
        GROUP BY mi.item_id, mi.name, mc.name
        ORDER BY total_revenue DESC
    """, engine)

    menu_df["contribution_margin"] = menu_df["price"] - menu_df["food_cost"]
    menu_df["margin_pct"] = (
        (menu_df["price"] - menu_df["food_cost"])
        / menu_df["price"].replace(0, np.nan) * 100
    ).round(2).fillna(0)

    in_window_ids = set(menu_df["item_id"].tolist())

    # ── Lifetime order counts (new-item detection) ────────────────────────────
    life_df = pd.read_sql("""
        SELECT mi.item_id,
               COALESCE(COUNT(DISTINCT oi.order_id), 0) AS lifetime_orders
        FROM menu_items mi
        LEFT JOIN order_items oi ON oi.item_id = mi.item_id
        GROUP BY mi.item_id
    """, engine).set_index("item_id")["lifetime_orders"]

    low_order_ids = set(life_df[life_df < 50].index.tolist())

    # ── All menu items (for fetching items with zero 60-day orders) ───────────
    all_items_df = pd.read_sql("""
        SELECT mi.item_id, mi.name,
               mc.name AS category,
               COALESCE(AVG(mv.selling_price), 0)::float AS price,
               COALESCE(AVG(mv.food_cost), 0)::float     AS food_cost
        FROM menu_items mi
        LEFT JOIN menu_variants mv ON mv.item_id = mi.item_id
        LEFT JOIN menu_categories mc ON mi.category_id = mc.category_id
        GROUP BY mi.item_id, mi.name, mc.name
    """, engine)

    all_menu_item_ids = set(all_items_df["item_id"].tolist())
    missing_ids   = all_menu_item_ids - in_window_ids
    new_items_set = (in_window_ids & low_order_ids) | missing_ids

    # Append missing items (zero 60-day orders) with zeroed order metrics
    if missing_ids:
        missing_rows = all_items_df[all_items_df["item_id"].isin(missing_ids)].copy()
        missing_rows["order_count"]         = 0
        missing_rows["total_revenue"]       = 0.0
        missing_rows["avg_selling_price"]   = missing_rows["price"]
        missing_rows["contribution_margin"] = missing_rows["price"] - missing_rows["food_cost"]
        missing_rows["margin_pct"] = (
            (missing_rows["price"] - missing_rows["food_cost"])
            / missing_rows["price"].replace(0, np.nan) * 100
        ).round(2).fillna(0)
        menu_df = pd.concat([menu_df, missing_rows], ignore_index=True)

    # ── BCG classification (window items only; new items always → "New") ──────
    window_mask = menu_df["item_id"].isin(in_window_ids)
    median_cm   = menu_df.loc[window_mask, "contribution_margin"].median() if window_mask.any() else 0
    median_cnt  = menu_df.loc[window_mask, "order_count"].median()         if window_mask.any() else 0

    def bcg_class(row):
        if int(row["item_id"]) in new_items_set:
            return "New"
        high_cm   = row["contribution_margin"] >= median_cm
        high_vol  = row["order_count"] >= median_cnt
        if high_cm  and high_vol:     return "Star"
        if high_cm  and not high_vol: return "Puzzle"
        if not high_cm and high_vol:  return "Plowhorse"
        return "Dog"

    menu_df["bcg_class"] = menu_df.apply(bcg_class, axis=1)

    # ── Elasticity caps per category ──────────────────────────────────────────
    ELASTICITY_CAPS = {
        "Bread":   {"up": 5,  "down": 5},
        "Drink":   {"up": 8,  "down": 8},
        "Dessert": {"up": 10, "down": 10},
        "Starter": {"up": 12, "down": 12},
        "Main":    {"up": 15, "down": 10},
        "Rice":    {"up": 15, "down": 10},
        "Addon":   {"up": 8,  "down": 8},
    }

    # ── BCG strategy for normal items ─────────────────────────────────────────
    STRATEGY = {
        "Star":      ("increase",  0.05,  "Slight increase acceptable — strong performer"),
        "Puzzle":    ("decrease", -0.12,  "Lower price to increase volume — above-median margin"),
        "Plowhorse": ("increase",  0.08,  "Raise price to improve margin — inelastic demand"),
        "Dog":       ("decrease", -0.20,  "Cut price or bundle to drive movement"),
    }

    # ── Price recommendations ─────────────────────────────────────────────────
    price_recs     = []
    new_item_count = 0

    for _, row in menu_df.iterrows():
        item_id       = int(row["item_id"])
        current_price = float(row["price"])    if row["price"]    > 0 else 0.0
        food_cost     = float(row["food_cost"]) if not pd.isnull(row["food_cost"]) else 0.0
        cat           = str(row["category"])    if row["category"] else ""
        cap           = ELASTICITY_CAPS.get(cat, {"up": 10, "down": 10})
        actual_margin = float(row["margin_pct"])

        # ── New-item branch: margin-only, half elasticity cap ─────────────────
        if item_id in new_items_set:
            cat_rows = menu_df[menu_df["category"] == cat]
            if len(cat_rows) > 0:
                med_cnt_cat = cat_rows["order_count"].median()
                top_half    = cat_rows[cat_rows["order_count"] >= med_cnt_cat]
                target      = float(top_half["margin_pct"].quantile(0.75)) if len(top_half) > 0 else actual_margin
            else:
                target = actual_margin

            half_cap = {"up": cap["up"] / 2, "down": cap["down"] / 2}
            raw_new  = ((actual_margin - target) / max(100 - target, 1)) * 100
            raw_new  = max(-half_cap["up"], min(half_cap["down"], raw_new))

            if abs(raw_new) < 0.5 or current_price == 0:
                direction = "maintain"
                suggested = current_price
            elif raw_new > 0:
                direction = "decrease"
                suggested = psych_round(current_price * (1 - raw_new / 100))
            else:
                direction = "increase"
                suggested = psych_round(current_price * (1 + abs(raw_new) / 100))

            if food_cost > 0:
                suggested = max(suggested, food_cost * 1.25)
            change_pct = round(((suggested - current_price) / current_price) * 100, 1) if current_price > 0 else 0.0
            cap_used   = half_cap["up"] if raw_new > 0 else half_cap["down"]

            price_recs.append({
                "item_id":                    item_id,
                "name":                       str(row["name"]),
                "category":                   cat,
                "bcg_class":                  "New",
                "current_price":              current_price,
                "suggested_price":            float(suggested),
                "price_change_pct":           float(change_pct),
                "direction":                  direction,
                "reason": (
                    f"New item — margin {actual_margin:.1f}% vs "
                    f"{cat or 'overall'} target ({target:.1f}%). "
                    f"Gentle {direction} (\u2264{cap_used:.0f}% cap, margin-only)."
                ),
                "actual_margin_pct":          actual_margin,
                "category_target_margin_pct": float(target),
                "margin_gap_pp":              float(actual_margin - target),
                "demand_percentile":          0.0,
                "demand_dampen_factor":       0.0,
                "elasticity_cap_up":          float(half_cap["up"]),
                "elasticity_cap_down":        float(half_cap["down"]),
                "window_days":                60,
                "is_new_item":                True,
            })
            new_item_count += 1
            continue

        # ── Normal-item BCG branch ────────────────────────────────────────────
        action, delta, reason = STRATEGY[row["bcg_class"]]
        suggested  = psych_round(row["price"] * (1 + delta))
        min_price  = food_cost * 1.3
        suggested  = max(suggested, min_price)
        change_pct = round(((suggested - row["price"]) / row["price"]) * 100, 1) if row["price"] > 0 else 0.0

        price_recs.append({
            "item_id":                    item_id,
            "name":                       str(row["name"]),
            "category":                   cat,
            "bcg_class":                  str(row["bcg_class"]),
            "current_price":              float(row["price"]),
            "suggested_price":            float(suggested),
            "price_change_pct":           float(change_pct),
            "direction":                  action,
            "reason":                     reason,
            "actual_margin_pct":          actual_margin,
            "category_target_margin_pct": 0.0,
            "margin_gap_pp":              0.0,
            "demand_percentile":          0.0,
            "demand_dampen_factor":       0.0,
            "elasticity_cap_up":          float(cap["up"]),
            "elasticity_cap_down":        float(cap["down"]),
            "window_days":                60,
            "is_new_item":                False,
        })

    # ── Co-occurrence / upsell via SQL ────────────────────────────────────────
    cooc_df = pd.read_sql("""
        SELECT a.item_id AS item_a, b.item_id AS item_b, COUNT(*) AS co_occurrences
        FROM order_items a
        JOIN order_items b ON a.order_id = b.order_id AND a.item_id < b.item_id
        GROUP BY a.item_id, b.item_id HAVING COUNT(*) > 5
        ORDER BY co_occurrences DESC LIMIT 200
    """, engine)

    total_orders = pd.read_sql("SELECT COUNT(DISTINCT order_id) AS n FROM orders", engine)["n"].iloc[0]
    item_freq = pd.read_sql(
        "SELECT item_id, COUNT(DISTINCT order_id) AS freq FROM order_items GROUP BY item_id", engine
    ).set_index("item_id")["freq"]
    names = pd.read_sql("SELECT item_id, name FROM menu_items", engine).set_index("item_id")["name"]

    def calc_lift(row):
        pa  = item_freq.get(row["item_a"], 1) / total_orders
        pb  = item_freq.get(row["item_b"], 1) / total_orders
        pab = row["co_occurrences"] / total_orders
        return round(pab / (pa * pb + 1e-9), 3)

    cooc_df["lift"]   = cooc_df.apply(calc_lift, axis=1)
    cooc_df["name_a"] = cooc_df["item_a"].map(names)
    cooc_df["name_b"] = cooc_df["item_b"].map(names)

    upsell_pairs = [
        {
            "item_a": int(r["item_a"]), "item_b": int(r["item_b"]),
            "name_a": r["name_a"],      "name_b": r["name_b"],
            "co_occurrences": int(r["co_occurrences"]), "lift": float(r["lift"]),
        }
        for _, r in cooc_df.nlargest(50, "lift").iterrows()
    ]

    # ── FP-Growth basket mining (60-day window) ───────────────────────────────
    basket_raw = pd.read_sql(f"""
        SELECT oi.order_id, mi.name AS item_name
        FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id AND o.status != 'cancelled'
            AND o.placed_at >= '{window_start.date()}'
        JOIN menu_items mi ON mi.item_id = oi.item_id
    """, engine)
    basket = basket_raw.groupby(["order_id", "item_name"]).size().unstack(fill_value=0)
    basket = (basket > 0).astype(int)

    freq_items = fpgrowth(basket, min_support=0.01, use_colnames=True)
    freq_items["itemset_size"] = freq_items["itemsets"].apply(len)

    # ── Item price/cost lookup by name (for combo pricing & DB write) ─────────
    item_prices_df = pd.read_sql("""
        SELECT mi.item_id, mi.name,
               COALESCE(AVG(mv.selling_price), 0)::float AS avg_price,
               COALESCE(AVG(mv.food_cost), 0)::float     AS avg_cost
        FROM menu_items mi
        LEFT JOIN menu_variants mv ON mv.item_id = mi.item_id
        GROUP BY mi.item_id, mi.name
    """, engine)
    name_to_info = {
        r["name"]: {
            "item_id":   int(r["item_id"]),
            "avg_price": float(r["avg_price"]),
            "avg_cost":  float(r["avg_cost"]),
        }
        for _, r in item_prices_df.iterrows()
    }

    # Individual item support fraction (for set-lift computation)
    total_baskets = max(len(basket), 1)
    item_support  = {col: float(basket[col].sum()) / total_baskets for col in basket.columns}

    # Score every pair and triplet itemset
    scored_combos = []
    for _, frow in freq_items.iterrows():
        size = int(frow["itemset_size"])
        if size not in (2, 3):
            continue
        items_list = sorted(list(frow["itemsets"]))
        sup        = float(frow["support"])

        # set_lift = P(A∩B∩…) / (P(A) × P(B) × …)
        expected = 1.0
        for n in items_list:
            expected *= item_support.get(n, sup)
        set_lift = sup / (expected + 1e-9)

        if any(n not in name_to_info for n in items_list):
            continue  # item without price data — skip

        t_price  = sum(name_to_info[n]["avg_price"] for n in items_list)
        t_cost   = sum(name_to_info[n]["avg_cost"]  for n in items_list)
        discount = 0.12 if size == 3 else 0.10
        combo_p  = psych_round(max(t_price * (1 - discount), t_cost * 1.3))
        cscore   = min(100.0, set_lift * 20 + sup * 100)

        scored_combos.append({
            "items_list":  items_list,
            "item_ids":    [name_to_info[n]["item_id"] for n in items_list],
            "size":        size,
            "combo_score": cscore,
            "lift":        set_lift,
            "t_price":     t_price,
            "t_cost":      t_cost,
            "combo_price": combo_p,
        })

    # Top 40 by combo_score
    scored_combos.sort(key=lambda x: x["combo_score"], reverse=True)
    top_combos    = scored_combos[:40]
    auto_pairs    = sum(1 for c in top_combos if c["size"] == 2)
    auto_triplets = sum(1 for c in top_combos if c["size"] == 3)

    # ── Write auto-mined combos to DB (DELETE → INSERT single transaction) ────
    if top_combos:
        with engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM combo_items
                WHERE combo_id IN (
                    SELECT combo_id FROM menu_combos WHERE description = 'auto_mined'
                )
            """))
            conn.execute(text("DELETE FROM menu_combos WHERE description = 'auto_mined'"))

            for c in top_combos:
                combo_name = " + ".join(c["items_list"])[:100]
                result = conn.execute(text("""
                    INSERT INTO menu_combos
                        (combo_name, description, selling_price, food_cost,
                         combo_size, combo_score, lift, is_active, valid_from)
                    VALUES
                        (:name, 'auto_mined', :price, :cost,
                         :size, :score, :lift, TRUE, CURRENT_DATE)
                    RETURNING combo_id
                """), {
                    "name":  combo_name,
                    "price": float(c["combo_price"]),
                    "cost":  float(c["t_cost"]),
                    "size":  int(c["size"]),
                    "score": float(c["combo_score"]),
                    "lift":  float(c["lift"]),
                })
                new_combo_id = result.fetchone()[0]
                for iid in c["item_ids"]:
                    conn.execute(text("""
                        INSERT INTO combo_items (combo_id, item_id, qty)
                        VALUES (:combo_id, :item_id, 1)
                    """), {"combo_id": new_combo_id, "item_id": int(iid)})

    # ── Backfill lifetime order stats on menu_items ───────────────────────────
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE menu_items mi
            SET total_orders_ever = sub.cnt
            FROM (
                SELECT item_id, COUNT(*) AS cnt FROM order_items GROUP BY item_id
            ) sub
            WHERE mi.item_id = sub.item_id
        """))
        conn.execute(text("""
            UPDATE menu_items mi
            SET first_ordered_at = sub.first_at
            FROM (
                SELECT oi.item_id, MIN(o.placed_at) AS first_at
                FROM order_items oi
                JOIN orders o USING (order_id)
                GROUP BY oi.item_id
            ) sub
            WHERE mi.item_id = sub.item_id
        """))

    # ── FP-Growth JSON output (top-100 by support, top-50 rules by lift) ──────
    fpgrowth_combos = [
        {
            "items":   sorted(list(r["itemsets"])),
            "support": round(float(r["support"]), 4),
            "size":    int(r["itemset_size"]),
        }
        for _, r in freq_items.nlargest(100, "support").iterrows()
    ]

    rules_df = association_rules(freq_items, metric="lift", min_threshold=1.0)
    for col in ["support", "confidence", "lift"]:
        if col in rules_df.columns:
            rules_df[col] = pd.to_numeric(rules_df[col], errors="coerce")
    rules_df = rules_df.sort_values("lift", ascending=False)

    fpgrowth_rules = [
        {
            "antecedents": sorted(list(r["antecedents"])),
            "consequents": sorted(list(r["consequents"])),
            "support":    round(float(r["support"]),    4),
            "confidence": round(float(r["confidence"]), 4),
            "lift":       round(float(r["lift"]),        3),
        }
        for _, r in rules_df.nlargest(50, "lift").iterrows()
    ]

    output = {
        "price_recommendations": price_recs,
        "upsell_pairs":          upsell_pairs,
        "fpgrowth_combos":       fpgrowth_combos,
        "fpgrowth_rules":        fpgrowth_rules,
    }
    with open(os.path.join(OUT_DIR, "menu_optimization_output.json"), "w") as f:
        json.dump(output, f, indent=2)

    n_increase = sum(1 for r in price_recs if r["direction"] == "increase")
    n_decrease = sum(1 for r in price_recs if r["direction"] == "decrease")
    n_maintain = sum(1 for r in price_recs if r["direction"] == "maintain")
    print(
        f"  -> {len(price_recs)} price recs "
        f"(+{n_increase} increase, -{n_decrease} decrease, "
        f"={n_maintain} maintain, {new_item_count} new-item), "
        f"{len(upsell_pairs)} upsell pairs, "
        f"{auto_pairs} auto-pairs + {auto_triplets} auto-triplets written to DB"
    )


# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("PetPooja ML Pipeline — Training All Models")
    print("=" * 60)
    train_anomaly()
    train_churn()
    train_demand()
    train_menu()
    print("=" * 60)
    print("All models trained. Start the FastAPI server with:")
    print("  python main.py")
    print("=" * 60)
