import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='postgres', user='postgres', password='postgres')
cur = conn.cursor()

offers = [
    (1, 'Offer 20pct 150min', 'pct', 20, 150, ['dine_in','phone'], '2024-01-01', '2024-12-31'),
    (2, 'Offer 15pct 300min', 'pct', 15, 300, ['dine_in','takeaway'], '2024-01-01', '2024-12-31'),
    (3, 'Flat 50 400min', 'flat', 50, 400, ['dine_in','takeaway','phone'], '2024-01-01', '2024-12-31'),
    (4, 'Offer 10pct 0min', 'pct', 10, 0, ['dine_in','takeaway','phone'], '2024-01-01', '2024-12-31'),
    (5, 'Festive 25pct', 'pct', 25, 500, ['dine_in','takeaway','phone'], '2024-10-28', '2024-11-05'),
    (6, 'Flash Flat100', 'flat', 100, 600, ['dine_in','phone'], '2024-03-24', '2024-03-26'),
    (7, 'Zomato 30pct', 'pct', 30, 200, ['zomato'], '2024-01-01', '2024-12-31'),
    (8, 'Swiggy 20pct', 'pct', 20, 250, ['swiggy'], '2024-01-01', '2024-12-31'),
    (9, 'DineIn Flat30', 'flat', 30, 200, ['dine_in'], '2024-01-01', '2024-12-31'),
    (10, 'Offer 15pct 0min', 'pct', 15, 0, ['dine_in','takeaway','phone'], '2024-01-01', '2024-12-31'),
]

for o in offers:
    cur.execute(
        """INSERT INTO offers (offer_id, name, type, discount_value, min_order_val, applicable_channels, valid_from, valid_to)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (offer_id) DO NOTHING""",
        (o[0], o[1], o[2], o[3], o[4], o[5], o[6], o[7])
    )

# Reset sequence so future auto-inserts don't conflict
cur.execute("SELECT setval('offers_offer_id_seq', 10)")

conn.commit()
cur.execute('SELECT COUNT(*) FROM offers')
print(f"Offers in DB: {cur.fetchone()[0]}")
conn.close()
print("Done!")
