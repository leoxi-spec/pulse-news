import { get, post } from './api.js';
import {
  state, setBoot, on, emit, prefs, savePrefs, toggleSave, profileInitials,
  dailyProgress, streak, levels, followedTopics, topicLabel, setProfile,
} from './store.js';
import {
  html, raw, icons, toast, modal, errorState, esc, timeAgo, compactNumber, registerAction,
  toastProgress, absDate,
} from './ui.js';
import { scoreMini } from './components.js';
import { bindShortcuts as bindPaletteShortcuts, open as openPalette } from './palette.js';
import { openLegend } from './legend.js';
import * as router from './router.js';
import { homeView } from './views/home.js';
import { articleView } from './views/article.js';
import { discoverView, topicView, storyView, archiveView } from './views/discover.js';
import { sourcesView, sourceView } from './views/sources.js';
import { sportsView } from './views/sports.js';
import { searchView, savedView, briefView, studyView, profileView, onboardingView } from './views/misc.js';
import { researchView } from './views/research.js';
import { bootPrefsFromStorage } from './store.js';

const NAV = [
  { href: '/', label: 'Home', icon: 'home', mobile: true },
  { href: '/discover', label: 'Discover', icon: 'compass', mobile: true },
  { href: '/sports', label: 'Scores', icon: 'trophy' },
  { href: '/brief', label: 'Brief', icon: 'bolt' },
  { href: '/saved', label: 'Saved', icon: 'bookmark', mobile: true },
  { href: '/study', label: 'Study', icon: 'book' },
  { href: '/research', label: 'Research', icon: 'quote' },
  { href: '/sources', label: 'Sources', icon: 'filter' },
  { href: '/profile', label: 'Profile', icon: 'user', mobile: true },
];

const BOTTOM = [
  { href: '/', label: 'Home', icon: 'home' },
  { href: '/discover', label: 'Explore', icon: 'compass' },
  { href: '/search', label: 'Search', icon: 'search' },
  { href: '/saved', label: 'Saved', icon: 'bookmark' },
  { href: '/profile', label: 'You', icon: 'user' },
];

function registerRoutes() {
  router.add('/', homeView);
  router.add('/discover', discoverView);
  router.add('/topic/:slug', topicView);
  router.add('/story/:id', storyView);
  router.add('/article/:id', articleView);
  router.add('/search', searchView);
  router.add('/saved', savedView);
  router.add('/brief', briefView);
  router.add('/study', studyView);
  router.add('/research', researchView);
  router.add('/sports', sportsView);
  router.add('/sources', sourcesView);
  router.add('/source/:id', sourceView);
  router.add('/archive', archiveView);
  router.add('/profile', profileView);
  router.add('/settings', (root, ctx) => profileView(root, { ...ctx, query: { ...ctx.query, focus: 'settings' } }));
  router.add('/onboarding', onboardingView);
}

function currentPath() {
  return window.location.pathname;
}

