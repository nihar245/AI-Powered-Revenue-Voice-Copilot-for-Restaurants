import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='postgres', user='postgres', password='postgres')
cur = conn.cursor()

# Truncate all generated data tables in dependency order, keeping seed tables
tables = [
    'offer_redemptions',
    'feedback',
    'kot_items',
    'kot',
    'order_payments',
    'order_addons',
    'order_items',
    'orders',
    'customers',
    'inventory_log',
]

for t in tables:
    cur.execute(f'TRUNCATE TABLE {t} RESTART IDENTITY CASCADE')
    print(f'Truncated {t}')

conn.commit()
conn.close()
print('Clean slate ready.')
