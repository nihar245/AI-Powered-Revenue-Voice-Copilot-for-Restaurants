const express = require('express');
const router = express.Router();
const menuController = require('../controllers/menuController');

router.get('/items', menuController.getItems);
router.get('/variants/:item_id', menuController.getVariants);
router.get('/addons/:item_id', menuController.getAddons);
router.get('/combos', menuController.getCombos);

module.exports = router;
