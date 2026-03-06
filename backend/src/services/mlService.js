const axios = require('axios');

const ML_URL = process.env.ML_SERVICE_URL || 'http://localhost:8000';
const TIMEOUT = 10000; // 10 seconds

async function get(path) {
  try {
    const resp = await axios.get(`${ML_URL}${path}`, { timeout: TIMEOUT });
    return resp.data;
  } catch {
    return null; // ML service unavailable — caller should use fallback
  }
}

async function post(path, body) {
  try {
    const resp = await axios.post(`${ML_URL}${path}`, body, { timeout: TIMEOUT });
    return resp.data;
  } catch {
    return null;
  }
}

module.exports = { get, post };
