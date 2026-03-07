/**
 * aiService.js — Proxy helper for the ai_service_gemini FastAPI server (port 8002).
 * Replaces the old mlService calls that targeted port 8000.
 */
const axios = require('axios');
const FormData = require('form-data');

const LOG = (...args) => console.log('[AI_SERVICE]', new Date().toISOString(), ...args);
const ERR = (...args) => console.error('[AI_SERVICE][ERROR]', new Date().toISOString(), ...args);

const AI_URL = process.env.AI_SERVICE_URL || 'http://127.0.0.1:8002';
const TIMEOUT = 40000; // 40 s — Live audio can take up to ~15 s

/**
 * Forward one voice turn to POST /test/voice-chat.
 * @param {object} opts
 * @param {Buffer}  opts.audioBuffer  — raw audio bytes from multer
 * @param {string}  opts.mimeType     — e.g. "audio/webm;codecs=opus"
 * @param {string}  opts.sessionId
 * @param {string}  [opts.language]
 * @param {string}  [opts.tableId]
 */
async function voiceChat({ audioBuffer, mimeType, sessionId, language = 'en', tableId = '' }) {
  LOG('voiceChat → POST %s/test/voice-chat  session=%s  size=%d  lang=%s',
    AI_URL, sessionId, audioBuffer?.length, language);
  const form = new FormData();
  form.append('audio', audioBuffer, {
    filename: 'audio.webm',
    contentType: mimeType || 'audio/webm',
  });
  form.append('session_id', sessionId);
  form.append('language', language);
  form.append('table_id', tableId);

  try {
    const resp = await axios.post(`${AI_URL}/test/voice-chat`, form, {
      headers: form.getHeaders(),
      timeout: TIMEOUT,
    });
    LOG('voiceChat ✔  session=%s  status=%d  intent=%s', sessionId, resp.status, resp.data?.intent);
    return resp.data;
  } catch (err) {
    ERR('voiceChat failed  session=%s  url=%s/test/voice-chat:', sessionId, AI_URL, err.message);
    throw err;
  }
}

/**
 * Add a single item by product_id (upsell chip click).
 * POST /test/add-item
 */
async function addItem({ sessionId, productId, itemName, quantity = 1 }) {
  LOG('addItem → POST %s/test/add-item  session=%s  product_id=%s  qty=%d',
    AI_URL, sessionId, productId, quantity);
  const form = new FormData();
  form.append('session_id', sessionId);
  form.append('product_id', String(productId));
  form.append('item_name', itemName);
  form.append('quantity', String(quantity));

  try {
    const resp = await axios.post(`${AI_URL}/test/add-item`, form, {
      headers: form.getHeaders(),
      timeout: TIMEOUT,
    });
    LOG('addItem ✔  session=%s  status=%d', sessionId, resp.status);
    return resp.data;
  } catch (err) {
    ERR('addItem failed  session=%s:', sessionId, err.message);
    throw err;
  }
}

/**
 * Button-based order confirmation.
 * POST /test/confirm-order
 */
async function confirmOrder({ sessionId }) {
  LOG('confirmOrder → POST %s/test/confirm-order  session=%s', AI_URL, sessionId);
  const form = new FormData();
  form.append('session_id', sessionId);

  try {
    const resp = await axios.post(`${AI_URL}/test/confirm-order`, form, {
      headers: form.getHeaders(),
      timeout: TIMEOUT,
    });
    LOG('confirmOrder ✔  session=%s  status=%d  data=%s',
      sessionId, resp.status, JSON.stringify(resp.data).slice(0, 200));
    return resp.data;
  } catch (err) {
    ERR('confirmOrder failed  session=%s  url=%s/test/confirm-order  error=%s',
      sessionId, AI_URL, err.message);
    if (err.response) {
      ERR('confirmOrder HTTP %d response body: %s',
        err.response.status, JSON.stringify(err.response.data).slice(0, 300));
    }
    throw err;
  }
}

/**
 * Fetch current menu from ai_service_gemini.
 * GET /test/menu
 */
async function getMenu() {
  LOG('getMenu → GET %s/test/menu', AI_URL);
  try {
    const resp = await axios.get(`${AI_URL}/test/menu`, { timeout: TIMEOUT });
    LOG('getMenu ✔  items=%d', resp.data?.length);
    return resp.data;
  } catch (err) {
    ERR('getMenu failed:', err.message);
    throw err;
  }
}

module.exports = { voiceChat, addItem, confirmOrder, getMenu };
