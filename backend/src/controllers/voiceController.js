const aiService = require('../services/aiService');
const axios = require('axios');
const db    = require('../config/db');

const LOG = (...args) => console.log('[VOICE]', new Date().toISOString(), ...args);
const ERR = (...args) => console.error('[VOICE][ERROR]', new Date().toISOString(), ...args);

const AI_URL = process.env.AI_SERVICE_URL || 'http://localhost:8002';

// ---- Transcribe: deprecated (Gemini Live handles STT internally) --------------------
exports.transcribe = async (_req, res) => {
  res.status(410).json({
    error: 'Separate transcribe endpoint removed. Use POST /api/voice/process-turn with audio.',
  });
};

// ---- Intent: deprecated (intent is bundled in the voice-chat response) -------------
exports.intent = async (_req, res) => {
  res.status(410).json({
    error: 'Separate intent endpoint removed. Use POST /api/voice/process-turn with audio.',
  });
};

// ---- Process Turn: receive audio -> proxy to ai_service_gemini /test/voice-chat ----
// Expects: multipart/form-data with fields:
//   audio      (file)   - recorded audio blob
//   session_id (string) - UUID, client-generated or returned from prior turn
//   language   (string) - optional, e.g. "en" / "hi"
//   table_id   (string) - optional table identifier
exports.processTurn = async (req, res, next) => {
  try {
    if (!req.file) {
      ERR('processTurn — missing audio file');
      return res.status(400).json({ error: 'Audio file is required (field: audio)' });
    }

    const sessionId = req.body.session_id;
    if (!sessionId) {
      ERR('processTurn — missing session_id');
      return res.status(400).json({ error: 'session_id is required' });
    }

    LOG('processTurn  session_id=%s  audio_size=%d  mime=%s  table_id=%s',
      sessionId, req.file.size, req.file.mimetype, req.body.table_id || '');

    const result = await aiService.voiceChat({
      audioBuffer: req.file.buffer,
      mimeType:    req.file.mimetype || 'audio/webm',
      sessionId,
      language:  req.body.language || 'en',
      tableId:   req.body.table_id || '',
    });

    LOG('processTurn ✔  session_id=%s  intent=%s  transcript=%s',
      sessionId, result?.intent, JSON.stringify(result?.transcript || '').slice(0, 80));
    res.json(result);
  } catch (err) {
    ERR('processTurn threw — session_id=%s:', req.body?.session_id, err.message);
    next(err);
  }
};

// ---- Add Item: upsell chip / quick-add -> proxy to /test/add-item ------------------
// Expects JSON: { session_id, product_id, item_name, quantity }
exports.addItem = async (req, res, next) => {
  try {
    const { session_id, product_id, item_name, quantity } = req.body;
    LOG('addItem  session_id=%s  product_id=%s  item_name=%s  qty=%s',
      session_id, product_id, item_name, quantity);
    if (!session_id || !product_id || !item_name) {
      ERR('addItem — missing required fields');
      return res.status(400).json({ error: 'session_id, product_id, item_name are required' });
    }

    const result = await aiService.addItem({
      sessionId:  session_id,
      productId:  product_id,
      itemName:   item_name,
      quantity:   quantity || 1,
    });

    LOG('addItem ✔  session_id=%s  result=%s', session_id, JSON.stringify(result).slice(0, 120));
    res.json(result);
  } catch (err) {
    ERR('addItem threw — session_id=%s:', req.body?.session_id, err.message);
    next(err);
  }
};

