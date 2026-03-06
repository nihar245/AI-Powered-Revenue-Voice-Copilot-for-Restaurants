const express = require('express');
const router = express.Router();
const orderController = require('../controllers/orderController');
const auth = require('../middleware/auth');

router.get('/', orderController.list);
router.get('/today', orderController.today);
router.post('/', auth, orderController.create);
router.put('/:id/status', auth, orderController.updateStatus);

module.exports = router;
