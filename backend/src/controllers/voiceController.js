const aiService = require('../services/aiService');
const axios = require('axios');

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

// ---- Confirm Order: button-based confirm -> proxy to /test/confirm-order ------------
// Expects JSON: { session_id }  (auth middleware populates req.user)
exports.confirmOrder = async (req, res, next) => {
  try {
    const { session_id } = req.body;
    LOG('confirmOrder called  session_id=%s', session_id);
    if (!session_id) {
      ERR('confirmOrder — missing session_id');
      return res.status(400).json({ error: 'session_id is required' });
    }

    LOG('confirmOrder → forwarding to aiService  session_id=%s', session_id);
    const result = await aiService.confirmOrder({ sessionId: session_id });
    LOG('confirmOrder ✔  session_id=%s  result=%s',
      session_id, JSON.stringify(result).slice(0, 200));
    res.status(201).json(result);
  } catch (err) {
    ERR('confirmOrder threw — session_id=%s:', req.body?.session_id, err.message);
    next(err);
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
