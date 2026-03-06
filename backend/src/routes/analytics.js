const express = require('express');
const router = express.Router();
const ac = require('../controllers/analyticsController');

router.get('/menu-profitability', ac.menuProfitability);
router.get('/combo-recommendations', ac.comboRecommendations);
router.get('/underperforming-items', ac.underperformingItems);
router.get('/popularity-scoring', ac.popularityScoring);
router.get('/hidden-stars', ac.hiddenStars);
router.get('/risk-detection', ac.riskDetection);
router.get('/menu-optimization', ac.menuOptimization);

module.exports = router;
