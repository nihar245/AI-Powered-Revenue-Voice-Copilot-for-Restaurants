const express = require('express');
const router = express.Router();
const multer = require('multer');
const vc = require('../controllers/voiceController');
const auth = require('../middleware/auth');

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });

// Gemini voice pipeline
router.post('/turn', upload.single('audio'), vc.voiceTurn);
router.post('/chat', vc.voiceChat);
router.post('/add-item', vc.addItem);
router.post('/reset', vc.resetSession);
router.get('/health', vc.health);

// DB order creation (fallback / explicit confirm)
router.post('/confirm-order', auth, vc.confirmOrder);

module.exports = router;
