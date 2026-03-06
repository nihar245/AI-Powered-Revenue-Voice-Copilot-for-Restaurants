const db = require('../config/db');
const mlService = require('../services/mlService');

// ──── Period filter helper ───────────────────────────────────────────────────
// Whitelisted — interval value never comes from raw user input, safe to interpolate.
function parsePeriod(req) {
  const VALID = { '7d': '7 days', '30d': '30 days', '90d': '90 days', all: null };
  const p = req?.query?.period;
  return Object.prototype.hasOwnProperty.call(VALID, p) ? VALID[p] : null;
}

// ──── Menu Profitability (frontend shape) ────────────────────────────────────
// Returns [{ name, popularity, margin, revenue }] matching mockData.menuProfitability
exports.menuProfitability = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pf = interval ? `AND oi.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const { rows } = await db.query(`
      WITH item_stats AS (
        SELECT
          mi.item_id,
          mi.name,
          SUM(oi.qty)::int AS total_qty,
          SUM(oi.revenue)::float AS revenue,
          AVG(mv.selling_price - mv.food_cost)::float AS avg_margin
        FROM order_items oi
        JOIN menu_items mi ON oi.item_id = mi.item_id
        JOIN menu_variants mv ON oi.variant_id = mv.variant_id
        WHERE 1=1 ${pf}
        GROUP BY mi.item_id, mi.name
      ),
      max_vals AS (
        SELECT MAX(total_qty) AS max_qty, MAX(avg_margin) AS max_margin FROM item_stats
      )
      SELECT
        s.name,
        ROUND((s.total_qty * 100.0 / NULLIF(m.max_qty, 0))::numeric, 0)::int AS popularity,
        ROUND((s.avg_margin * 100.0 / NULLIF(m.max_margin, 0))::numeric, 0)::int AS margin,
        s.revenue
      FROM item_stats s, max_vals m
      ORDER BY s.revenue DESC
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// ──── Combo Recommendations (frontend shape) ─────────────────────────────────
// Returns [{ itemA, itemB, confidence, lift }] matching mockData.comboRecommendations
exports.comboRecommendations = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pfA  = interval ? `AND a.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const pfOi = interval ? `AND order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const { rows } = await db.query(`
      WITH pairs AS (
        SELECT a.item_id AS item_a, b.item_id AS item_b
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
        pc.pair_count AS "pairCount",
        ROUND((pc.pair_count * 100.0 / ta.total)::numeric, 0)::int AS confidence,
        ROUND(
          ((pc.pair_count::float / ta.total) /
          (tb.total::float / (SELECT n FROM total_orders)))::numeric,
          1
        )::float AS lift
      FROM pair_counts pc
      JOIN menu_items ma ON pc.item_a = ma.item_id
      JOIN menu_items mb ON pc.item_b = mb.item_id
      JOIN item_totals ta ON pc.item_a = ta.item_id
      JOIN item_totals tb ON pc.item_b = tb.item_id
      WHERE pc.pair_count > 1
      ORDER BY lift DESC
      LIMIT 30
    `);
    res.json(rows);
  } catch (err) {
    next(err);
  }
};

