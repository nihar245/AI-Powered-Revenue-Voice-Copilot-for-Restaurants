const router  = require('express').Router();
const auth    = require('../middleware/auth');
const ctrl    = require('../controllers/ingredientsController');

// List all ingredients with unit costs
router.get('/',                        auth, ctrl.getIngredients);

// All variants: computed food costs + margin
router.get('/food-costs',              auth, ctrl.getFoodCosts);

// Recipe breakdown (ingredient list) for one variant
router.get('/recipe/:variantId',       auth, ctrl.getRecipe);

// Update unit cost for one ingredient (triggers DB recompute)
router.put('/:id/cost',                auth, ctrl.updateCost);

// Upsert one ingredient line in a variant's recipe
router.put('/recipe/:variantId',       auth, ctrl.upsertRecipeLine);

// Remove one ingredient line from a variant's recipe
router.delete('/recipe/:variantId/:ingId', auth, ctrl.deleteRecipeLine);

module.exports = router;
