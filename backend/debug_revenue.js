// Quick diagnostic — run: node debug_revenue.js
require('dotenv').config();
const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT, 10) || 5432,
  database: process.env.DB_NAME || 'postgres',
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
});

async function run() {
  console.log('\n====== DB CONNECTION ======');
  const connTest = await pool.query('SELECT current_database(), current_schema()');
  console.log('Connected to:', connTest.rows[0]);

  console.log('\n====== TABLE ROW COUNTS ======');
  const tables = ['restaurants','menu_categories','menu_items','menu_variants',
                  'customers','orders','order_items','order_payments','kot','kot_items',
                  'ingredients','inventory_log','order_addons','feedback'];
  for (const t of tables) {
    try {
      const r = await pool.query(`SELECT COUNT(*)::int AS cnt FROM ${t}`);
      console.log(`  ${t.padEnd(20)} => ${r.rows[0].cnt} rows`);
    } catch (e) {
      console.log(`  ${t.padEnd(20)} => ERROR: ${e.message}`);
    }
  }

  console.log('\n====== ORDERS SAMPLE ======');
  const orders = await pool.query('SELECT order_id, channel, status, total, placed_at FROM orders ORDER BY order_id LIMIT 5');
  console.table(orders.rows);

  console.log('\n====== ORDER_ITEMS SAMPLE ======');
  const items = await pool.query('SELECT line_id, order_id, item_id, variant_id, qty, unit_price, revenue, food_cost FROM order_items ORDER BY line_id LIMIT 5');
  console.table(items.rows);

  console.log('\n====== CONTRIBUTION MARGIN QUERY (first 3) ======');
  try {
    const cm = await pool.query(`
      SELECT
        mi.item_id,
        mi.name AS item_name,
        mv.variant_id,
        mv.variant_name,
        mv.selling_price::float,
        mv.food_cost::float,
        (mv.selling_price - mv.food_cost)::float AS margin,
        CASE WHEN mv.selling_price > 0
          THEN ROUND((mv.selling_price - mv.food_cost) / mv.selling_price * 100, 1)
          ELSE 0
        END::float AS margin_pct,
        COALESCE(s.qty_sold, 0)::int AS qty_sold,
        COALESCE(s.total_revenue, 0)::float AS total_revenue
      FROM menu_items mi
      JOIN menu_variants mv USING (item_id)
      LEFT JOIN (
        SELECT item_id, variant_id,
               SUM(qty) AS qty_sold,
               SUM(revenue) AS total_revenue
        FROM order_items GROUP BY item_id, variant_id
      ) s ON mv.item_id = s.item_id AND mv.variant_id = s.variant_id
      ORDER BY margin DESC
      LIMIT 3
    `);
    console.table(cm.rows);
  } catch (e) {
    console.log('CM QUERY ERROR:', e.message);
  }

  console.log('\n====== AOV BY CHANNEL ======');
  try {
    const aov = await pool.query(`
      SELECT channel, ROUND(AVG(total), 2)::float AS avg_order_value, COUNT(*)::int AS order_count
      FROM orders WHERE status != 'cancelled'
      GROUP BY channel ORDER BY avg_order_value DESC
    `);
    console.table(aov.rows);
  } catch (e) {
    console.log('AOV QUERY ERROR:', e.message);
  }

  console.log('\n====== ANOMALIES (z-score, first 3) ======');
  try {
    const an = await pool.query(`
      WITH daily AS (
        SELECT placed_at::date AS day, COUNT(*)::float AS order_count,
               SUM(total)::float AS revenue, AVG(total)::float AS avg_order_val
        FROM orders WHERE status != 'cancelled'
        GROUP BY placed_at::date
      ),
      stats AS (SELECT AVG(revenue) AS mean_rev, STDDEV(revenue) AS std_rev FROM daily)
      SELECT d.day, d.order_count, d.revenue,
             CASE WHEN s.std_rev > 0 THEN ROUND(ABS(d.revenue - s.mean_rev) / s.std_rev, 2) ELSE 0 END::float AS z_score,
             CASE WHEN s.std_rev > 0 AND ABS(d.revenue - s.mean_rev) / s.std_rev > 2 THEN TRUE ELSE FALSE END AS is_anomaly
      FROM daily d, stats s ORDER BY d.day DESC LIMIT 3
    `);
    console.table(an.rows);
  } catch (e) {
    console.log('ANOMALIES QUERY ERROR:', e.message);
  }

  // Now test the actual HTTP endpoints if server is running
  console.log('\n====== HTTP ENDPOINT TESTS (localhost:3000) ======');
  const http = require('http');
  const endpoints = [
    '/api/revenue/contribution-margin',
    '/api/revenue/price-recommendations',
    '/api/revenue/aov',
    '/api/revenue/anomalies',
    '/api/revenue/demand-forecast',
    '/api/revenue/upsell-recommendations',
  ];

  for (const ep of endpoints) {
    try {
      const data = await new Promise((resolve, reject) => {
        const req = http.get(`http://localhost:3000${ep}`, { timeout: 5000 }, (res) => {
          let body = '';
          res.on('data', chunk => body += chunk);
          res.on('end', () => {
            try {
              const json = JSON.parse(body);
              resolve({ status: res.statusCode, type: typeof json, length: Array.isArray(json) ? json.length : (json.data ? json.data.length : Object.keys(json).length) });
            } catch { resolve({ status: res.statusCode, body: body.slice(0, 200) }); }
          });
        });
        req.on('error', (e) => reject(e));
        req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
      });
      console.log(`  ${ep.padEnd(45)} => status=${data.status} items=${data.length || data.body}`);
    } catch (e) {
      console.log(`  ${ep.padEnd(45)} => FAIL: ${e.message}`);
    }
  }

  await pool.end();
  console.log('\n====== DONE ======');
}

run().catch(e => { console.error(e); process.exit(1); });