// ──── Popularity Scoring ─────────────────────────────────────────────────────
// Returns items classified as Fast Mover / Normal / Slow Mover / Dead based on
// sales velocity percentile.  velocity = total qty sold over all recorded time.
exports.popularityScoring = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pfJoin   = interval ? `AND oi.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const pfOrders = interval ? `WHERE placed_at >= NOW() - INTERVAL '${interval}'` : '';

    const [{ rows: items }, { rows: tspan }] = await Promise.all([
      db.query(`
        WITH item_sales AS (
          SELECT
            mi.item_id,
            mi.name,
            mc.name AS category,
            COALESCE(SUM(oi.qty), 0)::float AS total_sold,
            COALESCE(COUNT(DISTINCT oi.order_id), 0)::int AS order_frequency
          FROM menu_items mi
          LEFT JOIN menu_categories mc ON mi.category_id = mc.category_id
          LEFT JOIN order_items oi ON mi.item_id = oi.item_id ${pfJoin}
          GROUP BY mi.item_id, mi.name, mc.name
        )
        SELECT *, RANK() OVER (ORDER BY total_sold DESC)::int AS rank
        FROM item_sales
        ORDER BY total_sold DESC
      `),
      db.query(`
        SELECT GREATEST(1, EXTRACT(EPOCH FROM (MAX(placed_at) - MIN(placed_at))) / 86400.0)::float AS days_span
        FROM orders ${pfOrders}
      `),
    ]);

    if (items.length === 0) return res.json([]);

    const daysSpan = tspan[0]?.days_span || 1;
    const total    = items.length;
    const result = items.map((item, idx) => {
      const pct = ((total - idx) / total) * 100;
      let classification;
      if (item.total_sold === 0) classification = 'Dead';
      else if (pct >= 75) classification = 'Fast Mover';
      else if (pct >= 40) classification = 'Normal';
      else classification = 'Slow Mover';

      return {
        item_id: item.item_id,
        name: item.name,
        category: item.category,
        total_sold: item.total_sold,
        order_frequency: item.order_frequency,
        rank: item.rank,
        rank_pct: Math.round(pct),
        classification,
        velocity_per_day: parseFloat((item.total_sold / daysSpan).toFixed(2)),
      };
    });

    res.json(result);
  } catch (err) {
    next(err);
  }
};

// ──── Hidden Stars ────────────────────────────────────────────────────────────
// Items with above-median contribution margin but below-median sales velocity
// (BCG "Puzzle" / hidden gem) — high-value items that need visibility push.
exports.hiddenStars = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pfJoin = interval ? `AND oi.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const { rows: items } = await db.query(`
      WITH item_perf AS (
        SELECT
          mi.item_id,
          mi.name,
          mc.name AS category,
          COALESCE(SUM(oi.qty), 0)::float AS sales_velocity,
          COALESCE(AVG(mv.selling_price - mv.food_cost), 0)::float AS cm_per_unit,
          COALESCE(AVG(mv.selling_price), 0)::float AS avg_price,
          COALESCE(
            AVG(
              CASE WHEN mv.selling_price > 0
                THEN (mv.selling_price - mv.food_cost) / mv.selling_price * 100
              END
            ),
            0
          )::float AS margin_pct
        FROM menu_items mi
        LEFT JOIN menu_categories mc ON mi.category_id = mc.category_id
        LEFT JOIN order_items oi ON mi.item_id = oi.item_id ${pfJoin}
        LEFT JOIN menu_variants mv ON mi.item_id = mv.item_id
        GROUP BY mi.item_id, mi.name, mc.name
      )
      SELECT * FROM item_perf
    `);

    if (items.length === 0) return res.json([]);

    const sorted_sv = items.map(i => i.sales_velocity).sort((a, b) => a - b);
    const sorted_cm = items.map(i => i.cm_per_unit).sort((a, b) => a - b);
    const median = arr => {
      const mid = Math.floor(arr.length / 2);
      return arr.length % 2 !== 0 ? arr[mid] : (arr[mid - 1] + arr[mid]) / 2;
    };
    const medSV = median(sorted_sv);
    const medCM = median(sorted_cm);

    const hidden = items
      .filter(i => i.sales_velocity < medSV && i.cm_per_unit > medCM)
      .sort((a, b) => b.cm_per_unit - a.cm_per_unit)
      .map(i => ({
        item_id: i.item_id,
        name: i.name,
        category: i.category,
        sales_velocity: Math.round(i.sales_velocity),
        margin_pct: Math.round(i.margin_pct * 10) / 10,
        cm_per_unit: Math.round(i.cm_per_unit * 100) / 100,
        avg_price: Math.round(i.avg_price),
        combo_partners: [],
        promotion_advice: 'Feature on menu · create combo offer · upsell by staff',
      }));

    // Enrich each hidden star with items customers actually order alongside it
    if (hidden.length > 0) {
      const starIds = hidden.map(h => h.item_id);
      const ph = starIds.map((_, idx) => `$${idx + 1}`).join(',');
      const pfBase = interval
        ? `AND oi1.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')`
        : '';
      const { rows: partners } = await db.query(`
        SELECT oi1.item_id::int AS star_id, mi2.name AS partner_name, COUNT(*)::int AS co_count
        FROM order_items oi1
        JOIN order_items oi2 ON oi1.order_id = oi2.order_id AND oi1.item_id != oi2.item_id
        JOIN menu_items mi2 ON oi2.item_id = mi2.item_id
        WHERE oi1.item_id IN (${ph}) ${pfBase}
        GROUP BY oi1.item_id, mi2.name
        ORDER BY oi1.item_id, co_count DESC
      `, starIds);
      const pMap = {};
      for (const r of partners) {
        const sid = Number(r.star_id);
        if (!pMap[sid]) pMap[sid] = [];
        if (pMap[sid].length < 2) pMap[sid].push(r.partner_name);
      }
      for (const item of hidden) {
        item.combo_partners = pMap[item.item_id] || [];
        if (item.combo_partners.length > 0) {
          item.promotion_advice = `Customers also order: ${item.combo_partners.join(' & ')} — create combo deal`;
        }
      }
    }

    res.json({ count: hidden.length, median_cm: Math.round(medCM * 100) / 100, items: hidden });
  } catch (err) {
    next(err);
  }
};

