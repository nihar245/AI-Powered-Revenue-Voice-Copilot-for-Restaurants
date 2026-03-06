const express = require('express');
const router = express.Router();
const cc = require('../controllers/customerController');

router.post('/', cc.create);
router.post('/recalculate-segments', cc.recalculateSegments);
router.get('/search', cc.search);
router.get('/list', cc.list);
router.get('/churn-risk', cc.churnRisk);
router.get('/segments', cc.segments);
router.get('/:id', cc.getById);

module.exports = router;
