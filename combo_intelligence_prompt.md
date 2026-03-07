# Combo Intelligence Engine — Complete Generation Prompt

Use this prompt verbatim (or adapt the schema section) to regenerate the full notebook against any database.

---

## PROMPT

You are a senior data scientist and Python engineer. Generate a complete, production-ready Jupyter notebook (`.ipynb`) called **Combo Intelligence Engine** for a restaurant / food-service POS system.

The notebook analyses menu and sales data from a PostgreSQL database, mines item co-purchase patterns using a custom Apriori implementation, scores candidate combos on 5 business factors, generates both 2-item and 3-item combo recommendations (3-item only when statistically justified), suggests combo prices with margin guardrails, writes results back to the database, and maintains a full audit trail.

---

## DATABASE CONNECTION

```python
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://USER:PASSWORD@HOST:PORT/DBNAME')

def get_conn():
    return psycopg2.connect(DATABASE_URL)
```

Replace `USER`, `PASSWORD`, `HOST`, `PORT`, `DBNAME` with your actual credentials, or set the `DATABASE_URL` environment variable.

---

## SOURCE TABLE SCHEMA

> **This is the only section you need to change when adapting to a different database.**
> Replace the table names, column names, and JOIN logic below with your actual schema.
> Everything else in the notebook — the analytics, scoring, pricing, and output logic — stays identical.

### Tables the notebook reads from:

**`menu`** — one row per menu item
| Column | Type | Description |
|---|---|---|
| `item_id` | VARCHAR | Primary key |
| `item_name` | VARCHAR | Display name |
| `category_id` | FK | Links to categories |
| `sub_category` | VARCHAR | Fallback category label |
| `selling_price` | NUMERIC | Price charged to customer |
| `food_cost` | NUMERIC | Raw ingredient cost |
| `is_active` | BOOLEAN | Filter: only active items |

**`categories`** — lookup for category names
| Column | Type | Description |
|---|---|---|
| `category_id` | PK | |
| `name` | VARCHAR | Category label (e.g. "Main Course", "Beverage") |

**`orders`** — one row per order/transaction
| Column | Type | Description |
|---|---|---|
| `order_id` | VARCHAR/INT | Primary key |
| `order_date` | DATE | |
| `order_time` | TIME | Used for Lunch/Dinner session split |
| `order_type` | VARCHAR | e.g. 'dine_in', 'delivery', 'takeaway' |

**`order_items`** — one row per item within an order
| Column | Type | Description |
|---|---|---|
| `order_id` | FK → orders | |
| `item_id` | FK → menu | |
| `item_name` | VARCHAR | Snapshot of name at time of order |
| `category` | VARCHAR | Snapshot of category at time of order |
| `quantity` | INT | Units ordered |
| `unit_price` | NUMERIC | Price at time of order |
| `discount` | NUMERIC | Discount applied (0 if none) |
| `food_cost_snapshot` | NUMERIC | Cost at time of order (can be null, falls back to menu.food_cost) |

**`combos`** — existing combo definitions (may be empty on first run)
| Column | Type | Description |
|---|---|---|
| `combo_id` | VARCHAR | Primary key |
| `combo_label` | VARCHAR | Human-readable name |
| `combo_price` | NUMERIC | Price of the combo |
| `support` | NUMERIC | Statistical support when created |
| `confidence` | NUMERIC | Statistical confidence when created |
| `lift` | NUMERIC | Statistical lift when created |
| `times_recommended` | INT | How many times suggested to customer |
| `times_accepted` | INT | How many times customer accepted |
| `total_revenue_generated` | NUMERIC | Cumulative revenue |
| `avg_aov_uplift` | NUMERIC | Average order value uplift |
| `is_active` | BOOLEAN | Whether combo is currently live |
| `performance_flag` | VARCHAR | 'strong', 'average', 'weak', 'new' |
| `started_at` | TIMESTAMP | When combo was activated |
| `ended_at` | TIMESTAMP | When combo was deactivated (null if still active) |

**`combo_items`** — many-to-many: which items belong to each combo
| Column | Type | Description |
|---|---|---|
| `id` | SERIAL | Primary key |
| `combo_id` | FK → combos | |
| `item_id` | FK → menu | |

### Tables the notebook creates/writes to (auto-created if missing):

**`item_performance`** — computed item metrics, upserted each run
**`combo_price_history`** — immutable audit log of every price change
**`item_performance_snapshot`** — timestamped snapshot of item metrics per run
**`combo_performance_snapshot`** — timestamped snapshot of combo metrics per run

---

## SQL QUERIES TO USE IN CELL 1 (Data Loading)

```sql
-- Menu query
SELECT m.item_id, m.item_name,
       COALESCE(c.name, m.sub_category, 'Other') AS category,
       m.selling_price, m.food_cost
FROM menu m
LEFT JOIN categories c ON c.category_id = m.category_id
WHERE m.is_active = true

-- Sales query
SELECT oi.order_id, oi.item_id, oi.item_name,
       COALESCE(oi.category, c.name, 'Other') AS category,
       oi.quantity, oi.unit_price, oi.discount,
       COALESCE(oi.food_cost_snapshot, m.food_cost, 0) AS food_cost_snapshot,
       o.order_date, o.order_time::text AS order_time,
       COALESCE(o.order_type, 'Dine-in') AS order_type
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
LEFT JOIN menu m ON m.item_id = oi.item_id
LEFT JOIN categories c ON c.category_id = m.category_id
```

