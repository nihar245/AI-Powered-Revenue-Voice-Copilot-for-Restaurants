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

module.exports = router;
