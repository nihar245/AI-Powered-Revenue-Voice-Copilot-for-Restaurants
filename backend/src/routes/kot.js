const express = require('express');
const router = express.Router();
const kc = require('../controllers/kotController');

router.get('/pending', kc.pending);
router.put('/:id/status', kc.updateKotStatus);

module.exports = router;
