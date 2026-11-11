import { get, post } from '../api.js?v=1.4.0';
import { navigate } from '../router.js?v=1.4.0';
import {
  state, prefs, savePrefs, dailyProgress, streak, levels, followedTopics, topicLabel,
} from '../store.js?v=1.4.0';
import { html, raw, icons, toast, compactNumber, modal } from '../ui.js?v=1.4.0';
import {
  storyCard, topCard, hCard, mosaicCard, scoreMini, sectionHead, emptyState, skeletonFeed,
} from '../components.js?v=1.4.0';
import { open as openPalette, mountHomeSearch } from '../palette.js?v=1.4.0';

const DEFAULT_SECTIONS = ['brief', 'top', 'for-you', 'picks', 'my-sports', 'topic:tech', 'topic:world', 'topic:motorsport', 'longreads'];

const BASE_SECTIONS = [
  { id: 'brief', label: 'Your brief', hint: 'Five stories, two minutes' },
  { id: 'top', label: 'Top Stories', hint: 'What the most outlets are covering' },
  { id: 'picks', label: "Editor's picks", hint: 'Full-text stories worth the time' },
  { id: 'for-you', label: 'For you', hint: 'Your main personalised feed' },
  { id: 'sports', label: 'Live scores', hint: 'A scoreboard strip' },
  { id: 'my-sports', label: 'My sports', hint: 'Your pinned teams and leagues' },
  { id: 'longreads', label: 'Long reads', hint: 'Fewer, deeper pieces' },
  { id: 'saved', label: 'Saved for later', hint: 'A shortcut to your library' },
  { id: 'research', label: 'Research desk', hint: 'Citations and bibliography' },
];

function allSections() {
  const topics = (state.boot?.topics || []).map((topic) => ({
    id: `topic:${topic.slug}`,
    label: `${topic.icon} ${topic.label}`,
    hint: 'A topic row',
  }));
  return [...BASE_SECTIONS, ...topics];
}

function sectionMeta(id) {
  return allSections().find((section) => section.id === id) || { id, label: id, hint: '' };
}

function activeSections() {
  const saved = Array.isArray(prefs().home_sections) ? prefs().home_sections : [];
  const valid = saved.filter((id) => allSections().some((section) => section.id === id));
  return valid.length ? valid : DEFAULT_SECTIONS;
}

function localGreeting() {
  const hour = new Date().getHours();
  const part = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening';
  const name = (state.profile?.name || '').trim();
  const who = name && name !== 'Student' ? `, ${name.split(' ')[0]}` : '';
  return `Good ${part}${who}`;
}

function greeting() {
  const hour = new Date().getHours();
  const part = hour < 12 ? 'Morning' : hour < 18 ? 'Afternoon' : 'Evening';
  const name = (state.profile?.name || '').trim();
  return name && name !== 'Student' ? `Good ${part}, ${name.split(' ')[0]}` : `Good ${part}`;
}

function todayLine() {
  const archive = state.boot?.archive?.total || state.boot?.stats?.articles || 0;
  const healthy = state.boot?.feed_health?.healthy || 0;
  const feeds = state.boot?.feed_health?.total || 0;
  return `${compactNumber(archive)} stories archived · ${healthy}/${feeds} feeds live`;
}

const MOSAIC = [
  'hero', 'small', 'small', 'wide', 'small', 'medium',
  'small', 'small', 'wide', 'small', 'medium', 'small',
];

function mosaicOffset(seed) {
  let hash = 0;
  for (let i = 0; i < (seed || '').length; i += 1) hash = (hash * 31 + seed.charCodeAt(i)) % 997;
  return hash % MOSAIC.length;
}

function mosaicHtml(items, seed = '') {
  const offset = mosaicOffset(seed);
  return html`<div class="mosaic">${items.map((item, index) => mosaicCard(item, { size: MOSAIC[(index + offset) % MOSAIC.length] }))}</div>`;
}

