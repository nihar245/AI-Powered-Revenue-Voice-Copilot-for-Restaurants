const aiService = require('../services/aiService');
const axios = require('axios');

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
      return res.status(400).json({ error: 'Audio file is required (field: audio)' });
    }

    const sessionId = req.body.session_id;
    if (!sessionId) {
      return res.status(400).json({ error: 'session_id is required' });
    }

    const result = await aiService.voiceChat({
      audioBuffer: req.file.buffer,
      mimeType:    req.file.mimetype || 'audio/webm',
      sessionId,
      language:  req.body.language || 'en',
      tableId:   req.body.table_id || '',
    });

    res.json(result);
  } catch (err) {
    next(err);
  }
};

// ---- Add Item: upsell chip / quick-add -> proxy to /test/add-item ------------------
// Expects JSON: { session_id, product_id, item_name, quantity }
exports.addItem = async (req, res, next) => {
  try {
    const { session_id, product_id, item_name, quantity } = req.body;
    if (!session_id || !product_id || !item_name) {
      return res.status(400).json({ error: 'session_id, product_id, item_name are required' });
    }

    const result = await aiService.addItem({
      sessionId:  session_id,
      productId:  product_id,
      itemName:   item_name,
      quantity:   quantity || 1,
    });

    res.json(result);
  } catch (err) {
    next(err);
  }
};

// ---- Confirm Order: button-based confirm -> proxy to /test/confirm-order ------------
// Expects JSON: { session_id }  (auth middleware populates req.user)
exports.confirmOrder = async (req, res, next) => {
  try {
    const { session_id } = req.body;
    if (!session_id) {
      return res.status(400).json({ error: 'session_id is required' });
    }

    const result = await aiService.confirmOrder({ sessionId: session_id });
    res.status(201).json(result);
  } catch (err) {
    next(err);
  }
};

// ---- Get Session state -> proxy to ai_service_gemini /test/session/:id -------------
exports.getSession = async (req, res, next) => {
  try {
    const resp = await axios.get(
      `${AI_URL}/test/session/${req.params.session_id}`,
      { timeout: 10000 }
    );
    res.json(resp.data);
  } catch (err) {
    if (err.response && err.response.status === 404) {
      return res.status(404).json({ error: 'Session not found' });
    }
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
