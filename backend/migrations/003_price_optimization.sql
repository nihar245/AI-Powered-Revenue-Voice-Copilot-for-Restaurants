-- Migration 003: Price optimisation audit trail + new item tracking
-- Idempotent — safe to re-run.

-- Audit log for every accepted/rejected price change recommendation
CREATE TABLE IF NOT EXISTS price_change_log (
  id                   SERIAL PRIMARY KEY,
  item_id              INT REFERENCES menu_items(item_id),
  item_name            TEXT,
  old_price            NUMERIC(10,2),
  recommended_price    NUMERIC(10,2),
  change_pct           NUMERIC(6,2),
  direction            TEXT,          -- 'increase' | 'decrease' | 'maintain'
  reason               TEXT,
  status               TEXT DEFAULT 'pending',  -- 'pending' | 'accepted' | 'rejected'
  actual_elasticity    NUMERIC(8,4),   -- filled later when admin records actual demand impact
  recommended_at       TIMESTAMPTZ DEFAULT NOW(),
  changed_at           TIMESTAMPTZ
);

-- New-item tracking columns on menu_items
ALTER TABLE menu_items
  ADD COLUMN IF NOT EXISTS first_ordered_at   TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS total_orders_ever  INT DEFAULT 0;

-- Backfill lifetime order counts for existing items
UPDATE menu_items mi
SET total_orders_ever = sub.cnt
FROM (
  SELECT item_id, COUNT(*) AS cnt
  FROM order_items
  GROUP BY item_id
) sub
WHERE mi.item_id = sub.item_id
  AND mi.total_orders_ever = 0;

-- Backfill first_ordered_at for existing items
UPDATE menu_items mi
SET first_ordered_at = sub.first_at
FROM (
  SELECT oi.item_id, MIN(o.placed_at) AS first_at
  FROM order_items oi
  JOIN orders o USING (order_id)
  GROUP BY oi.item_id
) sub
WHERE mi.item_id = sub.item_id
  AND mi.first_ordered_at IS NULL;