export async function homeView(root, ctx) {
  const base = activeSections();
  const followed = followedTopics();
  const sections = [...base];
  for (const slug of followed) {
    const id = `topic:${slug}`;
    if (!sections.includes(id)) sections.push(id);
    if (sections.length > base.length + 3) break;
  }
  const progress = dailyProgress();
  const streakInfo = streak();
  const levelInfo = levels();

  root.innerHTML = html`
    <div class="today-bar">
      <div class="today-bar__main">
        <p class="today-bar__date">${new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric' }).format(new Date())}</p>
        <h1 class="today-bar__greeting">${greeting()}</h1>
        <p class="today-bar__meta">${todayLine()}</p>
      </div>
      <div class="today-bar__actions">
        ${streakInfo.count > 0 ? html`<span class="pill-progress" title="Daily streak">🔥 ${streakInfo.count} day${streakInfo.count === 1 ? '' : 's'}</span>` : ''}
        <a class="pill-progress" href="/profile" data-link title="Level ${levelInfo.level} · ${levelInfo.xp} XP">
          <span class="progress" role="progressbar" aria-valuenow="${levelInfo.progress.percent}" aria-valuemin="0" aria-valuemax="100"><span style="width:${levelInfo.progress.percent}%"></span></span>
          Lv ${levelInfo.level} · ${levelInfo.xp} XP
        </a>
      </div>
    </div>

    <button class="home-search" id="home-search" type="button">
      ${raw(icons.search)}
      <span>Search 300+ sources, topics and your archive…</span>
      <kbd class="kbd">⌘K</kbd>
    </button>

    <div class="between" style="margin:.2rem 0 .2rem">
      <div class="chip-row" id="quick-links">
        ${followedTopics().slice(0, 5).map((slug) => html`
          <a class="chip" href="/topic/${slug}" data-link>${state.topicMap.get(slug)?.icon || '•'} ${topicLabel(slug)}</a>`)}
        <a class="chip" href="/discover" data-link>${raw(icons.compass)} All sections</a>
      </div>
      <div class="hstack" style="gap:.3rem">
        <button class="btn btn--sm btn--ghost" id="customize-sections" title="Choose which sections appear">
          ${raw(icons.filter)} Customize
        </button>
        <button class="icon-btn" id="feed-refresh" title="Refresh feeds now" aria-label="Refresh feeds now">${raw(icons.refresh)}</button>
      </div>
    </div>

    <div id="home-sections" class="stack">
      ${sections.map((id) => {
        const meta = sectionMeta(id);
        return html`
          <section class="home-section" data-id="${id}" aria-label="${meta.label}">
            <div data-head></div>
            <div data-body>${id === 'for-you' ? skeletonFeed(4) : html`<div class="skeleton skeleton--card" style="height:150px"></div>`}</div>
          </section>`;
      })}
    </div>

    <div class="section" style="text-align:center">
      <button class="btn btn--ghost" id="add-section">${raw(icons.filter)} Add or reorder sections</button>
    </div>`;

  mountHomeSearch(root.querySelector('#home-search'));
  root.querySelector('#home-search').addEventListener('click', () => openPalette());
  root.querySelector('#customize-sections').addEventListener('click', () => openCustomizer(root, ctx));
  root.querySelector('#add-section').addEventListener('click', () => openCustomizer(root, ctx));
  bindRefresh(root, sections);
  bindQuickLinks(root);

  // Fill every section in parallel; each paints as soon as its data arrives.
  sections.forEach((id) => { fillSection(root, id); });
}

function bindQuickLinks(root) {
  root.querySelectorAll('#quick-links a').forEach((link) => {
    link.addEventListener('click', () => { /* router handles navigation */ });
  });
}

function bindRefresh(root, sections) {
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
      sections.forEach((id) => fillSection(root, id));
      toast('Up to date', { type: 'good' });
    } catch (err) {
      toast(err.message, { type: 'bad' });
    } finally {
      button.disabled = false;
      button.classList.remove('spin');
    }
  });
}

function sectionShell(root, id) {
  return root.querySelector(`.home-section[data-id="${CSS.escape(id)}"]`);
}

async function fillSection(root, id) {
  const shell = sectionShell(root, id);
  if (!shell) return;
  const head = shell.querySelector('[data-head]');
  const body = shell.querySelector('[data-body]');
  if (!body) return;
  try {
    if (id === 'brief') return renderBrief(shell, head, body);
    if (id === 'top') return renderTop(head, body);
    if (id === 'picks') return renderPicks(head, body);
    if (id === 'for-you') return renderForYou(root, shell, head, body);
    if (id === 'sports') return renderSports(head, body);
    if (id === 'my-sports') return renderMySports(head, body);
    if (id === 'longreads') return renderLongreads(head, body);
    if (id === 'saved') return renderSaved(head, body);
    if (id === 'research') return renderResearch(head, body);
    if (id.startsWith('topic:')) return renderTopic(head, body, id.slice(6));
  } catch (err) {
    body.innerHTML = html`<div class="card card-pad"><p class="small muted">${err.message}</p></div>`;
  }
}

