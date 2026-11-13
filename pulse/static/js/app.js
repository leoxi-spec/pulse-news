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
import { reelsView } from './views/reels.js';
import { videosView } from './views/videos.js';
import { aboutView, impactView, classroomView, roadmapView } from './views/founder.js';
import { keywordView } from './views/keyword.js';
import { arcadeView } from './views/arcade.js';
import { accountView } from './views/account.js';
import { privacyView, termsView } from './views/legal.js';
import { searchView, savedView, briefView, studyView, profileView, onboardingView } from './views/misc.js';
import { researchView } from './views/research.js';
import { bootPrefsFromStorage } from './store.js';
import { applyAmbient } from './ambient.js';
import { initWeather } from './weather.js';

const NAV = [
  { href: '/', label: 'Home', icon: 'home', mobile: true },
  {
    label: 'Watch', icon: 'play',
    items: [
      { href: '/reels', label: 'Shorts', icon: 'play', hint: 'Full-screen swipeable stories' },
      { href: '/videos', label: 'Videos', icon: 'play', hint: 'Newsroom clips and YouTube' },
      { href: '/arcade', label: 'Arcade', icon: 'game', hint: 'Fifteen brain-break games' },
    ],
  },
  { href: '/discover', label: 'Discover', icon: 'compass', mobile: true },
  { href: '/sports', label: 'Scores', icon: 'trophy' },
  {
    label: 'Read', icon: 'book',
    items: [
      { href: '/brief', label: 'Brief', icon: 'bolt', hint: 'The day in five stories' },
      { href: '/saved', label: 'Saved', icon: 'bookmark', hint: 'Your library and citations' },
      { href: '/study', label: 'Study', icon: 'book', hint: 'Quizzes, glossary and focus', minAge: 8 },
      { href: '/research', label: 'Research', icon: 'quote', hint: 'Citations and bibliography' },
    ],
  },
  {
    label: 'Project', icon: 'info',
    items: [
      { href: '/about', label: 'About', icon: 'info', hint: 'The story and press kit' },
      { href: '/impact', label: 'Impact', icon: 'sparkle', hint: 'Live product and reading data' },
      { href: '/classroom', label: 'Classroom', icon: 'book', hint: 'A 45-minute lesson' },
      { href: '/roadmap', label: 'Roadmap', icon: 'note', hint: 'Vote and send feedback' },
      { href: '/profile', label: 'Profile & settings', icon: 'user', hint: 'Photo, themes and data' },
      { href: '/account', label: 'Account & sync', icon: 'user', hint: 'Keep progress across browsers' },
    ],
  },
];

const BOTTOM = [
  { href: '/', label: 'Home', icon: 'home' },
  { href: '/reels', label: 'Shorts', icon: 'play' },
  { href: '/discover', label: 'Explore', icon: 'compass' },
  { href: '/search', label: 'Search', icon: 'search' },
  { href: '/saved', label: 'Saved', icon: 'bookmark' },
  { href: '/profile', label: 'You', icon: 'user' },
];

function registerRoutes() {
  router.add('/', homeView);
  router.add('/reels', reelsView);
  router.add('/videos', videosView);
  router.add('/about', aboutView);
  router.add('/impact', impactView);
  router.add('/classroom', classroomView);
  router.add('/roadmap', roadmapView);
  router.add('/discover', discoverView);
  router.add('/topic/:slug', topicView);
  router.add('/story/:id', storyView);
  router.add('/article/:id', articleView);
  router.add('/search', searchView);
  router.add('/keyword', keywordView);
  router.add('/arcade', arcadeView);
  router.add('/saved', savedView);
  router.add('/brief', briefView);
  router.add('/study', studyView);
  router.add('/research', researchView);
  router.add('/sports', sportsView);
  router.add('/sources', sourcesView);
  router.add('/source/:id', sourceView);
  router.add('/archive', archiveView);
  router.add('/account', accountView);
  router.add('/privacy', privacyView);
  router.add('/terms', termsView);
  router.add('/profile', profileView);
  router.add('/settings', (root, ctx) => profileView(root, { ...ctx, query: { ...ctx.query, focus: 'settings' } }));
  router.add('/onboarding', onboardingView);
}

function currentPath() {
  return window.location.pathname;
}

function activeNav(href, path) {
  return href === '/' ? path === '/' : path.startsWith(href);
}

function closeNavMenus() {
  document.querySelectorAll('.nav-group.is-open').forEach((group) => {
    group.classList.remove('is-open');
    group.querySelector('.nav-group__trigger')?.setAttribute('aria-expanded', 'false');
  });
}

