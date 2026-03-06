/**
 * aiService.js — Proxy helper for the ai_service_gemini FastAPI server (port 8002).
 * Replaces the old mlService calls that targeted port 8000.
 */
const axios = require('axios');
const FormData = require('form-data');

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
  const form = new FormData();
  form.append('audio', audioBuffer, {
    filename: 'audio.webm',
    contentType: mimeType || 'audio/webm',
  });
  form.append('session_id', sessionId);
  form.append('language', language);
  form.append('table_id', tableId);

  const resp = await axios.post(`${AI_URL}/test/voice-chat`, form, {
    headers: form.getHeaders(),
    timeout: TIMEOUT,
  });
  return resp.data;
}

/**
 * Add a single item by product_id (upsell chip click).
 * POST /test/add-item
 */
async function addItem({ sessionId, productId, itemName, quantity = 1 }) {
  const form = new FormData();
  form.append('session_id', sessionId);
  form.append('product_id', String(productId));
  form.append('item_name', itemName);
  form.append('quantity', String(quantity));

  const resp = await axios.post(`${AI_URL}/test/add-item`, form, {
    headers: form.getHeaders(),
    timeout: TIMEOUT,
  });
  return resp.data;
}

/**
 * Button-based order confirmation.
 * POST /test/confirm-order
 */
async function confirmOrder({ sessionId }) {
  const form = new FormData();
  form.append('session_id', sessionId);

  const resp = await axios.post(`${AI_URL}/test/confirm-order`, form, {
    headers: form.getHeaders(),
    timeout: TIMEOUT,
  });
  return resp.data;
}

/**
 * Fetch current menu from ai_service_gemini.
 * GET /test/menu
 */
async function getMenu() {
  const resp = await axios.get(`${AI_URL}/test/menu`, { timeout: TIMEOUT });
  return resp.data;
}

// ── Generic HTTP helpers (used by voiceController for transcribe/intent/speak) ──
// These proxy to ai_service on port 8001 (Deepgram STT + Groq LLM + Deepgram TTS)
const VOICE_URL = process.env.VOICE_SERVICE_URL || 'http://127.0.0.1:8001';
const _voiceHttp = axios.create({ baseURL: VOICE_URL, timeout: TIMEOUT });

async function post(path, data, config = {}) {
  return _voiceHttp.post(path, data, config);
}

async function get(path, config = {}) {
  return _voiceHttp.get(path, config);
}

module.exports = { voiceChat, addItem, confirmOrder, getMenu, post, get };