> **If your schema differs**, adapt these two queries. The rest of the notebook uses the resulting `menu` and `sales` DataFrames — column names must match exactly:
> - `menu`: `item_id`, `item_name`, `category`, `selling_price`, `food_cost`
> - `sales`: `order_id`, `item_id`, `item_name`, `category`, `quantity`, `unit_price`, `discount`, `food_cost_snapshot`, `order_date`, `order_time`, `order_type`

---

## FULL NOTEBOOK PIPELINE — 9 SECTIONS, 47 CELLS

Generate all sections in order. Do not skip any section.

---

### SECTION 0 — Title & Pipeline (1 markdown cell)

Title: `🍛 [Restaurant Name] — Combo Intelligence Engine`

Pipeline description:
```
1. Load & Validate Data
2. Menu Analysis       → margin classification, item scoring
3. Sales Analysis      → velocity, revenue, time patterns
4. Apriori Mining      → pair co-occurrence, support, confidence, lift
4b. Triplet Mining     → 3-item combos only when genuinely co-purchased
5. Combo Scoring       → multi-factor ranking (pairs)
5b. Triplet Scoring    → same 5-factor framework extended to 3 items
6. Unified Output      → pairs + triplets ranked on same score scale
7. AOV Uplift          → order value impact estimation
8. DB Write            → combo_performance table ready for insert
9. Price Impact        → elasticity analysis & audit trail
```

Triplet logic note:
```
3-item combos are only generated when ALL THREE gates pass:
- Support ≥ 3% of all orders
- All 3 sub-pairs independently pass pair thresholds (no weak links)
- Triplet lift ≥ 20% higher than best constituent pair (adds genuine signal)
```

---

### SECTION 1 — Setup & Imports (1 code cell)

```python
import pandas as pd
import numpy as np
import itertools
import json
import os
import warnings
from collections import defaultdict
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

warnings.filterwarnings('ignore')
pd.set_option('display.max_columns', None)
pd.set_option('display.float_format', '{:.3f}'.format)

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://pos_user:password@localhost:5432/pos_db'
)

def get_conn():
    """Return a fresh psycopg2 connection."""
    return psycopg2.connect(DATABASE_URL)

print('✅ Libraries loaded')
print(f'🔌 DB: {DATABASE_URL.split("@")[-1]}')
```

---

### SECTION 2 — Load & Validate Data (2 code cells)

**Cell 2a** — Load menu and sales from DB using the SQL queries above. After loading:

```python
sales['order_date']   = pd.to_datetime(sales['order_date'])
sales['order_time']   = pd.to_datetime(sales['order_time'], format='%H:%M:%S', errors='coerce').dt.time
sales['hour']         = pd.to_datetime(
    sales['order_time'].astype(str).str[:8], format='%H:%M:%S', errors='coerce'
).dt.hour.fillna(12).astype(int)
sales['net_revenue']  = (sales['unit_price'] * sales['quantity']) - sales['discount'].fillna(0)
sales['gross_profit'] = (sales['unit_price'] - sales['food_cost_snapshot']) * sales['quantity']
```

Print: row counts, order counts, date range.

**Cell 2b** — Data quality checks dict:
```python
checks = {
    'Menu nulls'            : menu.isnull().sum().sum(),
    'Sales nulls (key cols)': sales[['order_id','item_id','unit_price','quantity']].isnull().sum().sum(),
    'Negative prices'       : (sales['unit_price'] <= 0).sum(),
    'Zero quantities'       : (sales['quantity'] <= 0).sum(),
    'Items not in menu'     : (~sales['item_id'].isin(menu['item_id'])).sum(),
    'Duplicate order rows'  : sales.duplicated(['order_id','item_id']).sum(),
}
# Print ✅ or ⚠️ for each
```

---

### SECTION 3 — Past Combo Performance Review (1 markdown + 1 code cell)

Load existing combos from DB using this query:
```sql
SELECT
    c.combo_id, c.combo_label, c.combo_price,
    c.support, c.confidence, c.lift,
    c.times_recommended, c.times_accepted,
    c.total_revenue_generated, c.avg_aov_uplift,
    c.is_active, c.performance_flag,
    c.started_at, c.ended_at,
    MAX(CASE WHEN ci.rn = 1 THEN ci.item_id END) AS item_id_1,
    MAX(CASE WHEN ci.rn = 2 THEN ci.item_id END) AS item_id_2,
    MAX(CASE WHEN ci.rn = 3 THEN ci.item_id END) AS item_id_3
FROM combos c
LEFT JOIN (
    SELECT combo_id, item_id,
           ROW_NUMBER() OVER (PARTITION BY combo_id ORDER BY id) AS rn
    FROM combo_items
) ci ON ci.combo_id = c.combo_id
GROUP BY c.combo_id
ORDER BY c.combo_id
```

Build lookup dicts:
```python
price_map = menu.set_index('item_id')['selling_price'].to_dict()
fc_map    = menu.set_index('item_id')['food_cost'].to_dict()
```

Compute per combo:
- `acceptance_rate` = times_accepted / times_recommended * 100
- `sum_item_prices` and `sum_food_costs` from price_map / fc_map
- `discount_vs_individual` = (sum_item_prices - combo_price) / sum_item_prices * 100
- `combo_margin_pct` = (combo_price - sum_food_costs) / combo_price * 100

