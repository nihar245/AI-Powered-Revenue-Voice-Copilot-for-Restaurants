const express = require('express');
const router = express.Router();
const vc = require('../controllers/voiceController');
const auth = require('../middleware/auth');

router.post('/transcribe', vc.transcribe);
router.post('/intent', vc.intent);
router.post('/speak', vc.speak);
router.post('/confirm-order', auth, vc.confirmOrder);
router.get('/ai-health', vc.aiHealth);

module.exports = router;