function renderNav() {
  const path = currentPath();
  const nav = document.getElementById('nav');
  const navAge = Number(state.profile?.survey?.age || 13);
  const visibleNav = NAV.filter((item) => !item.minAge || navAge >= item.minAge);
  if (nav) {
    nav.innerHTML = visibleNav.map((item) => {
      if (!item.items) {
        return html`
          <a class="${activeNav(item.href, path) ? 'is-active' : ''}" href="${item.href}" data-link title="${item.label}">
            ${raw(icons[item.icon] || icons.home)}<span>${item.label}</span>
            ${item.href === '/sports' && state.liveCount ? html`<span class="nav__badge nav__badge--live">${state.liveCount}</span>` : ''}
          </a>`;
      }
      const children = item.items.filter((child) => !child.minAge || navAge >= child.minAge);
      const active = children.some((child) => activeNav(child.href, path));
      return html`
        <div class="nav-group ${active ? 'is-active' : ''}" data-nav-group>
          <button class="nav-group__trigger" type="button" aria-haspopup="true" aria-expanded="false">
            ${raw(icons[item.icon] || icons.home)}<span>${item.label}</span>
            <svg class="nav-group__chev" viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
          </button>
          <div class="nav-menu" role="menu">
            <div class="nav-menu__head">${item.label}</div>
            ${children.map((child) => html`
              <a class="nav-menu__item ${activeNav(child.href, path) ? 'is-active' : ''}" href="${child.href}" data-link role="menuitem">
                <span class="nav-menu__icon">${raw(icons[child.icon] || icons.home)}</span>
                <span><b>${child.label}</b><small>${child.hint}</small></span>
              </a>`)}
          </div>
        </div>`;
    }).join('');
    nav.querySelectorAll('[data-nav-group]').forEach((group) => {
      const trigger = group.querySelector('.nav-group__trigger');
      trigger?.addEventListener('click', (event) => {
        event.stopPropagation();
        const open = !group.classList.contains('is-open');
        closeNavMenus();
        group.classList.toggle('is-open', open);
        trigger.setAttribute('aria-expanded', String(open));
      });
      group.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeNavMenus));
    });
  }
  const bottom = document.getElementById('bottom-nav');
  if (bottom) {
    bottom.innerHTML = BOTTOM.map((item) => html`
      <a class="bottom-nav__item ${activeNav(item.href, path) ? 'is-active' : ''}" href="${item.href}" data-link>
        ${raw(icons[item.icon] || icons.home)}<span>${item.label}</span>
      </a>`).join('');
  }
  const avatar = document.getElementById('avatar');
  if (avatar) {
    const photo = prefs().avatar;
    avatar.classList.toggle('avatar--photo', Boolean(photo));
    avatar.textContent = photo ? '' : profileInitials();
    avatar.style.backgroundImage = photo ? `url("${photo}")` : '';
  }
}

function bindShell() {
  document.addEventListener('click', (event) => {
    if (!event.target.closest('[data-nav-group]')) closeNavMenus();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeNavMenus();
  });
  const mini = document.getElementById('search-mini');
  mini?.addEventListener('submit', (event) => {
    event.preventDefault();
    const input = document.getElementById('search-mini-input');
    const q = input.value.trim();
    if (!q) return;
    router.navigate(`/search?q=${encodeURIComponent(q)}`);
    input.blur();
  });

  document.getElementById('theme-btn')?.addEventListener('click', () => {
    const order = ['dark', 'light', 'sepia', 'system'];
    const next = order[(order.indexOf(prefs().theme || 'system') + 1) % order.length];
    savePrefs({ theme: next }).then(() => {
      renderNav();
      toast(`Theme: ${next}`);
    }).catch((err) => toast(err.message, { type: 'bad' }));
  });

  document.addEventListener('keydown', (event) => {
    const target = event.target;
    const typing = target instanceof HTMLElement && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
    if (event.key === 'Escape') {
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
      if (event.key === 'v') router.navigate('/videos');
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

async function pollLive() {
  try {
    const pinned = (prefs().pinned_sports || []).slice(0, 4);
    const fallback = (prefs().sports_leagues || []).slice(0, 3);
    const leagues = (pinned.length ? pinned : fallback).join(',');
    const data = await get(`/api/sports${leagues ? `?leagues=${leagues}` : ''}`, 30);
    const next = data.live_count || 0;
    if (next !== state.liveCount) {
      state.liveCount = next;
      renderNav();
    }
  } catch { /* scores are optional */ }
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
    const holder = img.closest('.hero, .story-card__media, .article__hero, .row, .mcard, .top-card');
    holder?.classList.add('img-fallback');
  }, true);
}

function setupChrome() {
  const appbar = document.getElementById('appbar');
  const onScroll = () => appbar?.classList.toggle('is-scrolled', window.scrollY > 8);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  const markImages = () => {
    document.querySelectorAll('img:not(.img-loaded)').forEach((img) => {
      if (img.complete && img.naturalWidth) img.classList.add('img-loaded');
      else img.addEventListener('load', () => img.classList.add('img-loaded'), { once: true });
    });
  };
  markImages();
  const view = document.getElementById('view');
  if (view) new MutationObserver(markImages).observe(view, { childList: true, subtree: true });
}

function setupInstall() {
  const button = document.getElementById('install-btn');
  let promptEvent = null;
  const standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    promptEvent = event;
    if (button) button.hidden = false;
  });
  window.pulseInstall = async () => {
    if (promptEvent) {
      promptEvent.prompt();
      await promptEvent.userChoice;
      promptEvent = null;
      button.hidden = true;
      return;
    }
    if (standalone) {
      toast('Pulse is already installed on this device');
      return;
    }
    modal({
      title: 'Install Pulse',
      body: html`
        <p class="small muted">Pulse works as an app, with its own icon and offline shell.</p>
        <div class="stack-sm" style="margin-top:.8rem">
          <p class="small"><b>iPhone / iPad</b><br>Open this page in Safari, tap Share, then <b>Add to Home Screen</b>.</p>
          <p class="small"><b>Android / Chrome</b><br>Open the browser menu and tap <b>Install app</b> (or Add to Home screen).</p>
          <p class="small"><b>Desktop</b><br>Use the install icon in the address bar, or the Install button in this app.</p>
        </div>`,
      actions: [{ label: 'Got it', class: 'btn--primary' }],
    });
  };
  button?.addEventListener('click', () => window.pulseInstall());
}

