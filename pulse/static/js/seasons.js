// Seasonal themes and icons. The server owns the holiday calendar; this module
// only applies the active palette, favicon and header mark.
import { get } from './api.js';
import { on, prefs, resolveTheme } from './store.js';

const TOKEN_KEYS = [
  '--bg', '--bg-alt', '--surface', '--surface-2', '--surface-3', '--line', '--line-soft',
  '--text', '--text-2', '--muted', '--faint', '--accent', '--accent-2', '--accent-3',
  '--accent-ink', '--grad', '--grad-soft',
];

const BASE_THEME_COLORS = {
  dark: '#0a0c11', light: '#f6f7fb', sepia: '#f4ecd8', midnight: '#060a14',
  forest: '#08110c', sunset: '#140a0b', mono: '#0c0c0d', rose: '#fff6f8', ocean: '#f2f8fc',
  dusk: '#14131a', sage: '#eef2ea', sand: '#f5efe6', mist: '#eef2f5', clay: '#f7eee9',
  lavender: '#f4f1fb', mint: '#edf9f3', peach: '#fff3ec', sky: '#eef7fe', cocoa: '#1a1412',
  honey: '#fdf7e7', seafoam: '#eefaf7', cloud: '#f7f8fc', twilight: '#171726', matcha: '#f1f6ea',
};

let payload = null;

function enabled() {
  return prefs().seasonal_themes !== false;
}

function clearTokens() {
  for (const key of TOKEN_KEYS) document.documentElement.style.removeProperty(key);
}

function setIcons(active) {
  const icon = active?.icon || payload?.normal?.icon;
  if (!icon) return;
  const favicon = document.getElementById('app-favicon');
  const touch = document.getElementById('app-touch-icon');
  if (favicon) {
    favicon.href = icon.small;
    favicon.type = 'image/png';
  }
  if (touch) touch.href = icon.apple;
  document.querySelectorAll('[data-season-icon]').forEach((image) => {
    image.src = icon.small;
    image.hidden = !active;
    image.alt = active ? `${active.label} icon` : '';
    image.closest('.brand')?.classList.toggle('has-season', Boolean(active));
  });
}

export function applySeason(data = payload) {
  const active = enabled() ? data?.active : null;
  const root = document.documentElement;
  clearTokens();
  if (active?.palette) {
    for (const [key, value] of Object.entries(active.palette)) {
      if (TOKEN_KEYS.includes(key) && value) root.style.setProperty(key, value);
    }
    root.dataset.season = active.id;
    root.dataset.seasonLabel = active.label;
  } else {
    delete root.dataset.season;
    delete root.dataset.seasonLabel;
  }
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    const theme = resolveTheme(prefs().theme || 'dark');
    meta.setAttribute('content', active?.palette?.['--bg'] || BASE_THEME_COLORS[theme] || '#0a0c11');
  }
  setIcons(active);
  window.dispatchEvent(new CustomEvent('pulse:season', { detail: { active } }));
}

async function refresh() {
  try {
    payload = await get('/api/season', 0, true);
    applySeason(payload);
  } catch {
    // Keep the normal theme if the season endpoint is unavailable.
  }
}

export async function initSeasons() {
  await refresh();
  on('prefs', () => applySeason(payload));
  on('profile', () => applySeason(payload));
  setInterval(refresh, 6 * 60 * 60 * 1000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refresh();
  });
}