async function renderBrief(shell, head, body) {
  head.innerHTML = '';
  const data = await get('/api/brief', 60, true);
  const minutes = data.minutes || 2;
  const count = (data.stories || []).length;
  const progress = dailyProgress();
  body.innerHTML = html`
    <div class="card card-pad-lg" style="background:var(--grad-soft);border-color:var(--line)">
      <div class="between">
        <div>
          <p class="eyebrow">${localGreeting()}</p>
          <h2 style="font-size:1.4rem;letter-spacing:-.03em;margin-top:.2rem">Your ${minutes}-minute brief</h2>
          <p class="small muted" style="margin-top:.3rem">${count} stories picked for you, with the context you need before class.</p>
        </div>
        <div class="hstack">
          <span class="badge badge--topic">${progress.read}/${progress.goal} today</span>
          <a class="btn btn--primary" href="/brief" data-link>Open brief ${raw(icons.chevron)}</a>
        </div>
      </div>
    </div>`;
}

async function renderTop(head, body) {
  const data = await get('/api/feed?mode=top&limit=3&days=2', 45);
  const items = (data.items || []).slice(0, 3);
  head.innerHTML = sectionHead('Top Stories', html`<a href="/?stream=top" data-link>More ${raw(icons.chevron)}</a>`, { sub: 'what the most outlets are covering' });
  if (!items.length) {
    body.innerHTML = emptyState({ icon: '📰', title: 'No top stories yet', text: 'The next refresh will fill this in.' });
    return;
  }
  body.innerHTML = html`<div class="top-grid">${items.map((item) => topCard(item))}</div>`;
}

function feedUrl(mode, offset, limit = 20) {
  const params = new URLSearchParams({ mode, offset: String(offset), limit: String(limit) });
  if (mode === 'longreads') params.set('days', '30');
  return `/api/feed?${params}`;
}

async function renderForYou(root, shell, head, body, mode = 'for-you', offset = 0, append = false) {
  head.innerHTML = html`
    <div class="section-head" style="margin-top:1.6rem">
      <h2>For you</h2>
      <div class="segmented" role="tablist" aria-label="Feed stream">
        ${[['for-you', 'For you'], ['readable', '📖 Readable here'], ['breaking', 'Breaking'], ['latest', 'Latest']].map(([id, label]) => html`
          <button type="button" role="tab" aria-selected="${mode === id}" class="${mode === id ? 'is-on' : ''}" data-mode="${id}">${label}</button>`)}
      </div>
    </div>`;
  head.querySelectorAll('[data-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      renderForYou(root, shell, head, body, button.dataset.mode, 0, false);
    });
  });
  if (!append) body.innerHTML = skeletonFeed(4);
  const data = await get(feedUrl(mode, offset), 20);
  const items = data.items || [];
  if (!items.length) {
    body.innerHTML = emptyState({
      icon: '📡',
      title: 'Nothing in this stream yet',
      text: 'Try another tab, or search the whole archive.',
      action: '<button class="btn btn--primary" data-open-search>Search news</button>',
    });
    body.querySelector('[data-open-search]')?.addEventListener('click', () => openPalette());
    return;
  }
  if (!append) {
    body.innerHTML = html`
      <div id="for-you-list">${mosaicHtml(items, mode)}</div>
      <div id="for-you-sentinel" style="height:1px"></div>`;
  } else {
    const list = body.querySelector('#for-you-list');
    if (list) {
      const offset = mosaicOffset(mode);
      const start = list.querySelectorAll('.mcard').length;
      list.insertAdjacentHTML('beforeend', items.map((item, index) => mosaicCard(item, {
        size: MOSAIC[(start + index + offset) % MOSAIC.length],
      })).join(''));
    }
  }
  if (data.has_more) attachSentinel(root, shell, body, mode, offset + items.length);
  else if (!append) {
    body.querySelector('#for-you-list')?.insertAdjacentHTML('afterend',
      html`<p class="tiny faint" style="text-align:center;padding:1rem 0">You're caught up. The archive keeps growing — search it any time.</p>`);
  }
}

let forYouObserver = null;
function attachSentinel(root, shell, body, mode, nextOffset) {
  const sentinel = body.querySelector('#for-you-sentinel');
  if (!sentinel) return;
  if (forYouObserver) forYouObserver.disconnect();
  forYouObserver = new IntersectionObserver((entries) => {
    if (!entries.some((entry) => entry.isIntersecting)) return;
    forYouObserver?.disconnect();
    forYouObserver = null;
    renderForYou(root, shell, shell.querySelector('[data-head]'), body, mode, nextOffset, true).catch(() => {});
  }, { rootMargin: '600px 0px' });
  forYouObserver.observe(sentinel);
}

