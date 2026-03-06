import psycopg2
import numpy as np
from faker import Faker
from datetime import datetime, timedelta, date
import random

fake = Faker('en_IN')
Faker.seed(42)
np.random.seed(42)
random.seed(42)

# ============================================================
# CONNECTION — change password
# ============================================================
conn = psycopg2.connect(
    host     = 'localhost',
    port     = 5432,
    database = 'postgres',
    user     = 'postgres',
    password = 'postgres'
)
cur = conn.cursor()
cur.execute("SELECT current_database(), current_schema(), inet_server_addr(), inet_server_port()")
print(cur.fetchone())
cur.execute("SELECT to_regclass('public.customers')")
print(cur.fetchone())
print('✅ Connected to PostgreSQL')

# ============================================================
# REFERENCE DATA
# ============================================================
ITEMS = {
    1:('Paneer Tikka','Starter',True),   2:('Dal Shorba','Starter',True),
    3:('Seekh Kebab','Starter',False),   4:('Veg Shammi Kebab','Starter',True),
    5:('Chicken 65','Starter',False),    6:('Butter Chicken','Main',False),
    7:('Dal Makhani','Main',True),       8:('Shahi Paneer','Main',True),
    9:('Palak Paneer','Main',True),      10:('Mutton Rogan Josh','Main',False),
    11:('Chicken Kadai','Main',False),   12:('Rajma Masala','Main',True),
    13:('Chana Masala','Main',True),     14:('Butter Naan','Bread',True),
    15:('Tandoori Roti','Bread',True),   16:('Garlic Naan','Bread',True),
    17:('Paratha','Bread',True),         18:('Chicken Biryani','Rice',False),
    19:('Veg Biryani','Rice',True),      20:('Mutton Biryani','Rice',False),
    21:('Jeera Rice','Rice',True),       22:('Sweet Lassi','Drink',True),
    23:('Masala Chai','Drink',True),     24:('Fresh Lime Soda','Drink',True),
    25:('Mango Lassi','Drink',True),     26:('Gulab Jamun','Dessert',True),
    27:('Rasgulla','Dessert',True),      28:('Kheer','Dessert',True),
    29:('Gajar Halwa','Dessert',True),   30:('Raita','Addon',True),
}

