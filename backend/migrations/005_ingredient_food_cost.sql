-- ============================================================
-- Migration 005: Ingredient-Based Food Cost Calculation
-- Populates ingredients, recipes, creates view + triggers,
-- then back-fills menu_variants.food_cost from actual recipes.
-- ============================================================

-- ── Step 1: Add unique constraints (idempotent) ────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_ingredients_name'
  ) THEN
    ALTER TABLE ingredients ADD CONSTRAINT uq_ingredients_name UNIQUE (name);
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_recipes_variant_ingredient'
  ) THEN
    ALTER TABLE recipes ADD CONSTRAINT uq_recipes_variant_ingredient
      UNIQUE (variant_id, ing_id);
  END IF;
END;
$$;

-- ── Step 2: Seed common ingredients with realistic INR unit costs ──────────
INSERT INTO ingredients (name, unit, cost_per_unit, min_stock, reorder_qty) VALUES
  ('Basmati Rice',      'kg',      120.00, 5.000, 10.000),
  ('Whole Wheat Flour', 'kg',       40.00, 3.000,  5.000),
  ('Chicken (fresh)',   'kg',      180.00, 2.000,  5.000),
  ('Mutton (fresh)',    'kg',      600.00, 1.000,  3.000),
  ('Paneer',            'kg',      280.00, 1.000,  2.000),
  ('Urad Dal',          'kg',      120.00, 2.000,  4.000),
  ('Rajma',             'kg',      100.00, 1.000,  2.000),
  ('Chana',             'kg',       80.00, 1.000,  2.000),
  ('Milk',              'litre',    60.00, 2.000,  4.000),
  ('Fresh Cream',       'litre',   120.00, 0.500,  1.000),
  ('Curd',              'kg',       60.00, 1.000,  2.000),
  ('Butter',            'kg',      500.00, 0.500,  1.000),
  ('Ghee',              'kg',      600.00, 0.500,  1.000),
  ('Khoya',             'kg',      300.00, 0.500,  1.000),
  ('Cooking Oil',       'litre',   120.00, 1.000,  2.000),
  ('Tomatoes',          'kg',       30.00, 2.000,  4.000),
  ('Onions',            'kg',       25.00, 3.000,  5.000),
  ('Garlic',            'kg',      150.00, 0.500,  1.000),
  ('Ginger',            'kg',      100.00, 0.250,  0.500),
  ('Spinach',           'kg',       30.00, 1.000,  2.000),
  ('Bell Pepper',       'kg',       60.00, 0.500,  1.000),
  ('Carrots',           'kg',       30.00, 1.000,  2.000),
  ('Cucumber',          'kg',       20.00, 0.500,  1.000),
  ('Spice Mix',         'kg',      500.00, 0.500,  1.000),
  ('Sugar',             'kg',       45.00, 2.000,  3.000),
  ('Rose Water',        'litre',   200.00, 0.250,  0.500),
  ('Mango Pulp',        'kg',      100.00, 0.500,  1.000),
  ('Cashews',           'kg',      800.00, 0.250,  0.500),
  ('Dry Fruits Mix',    'kg',      700.00, 0.250,  0.500),
  ('Lime',              'kg',       50.00, 0.500,  1.000),
  ('Soda Water',        'litre',    20.00, 1.000,  2.000),
  ('Tea Leaves',        'kg',      400.00, 0.250,  0.500),
  ('Green Cardamom',    'kg',     1200.00, 0.100,  0.200)
ON CONFLICT (name) DO UPDATE SET
  cost_per_unit = EXCLUDED.cost_per_unit,
  unit          = EXCLUDED.unit;

