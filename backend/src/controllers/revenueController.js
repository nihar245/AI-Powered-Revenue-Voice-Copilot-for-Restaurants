const db = require('../config/db');
const mlService = require('../services/mlService');

// ──── Period filter helper ───────────────────────────────────────────────────
function parsePeriod(req) {
  const VALID = { '7d': '7 days', '30d': '30 days', '90d': '90 days', all: null };
  const p = req?.query?.period;
  return Object.prototype.hasOwnProperty.call(VALID, p) ? VALID[p] : null;
}

// ──── Contribution Margin ────────────────────────────────────────────────────
exports.contributionMargin = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pf = interval ? `AND oi.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const { rows } = await db.query(`
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
        FROM order_items oi WHERE 1=1 ${pf} GROUP BY item_id, variant_id
      ) s ON mv.item_id = s.item_id AND mv.variant_id = s.variant_id
      ORDER BY margin DESC
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// ──── Menu Engineering Matrix ────────────────────────────────────────────────
// dynamic median split: Star / Puzzle / Plowhorse / Dog
exports.menuEngineering = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pf = interval ? `AND oi.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const { rows: items } = await db.query(`
      WITH item_perf AS (
        SELECT
          mi.item_id,
          mi.name,
          mc.name AS category,
          SUM(oi.qty)::float AS sales_velocity,
          AVG(mv.selling_price - mv.food_cost)::float AS cm_per_unit,
          SUM(oi.revenue)::float AS total_revenue
        FROM order_items oi
        JOIN menu_items mi ON oi.item_id = mi.item_id
        JOIN menu_categories mc ON mi.category_id = mc.category_id
        JOIN menu_variants mv ON oi.variant_id = mv.variant_id
        WHERE 1=1 ${pf}
        GROUP BY mi.item_id, mi.name, mc.name
      )
      SELECT * FROM item_perf
      ORDER BY total_revenue DESC
    `);

    if (items.length === 0) return res.json([]);

    // Compute medians dynamically
    const sorted_sv = items.map(i => i.sales_velocity).sort((a, b) => a - b);
    const sorted_cm = items.map(i => i.cm_per_unit).sort((a, b) => a - b);
    const median = arr => {
      const mid = Math.floor(arr.length / 2);
      return arr.length % 2 !== 0 ? arr[mid] : (arr[mid - 1] + arr[mid]) / 2;
    };
    const medSV = median(sorted_sv);
    const medCM = median(sorted_cm);

    const classified = items.map(i => {
      let classification;
      if (i.sales_velocity >= medSV && i.cm_per_unit >= medCM) classification = 'Star';
      else if (i.sales_velocity < medSV && i.cm_per_unit >= medCM) classification = 'Puzzle';
      else if (i.sales_velocity >= medSV && i.cm_per_unit < medCM) classification = 'Plowhorse';
      else classification = 'Dog';
      return { ...i, classification };
    });

    res.json({ items: classified, medians: { sales_velocity: medSV, cm_per_unit: medCM } });
  } catch (err) {
    next(err);
  }
};

// ──── Top Combos (co-occurrence analysis) ────────────────────────────────────
exports.topCombos = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pfA  = interval ? `AND a.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const pfOi = interval ? `AND order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const { rows } = await db.query(`
      WITH pairs AS (
        SELECT
          a.item_id AS item_a,
          b.item_id AS item_b
        FROM order_items a
        JOIN order_items b ON a.order_id = b.order_id AND a.item_id < b.item_id
        WHERE 1=1 ${pfA}
      ),
      pair_counts AS (
        SELECT item_a, item_b, COUNT(*) AS pair_count
        FROM pairs GROUP BY item_a, item_b
      ),
      item_totals AS (
        SELECT item_id, COUNT(DISTINCT order_id) AS total
        FROM order_items WHERE 1=1 ${pfOi} GROUP BY item_id
      ),
      total_orders AS (
        SELECT COUNT(DISTINCT order_id)::float AS n FROM order_items WHERE 1=1 ${pfOi}
      )
      SELECT
        ma.name AS "itemA",
        mb.name AS "itemB",
        pc.pair_count,
        ROUND(pc.pair_count * 100.0 / ta.total, 1)::float AS confidence,
        ROUND(
          ((pc.pair_count::float / ta.total) /
          (tb.total::float / (SELECT n FROM total_orders)))::numeric,
          2
        )::float AS lift
      FROM pair_counts pc
      JOIN menu_items ma ON pc.item_a = ma.item_id
      JOIN menu_items mb ON pc.item_b = mb.item_id
      JOIN item_totals ta ON pc.item_a = ta.item_id
      JOIN item_totals tb ON pc.item_b = tb.item_id
      ORDER BY lift DESC, pair_count DESC
      LIMIT 20
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// ──── AOV (Average Order Value) ──────────────────────────────────────────────
exports.aov = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pf  = interval ? `AND placed_at >= NOW() - INTERVAL '${interval}'` : '';
    const pfO = interval ? `AND o.placed_at >= NOW() - INTERVAL '${interval}'` : '';
    const byChannel = await db.query(`
      SELECT channel, ROUND(AVG(total), 2)::float AS avg_order_value, COUNT(*)::int AS order_count
      FROM orders WHERE status != 'cancelled' ${pf}
      GROUP BY channel ORDER BY avg_order_value DESC
    `);
    const byDayOfWeek = await db.query(`
      SELECT TO_CHAR(placed_at, 'Dy') AS day,
             EXTRACT(DOW FROM placed_at)::int AS dow,
             ROUND(AVG(total), 2)::float AS avg_order_value
      FROM orders WHERE status != 'cancelled' ${pf}
      GROUP BY TO_CHAR(placed_at, 'Dy'), EXTRACT(DOW FROM placed_at)
      ORDER BY dow
    `);
    const byHour = await db.query(`
      SELECT EXTRACT(HOUR FROM placed_at)::int AS hour,
             ROUND(AVG(total), 2)::float AS avg_order_value
      FROM orders WHERE status != 'cancelled' ${pf}
      GROUP BY EXTRACT(HOUR FROM placed_at)
      ORDER BY hour
    `);
    // Payment method breakdown via order_payments join
    const byPaymentMethod = await db.query(`
      SELECT
        op.method AS payment_method,
        ROUND(AVG(o.total), 2)::float AS avg_order_value,
        COUNT(DISTINCT o.order_id)::int AS order_count,
        ROUND(SUM(o.total), 2)::float AS total_revenue
      FROM orders o
      JOIN order_payments op ON o.order_id = op.order_id
      WHERE o.status != 'cancelled' ${pfO}
      GROUP BY op.method
      ORDER BY avg_order_value DESC
    `);
    // Weekend vs weekday split
    const byWeekType = await db.query(`
      SELECT
        CASE WHEN EXTRACT(DOW FROM placed_at) IN (0,6) THEN 'Weekend' ELSE 'Weekday' END AS week_type,
        ROUND(AVG(total), 2)::float AS avg_order_value,
        COUNT(*)::int AS order_count
      FROM orders WHERE status != 'cancelled' ${pf}
      GROUP BY week_type
      ORDER BY avg_order_value DESC
    `);
    res.json({
      byChannel: byChannel.rows,
      byDayOfWeek: byDayOfWeek.rows,
      byHour: byHour.rows,
      byPaymentMethod: byPaymentMethod.rows,
      byWeekType: byWeekType.rows,
    });
  } catch (err) {
    next(err);
  }
};

