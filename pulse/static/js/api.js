// Typed-ish fetch wrapper: JSON only, CSRF header, timeouts, tiny GET cache.
export class ApiError extends Error {
  constructor(status, message, code) {
    super(message);
    this.status = status;
    this.code = code || null;
  }
}

const CSRF_HEADER = { 'X-Pulse-Client': 'web' };
const cache = new Map();
const inflight = new Map();

function cacheKey(path, opts) {
  return `${opts.method || 'GET'} ${path}`;
}

export function invalidate(prefix = '') {
  for (const key of [...cache.keys()]) {
    if (!prefix || key.includes(prefix)) cache.delete(key);
  }
}

export async function api(path, opts = {}) {
  const method = (opts.method || 'GET').toUpperCase();
  const ttl = opts.cacheTtl ?? 0;
  const key = cacheKey(path, { method });
  if (method === 'GET' && ttl > 0 && !opts.force) {
    const cached = cache.get(key);
    if (cached && Date.now() - cached.at < ttl * 1000) return cached.data;
  }
  if (method === 'GET' && inflight.has(key)) return inflight.get(key);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeout ?? 25000);
  if (opts.signal) {
    if (opts.signal.aborted) controller.abort();
    else opts.signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  const headers = { Accept: 'application/json', ...CSRF_HEADER, ...(opts.headers || {}) };
  let body;
  if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }

  const promise = (async () => {
    let response;
    try {
      response = await fetch(path, { method, headers, body, signal: controller.signal, credentials: 'same-origin' });
    } catch (err) {
      if (err.name === 'AbortError') {
        window.dispatchEvent(new CustomEvent('pulse:network-error', { detail: { path, reason: 'timeout' } }));
        throw new ApiError(0, 'Request timed out. Check your connection and try again.', 'timeout');
      }
      // A local Pulse server can be stopped — or restarting on Render — while
      // the browser still has a network connection. Tell the shell so it can
      // watch for recovery and refresh automatically.
      window.dispatchEvent(new CustomEvent('pulse:network-error', { detail: { path, reason: 'offline' } }));
      throw new ApiError(0, 'Pulse cannot reach its server. Reconnecting…', 'offline');
    } finally {
      clearTimeout(timer);
    }
    if (response.status === 401) {
      let detail = {};
      try { detail = await response.json(); } catch { /* ignore */ }
      window.dispatchEvent(new CustomEvent('pulse:auth-required', { detail }));
      throw new ApiError(401, 'Access token required.', 'token_required');
    }
    if (response.status >= 500) {
      // Render serves its own 502/503 HTML page while an instance restarts.
      // Treat that as a temporary outage so the app can keep its shell and
      // reconnect instead of surfacing "Request failed (502)".
      window.dispatchEvent(new CustomEvent('pulse:network-error', { detail: { path, reason: `http_${response.status}` } }));
      throw new ApiError(response.status, 'Pulse is restarting. Reconnecting…', 'server_error');
    }
    if (!response.ok) {
      let detail = {};
      try { detail = await response.json(); } catch { /* ignore */ }
      throw new ApiError(response.status, detail.error || `Request failed (${response.status})`, detail.code);
    }
    if (response.status === 204) return {};
    const data = await response.json();
    if (method === 'GET' && ttl > 0) cache.set(key, { at: Date.now(), data });
    return data;
  })();

  if (method === 'GET') {
    inflight.set(key, promise);
    promise.finally(() => inflight.delete(key));
  }
  return promise;
}

export const get = (path, ttl = 0, force = false) => api(path, { cacheTtl: ttl, force });
export const post = (path, body) => api(path, { method: 'POST', body });
export const patch = (path, body) => api(path, { method: 'PATCH', body });
export const del = (path, body) => api(path, { method: 'DELETE', body });