function renderNav() {
  const path = currentPath();
  const isActive = (href) => (href === '/' ? path === '/' : path.startsWith(href));
  const nav = document.getElementById('nav');
  if (nav) {
    nav.innerHTML = html`
      <button class="nav__item nav__search" id="nav-search" type="button">
        ${raw(icons.search)}<span>Search</span><kbd class="kbd" style="margin-left:auto">⌘K</kbd>
      </button>
      ${NAV.map((item) => html`
        <a class="nav__item ${isActive(item.href) ? 'is-active' : ''}" href="${item.href}" data-link title="${item.label}">
          ${raw(icons[item.icon] || icons.home)}<span>${item.label}</span>
          ${item.href === '/sports' && state.liveCount ? html`<span class="nav__badge nav__badge--live">${state.liveCount}</span>` : ''}
        </a>`)}
    `;
  }
  const bottom = document.getElementById('bottom-nav');
  if (bottom) {
    bottom.innerHTML = BOTTOM.map((item) => html`
      <a class="bottom-nav__item ${isActive(item.href) ? 'is-active' : ''}" href="${item.href}" data-link>
        ${raw(icons[item.icon] || icons.home)}<span>${item.label}</span>
      </a>`).join('');
  }
  const avatar = document.getElementById('avatar');
  if (avatar) avatar.textContent = profileInitials();
  const topics = document.getElementById('sidebar-topics');
  if (topics) {
    topics.innerHTML = followedTopics().slice(0, 7).map((slug) => html`
      <a class="topic-mini__item" href="/topic/${slug}" data-link>${state.topicMap.get(slug)?.icon || '•'} ${topicLabel(slug)}</a>`).join('');
  }
  const streakCard = document.getElementById('streak-card');
  if (streakCard) {
    const info = streak();
    const today = dailyProgress();
    const level = levels();
    streakCard.innerHTML = html`
      <div class="streak-card__top">
        <div>
          <div class="hstack" style="gap:.35rem"><span class="streak-card__flame">🔥</span><span class="streak-card__count">${info.count}</span></div>
          <div class="streak-card__label">day streak · best ${info.best}</div>
        </div>
        <span class="badge badge--topic">Lv ${level.level}</span>
      </div>
      <div class="streak-card__goal">
        <span><span>Today's goal</span><span>${today.read}/${today.goal}</span></span>
        <div class="progress" style="margin-top:.3rem"><span style="width:${today.percent}%"></span></div>
      </div>`;
  }
}

function renderRail() {
  const brief = document.getElementById('rail-brief');
  if (brief) {
    const today = dailyProgress();
    brief.innerHTML = html`
      <h3>⚡ Your 2-minute brief</h3>
      <p class="small muted">Five stories, ranked for you, with the context you need before class.</p>
      <div class="progress" style="margin:.7rem 0 .6rem"><span style="width:${today.percent}%"></span></div>
      <div class="between">
        <span class="tiny faint">${today.read} of ${today.goal} today</span>
        <a class="btn btn--sm btn--primary" href="/brief" data-link>Open</a>
      </div>`;
  }
  loadRailSports();
  loadRailTrending();
  const status = document.getElementById('rail-status');
  if (status) {
    const boot = state.boot || {};
    status.innerHTML = html`
      <p><b>${compactNumber(boot.stats?.articles)}</b> articles archived since ${boot.archive?.earliest ? absDate(boot.archive.earliest, false) : 'launch'}.</p>
      <p style="margin-top:.4rem">${boot.feed_health?.healthy}/${boot.feed_health?.total} feeds healthy${boot.feed_health?.blocked ? ` · ${boot.feed_health.blocked} blocked on this network` : ''}.</p>
      <p style="margin-top:.4rem">AI overviews: ${boot.ai?.enabled ? `on (${boot.ai.model})` : 'off'}</p>
      <button class="btn btn--sm btn--ghost" id="rail-refresh" style="margin-top:.6rem">${raw(icons.refresh)} Refresh feeds</button>`;
    status.querySelector('#rail-refresh')?.addEventListener('click', async (event) => {
      event.target.disabled = true;
      try {
        await post('/api/ingest/refresh', {});
        toast('Refreshing feeds in the background', { type: 'good' });
      } catch (err) { toast(err.message, { type: 'bad' }); }
      setTimeout(() => { event.target.disabled = false; }, 5000);
    });
  }
}

