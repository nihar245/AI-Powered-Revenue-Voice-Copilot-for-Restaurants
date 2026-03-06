-- Seed realistic order data for Reports, Dashboard, Analytics, and Revenue pages
-- Generates ~50 orders across the last 30 days with realistic patterns

-- Step 1: Insert customers first (outside the main DO block)
INSERT INTO customers (name, phone, email) VALUES
    ('Rahul Sharma', '9876543210', 'rahul@email.com'),
    ('Priya Patel', '9876543211', 'priya@email.com'),
    ('Amit Kumar', '9876543212', 'amit@email.com'),
    ('Sneha Gupta', '9876543213', 'sneha@email.com'),
    ('Rajesh Verma', '9876543214', 'rajesh@email.com')
ON CONFLICT (phone) DO NOTHING;

-- Step 2: Generate orders
DO $$
DECLARE
    v_order_id INT;
    v_kot_id INT;
    v_item RECORD;
    v_variant RECORD;
    v_line_revenue NUMERIC;
    v_line_cost NUMERIC;
    v_line_gst NUMERIC;
    v_subtotal NUMERIC;
    v_tax NUMERIC;
    v_total NUMERIC;
    v_placed_at TIMESTAMP;
    v_channel TEXT;
    v_status TEXT;
    v_customer_id INT;
    v_payment_method TEXT;
    v_cust_ids INT[];
    i INT;
    j INT;
    v_num_items INT;
    v_item_id INT;
    v_qty INT;
