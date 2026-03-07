INSERT INTO restaurants (name, address, city, cuisine_type, gstin, fssai_no, opening_time, closing_time, seating_capacity)
VALUES ('Spice Garden', '42 MG Road, Koregaon Park', 'Pune', 'North Indian', '27ABCDE1234F1Z5', '10016011000', '08:00', '23:00', 80);

SELECT 'restaurants done', COUNT(*) FROM restaurants;


INSERT INTO menu_categories (name, display_order, is_active, meal_time) VALUES
('Starter', 1, TRUE, 'all'),
('Main',    2, TRUE, 'all'),
('Bread',   3, TRUE, 'all'),
('Rice',    4, TRUE, 'all'),
('Drink',   5, TRUE, 'all'),
('Dessert', 6, TRUE, 'all');

SELECT 'categories done', COUNT(*) FROM menu_categories;


INSERT INTO menu_items (category_id, name, description, is_veg, is_jain, is_available, display_order, tags) VALUES
(1, 'Paneer Tikka',      'Cottage cheese marinated in yogurt and spices, grilled in tandoor', TRUE,  FALSE, TRUE, 1, '{bestseller,spicy}'),
(1, 'Dal Shorba',        'Lentil soup tempered with cumin and ghee',                          TRUE,  TRUE,  TRUE, 2, '{}'),
(1, 'Seekh Kebab',       'Minced lamb mixed with herbs and spices, shaped on skewers',        FALSE, FALSE, TRUE, 3, '{spicy,chef_special}'),
(1, 'Veg Shammi Kebab',  'Lentil and vegetable patties seasoned with aromatic spices',        TRUE,  FALSE, TRUE, 4, '{}'),
(1, 'Chicken 65',        'Deep fried spicy chicken marinated in red chili and curry leaves',  FALSE, FALSE, TRUE, 5, '{spicy,bestseller}'),
(2, 'Butter Chicken',    'Tender chicken in a rich tomato cream sauce, mildly spiced',        FALSE, FALSE, TRUE, 1, '{bestseller}'),
(2, 'Dal Makhani',       'Black lentils slow cooked overnight with butter and cream',         TRUE,  FALSE, TRUE, 2, '{bestseller,chef_special}'),
(2, 'Shahi Paneer',      'Cottage cheese in a rich cashew and cream gravy',                   TRUE,  FALSE, TRUE, 3, '{}'),
(2, 'Palak Paneer',      'Cottage cheese in a smooth spinach gravy',                          TRUE,  TRUE,  TRUE, 4, '{}'),
(2, 'Mutton Rogan Josh', 'Slow cooked mutton in aromatic Kashmiri spices',                    FALSE, FALSE, TRUE, 5, '{chef_special,spicy}'),
(2, 'Chicken Kadai',     'Chicken cooked in a wok with bell peppers and kadai masala',        FALSE, FALSE, TRUE, 6, '{spicy}'),
(2, 'Rajma Masala',      'Kidney beans in thick spiced tomato gravy',                         TRUE,  FALSE, TRUE, 7, '{}'),
(2, 'Chana Masala',      'Chickpeas cooked in tangy spiced onion tomato gravy',               TRUE,  TRUE,  TRUE, 8, '{}'),
(3, 'Butter Naan',       'Soft leavened flatbread brushed with butter, baked in tandoor',     TRUE,  FALSE, TRUE, 1, '{bestseller}'),
(3, 'Tandoori Roti',     'Whole wheat bread baked in tandoor',                                TRUE,  TRUE,  TRUE, 2, '{}'),
(3, 'Garlic Naan',       'Naan topped with garlic and coriander',                             TRUE,  FALSE, TRUE, 3, '{bestseller}'),
(3, 'Paratha',           'Layered whole wheat flatbread pan fried with butter',               TRUE,  FALSE, TRUE, 4, '{}'),
(4, 'Chicken Biryani',   'Fragrant basmati rice slow cooked with spiced chicken, dum style',  FALSE, FALSE, TRUE, 1, '{bestseller}'),
(4, 'Veg Biryani',       'Basmati rice cooked with seasonal vegetables and whole spices',     TRUE,  FALSE, TRUE, 2, '{}'),
(4, 'Mutton Biryani',    'Aromatic long grain rice with tender mutton and whole spices',       FALSE, FALSE, TRUE, 3, '{chef_special}'),
(4, 'Jeera Rice',        'Steamed basmati rice tempered with cumin seeds and ghee',           TRUE,  TRUE,  TRUE, 4, '{}'),
(5, 'Sweet Lassi',       'Chilled blended yogurt with sugar and cardamom',                    TRUE,  FALSE, TRUE, 1, '{bestseller}'),
(5, 'Masala Chai',       'Spiced Indian tea brewed with ginger cardamom and milk',            TRUE,  FALSE, TRUE, 2, '{}'),
(5, 'Fresh Lime Soda',   'Fresh lime juice with soda water served sweet or salted',           TRUE,  TRUE,  TRUE, 3, '{}'),
(5, 'Mango Lassi',       'Thick blended yogurt with Alphonso mango pulp',                     TRUE,  FALSE, TRUE, 4, '{bestseller,new}'),
(6, 'Gulab Jamun',       'Soft milk dumplings soaked in rose flavoured sugar syrup',          TRUE,  FALSE, TRUE, 1, '{bestseller}'),
(6, 'Rasgulla',          'Spongy cottage cheese balls in light sugar syrup',                  TRUE,  FALSE, TRUE, 2, '{}'),
(6, 'Kheer',             'Creamy rice pudding slow cooked with milk sugar and cardamom',      TRUE,  TRUE,  TRUE, 3, '{}'),
(6, 'Gajar Halwa',       'Slow cooked carrot pudding with ghee khoya and dry fruits',         TRUE,  FALSE, TRUE, 4, '{chef_special}'),
(6, 'Raita',             'Chilled yogurt with cucumber onion and mild spices',                TRUE,  TRUE,  TRUE, 5, '{}');

