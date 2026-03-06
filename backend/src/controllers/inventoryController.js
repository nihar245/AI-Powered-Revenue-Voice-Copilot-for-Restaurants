const db = require('../config/db');

// ──── Inventory-Linked Performance Signals ────────────────────────────────────
// Find menu items (especially Stars/Plowhorses) that are at supply risk because
// one or more of their ingredients is below min_stock threshold.
exports.performanceSignals = async (_req, res, next) => {
  try {
    // Get all ingredients below min_stock
    const { rows: lowStock } = await db.query(`
      SELECT ing_id, name AS ingredient, unit,
             current_stock::float, min_stock::float,
             ROUND((current_stock / NULLIF(min_stock, 0)) * 100, 0)::int AS stock_pct
      FROM ingredients
      WHERE current_stock < min_stock
    `);

    if (lowStock.length === 0) return res.json({ signals: [], low_stock_count: 0 });

    const lowIngIds = lowStock.map(r => r.ing_id);
    const placeholders = lowIngIds.map((_, i) => `$${i + 1}`).join(',');

    // Find menu items that use these ingredients via recipes
    const { rows: atRiskItems } = await db.query(`
      WITH item_perf AS (
        SELECT
          mi.item_id,
          mi.name AS item_name,
          mc.name AS category,
          COALESCE(SUM(oi.qty), 0)::float AS sales_velocity,
          COALESCE(AVG(mv.selling_price - mv.food_cost), 0)::float AS cm_per_unit
        FROM menu_items mi
        LEFT JOIN menu_categories mc ON mi.category_id = mc.category_id
        LEFT JOIN order_items oi ON mi.item_id = oi.item_id
        LEFT JOIN menu_variants mv ON mi.item_id = mv.item_id
        GROUP BY mi.item_id, mi.name, mc.name
      ),
      item_medians AS (
        SELECT
          percentile_cont(0.5) WITHIN GROUP (ORDER BY sales_velocity) AS med_sv,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY cm_per_unit) AS med_cm
        FROM item_perf
      )
      SELECT
        ip.item_id,
        ip.item_name,
        ip.category,
        ip.sales_velocity,
        ip.cm_per_unit,
        CASE
          WHEN ip.sales_velocity >= im.med_sv AND ip.cm_per_unit >= im.med_cm THEN 'Star'
          WHEN ip.sales_velocity < im.med_sv AND ip.cm_per_unit >= im.med_cm THEN 'Puzzle'
          WHEN ip.sales_velocity >= im.med_sv AND ip.cm_per_unit < im.med_cm THEN 'Plowhorse'
          ELSE 'Dog'
        END AS bcg_class,
        r.ing_id
      FROM item_perf ip, item_medians im
      JOIN recipes r ON ip.item_id = r.item_id AND r.ing_id IN (${placeholders})
    `, lowIngIds);

    // Merge in ingredient detail
    const ingMap = Object.fromEntries(lowStock.map(r => [r.ing_id, r]));
    const signals = atRiskItems.map(item => ({
      item_id: item.item_id,
      item_name: item.item_name,
      category: item.category,
      bcg_class: item.bcg_class,
      sales_velocity: Math.round(item.sales_velocity),
      ingredient: ingMap[item.ing_id]?.ingredient,
      current_stock: ingMap[item.ing_id]?.current_stock,
      min_stock: ingMap[item.ing_id]?.min_stock,
      stock_pct: ingMap[item.ing_id]?.stock_pct,
      urgency: item.bcg_class === 'Star' || item.bcg_class === 'Plowhorse' ? 'High' : 'Medium',
    })).sort((a, b) => (a.urgency === 'High' ? -1 : 1) - (b.urgency === 'High' ? -1 : 1) || b.sales_velocity - a.sales_velocity);

    res.json({ signals, low_stock_count: lowStock.length });
  } catch (err) {
    next(err);
  }
};

// Low-stock alerts: ingredients below their min_stock threshold
exports.alerts = async (_req, res, next) => {
  try {
    const { rows } = await db.query(`
      SELECT
        ing_id, name, unit,
        current_stock::float,
        min_stock::float,
        reorder_qty::float,
        cost_per_unit::float,
        last_restocked_at
      FROM ingredients
      WHERE current_stock < min_stock
      ORDER BY (current_stock / NULLIF(min_stock, 0)) ASC
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// Full inventory log (recent entries)
exports.log = async (req, res, next) => {
  try {
    const limit = Math.min(parseInt(req.query.limit, 10) || 100, 500);
    const { rows } = await db.query(`
      SELECT
        il.log_id, i.name AS ingredient, il.change_type,
        il.qty_changed::float, il.reason, il.logged_at
      FROM inventory_log il
      JOIN ingredients i ON il.ing_id = i.ing_id
      ORDER BY il.logged_at DESC
      LIMIT $1
    `, [limit]);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// Full stock overview
exports.stock = async (_req, res, next) => {
  try {
    const { rows } = await db.query(`
      SELECT
        ing_id, name, unit,
        current_stock::float,
        min_stock::float,
        reorder_qty::float,
        cost_per_unit::float,
        last_restocked_at
      FROM ingredients
      ORDER BY name
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// ──── Restock an ingredient ──────────────────────────────────────────────────
exports.restock = async (req, res, next) => {
  try {
    const { ing_id, qty } = req.body;
    if (!ing_id || !qty || qty <= 0) {
      return res.status(400).json({ error: 'ing_id and positive qty required' });
    }
    await db.query(
      `UPDATE ingredients
       SET current_stock = current_stock + $1, last_restocked_at = NOW()
       WHERE ing_id = $2`,
      [qty, ing_id]
    );
    await db.query(
      `INSERT INTO inventory_log (ing_id, change_type, qty_changed, reason, logged_at)
       VALUES ($1, 'restock', $2, $3, NOW())`,
      [ing_id, qty, req.body.reason || 'Manual restock']
    );
    res.json({ success: true });
  } catch (err) {
    next(err);
  }
};

// ──── Add a new ingredient ───────────────────────────────────────────────────
exports.addIngredient = async (req, res, next) => {
  try {
    const { name, unit, current_stock, min_stock, reorder_qty, cost_per_unit } = req.body;
    if (!name || !unit) {
      return res.status(400).json({ error: 'name and unit are required' });
    }
    const { rows } = await db.query(
      `INSERT INTO ingredients (name, unit, current_stock, min_stock, reorder_qty, cost_per_unit, last_restocked_at)
       VALUES ($1, $2, $3, $4, $5, $6, NOW()) RETURNING *`,
      [name, unit, current_stock || 0, min_stock || 0, reorder_qty || 0, cost_per_unit || 0]
    );
    res.status(201).json(rows[0]);
  } catch (err) {
    next(err);
  }
};

// ──── Update ingredient details ──────────────────────────────────────────────
exports.updateIngredient = async (req, res, next) => {
  try {
    const { id } = req.params;
    const { name, unit, min_stock, reorder_qty, cost_per_unit } = req.body;
    const { rows } = await db.query(
      `UPDATE ingredients
       SET name = COALESCE($1, name),
           unit = COALESCE($2, unit),
           min_stock = COALESCE($3, min_stock),
           reorder_qty = COALESCE($4, reorder_qty),
           cost_per_unit = COALESCE($5, cost_per_unit)
       WHERE ing_id = $6 RETURNING *`,
      [name, unit, min_stock, reorder_qty, cost_per_unit, id]
    );
    if (rows.length === 0) return res.status(404).json({ error: 'Ingredient not found' });
    res.json(rows[0]);
  } catch (err) {
    next(err);
  }
};
