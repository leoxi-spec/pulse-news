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
let flash = 0;
let lastFrame = 0;
let lastDraw = 0;
let width = 0;
let height = 0;
let resizeBound = false;
const FRAME_MS = 1000 / 30;

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
  ctx = canvas.getContext('2d', { alpha: true, desynchronized: true });
  const resize = () => {
    // Retina screens at 2x make a full-window canvas expensive to clear every
    // frame. The particles are soft-edged, so 1.5x is visually indistinguishable
    // while cutting the pixel count by roughly half.
    const dpr = Math.min(1.5, window.devicePixelRatio || 1);
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
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && animation !== 'none' && !raf && !prefs().reduce_motion) {
        lastFrame = 0;
        lastDraw = 0;
        raf = requestAnimationFrame(frame);
      }
    }, { passive: true });
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
    const rain = ['rain', 'heavy-rain', 'drizzle', 'thunder', 'storm'].includes(animation);
    const heavy = animation === 'heavy-rain' || animation === 'storm';
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: rain ? -0.55 - Math.random() * 0.9 : (Math.random() - 0.5) * 0.8,
      vy: rain ? (heavy ? 4.2 + Math.random() * 4 : animation === 'drizzle' ? 1.1 + Math.random() * 1.6 : 2.8 + Math.random() * 4.2) : spec.speed * (0.4 + Math.random() * 0.9),
      size: rain ? 0.8 + Math.random() * 1.3 : 1 + Math.random() * 2.6,
      life: Math.random() * Math.PI * 2,
      speed: 0.4 + Math.random() * 0.8,
      meteor: animation === 'night-sky' && i < 6,
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

Object.assign(DEFAULTS, {
  thunder: { count: 120, speed: 4.2, color: 'rgba(185,205,255,.68)' },
  lightning: { count: 9, speed: 0.8, color: 'rgba(230,240,255,.95)' },
  'heavy-rain': { count: 230, speed: 4.6, color: 'rgba(170,205,255,.72)' },
  drizzle: { count: 95, speed: 1.5, color: 'rgba(185,215,255,.48)' },
  hail: { count: 70, speed: 3.8, color: 'rgba(235,248,255,.9)' },
  sleet: { count: 105, speed: 2.8, color: 'rgba(215,235,255,.7)' },
  snowstorm: { count: 150, speed: 1.5, color: 'rgba(255,255,255,.88)' },
  fog: { count: 14, speed: 0.12, color: 'rgba(205,220,240,.14)' },
  mist: { count: 24, speed: 0.08, color: 'rgba(220,235,250,.12)' },
  wind: { count: 32, speed: 1.3, color: 'rgba(210,230,250,.28)' },
  clouds: { count: 11, speed: 0.12, color: 'rgba(235,245,255,.12)' },
  'sun-rays': { count: 13, speed: 0.04, color: 'rgba(255,221,130,.16)' },
  heat: { count: 28, speed: 0.35, color: 'rgba(255,190,120,.12)' },
  ripples: { count: 16, speed: 0.35, color: 'rgba(170,225,255,.42)' },
  storm: { count: 150, speed: 4.4, color: 'rgba(180,200,255,.65)' },
  rainbow: { count: 9, speed: 0.1, color: 'rgba(255,255,255,.14)' },
  dust: { count: 65, speed: 0.4, color: 'rgba(235,215,170,.35)' },
  ash: { count: 70, speed: 0.6, color: 'rgba(205,205,205,.45)' },
  embers: { count: 55, speed: 0.5, color: 'rgba(255,155,70,.75)' },
  bokeh: { count: 22, speed: 0.16, color: 'rgba(255,220,190,.12)' },
  'night-sky': { count: 95, speed: 0.15, color: 'rgba(255,255,255,.86)' },
});

