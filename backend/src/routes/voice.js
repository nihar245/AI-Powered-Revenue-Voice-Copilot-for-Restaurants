const express = require('express');
const router = express.Router();
const vc = require('../controllers/voiceController');
const auth = require('../middleware/auth');

router.post('/transcribe', vc.transcribe);
router.post('/intent', vc.intent);
router.post('/process-turn', vc.processTurn);
router.post('/confirm-order', auth, vc.confirmOrder);
router.get('/session/:session_id', vc.getSession);

module.exports = router;
