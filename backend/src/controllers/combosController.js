const db = require('../config/db');

// ──── List all combos ────────────────────────────────────────────────────────
exports.list = async (_req, res, next) => {
  try {
    const { rows: combos } = await db.query(`
      SELECT mc.combo_id, mc.combo_name, mc.description, mc.selling_price::float,
             mc.food_cost::float, mc.valid_from, mc.valid_to, mc.is_active,
             COALESCE(
               json_agg(
                 json_build_object(
                   'combo_item_id', ci.combo_item_id,
                   'item_id',       ci.item_id,
                   'variant_id',    ci.variant_id,
                   'qty',           ci.qty,
                   'item_name',     mi.name,
                   'variant_name',  mv.variant_name,
                   'selling_price', mv.selling_price::float,
                   'food_cost',     mv.food_cost::float
                 ) ORDER BY ci.combo_item_id
               ) FILTER (WHERE ci.combo_item_id IS NOT NULL),
               '[]'
             ) AS items
      FROM menu_combos mc
      LEFT JOIN combo_items ci USING (combo_id)
      LEFT JOIN menu_items  mi ON ci.item_id = mi.item_id
      LEFT JOIN menu_variants mv ON ci.variant_id = mv.variant_id
      GROUP BY mc.combo_id
      ORDER BY mc.combo_name
    `);

    // compute individual total for each combo so frontend can show savings
    for (const c of combos) {
      c.individual_total = (c.items || []).reduce(
        (sum, i) => sum + (i.selling_price || 0) * (i.qty || 1), 0
      );
      c.savings = Math.max(0, c.individual_total - c.selling_price);
    }

    res.json(combos);
  } catch (err) { next(err); }
};

// ──── Get single combo ───────────────────────────────────────────────────────
exports.get = async (req, res, next) => {
  try {
    const { id } = req.params;
    const { rows } = await db.query(`
      SELECT mc.*, 
             COALESCE(
               json_agg(
                 json_build_object(
                   'combo_item_id', ci.combo_item_id,
                   'item_id',       ci.item_id,
                   'variant_id',    ci.variant_id,
                   'qty',           ci.qty,
                   'item_name',     mi.name,
                   'variant_name',  mv.variant_name,
                   'selling_price', mv.selling_price::float,
                   'food_cost',     mv.food_cost::float
                 ) ORDER BY ci.combo_item_id
               ) FILTER (WHERE ci.combo_item_id IS NOT NULL),
               '[]'
             ) AS items
      FROM menu_combos mc
      LEFT JOIN combo_items ci USING (combo_id)
      LEFT JOIN menu_items  mi ON ci.item_id = mi.item_id
      LEFT JOIN menu_variants mv ON ci.variant_id = mv.variant_id
      WHERE mc.combo_id = $1
      GROUP BY mc.combo_id
    `, [id]);
    if (rows.length === 0) return res.status(404).json({ error: 'Combo not found' });
    res.json(rows[0]);
  } catch (err) { next(err); }
};

// ──── Create combo ───────────────────────────────────────────────────────────
// Body: { combo_name, description, selling_price, valid_from, valid_to, items: [{ item_id, variant_id, qty }] }
exports.create = async (req, res, next) => {
  const client = await db.pool.connect();
  try {
    await client.query('BEGIN');
    const { combo_name, description, selling_price, valid_from, valid_to, items } = req.body;
    if (!combo_name || !selling_price || !items || items.length < 2) {
      return res.status(400).json({ error: 'combo_name, selling_price and at least 2 items required' });
    }

    // compute food_cost from constituent items
    let foodCost = 0;
    for (const it of items) {
      const { rows } = await client.query(
        'SELECT food_cost::float FROM menu_variants WHERE variant_id = $1', [it.variant_id]
      );
      if (rows.length) foodCost += rows[0].food_cost * (it.qty || 1);
    }

    const { rows: comboRows } = await client.query(
      `INSERT INTO menu_combos (combo_name, description, selling_price, food_cost, valid_from, valid_to, is_active)
       VALUES ($1, $2, $3, $4, $5, $6, TRUE) RETURNING combo_id`,
      [combo_name, description || '', selling_price, Math.round(foodCost * 100) / 100,
       valid_from || null, valid_to || null]
    );
    const comboId = comboRows[0].combo_id;

    for (const it of items) {
      await client.query(
        `INSERT INTO combo_items (combo_id, item_id, variant_id, qty) VALUES ($1,$2,$3,$4)`,
        [comboId, it.item_id, it.variant_id, it.qty || 1]
      );
    }

    await client.query('COMMIT');
    res.status(201).json({ combo_id: comboId, combo_name });
  } catch (err) {
    await client.query('ROLLBACK');
    next(err);
  } finally { client.release(); }
};

// ──── Update combo ───────────────────────────────────────────────────────────
exports.update = async (req, res, next) => {
  const client = await db.pool.connect();
  try {
    await client.query('BEGIN');
    const { id } = req.params;
    const { combo_name, description, selling_price, valid_from, valid_to, is_active, items } = req.body;

    let foodCost = null;
    if (items && items.length > 0) {
      foodCost = 0;
      for (const it of items) {
        const { rows } = await client.query(
          'SELECT food_cost::float FROM menu_variants WHERE variant_id = $1', [it.variant_id]
        );
        if (rows.length) foodCost += rows[0].food_cost * (it.qty || 1);
      }
      foodCost = Math.round(foodCost * 100) / 100;
    }

    await client.query(
      `UPDATE menu_combos SET
         combo_name    = COALESCE($1, combo_name),
         description   = COALESCE($2, description),
         selling_price = COALESCE($3, selling_price),
         food_cost     = COALESCE($4, food_cost),
         valid_from    = COALESCE($5, valid_from),
         valid_to      = COALESCE($6, valid_to),
         is_active     = COALESCE($7, is_active)
       WHERE combo_id = $8`,
      [combo_name, description, selling_price, foodCost, valid_from || null, valid_to || null, is_active, id]
    );

    if (items && items.length > 0) {
      await client.query('DELETE FROM combo_items WHERE combo_id = $1', [id]);
      for (const it of items) {
        await client.query(
          `INSERT INTO combo_items (combo_id, item_id, variant_id, qty) VALUES ($1,$2,$3,$4)`,
          [id, it.item_id, it.variant_id, it.qty || 1]
        );
      }
    }

    await client.query('COMMIT');
    res.json({ success: true });
  } catch (err) {
    await client.query('ROLLBACK');
    next(err);
  } finally { client.release(); }
};

// ──── Delete (deactivate) combo ──────────────────────────────────────────────
exports.remove = async (req, res, next) => {
  try {
    await db.query('UPDATE menu_combos SET is_active = FALSE WHERE combo_id = $1', [req.params.id]);
    res.json({ success: true });
  } catch (err) { next(err); }
};
