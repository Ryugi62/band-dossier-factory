// API access from the browser: the session (bearer token in localStorage), JSON calls, and the
// outcome of a write: ok, refused (any 4xx) or uncertain (no response, or a 5xx) — decision D20.
const SESSION_KEY = 'dossier.session';

export function session() {
  try {
    const s = JSON.parse(localStorage.getItem(SESSION_KEY));
    return s && typeof s.token === 'string' ? s : null;
  } catch {
    return null;
  }
}

export function saveSession(s) {
  localStorage.setItem(SESSION_KEY, JSON.stringify({ token: s.token, user_id: s.user_id, display_name: s.display_name }));
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

export function signOutToLogin() {
  clearSession();
  location.assign('/login');
}

export function newKey() {
  if (globalThis.crypto && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

// One HTTP call. Resolves {status, body}; rejects only when no response arrived.
export async function call(method, path, { body, key, auth = true, timeoutMs = 0 } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (key) headers['Idempotency-Key'] = key;
  const s = auth ? session() : null;
  if (s) headers.Authorization = `Bearer ${s.token}`;
  const controller = timeoutMs ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  let res;
  try {
    res = await fetch(path, {
      method, headers, cache: 'no-store', body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller ? controller.signal : undefined,
    });
  } finally {
    if (timer) clearTimeout(timer);
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  return { status: res.status, body: data };
}

// A read: 401 signs the visitor out; anything else is returned as is.
export async function read(path) {
  const r = await call('GET', path);
  if (r.status === 401) signOutToLogin();
  return r;
}

// A write that has not answered after WRITE_TIMEOUT_MS is treated as lost: its outcome is unknown.
const WRITE_TIMEOUT_MS = 15000;

export async function write(method, path, opts) {
  let r;
  try {
    r = await call(method, path, { timeoutMs: WRITE_TIMEOUT_MS, ...opts });
  } catch {
    return { outcome: 'uncertain', status: 0, body: null };
  }
  if (r.status === 401) {
    signOutToLogin();
    return { outcome: 'refused', ...r };
  }
  if (r.status >= 500) return { outcome: 'uncertain', ...r };
  if (r.status >= 400) return { outcome: 'refused', ...r };
  return { outcome: 'ok', ...r };
}

// Every dossier summary, following has_more.
export async function listAll(q) {
  const out = [];
  for (let offset = 0; ; offset += 200) {
    const qs = new URLSearchParams({ limit: '200', offset: String(offset) });
    if (q) qs.set('q', q);
    const r = await read(`/dossiers?${qs}`);
    if (r.status !== 200) throw new Error(`list failed (${r.status})`);
    out.push(...r.body.dossiers);
    if (!r.body.has_more) return out;
  }
}

export function errorText(body, fallback) {
  return (body && body.error && body.error.message) || fallback;
}