Decision logic:
```python
def combo_decision(row):
    flag   = str(row.get('performance_flag', '')).lower()
    rate   = float(row.get('acceptance_rate', 0) or 0)
    active = bool(row.get('is_active', True))
    if not active:                          return 'REMOVE'
    if flag == 'strong' or rate >= 50:      return 'KEEP'
    if flag == 'average' or 30 <= rate < 50: return 'REVIEW'
    return 'REMOVE'
```

Track `active_item_pairs` (frozensets of item pairs with decision == 'KEEP') — used later to avoid re-suggesting existing combos.

Print summary: total, KEEP count, REVIEW count, REMOVE count.

---

### SECTION 4 — Menu Analysis (1 markdown + 2 code cells)

**Cell 4a** — Contribution margin and margin tier:
```python
menu['contribution_margin'] = menu['selling_price'] - menu['food_cost']
menu['margin_pct']          = (menu['contribution_margin'] / menu['selling_price'] * 100).round(1)

def margin_tier(pct):
    if pct >= 60: return 'High'
    if pct >= 45: return 'Medium'
    return 'Low'

menu['margin_tier'] = menu['margin_pct'].apply(margin_tier)
```

Display tier distribution and full table sorted by margin_pct descending.

**Cell 4b** — Category margin summary:
```python
cat_summary = menu.groupby('category').agg(
    item_count        = ('item_id', 'count'),
    avg_selling_price = ('selling_price', 'mean'),
    avg_food_cost     = ('food_cost', 'mean'),
    avg_margin_pct    = ('margin_pct', 'mean'),
).round(1).sort_values('avg_margin_pct', ascending=False)
```

---

### SECTION 5 — Sales Analysis (1 markdown + 4 code cells)

**Cell 5a** — Item-level performance:
```python
item_perf = sales.groupby(['item_id','item_name','category']).agg(
    total_qty_sold  = ('quantity', 'sum'),
    total_orders    = ('order_id', 'nunique'),
    total_revenue   = ('net_revenue', 'sum'),
    total_gp        = ('gross_profit', 'sum'),
    avg_qty_per_day = ('quantity', 'sum'),
).reset_index()

n_days = sales['order_date'].nunique()
item_perf['avg_qty_per_day'] = (item_perf['total_qty_sold'] / n_days).round(2)

# Popularity score normalised 0-100
item_perf['popularity_score'] = (
    (item_perf['total_qty_sold'] - item_perf['total_qty_sold'].min()) /
    (item_perf['total_qty_sold'].max() - item_perf['total_qty_sold'].min()) * 100
).round(1)

# Merge margin info from menu
item_perf = item_perf.merge(
    menu[['item_id','selling_price','contribution_margin','margin_pct','margin_tier']],
    on='item_id'
)
```

Display top 10 by revenue.

**Cell 5b** — BCG classification:
```python
pop_median    = item_perf['popularity_score'].median()
margin_median = item_perf['margin_pct'].median()

def bcg_class(row):
    high_pop    = row['popularity_score'] >= pop_median
    high_margin = row['margin_pct']       >= margin_median
    if high_pop and high_margin:      return 'Star'       # promote heavily
    if high_pop and not high_margin:  return 'Plowhorse'  # reposition / increase price
    if not high_pop and high_margin:  return 'Puzzle'     # needs promotion
    return 'Dog'                                           # consider removing

item_perf['bcg_class'] = item_perf.apply(bcg_class, axis=1)
```

Display classification counts and full table.

**Cell 5c** — Time-of-day session analysis:
```python
sales['session'] = sales['hour'].apply(
    lambda h: 'Lunch' if 11 <= h <= 15 else ('Dinner' if 18 <= h <= 23 else 'Other')
)

session_perf = sales.groupby(['session','category']).agg(
    orders   = ('order_id', 'nunique'),
    qty_sold = ('quantity', 'sum'),
    revenue  = ('net_revenue', 'sum'),
).reset_index().sort_values(['session','revenue'], ascending=[True, False])
```

**Cell 5d** — Order type breakdown (dine_in / delivery / takeaway):
```python
order_type_summary = sales.groupby('order_type').agg(
    orders          = ('order_id', 'nunique'),
    avg_order_value = ('net_revenue', lambda x: (x.sum() / sales.loc[x.index, 'order_id'].nunique())),
    total_revenue   = ('net_revenue', 'sum'),
).round(2)
```

---

### SECTION 6 — Apriori Pair Mining (1 markdown + 2 code cells)

Markdown note: "Custom implementation — no external libraries needed."

**Cell 6a** — Build baskets (orders with 2+ distinct items):
```python
baskets = sales.groupby('order_id')['item_id'].apply(list).reset_index()
baskets.columns = ['order_id', 'items']
baskets['items'] = baskets['items'].apply(lambda x: list(set(x)))
baskets = baskets[baskets['items'].apply(len) >= 2]
total_orders = len(baskets)
```

Print: total orders, avg items/order, max items in one order.

