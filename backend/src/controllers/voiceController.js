const db = require('../config/db');
const mlService = require('../services/mlService');
const crypto = require('crypto');

// In-memory session store (per plan.md: voice session state is in-memory)
const sessions = new Map();

// ──── Transcribe: audio → text (proxy to ML Whisper) ─────────────────────────
exports.transcribe = async (req, res, next) => {
  try {
    const mlResult = await mlService.post('/voice/transcribe', req.body);
    if (mlResult) return res.json(mlResult);
    res.status(503).json({ error: 'ML service unavailable. Start FastAPI on port 8000.' });
  } catch (err) {
    next(err);
  }
};

// ──── Intent: text → intent label (proxy to ML DistilBERT) ───────────────────
exports.intent = async (req, res, next) => {
  try {
    const mlResult = await mlService.post('/predict/intent', req.body);
    if (mlResult) return res.json(mlResult);
    res.status(503).json({ error: 'ML service unavailable. Start FastAPI on port 8000.' });
  } catch (err) {
    next(err);
  }
};

// ──── Process Turn: full pipeline (proxy to ML) ──────────────────────────────
exports.processTurn = async (req, res, next) => {
  try {
    const { text, session_id } = req.body;
    const sid = session_id || crypto.randomUUID();

    // Get or create session
    if (!sessions.has(sid)) {
      sessions.set(sid, { session_id: sid, items: [], created_at: new Date() });
    }
    const session = sessions.get(sid);

    // Proxy to ML full pipeline
    const mlResult = await mlService.post('/voice/process-turn', {
      text,
      session_id: sid,
      current_items: session.items,
    });

    if (mlResult) {
      // Update session with ML-returned items
      if (mlResult.items) session.items = mlResult.items;
      sessions.set(sid, session);
      return res.json({ ...mlResult, session_id: sid });
    }

    // Fallback: echo back with session
    res.json({
      session_id: sid,
      transcript: text,
      intent: 'unknown',
      items: session.items,
      message: 'ML service unavailable — voice pipeline not active',
    });
  } catch (err) {
    next(err);
  }
};

// ──── Confirm Order: create order in DB from voice session ───────────────────
exports.confirmOrder = async (req, res, next) => {
  const client = await db.pool.connect();
  try {
    const { session_id, customer_id, channel } = req.body;

    const session = sessions.get(session_id);
    if (!session || session.items.length === 0) {
      return res.status(400).json({ error: 'No active voice session or empty cart' });
    }

    await client.query('BEGIN');

    let subtotal = 0;
    let totalTax = 0;
    const resolvedItems = [];

    for (const item of session.items) {
      const vRes = await client.query(
        'SELECT selling_price, food_cost, gst_pct FROM menu_variants WHERE variant_id = $1',
        [item.variant_id]
      );
      if (vRes.rows.length === 0) continue;
      const v = vRes.rows[0];
      const qty = item.qty || 1;
      const lineRevenue = parseFloat(v.selling_price) * qty;
      const lineCost = parseFloat(v.food_cost) * qty;
      const lineGst = lineRevenue * parseFloat(v.gst_pct) / 100;

      subtotal += lineRevenue;
      totalTax += lineGst;
      resolvedItems.push({
        item_id: item.item_id,
        variant_id: item.variant_id,
        qty,
        unit_price: parseFloat(v.selling_price),
        revenue: lineRevenue,
        food_cost: lineCost,
        gst_amt: lineGst,
        special_instructions: item.special_instructions || null,
      });
    }

    const total = subtotal + totalTax;

    const orderRes = await client.query(
      `INSERT INTO orders (restaurant_id, customer_id, placed_by, channel, status,
        placed_at, subtotal, discount_amt, tax_amt, total, payment_status)
       VALUES (1, $1, 'voice_copilot', $2, 'placed', NOW(), $3, 0, $4, $5, 'pending')
       RETURNING order_id`,
      [customer_id || null, channel || 'dine_in', subtotal, totalTax, total]
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

    // Clear session
    sessions.delete(session_id);

    res.status(201).json({ order_id: orderId, kot_id: kotId, total, status: 'placed' });
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
