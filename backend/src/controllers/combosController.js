const db = require('../config/db');

// ── GET /api/combos/suggestions ─────────────────────────────────────────────
// Returns paginated combo suggestions ranked by combo_score.
// Falls back gracefully if the combo_score / combo_size columns don't exist yet
// (migration 002 not yet applied).
exports.getSuggestions = async (req, res, next) => {
  try {
    let page  = Math.max(1, parseInt(req.query.page,  10) || 1);
    let limit = Math.min(20, Math.max(1, parseInt(req.query.limit, 10) || 5));
    const offset = (page - 1) * limit;

    // Total active combos
    const { rows: countRows } = await db.query(`
      SELECT COUNT(*)::int AS total
      FROM menu_combos
      WHERE is_active = TRUE
    `);
    const total       = countRows[0].total;
    const total_pages = Math.max(1, Math.ceil(total / limit));
    page = Math.min(page, total_pages);

    if (total === 0) {
      return res.json({ total: 0, page, limit, total_pages: 0, combos: [] });
    }

    // Paginated combo rows — COALESCE handles tables without migration 002
    const { rows: comboRows } = await db.query(`
      SELECT
        combo_id,
        combo_name,
        description,
        selling_price::float            AS combo_price,
        COALESCE(combo_size, 2)::int    AS combo_size,
        COALESCE(combo_score, 0)::float AS combo_score,
        COALESCE(lift, 1)::float        AS lift
      FROM menu_combos
      WHERE is_active = TRUE
      ORDER BY
        COALESCE(combo_score, 0) DESC,
        COALESCE(combo_size,  2) DESC,
        combo_id ASC
      LIMIT $1 OFFSET $2
    `, [limit, offset]);

    if (comboRows.length === 0) {
      return res.json({ total, page, limit, total_pages, combos: [] });
    }

    const comboIds = comboRows.map(c => c.combo_id);

    // Fetch items for all returned combos in one query
    // Average selling_price across variants as item price
    const { rows: itemRows } = await db.query(`
      SELECT
        ci.combo_id,
        ci.item_id,
        ci.qty,
        mi.name,
        COALESCE(
          (SELECT AVG(mv.selling_price)::float
           FROM menu_variants mv
           WHERE mv.item_id = ci.item_id),
          0
        ) AS price
      FROM combo_items ci
      JOIN menu_items mi ON ci.item_id = mi.item_id
      WHERE ci.combo_id = ANY($1::int[])
      ORDER BY ci.combo_id, ci.combo_item_id
    `, [comboIds]);

    // Group items by combo_id
    const itemsByCombo = {};
    for (const row of itemRows) {
      if (!itemsByCombo[row.combo_id]) itemsByCombo[row.combo_id] = [];
      itemsByCombo[row.combo_id].push({
        item_id: row.item_id,
        name:    row.name,
        price:   row.price,
        qty:     row.qty,
      });
    }

    const combos = comboRows.map(c => {
      const items         = itemsByCombo[c.combo_id] || [];
      const original_price = items.reduce((sum, i) => sum + (i.price * i.qty), 0);
      const saving        = Math.max(0, Math.floor(original_price - c.combo_price));
      const saving_pct    = original_price > 0
        ? Math.round((saving / original_price) * 100)
        : 0;

      return {
        combo_id:       c.combo_id,
        combo_name:     c.combo_name,
        combo_label:    items.map(i => i.name).join(' + ') || c.combo_name,
        description:    c.description,
        combo_size:     c.combo_size,
        combo_price:    c.combo_price,
        original_price: Math.round(original_price),
        saving,
        saving_pct,
        combo_score:    c.combo_score,
        lift:           c.lift,
        items,
      };
    });

    res.json({ total, page, limit, total_pages, combos });
  } catch (err) {
    next(err);
  }
};