**Cell 6b** — Mine pair rules:
```python
item_counts = defaultdict(int)
for items in baskets['items']:
    for item in items:
        item_counts[item] += 1

item_support = {k: v / total_orders for k, v in item_counts.items()}

pair_counts = defaultdict(int)
for items in baskets['items']:
    for pair in itertools.combinations(sorted(items), 2):
        pair_counts[pair] += 1

MIN_SUPPORT    = 0.05   # pair in ≥ 5% of orders
MIN_CONFIDENCE = 0.20   # 20% of orders with item A also have B
MIN_LIFT       = 1.0    # positive association only

rules = []
for (item_a, item_b), count in pair_counts.items():
    support   = count / total_orders
    if support < MIN_SUPPORT: continue
    conf_ab   = support / item_support.get(item_a, 1e-9)
    conf_ba   = support / item_support.get(item_b, 1e-9)
    lift      = support / (item_support.get(item_a, 1e-9) * item_support.get(item_b, 1e-9))
    if lift >= MIN_LIFT:
        rules.append({
            'item_id_1' : item_a,
            'item_id_2' : item_b,
            'co_count'  : count,
            'support'   : round(support, 4),
            'confidence': round(max(conf_ab, conf_ba), 4),
            'lift'      : round(lift, 4),
        })

rules_df = pd.DataFrame(rules).sort_values('lift', ascending=False)
```

Print: rules found. Display top 10.

---

### SECTION 7 — Multi-Factor Pair Scoring (1 markdown + 3 code cells)

Markdown table:
```
| Factor               | Weight | Rationale                          |
|----------------------|--------|------------------------------------|
| Lift                 | 25%    | Statistical strength of association|
| Combined margin      | 30%    | Business value of the combo        |
| Popularity balance   | 15%    | Avoid pairing two slow-movers      |
| Price complementarity| 15%    | AOV uplift potential               |
| Category compatibility| 15%   | Culinary sense                     |
```

**Cell 7a** — Merge metadata and compute 5 factor scores:

```python
item_meta = item_perf[['item_id','item_name','category','selling_price',
                        'contribution_margin','margin_pct','popularity_score','bcg_class']].copy()

rules_df = rules_df.merge(item_meta.add_suffix('_1').rename(columns={'item_id_1':'item_id_1'}),
                           left_on='item_id_1', right_on='item_id_1')
rules_df = rules_df.merge(item_meta.add_suffix('_2').rename(columns={'item_id_2':'item_id_2'}),
                           left_on='item_id_2', right_on='item_id_2')

# Factor 1: Lift score (normalised 0-100)
rules_df['lift_score'] = (
    (rules_df['lift'] - rules_df['lift'].min()) /
    (rules_df['lift'].max() - rules_df['lift'].min()) * 100
).round(1)

# Factor 2: Combined margin score
rules_df['combined_margin'] = rules_df['contribution_margin_1'] + rules_df['contribution_margin_2']
rules_df['margin_score'] = (
    (rules_df['combined_margin'] - rules_df['combined_margin'].min()) /
    (rules_df['combined_margin'].max() - rules_df['combined_margin'].min()) * 100
).round(1)

# Factor 3: Popularity balance (min of both items' scores)
rules_df['pop_balance'] = rules_df[['popularity_score_1','popularity_score_2']].min(axis=1)
rules_df['popularity_score_combo'] = (
    (rules_df['pop_balance'] - rules_df['pop_balance'].min()) /
    (rules_df['pop_balance'].max() - rules_df['pop_balance'].min()) * 100
).round(1)

# Factor 4: Price complementarity (ideal ratio 2.5x to 6x)
rules_df['price_ratio'] = (
    rules_df[['selling_price_1','selling_price_2']].max(axis=1) /
    rules_df[['selling_price_1','selling_price_2']].min(axis=1)
)
rules_df['price_comp_score'] = rules_df['price_ratio'].apply(
    lambda r: 100 if 2.5 <= r <= 6 else (60 if 1.5 <= r < 2.5 else 20)
)

# Factor 5: Category compatibility
# *** CUSTOMISE THIS DICT FOR YOUR MENU CATEGORIES ***
COMPATIBLE_PAIRS = {
    frozenset(['Main Course', 'Bread'])      : 100,
    frozenset(['Main Course', 'Rice'])       : 100,
    frozenset(['Starter',     'Beverage'])   : 90,
    frozenset(['Main Course', 'Beverage'])   : 80,
    frozenset(['Starter',     'Main Course']): 70,
    frozenset(['Dessert',     'Beverage'])   : 75,
    frozenset(['Main Course', 'Dessert'])    : 60,
}

def cat_compat(row):
    pair = frozenset([row['category_1'], row['category_2']])
    return COMPATIBLE_PAIRS.get(pair, 10)

rules_df['category_score'] = rules_df.apply(cat_compat, axis=1)
```

**Cell 7b** — Weighted composite score and top 15:
```python
WEIGHTS = {
    'lift_score'            : 0.25,
    'margin_score'          : 0.30,
    'popularity_score_combo': 0.15,
    'price_comp_score'      : 0.15,
    'category_score'        : 0.15,
}

rules_df['combo_score'] = sum(
    rules_df[col] * w for col, w in WEIGHTS.items()
).round(1)

top_combos = rules_df.sort_values('combo_score', ascending=False).head(15)
```

Display: item names, categories, support, confidence, lift, combined_margin, combo_score.

