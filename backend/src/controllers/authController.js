const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const db = require('../config/db');

const SALT_ROUNDS = 10;

function signToken(user) {
  return jwt.sign(
    { id: user.user_id, email: user.email, restaurant_id: user.restaurant_id },
    process.env.JWT_SECRET,
    { expiresIn: '24h' }
  );
}

exports.signup = async (req, res, next) => {
  try {
    const { name, email, password, restaurant_id } = req.body;
    if (!name || !email || !password) {
      return res.status(400).json({ error: 'name, email, and password are required' });
    }

    const existing = await db.query('SELECT user_id FROM users WHERE email = $1', [email]);
    if (existing.rows.length > 0) {
      return res.status(409).json({ error: 'Email already registered' });
    }

    const hash = await bcrypt.hash(password, SALT_ROUNDS);
    const result = await db.query(
      `INSERT INTO users (name, email, password_hash, restaurant_id)
       VALUES ($1, $2, $3, $4) RETURNING user_id, name, email, restaurant_id`,
      [name, email, hash, restaurant_id || 1]
    );

    const user = result.rows[0];
    const token = signToken(user);
    res.status(201).json({ token, user: { id: user.user_id, name: user.name, email: user.email } });
  } catch (err) {
    next(err);
  }
};

exports.login = async (req, res, next) => {
  try {
    const { email, password } = req.body;
    if (!email || !password) {
      return res.status(400).json({ error: 'email and password are required' });
    }

    const result = await db.query(
      'SELECT user_id, name, email, password_hash, restaurant_id FROM users WHERE email = $1',
      [email]
    );
    if (result.rows.length === 0) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const user = result.rows[0];
    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const token = signToken(user);
    res.json({ token, user: { id: user.user_id, name: user.name, email: user.email } });
  } catch (err) {
    next(err);
  }
};