// ──── Upsell Performance Stats ────────────────────────────────────────────────
exports.upsellStats = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pf   = interval ? `AND order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const pfOi = interval ? `AND oi.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const summary = await db.query(`
      SELECT
        COUNT(*)::int                          AS total_upsell_items,
        COUNT(DISTINCT order_id)::int          AS orders_with_upsell,
        COALESCE(SUM(revenue), 0)::float       AS total_upsell_revenue,
        COALESCE(AVG(revenue), 0)::float       AS avg_upsell_value
      FROM order_items
      WHERE is_upsell = TRUE ${pf}
    `);
    const topItems = await db.query(`
      SELECT
        mi.name                              AS item_name,
        COUNT(*)::int                        AS times_upsold,
        COALESCE(SUM(oi.revenue), 0)::float  AS revenue_generated
      FROM order_items oi
      JOIN menu_items mi ON oi.item_id = mi.item_id
      WHERE oi.is_upsell = TRUE ${pfOi}
      GROUP BY mi.name
      ORDER BY revenue_generated DESC
      LIMIT 10
    `);
    const recent = await db.query(`
      SELECT
        ue.event_id, ue.order_id,
        mi.name         AS item_name,
        ue.trigger_item_name,
        ue.revenue::float,
        ue.recorded_at
      FROM upsell_events ue
      JOIN menu_items mi ON ue.item_id = mi.item_id
      ORDER BY ue.recorded_at DESC
      LIMIT 20
    `);
    res.json({
      summary: summary.rows[0],
      top_items: topItems.rows,
      recent_events: recent.rows,
    });
  } catch (err) {
    next(err);
  }
};

