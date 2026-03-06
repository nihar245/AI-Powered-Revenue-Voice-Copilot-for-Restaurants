const db = require('../config/db');
const aiService = require('../services/aiService');
const crypto = require('crypto');

// ──── Transcribe: audio → text (proxy to AI service Deepgram STT) ────────────
exports.transcribe = async (req, res, next) => {
  try {
    const result = await aiService.post('/voice/transcribe', req.body, {
      headers: req.headers['content-type']
        ? { 'Content-Type': req.headers['content-type'] }
        : {},
    });
    if (result && result.data) return res.json(result.data);
    res.status(503).json({ error: 'AI service unavailable. Start ai_service on port 8001.' });
  } catch (err) {
    next(err);
  }
};

// ──── Intent: text → structured intent (proxy to AI service Groq LLM) ────────
exports.intent = async (req, res, next) => {
  try {
    // AI service expects { transcript }, frontend may send { text }
    const payload = { transcript: req.body.transcript || req.body.text };
    const result = await aiService.post('/voice/intent', payload);
    if (result && result.data) return res.json(result.data);
    res.status(503).json({ error: 'AI service unavailable. Start ai_service on port 8001.' });
  } catch (err) {
    next(err);
  }
};

// ──── Speak: text → TTS audio (proxy to AI service Deepgram TTS) ─────────────
exports.speak = async (req, res, next) => {
  try {
    const result = await aiService.post('/voice/speak', {
      text: req.body.text,
      response_format: 'json',
    });
    if (result && result.data) return res.json(result.data);
    res.status(503).json({ error: 'AI service unavailable.' });
  } catch (err) {
    next(err);
  }
};

// ──── AI Service Health ──────────────────────────────────────────────────────
exports.aiHealth = async (_req, res) => {
  try {
    const resp = await aiService.get('/health');
    if (resp && resp.data) return res.json({ ai_service: 'connected', ...resp.data });
    res.json({ ai_service: 'unavailable' });
  } catch {
    res.json({ ai_service: 'unavailable' });
  }
};

// ──── Confirm Order: resolve item names → DB IDs, create order + KOT ─────────


exports.confirmOrder = async (req, res, next) => {
  const client = await db.pool.connect();
  try {
    const { items, customer_id: _cid, channel, customer_name, phone } = req.body;

    if (!items || items.length === 0) {
      return res.status(400).json({ error: 'No items provided' });
    }

    await client.query('BEGIN');

    // ── Upsert customer if phone is provided ──────────────────────────────────
    let resolvedCustomerId = _cid || null;
    if (phone) {
      const custRes = await client.query(
        `INSERT INTO customers (phone, name, first_visit, last_visit, total_visits)
         VALUES ($1, $2, CURRENT_DATE, CURRENT_DATE, 1)
         ON CONFLICT (phone) DO UPDATE
           SET name        = COALESCE(NULLIF($2,''), customers.name),
               last_visit  = CURRENT_DATE,
               total_visits = customers.total_visits + 1
         RETURNING customer_id`,
        [phone, customer_name || '']
      );
      resolvedCustomerId = custRes.rows[0].customer_id;
    }

    let subtotal = 0;
    let totalTax = 0;
    const resolvedItems = [];

    for (const item of items) {
      // Resolve item name → item_id
      const itemRes = await client.query(
        `SELECT item_id FROM menu_items
         WHERE LOWER(name) = LOWER($1) AND is_available = TRUE
         LIMIT 1`,
        [item.name]
      );
      if (itemRes.rows.length === 0) continue;
      const itemId = itemRes.rows[0].item_id;

      // Get the default variant (prefer "Full", else first available)
      const varRes = await client.query(
        `SELECT variant_id, selling_price, food_cost, gst_pct
         FROM menu_variants
         WHERE item_id = $1 AND is_available = TRUE
         ORDER BY CASE WHEN variant_name = 'Full' THEN 0 ELSE 1 END, selling_price DESC
         LIMIT 1`,
        [itemId]
      );
      if (varRes.rows.length === 0) continue;
      const v = varRes.rows[0];

      const qty = item.quantity || 1;
      const lineRevenue = parseFloat(v.selling_price) * qty;
      const lineCost = parseFloat(v.food_cost) * qty;
      const lineGst = lineRevenue * parseFloat(v.gst_pct) / 100;

      subtotal += lineRevenue;
      totalTax += lineGst;
      resolvedItems.push({
        item_id: itemId,
        variant_id: v.variant_id,
        qty,
        unit_price: parseFloat(v.selling_price),
        revenue: lineRevenue,
        food_cost: lineCost,
        gst_amt: lineGst,
        special_instructions: (item.modifications || []).join(', ') || null,
      });
    }

    if (resolvedItems.length === 0) {
      await client.query('ROLLBACK');
      return res.status(400).json({ error: 'No valid items could be resolved from menu' });
    }

    const total = subtotal + totalTax;

    const orderRes = await client.query(
      `INSERT INTO orders (restaurant_id, customer_id, placed_by, channel, status,
        placed_at, subtotal, discount_amt, tax_amt, total, payment_status)
       VALUES (1, $1, $2, $3, 'placed', NOW(), $4, 0, $5, $6, 'pending')
       RETURNING order_id`,
      [resolvedCustomerId || null, customer_name || 'voice_copilot', channel || 'phone', subtotal, totalTax, total]
    );
    const orderId = orderRes.rows[0].order_id;

    for (const ri of resolvedItems) {
      await client.query(
        `INSERT INTO order_items (order_id, item_id, variant_id, qty, unit_price,
          discount_pct, revenue, food_cost, gst_amt, special_instructions)
         VALUES ($1,$2,$3,$4,$5,0,$6,$7,$8,$9)`,
        [orderId, ri.item_id, ri.variant_id, ri.qty, ri.unit_price,
         ri.revenue, ri.food_cost, ri.gst_amt, ri.special_instructions]
      );
    }

    const kotRes = await client.query(
      `INSERT INTO kot (order_id, status, priority, created_at) VALUES ($1, 'pending', 'normal', NOW()) RETURNING kot_id`,
      [orderId]
    );
    const kotId = kotRes.rows[0].kot_id;

    for (const ri of resolvedItems) {
      await client.query(
        `INSERT INTO kot_items (kot_id, item_id, variant_id, qty, special_instructions, status)
         VALUES ($1,$2,$3,$4,$5,'pending')`,
        [kotId, ri.item_id, ri.variant_id, ri.qty, ri.special_instructions]
      );
    }

    await client.query('COMMIT');

    res.status(201).json({
      order_id: orderId,
      kot_id: kotId,
      items_count: resolvedItems.length,
      total: Math.round(total * 100) / 100,
      status: 'placed',
      customer_name: customer_name || null,
      customer_id: resolvedCustomerId || null,
    });
  } catch (err) {
    await client.query('ROLLBACK');
    next(err);
  } finally {
    client.release();
  }
};

// ──── Get Session State ──────────────────────────────────────────────────────
exports.getSession = async (req, res) => {
  const session = sessions.get(req.params.session_id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  res.json(session);
};
