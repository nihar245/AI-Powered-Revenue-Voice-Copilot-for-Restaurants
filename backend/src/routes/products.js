const express = require('express');
const router = express.Router();
const pc = require('../controllers/productsController');

router.get('/', pc.list);
router.get('/categories', pc.categories);
router.get('/ingredients', pc.ingredients);
router.get('/:id', pc.get);
router.post('/', pc.create);
router.put('/:id', pc.update);
router.delete('/:id', pc.remove);

module.exports = router;