**Cell 7c** — Cannibalization filter (remove same-category substitutes):
```python
SUBSTITUTE_CATEGORY_PAIRS = [
    ('Bread', 'Bread'),
    ('Rice', 'Rice'),
    ('Beverage', 'Beverage'),
]

def is_substitute(row):
    pair = (row['category_1'], row['category_2'])
    return pair in SUBSTITUTE_CATEGORY_PAIRS or (pair[1], pair[0]) in SUBSTITUTE_CATEGORY_PAIRS

before = len(top_combos)
top_combos = top_combos[~top_combos.apply(is_substitute, axis=1)]
print(f'Removed {before - len(top_combos)} substitute pairs. Remaining: {len(top_combos)}')
```

---

### SECTION 8 — Triplet Mining (1 markdown + 1 code cell)

Markdown explains: triplets only when all 3 gates pass (support, pair coherence, lift gain).

**Cell 8** — Full triplet mining code:
```python
MIN_TRIPLET_SUPPORT    = 0.03   # ≥ 3% of all orders
MIN_TRIPLET_CONFIDENCE = 0.20
MIN_TRIPLET_LIFT       = 1.5    # stricter than pairs
LIFT_GAIN_THRESHOLD    = 0.20   # triplet lift must be ≥ 20% above best pair

# Build lookup of pair lifts
pair_lift_lookup = {}
for _, r in rules_df.iterrows():
    key = frozenset([r['item_id_1'], r['item_id_2']])
    pair_lift_lookup[key] = max(pair_lift_lookup.get(key, 0), r['lift'])

# Orders with 3+ distinct items only
triplet_baskets  = baskets[baskets['items'].apply(len) >= 3]
n_triplet_orders = len(triplet_baskets)
print(f'Orders with 3+ items : {n_triplet_orders} ({n_triplet_orders/total_orders*100:.1f}%)')

# Count item support across ALL baskets (consistent denominator)
item_counts_all = defaultdict(int)
for items in baskets['items']:
    for item in items:
        item_counts_all[item] += 1

# Count triplet co-occurrences from 3+ item orders
triplet_counts = defaultdict(int)
for items in triplet_baskets['items']:
    for triplet in itertools.combinations(sorted(items), 3):
        triplet_counts[triplet] += 1

print(f'Unique triplets observed: {len(triplet_counts)}')

triplet_rules = []
for (a, b, c), count in triplet_counts.items():
    support = count / total_orders
    if support < MIN_TRIPLET_SUPPORT: continue

    sup_a = item_counts_all[a] / total_orders
    sup_b = item_counts_all[b] / total_orders
    sup_c = item_counts_all[c] / total_orders

    lift = support / (sup_a * sup_b * sup_c)
    if lift < MIN_TRIPLET_LIFT: continue

    min_item_sup = min(sup_a, sup_b, sup_c)
    confidence   = support / min_item_sup if min_item_sup > 0 else 0
    if confidence < MIN_TRIPLET_CONFIDENCE: continue

    # Gate: all 3 sub-pairs must independently pass pair threshold
    sub_pairs      = [frozenset([a,b]), frozenset([b,c]), frozenset([a,c])]
    sub_pair_lifts = [pair_lift_lookup.get(p, 0) for p in sub_pairs]
    if any(l < MIN_LIFT for l in sub_pair_lifts): continue

    best_pair_lift = max(sub_pair_lifts)

    # Gate: triplet lift must be meaningfully higher than best pair
    if lift < best_pair_lift * (1 + LIFT_GAIN_THRESHOLD): continue

    triplet_rules.append({
        'item_id_1'    : a, 'item_id_2': b, 'item_id_3': c,
        'co_count'     : count,
        'support'      : round(support, 4),
        'confidence'   : round(confidence, 4),
        'lift'         : round(lift, 4),
        'best_pair_lift': round(best_pair_lift, 4),
        'lift_gain_pct': round((lift / best_pair_lift - 1) * 100, 1),
    })

triplet_rules_df = pd.DataFrame(triplet_rules).sort_values('lift', ascending=False) \
    if triplet_rules else pd.DataFrame()

print(f'\nTriplet rules passing all filters: {len(triplet_rules_df)}')
if not triplet_rules_df.empty:
    print(triplet_rules_df[['item_id_1','item_id_2','item_id_3',
                             'support','confidence','lift','best_pair_lift','lift_gain_pct']])
else:
    print('No qualifying triplets — pairs are sufficient. This is correct behaviour.')
```

---

### SECTION 9 — Triplet Scoring (1 markdown + 2 code cells)

Markdown: "Same 5-factor framework extended to 3 items. Triplets compete on same score scale as pairs."

