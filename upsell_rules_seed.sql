-- ============================================================
-- Upsell Rules Seed Data
-- Spice Garden — North Indian restaurant at Padmavati Bhojanalaya
--
-- Run AFTER schema.sql (which creates the upsell_rules table).
-- Run AFTER final_static_seed.sql (not a dependency, but logical order).
--
-- Rules are sorted by weight DESC when fetched. Higher weight = surfaced first.
-- Trigger items and suggest items must exactly match menu_items.name (case-insensitive).
-- ============================================================

-- Clear existing rules before re-seeding
TRUNCATE TABLE upsell_rules RESTART IDENTITY;

INSERT INTO upsell_rules (trigger_item, suggest_item, reason, weight) VALUES

-- ═══════════════════════════════════════════════════════════════
-- WEIGHT 10 — MUST-HAVE PAIRINGS (biryani always needs raita)
-- ═══════════════════════════════════════════════════════════════
('Chicken Biryani',   'Raita',         'Biryani is always better with cool, fresh raita to balance the spices',  10),
('Mutton Biryani',    'Raita',         'Raita is the perfect companion for Mutton Biryani — a must-have side',   10),
('Veg Biryani',       'Raita',         'Raita balances the aromatic spices of the biryani beautifully',          10),

-- ═══════════════════════════════════════════════════════════════
-- WEIGHT 9 — CLASSIC PAIRINGS (curry + bread, chawal + dal)
-- ═══════════════════════════════════════════════════════════════
('Butter Chicken',    'Garlic Naan',   'Butter chicken gravy is best scooped up with warm garlic naan',           9),
('Butter Chicken',    'Butter Naan',   'Soft butter naan is the classic partner for creamy butter chicken',       9),
('Dal Makhani',       'Garlic Naan',   'Creamy dal makhani pairs beautifully with garlic naan',                   9),
('Mutton Rogan Josh', 'Garlic Naan',   'The rich rogan josh gravy is perfect for scooping with garlic naan',     9),
('Rajma Masala',      'Jeera Rice',    'Rajma chawal is a timeless North Indian classic — a complete meal',       9),
('Seekh Kebab',       'Garlic Naan',   'Seekh kebab with garlic naan is a winning combination',                   9),

-- ═══════════════════════════════════════════════════════════════
-- WEIGHT 8 — STRONG PAIRINGS
-- ═══════════════════════════════════════════════════════════════
('Shahi Paneer',      'Garlic Naan',   'Rich shahi paneer gravy is best enjoyed with soft garlic naan',          8),
('Palak Paneer',      'Tandoori Roti', 'Palak paneer with tandoori roti is a healthy, wholesome combo',          8),
('Chana Masala',      'Paratha',       'Chana masala with a flaky paratha is a North Indian classic',            8),
('Chicken Kadai',     'Garlic Naan',   'Spicy kadai chicken with garlic naan soaks up every drop of the gravy',  8),
('Paneer Tikka',      'Masala Chai',   'Paneer tikka with a warm masala chai is the perfect teatime combo',      8),
('Mutton Rogan Josh', 'Jeera Rice',    'Mutton rogan josh served over fragrant jeera rice is a Kashmiri classic',8),

-- ═══════════════════════════════════════════════════════════════
-- WEIGHT 7 — DRINK UPSELLS (lassi / soda after spicy food)
-- ═══════════════════════════════════════════════════════════════
('Chicken Biryani',   'Sweet Lassi',   'A chilled sweet lassi perfectly complements the spicy biryani',          7),
('Mutton Biryani',    'Sweet Lassi',   'Sweet lassi is the ideal coolant after spicy mutton biryani',            7),
('Veg Biryani',       'Mango Lassi',   'Mango lassi adds a refreshing tropical note to complete your biryani meal',7),
('Paneer Tikka',      'Mango Lassi',   'Cooling mango lassi is a perfect follow-up to spicy paneer tikka',      7),
('Chicken 65',        'Fresh Lime Soda','Spicy chicken 65 pairs brilliantly with a fizzy fresh lime soda',      7),
('Butter Chicken',    'Sweet Lassi',   'A chilled sweet lassi rounds off the butter chicken meal perfectly',     7),
('Dal Makhani',       'Jeera Rice',    'Dal makhani over jeera rice is the ultimate North Indian comfort food',  7),
('Seekh Kebab',       'Fresh Lime Soda','Fizzy lime soda alongside seekh kebab is refreshing and cooling',      7),

-- ═══════════════════════════════════════════════════════════════
-- WEIGHT 6 — CROSS-CATEGORY (mains + dessert, drinks)
-- ═══════════════════════════════════════════════════════════════
('Shahi Paneer',      'Jeera Rice',    'Shahi paneer with fragrant jeera rice is an indulgent combination',      6),
('Chicken Biryani',   'Mango Lassi',   'Mango lassi is a tropical delight alongside chicken biryani',           6),
('Dal Shorba',        'Butter Naan',   'Warm dal shorba with butter naan is a comforting, light starter combo',  6),
('Mutton Biryani',    'Gulab Jamun',   'End your biryani feast perfectly with warm, syrupy gulab jamun',        6),
('Chicken Biryani',   'Gulab Jamun',   'Gulab jamun is the classic dessert finish after a biryani meal',        6),
('Chicken Kadai',     'Sweet Lassi',   'Sweet lassi nicely cools down the bold spice of kadai chicken',         6),

-- ═══════════════════════════════════════════════════════════════
-- WEIGHT 5 — DESSERT & CHAI PAIRINGS
-- ═══════════════════════════════════════════════════════════════
('Gajar Halwa',       'Masala Chai',   'Gajar halwa with masala chai is an irresistible Indian dessert pairing', 5),
('Gulab Jamun',       'Masala Chai',   'Warm gulab jamun alongside masala chai is a perfect Indian dessert duo', 5),
('Kheer',             'Masala Chai',   'Kheer and masala chai is the most comforting way to end a meal',         5),
('Palak Paneer',      'Mango Lassi',   'Cool mango lassi balances the earthy spinach flavour of palak paneer',  5),
('Butter Chicken',    'Rasgulla',      'Finish your butter chicken meal on a sweet note with soft rasgulla',    5),
('Veg Shammi Kebab',  'Masala Chai',   'Veg shammi kebab with masala chai is a lovely teatime combination',     5),
('Paratha',           'Sweet Lassi',   'Paratha is elevated with a refreshing sweet lassi on the side',         5),
('Seekh Kebab',       'Butter Naan',   'Seekh kebab with butter naan is a satisfying mixed-grill starter combo',5),

-- ═══════════════════════════════════════════════════════════════
-- WEIGHT 4 — LIGHT / OCCASIONAL PAIRINGS
-- ═══════════════════════════════════════════════════════════════
('Dal Shorba',        'Garlic Naan',   'A bowl of dal shorba with garlic naan is a light, warming combo',        4),
('Chana Masala',      'Jeera Rice',    'Chana masala with jeera rice is a protein-packed, wholesome meal',       4),
('Rasgulla',          'Masala Chai',   'Soft rasgulla with a hot chai is a classic Indian sweet ending',        4),
('Mutton Biryani',    'Mango Lassi',   'Mango lassi brings a refreshing contrast to rich mutton biryani',       4),
('Chicken 65',        'Mango Lassi',   'Cool down the heat of chicken 65 with a tall mango lassi',              4);

SELECT 'upsell_rules done', COUNT(*) FROM upsell_rules;
