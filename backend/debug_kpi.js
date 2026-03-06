const { Pool } = require('pg');
const p = new Pool({ host: 'localhost', port: 5432, database: 'postgres', user: 'postgres', password: 'postgres' });

(async () => {
  try {
    // 1. DB timezone
    const tz = await p.query('SHOW timezone');
    console.log('DB timezone:', tz.rows[0].TimeZone);

    // 2. Total orders
    const total = await p.query('SELECT count(*)::int as total FROM orders');
    console.log('Total orders:', total.rows[0].total);

    // 3. Orders on 2024-06-15 specifically
    const june15 = await p.query("SELECT count(*)::int as cnt FROM orders WHERE placed_at::date = '2024-06-15'");
    console.log('Orders on 2024-06-15:', june15.rows[0].cnt);

    // 4. Top 10 busiest dates
    const top = await p.query('SELECT placed_at::date as d, count(*)::int as cnt FROM orders GROUP BY placed_at::date ORDER BY cnt DESC LIMIT 10');
    console.log('\nTop 10 busiest dates:');
    top.rows.forEach(r => console.log(' ', r.d, '->', r.cnt, 'orders'));

    // 5. Last 5 orders placed_at
    const last = await p.query('SELECT order_id, placed_at, total, status FROM orders ORDER BY order_id DESC LIMIT 5');
    console.log('\nLast 5 orders:');
    last.rows.forEach(r => console.log(' ', r.order_id, r.placed_at, 'total:', r.total, 'status:', r.status));

    // 6. What the KPI endpoint would return for date=2024-06-15
    const kpiQuery = await p.query(`
      SELECT
        COUNT(*)::int AS "totalOrdersToday",
        COALESCE(SUM(total), 0)::float AS "totalRevenue",
        COALESCE(ROUND(AVG(total), 0), 0)::float AS "avgOrderValue"
      FROM orders
      WHERE placed_at::date = '2024-06-15' AND status != 'cancelled'
    `);
    console.log('\nKPI for 2024-06-15:', JSON.stringify(kpiQuery.rows[0]));

    // 7. What date range actually has data?
    const range = await p.query('SELECT MIN(placed_at)::date as min_date, MAX(placed_at)::date as max_date FROM orders');
    console.log('\nDate range of all orders:', range.rows[0].min_date, 'to', range.rows[0].max_date);

    // 8. Check if the placed_at CASE WHEN works
    const testInsertCheck = await p.query("SELECT ('2024-06-15'::date + (NOW()::time))::timestamptz as test_ts");
    console.log('CASE WHEN test timestamp:', testInsertCheck.rows[0].test_ts);
    console.log('  -> date part:', testInsertCheck.rows[0].test_ts.toISOString().slice(0, 10));

  } catch (e) {
    console.error('ERROR:', e.message);
  } finally {
    p.end();
  }
})();
