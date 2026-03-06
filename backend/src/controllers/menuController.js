const db = require('../config/db');

exports.getItems = async (_req, res, next) => {
  try {
    const { rows } = await db.query(`
      SELECT
        mi.item_id,
        mi.name,
        mi.description,
        mi.is_veg,
        mi.is_jain,
        mi.is_available,
        mi.tags,
        mi.image_url,
        mc.category_id,
        mc.name AS category,
        json_agg(
          json_build_object(
            'variant_id', mv.variant_id,
            'variant_name', mv.variant_name,
            'selling_price', mv.selling_price,
            'food_cost', mv.food_cost,
            'margin_pct', ROUND((mv.selling_price - mv.food_cost) / NULLIF(mv.selling_price, 0) * 100, 2),
            'gst_pct', mv.gst_pct,
            'is_available', mv.is_available
          ) ORDER BY mv.selling_price
        ) AS variants
      FROM menu_items mi
      JOIN menu_categories mc USING (category_id)
      LEFT JOIN menu_variants mv USING (item_id)
      WHERE mi.is_available = TRUE
      GROUP BY mi.item_id, mi.name, mi.description, mi.is_veg, mi.is_jain,
               mi.is_available, mi.tags, mi.image_url, mc.category_id, mc.name
      ORDER BY mc.display_order, mi.display_order
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

exports.getVariants = async (req, res, next) => {
  try {
    const { item_id } = req.params;
    const { rows } = await db.query(
      `SELECT variant_id, variant_name, selling_price, food_cost,
              ROUND((selling_price - food_cost) / NULLIF(selling_price, 0) * 100, 2) AS margin_pct,
              gst_pct, is_available
       FROM menu_variants WHERE item_id = $1 ORDER BY selling_price`,
      [item_id]
    );
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

exports.getAddons = async (req, res, next) => {
  try {
    const { item_id } = req.params;
    const { rows } = await db.query(
      `SELECT addon_id, addon_name, extra_price, is_available
       FROM menu_addons WHERE item_id = $1 AND is_available = TRUE`,
      [item_id]
    );
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

exports.getCombos = async (_req, res, next) => {
  try {
    const { rows } = await db.query(`
      SELECT
        c.combo_id, c.combo_name, c.description,
        c.selling_price, c.food_cost, c.valid_from, c.valid_to,
        json_agg(
          json_build_object(
            'item_id', ci.item_id,
            'item_name', mi.name,
            'variant_id', ci.variant_id,
            'variant_name', mv.variant_name,
            'qty', ci.qty
          )
        ) AS items
      FROM menu_combos c
      JOIN combo_items ci USING (combo_id)
      JOIN menu_items mi ON ci.item_id = mi.item_id
      LEFT JOIN menu_variants mv ON ci.variant_id = mv.variant_id
      WHERE c.is_active = TRUE
      GROUP BY c.combo_id
      ORDER BY c.combo_name
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};
