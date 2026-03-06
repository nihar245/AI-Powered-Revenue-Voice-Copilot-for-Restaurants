require('dotenv').config();

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');

const authRoutes = require('./routes/auth');
const menuRoutes = require('./routes/menu');
const orderRoutes = require('./routes/orders');
const dashboardRoutes = require('./routes/dashboard');
const revenueRoutes = require('./routes/revenue');
const analyticsRoutes = require('./routes/analytics');
const inventoryRoutes = require('./routes/inventory');
const customerRoutes = require('./routes/customers');
const voiceRoutes = require('./routes/voice');
const kotRoutes = require('./routes/kot');
const productsRoutes = require('./routes/products');
const reportsRoutes  = require('./routes/reports');
const paymentsRoutes = require('./routes/payments');

const app = express();

// --------------- Middleware ---------------
app.use(helmet());
// Allow local frontend dev servers on any localhost port (5173, 5174, etc.)
app.use(cors({
  origin: (origin, callback) => {
    if (!origin || /^http:\/\/localhost(:\d+)?$/.test(origin)) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  optionsSuccessStatus: 200,
}));
app.use(express.json({ limit: '10mb' }));

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 min
  max: 500,
  standardHeaders: true,
  legacyHeaders: false,
});
app.use(limiter);

// --------------- Routes ---------------
app.use('/api/auth', authRoutes);
app.use('/api/menu', menuRoutes);
app.use('/api/orders', orderRoutes);
app.use('/api/dashboard', dashboardRoutes);
app.use('/api/revenue', revenueRoutes);
app.use('/api/analytics', analyticsRoutes);
app.use('/api/inventory', inventoryRoutes);
app.use('/api/customers', customerRoutes);
app.use('/api/voice', voiceRoutes);
app.use('/api/kot', kotRoutes);
app.use('/api/products', productsRoutes);
app.use('/api/reports',  reportsRoutes);
app.use('/api/payments', paymentsRoutes);

// Health check
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// --------------- Error handler ---------------
app.use((err, _req, res, _next) => {
  console.error(err.stack || err);
  res.status(err.status || 500).json({
    error: err.message || 'Internal server error',
  });
});
// --------------- Auto-migrate on startup ---------------
const db = require('./config/db');

async function migrate() {
  try {
    // Create restaurants table first (required by users FK)
    await db.query(`
      CREATE TABLE IF NOT EXISTS restaurants (
        restaurant_id    SERIAL PRIMARY KEY,
        name             VARCHAR(100) NOT NULL,
        address          TEXT,
        city             VARCHAR(60),
        cuisine_type     VARCHAR(60),
        gstin            VARCHAR(20),
        fssai_no         VARCHAR(20),
        opening_time     TIME,
        closing_time     TIME,
        seating_capacity INT DEFAULT 0
      )
    `);

    await db.query(`
      CREATE TABLE IF NOT EXISTS users (
        user_id       SERIAL PRIMARY KEY,
        name          VARCHAR(100) NOT NULL,
        email         VARCHAR(150) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        restaurant_id INT REFERENCES restaurants(restaurant_id),
        created_at    TIMESTAMPTZ DEFAULT NOW()
      )
    `);
    // Add is_upsell column to order_items if it doesn't exist (schema patch)
    await db.query(`
      ALTER TABLE order_items ADD COLUMN IF NOT EXISTS is_upsell BOOLEAN DEFAULT FALSE
    `);

    // Create upsell_events table if it doesn't exist
    await db.query(`
      CREATE TABLE IF NOT EXISTS upsell_events (
        event_id          SERIAL PRIMARY KEY,
        order_id          INT REFERENCES orders(order_id),
        item_id           INT REFERENCES menu_items(item_id),
        variant_id        INT REFERENCES menu_variants(variant_id),
        trigger_item_name VARCHAR(150),
        revenue           NUMERIC(10,2),
        created_at        TIMESTAMPTZ DEFAULT NOW()
      )
    `);
    console.log('Migration check complete');
  } catch (err) {
    console.error('Migration failed:', err.message);
  }
}

// --------------- Start ---------------
const PORT = process.env.NODE_PORT || 3000;

migrate().then(() => {
  app.listen(PORT, () => {
    console.log(`PetPooja backend running on http://localhost:${PORT}`);
  });
});

module.exports = app;