function drawThunder(p, spec) { drawRain(p, spec); }
function drawLightning(p, spec) {
  ctx.strokeStyle = spec.color; ctx.lineWidth = 1.4; ctx.beginPath();
  ctx.moveTo(p.x, p.y);
  for (let i = 0; i < 4; i += 1) ctx.lineTo(p.x + (Math.random() - .5) * 16, p.y + 18 + i * 18);
  ctx.stroke();
}
function drawHeavyRain(p, spec) { drawRain(p, spec); }
function drawDrizzle(p, spec) {
  ctx.strokeStyle = spec.color; ctx.lineWidth = .7; ctx.beginPath();
  ctx.moveTo(p.x, p.y); ctx.lineTo(p.x + p.vx * 2, p.y + 8 + p.size * 3); ctx.stroke();
}
function drawHail(p, spec) {
  ctx.strokeStyle = spec.color; ctx.lineWidth = 1; ctx.beginPath();
  ctx.arc(p.x, p.y, p.size * 1.1, 0, Math.PI * 2); ctx.stroke();
}
function drawSleet(p, spec) { drawDrizzle(p, spec); drawHail({ ...p, y: p.y + 5, size: p.size * .7 }, spec); }
function drawSnowstorm(p, spec) { drawSnow(p, spec); ctx.strokeStyle = spec.color; ctx.lineWidth = .6; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - 3, p.y - 8); ctx.stroke(); }
function drawFog(p, spec) { ctx.fillStyle = spec.color; ctx.fillRect(0, p.y, width, 30 + p.size * 6); }
function drawMist(p, spec) { ctx.fillStyle = spec.color; ctx.beginPath(); ctx.arc(p.x, p.y, p.size * 18, 0, Math.PI * 2); ctx.fill(); }
function drawWind(p, spec) {
  ctx.strokeStyle = spec.color; ctx.lineWidth = .8; ctx.beginPath();
  ctx.moveTo(p.x, p.y); ctx.bezierCurveTo(p.x + 18, p.y - 8, p.x + 34, p.y + 8, p.x + 54, p.y); ctx.stroke();
}
function drawClouds(p, spec) { ctx.fillStyle = spec.color; ctx.beginPath(); ctx.ellipse(p.x, p.y, p.size * 18, p.size * 7, 0, 0, Math.PI * 2); ctx.fill(); }
function drawSunRays(p, spec) {
  const grad = ctx.createLinearGradient(width / 2, 0, width / 2 + p.x, height);
  grad.addColorStop(0, spec.color); grad.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = grad; ctx.beginPath();
  ctx.moveTo(width / 2 - 8, 0); ctx.lineTo(width / 2 + 8, 0); ctx.lineTo(p.x + 35, height); ctx.lineTo(p.x - 35, height);
  ctx.closePath(); ctx.fill();
}
function drawHeat(p, spec) { ctx.strokeStyle = spec.color; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(p.x, height); ctx.bezierCurveTo(p.x - 5, height * .6, p.x + 5, height * .3, p.x, 0); ctx.stroke(); }
function drawRipples(p, spec) { ctx.strokeStyle = spec.color; ctx.globalAlpha = Math.max(0, 1 - p.life); ctx.beginPath(); ctx.ellipse(p.x, p.y, 4 + p.life * 30, 1 + p.life * 7, 0, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1; }
function drawRainbow(p, spec) {
  const colors = ['#ff6b6b', '#ffbd5c', '#63e6a6', '#5d8cff', '#a67cff'];
  ctx.globalAlpha = .18; ctx.lineWidth = 8 + p.size * 3;
  colors.forEach((color, i) => { ctx.strokeStyle = color; ctx.beginPath(); ctx.arc(p.x, p.y, 90 + i * 13, Math.PI, Math.PI * 2); ctx.stroke(); });
  ctx.globalAlpha = 1;
}
function drawDust(p, spec) { ctx.fillStyle = spec.color; ctx.fillRect(p.x, p.y, p.size, p.size); }
function drawAsh(p, spec) { drawDust(p, spec); }
function drawEmbers(p, spec) { ctx.fillStyle = spec.color; ctx.beginPath(); ctx.arc(p.x, p.y, p.size * 1.2, 0, Math.PI * 2); ctx.fill(); }
function drawBokeh(p, spec) { ctx.fillStyle = spec.color; ctx.beginPath(); ctx.arc(p.x, p.y, p.size * 9, 0, Math.PI * 2); ctx.fill(); }
function drawNightSky(p, spec) {
  if (p.meteor) {
    const len = 42 + p.size * 20;
    const grad = ctx.createLinearGradient(p.x, p.y, p.x - len, p.y - len * .4);
    grad.addColorStop(0, 'rgba(255,255,255,.9)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.strokeStyle = grad; ctx.lineWidth = 1.3; ctx.beginPath();
    ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - len, p.y - len * .4); ctx.stroke();
  } else drawStar(p, spec);
}

const DRAW = {
  rain: drawRain, snow: drawSnow, meteors: drawMeteor, birds: drawBird,
  bubbles: drawBubble, stars: drawStar, leaves: drawLeaf,
  fireflies: drawFirefly, petals: drawPetal, aurora: drawAurora,
  thunder: drawThunder, lightning: drawLightning, 'heavy-rain': drawHeavyRain,
  drizzle: drawDrizzle, hail: drawHail, sleet: drawSleet, snowstorm: drawSnowstorm,
  fog: drawFog, mist: drawMist, wind: drawWind, clouds: drawClouds,
  'sun-rays': drawSunRays, heat: drawHeat, ripples: drawRipples, storm: drawThunder,
  rainbow: drawRainbow, dust: drawDust, ash: drawAsh, embers: drawEmbers, bokeh: drawBokeh,
  'night-sky': drawNightSky,
};

function frame(now) {
  raf = 0;
  const reduced = prefs().reduce_motion || document.body.classList.contains('reduce-motion');
  if (!ctx || animation === 'none' || reduced || document.hidden) return;
  // Ambient motion is decorative. 30fps is enough for drifting particles and
  // keeps scrolling responsive on Retina displays.
  if (lastDraw && now - lastDraw < FRAME_MS) {
    raf = requestAnimationFrame(frame);
    return;
  }
  lastDraw = now;
  const dt = Math.min(34, now - lastFrame || 16) / 16.67;
  lastFrame = now;
  ctx.clearRect(0, 0, width, height);
  const spec = DEFAULTS[animation];
  const draw = DRAW[animation];
  if (!spec || !draw) return;

  for (const p of particles) {
    p.life += 0.02 * p.speed;
    if (animation === 'night-sky' && p.meteor) {
      p.x += 2.4 * dt; p.y += 1.0 * dt;
      if (p.x > width + 60 || p.y > height + 40) { p.x = Math.random() * width * .8; p.y = -30; }
    } else if (['rain', 'heavy-rain', 'drizzle', 'thunder', 'storm'].includes(animation)) {
      p.x += p.vx * 1.8 * dt;
      p.y += p.vy * 1.8 * dt;
      if (p.y > height + 35) {
        if (Math.random() < 0.3) {
          splashes.push({ x: p.x, y: height - 2, life: 0 });
        }
        p.y = -25;
        p.x = Math.random() * (width + 80) - 20;
      }
    } else if (animation === 'embers') {
      p.y -= (1 + p.speed) * dt;
      p.x += Math.sin(p.life) * .35;
    } else if (animation === 'wind' || animation === 'clouds') {
      p.x += (animation === 'clouds' ? 1.4 : 3.2) * p.speed * dt;
      p.y += Math.sin(p.life) * .18;
    } else if (animation === 'fog' || animation === 'mist') {
      p.x += .18 * dt;
      p.y += Math.sin(p.life) * .08;
    } else if (animation === 'ripples') {
      p.life += .018 * dt;
      if (p.life > 1) { p.life = 0; p.x = Math.random() * width; p.y = height - 4; }
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
    if (animation === 'ripples' && p.life === 0) p.y = height - 4;
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
  if (animation === 'thunder' || animation === 'storm') {
    if (Math.random() < .006) flash = 1;
    if (flash > 0) {
      ctx.fillStyle = `rgba(220,230,255,${flash * .18})`;
      ctx.fillRect(0, 0, width, height);
      flash = Math.max(0, flash - .06 * dt);
    }
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
  lastDraw = 0;
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
  setAnimation(p.weather_theme ? (document.documentElement.dataset.weatherAnimation || p.animation || 'theme') : (p.animation || 'theme'));
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
