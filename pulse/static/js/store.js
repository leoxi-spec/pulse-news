import { get, patch, post, del, invalidate } from './api.js';

export const state = {
  boot: null,
  profile: null,
  topicMap: new Map(),
  sourceMap: new Map(),
  route: null,
  online: navigator.onLine,
  feedCache: new Map(),
};

const listeners = new Map();
export function on(event, fn) {
  if (!listeners.has(event)) listeners.set(event, new Set());
  listeners.get(event).add(fn);
  return () => listeners.get(event)?.delete(fn);
}
export function emit(event, detail) {
  listeners.get(event)?.forEach((fn) => {
    try { fn(detail); } catch (err) { console.error(err); }
  });
}

export function setBoot(boot) {
  state.boot = boot;
  state.topicMap = new Map((boot.topics || []).map((t) => [t.slug, t]));
  state.sourceMap = new Map((boot.sources || []).map((s) => [s.id, s]));
  if (boot.profile) setProfile(boot.profile, { silent: true });
  emit('boot', boot);
}

export function setProfile(profile, { silent = false } = {}) {
  if (!profile) return;
  state.profile = profile;
  applyPrefs(profile.prefs || {});
  if (!silent) emit('profile', profile);
}

export const getProfile = () => state.profile;
export const prefs = () => state.profile?.prefs || {};
export const isOnboarded = () => Boolean(state.profile?.onboarded);

export function topicLabel(slug) {
  return state.topicMap.get(slug)?.label || (slug ? slug[0].toUpperCase() + slug.slice(1) : '');
}
export function topicIcon(slug) {
  return state.topicMap.get(slug)?.icon || '•';
}
export function sourceOf(id) {
  return state.sourceMap.get(id) || null;
}

const THEME_COLORS = {
  dark: '#0a0c11', light: '#f6f7fb', sepia: '#f4ecd8', midnight: '#060a14',
  forest: '#08110c', sunset: '#140a0b', mono: '#0c0c0d', rose: '#fff6f8', ocean: '#f2f8fc',
};

export const THEMES = [
  { id: 'system', label: 'Auto', bg: 'linear-gradient(135deg,#0a0c11 50%,#f6f7fb 50%)', text: '#ffffff', grad: 'linear-gradient(120deg,#7c5cff,#ff4d8d)' },
  { id: 'dark', label: 'Dark', bg: '#0a0c11', text: '#eef1f6', grad: 'linear-gradient(120deg,#7c5cff,#ff4d8d)' },
  { id: 'light', label: 'Light', bg: '#f6f7fb', text: '#10131a', grad: 'linear-gradient(120deg,#7c5cff,#ff4d8d)' },
  { id: 'sepia', label: 'Sepia', bg: '#f4ecd8', text: '#2c2418', grad: 'linear-gradient(120deg,#b45309,#d97706)' },
  { id: 'midnight', label: 'Midnight', bg: '#060a14', text: '#eaf2ff', grad: 'linear-gradient(120deg,#4d8dff,#7c5cff)' },
  { id: 'forest', label: 'Forest', bg: '#08110c', text: '#e9f7ee', grad: 'linear-gradient(120deg,#22c55e,#a3e635)' },
  { id: 'sunset', label: 'Sunset', bg: '#140a0b', text: '#fff1ec', grad: 'linear-gradient(120deg,#ff7a59,#ffd166)' },
  { id: 'mono', label: 'Mono', bg: '#0c0c0d', text: '#f4f4f5', grad: 'linear-gradient(120deg,#f4f4f5,#a1a1aa)' },
  { id: 'rose', label: 'Rose', bg: '#fff6f8', text: '#2a1219', grad: 'linear-gradient(120deg,#e11d74,#f97316)' },
  { id: 'ocean', label: 'Ocean', bg: '#f2f8fc', text: '#0b2233', grad: 'linear-gradient(120deg,#0284c7,#06b6d4)' },
];

const TEXT_SCALES = [0.92, 1, 1.08, 1.18, 1.3];
const MEDIA = window.matchMedia('(prefers-color-scheme: light)');

export function resolveTheme(theme) {
  if (theme === 'system') return MEDIA.matches ? 'light' : 'dark';
  return theme || 'dark';
}