// ──── Upsell Recommendations ──────────────────────────────────────────────────
// GET /revenue/upsell-recommendations?item_ids=1,2,3
// Returns top items frequently ordered alongside the given item(s), not in current set.
exports.upsellRecommendations = async (req, res, next) => {
  try {
    const rawIds = req.query.item_ids || '';
    const itemIds = rawIds
      .split(',')
      .map(id => parseInt(id.trim(), 10))
      .filter(id => !isNaN(id) && id > 0);

    if (itemIds.length === 0) {
      // No context — return globally popular items with consistent schema
      const { rows } = await db.query(`
        SELECT mi.item_id, mi.name, mc.name AS category,
               SUM(oi.qty)::int AS co_count,
               ROUND(AVG(mv.selling_price), 0)::int AS avg_price,
               ROUND(AVG((mv.selling_price - mv.food_cost) * 100.0 / NULLIF(mv.selling_price, 0))::numeric, 1)::float AS margin
        FROM order_items oi
        JOIN menu_items mi ON oi.item_id = mi.item_id
        LEFT JOIN menu_categories mc ON mi.category_id = mc.category_id
        LEFT JOIN menu_variants mv ON oi.variant_id = mv.variant_id
        GROUP BY mi.item_id, mi.name, mc.name
        ORDER BY co_count DESC
        LIMIT 8
      `);
      return res.json({ type: 'global_popular', items: rows });
    }

    // Find items that co-occur with any of the given item_ids, excluding them
    const placeholders = itemIds.map((_, i) => `$${i + 1}`).join(',');
    const { rows } = await db.query(`
      WITH base_orders AS (
        SELECT DISTINCT order_id
        FROM order_items
        WHERE item_id IN (${placeholders})
      ),
      co_items AS (
        SELECT oi.item_id, COUNT(*)::int AS co_count
        FROM order_items oi
        JOIN base_orders bo ON oi.order_id = bo.order_id
        WHERE oi.item_id NOT IN (${placeholders})
        GROUP BY oi.item_id
      )
      SELECT
        mi.item_id,
        mi.name,
        mc.name AS category,
        ci.co_count,
        ROUND(AVG(mv.selling_price), 0)::int AS avg_price,
        ROUND(AVG((mv.selling_price - mv.food_cost) * 100.0 / NULLIF(mv.selling_price, 0))::numeric, 1)::float AS margin
      FROM co_items ci
      JOIN menu_items mi ON ci.item_id = mi.item_id
      LEFT JOIN menu_categories mc ON mi.category_id = mc.category_id
      LEFT JOIN menu_variants mv ON mi.item_id = mv.item_id
      GROUP BY mi.item_id, mi.name, mc.name, ci.co_count
      ORDER BY ci.co_count DESC
      LIMIT 6
    `, [...itemIds, ...itemIds]);

    res.json({ type: 'co_occurrence', based_on: itemIds, items: rows });
  } catch (err) {
    next(err);
  }
};