SELECT 'menu_items done', COUNT(*) FROM menu_items;



INSERT INTO menu_variants (item_id, variant_name, selling_price, food_cost, gst_pct) VALUES
(1,  'Half',      220, 55,  5),
(1,  'Full',      380, 95,  5),
(2,  'Small',     80,  18,  5),
(2,  'Large',     140, 32,  5),
(3,  'Half',      260, 75,  5),
(3,  'Full',      450, 130, 5),
(4,  'Half',      180, 42,  5),
(4,  'Full',      320, 78,  5),
(5,  'Half',      240, 70,  5),
(5,  'Full',      420, 125, 5),
(6,  'Half',      220, 65,  5),
(6,  'Full',      380, 110, 5),
(7,  'Half',      160, 38,  5),
(7,  'Full',      280, 68,  5),
(8,  'Half',      200, 55,  5),
(8,  'Full',      350, 95,  5),
(9,  'Half',      180, 48,  5),
(9,  'Full',      320, 85,  5),
(10, 'Half',      280, 95,  5),
(10, 'Full',      480, 165, 5),
(11, 'Half',      200, 60,  5),
(11, 'Full',      360, 110, 5),
(12, 'Half',      140, 32,  5),
(12, 'Full',      240, 55,  5),
(13, 'Half',      130, 28,  5),
(13, 'Full',      220, 50,  5),
(14, 'Single',    45,  9,   5),
(15, 'Single',    30,  6,   5),
(16, 'Single',    55,  11,  5),
(17, 'Single',    40,  8,   5),
(18, 'Half',      220, 80,  5),
(18, 'Full',      380, 135, 5),
(19, 'Half',      160, 45,  5),
(19, 'Full',      280, 80,  5),
(20, 'Half',      280, 110, 5),
(20, 'Full',      480, 185, 5),
(21, 'Single',    120, 28,  5),
(22, 'Small',     80,  18,  5),
(22, 'Large',     130, 30,  5),
(23, 'Single',    30,  6,   5),
(24, 'Single',    60,  12,  5),
(25, 'Small',     100, 25,  5),
(25, 'Large',     160, 40,  5),
(26, '2 Pieces',  60,  14,  5),
(26, '4 Pieces',  110, 26,  5),
(27, '2 Pieces',  55,  12,  5),
(27, '4 Pieces',  100, 22,  5),
(28, 'Small',     80,  20,  5),
(28, 'Large',     140, 35,  5),
(29, 'Small',     90,  22,  5),
(29, 'Large',     160, 40,  5),
(30, 'Single',    50,  10,  5);

SELECT 'menu_variants done', COUNT(*) FROM menu_variants;




