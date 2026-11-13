// Pulse Arcade: fifteen small, self-contained games. No external engines.
import { html, raw, icons, modal, toast, confetti } from '../ui.js';
import { record } from '../store.js';

const W = 480;
const H = 320;
const COLORS = {
  bg: '#0b1020', grid: 'rgba(160,175,220,.12)', text: '#eef1f6', muted: '#9aa6c4',
  accent: '#7c5cff', pink: '#ff4d8d', green: '#45d6a4', amber: '#ffbd5c', red: '#ff6577',
};

const GAMES = [
  { id: 'flappy', title: 'Flappy Pulse', genre: 'Arcade', blurb: 'Tap to keep the pulse alive between the pipes.', controls: 'Click, tap or Space to flap.', color: '#7c5cff' },
  { id: 'snake', title: 'Pulse Snake', genre: 'Arcade', blurb: 'Eat the dots, grow the line, avoid your own tail.', controls: 'Arrow keys or swipe to turn.', color: '#45d6a4' },
  { id: 'breakout', title: 'Brick Breaker', genre: 'Arcade', blurb: 'Clear every brick without losing the ball.', controls: 'Move with the mouse or arrow keys.', color: '#ffbd5c' },
  { id: 'pong', title: 'Pong', genre: 'Arcade', blurb: 'The original duel, against a patient CPU.', controls: 'Mouse or Up/Down. First to 7.', color: '#5d8cff' },
  { id: 'stack', title: 'Stack Tower', genre: 'Arcade', blurb: 'Drop each slab on the last. Keep it clean.', controls: 'Click, tap or Space to drop.', color: '#ff4d8d' },
  { id: 'asteroid', title: 'Asteroid Run', genre: 'Arcade', blurb: 'Dodge the field for as long as you can.', controls: 'Left/Right or A/D to steer.', color: '#72d4e8' },
  { id: 'bubble', title: 'Bubble Pop', genre: 'Reflex', blurb: 'Pop as many drifting bubbles as possible in 40 seconds.', controls: 'Click or tap the bubbles.', color: '#a67cff' },
  { id: 'runner', title: 'Pulse Runner', genre: 'Arcade', blurb: 'Jump the gaps and keep the run going.', controls: 'Click, tap or Space to jump.', color: '#38c98b' },
  { id: '2048', title: '2048', genre: 'Puzzle', blurb: 'Merge the tiles and reach 2048.', controls: 'Arrow keys or swipe.', color: '#ffbd5c' },
  { id: 'memory', title: 'Memory Match', genre: 'Puzzle', blurb: 'Match eight pairs in as few moves as possible.', controls: 'Click two cards at a time.', color: '#5d8cff' },
  { id: 'simon', title: 'Simon Says', genre: 'Memory', blurb: 'Repeat the colour sequence as it grows.', controls: 'Watch, then click the pads.', color: '#a67cff' },
  { id: 'ttt', title: 'Tic-Tac-Toe', genre: 'Puzzle', blurb: 'A small board with a stubborn CPU.', controls: 'Click a square. You are X.', color: '#45d6a4' },
  { id: 'mines', title: 'Mini Mines', genre: 'Puzzle', blurb: 'Clear an 8×8 field without hitting a mine.', controls: 'Click to reveal, right-click or Flag mode to mark.', color: '#ff6577' },
  { id: 'word', title: 'Word Scramble', genre: 'Word', blurb: 'Unscramble the news word before the clock runs out.', controls: 'Type the answer and press Enter.', color: '#ff9f43' },
  { id: 'reaction', title: 'Reaction Grid', genre: 'Reflex', blurb: 'Hit targets as fast as you can for 30 seconds.', controls: 'Click the lit square.', color: '#ff4d8d' },
];

const GENRES = ['All', 'Arcade', 'Puzzle', 'Word', 'Reflex', 'Memory'];
const STORE_KEY = 'pulse.arcade';
const SETTINGS_KEY = 'pulse.arcade.settings';
const STAR_LEVELS = {
  flappy: [5, 10, 20], snake: [50, 100, 200], breakout: [100, 250, 500],
  pong: [10, 14, 20], stack: [50, 100, 200], asteroid: [20, 50, 100],
  bubble: [50, 100, 200], runner: [30, 60, 120], '2048': [256, 512, 2048],
  memory: [400, 700, 900], simon: [5, 10, 15], ttt: [100, 300, 600],
  mines: [400, 700, 1000], word: [100, 250, 500], reaction: [15, 30, 45],
};
const SETTINGS_DEFAULT = { difficulty: 'normal', sound: true };
let audio = null;

function readSettings() {
  try { return { ...SETTINGS_DEFAULT, ...(JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}') || {}) }; } catch { return { ...SETTINGS_DEFAULT }; }
}
function saveSettings(next) {
  try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(next)); } catch { /* ignore */ }
  window.__pulseArcadeDifficulty = next.difficulty;
}
function starsFor(id, score) {
  const levels = STAR_LEVELS[id] || [100, 500, 1000];
  return levels.reduce((total, threshold) => total + (Number(score) >= threshold ? 1 : 0), 0);
}
function starMarkup(stars) {
  return html`<span class="arcade-stars" aria-label="${stars} of 3 stars">${[0, 1, 2].map((i) => html`<i class="${i < stars ? 'is-on' : ''}"></i>`)}</span>`;
}
function beep(freq = 520, duration = .08, type = 'sine') {
  const settings = readSettings();
  if (!settings.sound) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    audio = audio || new AudioCtx();
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.type = type; osc.frequency.value = freq;
    gain.gain.setValueAtTime(.035, audio.currentTime);
    gain.gain.exponentialRampToValueAtTime(.0001, audio.currentTime + duration);
    osc.connect(gain); gain.connect(audio.destination);
    osc.start(); osc.stop(audio.currentTime + duration);
  } catch { /* audio is optional */ }
}
function dailyGame() {
  const day = new Date().toISOString().slice(0, 10);
  let hash = 0;
  for (const char of day) hash = ((hash << 5) - hash + char.charCodeAt(0)) | 0;
  return GAMES[Math.abs(hash) % GAMES.length];
}

function readStore() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY) || '{}') || {}; } catch { return {}; }
}
function writeStore(data) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(data)); } catch { /* private mode */ }
}
function bestOf(id) {
  return Number(readStore()[id]?.best || 0);
}
function playsOf(id) {
  return Number(readStore()[id]?.plays || 0);
}
function recordScore(id, score) {
  const store = readStore();
  const previous = Number(store[id]?.best || 0);
  const value = Math.max(0, Math.round(Number(score) || 0));
  const newBest = value > previous;
  const stars = starsFor(id, newBest ? value : Math.max(previous, value));
  store[id] = { best: newBest ? value : previous, plays: Number(store[id]?.plays || 0) + 1, last: value, stars: Math.max(Number(store[id]?.stars || 0), stars) };
  writeStore(store);
  beep(newBest ? 760 : 440, newBest ? .16 : .08, 'triangle');
  if (newBest) toast(`New best: ${value.toLocaleString()} · ${stars}/3 stars`);
  if (stars >= 3) confetti(18);
  document.querySelector('.arcade-stage')?.classList.add('arcade-shake');
  setTimeout(() => document.querySelector('.arcade-stage')?.classList.remove('arcade-shake'), 420);
  record('arcade', { value, meta: { game: id, stars } }).catch(() => {});
  return { best: store[id].best, newBest, plays: store[id].plays, stars: store[id].stars };
}

