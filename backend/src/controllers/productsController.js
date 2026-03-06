const db = require('../config/db');

// ──── List all products (menu items) with variants, categories, recipe cost ───
exports.list = async (_req, res, next) => {
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
        COALESCE(
          json_agg(
            json_build_object(
              'variant_id',    mv.variant_id,
              'variant_name',  mv.variant_name,
              'selling_price', mv.selling_price::float,
              'food_cost',     mv.food_cost::float,
              'gst_pct',       mv.gst_pct::float,
              'is_available',  mv.is_available
            ) ORDER BY mv.selling_price
          ) FILTER (WHERE mv.variant_id IS NOT NULL),
          '[]'
        ) AS variants
      FROM menu_items mi
      JOIN menu_categories mc USING (category_id)
      LEFT JOIN menu_variants mv USING (item_id)
      GROUP BY mi.item_id, mi.name, mi.description, mi.is_veg, mi.is_jain,
               mi.is_available, mi.tags, mi.image_url, mc.category_id, mc.name
      ORDER BY mc.display_order, mi.display_order
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// ──── Get single product with full recipe breakdown ──────────────────────────
exports.get = async (req, res, next) => {
  try {
    const { id } = req.params;

    // Product + category
    const { rows: items } = await db.query(`
      SELECT mi.*, mc.name AS category
      FROM menu_items mi
      JOIN menu_categories mc USING (category_id)
      WHERE mi.item_id = $1
    `, [id]);
    if (items.length === 0) return res.status(404).json({ error: 'Product not found' });

    // Variants
    const { rows: variants } = await db.query(
      `SELECT variant_id, variant_name, selling_price::float, food_cost::float, gst_pct::float, is_available
       FROM menu_variants WHERE item_id = $1 ORDER BY selling_price`, [id]
    );

    // Recipes per variant
    for (const v of variants) {
      const { rows: recipe } = await db.query(`
        SELECT r.recipe_id, r.ing_id, i.name AS ingredient, i.unit,
               r.qty_required::float, i.cost_per_unit::float,
               (r.qty_required * i.cost_per_unit)::float AS line_cost
        FROM recipes r
        JOIN ingredients i USING (ing_id)
        WHERE r.item_id = $1 AND r.variant_id = $2
      `, [id, v.variant_id]);
      v.recipe = recipe;
    }

    res.json({ ...items[0], variants });
  } catch (err) {
    next(err);
  }
};

// ──── List categories (for dropdowns) ────────────────────────────────────────
exports.categories = async (_req, res, next) => {
  try {
    const { rows } = await db.query(
      `SELECT category_id, name, meal_time FROM menu_categories WHERE is_active = TRUE ORDER BY display_order`
    );
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// ──── List all ingredients (for recipe builder) ──────────────────────────────
exports.ingredients = async (_req, res, next) => {
  try {
    const { rows } = await db.query(
      `SELECT ing_id, name, unit, cost_per_unit::float FROM ingredients ORDER BY name`
    );
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// ──── Create a product (item + variants + recipes) ───────────────────────────
// Body shape:
// {
//   name, description, category_id, is_veg, is_jain, tags, image_url,
//   variants: [{ variant_name, selling_price, gst_pct, recipe: [{ ing_id, qty_required }] }]
// }
exports.create = async (req, res, next) => {
  const client = await db.connect();
  try {
    await client.query('BEGIN');
    const { name, description, category_id, is_veg, is_jain, tags, image_url, variants } = req.body;
    if (!name || !category_id || !variants || variants.length === 0) {
      return res.status(400).json({ error: 'name, category_id and at least one variant required' });
    }

    // Insert menu item
    const { rows: itemRows } = await client.query(
      `INSERT INTO menu_items (category_id, name, description, is_veg, is_jain, is_available, tags, image_url)
       VALUES ($1,$2,$3,$4,$5,TRUE,$6,$7) RETURNING item_id`,
      [category_id, name, description || '', is_veg ?? true, is_jain ?? false, tags || null, image_url || null]
    );
    const itemId = itemRows[0].item_id;

    const createdVariants = [];
    for (const v of variants) {
      // Compute food_cost from recipe ingredients
      let foodCost = 0;
      if (v.recipe && v.recipe.length > 0) {
        const ingIds = v.recipe.map(r => r.ing_id);
        const ph = ingIds.map((_, i) => `$${i + 1}`).join(',');
        const { rows: ings } = await client.query(
          `SELECT ing_id, cost_per_unit::float FROM ingredients WHERE ing_id IN (${ph})`, ingIds
        );
        const costMap = Object.fromEntries(ings.map(i => [i.ing_id, i.cost_per_unit]));
        for (const r of v.recipe) {
          foodCost += (costMap[r.ing_id] || 0) * r.qty_required;
        }
      }
      foodCost = Math.round(foodCost * 100) / 100;

      // Insert variant
      const { rows: varRows } = await client.query(
        `INSERT INTO menu_variants (item_id, variant_name, selling_price, food_cost, gst_pct, is_available)
         VALUES ($1,$2,$3,$4,$5,TRUE) RETURNING variant_id`,
        [itemId, v.variant_name, v.selling_price, foodCost, v.gst_pct || 5]
      );
      const variantId = varRows[0].variant_id;

      // Insert recipe rows
      if (v.recipe && v.recipe.length > 0) {
        for (const r of v.recipe) {
          await client.query(
            `INSERT INTO recipes (item_id, variant_id, ing_id, qty_required)
             VALUES ($1,$2,$3,$4)`,
            [itemId, variantId, r.ing_id, r.qty_required]
          );
        }
      }

      createdVariants.push({ variant_id: variantId, variant_name: v.variant_name, food_cost: foodCost });
    }

    await client.query('COMMIT');
    res.status(201).json({ item_id: itemId, name, variants: createdVariants });
  } catch (err) {
    await client.query('ROLLBACK');
    next(err);
  } finally {
    client.release();
  }
};

// ──── Update a product ───────────────────────────────────────────────────────
// Allows updating item details, and full replace of variants + recipes
exports.update = async (req, res, next) => {
  const client = await db.connect();
  try {
    await client.query('BEGIN');
    const { id } = req.params;
    const { name, description, category_id, is_veg, is_jain, tags, image_url, is_available, variants } = req.body;

    // Update item fields
    await client.query(
      `UPDATE menu_items SET
         name = COALESCE($1, name),
         description = COALESCE($2, description),
         category_id = COALESCE($3, category_id),
         is_veg = COALESCE($4, is_veg),
         is_jain = COALESCE($5, is_jain),
         tags = COALESCE($6, tags),
         image_url = COALESCE($7, image_url),
         is_available = COALESCE($8, is_available)
       WHERE item_id = $9`,
      [name, description, category_id, is_veg, is_jain, tags, image_url, is_available, id]
    );

    // If variants provided, replace them entirely
    if (variants && variants.length > 0) {
      // Remove old recipes & variants
      await client.query('DELETE FROM recipes WHERE item_id = $1', [id]);
      await client.query('DELETE FROM menu_variants WHERE item_id = $1', [id]);

      for (const v of variants) {
        let foodCost = 0;
        if (v.recipe && v.recipe.length > 0) {
          const ingIds = v.recipe.map(r => r.ing_id);
          const ph = ingIds.map((_, i) => `$${i + 1}`).join(',');
          const { rows: ings } = await client.query(
            `SELECT ing_id, cost_per_unit::float FROM ingredients WHERE ing_id IN (${ph})`, ingIds
          );
          const costMap = Object.fromEntries(ings.map(i => [i.ing_id, i.cost_per_unit]));
          for (const r of v.recipe) {
            foodCost += (costMap[r.ing_id] || 0) * r.qty_required;
          }
        }
        foodCost = Math.round(foodCost * 100) / 100;

        const { rows: varRows } = await client.query(
          `INSERT INTO menu_variants (item_id, variant_name, selling_price, food_cost, gst_pct, is_available)
           VALUES ($1,$2,$3,$4,$5,TRUE) RETURNING variant_id`,
          [id, v.variant_name, v.selling_price, foodCost, v.gst_pct || 5]
        );
        const variantId = varRows[0].variant_id;

        if (v.recipe && v.recipe.length > 0) {
          for (const r of v.recipe) {
            await client.query(
              `INSERT INTO recipes (item_id, variant_id, ing_id, qty_required) VALUES ($1,$2,$3,$4)`,
              [id, variantId, r.ing_id, r.qty_required]
            );
          }
        }
      }
    }

    await client.query('COMMIT');
    res.json({ success: true, item_id: parseInt(id) });
  } catch (err) {
    await client.query('ROLLBACK');
    next(err);
  } finally {
    client.release();
  }
};

// ──── Soft-delete (toggle availability) ──────────────────────────────────────
exports.remove = async (req, res, next) => {
  try {
    const { id } = req.params;
    await db.query('UPDATE menu_items SET is_available = FALSE WHERE item_id = $1', [id]);
    await db.query('UPDATE menu_variants SET is_available = FALSE WHERE item_id = $1', [id]);
    res.json({ success: true });
  } catch (err) {
    next(err);
  }
};
