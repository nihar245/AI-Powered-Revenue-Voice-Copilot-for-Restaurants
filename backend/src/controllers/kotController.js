const db = require('../config/db');

const LOG = (...args) => console.log('[KOT]', new Date().toISOString(), ...args);
const ERR = (...args) => console.error('[KOT][ERROR]', new Date().toISOString(), ...args);

// Update KOT status (pending → preparing → ready)
exports.updateKotStatus = async (req, res, next) => {
  try {
    const { id } = req.params;
    const { status } = req.body;
    LOG('updateKotStatus  kot_id=%s  requested_status=%s', id, status);
    const valid = ['preparing', 'ready'];
    if (!valid.includes(status)) {
      ERR('Invalid status=%s for kot_id=%s', status, id);
      return res.status(400).json({ error: 'Status must be preparing or ready' });
    }

    await db.query('UPDATE kot SET status = $1 WHERE kot_id = $2', [status, id]);
    LOG('kot updated  kot_id=%s  new_status=%s', id, status);

    // Sync parent order status: preparing → preparing, ready → ready
    const orderSync = await db.query(
      'UPDATE orders SET status = $1 WHERE order_id = (SELECT order_id FROM kot WHERE kot_id = $2) RETURNING order_id',
      [status, id]
    );
    LOG('order status synced  order_id=%s  status=%s',
      orderSync.rows[0]?.order_id, status);

    res.json({ kot_id: parseInt(id, 10), status });
  } catch (err) {
    ERR('updateKotStatus threw:', err.message);
    next(err);
  }
};

// Pending KOTs for kitchen display
exports.pending = async (_req, res, next) => {
  try {
    LOG('pending() called — fetching pending/preparing KOTs');
    const { rows } = await db.query(`
      SELECT
        k.kot_id,
        k.order_id,
        k.status,
        k.priority,
        k.created_at,
        json_agg(
          json_build_object(
            'kot_item_id', ki.kot_item_id,
            'item_name', mi.name,
            'variant_name', mv.variant_name,
            'qty', ki.qty,
            'addons', ki.addons,
            'special_instructions', ki.special_instructions,
            'status', ki.status
          ) ORDER BY ki.kot_item_id
        ) AS items
      FROM kot k
      JOIN kot_items ki ON k.kot_id = ki.kot_id
      JOIN menu_items mi ON ki.item_id = mi.item_id
      LEFT JOIN menu_variants mv ON ki.variant_id = mv.variant_id
      WHERE k.status IN ('pending', 'preparing')
      GROUP BY k.kot_id
      ORDER BY
        CASE k.priority WHEN 'urgent' THEN 0 ELSE 1 END,
        k.created_at ASC
    `);
    LOG('pending() returned %d KOT(s)', rows.length);
    res.json(rows);
  } catch (err) {
    ERR('pending() threw:', err.message);
    next(err);
  }
};
