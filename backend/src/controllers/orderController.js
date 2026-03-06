const db = require('../config/db');

exports.list = async (req, res, next) => {
  try {
    const { status, limit } = req.query;
    // Default to today when no date is provided so live mode shows only today's orders.
    const date = req.query.date || new Date().toISOString().slice(0, 10);
    const conditions = [];
    const params = [];
    let idx = 1;

    if (status) {
      conditions.push(`o.status = $${idx++}`);
      params.push(status);
    }
    conditions.push(`o.placed_at::date = $${idx++}`);
    params.push(date);

    const where = conditions.length > 0 ? 'WHERE ' + conditions.join(' AND ') : '';
    const lim = Math.min(parseInt(limit, 10) || 100, 500);

    const { rows } = await db.query(`
      SELECT
        o.order_id, o.channel, o.status, o.placed_at, o.delivered_at,
        o.subtotal, o.discount_amt, o.tax_amt, o.total, o.payment_status,
        o.customer_id, c.name AS customer_name,
        json_agg(
          json_build_object(
            'line_id', oi.line_id,
            'item_name', mi.name,
            'variant_name', mv.variant_name,
            'qty', oi.qty,
            'unit_price', oi.unit_price,
            'revenue', oi.revenue,
            'special_instructions', oi.special_instructions
          ) ORDER BY oi.line_id
        ) AS items
      FROM orders o
      LEFT JOIN customers c ON o.customer_id = c.customer_id
      LEFT JOIN order_items oi ON o.order_id = oi.order_id
      LEFT JOIN menu_items mi ON oi.item_id = mi.item_id
      LEFT JOIN menu_variants mv ON oi.variant_id = mv.variant_id
      ${where}
      GROUP BY o.order_id, c.name
      ORDER BY o.placed_at DESC
      LIMIT ${lim}
    `, params);

    res.json(rows);
  } catch (err) {
    next(err);
  }
};

exports.today = async (req, res, next) => {
  try {
    const date = req.query.date || new Date().toISOString().slice(0, 10);
    const { rows } = await db.query(`
      SELECT
        COUNT(*)::int AS total_orders,
        COALESCE(SUM(total), 0)::numeric AS total_revenue,
        COALESCE(AVG(total), 0)::numeric AS avg_order_value
      FROM orders
      WHERE placed_at::date = $1 AND status != 'cancelled'
    `, [date]);
    res.json(rows[0]);
  } catch (err) {
    next(err);
  }
};

