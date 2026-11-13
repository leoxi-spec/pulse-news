// Ambient layer: gentle full-screen particle animations and focus noise.
// Both are opt-in, persisted in prefs, and never autoplay audio without a tap.
import { prefs, savePrefs } from './store.js';
import { toast } from './ui.js';

const THEME_ANIMATIONS = {
  forest: 'leaves', sage: 'leaves', matcha: 'leaves', mint: 'fireflies',
  ocean: 'bubbles', seafoam: 'bubbles', sky: 'birds', cloud: 'snow',
  dusk: 'stars', twilight: 'stars', midnight: 'stars',
  sunset: 'petals', rose: 'petals', peach: 'petals', clay: 'petals',
  mist: 'rain', lavender: 'fireflies', honey: 'fireflies', cocoa: 'snow',
  sand: 'leaves', sepia: 'leaves', light: 'none', dark: 'none', mono: 'none',
};

const DEFAULTS = {
  rain: { count: 150, speed: 2.6, color: 'rgba(170,210,255,.62)' },
  snow: { count: 70, speed: 0.35, color: 'rgba(255,255,255,.8)' },
  meteors: { count: 9, speed: 1.1, color: 'rgba(255,220,150,.9)' },
  birds: { count: 12, speed: 0.35, color: 'rgba(255,255,255,.55)' },
  bubbles: { count: 40, speed: 0.25, color: 'rgba(150,220,255,.45)' },
  stars: { count: 90, speed: 0.15, color: 'rgba(255,255,255,.8)' },
  leaves: { count: 26, speed: 0.45, color: 'rgba(180,220,140,.6)' },
  fireflies: { count: 34, speed: 0.2, color: 'rgba(255,230,140,.9)' },
  petals: { count: 42, speed: 0.4, color: 'rgba(255,180,205,.7)' },
  aurora: { count: 4, speed: 0.06, color: 'rgba(140,255,220,.2)' },
};

let canvas = null;
let ctx = null;
let particles = [];
let animation = 'none';
let raf = 0;
let splashes = [];
let lastFrame = 0;
let width = 0;
let height = 0;
let resizeBound = false;

let audio = null;
let noiseNode = null;
let noiseGain = null;
let noiseFilter = null;
let noiseLfo = null;
let noiseType = 'off';

function resolveAnimation(pref, theme) {
  if (pref === 'none' || pref === 'theme') {
    if (pref === 'none') return 'none';
    return THEME_ANIMATIONS[theme] || 'none';
  }
  return DEFAULTS[pref] ? pref : 'none';
}

function ensureCanvas() {
  if (canvas) return;
  canvas = document.createElement('canvas');
  canvas.id = 'ambient-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  document.body.appendChild(canvas);
  ctx = canvas.getContext('2d');
  const resize = () => {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    seed();
  };
  if (!resizeBound) {
    window.addEventListener('resize', resize, { passive: true });
    resizeBound = true;
  }
  resize();
}

function seed() {
  const spec = DEFAULTS[animation];
  particles = [];
  splashes = [];
  if (!spec) return;
  for (let i = 0; i < spec.count; i += 1) {
    const rain = animation === 'rain';
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: rain ? -0.55 - Math.random() * 0.9 : (Math.random() - 0.5) * 0.8,
      vy: rain ? 2.8 + Math.random() * 4.2 : spec.speed * (0.4 + Math.random() * 0.9),
      size: rain ? 0.8 + Math.random() * 1.3 : 1 + Math.random() * 2.6,
      life: Math.random() * Math.PI * 2,
      speed: 0.4 + Math.random() * 0.8,
    });
  }
}