BEGIN
    -- Get actual customer IDs
    SELECT array_agg(customer_id) INTO v_cust_ids FROM customers LIMIT 5;

    -- Generate 50 orders over last 30 days
    FOR i IN 1..50 LOOP
        -- Random time in last 30 days, weighted toward lunch/dinner hours
        v_placed_at := NOW() - (random() * 30 || ' days')::INTERVAL 
                     + ((CASE 
                         WHEN random() < 0.4 THEN 12 + floor(random() * 3)  -- lunch 12-14
                         WHEN random() < 0.8 THEN 19 + floor(random() * 3)  -- dinner 19-21
                         ELSE 10 + floor(random() * 12)                      -- other hours
                        END) || ' hours')::INTERVAL
                     + (floor(random() * 60) || ' minutes')::INTERVAL;
        
        -- Random channel (must be one of: dine_in, takeaway, zomato, swiggy, phone)
        v_channel := (ARRAY['dine_in', 'dine_in', 'dine_in', 'takeaway', 'phone', 'zomato'])[floor(random() * 6 + 1)];
        
        -- Most orders completed, some cancelled
        v_status := (CASE WHEN random() < 0.85 THEN 'delivered' 
                         WHEN random() < 0.93 THEN 'placed'
                         ELSE 'cancelled' END);
        
        -- Random customer (some null for walk-ins)
        v_customer_id := (CASE WHEN random() < 0.6 AND v_cust_ids IS NOT NULL 
                          THEN v_cust_ids[1 + floor(random() * array_length(v_cust_ids, 1))::INT]
                          ELSE NULL END);
        
        -- Payment method (must be: cash, upi, credit_card, debit_card, wallet, razorpay, online)
        v_payment_method := (ARRAY['cash', 'cash', 'upi', 'upi', 'credit_card'])[floor(random() * 5 + 1)];
        
        v_subtotal := 0;
        v_tax := 0;
        
        -- Create order
        INSERT INTO orders (restaurant_id, customer_id, placed_by, channel, status, placed_at, subtotal, discount_amt, tax_amt, total, payment_status)
        VALUES (1, v_customer_id, 
                CASE WHEN v_channel = 'phone' THEN 'voice_copilot' ELSE 'staff' END,
                v_channel, v_status, v_placed_at, 0, 0, 0, 0,
                CASE WHEN v_status = 'cancelled' THEN 'refunded' ELSE 'paid' END)
        RETURNING order_id INTO v_order_id;
        
        -- Random number of items per order (2-5)
        v_num_items := floor(random() * 4 + 2)::INT;
        
        FOR j IN 1..v_num_items LOOP
            -- Pick random available item
            SELECT mi.item_id INTO v_item_id
            FROM menu_items mi
            WHERE mi.is_available = TRUE
            ORDER BY random()
            LIMIT 1;
            
            -- Get a variant for this item
            SELECT mv.variant_id, mv.selling_price, mv.food_cost, mv.gst_pct
            INTO v_variant
            FROM menu_variants mv
            WHERE mv.item_id = v_item_id AND mv.is_available = TRUE
            ORDER BY mv.selling_price DESC
            LIMIT 1;
            
            IF v_variant IS NOT NULL AND v_variant.selling_price > 0 THEN
                v_qty := (CASE WHEN random() < 0.7 THEN 1 WHEN random() < 0.9 THEN 2 ELSE 3 END);
                v_line_revenue := v_variant.selling_price * v_qty;
                v_line_cost := v_variant.food_cost * v_qty;
                v_line_gst := v_line_revenue * v_variant.gst_pct / 100;
                
                INSERT INTO order_items (order_id, item_id, variant_id, qty, unit_price, discount_pct, revenue, food_cost, gst_amt, special_instructions, is_upsell)
                VALUES (v_order_id, v_item_id, v_variant.variant_id, v_qty, v_variant.selling_price, 0, v_line_revenue, v_line_cost, v_line_gst, NULL, 
                        CASE WHEN j > 2 AND random() < 0.3 THEN TRUE ELSE FALSE END);
                
                v_subtotal := v_subtotal + v_line_revenue;
                v_tax := v_tax + v_line_gst;
            END IF;
        END LOOP;
        
        v_total := v_subtotal + v_tax;
        
        -- Update order totals
        UPDATE orders SET subtotal = v_subtotal, tax_amt = v_tax, total = v_total
        WHERE order_id = v_order_id;
        
        -- Create payment record
        INSERT INTO order_payments (order_id, method, amount, paid_at)
        VALUES (v_order_id, v_payment_method, v_total, 
                v_placed_at + INTERVAL '10 minutes');
        
        -- Create KOT for non-cancelled orders
        IF v_status != 'cancelled' THEN
            INSERT INTO kot (order_id, status, priority, created_at)
            VALUES (v_order_id, 
                    CASE WHEN v_status = 'delivered' THEN 'ready' ELSE 'pending' END,
                    'normal', v_placed_at)
            RETURNING kot_id INTO v_kot_id;
            
            -- Add KOT items
            INSERT INTO kot_items (kot_id, item_id, variant_id, qty, special_instructions, status)
            SELECT v_kot_id, oi.item_id, oi.variant_id, oi.qty, oi.special_instructions,
                   CASE WHEN v_status = 'delivered' THEN 'ready' ELSE 'pending' END
            FROM order_items oi
            WHERE oi.order_id = v_order_id;
        END IF;
        
        -- Deduct ingredients for completed orders
        IF v_status = 'delivered' THEN
            UPDATE ingredients i
            SET current_stock = GREATEST(0, i.current_stock - sub.total_needed)
            FROM (
                SELECT r.ing_id, SUM(r.qty_required * oi.qty) as total_needed
                FROM order_items oi
                JOIN recipes r ON r.item_id = oi.item_id AND r.variant_id = oi.variant_id
                WHERE oi.order_id = v_order_id
                GROUP BY r.ing_id
            ) sub
            WHERE i.ing_id = sub.ing_id;
        END IF;
    END LOOP;
    
    RAISE NOTICE 'Seeded 50 orders with items, payments, KOTs, and inventory deductions';
END $$;

-- Verify the seed
SELECT 'Orders: ' || COUNT(*) FROM orders;
SELECT 'Order Items: ' || COUNT(*) FROM order_items;
SELECT 'Payments: ' || COUNT(*) FROM order_payments;
SELECT 'KOTs: ' || COUNT(*) FROM kot;
SELECT 'Avg Order Value: ₹' || ROUND(AVG(total)::numeric, 0) FROM orders WHERE status != 'cancelled';