// ---- Confirm Order: fetch cart from Python session, write order+KOT to Node DB ----
// Expects JSON: { session_id }  (auth middleware populates req.user)
exports.confirmOrder = async (req, res, next) => {
  const client = await db.pool.connect();
  try {
    const { session_id } = req.body;
    LOG('confirmOrder called  session_id=%s', session_id);
    if (!session_id) {
      ERR('confirmOrder — missing session_id');
      client.release();
      return res.status(400).json({ error: 'session_id is required' });
    }

    // 1.  Fetch the live cart from Python session store
    LOG('confirmOrder: fetching session cart from Python  session_id=%s', session_id);
    let sessionData;
    try {
      const sessResp = await axios.get(`${AI_URL}/test/session/${session_id}`, { timeout: 10000 });
      sessionData = sessResp.data;
    } catch (e) {
      ERR('confirmOrder: session fetch failed  session_id=%s  error=%s', session_id, e.message);
      client.release();
      return res.status(404).json({ error: 'Voice session not found or expired' });
    }

    const cart = sessionData.cart || [];
    LOG('confirmOrder: session fetched  session_id=%s  cart_items=%d', session_id, cart.length);
    if (cart.length === 0) {
      ERR('confirmOrder: cart is empty  session_id=%s', session_id);
      client.release();
      return res.status(400).json({ error: 'Cart is empty — nothing to confirm' });
    }

    // 2.  Resolve totals from cart items sent by Python (already have price + tax_rate)
    let subtotal = 0;
    let totalTax = 0;
    const resolvedItems = cart.map(item => {
      const qty       = parseInt(item.quantity, 10) || 1;
      const unitPrice = parseFloat(item.unit_price) || 0;
      const taxRate   = parseFloat(item.tax_rate)   || 5;
      const revenue   = unitPrice * qty;
      const gstAmt    = revenue * taxRate / 100;
      subtotal += revenue;
      totalTax += gstAmt;
      return {
        item_id:               parseInt(item.product_id, 10),
        variant_id:            item.variant_id ? parseInt(item.variant_id, 10) : null,
        qty,
        unit_price:            unitPrice,
        revenue,
        food_cost:             0,
        gst_amt:               gstAmt,
        special_instructions:  item.notes || null,
      };
    });
    const total       = subtotal + totalTax;
    const orderNumber = `VO-${session_id.slice(0, 6).toUpperCase()}-${Date.now().toString(36).toUpperCase()}`;
    LOG('confirmOrder: totals  subtotal=%.2f  tax=%.2f  total=%.2f  items=%d',
      subtotal, totalTax, total, resolvedItems.length);

    // 3.  Write order → order_items → KOT → kot_items in one transaction
    await client.query('BEGIN');
    LOG('confirmOrder: BEGIN transaction');

    const orderRes = await client.query(
      `INSERT INTO orders
         (restaurant_id, placed_by, channel, status, placed_at,
          subtotal, discount_amt, tax_amt, total, payment_status)
       VALUES (1, 'voice_order', 'dine_in', 'placed', NOW(),
               $1, 0, $2, $3, 'pending')
       RETURNING order_id`,
      [subtotal, totalTax, total]
    );
    const orderId = orderRes.rows[0].order_id;
    LOG('confirmOrder: orders row inserted  order_id=%d', orderId);

    for (const ri of resolvedItems) {
      await client.query(
        `INSERT INTO order_items
           (order_id, item_id, variant_id, qty, unit_price,
            discount_pct, revenue, food_cost, gst_amt, special_instructions, is_upsell)
         VALUES ($1,$2,$3,$4,$5,0,$6,$7,$8,$9,FALSE)`,
        [orderId, ri.item_id, ri.variant_id, ri.qty, ri.unit_price,
         ri.revenue, ri.food_cost, ri.gst_amt, ri.special_instructions]
      );
    }
    LOG('confirmOrder: order_items inserted  count=%d', resolvedItems.length);

    const kotRes = await client.query(
      `INSERT INTO kot (order_id, status, priority, created_at)
       VALUES ($1, 'pending', 'normal', NOW())
       RETURNING kot_id`,
      [orderId]
    );
    const kotId = kotRes.rows[0].kot_id;
    LOG('confirmOrder: KOT inserted  kot_id=%d  order_id=%d  status=pending', kotId, orderId);

    for (const ri of resolvedItems) {
      await client.query(
        `INSERT INTO kot_items
           (kot_id, item_id, variant_id, qty, special_instructions, status)
         VALUES ($1,$2,$3,$4,$5,'pending')`,
        [kotId, ri.item_id, ri.variant_id, ri.qty, ri.special_instructions]
      );
    }
    LOG('confirmOrder: kot_items inserted  count=%d', resolvedItems.length);

    await client.query('COMMIT');
    LOG('confirmOrder: COMMITTED  order_id=%d  kot_id=%d  total=%.2f  order_number=%s',
      orderId, kotId, total, orderNumber);

    // 4.  Clear cart in Python session (fire-and-forget — don't block the response)
    axios.post(
      `${AI_URL}/test/clear-session`,
      new URLSearchParams({ session_id }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, timeout: 5000 }
    ).catch(e => ERR('confirmOrder: clear-session call failed  %s', e.message));

    res.status(201).json({
      order_number: orderNumber,
      order_id:     orderId,
      kot_id:       kotId,
      total,
      cart_events:  [`✅ Order #${orderNumber} sent to kitchen — ₹${Math.round(total)}`],
      message:      `Order confirmed — ₹${Math.round(total)}`,
    });
  } catch (err) {
    await client.query('ROLLBACK').catch(() => {});
    ERR('confirmOrder threw — session_id=%s:', req.body?.session_id, err.message);
    next(err);
  } finally {
    client.release();
  }
};