async function loadRailSports() {
  const slot = document.getElementById('rail-sports');
  if (!slot) return;
  try {
    const leagues = (prefs().sports_leagues || []).slice(0, 3).join(',');
    const data = await get(`/api/sports${leagues ? `?leagues=${leagues}` : ''}`, 30);
    state.liveCount = data.live_count || 0;
    const events = (data.events || []).slice(0, 3);
    if (!events.length) {
      slot.innerHTML = html`<h3>🏆 Scores</h3><p class="tiny muted">No games scheduled right now.</p><a class="tiny link" href="/sports" data-link>All scores →</a>`;
      return;
    }
    slot.innerHTML = html`
      <h3>🏆 ${data.live_count ? html`<span class="badge badge--live">${data.live_count} live</span>` : 'Scores'}</h3>
      <div class="stack-sm">${events.map((game) => scoreMini(game))}</div>
      <a class="tiny link" href="/sports" data-link style="display:inline-block;margin-top:.5rem">All scores →</a>`;
  } catch {
    slot.innerHTML = '';
  }
}

async function loadRailTrending() {
  const slot = document.getElementById('rail-trending');
  if (!slot) return;
  try {
    const data = await get('/api/discover', 120);
    const items = (data.trending || []).slice(0, 4);
    if (!items.length) { slot.innerHTML = ''; return; }
    slot.innerHTML = html`
      <h3>📈 Trending</h3>
      <div class="row-list">
        ${items.map((story, index) => html`
          <div class="row">
            <span class="row__rank">${index + 1}</span>
            <div class="row__body">
              <a class="row__title" style="font-size:.82rem" href="/article/${story.lead.id}" data-link>${story.title}</a>
              <div class="row__meta"><span>${story.source_count} outlets</span></div>
            </div>
          </div>`)}
      </div>`;
  } catch { slot.innerHTML = ''; }
}

function bindShell() {
  const mini = document.getElementById('search-mini');
  mini?.addEventListener('submit', (event) => {
    event.preventDefault();
    const input = document.getElementById('search-mini-input');
    const q = input.value.trim();
    if (!q) return;
    router.navigate(`/search?q=${encodeURIComponent(q)}`);
    input.blur();
  });

  document.getElementById('sidebar-toggle')?.addEventListener('click', async () => {
    try {
      const next = !(prefs().sidebar_slim !== false);
      await savePrefs({ sidebar_slim: next });
      const button = document.getElementById('sidebar-toggle');
      if (button) {
        button.title = next ? 'Expand sidebar' : 'Collapse sidebar';
        button.setAttribute('aria-label', button.title);
      }
      renderNav();
    } catch (err) { toast(err.message, { type: 'bad' }); }
  });

  document.getElementById('theme-btn')?.addEventListener('click', () => {
    const order = ['dark', 'light', 'sepia', 'system'];
    const next = order[(order.indexOf(prefs().theme || 'system') + 1) % order.length];
    savePrefs({ theme: next }).then(() => {
      renderNav();
      toast(`Theme: ${next}`);
    }).catch((err) => toast(err.message, { type: 'bad' }));
  });

  const menu = document.getElementById('menu-btn');
  const sidebar = document.getElementById('sidebar');
  const scrim = document.getElementById('scrim');
  const setMenu = (open) => {
    sidebar?.classList.toggle('is-open', open);
    menu?.setAttribute('aria-expanded', String(open));
    if (scrim) scrim.hidden = !open;
  };
  menu?.addEventListener('click', () => setMenu(!sidebar?.classList.contains('is-open')));
  scrim?.addEventListener('click', () => setMenu(false));

  document.addEventListener('keydown', (event) => {
    const target = event.target;
    const typing = target instanceof HTMLElement && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
    if (event.key === 'Escape') {
      setMenu(false);
      if (document.body.classList.contains('focus-mode')) {
        document.body.classList.remove('focus-mode');
        toast('Focus mode off');
      }
    } else if (!typing && event.key === '?') {
      openLegend();
    } else if (!typing && event.key === 'g') {
      window.__pulseG = true;
      setTimeout(() => { window.__pulseG = false; }, 800);
    } else if (!typing && window.__pulseG) {
      if (event.key === 'h') router.navigate('/');
      if (event.key === 'd') router.navigate('/discover');
      if (event.key === 's') router.navigate('/search');
      if (event.key === 'b') router.navigate('/brief');
      window.__pulseG = false;
    }
  });

  window.addEventListener('online', () => { state.online = true; toast('Back online', { type: 'good' }); });
  window.addEventListener('offline', () => { state.online = false; toast('You are offline — showing what is cached', { type: 'bad' }); });
  window.addEventListener('pulse:auth-required', showTokenModal);

  // Sidebar search + key buttons survive every nav re-render.
  document.addEventListener('click', (event) => {
    if (event.target.closest('#nav-search')) {
      event.preventDefault();
      openPalette();
    }
    if (event.target.closest('#legend-btn')) {
      event.preventDefault();
      openLegend();
    }
  });
}

