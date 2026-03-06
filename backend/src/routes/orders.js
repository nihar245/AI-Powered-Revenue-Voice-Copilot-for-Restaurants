const express = require('express');
const router = express.Router();
const orderController = require('../controllers/orderController');
const auth = require('../middleware/auth');

router.get('/', orderController.list);
router.get('/today', orderController.today);
router.post('/', auth, orderController.create);
router.put('/:id/status', auth, orderController.updateStatus);
router.put('/:id/cancel', auth, orderController.cancelById);
router.put('/:id/items', auth, orderController.updateItems);   // edit order items
router.delete('/:id', auth, orderController.deleteOrder);       // hard-delete (admin)
router.get('/by-phone/:phone', orderController.lookupByPhone);

module.exports = router;
