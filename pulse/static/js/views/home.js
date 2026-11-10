import { get, post } from '../api.js';
import { navigate } from '../router.js';
import {
  state, record, emit, dailyProgress, streak, levels, followedTopics, topicLabel,
} from '../store.js';
import { html, raw, mount, icons, toast, timeAgo, compactNumber, errorState, setLoading } from '../ui.js';
import {
  heroCard, storyCard, scoreMini, sectionHead, emptyState, skeletonFeed, topicTile,
} from '../components.js';

const STREAMS = [
  { id: 'for-you', label: 'For you' },
  { id: 'top', label: 'Top' },
  { id: 'breaking', label: 'Breaking' },
  { id: 'latest', label: 'Latest' },
  { id: 'longreads', label: 'Long reads' },
];

function greeting() {
  const hour = new Date().getHours();
  const part = hour < 12 ? 'Morning' : hour < 18 ? 'Afternoon' : 'Evening';
  const name = (state.profile?.name || '').trim();
  return name && name !== 'Student' ? `Good ${part}, ${name.split(' ')[0]}` : `Good ${part}`;
}

function todayLine() {
  const date = new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric' }).format(new Date());
  const archive = state.boot?.archive?.total || state.boot?.stats?.articles || 0;
  const healthy = state.boot?.feed_health?.healthy || 0;
  const feeds = state.boot?.feed_health?.total || 0;
  return `${date} · ${compactNumber(archive)} stories archived · ${healthy}/${feeds} feeds live`;
}

export async function homeView(root, ctx) {
  const stream = STREAMS.some((s) => s.id === ctx.query.stream) ? ctx.query.stream : 'for-you';
  const profile = state.profile || {};
  const progress = dailyProgress();
  const streakInfo = streak();
  const levelInfo = levels();

  root.innerHTML = html`
    <div id="breaking-slot"></div>
    <div class="greeting">
      <div>
        <h1>${greeting()}</h1>
        <p class="greeting__meta">${todayLine()}</p>
      </div>
      <div class="hstack" style="gap:.5rem">
        ${streakInfo.count > 0 ? html`<span class="pill-progress" title="Daily streak">🔥 ${streakInfo.count} day${streakInfo.count === 1 ? '' : 's'}</span>` : ''}
        <a class="pill-progress" href="/brief" data-link title="Your two-minute briefing">
          <span aria-hidden="true">⚡</span> 2-min brief ${raw(icons.chevron)}
        </a>
        <a class="pill-progress" href="/profile" data-link title="Level ${levelInfo.level}">
          <span class="progress" role="progressbar" aria-valuenow="${levelInfo.progress.percent}" aria-valuemin="0" aria-valuemax="100"><span style="width:${levelInfo.progress.percent}%"></span></span>
          Lv ${levelInfo.level}
        </a>
      </div>
    </div>

    <div id="hero-slot">${raw('<div class="skeleton" style="height:340px;border-radius:22px;margin-bottom:1rem"></div>')}</div>

    <div class="between" style="margin:1.2rem 0 .8rem;gap:1rem">
      <div class="segmented" role="tablist" aria-label="Feed streams">
        ${STREAMS.map((s) => html`<button type="button" role="tab" aria-selected="${s.id === stream}" class="${s.id === stream ? 'is-on' : ''}" data-stream="${s.id}">${s.label}</button>`)}
      </div>
      <div class="hstack" style="gap:.5rem">
        <span class="tiny muted" id="feed-meta"></span>
        <button class="icon-btn" id="feed-refresh" title="Refresh feeds now" aria-label="Refresh feeds now">${raw(icons.refresh)}</button>
      </div>
    </div>

    <div class="chip-row" id="topic-chips"></div>

    <div id="feed-slot">${skeletonFeed(5)}</div>
    <div id="sports-slot"></div>
    <div id="sentinel" style="height:1px"></div>
  `;

  renderTopics(root, stream);
  bindStreams(root, stream);
  bindRefresh(root, stream);

  // Breaking strip and sports strip in parallel with the feed.
  loadBreaking(root);
  loadSports(root);
  loadFeed(root, { stream, offset: 0, append: false });
}

function renderTopics(root, stream) {
  const chips = followedTopics().concat(['world', 'tech', 'sports', 'culture', 'science']);
  const unique = [...new Set(chips)];
  const slot = root.querySelector('#topic-chips');
  slot.innerHTML = html`
    <a class="chip ${stream === 'for-you' ? '' : ''}" href="/discover" data-link>${raw(icons.compass)} Explore all</a>
    ${unique.map((slug) => html`<a class="chip" href="/topic/${slug}" data-link>${state.topicMap.get(slug)?.icon || '•'} ${topicLabel(slug)}</a>`)}
  `;
}

function bindRefresh(root, stream) {
  const button = root.querySelector('#feed-refresh');
  if (!button) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    button.classList.add('spin');
    try {
      await post('/api/ingest/refresh', {});
      toast('Refreshing feeds…');
      for (let i = 0; i < 30; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const status = await get('/api/ingest/status', 0, true);
        if (!status.running) break;
      }
      await loadFeed(root, { stream, offset: 0, append: false });
      toast('Up to date', { type: 'good' });
    } catch (err) {
      toast(err.message, { type: 'bad' });
    } finally {
      button.disabled = false;
      button.classList.remove('spin');
    }
  });
}