// ──── Risk Detection ─────────────────────────────────────────────────────────
// Flag Plowhorse items: high volume but low contribution margin.
// risk_score = 0–100 where higher = more revenue at risk from thin margin.
exports.riskDetection = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pfJoin = interval ? `AND oi.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const { rows: items } = await db.query(`
      WITH item_perf AS (
        SELECT
          mi.item_id,
          mi.name,
          mc.name AS category,
          COALESCE(SUM(oi.qty), 0)::float AS sales_velocity,
          COALESCE(SUM(oi.revenue), 0)::float AS total_revenue,
          COALESCE(AVG(mv.selling_price - mv.food_cost), 0)::float AS cm_per_unit,
          COALESCE(
            AVG(
              CASE WHEN mv.selling_price > 0
                THEN (mv.selling_price - mv.food_cost) / mv.selling_price * 100
              END
            ),
            0
          )::float AS margin_pct,
          COALESCE(AVG(mv.selling_price), 0)::float AS avg_price
        FROM menu_items mi
        LEFT JOIN menu_categories mc ON mi.category_id = mc.category_id
        LEFT JOIN order_items oi ON mi.item_id = oi.item_id ${pfJoin}
        LEFT JOIN menu_variants mv ON mi.item_id = mv.item_id
        GROUP BY mi.item_id, mi.name, mc.name
      )
      SELECT * FROM item_perf WHERE sales_velocity > 0
    `);

    if (items.length === 0) return res.json([]);

    const sorted_sv = items.map(i => i.sales_velocity).sort((a, b) => a - b);
    const sorted_cm = items.map(i => i.cm_per_unit).sort((a, b) => a - b);
    const median = arr => {
      const mid = Math.floor(arr.length / 2);
      return arr.length % 2 !== 0 ? arr[mid] : (arr[mid - 1] + arr[mid]) / 2;
    };
    const medSV = median(sorted_sv);
    const medCM = median(sorted_cm);
    const maxSV = Math.max(...sorted_sv);

    const risks = items
      .filter(i => i.sales_velocity >= medSV && i.cm_per_unit < medCM)
      .map(i => {
        const volume_norm = i.sales_velocity / maxSV;
        const margin_gap = (medCM - i.cm_per_unit) / (medCM || 1);
        const risk_score = Math.round(volume_norm * margin_gap * 100);
        const gap = medCM - i.cm_per_unit;
        const target_price = Math.round(i.avg_price + gap);
        const pct_needed = i.avg_price > 0 ? Math.round((gap / i.avg_price) * 100) : 0;
        const food_cost = Math.round(i.avg_price - i.cm_per_unit);
        let action;
        if (pct_needed <= 12) {
          action = `Raise price ₹${Math.round(i.avg_price)} → ₹${target_price} (+${pct_needed}%) to close ₹${Math.round(gap)} margin gap`;
        } else {
          const target_fc = Math.max(0, Math.round(food_cost - gap * 0.5));
          action = `Margin gap ₹${Math.round(gap)}/unit — raise price to ₹${target_price} (+${pct_needed}%) OR cut food cost from ₹${food_cost} to ₹${target_fc}`;
        }
        return {
          item_id: i.item_id,
          name: i.name,
          category: i.category,
          sales_velocity: Math.round(i.sales_velocity),
          margin_pct: Math.round(i.margin_pct * 10) / 10,
          cm_per_unit: Math.round(i.cm_per_unit * 100) / 100,
          avg_price: Math.round(i.avg_price),
          total_revenue: Math.round(i.total_revenue),
          risk_score,
          risk_level: risk_score >= 60 ? 'High' : risk_score >= 30 ? 'Medium' : 'Low',
          action,
        };
      })
      .sort((a, b) => b.risk_score - a.risk_score);

    res.json({ count: risks.length, items: risks });
  } catch (err) {
    next(err);
  }
};

// ──── Underperforming Items (frontend shape) ─────────────────────────────────
// Returns [{ name, sales, margin, recommendation }] matching mockData.underperformingItems
exports.underperformingItems = async (req, res, next) => {
  try {
    const interval = parsePeriod(req);
    const pf = interval ? `AND oi.order_id IN (SELECT order_id FROM orders WHERE placed_at >= NOW() - INTERVAL '${interval}')` : '';
    const { rows: items } = await db.query(`
      WITH item_perf AS (
        SELECT
          mi.item_id,
          mi.name,
          SUM(oi.qty)::float AS sales_velocity,
          AVG(mv.selling_price - mv.food_cost)::float AS cm_per_unit,
          AVG(mv.selling_price)::float AS avg_price
        FROM order_items oi
        JOIN menu_items mi ON oi.item_id = mi.item_id
        JOIN menu_variants mv ON oi.variant_id = mv.variant_id
        WHERE 1=1 ${pf}
        GROUP BY mi.item_id, mi.name
      )
      SELECT * FROM item_perf
    `);

    if (items.length === 0) return res.json([]);

    const sorted_sv = items.map(i => i.sales_velocity).sort((a, b) => a - b);
    const sorted_cm = items.map(i => i.cm_per_unit).sort((a, b) => a - b);
    const median = arr => {
      const mid = Math.floor(arr.length / 2);
      return arr.length % 2 !== 0 ? arr[mid] : (arr[mid - 1] + arr[mid]) / 2;
    };
    const medSV = median(sorted_sv);
    const medCM = median(sorted_cm);

    const underperforming = items
      .map(i => {
        const lowSales = i.sales_velocity < medSV;
        const lowMargin = i.cm_per_unit < medCM;
        const sv = Math.round(i.sales_velocity);
        const cm = Math.round(i.cm_per_unit * 100) / 100;
        const gap = Math.round((medCM - i.cm_per_unit) * 100) / 100;
        const suggestedPrice = Math.round((i.avg_price || 0) + Math.max(0, gap));

        let sales, margin, recommendation;

        if (lowSales && lowMargin) {
          // Dog
          sales = 'Low'; margin = 'Low';
          recommendation = `${sv} units sold · ₹${cm}/unit margin — discount to clear stock, reprice lower, or remove`;
        } else if (lowSales && !lowMargin) {
          // Puzzle
          const potential = Math.round((medSV - i.sales_velocity) * i.cm_per_unit);
          sales = 'Low'; margin = 'High';
          recommendation = `High margin ₹${cm}/unit · only ${sv} orders — feature on menu or bundle deal; ₹${potential} upside if sales reach median`;
        } else if (!lowSales && lowMargin) {
          // Plowhorse
          sales = 'High'; margin = 'Low';
          recommendation = `Popular (${sv} units) but ₹${Math.abs(gap)} below median margin — raise price by ₹${Math.abs(gap)} (to ₹${suggestedPrice})`;
        } else {
          return null; // Star
        }
        return { name: i.name, sales, margin, recommendation, sales_velocity: sv, cm_per_unit: cm };
      })
      .filter(Boolean);

    res.json(underperforming);
  } catch (err) {
    next(err);
  }
};

// ──── Menu Optimization (proxy to ML) ────────────────────────────────────────
exports.menuOptimization = async (_req, res, next) => {
  try {
    const mlResult = await mlService.get('/predict/menu-optimization');
    if (mlResult) return res.json(mlResult);
    res.json({ source: 'unavailable', message: 'ML service not running. Start FastAPI on port 8000.' });
  } catch (err) {
    next(err);
  }
};
