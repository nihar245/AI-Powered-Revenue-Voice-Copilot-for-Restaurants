const express = require('express');
const router = express.Router();
const dashboardController = require('../controllers/dashboardController');

router.get('/kpis', dashboardController.kpis);
router.get('/hourly-orders', dashboardController.hourlyOrders);
router.get('/top-items', dashboardController.topItems);
router.get('/weekly-revenue', dashboardController.weeklyRevenue);

module.exports = router;
