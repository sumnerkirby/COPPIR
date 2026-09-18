// Thin wrappers over fetch for the JSON API.

import { showToast } from './toast.js';

/**
 * Turn a FastAPI error body into one line a user can act on.
 *
 * `detail` is a string for HTTPException but an array of per-field objects for
 * a 422, so passing it straight to Error() produced "[object Object]".
 */
function detailText(detail, fallback) {
  if (typeof detail === 'string') return detail;
  if (!Array.isArray(detail)) return fallback;
  return detail.map(d => {
    const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : null;
    const msg   = String(d.msg || '').replace(/^Value error, /, '');
    return field ? `${field}: ${msg}` : msg;
  }).join('; ') || fallback;
}

async function request(method, url, body) {
  try {
    const r = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(detailText(err.detail, r.statusText));
    }
    return r.json();
  } catch (e) {
    showToast(`Error: ${e.message}`);
    return null;
  }
}

export const apiPost = (url, body) => request('POST', url, body);
export const apiPut  = (url, body) => request('PUT',  url, body);