**Cell 9a** — Score each triplet:
```python
def score_triplet_row(row):
    ids   = [row['item_id_1'], row['item_id_2'], row['item_id_3']]
    metas = []
    for i in ids:
        m = item_meta[item_meta['item_id'] == i]
        if m.empty: return None
        metas.append(m.iloc[0])

    all_lifts  = list(rules_df['lift']) + [row['lift']]
    lift_min, lift_max = min(all_lifts), max(all_lifts)
    lift_score = (row['lift'] - lift_min) / (lift_max - lift_min) * 100 \
        if lift_max > lift_min else 50.0

    combined_margin  = sum(m['contribution_margin'] for m in metas)
    pop_balance      = min(m['popularity_score'] for m in metas)
    prices           = [m['selling_price'] for m in metas]
    price_ratio      = max(prices) / min(prices) if min(prices) > 0 else 1
    price_comp_score = 100 if 2.5 <= price_ratio <= 8 else (60 if 1.5 <= price_ratio < 2.5 else 20)
    cats             = [m['category'] for m in metas]
    pair_scores      = [COMPATIBLE_PAIRS.get(frozenset([ca,cb]), 10)
                        for ca,cb in itertools.combinations(cats, 2)]
    category_score   = sum(pair_scores) / len(pair_scores) if pair_scores else 10

    return {
        'item_id_1': ids[0], 'item_id_2': ids[1], 'item_id_3': ids[2],
        'item_name_1': metas[0]['item_name'],
        'item_name_2': metas[1]['item_name'],
        'item_name_3': metas[2]['item_name'],
        'category_1' : metas[0]['category'],
        'category_2' : metas[1]['category'],
        'category_3' : metas[2]['category'],
        'support'    : row['support'],
        'confidence' : row['confidence'],
        'lift'       : row['lift'],
        'lift_gain_pct'   : row['lift_gain_pct'],
        'combined_margin' : combined_margin,
        'lift_score'      : round(lift_score, 1),
        'pop_balance'     : pop_balance,
        'price_comp_score': price_comp_score,
        'category_score'  : round(category_score, 1),
    }


if not triplet_rules_df.empty:
    raw_triplets = [score_triplet_row(r) for _, r in triplet_rules_df.iterrows()]
    raw_triplets = [x for x in raw_triplets if x is not None]

    if raw_triplets:
        margins = [x['combined_margin'] for x in raw_triplets]
        pops    = [x['pop_balance']     for x in raw_triplets]
        m_min, m_max = min(margins), max(margins)
        p_min, p_max = min(pops),    max(pops)

        triplet_scored_rows = []
        for s in raw_triplets:
            margin_score = (s['combined_margin'] - m_min) / (m_max - m_min) * 100 \
                if m_max > m_min else 50.0
            pop_score    = (s['pop_balance'] - p_min) / (p_max - p_min) * 100 \
                if p_max > p_min else 50.0
            combo_score = (
                s['lift_score']        * WEIGHTS['lift_score'] +
                margin_score           * WEIGHTS['margin_score'] +
                pop_score              * WEIGHTS['popularity_score_combo'] +
                s['price_comp_score']  * WEIGHTS['price_comp_score'] +
                s['category_score']    * WEIGHTS['category_score']
            )
            s['combo_score'] = round(combo_score, 1)
            triplet_scored_rows.append(s)

        triplet_scored_df = pd.DataFrame(triplet_scored_rows).sort_values('combo_score', ascending=False)

        for _, r in triplet_scored_df.iterrows():
            print(f"  {r['item_name_1']} + {r['item_name_2']} + {r['item_name_3']}")
            print(f"  Score: {r['combo_score']} | Lift: {r['lift']:.3f} "
                  f"(+{r['lift_gain_pct']:.1f}% over best pair) | Margin: {r['combined_margin']}")
    else:
        triplet_scored_df = pd.DataFrame()
else:
    triplet_scored_df = pd.DataFrame()
    print('No triplet rules to score.')
```

**Cell 9b** — Triplet pricing (+2% extra discount over pairs):
```python
def suggest_triplet_price(item_id_1, item_id_2, item_id_3,
                           discount_pct=COMBO_DISCOUNT_PCT,
                           min_margin_pct=MIN_COMBO_MARGIN_PCT):
    ids        = [item_id_1, item_id_2, item_id_3]
    sum_price  = sum(price_map.get(i, 0) for i in ids)
    sum_fc     = sum(fc_map.get(i, 0) for i in ids)
    discounted = sum_price * (1 - (discount_pct + 0.02))
    min_price  = sum_fc / (1 - min_margin_pct)
    return int(round(max(discounted, min_price) / 5) * 5)

if not triplet_scored_df.empty:
    triplet_scored_df = triplet_scored_df.copy()
    triplet_scored_df['sum_item_prices'] = triplet_scored_df.apply(
        lambda r: sum(price_map.get(i,0) for i in [r['item_id_1'],r['item_id_2'],r['item_id_3']]), axis=1)
    triplet_scored_df['suggested_combo_price'] = triplet_scored_df.apply(
        lambda r: suggest_triplet_price(r['item_id_1'],r['item_id_2'],r['item_id_3']), axis=1)
    triplet_scored_df['savings_for_customer'] = (
        triplet_scored_df['sum_item_prices'] - triplet_scored_df['suggested_combo_price'])
    triplet_scored_df['discount_pct'] = (
        triplet_scored_df['savings_for_customer'] / triplet_scored_df['sum_item_prices'] * 100).round(1)
    triplet_scored_df['combo_label'] = (
        triplet_scored_df['item_name_1'] + ' + ' +
        triplet_scored_df['item_name_2'] + ' + ' +
        triplet_scored_df['item_name_3'])
```

---

### SECTION 10 — Unified Output: Pairs + Triplets (1 markdown + 1 code cell)

Merge pair and triplet outputs. Both have `combo_size` column (2 or 3). Sort by `combo_score` descending. Print counts and full ranked table.

---

### SECTION 11 — Session-Specific Combos (1 markdown + 1 code cell)

