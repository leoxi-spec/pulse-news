import { get, patch, post, del, invalidate } from './api.js';
import { toast, confetti } from './ui.js';

export const state = {
  boot: null,
  profile: null,
  account: null,
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
  state.account = boot.account || null;
  emit('account', state.account);
  emit('boot', boot);
}

const PROFILE_BACKUP_KEY = 'pulse.profile.backup';

function backupProfile(profile) {
  if (!profile?.onboarded) return;
  try {
    localStorage.setItem(PROFILE_BACKUP_KEY, JSON.stringify({
      name: profile.name || '',
      survey: profile.survey || {},
      prefs: profile.prefs || {},
      onboarded: true,
      saved_at: new Date().toISOString(),
    }));
  } catch { /* browser storage may be unavailable */ }
}

export function loadProfileBackup() {
  try {
    const value = JSON.parse(localStorage.getItem(PROFILE_BACKUP_KEY) || 'null');
    return value && value.onboarded && value.survey && typeof value.survey === 'object' ? value : null;
  } catch { return null; }
}

export function clearProfileBackup() {
  try { localStorage.removeItem(PROFILE_BACKUP_KEY); } catch { /* ignore */ }
}

export function setProfile(profile, { silent = false } = {}) {
  if (!profile) return;
  state.profile = profile;
  applyPrefs(profile.prefs || {});
  backupProfile(profile);
  if (!silent) emit('profile', profile);
}

export function setAccount(account) {
  state.account = account || null;
  emit('account', state.account);
}

export const getProfile = () => state.profile;
export const prefs = () => state.profile?.prefs || {};
export const isOnboarded = () => Boolean(state.profile?.onboarded);

export function topicLabel(slug) {
  return state.topicMap.get(slug)?.label || (slug ? slug[0].toUpperCase() + slug.slice(1) : '');
}
export function topicIcon(slug) {
  const label = topicLabel(slug);
  const letters = (label.match(/[A-Za-z]/g) || []).slice(0, 2).join('');
  return letters ? letters.toUpperCase() : 'N';
}
export function sourceOf(id) {
  return state.sourceMap.get(id) || null;
}

const THEME_COLORS = {
  dark: '#0a0c11', light: '#f6f7fb', sepia: '#f4ecd8', midnight: '#060a14',
  forest: '#08110c', sunset: '#140a0b', mono: '#0c0c0d', rose: '#fff6f8', ocean: '#f2f8fc',
  dusk: '#14131a', sage: '#eef2ea', sand: '#f5efe6', mist: '#eef2f5', clay: '#f7eee9',
  lavender: '#f4f1fb', mint: '#edf9f3', peach: '#fff3ec', sky: '#eef7fe', cocoa: '#1a1412',
  honey: '#fdf7e7', seafoam: '#eefaf7', cloud: '#f7f8fc', twilight: '#171726', matcha: '#f1f6ea',
};

export const AGE_BANDS = [
  { id: 'junior', label: 'Junior', min: 6, max: 8, mode: 'kids', goal: 2, length: 'short', scale: 1.15, blurb: 'Big pictures, play and gentle news' },
  { id: 'kids', label: 'Kids', min: 9, max: 11, mode: 'kids', goal: 3, length: 'short', scale: 1.08, blurb: 'Quizzes, explainers and bigger type' },
  { id: 'tween', label: 'Tween', min: 12, max: 14, mode: 'teens', goal: 5, length: 'medium', scale: 1, blurb: 'The full feed, training wheels off' },
  { id: 'teen', label: 'Teen', min: 15, max: 16, mode: 'teens', goal: 6, length: 'medium', scale: 1, blurb: 'Deeper reads and study tools' },
  { id: 'senior', label: 'Senior', min: 17, max: 18, mode: 'teens', goal: 8, length: 'long', scale: 1, blurb: 'Research mode and long reads' },
];

