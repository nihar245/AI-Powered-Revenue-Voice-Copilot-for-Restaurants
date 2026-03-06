const Razorpay = require('razorpay');
const crypto = require('crypto');
const db = require('../config/db');

const razorpay = new Razorpay({
  key_id: process.env.RAZORPAY_KEY_ID,
  key_secret: process.env.RAZORPAY_KEY_SECRET,
});

/**
 * POST /api/payments/razorpay-order
 * Body: { amount: <number in rupees> }
 * Creates a Razorpay order. Returns the order details + key_id for frontend checkout.
 */
exports.createRazorpayOrder = async (req, res, next) => {
  try {
    const { amount } = req.body;
    if (!amount || amount <= 0) {
      return res.status(400).json({ error: 'amount is required and must be > 0' });
    }

    if (!process.env.RAZORPAY_KEY_ID || !process.env.RAZORPAY_KEY_SECRET) {
      return res.status(503).json({ error: 'Payment gateway not configured' });
    }

    let order;
    try {
      order = await razorpay.orders.create({
        amount: Math.round(amount * 100), // paise
        currency: 'INR',
        receipt: `rcpt_${Date.now()}`,
        payment_capture: 1,
      });
    } catch (razorpayErr) {
      // Razorpay SDK v2.x can throw internally malformed errors — normalize them
      const message = razorpayErr?.error?.description
        || razorpayErr?.message
        || 'Payment gateway error';
      const status = razorpayErr?.statusCode || razorpayErr?.error?.http_status_code || 502;
      return res.status(status).json({ error: message });
    }

    res.json({
      razorpay_order_id: order.id,
      amount: order.amount,
      currency: order.currency,
      key_id: process.env.RAZORPAY_KEY_ID,
    });
  } catch (err) {
    next(err);
  }
};

/**
 * POST /api/payments/verify
 * Body: { razorpay_order_id, razorpay_payment_id, razorpay_signature, order_id }
 * Verifies Razorpay payment signature and marks order as paid.
 */
exports.verify = async (req, res, next) => {
  try {
    const { razorpay_order_id, razorpay_payment_id, razorpay_signature, order_id } = req.body;

    if (!razorpay_order_id || !razorpay_payment_id || !razorpay_signature || !order_id) {
      return res.status(400).json({ error: 'Missing required payment verification fields' });
    }

    // Verify HMAC signature
    const expectedSig = crypto
      .createHmac('sha256', process.env.RAZORPAY_KEY_SECRET)
      .update(`${razorpay_order_id}|${razorpay_payment_id}`)
      .digest('hex');

    if (expectedSig !== razorpay_signature) {
      return res.status(400).json({ error: 'Payment verification failed: signature mismatch' });
    }

    // Update order payment status and record payment id + transaction ref
    await db.query(
      `UPDATE orders SET payment_status = 'paid' WHERE order_id = $1`,
      [order_id]
    );
    await db.query(
      `UPDATE order_payments SET method = 'razorpay', transaction_ref = $1, paid_at = NOW() WHERE order_id = $2`,
      [razorpay_payment_id, order_id]
    );

    res.json({ success: true, payment_id: razorpay_payment_id });
  } catch (err) {
    next(err);
  }
};