INSERT INTO menu_addons (item_id, addon_name, extra_price, food_cost) VALUES
(6,  'Extra Gravy',        30, 8),
(6,  'Extra Chicken',      60, 25),
(7,  'Extra Dal',          40, 10),
(7,  'Extra Butter',       20, 5),
(1,  'Extra Chutney',      20, 4),
(1,  'Extra Paneer',       50, 20),
(18, 'Extra Raita',        30, 8),
(18, 'Extra Salan',        25, 6),
(20, 'Extra Raita',        30, 8),
(14, 'Extra Butter',       15, 3),
(16, 'Extra Garlic',       10, 2),
(22, 'Extra Sweet',        10, 2),
(25, 'Extra Mango',        20, 6),
(26, 'Extra Syrup',        15, 3),
(3,  'Extra Mint Chutney', 15, 3);

SELECT 'menu_addons done', COUNT(*) FROM menu_addons;


INSERT INTO menu_combos (combo_name, description, selling_price, food_cost, valid_from, valid_to, is_active) VALUES
-- ── Existing combos (updated to 2026) ─────────────────────────────────────────
('Butter Chicken Meal',   'Butter Chicken Full + 2 Butter Naan + Sweet Lassi — crowd favourite',           480, 165, '2026-01-01', '2026-12-31', TRUE),
('Biryani Special',       'Chicken Biryani Full + Raita + Sweet Lassi Small — complete biryani meal',      450, 160, '2026-01-01', '2026-12-31', TRUE),
('Veg Delight',           'Dal Makhani Full + Shahi Paneer Half + 2 Butter Naan + Raita',                  520, 165, '2026-01-01', '2026-12-31', TRUE),
('Kebab Platter',         'Paneer Tikka Half + Seekh Kebab Half — mixed grill starter',                    420, 140, '2026-01-01', '2026-12-31', TRUE),
('Lunch Thali',           'Dal Makhani Half + 2 Tandoori Roti + Jeera Rice + Raita — value lunch',         350, 110, '2026-01-01', '2026-12-31', TRUE),
('Mutton Feast',          'Mutton Rogan Josh Full + Mutton Biryani Half + Raita — for the meat lover',     680, 270, '2026-01-01', '2026-12-31', TRUE),
('Happy Hour Snack',      'Paneer Tikka Half + 2 Masala Chai — perfect tea-time combo',                    220,  67, '2026-01-01', '2026-12-31', TRUE),
('Sweet Ending',          'Gulab Jamun 2pcs + Kheer Small + Masala Chai — dessert finale',                 150,  40, '2026-01-01', '2026-12-31', TRUE),
-- ── New combos ────────────────────────────────────────────────────────────────
('Veg Biryani Combo',     'Veg Biryani Full + Raita + Mango Lassi Small — complete vegetarian biryani',   399, 115, '2026-01-01', '2026-12-31', TRUE),
('Mutton Biryani Combo',  'Mutton Biryani Full + Raita + Sweet Lassi Small — the ultimate biryani thali', 549, 213, '2026-01-01', '2026-12-31', TRUE),
('Royal Veg Dinner',      'Shahi Paneer Full + 2 Garlic Naan + Mango Lassi Small + Gulab Jamun 2pcs',     579, 156, '2026-01-01', '2026-12-31', TRUE),
('Chicken Kadai Combo',   'Chicken Kadai Full + 2 Paratha + Fresh Lime Soda — bold spicy meal',           459, 138, '2026-01-01', '2026-12-31', TRUE),
('Tandoori Night',        'Seekh Kebab Full + Paneer Tikka Half + 2 Garlic Naan + Mango Lassi Small',     799, 232, '2026-01-01', '2026-12-31', TRUE),
('Rajma Chawal',          'Rajma Masala Full + Jeera Rice + Raita — classic North Indian comfort meal',   379,  93, '2026-01-01', '2026-12-31', TRUE),
('Sweet Platter',         'Gulab Jamun 4pcs + Gajar Halwa Small + Masala Chai — dessert lovers delight',  199,  54, '2026-01-01', '2026-12-31', TRUE),
('Palak Paneer Thali',    'Palak Paneer Full + Jeera Rice + 2 Tandoori Roti + Raita — healthy thali',     499, 135, '2026-01-01', '2026-12-31', TRUE),
('Chicken 65 Snack Pack', 'Chicken 65 Half + 2 Garlic Naan + Fresh Lime Soda — spicy starter pack',       379, 104, '2026-01-01', '2026-12-31', TRUE);



INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 1, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Butter Chicken' AND v.variant_name = 'Full';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 1, v.item_id, v.variant_id, 2
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Butter Naan' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 1, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Sweet Lassi' AND v.variant_name = 'Small';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 2, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Chicken Biryani' AND v.variant_name = 'Full';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 2, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Raita' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 2, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Sweet Lassi' AND v.variant_name = 'Small';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 3, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Dal Makhani' AND v.variant_name = 'Full';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 3, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Shahi Paneer' AND v.variant_name = 'Half';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 3, v.item_id, v.variant_id, 2
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Butter Naan' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 3, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Raita' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 4, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Paneer Tikka' AND v.variant_name = 'Half';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 4, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Seekh Kebab' AND v.variant_name = 'Half';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 5, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Dal Makhani' AND v.variant_name = 'Half';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 5, v.item_id, v.variant_id, 2
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Tandoori Roti' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 5, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Jeera Rice' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 5, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Raita' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 6, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Mutton Rogan Josh' AND v.variant_name = 'Full';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 6, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Mutton Biryani' AND v.variant_name = 'Half';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 6, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Raita' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 7, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Paneer Tikka' AND v.variant_name = 'Half';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 7, v.item_id, v.variant_id, 2
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Masala Chai' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 8, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Gulab Jamun' AND v.variant_name = '2 Pieces';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 8, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Kheer' AND v.variant_name = 'Small';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 8, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Masala Chai' AND v.variant_name = 'Single';

-- ── Combo 9: Veg Biryani Combo ────────────────────────────────────────────────
INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 9, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Veg Biryani' AND v.variant_name = 'Full';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 9, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Raita' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 9, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Mango Lassi' AND v.variant_name = 'Small';

-- ── Combo 10: Mutton Biryani Combo ───────────────────────────────────────────
INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 10, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Mutton Biryani' AND v.variant_name = 'Full';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 10, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Raita' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 10, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Sweet Lassi' AND v.variant_name = 'Small';

-- ── Combo 11: Royal Veg Dinner ───────────────────────────────────────────────
INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 11, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Shahi Paneer' AND v.variant_name = 'Full';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 11, v.item_id, v.variant_id, 2
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Garlic Naan' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 11, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Mango Lassi' AND v.variant_name = 'Small';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 11, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Gulab Jamun' AND v.variant_name = '2 Pieces';

-- ── Combo 12: Chicken Kadai Combo ────────────────────────────────────────────
INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 12, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Chicken Kadai' AND v.variant_name = 'Full';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 12, v.item_id, v.variant_id, 2
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Paratha' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 12, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Fresh Lime Soda' AND v.variant_name = 'Single';

-- ── Combo 13: Tandoori Night ─────────────────────────────────────────────────
INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 13, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Seekh Kebab' AND v.variant_name = 'Full';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 13, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Paneer Tikka' AND v.variant_name = 'Half';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 13, v.item_id, v.variant_id, 2
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Garlic Naan' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 13, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Mango Lassi' AND v.variant_name = 'Small';

-- ── Combo 14: Rajma Chawal ───────────────────────────────────────────────────
INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 14, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Rajma Masala' AND v.variant_name = 'Full';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 14, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Jeera Rice' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 14, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Raita' AND v.variant_name = 'Single';

-- ── Combo 15: Sweet Platter ──────────────────────────────────────────────────
INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 15, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Gulab Jamun' AND v.variant_name = '4 Pieces';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 15, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Gajar Halwa' AND v.variant_name = 'Small';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 15, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Masala Chai' AND v.variant_name = 'Single';

-- ── Combo 16: Palak Paneer Thali ─────────────────────────────────────────────
INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 16, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Palak Paneer' AND v.variant_name = 'Full';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 16, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Jeera Rice' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 16, v.item_id, v.variant_id, 2
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Tandoori Roti' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 16, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Raita' AND v.variant_name = 'Single';

-- ── Combo 17: Chicken 65 Snack Pack ─────────────────────────────────────────
INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 17, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Chicken 65' AND v.variant_name = 'Half';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 17, v.item_id, v.variant_id, 2
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Garlic Naan' AND v.variant_name = 'Single';

INSERT INTO combo_items (combo_id, item_id, variant_id, qty)
SELECT 17, v.item_id, v.variant_id, 1
FROM menu_variants v JOIN menu_items i USING(item_id)
WHERE i.name = 'Fresh Lime Soda' AND v.variant_name = 'Single';

SELECT 'combo_items done', COUNT(*) FROM combo_items;




