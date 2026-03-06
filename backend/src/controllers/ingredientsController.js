const db = require('../config/db');

// GET /api/ingredients — list all ingredients with current unit costs
exports.getIngredients = async (_req, res, next) => {
  try {
    const { rows } = await db.query(`
      SELECT
        ing_id,
        name,
        unit,
        cost_per_unit,
        current_stock,
        min_stock,
        reorder_qty,
        last_restocked_at
      FROM ingredients
      ORDER BY name
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// PUT /api/ingredients/:id/cost — update unit cost (triggers DB recompute)
exports.updateCost = async (req, res, next) => {
  try {
    const { id } = req.params;
    const { cost_per_unit } = req.body;

    const cost = Number(cost_per_unit);
    if (!Number.isFinite(cost) || cost < 0) {
      return res.status(400).json({ error: 'cost_per_unit must be a non-negative number' });
    }

    const { rows } = await db.query(
      `UPDATE ingredients
          SET cost_per_unit = $1
        WHERE ing_id = $2
        RETURNING ing_id, name, unit, cost_per_unit`,
      [cost, id]
    );
    if (!rows.length) return res.status(404).json({ error: 'Ingredient not found' });
    res.json(rows[0]);
  } catch (err) {
    next(err);
  }
};

// GET /api/ingredients/food-costs — all variants with ingredient-computed food cost
exports.getFoodCosts = async (_req, res, next) => {
  try {
    const { rows } = await db.query(`
      SELECT
        variant_id,
        item_id,
        item_name,
        variant_name,
        selling_price,
        stored_food_cost,
        computed_food_cost,
        gross_margin_pct,
        stored_margin_pct
      FROM variant_food_cost_view
      ORDER BY item_name, variant_name
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// GET /api/ingredients/recipe/:variantId — full breakdown for one variant
exports.getRecipe = async (req, res, next) => {
  try {
    const { variantId } = req.params;
    const { rows } = await db.query(`
      SELECT
        variant_id,
        item_id,
        item_name,
        variant_name,
        selling_price,
        stored_food_cost,
        computed_food_cost,
        gross_margin_pct,
        stored_margin_pct,
        recipe_breakdown
      FROM variant_food_cost_view
      WHERE variant_id = $1
    `, [variantId]);

    if (!rows.length) return res.status(404).json({ error: 'Variant not found' });
    res.json(rows[0]);
  } catch (err) {
    next(err);
  }
};

// PUT /api/ingredients/recipe/:variantId — upsert recipe line for a variant
// Body: { ing_id, qty_required }
exports.upsertRecipeLine = async (req, res, next) => {
  try {
    const { variantId } = req.params;
    const { ing_id, qty_required } = req.body;

    const qty = Number(qty_required);
    if (!ing_id || !Number.isFinite(qty) || qty <= 0) {
      return res.status(400).json({ error: 'ing_id and positive qty_required are required' });
    }

    // Verify variant exists
    const check = await db.query(
      `SELECT variant_id FROM menu_variants WHERE variant_id = $1`, [variantId]
    );
    if (!check.rows.length) return res.status(404).json({ error: 'Variant not found' });

    // item_id for the recipe row
    const itemRow = await db.query(
      `SELECT item_id FROM menu_variants WHERE variant_id = $1`, [variantId]
    );

    await db.query(`
      INSERT INTO recipes (item_id, variant_id, ing_id, qty_required)
      VALUES ($1, $2, $3, $4)
      ON CONFLICT (variant_id, ing_id) DO UPDATE SET qty_required = EXCLUDED.qty_required
    `, [itemRow.rows[0].item_id, variantId, ing_id, qty]);

    // Return updated breakdown (trigger already synced food_cost)
    const { rows } = await db.query(`
      SELECT variant_id, item_name, variant_name,
             computed_food_cost, gross_margin_pct, recipe_breakdown
      FROM variant_food_cost_view
      WHERE variant_id = $1
    `, [variantId]);

    res.json(rows[0]);
  } catch (err) {
    next(err);
  }
};

// DELETE /api/ingredients/recipe/:variantId/:ingId — remove one ingredient line
exports.deleteRecipeLine = async (req, res, next) => {
  try {
    const { variantId, ingId } = req.params;
    await db.query(
      `DELETE FROM recipes WHERE variant_id = $1 AND ing_id = $2`,
      [variantId, ingId]
    );
    res.json({ message: 'Recipe line removed' });
  } catch (err) {
    next(err);
  }
};
