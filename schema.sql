-- ============================================================
-- PetPooja Restaurant Database Schema
-- PostgreSQL | Run this first in pgAdmin Query Tool
-- ============================================================

-- Drop existing tables if rerunning
DROP TABLE IF EXISTS feedback CASCADE;
DROP TABLE IF EXISTS offer_redemptions CASCADE;
DROP TABLE IF EXISTS kot_items CASCADE;
DROP TABLE IF EXISTS kot CASCADE;
DROP TABLE IF EXISTS order_addons CASCADE;
DROP TABLE IF EXISTS order_payments CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS inventory_log CASCADE;
DROP TABLE IF EXISTS recipes CASCADE;
DROP TABLE IF EXISTS ingredients CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS upsell_rules CASCADE;
DROP TABLE IF EXISTS combo_items CASCADE;
DROP TABLE IF EXISTS menu_combos CASCADE;
DROP TABLE IF EXISTS offers CASCADE;
DROP TABLE IF EXISTS menu_addons CASCADE;
DROP TABLE IF EXISTS menu_variants CASCADE;
DROP TABLE IF EXISTS menu_items CASCADE;
DROP TABLE IF EXISTS menu_categories CASCADE;
DROP TABLE IF EXISTS restaurants CASCADE;

-- ============================================================
-- LEVEL 1: RESTAURANT CORE
-- ============================================================
CREATE TABLE restaurants (
    restaurant_id       SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    address             TEXT,
    city                VARCHAR(50),
    cuisine_type        VARCHAR(50),
    gstin               VARCHAR(15),
    fssai_no            VARCHAR(20),
    opening_time        TIME DEFAULT '08:00:00',
    closing_time        TIME DEFAULT '23:00:00',
    seating_capacity    INT DEFAULT 50,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- LEVEL 2: MENU
-- ============================================================
CREATE TABLE menu_categories (
    category_id         SERIAL PRIMARY KEY,
    name                VARCHAR(50) NOT NULL,
    display_order       INT DEFAULT 0,
    is_active           BOOLEAN DEFAULT TRUE,
    meal_time           VARCHAR(20) DEFAULT 'all'
                        CHECK (meal_time IN ('breakfast','lunch','dinner','all'))
);

CREATE TABLE menu_items (
    item_id             SERIAL PRIMARY KEY,
    category_id         INT REFERENCES menu_categories(category_id),
    name                VARCHAR(100) NOT NULL,
    description         TEXT,
    is_veg              BOOLEAN DEFAULT TRUE,
    is_jain             BOOLEAN DEFAULT FALSE,
    is_available        BOOLEAN DEFAULT TRUE,
    display_order       INT DEFAULT 0,
    tags                TEXT[],  -- {bestseller, spicy, new, chef_special}
    image_url           VARCHAR(255),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE menu_variants (
    variant_id          SERIAL PRIMARY KEY,
    item_id             INT REFERENCES menu_items(item_id),
    variant_name        VARCHAR(50) NOT NULL,  -- Half, Full, Small, Medium, Large
    selling_price       NUMERIC(10,2) NOT NULL,
    food_cost           NUMERIC(10,2) NOT NULL,
    gst_pct             NUMERIC(4,2) DEFAULT 5.00
                        CHECK (gst_pct IN (0, 5, 12, 18)),
    is_available        BOOLEAN DEFAULT TRUE
);

CREATE TABLE menu_addons (
    addon_id            SERIAL PRIMARY KEY,
    item_id             INT REFERENCES menu_items(item_id),
    addon_name          VARCHAR(100) NOT NULL,
    extra_price         NUMERIC(10,2) DEFAULT 0,
    food_cost           NUMERIC(10,2) DEFAULT 0,
    is_available        BOOLEAN DEFAULT TRUE
);

CREATE TABLE menu_combos (
    combo_id            SERIAL PRIMARY KEY,
    combo_name          VARCHAR(100) NOT NULL,
    description         TEXT,
    selling_price       NUMERIC(10,2) NOT NULL,
    food_cost           NUMERIC(10,2) NOT NULL,
    valid_from          DATE,
    valid_to            DATE,
    is_active           BOOLEAN DEFAULT TRUE
);

CREATE TABLE combo_items (
    combo_item_id       SERIAL PRIMARY KEY,
    combo_id            INT REFERENCES menu_combos(combo_id),
    item_id             INT REFERENCES menu_items(item_id),
    variant_id          INT REFERENCES menu_variants(variant_id),
    qty                 INT DEFAULT 1
);

-- ============================================================
-- LEVEL 3: INVENTORY
-- ============================================================
CREATE TABLE ingredients (
    ing_id              SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    unit                VARCHAR(20) NOT NULL,  -- kg, litre, pieces, grams
    current_stock       NUMERIC(10,3) DEFAULT 0,
    min_stock           NUMERIC(10,3) DEFAULT 0,
    reorder_qty         NUMERIC(10,3) DEFAULT 0,
    cost_per_unit       NUMERIC(10,2) DEFAULT 0,
    last_restocked_at   TIMESTAMP
);

CREATE TABLE recipes (
    recipe_id           SERIAL PRIMARY KEY,
    item_id             INT REFERENCES menu_items(item_id),
    variant_id          INT REFERENCES menu_variants(variant_id),
    ing_id              INT REFERENCES ingredients(ing_id),
    qty_required        NUMERIC(10,4) NOT NULL  -- qty of ingredient per serving
);

CREATE TABLE inventory_log (
    log_id              SERIAL PRIMARY KEY,
    ing_id              INT REFERENCES ingredients(ing_id),
    change_type         VARCHAR(20) NOT NULL
                        CHECK (change_type IN ('restock','consumed','wasted','adjusted')),
    qty_changed         NUMERIC(10,3) NOT NULL,
    reason              TEXT,
    logged_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- LEVEL 4: CUSTOMERS
-- ============================================================
CREATE TABLE customers (
    customer_id         SERIAL PRIMARY KEY,
    phone               VARCHAR(15) UNIQUE NOT NULL,
    name                VARCHAR(100),
    email               VARCHAR(100),
    dob                 DATE,
    anniversary         DATE,
    is_veg              BOOLEAN DEFAULT FALSE,
    is_jain             BOOLEAN DEFAULT FALSE,
    allergies           TEXT[],
    loyalty_points      INT DEFAULT 0,
    total_visits        INT DEFAULT 0,
    total_spent         NUMERIC(12,2) DEFAULT 0,
    avg_order_val       NUMERIC(10,2) DEFAULT 0,
    first_visit         DATE,
    last_visit          DATE,
    favourite_item      VARCHAR(100),
    favourite_payment   VARCHAR(20),
    churn_risk_score    NUMERIC(4,3) DEFAULT 0,  -- 0 to 1
    segment             VARCHAR(20) DEFAULT 'New'
                        CHECK (segment IN ('VIP','Regular','Occasional','Lost','New')),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- LEVEL 5: OFFERS
-- ============================================================
CREATE TABLE offers (
    offer_id            SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    type                VARCHAR(20) NOT NULL
                        CHECK (type IN ('flat','pct','bogo','combo','happy_hour')),
    discount_value      NUMERIC(10,2) NOT NULL,
    min_order_val       NUMERIC(10,2) DEFAULT 0,
    applicable_items    INT[],   -- array of item_ids, NULL = all items
    applicable_channels TEXT[],  -- {dine_in, takeaway, zomato, swiggy, phone}
    valid_from          DATE NOT NULL,
    valid_to            DATE NOT NULL,
    usage_limit         INT DEFAULT 999999,
    used_count          INT DEFAULT 0,
    is_active           BOOLEAN DEFAULT TRUE
);

-- ============================================================
-- LEVEL 5.5: UPSELL RULES
-- ============================================================
CREATE TABLE upsell_rules (
    rule_id         SERIAL PRIMARY KEY,
    trigger_item    VARCHAR(100) NOT NULL,  -- exact menu item name that triggers suggestion
    suggest_item    VARCHAR(100) NOT NULL,  -- exact menu item name to suggest
    reason          TEXT NOT NULL,          -- voice-friendly reason (used directly in AI prompt)
    weight          SMALLINT DEFAULT 5      -- 1 (low) to 10 (high) — higher = suggest first
                    CHECK (weight BETWEEN 1 AND 10),
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_upsell_rules_trigger ON upsell_rules (LOWER(trigger_item)) WHERE is_active = TRUE;

-- ============================================================
-- LEVEL 6: ORDERS
-- ============================================================
CREATE TABLE orders (
    order_id            SERIAL PRIMARY KEY,
    restaurant_id       INT REFERENCES restaurants(restaurant_id),
    customer_id         INT REFERENCES customers(customer_id), -- NULL for walk-ins
    placed_by           VARCHAR(100),   -- staff name
    channel             VARCHAR(20) NOT NULL
                        CHECK (channel IN ('dine_in','takeaway','zomato','swiggy','phone')),
    status              VARCHAR(20) DEFAULT 'delivered'
                        CHECK (status IN ('placed','preparing','ready','delivered','cancelled')),
    placed_at           TIMESTAMP NOT NULL,
    delivered_at        TIMESTAMP,
    subtotal            NUMERIC(10,2) NOT NULL,
    discount_amt        NUMERIC(10,2) DEFAULT 0,
    tax_amt             NUMERIC(10,2) DEFAULT 0,
    total               NUMERIC(10,2) NOT NULL,
    payment_status      VARCHAR(20) DEFAULT 'paid'
                        CHECK (payment_status IN ('paid','pending','failed','refunded'))
);

CREATE TABLE order_items (
    line_id             SERIAL PRIMARY KEY,
    order_id            INT REFERENCES orders(order_id),
    item_id             INT REFERENCES menu_items(item_id),
    variant_id          INT REFERENCES menu_variants(variant_id),
    qty                 INT NOT NULL DEFAULT 1,
    unit_price          NUMERIC(10,2) NOT NULL,
    discount_pct        NUMERIC(4,2) DEFAULT 0,
    revenue             NUMERIC(10,2) NOT NULL,
    food_cost           NUMERIC(10,2) NOT NULL,
    gst_amt             NUMERIC(10,2) DEFAULT 0,
    special_instructions TEXT,
    is_upsell           BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS upsell_events (
    event_id            SERIAL PRIMARY KEY,
    order_id            INT REFERENCES orders(order_id),
    item_id             INT REFERENCES menu_items(item_id),
    variant_id          INT REFERENCES menu_variants(variant_id),
    trigger_item_name   VARCHAR(150),
    revenue             NUMERIC(10,2),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE order_addons (
    addon_line_id       SERIAL PRIMARY KEY,
    line_id             INT REFERENCES order_items(line_id),
    addon_id            INT REFERENCES menu_addons(addon_id),
    qty                 INT DEFAULT 1,
    price               NUMERIC(10,2) NOT NULL
);

CREATE TABLE order_payments (
    payment_id          SERIAL PRIMARY KEY,
    order_id            INT REFERENCES orders(order_id),
    method              VARCHAR(20) NOT NULL
                        CHECK (method IN ('cash','upi','credit_card','debit_card','wallet','razorpay','online')),
    amount              NUMERIC(10,2) NOT NULL,
    transaction_ref     VARCHAR(100),
    paid_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- LEVEL 7: KITCHEN
-- ============================================================
CREATE TABLE kot (
    kot_id              SERIAL PRIMARY KEY,
    order_id            INT REFERENCES orders(order_id),
    status              VARCHAR(20) DEFAULT 'ready'
                        CHECK (status IN ('pending','preparing','ready')),
    priority            VARCHAR(10) DEFAULT 'normal'
                        CHECK (priority IN ('normal','urgent')),
    created_at          TIMESTAMP NOT NULL,
    completed_at        TIMESTAMP
);

CREATE TABLE kot_items (
    kot_item_id         SERIAL PRIMARY KEY,
    kot_id              INT REFERENCES kot(kot_id),
    item_id             INT REFERENCES menu_items(item_id),
    variant_id          INT REFERENCES menu_variants(variant_id),
    qty                 INT NOT NULL,
    addons              TEXT,
    special_instructions TEXT,
    status              VARCHAR(20) DEFAULT 'ready'
                        CHECK (status IN ('pending','preparing','ready'))
);

-- ============================================================
-- LEVEL 8: OFFER REDEMPTIONS
-- ============================================================
CREATE TABLE offer_redemptions (
    redemption_id       SERIAL PRIMARY KEY,
    offer_id            INT REFERENCES offers(offer_id),
    order_id            INT REFERENCES orders(order_id),
    customer_id         INT REFERENCES customers(customer_id),
    discount_applied    NUMERIC(10,2) NOT NULL,
    redeemed_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- LEVEL 9: FEEDBACK
-- ============================================================
CREATE TABLE feedback (
    feedback_id         SERIAL PRIMARY KEY,
    order_id            INT REFERENCES orders(order_id),
    customer_id         INT REFERENCES customers(customer_id),
    overall_rating      INT CHECK (overall_rating BETWEEN 1 AND 5),
    food_rating         INT CHECK (food_rating BETWEEN 1 AND 5),
    service_rating      INT CHECK (service_rating BETWEEN 1 AND 5),
    comment             TEXT,
    sentiment           VARCHAR(10)
                        CHECK (sentiment IN ('positive','neutral','negative')),
    submitted_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- INDEXES for query performance
-- ============================================================
CREATE INDEX idx_orders_placed_at      ON orders(placed_at);
CREATE INDEX idx_orders_customer       ON orders(customer_id);
CREATE INDEX idx_orders_channel        ON orders(channel);
CREATE INDEX idx_order_items_order     ON order_items(order_id);
CREATE INDEX idx_order_items_item      ON order_items(item_id);
CREATE INDEX idx_inventory_log_ing     ON inventory_log(ing_id);
CREATE INDEX idx_inventory_log_type    ON inventory_log(change_type);
CREATE INDEX idx_feedback_order        ON feedback(order_id);
CREATE INDEX idx_customers_phone       ON customers(phone);
CREATE INDEX idx_customers_segment     ON customers(segment);
CREATE INDEX idx_kot_order             ON kot(order_id);
CREATE INDEX idx_kot_status            ON kot(status);

-- ============================================================
SELECT 'Schema created successfully — 18 tables ready' AS status;