function setupVersionWatch() {
  const current = state.boot?.app?.version;
  if (!current) return;
  let announced = false;
  const check = async () => {
    try {
      const data = await get('/api/health', 0, true);
      if (data.app?.version && data.app.version !== current && !announced) {
        announced = true;
        toast(`Pulse ${data.app.version} is ready. Reload to update — no reinstall needed.`, {
          duration: 10000,
          actionLabel: 'Reload',
          onAction: () => window.location.reload(),
        });
        navigator.serviceWorker?.getRegistration().then((reg) => reg?.update()).catch(() => {});
      }
    } catch { /* server unavailable */ }
  };
  setInterval(check, 60_000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
}

function setupServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    let hadController = Boolean(navigator.serviceWorker.controller);
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (!hadController) { hadController = true; return; }
      if (sessionStorage.getItem('pulse.sw-reloaded')) return;
      sessionStorage.setItem('pulse.sw-reloaded', '1');
      window.location.reload();
    });
    navigator.serviceWorker.register('/sw.js').then((registration) => {
      const check = () => registration.update().catch(() => {});
      check();
      if (registration.waiting) registration.waiting.postMessage({ type: 'SKIP_WAITING' });
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
      // Installed apps stay open for days. Check on focus and every 15 minutes
      // so a new build does not wait for a full browser restart.
      document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
      window.addEventListener('focus', check);
      setInterval(check, 15 * 60 * 1000);
      setTimeout(() => sessionStorage.removeItem('pulse.sw-reloaded'), 10000);
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
});

on('profile', () => { renderNav(); applyAmbient(); });
on('prefs', () => { applyAmbient(); renderNav(); });
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
  setupChrome();
  setupVersionWatch();
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
      bootEl.innerHTML = `<div class="empty" style="max-width:420px"><div class="empty__mark"></div><h2>Can't reach the Pulse server</h2><p>${err.message}</p><button class="btn btn--primary" style="margin-top:1rem" onclick="location.reload()">Retry</button></div>`;
    }
    return;
  }
  setBoot(data);
  applyAmbient();
  initWeather().catch(() => {});
  document.getElementById('shell').hidden = false;
  if (bootEl) bootEl.remove();
  document.body.dataset.ready = '1';

  renderNav();
  router.start();

  const publicPaths = ['/onboarding', '/account', '/privacy', '/terms'];
  if (!data.profile?.onboarded && !publicPaths.some((path) => location.pathname.startsWith(path))) {
    router.navigate('/onboarding', { replace: true });
  }

  pollBreaking();
  pollLive();
  setInterval(pollBreaking, 240000);
  setInterval(pollLive, 120000);
  setInterval(pollIngest, 90000);

  // Warm the sports cache in the background so the rail is instant next time.
  if (data.sports?.leagues?.length) {
    get('/api/sports', 25).catch(() => {});
  }
}

boot();