function showShortcuts() {
  modal({
    title: 'Keyboard shortcuts',
    body: html`
      <div class="stack-sm small">
        ${[['/', 'Focus search'], ['g then h', 'Home'], ['g then d', 'Discover'], ['g then s', 'Search'], ['g then b', 'Brief'],
          ['Esc', 'Close menu / leave focus mode'], ['?', 'This dialog']].map(([key, label]) => html`
          <div class="between"><span>${label}</span><kbd class="kbd">${key}</kbd></div>`)}
      </div>`,
    actions: [{ label: 'Got it', class: 'btn--ghost' }],
  });
}

function showTokenModal() {
  if (document.getElementById('token-modal')) return;
  const input = document.createElement('input');
  input.type = 'password';
  input.placeholder = 'PULSE_ACCESS_TOKEN';
  input.id = 'token-modal';
  const { close } = modal({
    title: 'Access token required',
    body: html`<p class="small muted" style="margin-bottom:.7rem">This server is protected. Paste the access token you configured with <span class="mono">PULSE_ACCESS_TOKEN</span>.</p>`,
    actions: [
      { label: 'Cancel', class: 'btn--ghost' },
      {
        label: 'Continue',
        class: 'btn--primary',
        onClick: () => {
          const token = encodeURIComponent(input.value.trim());
          if (!token) return false;
          window.location.href = `${window.location.pathname}?token=${token}`;
          return true;
        },
      },
    ],
  });
  document.querySelector('#modal-root .modal__body')?.append(input);
  input.focus();
  void close;
}

async function pollBreaking() {
  if (!(prefs().notify_breaking ?? true)) return;
  try {
    const data = await get('/api/feed?mode=breaking&limit=4', 0, true);
    const items = (data.items || []).filter((item) => item.breaking);
    const ids = new Set(items.map((item) => item.id));
    const seen = new Set(JSON.parse(localStorage.getItem('pulse.breaking') || '[]'));
    const fresh = items.filter((item) => !seen.has(item.id));
    localStorage.setItem('pulse.breaking', JSON.stringify([...ids].slice(-40)));
    const btn = document.getElementById('breaking-btn');
    if (btn) {
      btn.hidden = items.length === 0;
      btn.classList.toggle('icon-btn--live', items.length > 0);
      btn.title = items.length ? `${items.length} breaking` : '';
      btn.innerHTML = icons.bolt;
      btn.onclick = () => router.navigate('/?stream=breaking');
    }
    if (fresh.length && seen.size) {
      const item = fresh[0];
      toast(`Breaking: ${item.title}`, {
        type: 'bad',
        duration: 6500,
        actionLabel: 'Read',
        onAction: () => router.navigate(`/article/${item.id}`),
      });
    }
  } catch { /* quiet */ }
}

async function pollIngest() {
  try {
    const data = await get('/api/ingest/status', 0, true);
    if (data.running) {
      toast('Feeds refreshing…', { duration: 1800 });
      setTimeout(pollIngest, 6000);
      return;
    }
    if (data.last_run && Date.now() - new Date(data.last_run.finished_at).getTime() < 15000) {
      const boot = await get('/api/bootstrap', 0, true);
      setBoot(boot);
      renderRail();
      renderNav();
      toast('Feed refreshed', { type: 'good' });
    }
  } catch { /* quiet */ }
}

