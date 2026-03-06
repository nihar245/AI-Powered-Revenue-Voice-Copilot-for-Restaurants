const db = require('../config/db');

function parsePeriod(req) {
  const VALID = { '7d': '7 days', '30d': '30 days', '90d': '90 days', all: null };
  const p = req?.query?.period;
  return Object.prototype.hasOwnProperty.call(VALID, p) ? VALID[p] : null;
}

exports.summary = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pf    = interval ? `AND placed_at >= NOW() - INTERVAL '${interval}'` : '';
    const pfO   = interval ? `AND o.placed_at >= NOW() - INTERVAL '${interval}'` : '';
    const pfOi  = interval ? `AND oi.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';

    const [
      kpiRes,
      foodCostRes,
      dailyTrendRes,
      categoryRes,
      topItemsRes,
      paymentRes,
      channelRes,
      hourlyRes,
      dowRes,
      upsellRes,
    ] = await Promise.all([

      // ── KPIs ──────────────────────────────────────────────────────────────
      db.query(`
        SELECT
          COUNT(*)::int AS total_orders,
          COUNT(*) FILTER (WHERE status != 'cancelled')::int AS completed_orders,
          COUNT(*) FILTER (WHERE status = 'cancelled')::int AS cancelled_orders,
          COALESCE(SUM(total) FILTER (WHERE status != 'cancelled'), 0)::float AS total_revenue,
          COALESCE(ROUND(AVG(total) FILTER (WHERE status != 'cancelled')::numeric, 2), 0)::float AS avg_order_value,
          COALESCE(SUM(tax_amt) FILTER (WHERE status != 'cancelled'), 0)::float AS total_tax
        FROM orders
        WHERE 1=1 ${pf}
      `),

      // ── Food Cost (via order_items snapshot) ────────────────────────────
      db.query(`
        SELECT
          COALESCE(SUM(oi.food_cost), 0)::float AS total_food_cost,
          COALESCE(SUM(oi.revenue), 0)::float    AS items_revenue
        FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id
        WHERE o.status != 'cancelled' ${pfO}
      `),

      // ── Daily Revenue Trend ───────────────────────────────────────────────
      db.query(`
        SELECT
          placed_at::date                                       AS date,
          TO_CHAR(placed_at::date, 'DD Mon')                   AS label,
          COUNT(*)::int                                         AS orders,
          COALESCE(SUM(total), 0)::float                        AS revenue,
          COALESCE(ROUND(AVG(total)::numeric, 2), 0)::float     AS aov
        FROM orders
        WHERE status != 'cancelled' ${pf}
        GROUP BY placed_at::date
        ORDER BY placed_at::date
      `),

      // ── Category Breakdown ────────────────────────────────────────────────
      db.query(`
        SELECT
          mc.name                              AS category,
          COUNT(DISTINCT oi.order_id)::int     AS orders,
          SUM(oi.qty)::int                     AS units_sold,
          COALESCE(SUM(oi.revenue), 0)::float  AS revenue
        FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id
        JOIN menu_items mi ON oi.item_id = mi.item_id
        JOIN menu_categories mc ON mi.category_id = mc.category_id
        WHERE o.status != 'cancelled' ${pfO}
        GROUP BY mc.name
        ORDER BY revenue DESC
      `),

      // ── Top 10 Items ──────────────────────────────────────────────────────
      db.query(`
        SELECT
          mi.name,
          mc.name                              AS category,
          SUM(oi.qty)::int                     AS units_sold,
          COALESCE(SUM(oi.revenue), 0)::float  AS revenue,
          COALESCE(SUM(oi.food_cost), 0)::float AS food_cost
        FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id
        JOIN menu_items mi ON oi.item_id = mi.item_id
        JOIN menu_categories mc ON mi.category_id = mc.category_id
        WHERE o.status != 'cancelled' ${pfO}
        GROUP BY mi.name, mc.name
        ORDER BY revenue DESC
        LIMIT 10
      `),

      // ── Payment Method Split ──────────────────────────────────────────────
      db.query(`
        SELECT
          op.method                            AS payment_method,
          COUNT(DISTINCT o.order_id)::int      AS orders,
          COALESCE(SUM(o.total), 0)::float     AS revenue,
          ROUND(AVG(o.total)::numeric, 2)::float AS avg_order_value
        FROM orders o
        JOIN order_payments op ON o.order_id = op.order_id
        WHERE o.status != 'cancelled' ${pfO}
        GROUP BY op.method
        ORDER BY revenue DESC
      `),

      // ── Channel Split ─────────────────────────────────────────────────────
      db.query(`
        SELECT
          channel,
          COUNT(*)::int                        AS orders,
          COALESCE(SUM(total), 0)::float       AS revenue,
          ROUND(AVG(total)::numeric, 2)::float AS avg_order_value
        FROM orders
        WHERE status != 'cancelled' ${pf}
        GROUP BY channel
        ORDER BY revenue DESC
      `),

      // ── Hourly Pattern ────────────────────────────────────────────────────
      db.query(`
        SELECT
          EXTRACT(HOUR FROM placed_at)::int        AS hour,
          COUNT(*)::int                            AS orders,
          COALESCE(SUM(total), 0)::float           AS revenue,
          ROUND(AVG(total)::numeric, 2)::float     AS avg_order_value
        FROM orders
        WHERE status != 'cancelled' ${pf}
        GROUP BY EXTRACT(HOUR FROM placed_at)
        ORDER BY hour
      `),

      // ── Day of Week Pattern ───────────────────────────────────────────────
      db.query(`
        SELECT
          EXTRACT(DOW FROM placed_at)::int         AS dow,
          TO_CHAR(placed_at, 'Dy')                 AS day,
          COUNT(*)::int                            AS orders,
          COALESCE(SUM(total), 0)::float           AS revenue,
          ROUND(AVG(total)::numeric, 2)::float     AS avg_order_value
        FROM orders
        WHERE status != 'cancelled' ${pf}
        GROUP BY EXTRACT(DOW FROM placed_at), TO_CHAR(placed_at, 'Dy')
        ORDER BY dow
      `),

      // ── Upsell Contribution ───────────────────────────────────────────────
      db.query(`
        SELECT
          COUNT(*)::int                        AS upsell_items,
          COALESCE(SUM(oi.revenue), 0)::float  AS upsell_revenue
        FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id
        WHERE oi.is_upsell = TRUE AND o.status != 'cancelled' ${pfO}
      `),
    ]);

    const kpi       = kpiRes.rows[0];
    const fc        = foodCostRes.rows[0];
    const totalOrds = kpi.total_orders;
    const cancRate  = totalOrds > 0
      ? parseFloat(((kpi.cancelled_orders / totalOrds) * 100).toFixed(1))
      : 0;
    const grossProfit   = parseFloat((kpi.total_revenue - fc.total_food_cost).toFixed(2));
    const grossMarginPct = kpi.total_revenue > 0
      ? parseFloat(((grossProfit / kpi.total_revenue) * 100).toFixed(1))
      : 0;

    res.json({
      kpi: {
        total_orders:       kpi.total_orders,
        completed_orders:   kpi.completed_orders,
        cancelled_orders:   kpi.cancelled_orders,
        total_revenue:      kpi.total_revenue,
        avg_order_value:    kpi.avg_order_value,
        total_tax:          kpi.total_tax,
        total_food_cost:    fc.total_food_cost,
        gross_profit:       grossProfit,
        gross_margin_pct:   grossMarginPct,
        cancellation_rate:  cancRate,
        upsell_revenue:     upsellRes.rows[0]?.upsell_revenue || 0,
        upsell_items:       upsellRes.rows[0]?.upsell_items || 0,
      },
      daily_trend:        dailyTrendRes.rows,
      category_breakdown: categoryRes.rows,
      top_items:          topItemsRes.rows,
      payment_methods:    paymentRes.rows,
      channels:           channelRes.rows,
      hourly_pattern:     hourlyRes.rows,
      day_of_week:        dowRes.rows,
    });
  } catch (err) {
    next(err);
  }
};