function point(event, canvas) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left) * (canvas.width / rect.width),
    y: (event.clientY - rect.top) * (canvas.height / rect.height),
  };
}

function keys(handler) {
  const fn = (event) => {
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(event.code)) event.preventDefault();
    handler(event);
  };
  window.addEventListener('keydown', fn);
  return () => window.removeEventListener('keydown', fn);
}

function loop(update, draw) {
  let raf = 0;
  let last = 0;
  const frame = (now) => {
    const speed = window.__pulseArcadeDifficulty === 'chill' ? .72 : window.__pulseArcadeDifficulty === 'turbo' ? 1.28 : 1;
    const dt = (Math.min(2.4, Math.max(0.3, (now - last) / 16.67)) || 1) * speed;
    last = now;
    update(dt);
    draw();
    raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);
  return () => cancelAnimationFrame(raf);
}

function canvasShell(stage, game, help) {
  stage.innerHTML = html`
    <div class="arcade-hud">
      <div class="arcade-hud__score"><b data-score>0</b><span>score</span></div>
      <div class="arcade-hud__best"><b data-best>${bestOf(game.id).toLocaleString()}</b><span>best</span></div>
      <button class="btn btn--sm btn--ghost" type="button" data-restart>${raw(icons.refresh)} Restart</button>
    </div>
    <canvas width="${W}" height="${H}" aria-label="${game.title} game canvas"></canvas>
    <p class="arcade-help">${help}</p>`;
  const canvas = stage.querySelector('canvas');
  const scoreEl = stage.querySelector('[data-score]');
  const bestEl = stage.querySelector('[data-best]');
  const restart = stage.querySelector('[data-restart]');
  return {
    canvas,
    ctx: canvas.getContext('2d'),
    scoreEl,
    bestEl,
    restart,
    setScore(value) { if (scoreEl) scoreEl.textContent = Math.round(value).toLocaleString(); },
    record(value) {
      const result = recordScore(game.id, value);
      if (bestEl) bestEl.textContent = result.best.toLocaleString();
      return result;
    },
    point: (event) => point(event, canvas),
    onRestart: null,
  };
}

function domShell(stage, game, help, body) {
  stage.innerHTML = html`
    <div class="arcade-hud">
      <div class="arcade-hud__score"><b data-score>0</b><span>score</span></div>
      <div class="arcade-hud__best"><b data-best>${bestOf(game.id).toLocaleString()}</b><span>best</span></div>
      <button class="btn btn--sm btn--ghost" type="button" data-restart>${raw(icons.refresh)} Restart</button>
    </div>
    <div class="arcade-board" data-board>${body}</div>
    <p class="arcade-help">${help}</p>`;
  const scoreEl = stage.querySelector('[data-score]');
  const bestEl = stage.querySelector('[data-best]');
  return {
    board: stage.querySelector('[data-board]'),
    scoreEl,
    bestEl,
    restart: stage.querySelector('[data-restart]'),
    setScore(value) { if (scoreEl) scoreEl.textContent = Math.round(value).toLocaleString(); },
    record(value) {
      const result = recordScore(game.id, value);
      if (bestEl) bestEl.textContent = result.best.toLocaleString();
      return result;
    },
  };
}

function drawText(ctx, text, x, y, size = 16, color = COLORS.text, align = 'left') {
  ctx.fillStyle = color;
  ctx.font = `700 ${size}px ui-sans-serif, system-ui, sans-serif`;
  ctx.textAlign = align;
  ctx.fillText(text, x, y);
}

function drawGameOver(ctx, title, sub = 'Press Restart to play again') {
  ctx.fillStyle = 'rgba(5,7,12,.72)';
  ctx.fillRect(0, 0, W, H);
  drawText(ctx, title, W / 2, H / 2 - 8, 28, COLORS.text, 'center');
  drawText(ctx, sub, W / 2, H / 2 + 24, 13, COLORS.muted, 'center');
}

