-- Migration 004: New-item support views
-- Idempotent — safe to re-run.

-- View that flags menu items with < 50 lifetime orders or added in the last 30 days
CREATE OR REPLACE VIEW new_items_view AS
SELECT
  mi.item_id,
  mi.name,
  COALESCE(mi.total_orders_ever, 0)  AS total_orders_ever,
  mi.first_ordered_at,
  (
    COALESCE(mi.total_orders_ever, 0) < 50
    OR mi.first_ordered_at > NOW() - INTERVAL '30 days'
  ) AS is_new_item
FROM menu_items mi;

-- Coverage view: which items have had orders in the last 60 days
CREATE OR REPLACE VIEW item_pricing_coverage AS
SELECT
  mi.item_id,
  mi.name,
  COUNT(DISTINCT oi.order_id) AS orders_60d,
  MAX(o.placed_at)            AS last_ordered_at
FROM menu_items mi
LEFT JOIN order_items oi ON mi.item_id = oi.item_id
LEFT JOIN orders o       ON oi.order_id = o.order_id
  AND o.placed_at >= NOW() - INTERVAL '60 days'
GROUP BY mi.item_id, mi.name;
