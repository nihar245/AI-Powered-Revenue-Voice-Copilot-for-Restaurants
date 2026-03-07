const express = require('express');
const multer  = require('multer');
const router  = express.Router();
const vc   = require('../controllers/voiceController');
const auth = require('../middleware/auth');

// Upload audio in memory (no disk writes) — 10 MB limit
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });

// Deprecated — STT & intent are now handled internally by Gemini Live
router.post('/transcribe', vc.transcribe);
router.post('/intent',     vc.intent);

// Primary voice turn: multipart/form-data { audio (file), session_id, language?, table_id? }
router.post('/process-turn', upload.single('audio'), vc.processTurn);

// Upsell chip / quick-add: JSON { session_id, product_id, item_name, quantity? }
router.post('/add-item', vc.addItem);

// Button-based confirm: JSON { session_id }  (requires auth)
router.post('/confirm-order', auth, vc.confirmOrder);

// Session state passthrough
router.get('/session/:session_id', vc.getSession);

// Menu reference — proxies to ai_service_gemini /test/menu
router.get('/menu', vc.getMenu);

// Phone call logs — proxies to ai_service_gemini GET /twilio/call-logs
router.get('/call-logs', vc.getCallLogs);

// Active phone call state — proxies to ai_service_gemini GET /twilio/active-call
router.get('/active-call', vc.getActiveCall);

// Confirm phone order from dashboard — proxies to ai_service_gemini POST /twilio/confirm-phone-order/:callSid
// No auth guard — the Twilio call SID acts as the access token for this internal dashboard action.
router.post('/confirm-phone-order/:callSid', vc.confirmPhoneOrder);

module.exports = router;