-- ── Step 3: Seed recipes (ingredient quantities per serving) ───────────────
-- Uses item/variant/ingredient names so IDs don't need to be hardcoded.
-- qty_required is in the ingredient's own unit (kg or litre).
-- ON CONFLICT updates qty if recipe is re-run.
WITH recipe_data(item_name, variant_name, ing_name, qty) AS (
  VALUES
  -- ─── Starter: Paneer Tikka ─────────────────────────────────────────────
  ('Paneer Tikka','Half','Paneer',           0.1000::numeric),
  ('Paneer Tikka','Half','Curd',             0.0500::numeric),
  ('Paneer Tikka','Half','Onions',           0.0600::numeric),
  ('Paneer Tikka','Half','Bell Pepper',      0.0500::numeric),
  ('Paneer Tikka','Half','Spice Mix',        0.0150::numeric),
  ('Paneer Tikka','Half','Butter',           0.0150::numeric),
  ('Paneer Tikka','Half','Cooking Oil',      0.0300::numeric),

  ('Paneer Tikka','Full','Paneer',           0.1750::numeric),
  ('Paneer Tikka','Full','Curd',             0.0800::numeric),
  ('Paneer Tikka','Full','Onions',           0.1000::numeric),
  ('Paneer Tikka','Full','Bell Pepper',      0.0800::numeric),
  ('Paneer Tikka','Full','Spice Mix',        0.0250::numeric),
  ('Paneer Tikka','Full','Butter',           0.0250::numeric),
  ('Paneer Tikka','Full','Cooking Oil',      0.0500::numeric),

  -- ─── Starter: Dal Shorba ──────────────────────────────────────────────
  ('Dal Shorba','Small','Urad Dal',          0.0500::numeric),
  ('Dal Shorba','Small','Onions',            0.0300::numeric),
  ('Dal Shorba','Small','Tomatoes',          0.0400::numeric),
  ('Dal Shorba','Small','Ghee',              0.0050::numeric),
  ('Dal Shorba','Small','Spice Mix',         0.0100::numeric),
  ('Dal Shorba','Small','Milk',              0.0300::numeric),

  ('Dal Shorba','Large','Urad Dal',          0.0900::numeric),
  ('Dal Shorba','Large','Onions',            0.0500::numeric),
  ('Dal Shorba','Large','Tomatoes',          0.0700::numeric),
  ('Dal Shorba','Large','Ghee',              0.0080::numeric),
  ('Dal Shorba','Large','Spice Mix',         0.0180::numeric),
  ('Dal Shorba','Large','Milk',              0.0600::numeric),

  -- ─── Starter: Seekh Kebab ─────────────────────────────────────────────
  ('Seekh Kebab','Half','Mutton (fresh)',    0.1000::numeric),
  ('Seekh Kebab','Half','Onions',            0.0600::numeric),
  ('Seekh Kebab','Half','Spice Mix',         0.0150::numeric),
  ('Seekh Kebab','Half','Cooking Oil',       0.0250::numeric),
  ('Seekh Kebab','Half','Ginger',            0.0150::numeric),

  ('Seekh Kebab','Full','Mutton (fresh)',    0.1750::numeric),
  ('Seekh Kebab','Full','Onions',            0.1000::numeric),
  ('Seekh Kebab','Full','Spice Mix',         0.0250::numeric),
  ('Seekh Kebab','Full','Cooking Oil',       0.0400::numeric),
  ('Seekh Kebab','Full','Ginger',            0.0250::numeric),

  -- ─── Starter: Veg Shammi Kebab ────────────────────────────────────────
  ('Veg Shammi Kebab','Half','Chana',        0.1000::numeric),
  ('Veg Shammi Kebab','Half','Onions',       0.0800::numeric),
  ('Veg Shammi Kebab','Half','Tomatoes',     0.0800::numeric),
  ('Veg Shammi Kebab','Half','Spice Mix',    0.0200::numeric),
  ('Veg Shammi Kebab','Half','Cooking Oil',  0.0600::numeric),
  ('Veg Shammi Kebab','Half','Whole Wheat Flour', 0.1000::numeric),
  ('Veg Shammi Kebab','Half','Ginger',       0.0500::numeric),
  ('Veg Shammi Kebab','Half','Curd',         0.0500::numeric),

  ('Veg Shammi Kebab','Full','Chana',        0.1900::numeric),
  ('Veg Shammi Kebab','Full','Onions',       0.1500::numeric),
  ('Veg Shammi Kebab','Full','Tomatoes',     0.1500::numeric),
  ('Veg Shammi Kebab','Full','Spice Mix',    0.0380::numeric),
  ('Veg Shammi Kebab','Full','Cooking Oil',  0.1100::numeric),
  ('Veg Shammi Kebab','Full','Whole Wheat Flour', 0.1900::numeric),
  ('Veg Shammi Kebab','Full','Ginger',       0.0900::numeric),
  ('Veg Shammi Kebab','Full','Curd',         0.0900::numeric),

  -- ─── Starter: Chicken 65 ──────────────────────────────────────────────
  ('Chicken 65','Half','Chicken (fresh)',    0.2300::numeric),
  ('Chicken 65','Half','Spice Mix',          0.0200::numeric),
  ('Chicken 65','Half','Cooking Oil',        0.0600::numeric),
  ('Chicken 65','Half','Curd',               0.0500::numeric),
  ('Chicken 65','Half','Garlic',             0.0300::numeric),
  ('Chicken 65','Half','Ginger',             0.0250::numeric),
  ('Chicken 65','Half','Onions',             0.0600::numeric),

  ('Chicken 65','Full','Chicken (fresh)',    0.4000::numeric),
  ('Chicken 65','Full','Spice Mix',          0.0380::numeric),
  ('Chicken 65','Full','Cooking Oil',        0.1000::numeric),
  ('Chicken 65','Full','Curd',               0.0900::numeric),
  ('Chicken 65','Full','Garlic',             0.0500::numeric),
  ('Chicken 65','Full','Ginger',             0.0450::numeric),
  ('Chicken 65','Full','Onions',             0.1000::numeric),

  -- ─── Main: Butter Chicken ─────────────────────────────────────────────
  ('Butter Chicken','Half','Chicken (fresh)',0.2000::numeric),
  ('Butter Chicken','Half','Tomatoes',       0.1000::numeric),
  ('Butter Chicken','Half','Fresh Cream',    0.0400::numeric),
  ('Butter Chicken','Half','Butter',         0.0200::numeric),
  ('Butter Chicken','Half','Spice Mix',      0.0150::numeric),
  ('Butter Chicken','Half','Onions',         0.0600::numeric),

  ('Butter Chicken','Full','Chicken (fresh)',0.3400::numeric),
  ('Butter Chicken','Full','Tomatoes',       0.1700::numeric),
  ('Butter Chicken','Full','Fresh Cream',    0.0700::numeric),
  ('Butter Chicken','Full','Butter',         0.0350::numeric),
  ('Butter Chicken','Full','Spice Mix',      0.0260::numeric),
  ('Butter Chicken','Full','Onions',         0.1000::numeric),

  -- ─── Main: Dal Makhani ────────────────────────────────────────────────
  ('Dal Makhani','Half','Urad Dal',          0.1000::numeric),
  ('Dal Makhani','Half','Tomatoes',          0.0800::numeric),
  ('Dal Makhani','Half','Butter',            0.0100::numeric),
  ('Dal Makhani','Half','Fresh Cream',       0.0300::numeric),
  ('Dal Makhani','Half','Spice Mix',         0.0200::numeric),
  ('Dal Makhani','Half','Onions',            0.0600::numeric),
  ('Dal Makhani','Half','Ghee',              0.0050::numeric),

  ('Dal Makhani','Full','Urad Dal',          0.1800::numeric),
  ('Dal Makhani','Full','Tomatoes',          0.1400::numeric),
  ('Dal Makhani','Full','Butter',            0.0180::numeric),
  ('Dal Makhani','Full','Fresh Cream',       0.0550::numeric),
  ('Dal Makhani','Full','Spice Mix',         0.0340::numeric),
  ('Dal Makhani','Full','Onions',            0.1000::numeric),
  ('Dal Makhani','Full','Ghee',              0.0090::numeric),

  -- ─── Main: Shahi Paneer ───────────────────────────────────────────────
  ('Shahi Paneer','Half','Paneer',           0.1000::numeric),
  ('Shahi Paneer','Half','Cashews',          0.0180::numeric),
  ('Shahi Paneer','Half','Fresh Cream',      0.0250::numeric),
  ('Shahi Paneer','Half','Tomatoes',         0.0600::numeric),
  ('Shahi Paneer','Half','Onions',           0.0600::numeric),
  ('Shahi Paneer','Half','Spice Mix',        0.0120::numeric),

  ('Shahi Paneer','Full','Paneer',           0.1750::numeric),
  ('Shahi Paneer','Full','Cashews',          0.0300::numeric),
  ('Shahi Paneer','Full','Fresh Cream',      0.0400::numeric),
  ('Shahi Paneer','Full','Tomatoes',         0.1000::numeric),
  ('Shahi Paneer','Full','Onions',           0.1000::numeric),
  ('Shahi Paneer','Full','Spice Mix',        0.0200::numeric),

  -- ─── Main: Palak Paneer ───────────────────────────────────────────────
  ('Palak Paneer','Half','Paneer',           0.0950::numeric),
  ('Palak Paneer','Half','Spinach',          0.1600::numeric),
  ('Palak Paneer','Half','Fresh Cream',      0.0200::numeric),
  ('Palak Paneer','Half','Onions',           0.0600::numeric),
  ('Palak Paneer','Half','Spice Mix',        0.0150::numeric),
  ('Palak Paneer','Half','Ghee',             0.0100::numeric),

  ('Palak Paneer','Full','Paneer',           0.1700::numeric),
  ('Palak Paneer','Full','Spinach',          0.2700::numeric),
  ('Palak Paneer','Full','Fresh Cream',      0.0350::numeric),
  ('Palak Paneer','Full','Onions',           0.1000::numeric),
  ('Palak Paneer','Full','Spice Mix',        0.0260::numeric),
  ('Palak Paneer','Full','Ghee',             0.0180::numeric),

  -- ─── Main: Mutton Rogan Josh ──────────────────────────────────────────
  ('Mutton Rogan Josh','Half','Mutton (fresh)', 0.1250::numeric),
  ('Mutton Rogan Josh','Half','Tomatoes',       0.0600::numeric),
  ('Mutton Rogan Josh','Half','Onions',         0.0700::numeric),
  ('Mutton Rogan Josh','Half','Spice Mix',      0.0150::numeric),
  ('Mutton Rogan Josh','Half','Ghee',           0.0100::numeric),
  ('Mutton Rogan Josh','Half','Curd',           0.0400::numeric),

  ('Mutton Rogan Josh','Full','Mutton (fresh)', 0.2200::numeric),
  ('Mutton Rogan Josh','Full','Tomatoes',       0.1000::numeric),
  ('Mutton Rogan Josh','Full','Onions',         0.1200::numeric),
  ('Mutton Rogan Josh','Full','Spice Mix',      0.0250::numeric),
  ('Mutton Rogan Josh','Full','Ghee',           0.0150::numeric),
  ('Mutton Rogan Josh','Full','Curd',           0.0600::numeric),

  -- ─── Main: Chicken Kadai ──────────────────────────────────────────────
  ('Chicken Kadai','Half','Chicken (fresh)',  0.1900::numeric),
  ('Chicken Kadai','Half','Bell Pepper',      0.0800::numeric),
  ('Chicken Kadai','Half','Tomatoes',         0.0800::numeric),
  ('Chicken Kadai','Half','Onions',           0.0800::numeric),
  ('Chicken Kadai','Half','Spice Mix',        0.0150::numeric),
  ('Chicken Kadai','Half','Cooking Oil',      0.0600::numeric),

  ('Chicken Kadai','Full','Chicken (fresh)',  0.3700::numeric),
  ('Chicken Kadai','Full','Bell Pepper',      0.1400::numeric),
  ('Chicken Kadai','Full','Tomatoes',         0.1400::numeric),
  ('Chicken Kadai','Full','Onions',           0.1400::numeric),
  ('Chicken Kadai','Full','Spice Mix',        0.0270::numeric),
  ('Chicken Kadai','Full','Cooking Oil',      0.1000::numeric),

  -- ─── Main: Rajma Masala ───────────────────────────────────────────────
  ('Rajma Masala','Half','Rajma',            0.1200::numeric),
  ('Rajma Masala','Half','Tomatoes',         0.0900::numeric),
  ('Rajma Masala','Half','Onions',           0.0800::numeric),
  ('Rajma Masala','Half','Spice Mix',        0.0150::numeric),
  ('Rajma Masala','Half','Cooking Oil',      0.0400::numeric),
  ('Rajma Masala','Half','Ginger',           0.0200::numeric),

  ('Rajma Masala','Full','Rajma',            0.2100::numeric),
  ('Rajma Masala','Full','Tomatoes',         0.1500::numeric),
  ('Rajma Masala','Full','Onions',           0.1400::numeric),
  ('Rajma Masala','Full','Spice Mix',        0.0260::numeric),
  ('Rajma Masala','Full','Cooking Oil',      0.0600::numeric),
  ('Rajma Masala','Full','Ginger',           0.0300::numeric),

  -- ─── Main: Chana Masala ───────────────────────────────────────────────
  ('Chana Masala','Half','Chana',            0.1200::numeric),
  ('Chana Masala','Half','Tomatoes',         0.0900::numeric),
  ('Chana Masala','Half','Onions',           0.0800::numeric),
  ('Chana Masala','Half','Spice Mix',        0.0150::numeric),
  ('Chana Masala','Half','Cooking Oil',      0.0300::numeric),
  ('Chana Masala','Half','Ginger',           0.0150::numeric),

  ('Chana Masala','Full','Chana',            0.2200::numeric),
  ('Chana Masala','Full','Tomatoes',         0.1600::numeric),
  ('Chana Masala','Full','Onions',           0.1400::numeric),
  ('Chana Masala','Full','Spice Mix',        0.0260::numeric),
  ('Chana Masala','Full','Cooking Oil',      0.0550::numeric),
  ('Chana Masala','Full','Ginger',           0.0250::numeric),

  -- ─── Bread ────────────────────────────────────────────────────────────
  ('Butter Naan','Single','Whole Wheat Flour', 0.0800::numeric),
  ('Butter Naan','Single','Butter',            0.0080::numeric),
  ('Butter Naan','Single','Curd',              0.0200::numeric),

  ('Tandoori Roti','Single','Whole Wheat Flour', 0.1000::numeric),
  ('Tandoori Roti','Single','Ghee',              0.0030::numeric),

  ('Garlic Naan','Single','Whole Wheat Flour', 0.0800::numeric),
  ('Garlic Naan','Single','Butter',            0.0100::numeric),
  ('Garlic Naan','Single','Garlic',            0.0150::numeric),
  ('Garlic Naan','Single','Curd',              0.0200::numeric),

  ('Paratha','Single','Whole Wheat Flour',     0.1000::numeric),
  ('Paratha','Single','Butter',                0.0060::numeric),
  ('Paratha','Single','Ghee',                  0.0010::numeric),

  -- ─── Rice / Biryani ───────────────────────────────────────────────────
  ('Chicken Biryani','Half','Basmati Rice',    0.2000::numeric),
  ('Chicken Biryani','Half','Chicken (fresh)', 0.2000::numeric),
  ('Chicken Biryani','Half','Onions',          0.0800::numeric),
  ('Chicken Biryani','Half','Tomatoes',        0.0600::numeric),
  ('Chicken Biryani','Half','Spice Mix',       0.0180::numeric),
  ('Chicken Biryani','Half','Ghee',            0.0100::numeric),
  ('Chicken Biryani','Half','Curd',            0.0300::numeric),

  ('Chicken Biryani','Full','Basmati Rice',    0.3500::numeric),
  ('Chicken Biryani','Full','Chicken (fresh)', 0.3400::numeric),
  ('Chicken Biryani','Full','Onions',          0.1400::numeric),
  ('Chicken Biryani','Full','Tomatoes',        0.1000::numeric),
  ('Chicken Biryani','Full','Spice Mix',       0.0300::numeric),
  ('Chicken Biryani','Full','Ghee',            0.0150::numeric),
  ('Chicken Biryani','Full','Curd',            0.0500::numeric),

  ('Veg Biryani','Half','Basmati Rice',        0.2000::numeric),
  ('Veg Biryani','Half','Onions',              0.0800::numeric),
  ('Veg Biryani','Half','Bell Pepper',         0.0600::numeric),
  ('Veg Biryani','Half','Carrots',             0.0600::numeric),
  ('Veg Biryani','Half','Tomatoes',            0.0600::numeric),
  ('Veg Biryani','Half','Spice Mix',           0.0150::numeric),
  ('Veg Biryani','Half','Ghee',                0.0070::numeric),

  ('Veg Biryani','Full','Basmati Rice',        0.3500::numeric),
  ('Veg Biryani','Full','Onions',              0.1400::numeric),
  ('Veg Biryani','Full','Bell Pepper',         0.1000::numeric),
  ('Veg Biryani','Full','Carrots',             0.1000::numeric),
  ('Veg Biryani','Full','Tomatoes',            0.1000::numeric),
  ('Veg Biryani','Full','Spice Mix',           0.0250::numeric),
  ('Veg Biryani','Full','Ghee',                0.0120::numeric),

  ('Mutton Biryani','Half','Basmati Rice',     0.2000::numeric),
  ('Mutton Biryani','Half','Mutton (fresh)',   0.1050::numeric),
  ('Mutton Biryani','Half','Onions',           0.1000::numeric),
  ('Mutton Biryani','Half','Tomatoes',         0.0800::numeric),
  ('Mutton Biryani','Half','Spice Mix',        0.0220::numeric),
  ('Mutton Biryani','Half','Ghee',             0.0100::numeric),
  ('Mutton Biryani','Half','Curd',             0.0300::numeric),

  ('Mutton Biryani','Full','Basmati Rice',     0.3500::numeric),
  ('Mutton Biryani','Full','Mutton (fresh)',   0.1800::numeric),
  ('Mutton Biryani','Full','Onions',           0.1500::numeric),
  ('Mutton Biryani','Full','Tomatoes',         0.1300::numeric),
  ('Mutton Biryani','Full','Spice Mix',        0.0380::numeric),
  ('Mutton Biryani','Full','Ghee',             0.0150::numeric),
  ('Mutton Biryani','Full','Curd',             0.0500::numeric),

  ('Jeera Rice','Single','Basmati Rice',       0.1750::numeric),
  ('Jeera Rice','Single','Ghee',               0.0090::numeric),
  ('Jeera Rice','Single','Spice Mix',          0.0030::numeric),

  -- ─── Drinks ───────────────────────────────────────────────────────────
  ('Sweet Lassi','Small','Curd',               0.2000::numeric),
  ('Sweet Lassi','Small','Sugar',              0.0300::numeric),
  ('Sweet Lassi','Small','Green Cardamom',     0.0020::numeric),
  ('Sweet Lassi','Small','Milk',               0.0300::numeric),

  ('Sweet Lassi','Large','Curd',               0.3300::numeric),
  ('Sweet Lassi','Large','Sugar',              0.0500::numeric),
  ('Sweet Lassi','Large','Green Cardamom',     0.0040::numeric),
  ('Sweet Lassi','Large','Milk',               0.0500::numeric),

  ('Masala Chai','Single','Milk',              0.0500::numeric),
  ('Masala Chai','Single','Tea Leaves',        0.0030::numeric),
  ('Masala Chai','Single','Green Cardamom',    0.0010::numeric),
  ('Masala Chai','Single','Sugar',             0.0080::numeric),

  ('Fresh Lime Soda','Single','Lime',          0.0800::numeric),
  ('Fresh Lime Soda','Single','Sugar',         0.0300::numeric),
  ('Fresh Lime Soda','Single','Soda Water',    0.3000::numeric),

  ('Mango Lassi','Small','Curd',               0.1500::numeric),
  ('Mango Lassi','Small','Mango Pulp',         0.1200::numeric),
  ('Mango Lassi','Small','Sugar',              0.0200::numeric),
  ('Mango Lassi','Small','Milk',               0.0500::numeric),
  ('Mango Lassi','Small','Green Cardamom',     0.0010::numeric),

  ('Mango Lassi','Large','Curd',               0.2200::numeric),
  ('Mango Lassi','Large','Mango Pulp',         0.1800::numeric),
  ('Mango Lassi','Large','Sugar',              0.0250::numeric),
  ('Mango Lassi','Large','Milk',               0.0600::numeric),
  ('Mango Lassi','Large','Green Cardamom',     0.0020::numeric),

  -- ─── Desserts ─────────────────────────────────────────────────────────
  ('Gulab Jamun','2 Pieces','Khoya',           0.0300::numeric),
  ('Gulab Jamun','2 Pieces','Sugar',           0.0400::numeric),
  ('Gulab Jamun','2 Pieces','Rose Water',      0.0100::numeric),
  ('Gulab Jamun','2 Pieces','Whole Wheat Flour',0.0100::numeric),

  ('Gulab Jamun','4 Pieces','Khoya',           0.0600::numeric),
  ('Gulab Jamun','4 Pieces','Sugar',           0.0750::numeric),
  ('Gulab Jamun','4 Pieces','Rose Water',      0.0200::numeric),
  ('Gulab Jamun','4 Pieces','Whole Wheat Flour',0.0180::numeric),

  ('Rasgulla','2 Pieces','Paneer',             0.0300::numeric),
  ('Rasgulla','2 Pieces','Sugar',              0.0400::numeric),
  ('Rasgulla','2 Pieces','Rose Water',         0.0100::numeric),

  ('Rasgulla','4 Pieces','Paneer',             0.0550::numeric),
  ('Rasgulla','4 Pieces','Sugar',              0.0750::numeric),
  ('Rasgulla','4 Pieces','Rose Water',         0.0200::numeric),

  ('Kheer','Small','Milk',                     0.1500::numeric),
  ('Kheer','Small','Basmati Rice',             0.0200::numeric),
  ('Kheer','Small','Sugar',                    0.0400::numeric),
  ('Kheer','Small','Dry Fruits Mix',           0.0070::numeric),
  ('Kheer','Small','Green Cardamom',           0.0010::numeric),

  ('Kheer','Large','Milk',                     0.2700::numeric),
  ('Kheer','Large','Basmati Rice',             0.0350::numeric),
  ('Kheer','Large','Sugar',                    0.0700::numeric),
  ('Kheer','Large','Dry Fruits Mix',           0.0120::numeric),
  ('Kheer','Large','Green Cardamom',           0.0020::numeric),

  ('Gajar Halwa','Small','Carrots',            0.2000::numeric),
  ('Gajar Halwa','Small','Ghee',               0.0100::numeric),
  ('Gajar Halwa','Small','Khoya',              0.0180::numeric),
  ('Gajar Halwa','Small','Sugar',              0.0800::numeric),
  ('Gajar Halwa','Small','Milk',               0.0150::numeric),

  ('Gajar Halwa','Large','Carrots',            0.3600::numeric),
  ('Gajar Halwa','Large','Ghee',               0.0180::numeric),
  ('Gajar Halwa','Large','Khoya',              0.0300::numeric),
  ('Gajar Halwa','Large','Sugar',              0.1400::numeric),
  ('Gajar Halwa','Large','Milk',               0.0250::numeric),

  ('Raita','Single','Curd',                    0.1200::numeric),
  ('Raita','Single','Cucumber',                0.0500::numeric),
  ('Raita','Single','Onions',                  0.0250::numeric),
  ('Raita','Single','Spice Mix',               0.0020::numeric)
)
INSERT INTO recipes (item_id, variant_id, ing_id, qty_required)
SELECT
  mi.item_id,
  mv.variant_id,
  i.ing_id,
  rd.qty