# VARIANTS — keyed by variant_id AS ASSIGNED BY POSTGRESQL SERIAL
# Verify with: SELECT variant_id, item_id, variant_name FROM menu_variants ORDER BY variant_id
# item order: Paneer Tikka=1,Dal Shorba=2,Seekh Kebab=3,Veg Shammi=4,Chicken65=5
#             ButterChicken=6,DalMakhani=7,ShahiPaneer=8,PalakPaneer=9,MuttonRoganJosh=10
#             ChickenKadai=11,RajmaMasala=12,ChanaMasala=13
#             ButterNaan=14,TandooriRoti=15,GarlicNaan=16,Paratha=17
#             ChickenBiryani=18,VegBiryani=19,MuttonBiryani=20,JeeraRice=21
#             SweetLassi=22,MasalaChai=23,FreshLimeSoda=24,MangoLassi=25
#             GulabJamun=26,Rasgulla=27,Kheer=28,GajarHalwa=29,Raita=30
VARIANTS = {
    1: (1, 'Half',     220, 55),   # Paneer Tikka Half
    2: (1, 'Full',     380, 95),   # Paneer Tikka Full
    3: (2, 'Small',    80,  18),   # Dal Shorba Small
    4: (2, 'Large',    140, 32),   # Dal Shorba Large
    5: (3, 'Half',     260, 75),   # Seekh Kebab Half
    6: (3, 'Full',     450, 130),  # Seekh Kebab Full
    7: (4, 'Half',     180, 42),   # Veg Shammi Half
    8: (4, 'Full',     320, 78),   # Veg Shammi Full
    9: (5, 'Half',     240, 70),   # Chicken 65 Half
    10:(5, 'Full',     420, 125),  # Chicken 65 Full
    11:(6, 'Half',     220, 65),   # Butter Chicken Half
    12:(6, 'Full',     380, 110),  # Butter Chicken Full
    13:(7, 'Half',     160, 38),   # Dal Makhani Half
    14:(7, 'Full',     280, 68),   # Dal Makhani Full
    15:(8, 'Half',     200, 55),   # Shahi Paneer Half
    16:(8, 'Full',     350, 95),   # Shahi Paneer Full
    17:(9, 'Half',     180, 48),   # Palak Paneer Half
    18:(9, 'Full',     320, 85),   # Palak Paneer Full
    19:(10,'Half',     280, 95),   # Mutton Rogan Josh Half
    20:(10,'Full',     480, 165),  # Mutton Rogan Josh Full
    21:(11,'Half',     200, 60),   # Chicken Kadai Half
    22:(11,'Full',     360, 110),  # Chicken Kadai Full
    23:(12,'Half',     140, 32),   # Rajma Half
    24:(12,'Full',     240, 55),   # Rajma Full
    25:(13,'Half',     130, 28),   # Chana Half
    26:(13,'Full',     220, 50),   # Chana Full
    27:(14,'Single',   45,  9),    # Butter Naan
    28:(15,'Single',   30,  6),    # Tandoori Roti
    29:(16,'Single',   55,  11),   # Garlic Naan
    30:(17,'Single',   40,  8),    # Paratha
    31:(18,'Half',     220, 80),   # Chicken Biryani Half
    32:(18,'Full',     380, 135),  # Chicken Biryani Full
    33:(19,'Half',     160, 45),   # Veg Biryani Half
    34:(19,'Full',     280, 80),   # Veg Biryani Full
    35:(20,'Half',     280, 110),  # Mutton Biryani Half
    36:(20,'Full',     480, 185),  # Mutton Biryani Full
    37:(21,'Single',   120, 28),   # Jeera Rice
    38:(22,'Small',    80,  18),   # Sweet Lassi Small
    39:(22,'Large',    130, 30),   # Sweet Lassi Large
    40:(23,'Single',   30,  6),    # Masala Chai
    41:(24,'Single',   60,  12),   # Fresh Lime Soda
    42:(25,'Small',    100, 25),   # Mango Lassi Small
    43:(25,'Large',    160, 40),   # Mango Lassi Large
    44:(26,'2 Pieces', 60,  14),   # Gulab Jamun 2pc
    45:(26,'4 Pieces', 110, 26),   # Gulab Jamun 4pc
    46:(27,'2 Pieces', 55,  12),   # Rasgulla 2pc
    47:(27,'4 Pieces', 100, 22),   # Rasgulla 4pc
    48:(28,'Small',    80,  20),   # Kheer Small
    49:(28,'Large',    140, 35),   # Kheer Large
    50:(29,'Small',    90,  22),   # Gajar Halwa Small
    51:(29,'Large',    160, 40),   # Gajar Halwa Large
    52:(30,'Single',   50,  10),   # Raita
}

ITEM_VARIANTS = {}
for vid,(iid,vname,price,cost) in VARIANTS.items():
    ITEM_VARIANTS.setdefault(iid,[]).append(vid)

ADDONS = {
    1:(6,'Extra Gravy',30),       2:(6,'Extra Chicken',60),
    3:(7,'Extra Dal',40),         4:(7,'Extra Butter',20),
    5:(1,'Extra Chutney',20),     6:(1,'Extra Paneer',50),
    7:(18,'Extra Raita',30),      8:(18,'Extra Salan',25),
    9:(20,'Extra Raita',30),      10:(14,'Extra Butter',15),
    11:(16,'Extra Garlic',10),    12:(22,'Extra Sweet',10),
    13:(25,'Extra Mango',20),     14:(26,'Extra Syrup',15),
    15:(3,'Extra Mint Chutney',15),
}
ITEM_ADDONS = {}
for aid,(iid,aname,aprice) in ADDONS.items():
    ITEM_ADDONS.setdefault(iid,[]).append(aid)

ITEM_WEIGHTS = {
    1:8,2:3,3:5,4:3,5:7,6:12,7:11,8:7,9:6,10:5,
    11:8,12:5,13:4,14:15,15:8,16:12,17:5,18:13,
    19:7,20:6,21:5,22:9,23:10,24:6,25:8,26:7,
    27:4,28:4,29:4,30:6
}