async function renderMySports(head, body) {
  const pinnedLeagues = prefs().pinned_sports || [];
  const pinnedTeams = prefs().pinned_teams || [];
  if (!pinnedLeagues.length && !pinnedTeams.length) {
    head.innerHTML = '';
    body.innerHTML = '';
    return;
  }
  const teamIds = new Set(pinnedTeams.map((team) => String(team.id)));
  const leagueSlugs = new Set(pinnedLeagues);
  const data = await get('/api/sports', 25);
  const games = (data.events || []).filter((game) => leagueSlugs.has(game.league)
    || game.competitors.some((team) => teamIds.has(String(team.id)))).slice(0, 5);
  head.innerHTML = sectionHead(
    '★ My sports',
    html`<a href="/sports" data-link>Open scores ${raw(icons.chevron)}</a>`,
    { sub: pinnedTeams.map((team) => team.abbr || team.name).slice(0, 4).join(' · ') || `${leagueSlugs.size} leagues` },
  );
  if (!games.length) {
    body.innerHTML = html`
      <div class="card card-pad">
        <p class="small muted">No games for your pinned teams today.</p>
        <a class="btn btn--sm btn--ghost" style="margin-top:.5rem" href="/sports" data-link>Manage pins</a>
      </div>`;
    return;
  }
  body.innerHTML = html`<div class="score-strip">${games.map((game) => scoreMini(game))}</div>`;
}

async function renderSports(head, body) {
  const data = await get('/api/sports', 20);
  const events = (data.events || []).slice(0, 8);
  head.innerHTML = sectionHead(
    `🏆 Live & upcoming ${data.live_count ? html`<span class="badge badge--live">${data.live_count} live</span>` : ''}`,
    html`<a href="/sports" data-link>All scores ${raw(icons.chevron)}</a>`,
  );
  if (!events.length) {
    body.innerHTML = html`<div class="card card-pad"><p class="small muted">No games scheduled right now. <a class="link" href="/sports" data-link>Open scores</a></p></div>`;
    return;
  }
  body.innerHTML = html`<div class="score-strip">${events.map((game) => scoreMini(game))}</div>`;
  if (data.partial) {
    setTimeout(() => {
      const node = document.querySelector('.home-section[data-id="sports"]');
      if (node) fillSection(document.getElementById('view'), 'sports');
    }, 4000);
  }
}

async function renderPicks(head, body) {
  const data = await get('/api/discover', 120);
  const items = (data.editors_picks || []).slice(0, 3);
  head.innerHTML = sectionHead("Editor's picks", html`<a href="/discover" data-link>More ${raw(icons.chevron)}</a>`, { sub: 'full text readable in Pulse' });
  if (!items.length) {
    head.innerHTML = '';
    body.innerHTML = '';
    return;
  }
  body.innerHTML = html`<div class="topic-grid">${items.map((item) => mosaicCard(item, { size: 'medium' }))}</div>`;
}

async function renderTopic(head, body, slug) {
  const meta = state.topicMap.get(slug);
  if (!meta) {
    head.innerHTML = '';
    body.innerHTML = '';
    return;
  }
  const data = await get(`/api/feed?topic=${encodeURIComponent(slug)}&mode=top&limit=8&days=14`, 60);
  const items = data.items || [];
  head.innerHTML = sectionHead(
    `${meta.icon} ${meta.label}`,
    html`<a href="/topic/${slug}" data-link>See all ${raw(icons.chevron)}</a>`,
  );
  if (!items.length) {
    body.innerHTML = html`<div class="card card-pad"><p class="small muted">No fresh ${meta.label} stories yet — <a class="link" href="/topic/${slug}" data-link>browse the topic</a>.</p></div>`;
    return;
  }
  const offset = mosaicOffset(slug);
  body.innerHTML = html`<div class="topic-grid">${items.slice(0, 6).map((item, index) => mosaicCard(item, {
    size: index === 0 && offset % 2 === 0 ? 'medium' : 'medium',
  }))}</div>`;
}

async function renderLongreads(head, body) {
  const data = await get('/api/feed?mode=longreads&limit=6&days=45', 120);
  const items = data.items || [];
  head.innerHTML = sectionHead('Long reads', html`<a href="/discover" data-link>More ${raw(icons.chevron)}</a>`, { sub: 'worth the time' });
  if (!items.length) {
    body.innerHTML = html`<div class="card card-pad"><p class="small muted">Long reads appear once full text is extracted. <a class="link" href="/?stream=longreads" data-link>Try the stream</a>.</p></div>`;
    return;
  }
  body.innerHTML = html`<div class="hscroll">${items.map((item) => hCard(item))}</div>`;
}