```python
def get_session_combos(session_name, min_support=0.05):
    session_sales  = sales[sales['session'] == session_name]
    session_orders = session_sales.groupby('order_id')['item_id'].apply(
        lambda x: list(set(x))).reset_index()
    session_orders = session_orders[session_orders['item_id'].apply(len) >= 2]
    n = len(session_orders)
    if n < 10: return pd.DataFrame()

    pair_c = defaultdict(int)
    item_c = defaultdict(int)
    for items in session_orders['item_id']:
        for item in items: item_c[item] += 1
        for pair in itertools.combinations(sorted(items), 2): pair_c[pair] += 1

    rows = []
    for (a, b), cnt in pair_c.items():
        sup  = cnt / n
        lift = sup / ((item_c[a]/n) * (item_c[b]/n))
        if sup >= min_support and lift >= 1.0:
            rows.append({'item_id_1': a, 'item_id_2': b,
                         'support': round(sup,3), 'lift': round(lift,3),
                         'session': session_name, 'session_orders': n})
    return pd.DataFrame(rows).sort_values('lift', ascending=False)

lunch_combos  = get_session_combos('Lunch')
dinner_combos = get_session_combos('Dinner')
```

Print candidate counts for each session. Display top 5 Lunch combos with item names merged in.

---

### SECTION 12 — AOV Uplift Estimation (1 markdown + 1 code cell)

```python
order_aov    = sales.groupby('order_id')['net_revenue'].sum()
baseline_aov = order_aov.mean()

def combo_aov_uplift(item_a, item_b):
    orders_a     = set(sales[sales['item_id'] == item_a]['order_id'])
    orders_b     = set(sales[sales['item_id'] == item_b]['order_id'])
    combo_orders = orders_a & orders_b
    if len(combo_orders) < 3: return 0.0
    return round(order_aov[order_aov.index.isin(combo_orders)].mean() - baseline_aov, 2)

top_combos = top_combos.copy()
top_combos['aov_uplift'] = top_combos.apply(
    lambda r: combo_aov_uplift(r['item_id_1'], r['item_id_2']), axis=1)
```

Print baseline AOV and combo AOV uplift table.

---

### SECTION 13 — Final Combo Output + Pricing (1 markdown + 2 code cells)

Markdown notes dynamic price management:
- Auto-update when item prices change
- Manual % adjustments per combo label

**Cell 13a** — Build `combo_output` DataFrame:

Pricing constants:
```python
COMBO_DISCOUNT_PCT   = 0.12   # ~12% off vs buying individually
MIN_COMBO_MARGIN_PCT = 0.40   # combo must retain ≥ 40% gross margin
```

Pricing function for pairs:
```python
def suggest_combo_price(row):
    items      = [row['item_id_1'], row['item_id_2']]
    sum_price  = sum(price_map.get(i, 0) for i in items)
    sum_fc     = sum(fc_map.get(i, 0) for i in items)
    discounted = sum_price * (1 - COMBO_DISCOUNT_PCT)
    min_price  = sum_fc / (1 - MIN_COMBO_MARGIN_PCT)
    return int(round(max(discounted, min_price) / 5) * 5)
```

Build `combo_output` with these columns:
`item_id_1`, `item_id_2`, `item_id_3` (None for pairs), `combo_label`, `category_pair`, `support`, `confidence`, `lift`, `combined_margin`, `avg_aov_uplift`, `combo_score`, `suggested_combo_price`, `sum_item_prices`, `savings_for_customer`, `discount_pct`, `already_active`, `times_recommended` (0), `times_accepted` (0), `total_revenue_generated` (0.0), `is_active` (True), `performance_flag` ('new')

**Cell 13b** — Price management helper functions:
```python
def recalculate_combo_price(item_id_1, item_id_2,
                             discount_pct=COMBO_DISCOUNT_PCT,
                             min_margin_pct=MIN_COMBO_MARGIN_PCT):
    # Recalculate from current item prices — called on each run for auto-sync
    ...

def adjust_combo_price(current_price, adjustment_pct):
    # Manual % override: +10 = increase 10%, -5 = decrease 5%
    ...

COMBO_PRICE_ADJUSTMENTS = {
    # 'Combo Label': adjustment_pct
}
```

---

### SECTION 14 — Audit & Historical Tracking (1 markdown + 1 code cell)

Define three functions:

```python
def log_price_change(combo_id, combo_label, old_price, new_price, reason='auto_sync'):
    # INSERT into combo_price_history

def snapshot_item_performance(run_id):
    # INSERT into item_performance_snapshot and combo_performance_snapshot

def compare_combo_performance(combo_id, start_date, end_date):
    # SELECT from combo_performance_snapshot for date range
```

---

### SECTION 15 — DB Write (1 code cell)

This is the main write cell. In order:

1. Generate `run_id = f"RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}"`
2. Upsert all rows into `item_performance` table (ON CONFLICT on item_id)
3. Take snapshot: INSERT into `item_performance_snapshot`
4. Auto-sync existing combo prices: for each active combo, recalculate price from current menu prices, log to `combo_price_history` if changed, UPDATE combos table
5. Insert new combos: for each row in `combo_output`, check if item pair already exists in `combo_items` — skip if yes, otherwise INSERT into `combos` and `combo_items`, log initial creation to `combo_price_history`
6. Deactivate REMOVE combos: `UPDATE combos SET is_active = false WHERE combo_id = ANY(%s)`
7. Save CSV backups: `combo_performance.csv`, `item_performance.csv`, `past_combo_decisions.csv`