OFFERS = {
    1:('pct',20,150,['dine_in','phone'],date(2024,1,1),date(2024,12,31)),
    2:('pct',15,300,['dine_in','takeaway'],date(2024,1,1),date(2024,12,31)),
    3:('flat',50,400,['dine_in','takeaway','phone'],date(2024,1,1),date(2024,12,31)),
    4:('pct',10,0,['dine_in','takeaway','phone'],date(2024,1,1),date(2024,12,31)),
    5:('pct',25,500,['dine_in','takeaway','phone'],date(2024,10,28),date(2024,11,5)),
    6:('flat',100,600,['dine_in','phone'],date(2024,3,24),date(2024,3,26)),
    7:('pct',30,200,['zomato'],date(2024,1,1),date(2024,12,31)),
    8:('pct',20,250,['swiggy'],date(2024,1,1),date(2024,12,31)),
    9:('flat',30,200,['dine_in'],date(2024,1,1),date(2024,12,31)),
    10:('pct',15,0,['dine_in','takeaway','phone'],date(2024,1,1),date(2024,12,31)),
}

FESTIVALS = {
    date(2024,1,14),date(2024,1,26),date(2024,3,25),
    date(2024,4,14),date(2024,8,15),date(2024,10,2),
    date(2024,10,24),date(2024,11,1),date(2024,11,2),
    date(2024,11,3),date(2024,12,25),date(2024,12,31),
}

PREP_TIMES = {
    'Starter':12,'Main':20,'Bread':8,
    'Rice':25,'Drink':4,'Dessert':6,'Addon':3
}

HOURS   = list(range(8,24))
HOUR_W  = [3,5,4,5,14,16,10,5,6,7,8,14,16,12,8,5]
HOUR_P  = np.array(HOUR_W,dtype=float); HOUR_P/=HOUR_P.sum()

CHANNELS  = ['dine_in','takeaway','zomato','swiggy','phone']
CHANNEL_P = [0.45,0.20,0.15,0.12,0.08]

ALL_IIDS  = list(ITEMS.keys())
ALL_IW    = np.array([ITEM_WEIGHTS[i] for i in ALL_IIDS],dtype=float)
ALL_IW   /= ALL_IW.sum()

# RECIPES_MAP: (item_id, variant_id) → [(ing_id, qty_per_serving)]
# variant_ids now match actual PostgreSQL SERIAL assignments
RECIPES_MAP = {
    # Butter Chicken (item=6) — variant 11=Half, 12=Full
    (6, 11): [(1,0.150),(6,0.080),(8,0.040),(9,0.020),(19,0.015)],
    (6, 12): [(1,0.270),(6,0.140),(8,0.075),(9,0.035),(19,0.025)],
    # Dal Makhani (item=7) — variant 13=Half, 14=Full
    (7, 13): [(10,0.080),(9,0.025),(8,0.030),(19,0.010)],
    (7, 14): [(10,0.150),(9,0.045),(8,0.055),(19,0.018)],
    # Paneer Tikka (item=1) — variant 1=Half, 2=Full
    (1, 1):  [(3,0.120),(15,0.040),(19,0.015)],
    (1, 2):  [(3,0.220),(15,0.070),(19,0.025)],
    # Chicken Biryani (item=18) — variant 31=Half, 32=Full
    (18,31): [(1,0.180),(4,0.150),(19,0.020),(9,0.015)],
    (18,32): [(1,0.320),(4,0.280),(19,0.035),(9,0.025)],
    # Mutton Biryani (item=20) — variant 35=Half, 36=Full
    (20,35): [(2,0.200),(4,0.150),(19,0.022)],
    (20,36): [(2,0.360),(4,0.280),(19,0.038)],
    # Butter Naan (item=14) — variant 27=Single
    (14,27): [(13,0.060),(9,0.010)],
    # Garlic Naan (item=16) — variant 29=Single
    (16,29): [(13,0.060),(9,0.010)],
    # Sweet Lassi (item=22) — variant 38=Small, 39=Large
    (22,38): [(15,0.180),(17,0.025)],
    (22,39): [(15,0.300),(17,0.040)],
    # Mango Lassi (item=25) — variant 42=Small, 43=Large
    (25,42): [(15,0.150),(23,0.060)],
    (25,43): [(15,0.250),(23,0.100)],
    # Gulab Jamun (item=26) — variant 44=2pc, 45=4pc
    (26,44): [(24,0.040),(17,0.030)],
    (26,45): [(24,0.080),(17,0.060)],
    # Shahi Paneer (item=8) — variant 15=Half, 16=Full
    (8, 15): [(3,0.100),(25,0.020),(8,0.035)],
    (8, 16): [(3,0.190),(25,0.038),(8,0.065)],
}

