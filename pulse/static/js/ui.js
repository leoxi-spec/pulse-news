// Small DOM/render toolkit. All interpolated data is escaped by default.
const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

class SafeString extends String {}

export const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ESCAPES[c]);
export const raw = (value) => new SafeString(value == null ? '' : String(value));

function flatten(value) {
  if (value == null || value === false) return '';
  if (value instanceof SafeString) return String(value);
  if (Array.isArray(value)) return value.map(flatten).join('');
  return esc(value);
}

export function html(strings, ...values) {
  let out = strings[0];
  for (let i = 0; i < values.length; i += 1) out += flatten(values[i]) + strings[i + 1];
  return new SafeString(out);
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const mount = (node, markup) => { node.innerHTML = markup; return node; };

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'html') node.innerHTML = value;
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export const number = (value) => new Intl.NumberFormat(undefined).format(Number(value || 0));

export function compactNumber(value) {
  const n = Number(value || 0);
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0).replace('.0', '')}k`;
  return `${(n / 1_000_000).toFixed(1).replace('.0', '')}m`;
}

const MINUTE = 60_000;
export function timeAgo(dateish) {
  if (!dateish) return '';
  const then = new Date(dateish).getTime();
  if (Number.isNaN(then)) return '';
  const diff = Date.now() - then;
  const future = diff < 0;
  const s = Math.abs(diff) / 1000;
  let label;
  if (s < 45) return 'just now';
  else if (s < 90) label = '1 min';
  else if (s < 3600) label = `${Math.round(s / 60)} min`;
  else if (s < 5400) label = '1 hr';
  else if (s < 86400) label = `${Math.round(s / 3600)} hr`;
  else if (s < 172800) label = '1 day';
  else if (s < 604800) label = `${Math.round(s / 86400)} days`;
  else if (s < 2629800) label = `${Math.round(s / 604800)} wk`;
  else if (s < 31557600) label = `${Math.round(s / 2629800)} mo`;
  else label = `${Math.round(s / 31557600)} yr`;
  return future ? `in ${label}` : `${label} ago`;
}

export function absDate(dateish, withTime = true) {
  if (!dateish) return '';
  const d = new Date(dateish);
  if (Number.isNaN(d.getTime())) return '';
  const opts = withTime
    ? { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }
    : { month: 'short', day: 'numeric', year: 'numeric' };
  return new Intl.DateTimeFormat(undefined, opts).format(d);
}

export function dateChip(item) {
  const label = item.date_label || 'Published';
  const value = item.published_relative || timeAgo(item.published_at || item.first_seen_at);
  const exact = absDate(item.published_at || item.first_seen_at);
  return html`<span class="tiny muted" title="${exact}">${label} ${value}</span>`;
}

// ------------------------------------------------------------------- toasts
let toastTimer = null;
export function confetti(count = 48) {
  if (typeof document === 'undefined') return;
  const reduce = document.documentElement.dataset.reduceMotion === '1'
    || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    || document.body.classList.contains('no-confetti');
  if (reduce) return;
  const colors = ['#ff4d6d', '#ffd166', '#06d6a0', '#4cc9f0', '#b388ff', '#ff9f1c'];
  const layer = document.createElement('div');
  layer.className = 'confetti-layer';
  layer.setAttribute('aria-hidden', 'true');
  for (let i = 0; i < count; i += 1) {
    const bit = document.createElement('i');
    bit.className = 'confetti-bit';
    bit.style.left = `${Math.random() * 100}%`;
    bit.style.background = colors[i % colors.length];
    bit.style.animationDelay = `${Math.random() * 0.5}s`;
    bit.style.animationDuration = `${1.4 + Math.random() * 1.1}s`;
    bit.style.transform = `rotate(${Math.random() * 360}deg)`;
    layer.appendChild(bit);
  }
  document.body.appendChild(layer);
  setTimeout(() => layer.remove(), 3000);
}

export function haptic(ms = 8) {
  if (document.body.classList.contains('no-haptics')) return;
  navigator.vibrate?.(ms);
}

export function toast(message, { type = '', actionLabel = '', onAction = null, duration = 3600 } = {}) {
  const root = document.getElementById('toast-root');
  if (!root) return;
  const node = el('div', { class: `toast ${type ? `toast--${type}` : ''}`, role: 'status' });
  node.innerHTML = html`<span>${message}</span>`;
  if (actionLabel) {
    const btn = el('button', { class: 'toast__action', type: 'button' }, actionLabel);
    btn.addEventListener('click', () => { node.remove(); onAction?.(); });
    node.append(btn);
  }
  root.append(node);
  while (root.children.length > 3) root.firstElementChild.remove();
  setTimeout(() => node.remove(), duration);
}

export function toastProgress(progress) {
  if (!progress) return;
  if (progress.xp_awarded > 0) {
    const levelUp = progress.level_progress?.percent === 0 && progress.xp_awarded > 0;
    toast(`+${progress.xp_awarded} XP${levelUp ? ` · Level ${progress.level}` : ''}`, { type: 'good', duration: 2200 });
  }
  const fresh = (progress.badges || []).filter((b) => b.earned && !progress.__known);
  if (fresh.length && progress.xp_awarded > 0) {
    const newest = fresh[fresh.length - 1];
    if (newest) toast(`Badge unlocked: ${newest.label}`, { type: 'good', duration: 4000 });
  }
}

// -------------------------------------------------------------------- modal
export function modal({ title, body, actions = [], wide = false, onClose = null }) {
  const root = document.getElementById('modal-root');
  const previousFocus = document.activeElement;
  const wrapper = el('div', { class: `modal ${wide ? 'modal--wide' : ''}`, role: 'dialog', 'aria-modal': 'true', 'aria-label': title || 'Dialog' });
  wrapper.innerHTML = html`
    <div class="modal__head">
      <h2>${title || ''}</h2>
      <button class="icon-btn" data-close aria-label="Close"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
    </div>
    <div class="modal__body"></div>
    ${actions.length ? raw('<div class="modal__foot"></div>') : ''}`;
  const bodyNode = $('.modal__body', wrapper);
  if (body instanceof Node) bodyNode.append(body);
  else bodyNode.innerHTML = body || '';
  const foot = $('.modal__foot', wrapper);
  actions.forEach((action) => {
    const btn = el('button', { class: `btn ${action.class || ''}`, type: 'button' }, action.label);
    btn.addEventListener('click', async () => {
      if (action.onClick) {
        const result = await action.onClick({ close, modal: wrapper });
        if (result === false) return;
      }
      if (action.close !== false) close();
    });
    foot?.append(btn);
  });

  const close = () => {
    root.hidden = true;
    root.innerHTML = '';
    document.body.classList.remove('no-scroll');
    document.removeEventListener('keydown', onKey);
    if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
    onClose?.();
  };
  const focusable = () => [...wrapper.querySelectorAll(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  )].filter((node) => node.offsetParent !== null);
  const onKey = (event) => {
    if (event.key === 'Escape') { close(); return; }
    if (event.key !== 'Tab') return;
    const nodes = focusable();
    if (!nodes.length) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  document.addEventListener('keydown', onKey);
  $('[data-close]', wrapper).addEventListener('click', close);
  wrapper.addEventListener('click', (event) => { if (event.target === wrapper) close(); });
  root.innerHTML = '';
  root.append(wrapper);
  root.hidden = false;
  document.body.classList.add('no-scroll');
  setTimeout(() => wrapper.querySelector('button, input, textarea, a')?.focus(), 30);
  return { close, modal: wrapper };
}

export function confirmDialog(message, { title = 'Are you sure?', confirmLabel = 'Confirm', danger = false } = {}) {
  return new Promise((resolve) => {
    const { close } = modal({
      title,
      body: html`<p class="muted" style="font-size:.92rem">${message}</p>`,
      actions: [
        { label: 'Cancel', class: 'btn--ghost', onClick: () => { resolve(false); } },
        { label: confirmLabel, class: danger ? 'btn--danger' : 'btn--primary', onClick: () => { resolve(true); } },
      ],
      onClose: () => resolve(false),
    });
    void close;
  });
}

// ------------------------------------------------------------------- actions
export const actions = new Map();
export function registerAction(id, handler) { actions.set(id, handler); }

document.addEventListener('click', (event) => {
  const target = event.target.closest('[data-action]');
  if (!target) return;
  const id = target.dataset.action;
  const handler = actions.get(id);
  if (!handler) return;
  event.preventDefault();
  handler(target, event).catch((err) => {
    console.error(err);
    toast(err?.message || 'Something went wrong', { type: 'bad' });
  });
});

// ---------------------------------------------------------------- utilities
export function debounce(fn, wait = 220) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

export function throttle(fn, wait = 500) {
  let last = 0;
  let queued = null;
  return (...args) => {
    const now = Date.now();
    if (now - last >= wait) { last = now; fn(...args); }
    else { clearTimeout(queued); queued = setTimeout(() => { last = Date.now(); fn(...args); }, wait - (now - last)); }
  };
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.append(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  }
}

export function setLoading(node, label = 'Loading') {
  node.innerHTML = html`<div class="empty"><div class="skeleton" style="width:42px;height:42px;border-radius:50%;margin:0 auto .8rem"></div><p class="muted small">${label}…</p></div>`;
}

export function errorState(node, message, retry = null) {
  node.innerHTML = html`
    <div class="empty">
      <div class="empty__mark"></div>
      <h2>That didn't load</h2>
      <p>${message || 'Check your connection and try again.'}</p>
      ${retry ? raw('<button class="btn btn--ghost" style="margin-top:1rem" data-retry>Try again</button>') : ''}
    </div>`;
  if (retry) node.querySelector('[data-retry]')?.addEventListener('click', retry);
}

export const proxyImg = (url) => (url ? `/api/img?u=${encodeURIComponent(url)}` : null);

export const icons = {
  home: '<svg viewBox="0 0 24 24"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.8V21h14V9.8"/></svg>',
  compass: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2.2 5.5L8 16l2.5-5.5Z"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  bookmark: '<svg viewBox="0 0 24 24"><path d="M6 4h12v17l-6-4-6 4Z"/></svg>',
  user: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6"/></svg>',
  bolt: '<svg viewBox="0 0 24 24"><path d="M13 2 4 14h6l-1 8 9-12h-6Z"/></svg>',
  printer: '<svg viewBox="0 0 24 24"><path d="M7 9V4h10v5"/><rect x="4" y="9" width="16" height="7" rx="2"/><path d="M7 16h10v5H7Z"/></svg>',
  pause: '<svg viewBox="0 0 24 24"><path d="M9 5v14"/><path d="M15 5v14"/></svg>',
  sound: '<svg viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9Z"/><path d="M16.5 8.5a5 5 0 0 1 0 7"/><path d="M19 6a8.5 8.5 0 0 1 0 12"/></svg>',
  trophy: '<svg viewBox="0 0 24 24"><path d="M7 4h10v5a5 5 0 0 1-10 0Z"/><path d="M7 5H4v2a3 3 0 0 0 3 3M17 5h3v2a3 3 0 0 1-3 3"/><path d="M12 14v3M9 21h6"/></svg>',
  book: '<svg viewBox="0 0 24 24"><path d="M4 4h7v16H4zM13 4h7v16h-7z"/></svg>',
  clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  fire: '<svg viewBox="0 0 24 24"><path d="M12 3s5 4 5 9a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3 1-6 1-8Z"/></svg>',
  sparkle: '<svg viewBox="0 0 24 24"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8Z"/><path d="M18 16l.8 2.2L21 19l-2.2.8L18 22l-.8-2.2L15 19l2.2-.8Z"/></svg>',
  share: '<svg viewBox="0 0 24 24"><path d="M12 16V4m0 0 4 4m-4-4L8 8"/><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5"/></svg>',
  quote: '<svg viewBox="0 0 24 24"><path d="M7 7h4v5H7a3 3 0 0 0 3 3M14 7h4v5h-4a3 3 0 0 0 3 3"/></svg>',
  text: '<svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h10M4 18h7"/></svg>',
  camera: '<svg viewBox="0 0 24 24"><path d="M4 8h3l2-3h6l2 3h3v11H4Z"/><circle cx="12" cy="13" r="3.2"/></svg>',
  play: '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7Z"/></svg>',
  game: '<svg viewBox="0 0 24 24"><rect x="3" y="8" width="18" height="11" rx="4"/><path d="M7 11v5M4.5 13.5h5M15 12h.01M18 15h.01"/></svg>',
  heart: '<svg viewBox="0 0 24 24"><path d="M12 20s-7-4.5-7-9a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 4.5-7 9-7 9Z"/></svg>',
  close: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="m5 13 4 4L19 7"/></svg>',
  chevron: '<svg viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg>',
  refresh: '<svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 0 1 14-5M20 12a8 8 0 0 1-14 5"/><path d="M18 3v4h-4M6 21v-4h4"/></svg>',
  filter: '<svg viewBox="0 0 24 24"><path d="M4 6h16M7 12h10M10 18h4"/></svg>',
  moon: '<svg viewBox="0 0 24 24"><path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.6 6.6 0 0 0 9.8 9.8Z"/></svg>',
  sun: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19"/></svg>',
  info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>',
  note: '<svg viewBox="0 0 24 24"><path d="M5 3h9l5 5v13H5z"/><path d="M14 3v5h5"/></svg>',
  external: '<svg viewBox="0 0 24 24"><path d="M14 4h6v6"/><path d="M20 4 10 14"/><path d="M19 14v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h5"/></svg>',
  eye: '<svg viewBox="0 0 24 24"><path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.6"/></svg>',
};

export function emptyState({ icon = '', title, text, action = '' }) {
  return html`
    <div class="empty">
      <div class="empty__mark" aria-hidden="true"></div>
      <h2>${title}</h2>
      <p>${text}</p>
      ${action ? html`<div style="margin-top:1.1rem">${raw(action)}</div>` : ''}
    </div>`;
}
