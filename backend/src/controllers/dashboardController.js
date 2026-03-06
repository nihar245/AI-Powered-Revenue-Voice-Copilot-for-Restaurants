const db = require('../config/db');

// Helper: resolve the target date — accepts ?date=YYYY-MM-DD, defaults to today
function targetDate(req) {
  return req.query.date || new Date().toISOString().slice(0, 10);
}

exports.kpis = async (req, res, next) => {
  try {
    const date = targetDate(req);

    // Current day stats
    const summary = await db.query(`
      SELECT
        COUNT(*)::int AS "totalOrdersToday",
        COALESCE(SUM(total), 0)::float AS "totalRevenue",
        COALESCE(ROUND(AVG(total), 0), 0)::float AS "avgOrderValue"
      FROM orders
      WHERE placed_at::date = $1 AND status != 'cancelled'
    `, [date]);

    // Previous day stats for comparison
    const prev = await db.query(`
      SELECT
        COUNT(*)::int AS "totalOrdersToday",
        COALESCE(SUM(total), 0)::float AS "totalRevenue",
        COALESCE(ROUND(AVG(total), 0), 0)::float AS "avgOrderValue"
      FROM orders
      WHERE placed_at::date = ($1::date - interval '1 day')::date
        AND status != 'cancelled'
    `, [date]);

    const topItem = await db.query(`
      SELECT mi.name
      FROM order_items oi
      JOIN orders o ON oi.order_id = o.order_id
      JOIN menu_items mi ON oi.item_id = mi.item_id
      WHERE o.placed_at::date = $1 AND o.status != 'cancelled'
      GROUP BY mi.name
      ORDER BY SUM(oi.qty) DESC
      LIMIT 1
    `, [date]);

    const cur = summary.rows[0];
    const prv = prev.rows[0];
    const pct = (c, p) => p ? Math.round(((c - p) / p) * 100 * 10) / 10 : null;

    res.json({
      ...cur,
      topSellingItem: topItem.rows.length > 0 ? topItem.rows[0].name : 'None',
      changes: {
        orders: pct(cur.totalOrdersToday, prv.totalOrdersToday),
        revenue: pct(cur.totalRevenue, prv.totalRevenue),
        aov: pct(cur.avgOrderValue, prv.avgOrderValue),
      },
    });
  } catch (err) {
    next(err);
  }
};

exports.hourlyOrders = async (req, res, next) => {
  try {
    const date = targetDate(req);
    const { rows } = await db.query(`
      SELECT
        TO_CHAR(placed_at, 'HH12AM') AS time,
        EXTRACT(HOUR FROM placed_at)::int AS hour,
        COUNT(*)::int AS orders,
        COALESCE(SUM(total), 0)::float AS revenue
      FROM orders
      WHERE placed_at::date = $1 AND status != 'cancelled'
      GROUP BY EXTRACT(HOUR FROM placed_at), TO_CHAR(placed_at, 'HH12AM')
      ORDER BY hour
    `, [date]);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

exports.topItems = async (req, res, next) => {
  try {
    const date = targetDate(req);
    const { rows } = await db.query(`
      SELECT
        mi.name,
        SUM(oi.qty)::int AS orders,
        SUM(oi.revenue)::float AS revenue
      FROM order_items oi
      JOIN orders o ON oi.order_id = o.order_id
      JOIN menu_items mi ON oi.item_id = mi.item_id
      WHERE o.placed_at::date = $1 AND o.status != 'cancelled'
      GROUP BY mi.name
      ORDER BY orders DESC
      LIMIT 10
    `, [date]);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

exports.weeklyRevenue = async (req, res, next) => {
  try {
    const date = targetDate(req);
    const { rows } = await db.query(`
      SELECT
        TO_CHAR(placed_at::date, 'Dy') AS day,
        placed_at::date AS date,
        SUM(total)::float AS revenue
      FROM orders
      WHERE placed_at::date BETWEEN ($1::date - INTERVAL '6 days') AND $1::date
        AND status != 'cancelled'
      GROUP BY placed_at::date
      ORDER BY placed_at::date
    `, [date]);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};
