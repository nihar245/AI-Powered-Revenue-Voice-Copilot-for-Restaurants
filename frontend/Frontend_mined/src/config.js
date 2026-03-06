export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api';

// AI Voice Service (WebSocket for real-time browser conversation)
export const AI_SERVICE_WS = import.meta.env.VITE_AI_WS_URL || 'ws://localhost:8001/ws/conversation';

// AI Service admin WebSocket — receives ALL phone call broadcasts (call_started, transcript_received, response_generated, order_confirmed)
export const AI_SERVICE_ADMIN_WS = import.meta.env.VITE_AI_ADMIN_WS_URL || 'ws://localhost:8001/ws/admin';

// Set to a YYYY-MM-DD string to pin the app to a demo/seed date.
// Leave as '' to use today's live date.
export const DATA_DATE = import.meta.env.VITE_DATA_DATE || '';

export async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('token');
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `API ${res.status}`);
  }
  return res.json();
}