export function ageBand(age) {
  const value = Math.max(6, Math.min(18, Number(age) || 13));
  return AGE_BANDS.find((band) => value >= band.min && value <= band.max) || AGE_BANDS[3];
}

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
  { id: 'dusk', label: 'Dusk', bg: '#14131a', text: '#eceaf5', grad: 'linear-gradient(120deg,#a78bfa,#f0abfc)' },
  { id: 'sage', label: 'Sage', bg: '#eef2ea', text: '#1f2a1c', grad: 'linear-gradient(120deg,#5f8d63,#a3b18a)' },
  { id: 'sand', label: 'Sand', bg: '#f5efe6', text: '#2b2519', grad: 'linear-gradient(120deg,#b08968,#d4a373)' },
  { id: 'mist', label: 'Mist', bg: '#eef2f5', text: '#16242c', grad: 'linear-gradient(120deg,#5f8aa6,#a3c4d4)' },
  { id: 'clay', label: 'Clay', bg: '#f7eee9', text: '#2e211a', grad: 'linear-gradient(120deg,#c97c5d,#e0a17c)' },
  { id: 'lavender', label: 'Lavender', bg: '#f4f1fb', text: '#241f33', grad: 'linear-gradient(120deg,#8b7ad6,#c4a7e7)' },
  { id: 'mint', label: 'Mint', bg: '#edf9f3', text: '#122620', grad: 'linear-gradient(120deg,#3f9d7d,#8fd4b8)' },
  { id: 'peach', label: 'Peach', bg: '#fff3ec', text: '#2d1d15', grad: 'linear-gradient(120deg,#d97c55,#f2b8a0)' },
  { id: 'sky', label: 'Sky', bg: '#eef7fe', text: '#102433', grad: 'linear-gradient(120deg,#3f8bc9,#9ec9ea)' },
  { id: 'cocoa', label: 'Cocoa', bg: '#1a1412', text: '#f7ece4', grad: 'linear-gradient(120deg,#c98f6a,#e8c3a0)' },
  { id: 'honey', label: 'Honey', bg: '#fdf7e7', text: '#2c2410', grad: 'linear-gradient(120deg,#c99a2e,#e8c766)' },
  { id: 'seafoam', label: 'Seafoam', bg: '#eefaf7', text: '#102622', grad: 'linear-gradient(120deg,#2f9d8e,#8fd4c8)' },
  { id: 'cloud', label: 'Cloud', bg: '#f7f8fc', text: '#1b2033', grad: 'linear-gradient(120deg,#6f7db8,#b4bfe3)' },
  { id: 'twilight', label: 'Twilight', bg: '#171726', text: '#efedff', grad: 'linear-gradient(120deg,#8d8bf0,#c4b5fd)' },
  { id: 'matcha', label: 'Matcha', bg: '#f1f6ea', text: '#1e2a16', grad: 'linear-gradient(120deg,#6f9445,#b5c98f)' },
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
  document.body.classList.toggle('sidebar-slim', p.sidebar_slim !== false);
  document.body.classList.toggle('no-images', p.show_images === false);
  document.body.classList.toggle('hide-why', p.show_why === false);
  document.body.classList.toggle('compact-cards', Boolean(p.compact_cards));
  document.body.classList.toggle('no-confetti', p.confetti === false);
  document.body.classList.toggle('no-haptics', p.haptics === false);
  const age = Number(state.profile?.survey?.age || 13);
  const band = ageBand(age);
  const mode = p.mode === 'kids' ? 'kids' : p.mode === 'teens' ? 'teens' : band.mode;
  document.body.dataset.mode = mode;
  document.body.dataset.band = band.id;
  document.body.classList.toggle('mode-kids', mode === 'kids');
  const scale = (TEXT_SCALES[Math.max(0, Math.min(4, Number(p.text_size) || 0))] || 1)
    * Math.max(band.scale || 1, mode === 'kids' ? 1.06 : 1);
  document.documentElement.style.setProperty('--text-scale', String(scale));
  document.documentElement.style.setProperty('--line-height', String(p.line_spacing || 1.72));
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
    const beforeLevel = state.profile?.level || 1;
    const result = await post('/api/events', { kind, article_id: articleId, story_id: storyId, value, meta });
    if (result.profile) setProfile(result.profile, { silent: true });
    if (result.profile && Number(result.profile.level) > Number(beforeLevel)) {
      confetti(90);
      toast(`Level up — you are now level ${result.profile.level}.`, { type: 'good' });
    }
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