function setupImageFallbacks() {
  document.addEventListener('error', (event) => {
    const img = event.target;
    if (!(img instanceof HTMLImageElement)) return;
    if (img.dataset.failed) return;
    img.dataset.failed = '1';
    img.classList.add('img-broken');
    const holder = img.closest('.hero, .story-card__media, .article__hero, .row');
    holder?.classList.add('img-fallback');
  }, true);
}

function setupInstall() {
  const button = document.getElementById('install-btn');
  let promptEvent = null;
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    promptEvent = event;
    if (button) button.hidden = false;
  });
  button?.addEventListener('click', async () => {
    if (!promptEvent) return;
    promptEvent.prompt();
    await promptEvent.userChoice;
    promptEvent = null;
    button.hidden = true;
  });
}

function setupServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').then((registration) => {
      registration.addEventListener('updatefound', () => {
        const worker = registration.installing;
        worker?.addEventListener('statechange', () => {
          if (worker.state === 'installed' && navigator.serviceWorker.controller) {
            toast('A new Pulse version is ready. Reload to update.', {
              duration: 8000,
              actionLabel: 'Reload',
              onAction: () => window.location.reload(),
            });
          }
        });
      });
    }).catch((err) => console.warn('sw registration failed', err));
  });
}

registerAction('toggle-save', async (button) => {
  const id = Number(button.dataset.id);
  if (!Number.isFinite(id)) return;
  const isSaved = button.getAttribute('aria-pressed') === 'true';
  const { saved } = await toggleSave({ id, saved: isSaved });
  button.classList.toggle('is-on', saved);
  button.setAttribute('aria-pressed', String(saved));
  button.setAttribute('aria-label', saved ? 'Remove from saved' : 'Save story');
  button.title = saved ? 'Saved' : 'Save';
  toast(saved ? 'Saved to your library' : 'Removed from saved', { duration: 1600 });
  const rail = document.getElementById('rail-brief');
  if (rail) renderRail();
});

on('profile', () => { renderNav(); renderRail(); });
on('save', ({ id, saved }) => {
  document.querySelectorAll(`[data-action="toggle-save"][data-id="${id}"]`).forEach((button) => {
    button.classList.toggle('is-on', saved);
    button.setAttribute('aria-pressed', String(saved));
  });
});
on('progress', (progress) => { toastProgress(progress); renderNav(); });

async function boot() {
  bootPrefsFromStorage();
  bindPaletteShortcuts();
  setupServiceWorker();
  setupImageFallbacks();
  setupInstall();
  bindShell();
  registerRoutes();

  const bootEl = document.getElementById('boot');
  let data;
  try {
    data = await Promise.race([
      get('/api/bootstrap', 0, true),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 20000)),
    ]);
  } catch (err) {
    if (bootEl) {
      bootEl.innerHTML = `<div class="empty" style="max-width:420px"><div class="empty__icon">📡</div><h2>Can't reach the Pulse server</h2><p>${err.message}</p><button class="btn btn--primary" style="margin-top:1rem" onclick="location.reload()">Retry</button></div>`;
    }
    return;
  }
  setBoot(data);
  document.getElementById('shell').hidden = false;
  if (bootEl) bootEl.remove();
  document.body.dataset.ready = '1';

  renderNav();
  renderRail();
  router.start();

  if (!data.profile?.onboarded && !location.pathname.startsWith('/onboarding')) {
    router.navigate('/onboarding', { replace: true });
  }

  pollBreaking();
  setInterval(pollBreaking, 240000);
  setInterval(() => { if (!document.hidden) loadRailSports(); }, 45000);
  setInterval(pollIngest, 90000);

  // Warm the sports cache in the background so the rail is instant next time.
  if (data.sports?.leagues?.length) {
    get('/api/sports', 25).catch(() => {});
  }
}

boot();