-- ============================================================
-- INGREDIENTS
-- ============================================================
INSERT INTO ingredients (name, unit, current_stock, min_stock, reorder_qty, cost_per_unit, last_restocked_at) VALUES
('Chicken',          'kg',      25.0,  8.0,  20.0, 180, NOW()),
('Mutton',           'kg',      12.0,  5.0,  15.0, 420, NOW()),
('Paneer',           'kg',      8.0,   3.0,  10.0, 280, NOW()),
('Basmati Rice',     'kg',      30.0,  10.0, 25.0, 85,  NOW()),
('Onion',            'kg',      15.0,  5.0,  15.0, 25,  NOW()),
('Tomato',           'kg',      12.0,  4.0,  12.0, 30,  NOW()),
('Ginger Garlic',    'kg',      3.0,   1.0,  5.0,  120, NOW()),
('Cream',            'litre',   4.0,   1.5,  5.0,  95,  NOW()),
('Butter',           'kg',      3.0,   1.0,  5.0,  350, NOW()),
('Black Lentils',    'kg',      10.0,  3.0,  10.0, 90,  NOW()),
('Chickpeas',        'kg',      8.0,   3.0,  8.0,  75,  NOW()),
('Kidney Beans',     'kg',      7.0,   3.0,  8.0,  80,  NOW()),
('Maida',            'kg',      15.0,  5.0,  15.0, 35,  NOW()),
('Whole Wheat',      'kg',      10.0,  4.0,  12.0, 38,  NOW()),
('Yogurt',           'kg',      6.0,   2.0,  8.0,  55,  NOW()),
('Milk',             'litre',   10.0,  3.0,  10.0, 55,  NOW()),
('Sugar',            'kg',      5.0,   2.0,  8.0,  42,  NOW()),
('Oil',              'litre',   8.0,   3.0,  10.0, 110, NOW()),
('Spice Mix',        'kg',      2.0,   0.5,  3.0,  180, NOW()),
('Spinach',          'kg',      4.0,   1.5,  5.0,  40,  NOW()),
('Carrot',           'kg',      5.0,   2.0,  6.0,  35,  NOW()),
('Lemon',            'pieces',  30.0,  10.0, 30.0, 4,   NOW()),
('Mango Pulp',       'litre',   3.0,   1.0,  4.0,  120, NOW()),
('Khoya',            'kg',      2.0,   0.5,  3.0,  320, NOW()),
('Cashews',          'kg',      1.0,   0.3,  2.0,  850, NOW());