function drawRain(p, spec) {
  const len = 15 + p.vy * 5.5;
  ctx.strokeStyle = spec.color;
  ctx.lineWidth = 0.8 + p.size * 0.35;
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(p.x, p.y);
  ctx.lineTo(p.x + p.vx * 5.5, p.y + len);
  ctx.stroke();
  ctx.fillStyle = spec.color;
  ctx.globalAlpha = 0.8;
  ctx.beginPath();
  ctx.arc(p.x, p.y, Math.max(0.6, p.size * 0.45), 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawSnow(p, spec) {
  ctx.fillStyle = spec.color;
  ctx.beginPath();
  ctx.arc(p.x, p.y, p.size * 0.75, 0, Math.PI * 2);
  ctx.fill();
}

function drawMeteor(p, spec) {
  const len = 30 + p.size * 12;
  const grad = ctx.createLinearGradient(p.x, p.y, p.x - len, p.y - len * 0.45);
  grad.addColorStop(0, spec.color);
  grad.addColorStop(1, 'rgba(255,220,150,0)');
  ctx.strokeStyle = grad;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.moveTo(p.x, p.y);
  ctx.lineTo(p.x - len, p.y - len * 0.45);
  ctx.stroke();
}

function drawBird(p, spec) {
  ctx.strokeStyle = spec.color;
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  const flap = Math.sin(p.life) * 3;
  ctx.moveTo(p.x - 5, p.y + flap);
  ctx.quadraticCurveTo(p.x - 2, p.y - 2, p.x, p.y);
  ctx.quadraticCurveTo(p.x + 2, p.y - 2, p.x + 5, p.y + flap);
  ctx.stroke();
}

function drawBubble(p, spec) {
  ctx.strokeStyle = spec.color;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(p.x, p.y, p.size * 2.4, 0, Math.PI * 2);
  ctx.stroke();
}

function drawStar(p, spec) {
  const twinkle = 0.35 + Math.abs(Math.sin(p.life)) * 0.65;
  ctx.fillStyle = spec.color;
  ctx.globalAlpha = twinkle;
  ctx.beginPath();
  ctx.arc(p.x, p.y, p.size * 0.7, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawLeaf(p, spec) {
  ctx.save();
  ctx.translate(p.x, p.y);
  ctx.rotate(p.life);
  ctx.fillStyle = spec.color;
  ctx.beginPath();
  ctx.ellipse(0, 0, p.size * 1.8, p.size * 0.9, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawFirefly(p, spec) {
  const glow = 0.3 + Math.abs(Math.sin(p.life)) * 0.7;
  ctx.fillStyle = spec.color;
  ctx.globalAlpha = glow;
  ctx.beginPath();
  ctx.arc(p.x, p.y, p.size * 1.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawPetal(p, spec) {
  ctx.save();
  ctx.translate(p.x, p.y);
  ctx.rotate(p.life);
  ctx.fillStyle = spec.color;
  ctx.beginPath();
  ctx.ellipse(0, 0, p.size * 2, p.size, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawAurora(p, spec) {
  const y = p.y % height;
  const grad = ctx.createLinearGradient(0, y, width, y + 180);
  grad.addColorStop(0, 'rgba(120,255,200,0)');
  grad.addColorStop(0.4, spec.color);
  grad.addColorStop(1, 'rgba(140,120,255,0)');
  ctx.fillStyle = grad;
  ctx.globalAlpha = 0.35 + Math.sin(p.life) * 0.1;
  ctx.fillRect(0, y, width, 150);
  ctx.globalAlpha = 1;
}

const DRAW = {
  rain: drawRain, snow: drawSnow, meteors: drawMeteor, birds: drawBird,
  bubbles: drawBubble, stars: drawStar, leaves: drawLeaf,
  fireflies: drawFirefly, petals: drawPetal, aurora: drawAurora,
};

function frame(now) {
  raf = 0;
  const reduced = prefs().reduce_motion || document.body.classList.contains('reduce-motion');
  if (!ctx || animation === 'none' || reduced || document.hidden) return;
  const dt = Math.min(34, now - lastFrame || 16) / 16.67;
  lastFrame = now;
  ctx.clearRect(0, 0, width, height);
  const spec = DEFAULTS[animation];
  const draw = DRAW[animation];
  if (!spec || !draw) return;

  for (const p of particles) {
    p.life += 0.02 * p.speed;
    if (animation === 'rain') {
      p.x += p.vx * 1.8 * dt;
      p.y += p.vy * 1.8 * dt;
      if (p.y > height + 35) {
        if (Math.random() < 0.3) {
          splashes.push({ x: p.x, y: height - 2, life: 0 });
        }
        p.y = -25;
        p.x = Math.random() * (width + 80) - 20;
      }
    } else if (animation === 'meteors') {
      p.x += 4.2 * p.speed * dt;
      p.y += 2.0 * p.speed * dt;
    } else if (animation === 'birds') {
      p.x += 0.8 * p.speed * dt;
      p.y += Math.sin(p.life) * 0.25;
    } else if (animation === 'bubbles' || animation === 'fireflies') {
      p.y -= p.vy * dt * 0.5;
      p.x += Math.sin(p.life) * 0.2;
    } else if (animation === 'aurora') {
      p.y += 0.08 * dt;
    } else {
      p.y += p.vy * dt;
      p.x += p.vx * dt + Math.sin(p.life) * 0.2;
    }

    if (p.y > height + 30) { p.y = -30; p.x = Math.random() * width; }
    if (p.y < -40) { p.y = height + 20; p.x = Math.random() * width; }
    if (p.x > width + 40) p.x = -30;
    if (p.x < -40) p.x = width + 30;

    draw(p, spec);
  }
  if (animation === 'rain') {
    for (const splash of splashes) {
      splash.life += 0.055 * dt;
      ctx.strokeStyle = spec.color;
      ctx.globalAlpha = Math.max(0, 1 - splash.life);
      ctx.lineWidth = 0.8;
      ctx.beginPath();
      ctx.ellipse(splash.x, splash.y, 2 + splash.life * 12, 1 + splash.life * 4, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    splashes = splashes.filter((splash) => splash.life < 1);
  }
  raf = requestAnimationFrame(frame);
}

export function setAnimation(pref) {
  const theme = document.documentElement.dataset.theme || 'dark';
  const next = resolveAnimation(pref || 'theme', theme);
  if (next === animation && raf) return;
  animation = next;
  if (animation === 'none') {
    cancelAnimationFrame(raf);
    raf = 0;
    if (ctx) ctx.clearRect(0, 0, width, height);
    return;
  }
  ensureCanvas();
  seed();
  lastFrame = 0;
  if (!raf) raf = requestAnimationFrame(frame);
}

export function refreshAnimation() {
  setAnimation(prefs().animation || 'theme');
}

// ------------------------------------------------------------------- noise
function makeNoise(type) {
  const seconds = 2;
  const rate = audio.sampleRate;
  const buffer = audio.createBuffer(1, rate * seconds, rate);
  const data = buffer.getChannelData(0);
  let last = 0;
  for (let i = 0; i < data.length; i += 1) {
    const white = Math.random() * 2 - 1;
    if (type === 'brown' || type === 'waves') {
      last = (last + 0.02 * white) / 1.02;
      data[i] = last * 3.2;
    } else if (type === 'pink') {
      last = 0.98 * last + 0.02 * white;
      data[i] = (white * 0.35 + last * 2.2) * 0.8;
    } else {
      data[i] = white * 0.5;
    }
  }
  return buffer;
}

function ensureAudio() {
  if (audio) return;
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return;
  audio = new AudioCtx();
}

export function stopNoise() {
  if (noiseNode) { try { noiseNode.stop(); } catch { /* already stopped */ } noiseNode.disconnect(); noiseNode = null; }
  if (noiseGain) { noiseGain.disconnect(); noiseGain = null; }
  if (noiseFilter) { noiseFilter.disconnect(); noiseFilter = null; }
  if (noiseLfo) { try { noiseLfo.stop(); } catch { /* ignore */ } noiseLfo = null; }
  noiseType = 'off';
}

export function startNoise(type, volume = prefs().noise_volume || 0.35) {
  if (type === 'off') { stopNoise(); return; }
  ensureAudio();
  if (!audio) { toast('Audio is not available in this browser.'); return; }
  stopNoise();
  noiseType = type;
  if (audio.state === 'suspended') audio.resume().catch(() => {});
  const source = audio.createBufferSource();
  source.buffer = makeNoise(type);
  source.loop = true;
  const filter = audio.createBiquadFilter();
  const gain = audio.createGain();
  gain.gain.value = 0;
  let target = Math.max(0, Math.min(1, Number(volume) || 0.35)) * 0.5;

  if (type === 'rain') {
    filter.type = 'bandpass'; filter.frequency.value = 1600; filter.Q.value = 0.35;
  } else if (type === 'wind') {
    filter.type = 'bandpass'; filter.frequency.value = 420; filter.Q.value = 0.7;
    const lfo = audio.createOscillator();
    const lfoGain = audio.createGain();
    lfo.frequency.value = 0.09;
    lfoGain.gain.value = 220;
    lfo.connect(lfoGain).connect(filter.frequency);
    lfo.start();
    noiseLfo = lfo;
  } else if (type === 'waves') {
    filter.type = 'lowpass'; filter.frequency.value = 520; filter.Q.value = 0.3;
    const lfo = audio.createOscillator();
    const lfoGain = audio.createGain();
    lfo.frequency.value = 0.11;
    lfoGain.gain.value = 0.22;
    lfo.connect(lfoGain).connect(gain.gain);
    lfo.start();
    noiseLfo = lfo;
    target *= 0.7;
  } else {
    filter.type = 'lowpass'; filter.frequency.value = type === 'white' ? 12000 : 900; filter.Q.value = 0.2;
  }

  source.connect(filter).connect(gain).connect(audio.destination);
  gain.gain.setValueAtTime(0.0001, audio.currentTime);
  gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, target), audio.currentTime + 0.8);
  source.start();
  noiseNode = source;
  noiseGain = gain;
  noiseFilter = filter;
}

export function setNoiseVolume(volume) {
  if (!noiseGain || !audio) return;
  const target = Math.max(0, Math.min(1, Number(volume) || 0.35)) * (noiseType === 'waves' ? 0.35 : 0.5);
  noiseGain.gain.setTargetAtTime(Math.max(0.0001, target), audio.currentTime, 0.15);
}

export function currentNoise() {
  return noiseType;
}

// ------------------------------------------------------------------- wiring
export function applyAmbient() {
  const p = prefs();
  setAnimation(p.animation || 'theme');
  if (p.noise && p.noise !== 'off' && currentNoise() !== p.noise) {
    // Autoplay is often blocked; only resume if audio was already unlocked.
    if (audio && audio.state === 'running') startNoise(p.noise, p.noise_volume);
  }
  if ((p.noise || 'off') === 'off') stopNoise();
}

export async function chooseNoise(type) {
  ensureAudio();
  if (audio && audio.state === 'suspended') {
    try { await audio.resume(); } catch { /* gesture required */ }
  }
  if (type === 'off') stopNoise(); else startNoise(type, prefs().noise_volume || 0.35);
  await savePrefs({ noise: type }).catch(() => {});
}

export async function chooseAnimation(type) {
  await savePrefs({ animation: type }).catch(() => {});
  setAnimation(type);
}
