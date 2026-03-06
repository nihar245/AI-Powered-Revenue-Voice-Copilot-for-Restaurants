const router = require('express').Router();
const auth   = require('../middleware/auth');
const { getSuggestions } = require('../controllers/combosController');

router.get('/suggestions', auth, getSuggestions);

module.exports = router;