// ──── Price Recommendations (rule engine on menu engineering) ─────────────────
exports.priceRecommendations = async (req, res, next) => {
  try {
    // ── 1. Try ML service ─────────────────────────────────────────────────────
    const mlResult = await mlService.get('/predict/menu-optimization');
    if (mlResult?.price_recommendations?.length > 0) {
      const recommendations = mlResult.price_recommendations.map(item => ({
        item_id:                    item.item_id,
        item_name:                  item.name,
        category:                   item.category,
        bcg_class:                  item.bcg_class,
        classification:             item.bcg_class,   // backward-compat alias
        variant_name:               item.variant_name || null,
        current_price:              item.current_price,
        suggested_price:            item.suggested_price,
        price_change_pct:           item.price_change_pct,
        direction:                  item.direction,
        reason:                     item.reason,
        actual_margin_pct:          item.actual_margin_pct,
        category_target_margin_pct: item.category_target_margin_pct,
        margin_gap_pp:              item.margin_gap_pp,
        demand_percentile:          item.demand_percentile,
        demand_dampen_factor:       item.demand_dampen_factor,
        elasticity_cap_up:          item.elasticity_cap_up,
        elasticity_cap_down:        item.elasticity_cap_down,
        window_days:                item.window_days,
        is_new_item:                item.is_new_item || false,
      }));
      return res.json({
        recommendations,
        category_targets: mlResult.category_targets || {},
        source:           'ml_dynamic',
        generated_at:     mlResult.generated_at || null,
        window_days:      mlResult.window_days   || 60,
      });
    }

    // ── 2. Fallback: rule-based BCG price recommendations ─────────────────────
    const interval = parsePeriod(req);
    const pf = interval
      ? `AND oi.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')`
      : '';
    const { rows: items } = await db.query(`
      WITH item_perf AS (
        SELECT
          mi.item_id,
          mi.name,
          mv.variant_id,
          mv.variant_name,
          mv.selling_price::float AS current_price,
          SUM(oi.qty)::float AS sales_velocity,
          AVG(mv.selling_price - mv.food_cost)::float AS cm_per_unit
        FROM order_items oi
        JOIN menu_items mi ON oi.item_id = mi.item_id
        JOIN menu_variants mv ON oi.variant_id = mv.variant_id
        WHERE 1=1 ${pf}
        GROUP BY mi.item_id, mi.name, mv.variant_id, mv.variant_name, mv.selling_price
      )
      SELECT * FROM item_perf ORDER BY sales_velocity DESC
    `);

    if (items.length === 0) {
      return res.json({ recommendations: [], source: 'fallback_dynamic', window_days: 60 });
    }

    const sorted_sv = items.map(i => i.sales_velocity).sort((a, b) => a - b);
    const sorted_cm = items.map(i => i.cm_per_unit).sort((a, b) => a - b);
    const median = arr => {
      const mid = Math.floor(arr.length / 2);
      return arr.length % 2 !== 0 ? arr[mid] : (arr[mid - 1] + arr[mid]) / 2;
    };
    const medSV = median(sorted_sv);
    const medCM = median(sorted_cm);

    const recommendations = items
      .map(i => {
        let classification, factor, reason;
        if (i.sales_velocity >= medSV && i.cm_per_unit >= medCM) {
          classification = 'Star';
        } else if (i.sales_velocity < medSV && i.cm_per_unit >= medCM) {
          classification = 'Puzzle';
          factor = 0.92;
          reason = 'Low sales, high margin — reduce price 8% to boost volume';
        } else if (i.sales_velocity >= medSV && i.cm_per_unit < medCM) {
          classification = 'Plowhorse';
          factor = 1.07;
          reason = 'High sales, low margin — increase price 7% to improve margin';
        } else {
          classification = 'Dog';
        }
        if (!factor) return null;
        return {
          item_name:       i.name,
          variant_name:    i.variant_name,
          current_price:   i.current_price,
          suggested_price: Math.round(i.current_price * factor),
          bcg_class:       classification,
          classification,
          reason,
          is_new_item:     false,
        };
      })
      .filter(Boolean);

    res.json({ recommendations, source: 'fallback_dynamic', window_days: 60 });
  } catch (err) {
    next(err);
  }
};

