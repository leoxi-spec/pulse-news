import { errorState } from './ui.js';
import { emptyState } from './components.js';

const routes = [];
const scrollMemory = new Map();

function compile(pattern) {
  const keys = [];
  const source = pattern.replace(/\/:([A-Za-z_]+)/g, (_, key) => { keys.push(key); return '/([^/]+)'; });
  return { regex: new RegExp(`^${source}/?$`), keys };
}

export function add(pattern, handler) {
  routes.push({ pattern, ...compile(pattern), handler });
}

export function parseQuery(search) {
  const query = {};
  new URLSearchParams(search || '').forEach((value, key) => { query[key] = value; });
  return query;
}

export async function render(url = window.location.pathname + window.location.search, { restoreScroll = false } = {}) {
  const [path, search = ''] = url.split('?');
  const query = parseQuery(search);
  let match = null;
  for (const route of routes) {
    const result = route.regex.exec(path);
    if (result) {
      const params = {};
      route.keys.forEach((key, i) => { params[key] = decodeURIComponent(result[i + 1]); });
      match = { route, params };
      break;
    }
  }
  const view = document.getElementById('view');
  if (!view) return;
  if (!match) {
    view.innerHTML = emptyState({
      icon: '🧭',
      title: 'Page not found',
      text: `There is nothing at ${path}. Try the feed, discover or search.`,
      action: '<a class="btn btn--primary" href="/" data-link>Back to feed</a>',
    });
    return;
  }
  const context = { path, query, params: match.params, url };
  window.__pulseRoute = context;
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  document.body.classList.toggle('onboarding-mode', path === '/onboarding');
  document.body.classList.toggle('reels-mode', path === '/reels');
  document.title = 'Pulse — Student News';

  // Move to the top *before* rendering. Doing it after the async handler used
  // to yank the viewport back down while you were already scrolling a
  // half-loaded page.
  if (restoreScroll && scrollMemory.has(path)) {
    window.scrollTo({ top: scrollMemory.get(path), behavior: 'instant' });
  } else {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }

  try {
    await match.route.handler(view, context);
  } catch (err) {
    console.error('route failed', path, err);
    errorState(view, err?.message || 'This page failed to load.', () => render(url));
  }
  view.classList.remove('page-enter');
  void view.offsetWidth;
  view.classList.add('page-enter');
  const main = document.getElementById('main');
  if (main && !restoreScroll) main.focus({ preventScroll: true });
}

export function navigate(url, { replace = false } = {}) {
  const current = window.location.pathname + window.location.search;
  scrollMemory.set(window.location.pathname, window.scrollY);
  if (url === current) {
    render(url);
    return;
  }
  window.history[replace ? 'replaceState' : 'pushState']({}, '', url);
  render(url);
}

export function start() {
  document.addEventListener('click', (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a');
    if (!link) return;
    const href = link.getAttribute('href');
    if (!href || link.target || link.hasAttribute('download') || href.startsWith('http') || href.startsWith('#')) return;
    if (link.dataset.external !== undefined) return;
    event.preventDefault();
    navigate(href);
  });
  window.addEventListener('popstate', () => {
    render(window.location.pathname + window.location.search, { restoreScroll: true });
  });
  render();
}
