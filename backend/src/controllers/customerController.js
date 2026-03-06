const db = require('../config/db');
const mlService = require('../services/mlService');

// Churn risk: proxy to ML if available, else SQL fallback using churn_risk_score column
exports.churnRisk = async (req, res, next) => {
  try {
    const mlResult = await mlService.get('/predict/churn');
    if (mlResult) return res.json(mlResult);

    // SQL fallback — use pre-computed churn_risk_score
    const threshold = parseFloat(req.query.threshold) || 0.6;
    const { rows } = await db.query(`
      SELECT
        customer_id, name, phone, email, segment,
        total_visits, total_spent::float, avg_order_val::float,
        last_visit,
        churn_risk_score::float,
        favourite_item
      FROM customers
      WHERE churn_risk_score > $1
      ORDER BY churn_risk_score DESC
    `, [threshold]);
    res.json({ source: 'sql_fallback', threshold, data: rows });
  } catch (err) {
    next(err);
  }
};

// Customer segment breakdown
exports.segments = async (_req, res, next) => {
  try {
    const { rows } = await db.query(`
      SELECT
        segment,
        COUNT(*)::int AS count,
        ROUND(AVG(total_spent), 2)::float AS avg_spent,
        ROUND(AVG(total_visits), 1)::float AS avg_visits,
        ROUND(AVG(churn_risk_score), 3)::float AS avg_churn_risk
      FROM customers
      GROUP BY segment
      ORDER BY count DESC
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// List customers with optional period filter and search
exports.list = async (req, res, next) => {
  try {
    const { period, q } = req.query;
    const conditions = [];
    const params = [];
    let idx = 1;

    if (period && period !== 'all') {
      const days = { '7d': 7, '30d': 30, '90d': 90 }[period];
      if (days) {
        conditions.push(`last_visit >= CURRENT_DATE - INTERVAL '${days} days'`);
      }
    }

    if (q && q.trim()) {
      conditions.push(`(name ILIKE $${idx} OR phone ILIKE $${idx})`);
      params.push(`%${q.trim()}%`);
      idx++;
    }

    const where = conditions.length > 0 ? 'WHERE ' + conditions.join(' AND ') : '';

    const { rows } = await db.query(`
      SELECT
        customer_id, name, phone, email, segment,
        total_visits, total_spent::float, avg_order_val::float,
        last_visit, first_visit,
        churn_risk_score::float,
        favourite_item, favourite_payment,
        loyalty_points, is_veg, is_jain
      FROM customers
      ${where}
      ORDER BY total_spent DESC
      LIMIT 200
    `, params);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// Search customers by name or phone (typeahead — lightweight)
exports.search = async (req, res, next) => {
  try {
    const q = (req.query.q || '').trim();
    if (!q) return res.json([]);
    const { rows } = await db.query(`
      SELECT customer_id, name, phone, segment, total_visits, last_visit, favourite_item
      FROM customers
      WHERE name ILIKE $1 OR phone ILIKE $1
      ORDER BY total_visits DESC
      LIMIT 10
    `, [`%${q}%`]);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// Single customer by ID with recent orders
exports.getById = async (req, res, next) => {
  try {
    const { id } = req.params;
    const { rows } = await db.query(
      'SELECT * FROM customers WHERE customer_id = $1',
      [id]
    );
    if (rows.length === 0) return res.status(404).json({ error: 'Customer not found' });

    // Fetch last 20 orders for this customer
    const { rows: orders } = await db.query(`
      SELECT
        o.order_id, o.placed_at, o.total::float, o.channel, o.status,
        json_agg(
          json_build_object(
            'item_name', mi.name,
            'variant_name', mv.variant_name,
            'qty', oi.qty
          ) ORDER BY oi.line_id
        ) AS items
      FROM orders o
      LEFT JOIN order_items oi ON o.order_id = oi.order_id
      LEFT JOIN menu_items mi ON oi.item_id = mi.item_id
      LEFT JOIN menu_variants mv ON oi.variant_id = mv.variant_id
      WHERE o.customer_id = $1
      GROUP BY o.order_id
      ORDER BY o.placed_at DESC
      LIMIT 20
    `, [id]);

    res.json({ ...rows[0], recent_orders: orders });
  } catch (err) {
    next(err);
  }
};

// Create new customer
exports.create = async (req, res, next) => {
  try {
    const { phone, name, email, dob, anniversary, is_veg, is_jain, allergies } = req.body;
    if (!phone) return res.status(400).json({ error: 'Phone is required' });

    const { rows } = await db.query(`
      INSERT INTO customers
        (phone, name, email, dob, anniversary, is_veg, is_jain, allergies, first_visit, last_visit)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, CURRENT_DATE, CURRENT_DATE)
      RETURNING *
    `, [
      phone,
      name || null,
      email || null,
      dob || null,
      anniversary || null,
      is_veg || false,
      is_jain || false,
      allergies ? JSON.stringify(allergies) : null,
    ]);
    res.status(201).json(rows[0]);
  } catch (err) {
    if (err.code === '23505') {
      return res.status(409).json({ error: 'A customer with this phone number already exists' });
    }
    next(err);
  }
};

// Bulk recalculate segment + churn_risk_score for every customer
// Segment rules must match generate_data_final.py exactly.
exports.recalculateSegments = async (_req, res, next) => {
  try {
    const { rowCount } = await db.query(`
      UPDATE customers SET
        churn_risk_score = LEAST(
          GREATEST((CURRENT_DATE - last_visit)::numeric / 180, 0),
          1
        ),
        segment = CASE
          WHEN total_spent > 15000 AND total_visits > 20           THEN 'VIP'
          WHEN total_visits > 10                                   THEN 'Regular'
          WHEN last_visit < CURRENT_DATE - INTERVAL '90 days'      THEN 'Lost'
          WHEN total_visits <= 2                                   THEN 'New'
          ELSE 'Occasional'
        END
    `);
    res.json({ updated: rowCount });
  } catch (err) {
    next(err);
  }
};
