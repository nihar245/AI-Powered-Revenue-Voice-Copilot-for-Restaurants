const db = require('../config/db');
const axios = require('axios');
const FormData = require('form-data');
const crypto = require('crypto');

const AI_URL = process.env.AI_SERVICE_URL || 'http://localhost:8002';

// ──── Voice Turn (audio) – proxy multipart to Python /voice/order ────────────
exports.voiceTurn = async (req, res, next) => {
  try {
    const form = new FormData();
    if (req.file) {
      form.append('audio', req.file.buffer, {
        filename: req.file.originalname || 'audio.webm',
        contentType: req.file.mimetype || 'audio/webm',
      });
    }
    form.append('session_id', req.body.session_id || crypto.randomUUID());
    if (req.body.channel) form.append('channel', req.body.channel);

    const resp = await axios.post(`${AI_URL}/voice/order`, form, {
      headers: form.getHeaders(),
      timeout: 60000,
      maxContentLength: 50 * 1024 * 1024,
    });
    res.json(resp.data);
  } catch (err) {
    if (err.response) return res.status(err.response.status).json(err.response.data);
    next(err);
  }
};

// ──── Voice Chat (text) – proxy to Python /test/voice-chat ───────────────────
exports.voiceChat = async (req, res, next) => {
  try {
    const form = new FormData();
    form.append('session_id', req.body.session_id || crypto.randomUUID());
    form.append('user_text', req.body.user_text || '');
    if (req.body.channel) form.append('channel', req.body.channel);

    const resp = await axios.post(`${AI_URL}/test/voice-chat`, form, {
      headers: form.getHeaders(),
      timeout: 30000,
    });
    res.json(resp.data);
  } catch (err) {
    if (err.response) return res.status(err.response.status).json(err.response.data);
    next(err);
  }
};

// ──── Add Item (upsell chip click) – proxy to Python /test/add-item ─────────
exports.addItem = async (req, res, next) => {
  try {
    const form = new FormData();
    form.append('session_id', req.body.session_id);
    form.append('product_id', req.body.product_id);
    form.append('item_name', req.body.item_name);
    if (req.body.quantity) form.append('quantity', String(req.body.quantity));

    const resp = await axios.post(`${AI_URL}/test/add-item`, form, {
      headers: form.getHeaders(),
      timeout: 10000,
    });
    res.json(resp.data);
  } catch (err) {
    if (err.response) return res.status(err.response.status).json(err.response.data);
    next(err);
  }
};

// ──── Reset Session ──────────────────────────────────────────────────────────
exports.resetSession = async (req, res, next) => {
  try {
    const resp = await axios.post(`${AI_URL}/voice/reset`,
      { session_id: req.body.session_id },
      { headers: { 'Content-Type': 'application/json' }, timeout: 5000 }
    );
    res.json(resp.data);
  } catch (err) {
    if (err.response) return res.status(err.response.status).json(err.response.data);
    next(err);
  }
};

// ──── Get AI Service Health ──────────────────────────────────────────────────
exports.health = async (req, res) => {
  try {
    const resp = await axios.get(`${AI_URL}/health`, { timeout: 5000 });
    res.json({ status: 'ok', ai_service: resp.data });
  } catch {
    res.json({ status: 'degraded', ai_service: 'unavailable' });
  }
};

// ──── Confirm Order: create order in DB from voice session ───────────────────
exports.confirmOrder = async (req, res, next) => {
  const client = await db.pool.connect();
  try {
    const { session_id, customer_id, channel } = req.body;

    // Fetch session cart from AI service
    let cart;
    try {
      const resp = await axios.get(`${AI_URL}/test/session/${session_id}`, { timeout: 5000 });
      cart = resp.data && resp.data.cart;
    } catch {
      cart = null;
    }

    if (!cart || cart.length === 0) {
      return res.status(400).json({ error: 'No active voice session or empty cart' });
    }

    await client.query('BEGIN');

    let subtotal = 0;
    let totalTax = 0;
    const resolvedItems = [];

    for (const item of cart) {
      const vid = item.variant_id || item.item_id;
      const vRes = await client.query(
        'SELECT selling_price, food_cost, gst_pct FROM menu_variants WHERE variant_id = $1',
        [vid]
      );
      if (vRes.rows.length === 0) continue;
      const v = vRes.rows[0];
      const qty = item.quantity || item.qty || 1;
      const lineRevenue = parseFloat(v.selling_price) * qty;
      const lineCost = parseFloat(v.food_cost) * qty;
      const lineGst = lineRevenue * parseFloat(v.gst_pct) / 100;

      subtotal += lineRevenue;
      totalTax += lineGst;
      resolvedItems.push({
        item_id: item.item_id,
        variant_id: vid,
        qty,
        unit_price: parseFloat(v.selling_price),
        revenue: lineRevenue,
        food_cost: lineCost,
        gst_amt: lineGst,
        special_instructions: item.notes || item.special_instructions || null,
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

    res.status(201).json({ order_id: orderId, kot_id: kotId, total, status: 'placed' });
  } catch (err) {
    await client.query('ROLLBACK');
    next(err);
  } finally {
    client.release();
  }
};

// ──── Route name aliases ──────────────────────────────────────────────────────
// voice.js router uses these names; map them to the implementations above.
exports.transcribe  = exports.voiceTurn;    // POST /transcribe  → audio → AI
exports.intent      = exports.voiceChat;    // POST /intent      → text  → AI
exports.processTurn = exports.voiceTurn;    // POST /process-turn → audio turn

// GET /session/:session_id — proxy to AI service session state
exports.getSession = async (req, res, next) => {
  try {
    const resp = await axios.get(
      `${AI_URL}/test/session/${req.params.session_id}`,
      { timeout: 5000 }
    );
    res.json(resp.data);
  } catch (err) {
    if (err.response) return res.status(err.response.status).json(err.response.data);
    next(err);
  }
};