-- ============================================================
-- RECIPES (item_id, variant_id, ing_id, qty_required)
-- qty_required = per serving amount
-- ============================================================
INSERT INTO recipes (item_id, variant_id, ing_id, qty_required) VALUES
-- Butter Chicken Half (variant_id=11)
(6, 11, 1,  0.150),  -- 150g chicken
(6, 11, 6,  0.080),  -- 80g tomato
(6, 11, 8,  0.040),  -- 40ml cream
(6, 11, 9,  0.020),  -- 20g butter
(6, 11, 19, 0.015),  -- spice mix
-- Butter Chicken Full (variant_id=12)
(6, 12, 1,  0.270),  -- 270g chicken
(6, 12, 6,  0.140),  -- 140g tomato
(6, 12, 8,  0.075),  -- 75ml cream
(6, 12, 9,  0.035),  -- 35g butter
(6, 12, 19, 0.025),  -- spice mix
-- Dal Makhani Half (variant_id=13)
(7, 13, 10, 0.080),  -- 80g black lentils
(7, 13, 9,  0.025),  -- 25g butter
(7, 13, 8,  0.030),  -- 30ml cream
(7, 13, 19, 0.010),  -- spice mix
-- Dal Makhani Full (variant_id=14)
(7, 14, 10, 0.150),  -- 150g black lentils
(7, 14, 9,  0.045),  -- 45g butter
(7, 14, 8,  0.055),  -- 55ml cream
(7, 14, 19, 0.018),  -- spice mix
-- Paneer Tikka Half (variant_id=1)
(1, 1,  3,  0.120),  -- 120g paneer
(1, 1,  15, 0.040),  -- 40g yogurt
(1, 1,  19, 0.015),  -- spice mix
-- Paneer Tikka Full (variant_id=2)
(1, 2,  3,  0.220),  -- 220g paneer
(1, 2,  15, 0.070),  -- 70g yogurt
(1, 2,  19, 0.025),  -- spice mix
-- Chicken Biryani Half (variant_id=33)
(18, 33, 1,  0.180), -- 180g chicken
(18, 33, 4,  0.150), -- 150g rice
(18, 33, 19, 0.020), -- spice mix
(18, 33, 9,  0.015), -- butter
-- Chicken Biryani Full (variant_id=34)
(18, 34, 1,  0.320), -- 320g chicken
(18, 34, 4,  0.280), -- 280g rice
(18, 34, 19, 0.035), -- spice mix
(18, 34, 9,  0.025), -- butter
-- Mutton Biryani Half (variant_id=37)
(20, 37, 2,  0.200), -- 200g mutton
(20, 37, 4,  0.150), -- 150g rice
(20, 37, 19, 0.022), -- spice mix
-- Mutton Biryani Full (variant_id=38)
(20, 38, 2,  0.360), -- 360g mutton
(20, 38, 4,  0.280), -- 280g rice
(20, 38, 19, 0.038), -- spice mix
-- Butter Naan (variant_id=30)
(14, 30, 13, 0.060), -- 60g maida
(14, 30, 9,  0.010), -- 10g butter
-- Garlic Naan (variant_id=32)
(16, 32, 13, 0.060), -- 60g maida
(16, 32, 9,  0.010), -- butter
-- Sweet Lassi Small (variant_id=39)
(22, 39, 15, 0.180), -- 180ml yogurt
(22, 39, 17, 0.025), -- 25g sugar
-- Mango Lassi Small (variant_id=43)
(25, 43, 15, 0.150), -- 150ml yogurt
(25, 43, 23, 0.060), -- 60ml mango pulp
-- Gulab Jamun 2pcs (variant_id=47)
(26, 47, 24, 0.040), -- 40g khoya
(26, 47, 17, 0.030), -- 30g sugar
-- Shahi Paneer Half (variant_id=15)
(8,  15, 3,  0.100), -- 100g paneer
(8,  15, 25, 0.020), -- 20g cashews
(8,  15, 8,  0.035), -- 35ml cream
-- Shahi Paneer Full (variant_id=16)
(8,  16, 3,  0.190), -- 190g paneer
(8,  16, 25, 0.038), -- 38g cashews
(8,  16, 8,  0.065); -- 65ml cream

-- ============================================================
-- OFFERS
-- ============================================================
INSERT INTO offers (name, type, discount_value, min_order_val, applicable_channels, valid_from, valid_to, usage_limit, is_active) VALUES
('Happy Hour 20% Off',      'pct',   20, 150,  '{dine_in,phone}',               '2026-01-01', '2026-12-31', 999999, TRUE),
('Weekend Special 15%',     'pct',   15, 300,  '{dine_in,takeaway}',            '2026-01-01', '2026-12-31', 999999, TRUE),
('Flat 50 Off',             'flat',  50, 400,  '{dine_in,takeaway,phone}',      '2026-01-01', '2026-12-31', 999999, TRUE),
('New Customer 10%',        'pct',   10,   0,  '{dine_in,takeaway,phone}',      '2026-01-01', '2026-12-31', 999999, TRUE),
('Lunch Special Flat 30',   'flat',  30, 200,  '{dine_in}',                     '2026-01-01', '2026-12-31', 999999, TRUE),
('Birthday Treat 15%',      'pct',   15,   0,  '{dine_in,takeaway,phone}',      '2026-01-01', '2026-12-31', 999999, TRUE),
('Holi Special 25%',        'pct',   25, 500,  '{dine_in,takeaway,phone}',      '2026-03-13', '2026-03-16', 999999, TRUE),
('Loyalty Flat 100 Off',    'flat', 100, 600,  '{dine_in,phone}',               '2026-01-01', '2026-12-31', 999999, TRUE),
('Zomato 30% Off',          'pct',   30, 200,  '{zomato}',                      '2026-01-01', '2026-12-31', 999999, TRUE),
('Swiggy One 20%',          'pct',   20, 250,  '{swiggy}',                      '2026-01-01', '2026-12-31', 999999, TRUE);

SELECT 'offers done', COUNT(*) FROM offers;

-- ============================================================
SELECT 'Static seed data inserted successfully' AS status;
SELECT 'Tables populated: restaurants, menu_categories, menu_items, menu_variants,' AS tables_1;
SELECT 'menu_addons, menu_combos, combo_items, ingredients, recipes, offers' AS tables_2;