# ============================================================
# 1. CUSTOMERS
# ============================================================
print('Inserting customers...')

used_phones = set()

def unique_phone(used):
    while True:
        phone = f'9{random.randint(100000000,999999999)}'
        if phone not in used:
            used.add(phone)
            return phone

payment_methods = ['cash','upi','credit_card','debit_card','wallet']

for i in range(500):
    fv   = fake.date_between(start_date=date(2024,1,1), end_date=date(2024,6,1))
    lv   = fake.date_between(start_date=fv, end_date=date(2024,12,31))
    vis  = random.randint(1,48)
    avg  = round(random.uniform(280,850),2)
    tot  = round(avg*vis,2)
    days = (date(2024,12,31)-lv).days

    if tot>15000 and vis>20:  seg='VIP'
    elif vis>10:               seg='Regular'
    elif days>90:              seg='Lost'
    elif vis<=2:               seg='New'
    else:                      seg='Occasional'

    is_veg    = random.random()<0.45
    veg_items = [v[0] for v in ITEMS.values() if v[2]]
    all_items = [v[0] for v in ITEMS.values()]
    fav       = random.choice(veg_items if is_veg else all_items)

    cur.execute("""
        INSERT INTO customers
        (phone,name,email,dob,anniversary,is_veg,is_jain,allergies,
         loyalty_points,total_visits,total_spent,avg_order_val,
         first_visit,last_visit,favourite_item,favourite_payment,
         churn_risk_score,segment)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        unique_phone(used_phones),
        fake.name(),
        fake.email() if random.random()<0.6 else None,
        fake.date_of_birth(minimum_age=18,maximum_age=65) if random.random()<0.4 else None,
        fake.date_between(start_date=date(2015,1,1),
                          end_date=date(2023,12,31)) if random.random()<0.25 else None,
        is_veg,
        random.random()<0.05,
        '{nuts}' if random.random()<0.05 else '{}',
        int(tot//50), vis, tot, avg, fv, lv, fav,
        random.choice(payment_methods),
        round(min(1.0,days/180),3),
        seg
    ))

conn.commit()
print('✅ Customers done — 500 rows')

# ============================================================
# 2. ORDERS + ALL RELATED TABLES
# ============================================================
print('Inserting orders (5-10 mins)...')

start_date = date(2024,1,1)
cur.execute("SELECT COALESCE(MAX(order_id),0) FROM orders")
order_id = cur.fetchone()[0] + 1
cur.execute("SELECT COALESCE(MAX(line_id),0) FROM order_items")
line_id = cur.fetchone()[0] + 1
cur.execute("SELECT COALESCE(MAX(addon_line_id),0) FROM order_addons")
addon_line = cur.fetchone()[0] + 1
cur.execute("SELECT COALESCE(MAX(payment_id),0) FROM order_payments")
payment_id = cur.fetchone()[0] + 1
cur.execute("SELECT COALESCE(MAX(kot_id),0) FROM kot")
kot_id = cur.fetchone()[0] + 1
cur.execute("SELECT COALESCE(MAX(kot_item_id),0) FROM kot_items")
kot_iid = cur.fetchone()[0] + 1
cur.execute("SELECT COALESCE(MAX(redemption_id),0) FROM offer_redemptions")
red_id = cur.fetchone()[0] + 1
cur.execute("SELECT COALESCE(MAX(feedback_id),0) FROM feedback")
fb_id = cur.fetchone()[0] + 1

daily_consumption = {}

for day_offset in range(365):
    d       = start_date + timedelta(days=day_offset)
    dow     = d.weekday()
    is_wknd = dow >= 5
    is_fest = d in FESTIVALS
    is_pay  = d.day in [1,2,28,29,30,31]
    month   = d.month

    base = 80
    if is_wknd:        base = int(base*1.55)
    if is_fest:        base = int(base*2.10)
    if is_pay:         base = int(base*1.18)
    if month in [6,7]: base = int(base*0.78)
    if month in [12,1]:base = int(base*1.15)
    n_orders = max(20, np.random.poisson(base))

    for _ in range(n_orders):
        hour      = np.random.choice(HOURS, p=HOUR_P)
        placed_at = datetime(d.year,d.month,d.day,hour,
                             random.randint(0,59),random.randint(0,59))
        channel   = str(np.random.choice(CHANNELS, p=CHANNEL_P))
        cust_id   = random.randint(1,500) if random.random()<0.60 else None
        n_items   = np.random.choice([1,2,3,4,5],p=[0.15,0.35,0.30,0.15,0.05])
        chosen    = np.random.choice(ALL_IIDS,
                                     size=min(n_items,len(ALL_IIDS)),
                                     replace=False, p=ALL_IW)

        subtotal   = 0
        oi_rows    = []
        addon_rows = []
        max_prep   = 0

        for item_id in chosen:
            variants = ITEM_VARIANTS.get(int(item_id),[])
            if not variants: continue

            if len(variants)==1:
                vid = variants[0]
            else:
                fp  = 0.55 if hour>=19 else 0.40
                pr  = np.array([1-fp]+[fp/(len(variants)-1)]*(len(variants)-1))
                pr  = pr[:len(variants)]; pr/=pr.sum()
                vid = int(np.random.choice(variants,p=pr))

            _,_,unit_price,food_cost = VARIANTS[vid]
            qty  = int(np.random.choice([1,2],p=[0.88,0.12]))
            disc = int(np.random.choice([0,0,0,5,10],p=[0.65,0.15,0.10,0.06,0.04]))
            unit_price = float(unit_price)
            rev  = float(round(unit_price*qty*(1-disc/100),2))
            gst  = float(round(rev*0.05,2))
            fc   = float(round(food_cost*qty,2))
            subtotal += rev
            cat  = ITEMS[int(item_id)][1]
            max_prep = max(max_prep, PREP_TIMES.get(cat,15))
            instr = random.choice(['less spicy','extra spicy','no onion',
                                   'no garlic','well done',
                                   None,None,None,None,None])

            oi_rows.append((line_id,order_id,int(item_id),vid,qty,
                            unit_price,disc,rev,fc,gst,instr))

            # Track ingredient consumption
            key = (int(item_id), vid)
            if key in RECIPES_MAP:
                for ing_id, qty_req in RECIPES_MAP[key]:
                    dk = (d, ing_id)
                    daily_consumption[dk] = daily_consumption.get(dk,0) + qty_req*qty

            # Collect addon (insert AFTER order_items)
            if int(item_id) in ITEM_ADDONS and random.random()<0.20:
                aid    = random.choice(ITEM_ADDONS[int(item_id)])
                aprice = ADDONS[aid][2]
                addon_rows.append((addon_line, line_id, aid, 1, aprice))
                subtotal  += aprice
                addon_line += 1

            line_id += 1

        if not oi_rows:
            continue

        # Offer
        disc_amt = 0.0
        off_id   = None
        if random.random()<0.12:
            applicable = [
                (oid,ot,ov)
                for oid,(ot,ov,omin,och,ovf,ovt) in OFFERS.items()
                if channel in och and ovf<=d<=ovt and subtotal>=omin
            ]
            if applicable:
                oid,ot,ov = random.choice(applicable)
                disc_amt  = float(round(subtotal*ov/100,2)) if ot=='pct' else float(ov)
                off_id    = oid

            subtotal = float(subtotal)
        tax_amt  = float(round(subtotal*0.05,2))
        total    = float(round(subtotal - disc_amt + tax_amt, 2))
        del_off  = max_prep + random.randint(0,10)
        deliv_at = placed_at + timedelta(minutes=del_off)

        # INSERT ORDER
        cur.execute("""
            INSERT INTO orders
            (order_id,restaurant_id,customer_id,placed_by,channel,status,
             placed_at,delivered_at,subtotal,discount_amt,tax_amt,total,payment_status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (order_id,1,cust_id,
              random.choice(['Amit','Priya','Rahul','Sneha','Vijay']),
              channel,'delivered',placed_at,deliv_at,
              float(round(subtotal,2)),float(disc_amt),float(tax_amt),float(total),'paid'))

        # INSERT ORDER ITEMS
        for row in oi_rows:
            cur.execute("""
                INSERT INTO order_items
                (line_id,order_id,item_id,variant_id,qty,unit_price,
                 discount_pct,revenue,food_cost,gst_amt,special_instructions)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, row)

        # INSERT ADDONS (after order_items)
        for arow in addon_rows:
            cur.execute("""
                INSERT INTO order_addons (addon_line_id,line_id,addon_id,qty,price)
                VALUES (%s,%s,%s,%s,%s)
            """, arow)

        # INSERT PAYMENT
        if channel=='zomato':
            method='upi'
        elif channel=='swiggy':
            method=random.choice(['upi','credit_card'])
        else:
            method=str(np.random.choice(
                ['cash','upi','credit_card','debit_card','wallet'],
                p=[0.22,0.45,0.16,0.12,0.05]
            ))
        ref = f'TXN{random.randint(100000000,999999999)}' if method!='cash' else None
        cur.execute("""
            INSERT INTO order_payments
            (payment_id,order_id,method,amount,transaction_ref,paid_at)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (payment_id,order_id,method,total,ref,placed_at))
        payment_id += 1

        # INSERT KOT
        priority = 'urgent' if (is_fest or len(oi_rows)>=4) else 'normal'
        cur.execute("""
            INSERT INTO kot (kot_id,order_id,status,priority,created_at,completed_at)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (kot_id,order_id,'ready',priority,placed_at,deliv_at))

        for row in oi_rows:
            cur.execute("""
                INSERT INTO kot_items
                (kot_item_id,kot_id,item_id,variant_id,qty,
                 special_instructions,status)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (kot_iid,kot_id,row[2],row[3],row[4],row[10],'ready'))
            kot_iid += 1
        kot_id += 1

        # INSERT OFFER REDEMPTION
        if off_id and disc_amt>0:
            cur.execute("""
                INSERT INTO offer_redemptions
                (redemption_id,offer_id,order_id,customer_id,
                 discount_applied,redeemed_at)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (red_id,off_id,order_id,cust_id,disc_amt,placed_at))
            red_id += 1

        # INSERT FEEDBACK
        if cust_id and random.random()<0.30:
            if del_off<=20:    rp=[0.01,0.02,0.07,0.30,0.60]
            elif del_off<=35:  rp=[0.02,0.05,0.15,0.45,0.33]
            else:              rp=[0.05,0.15,0.30,0.35,0.15]
            ovr  = int(np.random.choice([1,2,3,4,5],p=rp))
            fr   = int(min(5,max(1,ovr+random.randint(-1,1))))
            sr   = int(min(5,max(1,ovr+random.randint(-1,1))))
            sent = 'positive' if ovr>=4 else 'neutral' if ovr==3 else 'negative'
            cur.execute("""
                INSERT INTO feedback
                (feedback_id,order_id,customer_id,overall_rating,
                 food_rating,service_rating,comment,sentiment,submitted_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (fb_id,order_id,cust_id,ovr,fr,sr,None,sent,
                  deliv_at+timedelta(minutes=random.randint(5,60))))
            fb_id += 1

        order_id += 1

    # Commit every 30 days
    if day_offset % 30 == 0:
        conn.commit()
        print(f'  Day {day_offset}/365 — orders so far: {order_id-1:,}')

conn.commit()
print(f'✅ Orders done: {order_id-1:,} total')

# ============================================================
# 3. INVENTORY LOG
# ============================================================
print('Inserting inventory log...')
log_id = 1

for (d, ing_id), qty in daily_consumption.items():
    cur.execute("""
        INSERT INTO inventory_log
        (ing_id,change_type,qty_changed,reason,logged_at)
        VALUES (%s,%s,%s,%s,%s)
    """, (ing_id,'consumed',round(qty,4),
          'Daily order consumption',
          datetime(d.year,d.month,d.day,23,59,0)))
    log_id += 1

for week in range(52):
    rd = start_date + timedelta(weeks=week)
    for ing_id in range(1,26):
        if random.random()<0.7:
            cur.execute("""
                INSERT INTO inventory_log
                (ing_id,change_type,qty_changed,reason,logged_at)
                VALUES (%s,%s,%s,%s,%s)
            """, (ing_id,'restock',round(random.uniform(5,30),2),
                  'Weekly supplier delivery',
                  datetime(rd.year,rd.month,rd.day,7,0,0)))
            log_id += 1

for _ in range(200):
    rd = start_date + timedelta(days=random.randint(0,364))
    cur.execute("""
        INSERT INTO inventory_log
        (ing_id,change_type,qty_changed,reason,logged_at)
        VALUES (%s,%s,%s,%s,%s)
    """, (random.randint(1,25),'wasted',
          round(random.uniform(0.1,2.0),3),
          random.choice(['expired','spillage','over-prep','quality issue']),
          datetime(rd.year,rd.month,rd.day,random.randint(8,22),0,0)))
    log_id += 1

conn.commit()
print(f'✅ Inventory log done: {log_id-1:,} entries')

# ============================================================
# CRITICAL — RESET ALL SEQUENCES
# Without this, Express API inserts will crash with
# duplicate key errors on first request
# ============================================================
print('\nResetting sequences...')
sequences = [
    ('customers',         'customer_id'),
    ('orders',            'order_id'),
    ('order_items',       'line_id'),
    ('order_addons',      'addon_line_id'),
    ('order_payments',    'payment_id'),
    ('kot',               'kot_id'),
    ('kot_items',         'kot_item_id'),
    ('offer_redemptions', 'redemption_id'),
    ('feedback',          'feedback_id'),
    ('inventory_log',     'log_id'),
]
for table, col in sequences:
    cur.execute(f"""
        SELECT setval(
            pg_get_serial_sequence('{table}', '{col}'),
            (SELECT MAX({col}) FROM {table})
        )
    """)
    cur.execute(f"SELECT currval(pg_get_serial_sequence('{table}', '{col}'))")
    val = cur.fetchone()[0]
    print(f'  {table:25s} → sequence reset to {val:,}')

conn.commit()
print('✅ All sequences reset — Express API inserts safe')

# ============================================================
# FINAL VERIFICATION
# ============================================================
print('\n📊 FINAL ROW COUNTS:')
for table in ['customers','orders','order_items','order_addons',
              'order_payments','kot','kot_items','offer_redemptions',
              'feedback','inventory_log']:
    cur.execute(f'SELECT COUNT(*) FROM {table}')
    print(f'  {table:25s}: {cur.fetchone()[0]:,}')

# Sanity checks
print('\n🔍 SANITY CHECKS:')
cur.execute("SELECT COUNT(*) FROM orders WHERE customer_id IS NOT NULL")
print(f'  Orders with customer    : {cur.fetchone()[0]:,} (~60% expected)')

cur.execute("SELECT COUNT(*) FROM order_addons oa JOIN order_items oi ON oa.line_id = oi.line_id")
print(f'  Addons with valid FK    : {cur.fetchone()[0]:,} (should match total addons)')

cur.execute("SELECT COUNT(*) FROM order_addons")
total_addons = cur.fetchone()[0]
print(f'  Total addons            : {total_addons:,}')

cur.execute("SELECT AVG(total) FROM orders")
print(f'  Avg order value         : ₹{cur.fetchone()[0]:,.0f}')

cur.execute("SELECT SUM(total) FROM orders")
print(f'  Total revenue           : ₹{cur.fetchone()[0]:,.0f}')

cur.execute("""
    SELECT channel, COUNT(*), ROUND(AVG(total)::numeric, 0)
    FROM orders GROUP BY channel ORDER BY COUNT DESC
""")
print('\n  Revenue by channel:')
for row in cur.fetchall():
    print(f'    {row[0]:12s}: {row[1]:,} orders | avg ₹{row[2]}')

cur.close()
conn.close()
print('\n✅ Database fully populated and ready!')
