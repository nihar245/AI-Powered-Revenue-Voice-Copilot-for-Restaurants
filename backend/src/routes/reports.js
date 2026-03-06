const express = require('express');
const router  = express.Router();
const rc      = require('../controllers/reportsController');

router.get('/summary', rc.summary);

module.exports = router;