Create audit tables with `CREATE TABLE IF NOT EXISTS`:
- `combo_price_history` (id, combo_id, combo_label, old_price, new_price, change_reason, changed_at)
- `item_performance_snapshot` (id, run_id, item_id, item_name, total_qty_sold, total_revenue, total_gp, popularity_score, margin_pct, bcg_class, snapshot_date) — UNIQUE(run_id, item_id)
- `combo_performance_snapshot` (id, run_id, combo_id, combo_label, combo_price, acceptance_rate, times_recommended, times_accepted, total_revenue_generated, snapshot_date) — UNIQUE(run_id, combo_id)

---

### SECTION 16 — Summary Dashboard (1 code cell)

Print a formatted summary showing:
- Total orders analysed
- Baseline AOV
- Association rules found
- Past combo health (KEEP / REVIEW / REMOVE with acceptance rate, revenue, price for each)
- New combo suggestions with score, lift, margin, AOV uplift, and suggested price

---

### SECTION 17 — Price Management Guide (1 code cell)

Print a formatted guide explaining:
1. Auto-sync (happens automatically each run)
2. Manual adjustment via `COMBO_PRICE_ADJUSTMENTS` dict
3. Code examples for increase, decrease, and removal

---

### SECTION 18 — Audit Trail Queries (1 code cell)

Query and display `combo_price_history` (last 20 changes). Print example SQL patterns for comparing before/after performance.

---

### SECTION 19 — Price Change Impact Analysis (1 markdown + 3 code cells)

**Cell 19a** — Load snapshots and price_changes from DB, print price change timeline with emoji indicators (📈/📉), print performance comparison (acceptance rate, revenue, recommendations before vs after).

**Cell 19b** — Elasticity analysis:
```python
def analyze_combo_elasticity(combo_label):
    # elasticity = % change in acceptance_rate / % change in price
    # Returns dict with: price_change_pct, acceptance_change_pct, elasticity, revenue_change
```

Print for each combo:
- Price movement
- Acceptance rate response
- Elasticity value with interpretation (elastic/inelastic/premium)
- Revenue impact

**Cell 19c** — Strategic recommendations:
- Successful price increases → increase more
- Failed price increases → hold or reduce
- Positive elasticity → premium positioning
- Elasticity < -1.5 → price sensitive, avoid increases

Print "HOW TO USE THIS ANALYSIS" guide at end.

---

### SECTION 20 — Backend API Integration (1 code cell)

```python
import requests

try:
    response = requests.get('http://localhost:4000/api/analytics/price-impact')
    if response.status_code == 200:
        api_data = response.json()
        # Display: price_changes, elasticity_analysis, recommendations
    else:
        print(f'❌ Backend API Error: {response.status_code}')
except requests.exceptions.ConnectionError:
    print('⚠️  Backend server not running at http://localhost:4000')
except Exception as e:
    print(f'❌ Error: {str(e)}')
```

---

## KEY CUSTOMISATION POINTS (summary)

When adapting to a different database, change only these things:

| What to change | Where |
|---|---|
| DB connection string | Section 1 |
| `menu` SQL query | Section 2 |
| `sales` SQL query | Section 2 |
| `combos` / `combo_items` query | Section 3 |
| `COMPATIBLE_PAIRS` dict | Section 7a — replace category names with your own |
| `SUBSTITUTE_CATEGORY_PAIRS` list | Section 7c — your same-category substitutes |
| Session hours (Lunch/Dinner) | Section 5c — adjust if your meal times differ |
| Currency symbol (₹) | Anywhere it appears in print statements |
| Backend API URL | Section 20 |

---

## TUNABLE PARAMETERS

All in Section 6b and 8:

| Parameter | Default | Effect |
|---|---|---|
| `MIN_SUPPORT` | 0.05 | Lower = more pairs (may include noise) |
| `MIN_CONFIDENCE` | 0.20 | Lower = more pairs |
| `MIN_LIFT` | 1.0 | Raise to 1.5+ for stricter pairs |
| `MIN_TRIPLET_SUPPORT` | 0.03 | Lower than pairs since 3-item orders are rarer |
| `MIN_TRIPLET_LIFT` | 1.5 | Keep this higher than pair lift |
| `LIFT_GAIN_THRESHOLD` | 0.20 | How much extra lift triplet must add over best pair |
| `COMBO_DISCOUNT_PCT` | 0.12 | 12% off vs individual prices |
| `MIN_COMBO_MARGIN_PCT` | 0.40 | Minimum 40% gross margin on any combo |

---

## OUTPUT TABLES WRITTEN TO DATABASE

| Table | Purpose |
|---|---|
| `item_performance` | Current item metrics (upserted each run) |
| `combos` | New combos inserted, weak combos deactivated |
| `combo_items` | Item membership for each combo |
| `combo_price_history` | Immutable audit log of all price changes |
| `item_performance_snapshot` | Timestamped item metrics per run |
| `combo_performance_snapshot` | Timestamped combo metrics per run |

---

## LIBRARIES REQUIRED

```
pandas
numpy
psycopg2-binary
```

No Apriori/mlxtend library needed — the association mining is implemented from scratch using `itertools.combinations` and `collections.defaultdict`.