FROM recipe_data rd
JOIN menu_items    mi ON mi.name            = rd.item_name
JOIN menu_variants mv ON mv.item_id         = mi.item_id
                      AND mv.variant_name   = rd.variant_name
JOIN ingredients   i  ON i.name             = rd.ing_name
ON CONFLICT (variant_id, ing_id) DO UPDATE
  SET qty_required = EXCLUDED.qty_required;

-- ── Step 4: Food cost breakdown view ──────────────────────────────────────
CREATE OR REPLACE VIEW variant_food_cost_view AS
SELECT
  mv.variant_id,
  mi.item_id,
  mi.name                                            AS item_name,
  mv.variant_name,
  mv.selling_price,
  mv.food_cost                                       AS stored_food_cost,
  ROUND(COALESCE(SUM(r.qty_required * i.cost_per_unit), 0), 2)
                                                     AS computed_food_cost,
  ROUND(
    (mv.selling_price - COALESCE(SUM(r.qty_required * i.cost_per_unit), mv.food_cost))
    / NULLIF(mv.selling_price, 0) * 100, 2
  )                                                  AS gross_margin_pct,
  ROUND(
    (mv.selling_price - mv.food_cost)
    / NULLIF(mv.selling_price, 0) * 100, 2
  )                                                  AS stored_margin_pct,
  COALESCE(
    json_agg(
      json_build_object(
        'ingredient', i.name,
        'qty',        r.qty_required,
        'unit',       i.unit,
        'unit_cost',  i.cost_per_unit,
        'line_cost',  ROUND(r.qty_required * i.cost_per_unit, 2)
      ) ORDER BY i.name
    ) FILTER (WHERE i.ing_id IS NOT NULL),
    '[]'::json
  )                                                  AS recipe_breakdown
