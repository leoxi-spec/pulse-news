// Live Toronto weather theme: Open-Meteo through Pulse's own backend.
import { get } from './api.js';
import { prefs, on } from './store.js';
import { html, raw, icons } from './ui.js';
import { setAnimation } from './ambient.js';

let weather = null;
let loading = false;
let lastFetch = 0;
let clockTimer = null;

const TORONTO = { timeZone: 'America/Toronto', hour: 'numeric', minute: '2-digit' };
const clock = () => new Intl.DateTimeFormat('en-CA', TORONTO).format(new Date());
const temp = (value) => (value == null ? '—' : `${Math.round(Number(value))}°`);

export function weatherWidget() {
  return html`
    <div class="weather-strip" data-weather-card>
      <div class="weather-strip__main">
        <span class="weather-strip__place">${raw(icons.compass)} Toronto</span>
        <b data-weather-temp>—</b>
        <span data-weather-cond>Loading live weather…</span>
      </div>
      <div class="weather-strip__side">
        <span data-weather-clock>${clock()}</span>
        <span data-weather-meta>Open-Meteo</span>
      </div>
    </div>`;
}

function paint(root = document) {
  root.querySelectorAll('[data-weather-card]').forEach((card) => {
    const tempEl = card.querySelector('[data-weather-temp]');
    const condEl = card.querySelector('[data-weather-cond]');
    const clockEl = card.querySelector('[data-weather-clock]');
    const metaEl = card.querySelector('[data-weather-meta]');
    if (clockEl) clockEl.textContent = clock();
    if (!weather) {
      if (condEl) condEl.textContent = 'Weather unavailable';
      if (metaEl) metaEl.textContent = 'Toronto';
      return;
    }
    if (!weather.available) {
      if (tempEl) tempEl.textContent = '—';
      if (condEl) condEl.textContent = 'Live weather unavailable';
      if (metaEl) metaEl.textContent = 'Open-Meteo · Toronto';
      return;
    }
    if (tempEl) tempEl.textContent = temp(weather.temperature);
    if (condEl) condEl.textContent = weather.condition_label;
    if (metaEl) metaEl.textContent = `Feels ${temp(weather.feels_like)} · ${weather.wind_kmh} km/h · ${weather.stale ? 'cached' : 'live'}`;
  });
}

export function applyWeatherTheme() {
  const root = document.documentElement;
  const onNow = Boolean(prefs().weather_theme) && Boolean(weather?.available);
  if (onNow) {
    root.dataset.weatherTheme = weather.condition;
    root.dataset.weatherAnimation = weather.animation;
    setAnimation(weather.animation);
  } else {
    delete root.dataset.weatherTheme;
    delete root.dataset.weatherAnimation;
    setAnimation(prefs().animation || 'theme');
  }
}

export async function refreshWeather(force = false) {
  if (loading) return weather;
  if (!force && weather && Date.now() - lastFetch < 10 * 60 * 1000) {
    paint();
    applyWeatherTheme();
    return weather;
  }
  loading = true;
  try {
    weather = await get('/api/weather', 60);
    lastFetch = Date.now();
    paint();
    applyWeatherTheme();
  } catch {
    weather = { available: false, location: 'Toronto' };
    paint();
    applyWeatherTheme();
  } finally {
    loading = false;
  }
  return weather;
}

export async function initWeather() {
  await refreshWeather(true);
  on('prefs', () => applyWeatherTheme());
  on('profile', () => { paint(); applyWeatherTheme(); });
  if (!clockTimer) {
    clockTimer = setInterval(() => paint(), 30_000);
    setInterval(() => refreshWeather(), 10 * 60 * 1000);
  }
  // Home and profile call mountWeather() after rendering; no MutationObserver
  // here, because painting text would otherwise retrigger itself forever.
}

export function mountWeather(root = document) {
  paint(root);
  applyWeatherTheme();
}