// ──── Anomalies (proxy to ML, fallback: simple z-score) ─────────────────────
exports.anomalies = async (req, res, next) => {
  try {
    // Try ML service first
    const mlResult = await mlService.get('/predict/anomalies');
    if (mlResult) return res.json(mlResult);

    // Fallback: simple SQL-based z-score anomaly detection
    const interval = parsePeriod(req);
    const pf = interval ? `AND placed_at >= NOW() - INTERVAL '${interval}'` : '';
    const { rows } = await db.query(`
      WITH daily AS (
        SELECT
          placed_at::date AS day,
          COUNT(*)::float AS order_count,
          SUM(total)::float AS revenue,
          AVG(total)::float AS avg_order_val
        FROM orders WHERE status != 'cancelled' ${pf}
        GROUP BY placed_at::date
      ),
      stats AS (
        SELECT
          AVG(revenue) AS mean_rev,
          STDDEV(revenue) AS std_rev
        FROM daily
      )
      SELECT
        d.day,
        d.order_count,
        d.revenue,
        d.avg_order_val,
        CASE
          WHEN s.std_rev > 0
          THEN ROUND((ABS(d.revenue - s.mean_rev) / s.std_rev)::numeric, 2)
          ELSE 0
        END::float AS z_score,
        CASE
          WHEN s.std_rev > 0 AND ABS(d.revenue - s.mean_rev) / s.std_rev > 2
          THEN TRUE ELSE FALSE
        END AS is_anomaly
      FROM daily d, stats s
      ORDER BY d.day DESC
      LIMIT 90
    `);
    // Annotate each day with context (weekend / festival / weekday)
    const FESTIVALS = {
      '01-01':'New Year','01-14':'Makar Sankranti','01-15':'Pongal',
      '01-26':'Republic Day','02-14':"Valentine's Day",
      '03-25':'Holi','04-10':'Eid (approx)','08-15':'Independence Day',
      '10-02':'Gandhi Jayanti','10-12':'Dussehra (approx)',
      '11-01':'Diwali (approx)','11-02':'Diwali (approx)','12-25':'Christmas','12-31':"New Year's Eve",
    };
    const annotated = rows.map(r => {
      const d = new Date(r.day);
      const md = `${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
      const wd = d.getDay(); // 0=Sun
      const festival = FESTIVALS[md];
      let day_type, day_label;
      if (festival) { day_type = 'Festival'; day_label = festival; }
      else if (wd === 5) { day_type = 'Friday'; day_label = 'Friday — higher dining activity'; }
      else if (wd === 0 || wd === 6) { day_type = 'Weekend'; day_label = wd === 6 ? 'Saturday' : 'Sunday'; }
      else { day_type = 'Weekday'; day_label = d.toLocaleDateString('en-IN', { weekday: 'long' }); }
      return { ...r, day_type, day_label };
    });
    res.json({ source: 'sql_fallback', data: annotated });
  } catch (err) {
    next(err);
  }
};

// ──── Demand Forecast (proxy to ML) ──────────────────────────────────────────
exports.demandForecast = async (_req, res, next) => {
  try {
    const mlResult = await mlService.get('/predict/demand');
    if (mlResult) return res.json(mlResult);
    res.json({ source: 'unavailable', message: 'ML service not running. Start FastAPI on port 8000.' });
  } catch (err) {
    next(err);
  }
};
