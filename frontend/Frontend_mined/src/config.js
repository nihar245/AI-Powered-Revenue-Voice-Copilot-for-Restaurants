export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api';

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
