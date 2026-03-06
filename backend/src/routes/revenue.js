const express = require('express');
const router = express.Router();
const rc = require('../controllers/revenueController');

router.get('/contribution-margin', rc.contributionMargin);
router.get('/menu-engineering', rc.menuEngineering);
router.get('/top-combos', rc.topCombos);
router.get('/aov', rc.aov);
router.get('/price-recommendations', rc.priceRecommendations);
router.get('/anomalies', rc.anomalies);
router.get('/demand-forecast', rc.demandForecast);
router.get('/upsell-recommendations', rc.upsellRecommendations);
router.get('/upsell-stats', rc.upsellStats);

module.exports = router;
