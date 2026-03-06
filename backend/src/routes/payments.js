const express = require('express');
const router = express.Router();
const pc = require('../controllers/paymentsController');

router.post('/razorpay-order', pc.createRazorpayOrder);
router.post('/verify', pc.verify);

module.exports = router;
