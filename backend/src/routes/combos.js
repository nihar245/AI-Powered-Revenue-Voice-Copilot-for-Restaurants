const express = require('express');
const router = express.Router();
const cc = require('../controllers/combosController');

router.get('/', cc.list);
router.get('/:id', cc.get);
router.post('/', cc.create);
router.put('/:id', cc.update);
router.delete('/:id', cc.remove);

module.exports = router;