/* ------------------------------------------------------------------ canvas games */
function flappy(stage, game) {
  const h = canvasShell(stage, game, 'Click, tap or press Space to flap.');
  let birdY, vy, pipes, score, over, tick, recorded;
  const reset = () => {
    birdY = H / 2; vy = 0; pipes = []; score = 0; over = false; tick = 0; recorded = false;
    h.setScore(0);
  };
  const flap = () => {
    if (over) { reset(); return; }
    vy = -4.5;
  };
  h.canvas.addEventListener('pointerdown', (e) => { e.preventDefault(); flap(); });
  const cleanKeys = keys((e) => { if (e.code === 'Space' || e.code === 'ArrowUp') flap(); });
  const stop = loop((dt) => {
    if (over) return;
    tick += dt;
    vy += 0.24 * dt;
    birdY += vy * dt;
    if (!pipes.length || tick > 82) {
      tick = 0;
      pipes.push({ x: W + 20, top: 50 + Math.random() * 130, scored: false });
    }
    for (const pipe of pipes) pipe.x -= 2.15 * dt;
    pipes = pipes.filter((p) => p.x > -60);
    if (birdY > H - 26 || birdY < 10) over = true;
    for (const pipe of pipes) {
      if (100 + 12 > pipe.x && 100 - 12 < pipe.x + 46 && (birdY - 11 < pipe.top || birdY + 11 > pipe.top + 96)) over = true;
      if (!pipe.scored && pipe.x + 46 < 100) { pipe.scored = true; score += 1; h.setScore(score); }
    }
    if (over && !recorded) { recorded = true; h.record(score); }
  }, () => {
    const { ctx } = h;
    ctx.fillStyle = COLORS.bg; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(124,92,255,.12)';
    for (let y = 0; y < H; y += 40) ctx.fillRect(0, y, W, 1);
    for (const pipe of pipes) {
      ctx.fillStyle = COLORS.green;
      ctx.fillRect(pipe.x, 0, 46, pipe.top);
      ctx.fillRect(pipe.x, pipe.top + 96, 46, H - pipe.top - 96);
      ctx.fillStyle = 'rgba(255,255,255,.12)';
      ctx.fillRect(pipe.x + 4, 0, 5, pipe.top);
      ctx.fillRect(pipe.x + 4, pipe.top + 96, 5, H - pipe.top - 96);
    }
    ctx.fillStyle = COLORS.amber;
    ctx.beginPath(); ctx.arc(100, birdY, 12, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = COLORS.bg;
    ctx.beginPath(); ctx.arc(104, birdY - 4, 2.2, 0, Math.PI * 2); ctx.fill();
    if (over) drawGameOver(h.ctx, 'Down for now', 'Restart or tap to try again');
  });
  h.onRestart = reset;
  h.restart.addEventListener('click', reset);
  reset();
  return () => { stop(); cleanKeys(); };
}

function snake(stage, game) {
  const h = canvasShell(stage, game, 'Arrow keys or swipe to turn. Eat the amber dots.');
  const cell = 20;
  const cols = 24;
  const rows = 16;
  let body, dir, nextDir, food, score, over, acc;
  const reset = () => {
    body = [{ x: 12, y: 8 }, { x: 11, y: 8 }, { x: 10, y: 8 }];
    dir = { x: 1, y: 0 }; nextDir = { ...dir }; food = { x: 18, y: 8 };
    score = 0; over = false; acc = 0; h.setScore(0);
  };
  const turn = (x, y) => { if (x !== -dir.x || y !== -dir.y) nextDir = { x, y }; };
  const cleanKeys = keys((e) => {
    if (e.code === 'ArrowUp' || e.code === 'KeyW') turn(0, -1);
    if (e.code === 'ArrowDown' || e.code === 'KeyS') turn(0, 1);
    if (e.code === 'ArrowLeft' || e.code === 'KeyA') turn(-1, 0);
    if (e.code === 'ArrowRight' || e.code === 'KeyD') turn(1, 0);
  });
  let sx = 0, sy = 0;
  h.canvas.addEventListener('pointerdown', (e) => { const p = h.point(e); sx = p.x; sy = p.y; });
  h.canvas.addEventListener('pointerup', (e) => {
    const p = h.point(e); const dx = p.x - sx; const dy = p.y - sy;
    if (Math.abs(dx) < 18 && Math.abs(dy) < 18) return;
    if (Math.abs(dx) > Math.abs(dy)) turn(dx > 0 ? 1 : -1, 0); else turn(0, dy > 0 ? 1 : -1);
  });
  const stop = loop((dt) => {
    if (over) return;
    acc += dt;
    if (acc < 6.4) return;
    acc = 0;
    dir = nextDir;
    const head = { x: body[0].x + dir.x, y: body[0].y + dir.y };
    if (head.x < 0 || head.y < 0 || head.x >= cols || head.y >= rows || body.some((b) => b.x === head.x && b.y === head.y)) {
      over = true; h.record(score); return;
    }
    body.unshift(head);
    if (head.x === food.x && head.y === food.y) {
      score += 10; h.setScore(score);
      do { food = { x: Math.floor(Math.random() * cols), y: Math.floor(Math.random() * rows) }; }
      while (body.some((b) => b.x === food.x && b.y === food.y));
    } else body.pop();
  }, () => {
    const { ctx } = h;
    ctx.fillStyle = COLORS.bg; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = COLORS.grid; ctx.lineWidth = 1;
    for (let x = 0; x <= cols; x += 1) { ctx.beginPath(); ctx.moveTo(x * cell, 0); ctx.lineTo(x * cell, rows * cell); ctx.stroke(); }
    for (let y = 0; y <= rows; y += 1) { ctx.beginPath(); ctx.moveTo(0, y * cell); ctx.lineTo(cols * cell, y * cell); ctx.stroke(); }
    ctx.fillStyle = COLORS.amber;
    ctx.beginPath(); ctx.arc(food.x * cell + cell / 2, food.y * cell + cell / 2, 6, 0, Math.PI * 2); ctx.fill();
    body.forEach((b, i) => {
      ctx.fillStyle = i === 0 ? COLORS.green : `rgba(69,214,164,${Math.max(.25, .75 - i * .02)})`;
      ctx.fillRect(b.x * cell + 2, b.y * cell + 2, cell - 4, cell - 4);
    });
    if (over) drawGameOver(ctx, 'Game over', 'Restart to grow again');
  });
  h.onRestart = reset; h.restart.addEventListener('click', reset); reset();
  return () => { stop(); cleanKeys(); };
}

function breakout(stage, game) {
  const h = canvasShell(stage, game, 'Move the paddle with the mouse or arrow keys.');
  let paddle, ball, bricks, score, lives, over, won;
  const reset = () => {
    paddle = { x: W / 2 - 40, w: 80 };
    ball = { x: W / 2, y: H - 60, vx: 2.3, vy: -3.1 };
    bricks = [];
    for (let r = 0; r < 4; r += 1) for (let c = 0; c < 7; c += 1) {
      bricks.push({ x: 28 + c * 60, y: 36 + r * 26, w: 52, h: 16, alive: true, hue: [COLORS.accent, COLORS.pink, COLORS.amber, COLORS.green][r] });
    }
    score = 0; lives = 3; over = false; won = false; h.setScore(0);
  };
  const move = (x) => { paddle.x = Math.max(0, Math.min(W - paddle.w, x - paddle.w / 2)); };
  h.canvas.addEventListener('pointermove', (e) => move(h.point(e).x));
  const cleanKeys = keys((e) => {
    if (e.code === 'ArrowLeft' || e.code === 'KeyA') paddle.x = Math.max(0, paddle.x - 26);
    if (e.code === 'ArrowRight' || e.code === 'KeyD') paddle.x = Math.min(W - paddle.w, paddle.x + 26);
  });
  const stop = loop((dt) => {
    if (over) return;
    ball.x += ball.vx * dt; ball.y += ball.vy * dt;
    if (ball.x < 8 || ball.x > W - 8) ball.vx *= -1;
    if (ball.y < 8) ball.vy *= -1;
    if (ball.y > H + 20) { lives -= 1; if (lives <= 0) { over = true; h.record(score); return; } ball = { x: W / 2, y: H - 60, vx: 2.3, vy: -3.1 }; }
    if (ball.y > H - 34 && ball.y < H - 20 && ball.x > paddle.x && ball.x < paddle.x + paddle.w && ball.vy > 0) {
      ball.vy *= -1;
      ball.vx += ((ball.x - (paddle.x + paddle.w / 2)) / paddle.w) * 2.2;
    }
    for (const brick of bricks) {
      if (!brick.alive || ball.x < brick.x || ball.x > brick.x + brick.w || ball.y < brick.y || ball.y > brick.y + brick.h) continue;
      brick.alive = false; ball.vy *= -1; score += 10; h.setScore(score);
    }
    if (bricks.every((b) => !b.alive)) { won = true; over = true; h.record(score + 100); }
  }, () => {
    const { ctx } = h;
    ctx.fillStyle = COLORS.bg; ctx.fillRect(0, 0, W, H);
    for (const brick of bricks) if (brick.alive) { ctx.fillStyle = brick.hue; ctx.fillRect(brick.x, brick.y, brick.w, brick.h); }
    ctx.fillStyle = COLORS.text; ctx.fillRect(paddle.x, H - 24, paddle.w, 8);
    ctx.beginPath(); ctx.arc(ball.x, ball.y, 5, 0, Math.PI * 2); ctx.fillStyle = COLORS.text; ctx.fill();
    drawText(ctx, `Lives ${lives}`, 14, H - 40, 12, COLORS.muted);
    if (over) drawGameOver(ctx, won ? 'Board cleared' : 'Out of lives', 'Restart to play again');
  });
  h.onRestart = reset; h.restart.addEventListener('click', reset); reset();
  return () => { stop(); cleanKeys(); };
}

function pong(stage, game) {
  const h = canvasShell(stage, game, 'First to 7. Move with the mouse or Up/Down.');
  let player, cpu, ball, score, cpuScore, over;
  const reset = () => {
    player = H / 2; cpu = H / 2;
    ball = { x: W / 2, y: H / 2, vx: 3.1, vy: 1.5 };
    score = 0; cpuScore = 0; over = false; h.setScore(0);
  };
  h.canvas.addEventListener('pointermove', (e) => { player = Math.max(34, Math.min(H - 34, h.point(e).y)); });
  const cleanKeys = keys((e) => {
    if (e.code === 'ArrowUp' || e.code === 'KeyW') player = Math.max(34, player - 26);
    if (e.code === 'ArrowDown' || e.code === 'KeyS') player = Math.min(H - 34, player + 26);
  });
  const stop = loop((dt) => {
    if (over) return;
    ball.x += ball.vx * dt; ball.y += ball.vy * dt;
    if (ball.y < 10 || ball.y > H - 10) ball.vy *= -1;
    cpu += (ball.y - cpu) * 0.055 * dt;
    if (ball.x < 18 && Math.abs(ball.y - player) < 40) { ball.vx = Math.abs(ball.vx) * 1.02; ball.vy += (ball.y - player) * 0.04; }
    if (ball.x > W - 18 && Math.abs(ball.y - cpu) < 34) { ball.vx = -Math.abs(ball.vx) * 1.02; ball.vy += (ball.y - cpu) * 0.04; }
    if (ball.x < 0) { cpuScore += 1; ball = { x: W / 2, y: H / 2, vx: 3.1, vy: 1.5 }; }
    if (ball.x > W) { score += 1; h.setScore(score); ball = { x: W / 2, y: H / 2, vx: -3.1, vy: 1.5 }; }
    if (score >= 7 || cpuScore >= 7) { over = true; h.record(Math.max(0, score - cpuScore + 10)); }
  }, () => {
    const { ctx } = h;
    ctx.fillStyle = COLORS.bg; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = COLORS.grid; ctx.setLineDash([8, 12]); ctx.beginPath(); ctx.moveTo(W / 2, 0); ctx.lineTo(W / 2, H); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = COLORS.text; ctx.fillRect(10, player - 34, 8, 68); ctx.fillRect(W - 18, cpu - 34, 8, 68);
    ctx.beginPath(); ctx.arc(ball.x, ball.y, 6, 0, Math.PI * 2); ctx.fill();
    drawText(ctx, `${score}  ·  ${cpuScore}`, W / 2, 28, 18, COLORS.muted, 'center');
    if (over) drawGameOver(ctx, score >= 7 ? 'You win' : 'CPU wins', 'Restart for another match');
  });
  h.onRestart = reset; h.restart.addEventListener('click', reset); reset();
  return () => { stop(); cleanKeys(); };
}

function stack(stage, game) {
  const h = canvasShell(stage, game, 'Drop each slab onto the stack. Click or press Space.');
  let blocks, current, score, over, camera;
  const reset = () => {
    blocks = [{ x: 130, w: 220, y: H - 44 }];
    current = { x: 0, w: 220, dir: 1, speed: 2.1 };
    score = 0; over = false; camera = 0; h.setScore(0);
  };
  const drop = () => {
    if (over) return;
    const last = blocks[blocks.length - 1];
    const overlap = Math.max(0, Math.min(last.x + last.w, current.x + current.w) - Math.max(last.x, current.x));
    if (overlap <= 0) { over = true; h.record(score); return; }
    blocks.push({ x: Math.max(last.x, current.x), w: overlap, y: last.y - 24 });
    score += 10; h.setScore(score);
    if (blocks.length > 12) { blocks.shift(); camera += 24; }
    current = { x: 0, w: 220, dir: 1, speed: Math.min(5.5, 2.1 + blocks.length * .14) };
  };
  h.canvas.addEventListener('pointerdown', (e) => { e.preventDefault(); drop(); });
  const cleanKeys = keys((e) => { if (e.code === 'Space' || e.code === 'ArrowDown') drop(); });
  const stop = loop((dt) => {
    if (over) return;
    current.x += current.speed * current.dir * dt;
    if (current.x < 0) { current.x = 0; current.dir = 1; }
    if (current.x + current.w > W) { current.x = W - current.w; current.dir = -1; }
  }, () => {
    const { ctx } = h;
    ctx.fillStyle = COLORS.bg; ctx.fillRect(0, 0, W, H);
    for (const b of blocks) {
      ctx.fillStyle = COLORS.accent;
      ctx.fillRect(b.x, b.y + camera, b.w, 20);
      ctx.fillStyle = 'rgba(255,255,255,.15)';
      ctx.fillRect(b.x, b.y + camera, b.w, 3);
    }
    ctx.fillStyle = COLORS.pink;
    ctx.fillRect(current.x, H - 68, current.w, 20);
    if (over) drawGameOver(ctx, 'Tower fell', 'Restart to stack again');
  });
  h.onRestart = reset; h.restart.addEventListener('click', reset); reset();
  return () => { stop(); cleanKeys(); };
}

function asteroid(stage, game) {
  const h = canvasShell(stage, game, 'Dodge the field. Left/Right or A/D to steer.');
  let shipX, rocks, score, over, spawn;
  const reset = () => {
    shipX = W / 2; rocks = []; score = 0; over = false; spawn = 0; h.setScore(0);
  };
  const cleanKeys = keys((e) => {
    if (e.code === 'ArrowLeft' || e.code === 'KeyA') shipX = Math.max(24, shipX - 34);
    if (e.code === 'ArrowRight' || e.code === 'KeyD') shipX = Math.min(W - 24, shipX + 34);
  });
  let dragX = 0;
  h.canvas.addEventListener('pointerdown', (e) => { dragX = h.point(e).x; });
  h.canvas.addEventListener('pointermove', (e) => { if (dragX) { const x = h.point(e).x; shipX = Math.max(24, Math.min(W - 24, shipX + (x - dragX))); dragX = x; } });
  h.canvas.addEventListener('pointerup', () => { dragX = 0; });
  const stop = loop((dt) => {
    if (over) return;
    spawn += dt;
    if (spawn > 20) { spawn = 0; const size = 10 + Math.random() * 24; rocks.push({ x: Math.random() * W, y: -size, r: size, vy: 1.5 + Math.random() * 3, vx: (Math.random() - .5) * .8 }); }
    for (const rock of rocks) { rock.x += rock.vx * dt; rock.y += rock.vy * dt; }
    rocks = rocks.filter((rock) => rock.y < H + 50);
    score += .55 * dt; h.setScore(score);
    if (rocks.some((rock) => Math.hypot(rock.x - shipX, rock.y - (H - 38)) < rock.r + 12)) { over = true; h.record(score); }
  }, () => {
    const { ctx } = h;
    ctx.fillStyle = COLORS.bg; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(255,255,255,.13)';
    for (let i = 0; i < 40; i += 1) ctx.fillRect((i * 97) % W, (i * 53 + performance.now() * .02) % H, 2, 2);
    for (const rock of rocks) {
      ctx.fillStyle = COLORS.amber; ctx.beginPath(); ctx.arc(rock.x, rock.y, rock.r, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = 'rgba(0,0,0,.25)'; ctx.beginPath(); ctx.arc(rock.x + rock.r * .25, rock.y + rock.r * .2, rock.r * .3, 0, Math.PI * 2); ctx.fill();
    }
    ctx.fillStyle = COLORS.pink;
    ctx.beginPath(); ctx.moveTo(shipX, H - 58); ctx.lineTo(shipX - 14, H - 26); ctx.lineTo(shipX + 14, H - 26); ctx.closePath(); ctx.fill();
    if (over) drawGameOver(ctx, 'Impact', 'Restart for another run');
  });
  h.onRestart = reset; h.restart.addEventListener('click', reset); reset();
  return () => { stop(); cleanKeys(); };
}

function bubble(stage, game) {
  const h = canvasShell(stage, game, 'Pop the bubbles before the 40-second clock ends.');
  let bubbles, score, left, spawn, over;
  const reset = () => { bubbles = []; score = 0; left = 40; spawn = 0; over = false; h.setScore(0); };
  h.canvas.addEventListener('pointerdown', (e) => {
    if (over) { reset(); return; }
    const p = h.point(e);
    for (let i = bubbles.length - 1; i >= 0; i -= 1) {
      if (Math.hypot(bubbles[i].x - p.x, bubbles[i].y - p.y) < bubbles[i].r + 5) {
        bubbles.splice(i, 1); score += 5; h.setScore(score); break;
      }
    }
  });
  const stop = loop((dt) => {
    if (over) return;
    left -= dt / 60; if (left <= 0) { left = 0; over = true; h.record(score); return; }
    spawn += dt;
    if (spawn > 16) { spawn = 0; bubbles.push({ x: 30 + Math.random() * (W - 60), y: H + 20, r: 14 + Math.random() * 18, vy: .7 + Math.random() * 1.4, hue: [COLORS.accent, COLORS.pink, COLORS.amber, COLORS.green][Math.floor(Math.random() * 4)] }); }
    for (const b of bubbles) b.y -= b.vy * dt;
    bubbles = bubbles.filter((b) => b.y > -30);
  }, () => {
    const { ctx } = h;
    ctx.fillStyle = COLORS.bg; ctx.fillRect(0, 0, W, H);
    drawText(ctx, `${left.toFixed(1)}s`, 14, 26, 16, COLORS.muted);
    for (const b of bubbles) {
      ctx.strokeStyle = b.hue; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = `${b.hue}22`; ctx.fill();
    }
    if (over) drawGameOver(ctx, 'Time', `You popped ${score / 5} bubbles`);
  });
  h.onRestart = reset; h.restart.addEventListener('click', reset); reset();
  return () => stop();
}

function runner(stage, game) {
  const h = canvasShell(stage, game, 'Jump the obstacles. Click, tap or Space.');
  let y, vy, obstacles, score, over, spawn, speed;
  const reset = () => { y = H - 48; vy = 0; obstacles = []; score = 0; over = false; spawn = 0; speed = 3.4; h.setScore(0); };
  const jump = () => { if (over) { reset(); return; } if (y >= H - 50) vy = -7.4; };
  h.canvas.addEventListener('pointerdown', (e) => { e.preventDefault(); jump(); });
  const cleanKeys = keys((e) => { if (e.code === 'Space' || e.code === 'ArrowUp') jump(); });
  const stop = loop((dt) => {
    if (over) return;
    vy += .38 * dt; y += vy * dt;
    if (y > H - 48) { y = H - 48; vy = 0; }
    spawn += dt; if (spawn > 58) { spawn = 0; obstacles.push({ x: W + 20, w: 18 + Math.random() * 20, h: 20 + Math.random() * 26 }); }
    for (const o of obstacles) o.x -= speed * dt;
    obstacles = obstacles.filter((o) => o.x > -40);
    score += .6 * dt; h.setScore(score); speed = Math.min(7, 3.4 + score / 80);
    if (obstacles.some((o) => o.x < 70 && o.x + o.w > 44 && y + 18 > H - 48 - o.h)) { over = true; h.record(score); }
  }, () => {
    const { ctx } = h;
    ctx.fillStyle = COLORS.bg; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(255,255,255,.16)'; ctx.fillRect(0, H - 28, W, 2);
    for (const o of obstacles) { ctx.fillStyle = COLORS.pink; ctx.fillRect(o.x, H - 48 - o.h, o.w, o.h); }
    ctx.fillStyle = COLORS.green; ctx.fillRect(44, y, 20, 22);
    ctx.fillStyle = COLORS.bg; ctx.fillRect(49, y + 5, 4, 4);
    if (over) drawGameOver(ctx, 'Trip', 'Restart to run again');
  });
  h.onRestart = reset; h.restart.addEventListener('click', reset); reset();
  return () => { stop(); cleanKeys(); };
}

/* ------------------------------------------------------------------ DOM games */
function game2048(stage, game) {
  const h = domShell(stage, game, 'Arrow keys or swipe to merge matching tiles.');
  let grid, score, over, won;
  const reset = () => {
    grid = Array.from({ length: 4 }, () => [0, 0, 0, 0]); score = 0; over = false; won = false;
    add(); add(); h.setScore(0); paint();
  };
  const add = () => {
    const empty = [];
    grid.forEach((row, r) => row.forEach((v, c) => { if (!v) empty.push([r, c]); }));
    if (!empty.length) return;
    const [r, c] = empty[Math.floor(Math.random() * empty.length)];
    grid[r][c] = Math.random() < .9 ? 2 : 4;
  };
  const paint = () => {
    h.board.innerHTML = html`<div class="g2048">${grid.flatMap((row, r) => row.map((v, c) => html`<div class="g2048__cell g2048__v${v}" data-v="${v}">${v || ''}</div>`))}</div>`;
    h.setScore(score);
    if (over) h.record(score);
  };
  const move = (dr, dc) => {
    if (over) return;
    const before = JSON.stringify(grid);
    const rows = [...Array(4).keys()];
    const order = (dr > 0 || dc > 0) ? rows.slice().reverse() : rows;
    let moved = false;
    for (const r of order) for (const c of order) {
      let v = grid[r][c]; if (!v) continue;
      let nr = r, nc = c;
      while (true) {
        const tr = nr + dr, tc = nc + dc;
        if (tr < 0 || tr > 3 || tc < 0 || tc > 3) break;
        if (!grid[tr][tc]) { grid[tr][tc] = v; grid[nr][nc] = 0; nr = tr; nc = tc; moved = true; continue; }
        if (grid[tr][tc] === v) {
          grid[tr][tc] = v * 2; grid[nr][nc] = 0; score += v * 2; moved = true;
          if (v * 2 === 2048) won = true;
        }
        break;
      }
    }
    if (moved) { add(); paint(); }
    if (JSON.stringify(grid) === before) return;
    if (grid.flat().every((v) => v) && !canMove()) { over = true; paint(); }
  };
  const canMove = () => {
    for (let r = 0; r < 4; r += 1) for (let c = 0; c < 4; c += 1) {
      if (!grid[r][c]) return true;
      if (r < 3 && grid[r][c] === grid[r + 1][c]) return true;
      if (c < 3 && grid[r][c] === grid[r][c + 1]) return true;
    }
    return false;
  };
  const cleanKeys = keys((e) => {
    if (e.code === 'ArrowUp' || e.code === 'KeyW') move(-1, 0);
    if (e.code === 'ArrowDown' || e.code === 'KeyS') move(1, 0);
    if (e.code === 'ArrowLeft' || e.code === 'KeyA') move(0, -1);
    if (e.code === 'ArrowRight' || e.code === 'KeyD') move(0, 1);
  });
  let sx = 0, sy = 0;
  h.board.addEventListener('pointerdown', (e) => { sx = e.clientX; sy = e.clientY; });
  h.board.addEventListener('pointerup', (e) => {
    const dx = e.clientX - sx, dy = e.clientY - sy;
    if (Math.max(Math.abs(dx), Math.abs(dy)) < 25) return;
    if (Math.abs(dx) > Math.abs(dy)) move(0, dx > 0 ? 1 : -1); else move(dy > 0 ? 1 : -1, 0);
  });
  reset();
  h.onRestart = reset; h.restart.addEventListener('click', reset);
  return () => cleanKeys();
}

function memory(stage, game) {
  const h = domShell(stage, game, 'Click two cards. Match all eight pairs.');
  const pairs = ['CLIMATE', 'SPACE', 'SPORTS', 'TECH', 'MUSIC', 'HEALTH', 'WORLD', 'MONEY'];
  let cards, open, moves, score, lock, started, timer;
  const reset = () => {
    cards = [...pairs, ...pairs].sort(() => Math.random() - .5).map((word) => ({ word, flipped: false, done: false }));
    open = []; moves = 0; score = 0; lock = false; started = performance.now(); h.setScore(0); paint();
    clearInterval(timer);
    timer = setInterval(() => { const el = h.board.querySelector('[data-memory-time]'); if (el) el.textContent = `${Math.floor((performance.now() - started) / 1000)}s`; }, 500);
  };
  const paint = () => {
    h.board.innerHTML = html`<div class="memory-grid">${cards.map((card, i) => html`
      <button class="memory-card ${card.flipped || card.done ? 'is-open' : ''} ${card.done ? 'is-done' : ''}" data-card="${i}" ${card.done ? 'disabled' : ''}>
        <span>${card.flipped || card.done ? card.word : '?'}</span>
      </button>`)}</div>
      <p class="tiny muted" style="text-align:center;margin-top:.5rem">Moves ${moves} · <span data-memory-time>0s</span></p>`;
    h.board.querySelectorAll('[data-card]').forEach((button) => button.addEventListener('click', () => flip(Number(button.dataset.card))));
  };
  const flip = (index) => {
    if (lock || cards[index].flipped || cards[index].done) return;
    cards[index].flipped = true; open.push(index); paint();
    if (open.length < 2) return;
    moves += 1; h.setScore(moves);
    const [a, b] = open;
    if (cards[a].word === cards[b].word) {
      cards[a].done = true; cards[b].done = true; open = [];
      if (cards.every((c) => c.done)) { clearInterval(timer); score = Math.max(40, 1000 - moves * 30); h.record(score); confetti(20); }
      paint();
    } else {
      lock = true;
      setTimeout(() => { cards[a].flipped = false; cards[b].flipped = false; open = []; lock = false; paint(); }, 620);
    }
  };
  reset(); h.onRestart = reset; h.restart.addEventListener('click', reset);
  return () => clearInterval(timer);
}

function simon(stage, game) {
  const h = domShell(stage, game, 'Watch the sequence, then repeat it. It gets longer each round.');
  const pads = ['#7c5cff', '#45d6a4', '#ffbd5c', '#ff4d8d'];
  let seq, input, score, playing, showing;
  const reset = () => { seq = []; input = []; score = 0; playing = false; showing = false; h.setScore(0); next(); };
  const paint = () => {
    h.board.innerHTML = html`<div class="simon-grid">${pads.map((color, i) => html`<button class="simon-pad" data-pad="${i}" style="--pad:${color}" aria-label="Pad ${i + 1}"></button>`)}
      <div class="simon-center"><b>${score}</b><span>round</span></div></div>`;
    h.board.querySelectorAll('[data-pad]').forEach((button) => button.addEventListener('click', () => press(Number(button.dataset.pad))));
  };
  const flash = (i) => {
    const pad = h.board.querySelector(`[data-pad="${i}"]`);
    if (!pad) return;
    pad.classList.add('is-flash');
    setTimeout(() => pad.classList.remove('is-flash'), 260);
  };
  const play = async () => {
    showing = true;
    for (const i of seq) { flash(i); await new Promise((r) => setTimeout(r, 430)); }
    showing = false;
  };
  const next = () => {
    seq.push(Math.floor(Math.random() * 4)); input = []; paint(); setTimeout(play, 380);
  };
  const press = (i) => {
    if (showing) return; if (playing) return;
    flash(i); input.push(i);
    if (input[input.length - 1] !== seq[input.length - 1]) {
      playing = true; h.record(score); toast(`Sequence ended at round ${score}`); return;
    }
    if (input.length === seq.length) {
      score += 1; h.setScore(score); input = []; setTimeout(next, 500);
    }
  };
  reset(); h.onRestart = reset; h.restart.addEventListener('click', reset);
  return () => {};
}

function tictactoe(stage, game) {
  const h = domShell(stage, game, 'You are X. The CPU is O. Get three in a row.');
  let board, wins, losses, over;
  const lines = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
  const reset = () => { board = Array(9).fill(''); wins = 0; losses = 0; over = false; h.setScore(0); paint(); };
  const winner = (b) => { for (const [a,c,d] of lines) if (b[a] && b[a] === b[c] && b[a] === b[d]) return b[a]; return b.every(Boolean) ? 'draw' : null; };
  const minimax = (b, player) => {
    const result = winner(b);
    if (result === 'O') return { score: 10 }; if (result === 'X') return { score: -10 }; if (result === 'draw') return { score: 0 };
    let best = { score: player === 'O' ? -Infinity : Infinity, move: -1 };
    for (let i = 0; i < 9; i += 1) if (!b[i]) {
      b[i] = player; const value = minimax(b, player === 'O' ? 'X' : 'O').score; b[i] = '';
      if (player === 'O' ? value > best.score : value < best.score) best = { score: value, move: i };
    }
    return best;
  };
  const paint = () => {
    h.board.innerHTML = html`<div class="ttt-grid">${board.map((v, i) => html`<button class="ttt-cell ${v ? 'is-set' : ''}" data-cell="${i}" ${v || over ? 'disabled' : ''}>${v}</button>`)}
      </div><p class="tiny muted" style="text-align:center;margin-top:.5rem">You ${wins} · CPU ${losses}</p>`;
    h.board.querySelectorAll('[data-cell]').forEach((button) => button.addEventListener('click', () => play(Number(button.dataset.cell))));
  };
  const finish = () => {
    const result = winner(board); over = true;
    if (result === 'X') { wins += 1; h.setScore(wins * 100); confetti(15); } else if (result === 'O') losses += 1;
    else if (result === 'draw') h.setScore(wins * 100);
    if (result) h.record(wins * 100); paint();
  };
  const play = (index) => {
    if (over || board[index]) return;
    board[index] = 'X'; paint();
    if (winner(board)) { finish(); return; }
    const best = minimax([...board], 'O');
    if (best.move >= 0) board[best.move] = 'O';
    paint();
    if (winner(board)) finish();
  };
  reset(); h.onRestart = reset; h.restart.addEventListener('click', reset);
  return () => {};
}

function mines(stage, game) {
  const h = domShell(stage, game, 'Click to reveal. Right-click or Flag mode to mark mines.');
  let cells, over, flags, revealed, flagMode, started, timer;
  const reset = () => {
    cells = Array.from({ length: 64 }, (_, i) => ({ i, mine: false, open: false, flag: false, near: 0 }));
    let placed = 0;
    while (placed < 10) { const i = Math.floor(Math.random() * 64); if (!cells[i].mine) { cells[i].mine = true; placed += 1; } }
    for (const cell of cells) {
      if (cell.mine) continue;
      const r = Math.floor(cell.i / 8), c = cell.i % 8;
      let near = 0;
      for (let dr = -1; dr <= 1; dr += 1) for (let dc = -1; dc <= 1; dc += 1) {
        const nr = r + dr, nc = c + dc;
        if (nr >= 0 && nr < 8 && nc >= 0 && nc < 8) near += cells[nr * 8 + nc].mine ? 1 : 0;
      }
      cell.near = near;
    }
    over = false; flags = 0; revealed = 0; flagMode = false; started = performance.now(); h.setScore(0); paint();
    clearInterval(timer);
    timer = setInterval(() => { const el = h.board.querySelector('[data-mines-time]'); if (el && !over) el.textContent = `${Math.floor((performance.now() - started) / 1000)}s`; }, 500);
  };
  const reveal = (index) => {
    if (over) return;
    const cell = cells[index];
    if (cell.open || cell.flag) return;
    if (cell.mine) { over = true; clearInterval(timer); cells.forEach((c) => { if (c.mine) c.open = true; }); h.record(revealed); paint(); return; }
    const stack = [cell];
    while (stack.length) {
      const c = stack.pop(); if (c.open || c.flag) continue;
      c.open = true; revealed += 1; h.setScore(revealed);
      if (c.near === 0) {
        const r = Math.floor(c.i / 8), col = c.i % 8;
        for (let dr = -1; dr <= 1; dr += 1) for (let dc = -1; dc <= 1; dc += 1) {
          const nr = r + dr, nc = col + dc;
          if (nr >= 0 && nr < 8 && nc >= 0 && nc < 8) stack.push(cells[nr * 8 + nc]);
        }
      }
    }
    if (revealed >= 54) { over = true; clearInterval(timer); h.record(1000); confetti(20); }
    paint();
  };
  const paint = () => {
    h.board.innerHTML = html`<div class="mines-head"><span class="tiny muted">Flags ${flags}/10 · <span data-mines-time>0s</span></span><button class="btn btn--sm ${flagMode ? 'btn--primary' : 'btn--ghost'}" data-flag>${flagMode ? 'Flag mode on' : 'Flag mode'}</button></div>
      <div class="mines-grid">${cells.map((cell) => html`<button class="mines-cell ${cell.open ? 'is-open' : ''} ${cell.mine && cell.open ? 'is-mine' : ''} n${cell.near}" data-mine="${cell.i}" ${cell.open ? 'disabled' : ''}>${cell.flag ? 'F' : cell.open ? (cell.mine ? 'X' : (cell.near || '')) : ''}</button>`)}</div>`;
    h.board.querySelector('[data-flag]')?.addEventListener('click', () => { flagMode = !flagMode; paint(); });
    h.board.querySelectorAll('[data-mine]').forEach((button) => {
      button.addEventListener('click', (e) => {
        const i = Number(button.dataset.mine); const cell = cells[i];
        if (flagMode) { if (!cell.open) { cell.flag = !cell.flag; flags += cell.flag ? 1 : -1; paint(); } return; }
        reveal(i);
      });
      button.addEventListener('contextmenu', (e) => { e.preventDefault(); const cell = cells[Number(button.dataset.mine)]; if (!cell.open) { cell.flag = !cell.flag; flags += cell.flag ? 1 : -1; paint(); } });
    });
  };
  reset(); h.onRestart = reset; h.restart.addEventListener('click', reset);
  return () => clearInterval(timer);
}

function word(stage, game) {
  const h = domShell(stage, game, 'Unscramble the news word. Type it and press Enter.');
  const words = ['CLIMATE', 'ELECTION', 'BUDGET', 'SATELLITE', 'PLAYOFF', 'CURRENCY', 'PROTEST', 'STARTUP', 'CAMPUS', 'HISTORY', 'SCIENCE', 'CULTURE'];
  let score, current, scrambled, left, over, timer;
  const scramble = (word) => word.split('').sort(() => Math.random() - .5).join('');
  const next = () => {
    current = words[Math.floor(Math.random() * words.length)];
    scrambled = scramble(current);
    h.board.innerHTML = html`<div class="word-game">
      <p class="word-game__scramble">${scrambled}</p>
      <form class="word-game__form"><input name="answer" autocomplete="off" spellcheck="false" placeholder="Your answer" aria-label="Unscramble the word"><button class="btn btn--primary" type="submit">Check</button></form>
      <p class="tiny muted">${current.length} letters · ${left}s left</p></div>`;
    h.board.querySelector('form')?.addEventListener('submit', (event) => {
      event.preventDefault();
      const value = event.currentTarget.answer.value.trim().toUpperCase();
      if (value !== current) { toast('Not quite — try again.', { type: 'bad' }); return; }
      score += current.length * 10; h.setScore(score); next();
    });
  };
  const reset = () => { score = 0; left = 60; over = false; h.setScore(0); next(); clearInterval(timer); timer = setInterval(() => { left -= 1; if (left <= 0) { left = 0; over = true; clearInterval(timer); h.record(score); h.board.querySelector('.word-game')?.insertAdjacentHTML('beforeend', '<p class="tiny muted">Time. Press Restart to play again.</p>'); } else if (!over) { const label = h.board.querySelector('.word-game p.tiny'); if (label) label.textContent = `${current.length} letters · ${left}s left`; } }, 1000); };
  reset(); h.onRestart = reset; h.restart.addEventListener('click', reset);
  return () => clearInterval(timer);
}

function reaction(stage, game) {
  const h = domShell(stage, game, 'Click the lit square as fast as you can for 30 seconds.');
  let score, left, target, over, timer, started;
  const reset = () => {
    score = 0; left = 30; target = -1; over = false; started = performance.now(); h.setScore(0);
    h.board.innerHTML = html`<div class="reaction-wrap"><div class="reaction-grid">${Array.from({ length: 9 }).map((_, i) => html`<button class="reaction-cell" data-react="${i}" aria-label="Target ${i + 1}"></button>`)}</div><p class="tiny muted"><span data-reaction-timer>30s left</span> · <span data-reaction-last>waiting</span></p></div>`;
    h.board.querySelectorAll('[data-react]').forEach((button) => button.addEventListener('click', () => hit(Number(button.dataset.react), button)));
    move();
    clearInterval(timer);
    timer = setInterval(() => {
      left -= 1;
      const timerEl = h.board.querySelector('[data-reaction-timer]');
      if (timerEl) timerEl.textContent = `${left}s left`;
      if (left <= 0) {
        left = 0;
        over = true;
        clearInterval(timer);
        h.record(score);
        h.board.querySelector('.reaction-wrap')?.insertAdjacentHTML('beforeend', '<p class="tiny muted">Time. Restart to play again.</p>');
      }
    }, 1000);
  };
  const move = () => {
    if (over) return;
    const next = Math.floor(Math.random() * 9);
    target = next === target ? (next + 1) % 9 : next;
    h.board.querySelectorAll('[data-react]').forEach((button, i) => button.classList.toggle('is-target', i === target));
    window.__pulseReactionAt = performance.now();
  };
  const hit = (index, button) => {
    if (over || index !== target) return;
    score += 1; h.setScore(score); button.classList.add('is-hit');
    const last = h.board.querySelector('[data-reaction-last]');
    if (last) last.textContent = `${Math.round(performance.now() - (window.__pulseReactionAt || performance.now()))} ms`;
    window.__pulseReactionAt = performance.now();
    setTimeout(() => button.classList.remove('is-hit'), 140);
    move();
  };
  reset(); h.onRestart = reset; h.restart.addEventListener('click', reset);
  return () => clearInterval(timer);
}

const STARTERS = { flappy, snake, breakout, pong, stack, asteroid, bubble, runner, '2048': game2048, memory, simon, ttt: tictactoe, mines, word, reaction };

function openGame(game, onFinish) {
  const stage = document.createElement('div');
  stage.className = 'arcade-stage';
  let cleanup = () => {};
  cleanup = STARTERS[game.id]?.(stage, game) || (() => {});
  modal({
    title: game.title,
    wide: true,
    body: stage,
    onClose: () => { try { cleanup(); } catch { /* ignore */ } onFinish?.(); },
    actions: [{ label: 'Close' }],
  });
}

export function arcadeView(root, ctx) {
  const genre = ctx?.query?.genre || 'All';
  const store = readStore();
  const plays = Object.values(store).reduce((sum, row) => sum + Number(row?.plays || 0), 0);
  const best = Object.values(store).reduce((sum, row) => sum + Number(row?.best || 0), 0);
  const shown = genre === 'All' ? GAMES : GAMES.filter((game) => game.genre === genre);
  const settings = readSettings();
  window.__pulseArcadeDifficulty = settings.difficulty;
  const daily = dailyGame();
  const achievements = [
    { label: 'First game', on: plays > 0 },
    { label: 'Three-star club', on: Object.values(store).some((row) => Number(row?.stars) >= 3) },
    { label: 'Arcade regular', on: plays >= 10 },
    { label: 'Full house', on: Object.keys(store).length >= 15 },
  ];
  root.innerHTML = html`
    <section class="arcade-hero">
      <p class="eyebrow">Arcade · take a brain break</p>
      <h1>Fifteen small games.<br>No feeds, no ads.</h1>
      <p>Short, replayable arcade and puzzle games built into Pulse. Scores live on this device.</p>
      <div class="arcade-stats">
        <div><b>15</b><span>games</span></div>
        <div><b>${plays}</b><span>plays</span></div>
        <div><b>${best.toLocaleString()}</b><span>best total</span></div>
      </div>
      <div class="arcade-toolbar">
        <div class="arcade-difficulty"><span>Difficulty</span>
          ${[['chill', 'Chill'], ['normal', 'Normal'], ['turbo', 'Turbo']].map(([id, label]) => html`<button class="chip ${settings.difficulty === id ? 'is-on' : ''}" data-difficulty="${id}">${label}</button>`)}
        </div>
        <button class="chip ${settings.sound ? 'is-on' : ''}" data-arcade-sound>${raw(icons.sound)} Sound ${settings.sound ? 'on' : 'off'}</button>
      </div>
      <div class="arcade-daily">
        <span class="eyebrow">Daily challenge</span>
        <b>${daily.title}</b>
        <span class="tiny muted">Get at least two stars today.</span>
        <button class="btn btn--sm btn--primary" data-daily="${daily.id}">Play daily</button>
      </div>
      <div class="arcade-achievements">
        ${achievements.map((item) => html`<span class="arcade-achievement ${item.on ? 'is-on' : ''}">${item.label}</span>`)}
      </div>
    </section>
    <div class="chip-row arcade-filters">
      ${GENRES.map((filter) => html`<button class="chip ${genre === filter ? 'is-on' : ''}" data-genre="${filter}">${filter}</button>`)}
    </div>
    <div class="arcade-grid">
      ${shown.map((game) => html`
        <article class="arcade-card" data-game="${game.id}" style="--game:${game.color}">
          <div class="arcade-card__top"><span>${game.genre}</span><span class="arcade-card__best">${bestOf(game.id) ? `Best ${bestOf(game.id).toLocaleString()}` : 'New'} ${starMarkup(starCount(game.id))}</span></div>
          <div class="arcade-card__art" aria-hidden="true"><i></i><i></i><i></i><i></i><b>${game.title.split(' ').map((w) => w[0]).join('').slice(0, 3)}</b></div>
          <h2>${game.title}</h2>
          <p>${game.blurb}</p>
          <div class="arcade-card__foot"><span>${game.controls}</span><button class="btn btn--sm btn--primary" data-play="${game.id}">${raw(icons.play)} Play</button></div>
        </article>`)}
    </div>
    <p class="tiny faint arcade-note">All games run locally. High scores, stars, difficulty and sound stay in this browser. Built for keyboard, mouse and touch.</p>`;

  function starCount(id) { return Number(readStore()[id]?.stars || starsFor(id, bestOf(id))); }
  root.querySelectorAll('[data-genre]').forEach((button) => button.addEventListener('click', () => {
    arcadeView(root, { query: { genre: button.dataset.genre } });
  }));
  root.querySelectorAll('[data-difficulty]').forEach((button) => button.addEventListener('click', () => {
    saveSettings({ ...readSettings(), difficulty: button.dataset.difficulty });
    root.querySelectorAll('[data-difficulty]').forEach((node) => node.classList.toggle('is-on', node === button));
    toast(`Arcade difficulty: ${button.textContent.trim()}`);
  }));
  root.querySelector('[data-arcade-sound]')?.addEventListener('click', (event) => {
    const next = { ...readSettings(), sound: !readSettings().sound };
    saveSettings(next);
    event.currentTarget.classList.toggle('is-on', next.sound);
    event.currentTarget.innerHTML = `${raw(icons.sound)} Sound ${next.sound ? 'on' : 'off'}`;
  });
  root.querySelectorAll('[data-play], [data-game]').forEach((node) => node.addEventListener('click', (event) => {
    if (event.target.closest('[data-genre]')) return;
    const game = GAMES.find((item) => item.id === (node.dataset.play || node.dataset.game));
    if (game) openGame(game, () => arcadeView(root, { query: { genre } }));
  }));
}