FROM menu_variants mv
JOIN menu_items    mi USING (item_id)
LEFT JOIN recipes   r  USING (variant_id)
LEFT JOIN ingredients i USING (ing_id)
GROUP BY mv.variant_id, mi.item_id, mi.name,
         mv.variant_name, mv.selling_price, mv.food_cost;

-- ── Step 5: Trigger — keep food_cost in sync when recipes change ───────────
CREATE OR REPLACE FUNCTION fn_sync_food_cost_on_recipe()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  v_variant_id INT;
  v_computed   NUMERIC(10,2);
BEGIN
  v_variant_id := COALESCE(NEW.variant_id, OLD.variant_id);

  SELECT ROUND(COALESCE(SUM(r.qty_required * i.cost_per_unit), NULL), 2)
    INTO v_computed
  FROM recipes r
  JOIN ingredients i USING (ing_id)
  WHERE r.variant_id = v_variant_id;

  IF v_computed IS NOT NULL THEN
    UPDATE menu_variants
       SET food_cost = v_computed
     WHERE variant_id = v_variant_id;
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_recipe_food_cost ON recipes;
CREATE TRIGGER trg_recipe_food_cost
  AFTER INSERT OR UPDATE OR DELETE ON recipes
  FOR EACH ROW EXECUTE FUNCTION fn_sync_food_cost_on_recipe();