function bindStreams(root, stream) {
  root.querySelectorAll('[data-stream]').forEach((button) => {
    button.addEventListener('click', () => {
      const next = button.dataset.stream;
      if (next === stream) return;
      const url = next === 'for-you' ? '/' : `/?stream=${next}`;
      navigate(url);
    });
  });
}

async function loadBreaking(root) {
  try {
    const data = await get('/api/feed?mode=breaking&limit=5', 45);
    const seen = new Set();
    const items = (data.items || []).filter((item) => {
      if (!item.breaking) return false;
      const key = item.story?.id || item.id;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    const slot = root.querySelector('#breaking-slot');
    if (!slot) return;
    if (!items.length) { slot.innerHTML = ''; return; }
    slot.innerHTML = html`
      <div class="breaking-strip">
        <span class="breaking-strip__label"><span class="breaking-strip__dot"></span> Breaking</span>
        <div class="breaking-strip__items">
          ${items.slice(0, 5).map((item) => html`<a class="breaking-strip__item" href="/article/${item.id}" data-link>${item.title}</a>`)}
        </div>
      </div>`;
  } catch { /* strip is optional */ }
}

async function loadSports(root) {
  try {
    const data = await get('/api/sports', 20);
    const slot = root.querySelector('#sports-slot');
    if (!slot) return;
    const events = (data.events || []).slice(0, 8);
    if (!events.length) { slot.innerHTML = ''; return; }
    const live = events.filter((e) => e.is_live).length;
    slot.innerHTML = html`
      <div class="section">
        ${sectionHead(
          `🏆 Live & upcoming <span class="badge ${live ? 'badge--live' : 'badge--topic'}">${live ? `${live} live` : 'scores'}</span>`,
          html`<a href="/sports" data-link>All scores ${raw(icons.chevron)}</a>`,
        )}
        <div class="score-strip">${events.map((game) => scoreMini(game))}</div>
      </div>`;
  } catch { /* scores are optional */ }
}

function feedUrl(stream, offset, limit = 24) {
  const mode = stream === 'longreads' ? 'longreads' : stream;
  return `/api/feed?mode=${encodeURIComponent(mode)}&offset=${offset}&limit=${limit}${mode === 'longreads' ? '&days=30' : ''}`;
}

let observer = null;

async function loadFeed(root, { stream, offset, append }) {
  const slot = root.querySelector('#feed-slot');
  if (!slot) return;
  if (observer) { observer.disconnect(); observer = null; }
  if (!append) slot.innerHTML = skeletonFeed(5);
  try {
    const data = await get(feedUrl(stream, offset), 20);
    const items = data.items || [];
    if (!items.length) {
      slot.innerHTML = emptyState({
        icon: '📡',
        title: 'Nothing here yet',
        text: 'The archive fills up as feeds are fetched. Try another stream or search the archive.',
        action: '<a class="btn btn--primary" href="/discover" data-link>Explore</a>',
      });
      return;
    }
    if (!append) {
      let heroIndex = items.findIndex((item, index) => index < 4 && item.image);
      if (heroIndex < 0) heroIndex = 0;
      const first = items[heroIndex];
      const rest = items.filter((_, index) => index !== heroIndex);
      root.querySelector('#hero-slot').innerHTML = heroCard(first, {
        label: stream === 'breaking' ? 'Breaking' : stream === 'top' ? 'Top story' : 'For you',
      });
      slot.innerHTML = html`
        ${rest.length ? html`<div class="feed__divider">More for you</div>` : ''}
        <div class="feed" id="feed-list">${rest.map((item) => storyCard(item))}</div>`;
      const meta = root.querySelector('#feed-meta');
      if (meta) meta.textContent = `${Math.min(items.length, data.total)} of ${data.total} stories`;
    } else {
      const list = root.querySelector('#feed-list');
      if (list) list.insertAdjacentHTML('beforeend', items.map((item) => storyCard(item)).join(''));
      const meta = root.querySelector('#feed-meta');
      if (meta) meta.textContent = `${Math.min(offset + items.length, data.total)} of ${data.total} stories`;
    }
    if (data.has_more) {
      attachSentinel(root, stream, offset + items.length);
    } else {
      const list = root.querySelector('#feed-list');
      if (list && !list.dataset.ended) {
        list.dataset.ended = '1';
        list.insertAdjacentHTML('afterend', html`<div class="empty" style="padding:1.6rem"><p class="small muted">You're all caught up. The archive keeps growing — search it any time.</p></div>`);
      }
    }
  } catch (err) {
    if (append) toast('Could not load more stories', { type: 'bad' });
    else errorState(slot, err.message, () => loadFeed(root, { stream, offset, append: false }));
  }
}

function attachSentinel(root, stream, nextOffset) {
  const sentinel = root.querySelector('#sentinel');
  if (!sentinel) return;
  observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) {
      observer?.disconnect();
      observer = null;
      loadFeed(root, { stream, offset: nextOffset, append: true });
    }
  }, { rootMargin: '600px 0px' });
  observer.observe(sentinel);
}
