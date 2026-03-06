Best practice for a real restaurant: Use 30 days for pricing/menu decisions (recent enough to reflect changes), 90 days to catch seasonal patterns, 7 days to spot the current week's anomalies.

SQL vs ML — Feature Map
Feature	Where	Powered by
BCG Matrix (profitability scatter)	Analytics	SQL — aggregates margin × popularity from order_items
Combo Recommendations	Analytics	SQL — Apriori co-occurrence pairs (no ML library needed)
Popularity Scoring (Fast/Slow/Dead)	Analytics	SQL — percentile rank on total_sold
Hidden Stars	Analytics	SQL — above-median margin, below-median velocity
Risk Detection (Plowhorse items)	Analytics	SQL — high volume × thin margin flagging
Underperforming Items	Analytics	SQL — Dog + Plowhorse classification
ML Price Optimization tab	Analytics	ML model (/predict/menu-optimization) — tab only appears when FastAPI is running
Contribution Margin chart/table	Revenue	SQL — live food cost vs selling price from menu_variants
Price Recommendations	Revenue	SQL rule engine — BCG class → ±7% suggestion
AOV Intelligence (all 5 breakdowns)	Revenue	SQL — aggregated from orders by channel/day/hour/method/weektype
Anomaly Detection	Revenue	ML first (Isolation Forest via FastAPI) → SQL z-score fallback if ML is down
Demand Forecast	Revenue	ML only (LightGBM via FastAPI) — shows "unavailable" if ML is down
Upsell Performance Stats	Revenue	SQL — tracks is_upsell=TRUE rows in order_items