-- ── Step 6: Trigger — recompute all variants when ingredient cost changes ──
CREATE OR REPLACE FUNCTION fn_sync_food_cost_on_ingredient()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  UPDATE menu_variants mv
     SET food_cost = subq.total_cost
  FROM (
    SELECT r.variant_id,
           ROUND(SUM(r.qty_required * i.cost_per_unit), 2) AS total_cost
    FROM   recipes r
    JOIN   ingredients i USING (ing_id)
    WHERE  r.variant_id IN (
             SELECT DISTINCT variant_id FROM recipes WHERE ing_id = NEW.ing_id
           )
    GROUP  BY r.variant_id
  ) subq
  WHERE mv.variant_id = subq.variant_id;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ingredient_cost_sync ON ingredients;
CREATE TRIGGER trg_ingredient_cost_sync
  AFTER UPDATE OF cost_per_unit ON ingredients
  FOR EACH ROW
  WHEN (OLD.cost_per_unit IS DISTINCT FROM NEW.cost_per_unit)
  EXECUTE FUNCTION fn_sync_food_cost_on_ingredient();

-- ── Step 7: Initial back-fill of menu_variants.food_cost ──────────────────
UPDATE menu_variants mv
   SET food_cost = subq.total_cost
  FROM (
    SELECT r.variant_id,
           ROUND(SUM(r.qty_required * i.cost_per_unit), 2) AS total_cost
    FROM   recipes r
    JOIN   ingredients i USING (ing_id)
    GROUP  BY r.variant_id
  ) subq
WHERE mv.variant_id = subq.variant_id;