export function applyPrefs(p) {
  const theme = resolveTheme(p.theme);
  document.documentElement.dataset.theme = theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', THEME_COLORS[theme] || '#0a0c11');
  document.body.classList.toggle('font-serif', p.font === 'serif');
  document.body.classList.toggle('font-dyslexic', p.font === 'dyslexic');
  document.body.classList.toggle('contrast-high', Boolean(p.high_contrast));
  document.body.classList.toggle('reduce-motion', Boolean(p.reduce_motion));
  const scale = TEXT_SCALES[Math.max(0, Math.min(4, Number(p.text_size) || 0))] || 1;
  document.documentElement.style.setProperty('--text-scale', String(scale));
  try {
    localStorage.setItem('pulse.prefs', JSON.stringify({ theme: p.theme, font: p.font, text_size: p.text_size }));
  } catch { /* storage may be full or blocked */ }
}

export function bootPrefsFromStorage() {
  try {
    const saved = JSON.parse(localStorage.getItem('pulse.prefs') || '{}');
    if (saved.theme) applyPrefs(saved);
  } catch { /* ignore */ }
}

export async function savePrefs(patchObj, { quiet = false } = {}) {
  const previous = state.profile?.prefs;
  if (state.profile) {
    state.profile = { ...state.profile, prefs: { ...state.profile.prefs, ...patchObj } };
    applyPrefs(state.profile.prefs);
    emit('prefs', state.profile.prefs);
  }
  try {
    const result = await patch('/api/profile', { prefs: patchObj });
    if (result.profile) setProfile(result.profile, { silent: quiet });
    return result.profile;
  } catch (err) {
    if (state.profile && previous) {
      state.profile = { ...state.profile, prefs: previous };
      applyPrefs(previous);
      emit('prefs', previous);
    }
    throw err;
  }
}

export async function saveSurvey(survey, { onboarded = null, name = null } = {}) {
  const result = await patch('/api/profile', { survey, onboarded, name });
  if (result.profile) setProfile(result.profile);
  return result.profile;
}

export async function record(kind, { articleId = null, storyId = null, value = 0, meta = null, silent = false } = {}) {
  try {
    const result = await post('/api/events', { kind, article_id: articleId, story_id: storyId, value, meta });
    if (result.profile) setProfile(result.profile, { silent: true });
    emit('progress', result.progress);
    if (!silent) emit('activity', { kind, articleId });
    return result.progress;
  } catch (err) {
    if (!silent) console.warn('event failed', kind, err.message);
    return null;
  }
}

export async function toggleSave(item, collection = 'Saved') {
  const saved = !item.saved;
  const result = saved
    ? await post(`/api/articles/${item.id}/save`, { collection })
    : await del(`/api/articles/${item.id}/save`);
  item.saved = saved;
  emit('save', { id: item.id, saved });
  if (saved) record('save', { articleId: item.id });
  invalidate('/api/saved');
  return { saved, collections: result.collections };
}

export async function refreshBootstrap() {
  const boot = await get('/api/bootstrap', 0, true);
  setBoot(boot);
  return boot;
}

export function followedTopics() {
  const survey = state.profile?.survey || {};
  const topics = Object.entries(survey.topics || {}).filter(([, v]) => Number(v) > 0).sort((a, b) => b[1] - a[1]).map(([k]) => k);
  return topics.length ? topics : ['world', 'tech', 'sports'];
}

export function isFollowedTopic(slug) {
  const topics = state.profile?.survey?.topics || {};
  return Number(topics[slug] || 0) >= 1;
}

export function profileInitials() {
  const name = (state.profile?.name || 'Student').trim();
  const parts = name.split(/\s+/).filter(Boolean);
  if (!parts.length) return 'S';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function dailyProgress() {
  return state.profile?.today || { read: 0, goal: 5, percent: 0, minutes: 0, xp: 0 };
}

export function levels() {
  const p = state.profile;
  return { level: p?.level || 1, title: p?.level_title || 'Rookie', progress: p?.level_progress || { into: 0, needed: 60, percent: 0 }, xp: p?.xp || 0 };
}

export function streak() {
  return state.profile?.streak || { count: 0, best: 0, active_today: false };
}
