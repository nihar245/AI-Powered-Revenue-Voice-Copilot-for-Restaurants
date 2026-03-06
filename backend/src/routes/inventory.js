const express = require('express');
const router = express.Router();
const ic = require('../controllers/inventoryController');

router.get('/performance-signals', ic.performanceSignals);
router.get('/alerts', ic.alerts);
router.get('/log', ic.log);
router.get('/stock', ic.stock);
router.get('/availability', ic.availability);
router.post('/restock', ic.restock);
router.post('/adjust', ic.adjust);
router.post('/ingredients', ic.addIngredient);
router.put('/ingredients/:id', ic.updateIngredient);

module.exports = router;
