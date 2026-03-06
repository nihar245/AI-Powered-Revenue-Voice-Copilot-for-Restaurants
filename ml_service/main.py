"""
PetPooja ML Service — FastAPI server on port 8000.
Serves pre-trained model outputs for:
  GET  /predict/anomalies      — Isolation Forest anomaly detection
  GET  /predict/churn           — XGBoost churn predictions
  GET  /predict/demand          — LightGBM demand forecast
  GET  /predict/menu-optimization — BCG + FP-Growth menu analysis
  GET  /health                  — health check
"""

import os, json
from datetime import datetime, date
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Indian festivals / notable dates — YYYY-MM-DD
_FESTIVALS = {
    "01-01": "New Year", "01-14": "Makar Sankranti", "01-15": "Pongal",
    "01-26": "Republic Day", "02-14": "Valentine's Day",
    "03-08": "Holi (approx)", "03-25": "Holi",
    "04-10": "Eid (approx)", "04-14": "Ambedkar Jayanti",
    "05-01": "May Day", "05-23": "Buddha Purnima",
    "06-17": "Eid al-Adha (approx)",
    "08-15": "Independence Day", "08-26": "Janmashtami (approx)",
    "09-07": "Ganesh Chaturthi (approx)",
    "10-02": "Gandhi Jayanti", "10-12": "Dussehra (approx)",
    "10-20": "Navratri (approx)", "10-24": "Karwa Chauth (approx)",
    "10-31": "Halloween",
    "11-01": "Diwali (approx)", "11-02": "Diwali (approx)",
    "11-15": "Guru Nanak Jayanti (approx)", "11-27": "Thanksgiving (approx)",
    "12-25": "Christmas", "12-31": "New Year's Eve",
}

def day_context(day_str: str) -> dict:
    """Return day_type + day_label for a YYYY-MM-DD string."""
    dt = datetime.strptime(day_str[:10], "%Y-%m-%d")
    md = dt.strftime("%m-%d")
    wd = dt.weekday()  # 0=Mon … 6=Sun
    is_weekend = wd >= 5
    festival = _FESTIVALS.get(md)
    if festival:
        return {"day_type": "Festival", "day_label": festival}
    if wd == 4:  # Friday
        return {"day_type": "Friday", "day_label": "Friday — higher dining activity"}
    if is_weekend:
        return {"day_type": "Weekend", "day_label": "Saturday" if wd == 5 else "Sunday"}
    return {"day_type": "Weekday", "day_label": dt.strftime("%A")}

app = FastAPI(title="PetPooja ML Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(__file__)

def load_json(filename):
    path = os.path.join(BASE_DIR, filename)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

# Pre-load outputs at startup
anomaly_data = load_json("anomaly_detection_output.json")
churn_data = load_json("churn_output.json")
demand_data = load_json("demand_forecast_output.json")
menu_data = load_json("menu_optimization_output.json")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "models": {
            "anomaly_detection": anomaly_data is not None,
            "churn_prediction": churn_data is not None,
            "demand_forecast": demand_data is not None,
            "menu_optimization": menu_data is not None,
        },
    }


# ── Anomaly Detection ────────────────────────────────────────────────────────
@app.get("/predict/anomalies")
def predict_anomalies():
    if anomaly_data is None:
        return {"error": "Anomaly model not trained. Run train.py first."}
    # Normalise field names to match SQL-fallback schema so frontend charts work
    normalised = []
    for row in anomaly_data.get("data", []):
        ctx = day_context(row["day"])
        normalised.append({
            "day": row["day"],
            "order_count": row.get("order_count", row.get("daily_orders")),
            "revenue": row.get("revenue", row.get("daily_revenue")),
            "avg_order_val": row.get("avg_order_val", 0),
            "anomaly_score": row.get("anomaly_score", row.get("z_score", 0)),
            "is_anomaly": row.get("is_anomaly", False),
            **ctx,
        })
    return {
        "source": anomaly_data.get("source", "isolation_forest"),
        "model": anomaly_data.get("model", "isolation_forest"),
        "total_days": anomaly_data.get("total_days", len(normalised)),
        "anomalies_detected": anomaly_data.get("anomalies_detected", sum(1 for r in normalised if r["is_anomaly"])),
        "data": normalised,
    }


# ── Churn Prediction ─────────────────────────────────────────────────────────
@app.get("/predict/churn")
def predict_churn(threshold: float = 0.6):
    if churn_data is None:
        return {"error": "Churn model not trained. Run train.py first."}
    # Filter customers above threshold
    at_risk = [
        c for c in churn_data["all_customers"]
        if c["churn_risk_score"] >= threshold
    ]
    return {
        "source": "ml",
        "model": "xgboost",
        "threshold": threshold,
        "data": sorted(at_risk, key=lambda x: x["churn_risk_score"], reverse=True),
    }


# ── Demand Forecast ──────────────────────────────────────────────────────────
@app.get("/predict/demand")
def predict_demand():
    if demand_data is None:
        return {"error": "Demand model not trained. Run train.py first."}
    return demand_data


# ── Menu Optimization ────────────────────────────────────────────────────────
@app.get("/predict/menu-optimization")
def predict_menu():
    if menu_data is None:
        return {"error": "Menu model not trained. Run train.py first."}
    return menu_data


if __name__ == "__main__":
    import uvicorn
    print("Starting PetPooja ML Service on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