async function renderSaved(head, body) {
  const data = await get('/api/saved', 0, true);
  const items = (data.items || []).slice(0, 8);
  head.innerHTML = sectionHead('Saved for later', html`<a href="/saved" data-link>Library ${raw(icons.chevron)}</a>`);
  if (!items.length) {
    body.innerHTML = html`
      <div class="card card-pad">
        <p class="small muted">Nothing saved yet. Tap the bookmark on any story to keep it for revision or a citation.</p>
        <a class="btn btn--sm btn--ghost" style="margin-top:.6rem" href="/saved" data-link>Open library</a>
      </div>`;
    return;
  }
  body.innerHTML = html`<div class="hscroll">${items.map((item) => hCard(item))}</div>`;
}

async function renderResearch(head, body) {
  head.innerHTML = '';
  body.innerHTML = html`
    <div class="card card-pad-lg" style="border-color:var(--line)">
      <div class="between">
        <div>
          <p class="eyebrow">For essays & projects</p>
          <h2 style="font-size:1.15rem;margin-top:.2rem">Research desk</h2>
          <p class="small muted" style="margin-top:.3rem">Turn saved stories into a bibliography in MLA, APA, Chicago or Harvard — plus a quote collector for your notes.</p>
        </div>
        <a class="btn btn--primary" href="/research" data-link>Open research ${raw(icons.chevron)}</a>
      </div>
    </div>`;
}

// ---------------------------------------------------------------- customizer
function openCustomizer(root, ctx) {
  const selected = activeSections();
  let order = [...selected];
  const all = allSections();
  const body = document.createElement('div');
  body.className = 'section-picker';
  const box = modal({
    title: 'Customize your front page',
    wide: true,
    body,
    actions: [
      { label: 'Reset', class: 'btn--ghost', onClick: () => { order = [...DEFAULT_SECTIONS]; paint(); return false; } },
      { label: 'Cancel', class: 'btn--ghost' },
      {
        label: 'Save sections',
        class: 'btn--primary',
        onClick: async () => {
          try {
            await savePrefs({ home_sections: order });
            toast('Front page updated', { type: 'good' });
            homeView(root, ctx);
          } catch (err) {
            toast(err.message, { type: 'bad' });
            return false;
          }
          return true;
        },
      },
    ],
  });
  paint();

  function paint() {
    body.innerHTML = html`
      <p class="small muted" style="margin-bottom:.7rem">Turn sections on or off and put them in the order you want. Topic rows use the topics you already follow.</p>
      ${all.map((section) => {
        const index = order.indexOf(section.id);
        const on = index >= 0;
        return html`
          <div class="section-picker__row ${on ? '' : 'is-off'}">
            <button class="switch ${on ? 'is-on' : ''}" data-toggle="${section.id}" aria-pressed="${on}" aria-label="Toggle ${section.label}"></button>
            <span class="section-picker__name">${section.label}<span class="choice__sub">${section.hint}</span></span>
            <span class="section-picker__handle">
              <button data-up="${section.id}" aria-label="Move ${section.label} up" ${!on || index === 0 ? 'disabled' : ''}>↑</button>
              <button data-down="${section.id}" aria-label="Move ${section.label} down" ${!on || index === order.length - 1 ? 'disabled' : ''}>↓</button>
            </span>
          </div>`;
      })}`;
    body.querySelectorAll('[data-toggle]').forEach((button) => {
      button.addEventListener('click', () => {
        const id = button.dataset.toggle;
        if (order.includes(id)) order = order.filter((item) => item !== id);
        else order.push(id);
        paint();
      });
    });
    body.querySelectorAll('[data-up]').forEach((button) => {
      button.addEventListener('click', () => {
        const index = order.indexOf(button.dataset.up);
        if (index > 0) { [order[index - 1], order[index]] = [order[index], order[index - 1]]; paint(); }
      });
    });
    body.querySelectorAll('[data-down]').forEach((button) => {
      button.addEventListener('click', () => {
        const index = order.indexOf(button.dataset.down);
        if (index >= 0 && index < order.length - 1) { [order[index + 1], order[index]] = [order[index], order[index + 1]]; paint(); }
      });
    });
  }
  void box;
}