// ---- Get Session state -> proxy to ai_service_gemini /test/session/:id -------------
exports.getSession = async (req, res, next) => {
  try {
    LOG('getSession  session_id=%s', req.params.session_id);
    const resp = await axios.get(
      `${AI_URL}/test/session/${req.params.session_id}`,
      { timeout: 10000 }
    );
    LOG('getSession ✔  session_id=%s  cart_items=%d',
      req.params.session_id, resp.data?.cart?.length ?? 'n/a');
    res.json(resp.data);
  } catch (err) {
    if (err.response && err.response.status === 404) {
      ERR('getSession 404  session_id=%s', req.params.session_id);
      return res.status(404).json({ error: 'Session not found' });
    }
    ERR('getSession threw  session_id=%s:', req.params.session_id, err.message);
    next(err);
  }
};

// ---- Get Menu: proxy to ai_service_gemini GET /test/menu -------------------------
exports.getMenu = async (req, res, next) => {
  try {
    const result = await aiService.getMenu();
    res.json(result);
  } catch (err) {
    next(err);
  }
};

// ---- Get Call Logs: proxy to ai_service_gemini GET /twilio/call-logs -------------
exports.getCallLogs = async (req, res, next) => {
  try {
    const limit = Math.min(parseInt(req.query.limit) || 50, 200);
    LOG('getCallLogs  limit=%d', limit);
    const resp  = await axios.get(`${AI_URL}/twilio/call-logs`, {
      params:  { limit },
      timeout: 10000,
    });
    LOG('getCallLogs ✔  returned %d entries', resp.data?.length);
    res.json(resp.data);
  } catch (err) {
    ERR('getCallLogs threw:', err.message);
    if (err.response) return res.status(err.response.status).json(err.response.data);
    next(err);
  }
};

// ---- Get Phone/Voice Orders from DB: persistent history across restarts ----------
exports.getPhoneOrders = async (req, res, next) => {
  try {
    const limit = Math.min(parseInt(req.query.limit) || 50, 200);
    LOG('getPhoneOrders  limit=%d', limit);
    const { rows } = await db.pool.query(
      `SELECT
         o.order_id,
         o.placed_by,
         o.placed_at   AS start_time,
         o.total       AS order_total,
         COALESCE(
           JSON_AGG(
             JSON_BUILD_OBJECT('name', mi.name, 'qty', oi.qty, 'price', oi.unit_price)
             ORDER BY oi.line_id
           ) FILTER (WHERE mi.name IS NOT NULL),
           '[]'::json
         ) AS items
       FROM orders o
       LEFT JOIN order_items oi ON oi.order_id = o.order_id
       LEFT JOIN menu_items  mi ON mi.item_id  = oi.item_id
       WHERE o.placed_by IN ('phone_order', 'voice_order')
       GROUP BY o.order_id
       ORDER BY o.placed_at DESC
       LIMIT $1`,
      [limit]
    );
    const result = rows.map(r => ({
      call_sid:    `db_order_${r.order_id}`,
      status:      'order_confirmed',
      caller:      r.placed_by === 'phone_order' ? 'Phone Call' : 'Voice Order',
      start_time:  r.start_time,
      end_time:    r.start_time,
      transcript:  (r.items || []).map(it => ({ aria: `${it.name} × ${it.qty}  ₹${it.price}` })),
      order_number: `#${r.order_id}`,
      order_total:  parseFloat(r.order_total),
      turns:        0,
      source:       'db',
    }));
    LOG('getPhoneOrders ✔  returned %d entries', result.length);
    res.json(result);
  } catch (err) {
    ERR('getPhoneOrders threw:', err.message);
    next(err);
  }
};

// ---- Get Active Call State: proxy to ai_service_gemini GET /twilio/active-call ----
exports.getActiveCall = async (req, res, next) => {
  try {
    const resp = await axios.get(`${AI_URL}/twilio/active-call`, { timeout: 5000 });
    res.json(resp.data);
  } catch (err) {
    if (err.response) return res.status(err.response.status).json(err.response.data);
    // If AI service is unreachable, return inactive state rather than erroring
    res.json({ active: false });
  }
};

// ---- Confirm Phone Order from Dashboard: proxy to ai_service_gemini POST /twilio/confirm-phone-order/:callSid ----
exports.confirmPhoneOrder = async (req, res, next) => {
  try {
    const { callSid } = req.params;
    LOG('confirmPhoneOrder  callSid=%s', callSid);
    const resp = await axios.post(
      `${AI_URL}/twilio/confirm-phone-order/${encodeURIComponent(callSid)}`,
      {},
      { timeout: 10000 },
    );
    LOG('confirmPhoneOrder ✔  callSid=%s  result=%s',
      callSid, JSON.stringify(resp.data).slice(0, 120));
    res.json(resp.data);
  } catch (err) {
    ERR('confirmPhoneOrder threw  callSid=%s:', req.params.callSid, err.message);
    if (err.response) return res.status(err.response.status).json(err.response.data);
    next(err);
  }
};