exports.create = async (req, res, next) => {
  const client = await db.pool.connect();
  try {
    const {
      customer_id, channel, placed_by, items, addons, payment_method,
    } = req.body;

    if (!items || items.length === 0) {
      return res.status(400).json({ error: 'Order must contain at least one item' });
    }

    await client.query('BEGIN');

    // Fetch variant details for each item
    let subtotal = 0;
    let totalTax = 0;
    const resolvedItems = [];

    for (const item of items) {
      const vRes = await client.query(
        'SELECT selling_price, food_cost, gst_pct FROM menu_variants WHERE variant_id = $1',
        [item.variant_id]
      );
      if (vRes.rows.length === 0) {
        await client.query('ROLLBACK');
        return res.status(400).json({ error: `Variant ${item.variant_id} not found` });
      }
      const v = vRes.rows[0];
      const qty = item.qty || 1;
      const discPct = item.discount_pct || 0;
      const lineRevenue = parseFloat(v.selling_price) * qty * (1 - discPct / 100);
      const lineCost = parseFloat(v.food_cost) * qty;
      const lineGst = lineRevenue * parseFloat(v.gst_pct) / 100;

      subtotal += lineRevenue;
      totalTax += lineGst;
      resolvedItems.push({
        item_id: item.item_id,
        variant_id: item.variant_id,
        qty,
        unit_price: parseFloat(v.selling_price),
        discount_pct: discPct,
        revenue: lineRevenue,
        food_cost: lineCost,
        gst_amt: lineGst,
        special_instructions: item.special_instructions || null,
        is_upsell: item.is_upsell || false,
        trigger_item_name: item.trigger_item_name || null,
      });
    }

    const discountAmt = req.body.discount_amt || 0;
    const total = subtotal - discountAmt + totalTax;

    // ── Stock availability pre-check ────────────────────────────────────────
    // For each ordered item, check that every ingredient required by its recipe
    // has enough current_stock to fulfil this order.  We aggregate by ing_id
    // across all items so partial orders (e.g. 2 variants using the same
    // ingredient) are handled correctly.
    const requiredStock = {}; // ing_id -> { name, needed, available }
    for (const ri of resolvedItems) {
      const { rows: recipeRows } = await client.query(
        `SELECT r.ing_id, i.name, i.current_stock::float,
                r.qty_required::float
         FROM recipes r
         JOIN ingredients i ON i.ing_id = r.ing_id
         WHERE r.item_id = $1 AND r.variant_id = $2`,
        [ri.item_id, ri.variant_id]
      );
      for (const rr of recipeRows) {
        if (!requiredStock[rr.ing_id]) {
          requiredStock[rr.ing_id] = { name: rr.name, needed: 0, available: rr.current_stock };
        }
        requiredStock[rr.ing_id].needed += rr.qty_required * ri.qty;
      }
    }
    const shortfalls = Object.values(requiredStock).filter(r => r.needed > r.available);
    if (shortfalls.length > 0) {
      await client.query('ROLLBACK');
      return res.status(409).json({
        error: 'Insufficient stock to complete this order',
        shortfalls: shortfalls.map(s => ({
          ingredient: s.name,
          required: Math.round(s.needed * 1000) / 1000,
          available: Math.round(s.available * 1000) / 1000,
        })),
      });
    }
    // ────────────────────────────────────────────────────────────────────────
    // order_date allows the frontend to pass a simulation date (DATA_DATE) so new
    // orders appear in the same date bucket as the historical seed data.
    const orderDate = req.body.order_date || null;
    const orderRes = await client.query(
      `INSERT INTO orders (restaurant_id, customer_id, placed_by, channel, status,
        placed_at, subtotal, discount_amt, tax_amt, total, payment_status)
       VALUES (1, $1, $2, $3, 'placed',
         CASE WHEN $8::date IS NOT NULL
              THEN ($8::date + (NOW()::time))::timestamptz
              ELSE NOW() END,
         $4, $5, $6, $7, 'pending')
       RETURNING order_id`,
      [customer_id || null, placed_by || 'staff', channel || 'dine_in',
       subtotal, discountAmt, totalTax, total, orderDate]
    );
    const orderId = orderRes.rows[0].order_id;

    // 2. Insert order items
    const lineIds = [];
    for (const ri of resolvedItems) {
      const liRes = await client.query(
        `INSERT INTO order_items (order_id, item_id, variant_id, qty, unit_price,
          discount_pct, revenue, food_cost, gst_amt, special_instructions, is_upsell)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING line_id`,
        [orderId, ri.item_id, ri.variant_id, ri.qty, ri.unit_price,
         ri.discount_pct, ri.revenue, ri.food_cost, ri.gst_amt,
         ri.special_instructions, ri.is_upsell]
      );
      lineIds.push(liRes.rows[0].line_id);
      // Log upsell event for profit tracking
      if (ri.is_upsell) {
        await client.query(
          `INSERT INTO upsell_events (order_id, item_id, variant_id, trigger_item_name, revenue)
           VALUES ($1,$2,$3,$4,$5)`,
          [orderId, ri.item_id, ri.variant_id, ri.trigger_item_name, ri.revenue]
        );
      }
    }

    // 3. Insert order addons (if any)
    if (addons && addons.length > 0) {
      for (const addon of addons) {
        const lineIdx = addon.item_index || 0;
        const lineId = lineIds[lineIdx];
        if (!lineId) continue;

        const aRes = await client.query(
          'SELECT extra_price FROM menu_addons WHERE addon_id = $1',
          [addon.addon_id]
        );
        const addonPrice = aRes.rows.length > 0 ? parseFloat(aRes.rows[0].extra_price) : 0;

        await client.query(
          `INSERT INTO order_addons (line_id, addon_id, qty, price) VALUES ($1,$2,$3,$4)`,
          [lineId, addon.addon_id, addon.qty || 1, addonPrice * (addon.qty || 1)]
        );
      }
    }

    // 4. Insert payment
    await client.query(
      `INSERT INTO order_payments (order_id, method, amount, paid_at)
       VALUES ($1, $2, $3, NOW())`,
      [orderId, payment_method || 'cash', total]
    );

    // 5. Create KOT
    const kotRes = await client.query(
      `INSERT INTO kot (order_id, status, priority, created_at) VALUES ($1, 'pending', 'normal', NOW()) RETURNING kot_id`,
      [orderId]
    );
    const kotId = kotRes.rows[0].kot_id;

    // 6. Create KOT items
    for (let i = 0; i < resolvedItems.length; i++) {
      const ri = resolvedItems[i];
      await client.query(
        `INSERT INTO kot_items (kot_id, item_id, variant_id, qty, special_instructions, status)
         VALUES ($1,$2,$3,$4,$5,'pending')`,
        [kotId, ri.item_id, ri.variant_id, ri.qty, ri.special_instructions]
      );
    }

    // 7. Deduct inventory via recipes
    for (const ri of resolvedItems) {
      const recipes = await client.query(
        'SELECT ing_id, qty_required FROM recipes WHERE item_id = $1 AND variant_id = $2',
        [ri.item_id, ri.variant_id]
      );
      for (const recipe of recipes.rows) {
        const consumed = parseFloat(recipe.qty_required) * ri.qty;
        await client.query(
          'UPDATE ingredients SET current_stock = current_stock - $1 WHERE ing_id = $2',
          [consumed, recipe.ing_id]
        );
        await client.query(
          `INSERT INTO inventory_log (ing_id, change_type, qty_changed, reason, logged_at)
           VALUES ($1, 'consumed', $2, $3, NOW())`,
          [recipe.ing_id, -consumed, `Order #${orderId}`]
        );
      }
    }

    await client.query('COMMIT');

    // Update customer aggregates + re-derive segment (outside transaction — best-effort)
    if (customer_id) {
      await db.query(`
        UPDATE customers SET
          total_visits   = total_visits + 1,
          total_spent    = total_spent + $1,
          avg_order_val  = (total_spent + $1) / (total_visits + 1),
          last_visit     = CURRENT_DATE,
          favourite_item = (
            SELECT mi.name
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            JOIN menu_items mi ON oi.item_id = mi.item_id
            WHERE o.customer_id = $2
            GROUP BY mi.name
            ORDER BY SUM(oi.qty) DESC
            LIMIT 1
          ),
          segment = CASE
            WHEN (total_spent + $1) > 15000 AND (total_visits + 1) > 20 THEN 'VIP'
            WHEN (total_visits + 1) > 10                                 THEN 'Regular'
            WHEN CURRENT_DATE - INTERVAL '90 days' > last_visit          THEN 'Lost'
            WHEN (total_visits + 1) <= 2                                 THEN 'New'
            ELSE 'Occasional'
          END
        WHERE customer_id = $2
      `, [total, customer_id]);
    }

    res.status(201).json({
      order_id: orderId,
      kot_id: kotId,
      total,
      status: 'placed',
    });
  } catch (err) {
    await client.query('ROLLBACK');
    next(err);
  } finally {
    client.release();
  }
};

exports.updateStatus = async (req, res, next) => {
  try {
    const { id } = req.params;
    const { status } = req.body;
    const validStatuses = ['placed', 'preparing', 'ready', 'delivered', 'cancelled'];
    if (!validStatuses.includes(status)) {
      return res.status(400).json({ error: `Invalid status. Must be one of: ${validStatuses.join(', ')}` });
    }

    const deliveredAt = status === 'delivered' ? 'NOW()' : 'delivered_at';
    const paymentStatus = status === 'delivered' ? 'paid' : status === 'cancelled' ? 'refunded' : 'pending';

    await db.query(
      `UPDATE orders SET status = $1, delivered_at = ${deliveredAt}, payment_status = $3 WHERE order_id = $2`,
      [status, id, paymentStatus]
    );

    // Sync KOT status
    const kotStatusMap = {
      placed: 'pending',
      preparing: 'preparing',
      ready: 'ready',
      delivered: 'ready',
      cancelled: 'ready',
    };
    await db.query(
      'UPDATE kot SET status = $1 WHERE order_id = $2',
      [kotStatusMap[status], id]
    );

    res.json({ order_id: parseInt(id, 10), status });
  } catch (err) {
    next(err);
  }
};
