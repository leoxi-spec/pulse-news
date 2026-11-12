import { get, post } from '../api.js';
import {
  state, prefs, savePrefs, dailyProgress, streak, levels, followedTopics, topicLabel, topicIcon, ageBand,
} from '../store.js';
import { html, raw, icons, toast, compactNumber, modal } from '../ui.js';
import { topCard, rowsHtml, scoreMini, sectionHead, emptyState, skeletonFeed } from '../components.js';
import { open as openPalette, mountHomeSearch } from '../palette.js';
import { dailySection, bindDaily, loadDaily } from '../daily.js';

const DEFAULT_SECTIONS = [
  'brief', 'top', 'shorts', 'for-you', 'daily', 'picks', 'my-sports',
  'topic:tech', 'topic:world', 'topic:motorsport', 'longreads',
];

const BASE_SECTIONS = [
  { id: 'brief', label: 'Your brief', hint: 'Five stories, two minutes' },
  { id: 'shorts', label: 'Pulse Shorts', hint: 'Full-screen swipeable news' },
  { id: 'daily', label: 'Today', hint: 'Word, poll, quiz, debate and challenge' },
  { id: 'top', label: 'Top Stories', hint: 'What the most outlets are covering' },
  { id: 'for-you', label: 'For you', hint: 'The main personalised feed' },
  { id: 'picks', label: "Editor's picks", hint: 'Full-text stories worth the time' },
  { id: 'sports', label: 'Live scores', hint: 'A scoreboard strip' },
  { id: 'my-sports', label: 'My sports', hint: 'Your pinned teams and leagues' },
  { id: 'longreads', label: 'Long reads', hint: 'Fewer, deeper pieces' },
  { id: 'saved', label: 'Saved for later', hint: 'A shortcut to your library' },
  { id: 'research', label: 'Research desk', hint: 'Citations and bibliography' },
];

function allSections() {
  const topics = (state.boot?.topics || []).map((topic) => ({
    id: `topic:${topic.slug}`,
    label: topic.label,
    hint: 'A topic row',
  }));
  return [...BASE_SECTIONS, ...topics];
}

const sectionMeta = (id) => allSections().find((section) => section.id === id) || { id, label: id, hint: '' };

function activeSections() {
  const saved = Array.isArray(prefs().home_sections) ? prefs().home_sections : [];
  const valid = saved.filter((id) => allSections().some((section) => section.id === id));
  const age = Number(state.profile?.survey?.age || 13);
  const younger = age <= 8;
  const olderKid = age >= 9 && age <= 11;
  if (valid.length) {
    // one-time migration: make sure people who customised before motorsport
    // existed still get a Formula 1 row on the front page.
    if (!prefs().sections_v2) {
      const next = [...valid];
      if (!next.includes('daily')) next.splice(next.indexOf('brief') + 1 || 0, 0, 'daily');
      if (!next.includes('topic:motorsport')) {
        const world = next.indexOf('topic:world');
        next.splice(world >= 0 ? world + 1 : next.length, 0, 'topic:motorsport');
      }
      savePrefs({ home_sections: next, sections_v2: true });
      return next;
    }
    if (!prefs().sections_v3) {
      const next = [...valid];
      if (!next.includes('shorts')) {
        const brief = next.indexOf('brief');
        next.splice(brief >= 0 ? brief + 1 : 0, 0, 'shorts');
      }
      savePrefs({ home_sections: next, sections_v3: true });
      return next;
    }
    if (!prefs().sections_v2) savePrefs({ sections_v2: true });
    return valid;
  }
  if (younger) {
    return ['brief', 'top', 'shorts', 'for-you', 'daily', 'topic:science', 'topic:culture', 'topic:sports', 'topic:motorsport'];
  }
  if (olderKid) {
    return ['brief', 'top', 'shorts', 'for-you', 'daily', 'topic:science', 'topic:world', 'topic:sports', 'topic:culture', 'longreads'];
  }
  const withInterests = [...DEFAULT_SECTIONS];
  for (const slug of followedTopics()) {
    const id = `topic:${slug}`;
    if (!withInterests.includes(id)) withInterests.push(id);
    if (withInterests.length > DEFAULT_SECTIONS.length + 3) break;
  }
  return withInterests;
}

function localGreeting() {
  const hour = new Date().getHours();
  const part = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening';
  const name = (state.profile?.name || '').trim();
  const who = name && name !== 'Student' ? `, ${name.split(' ')[0]}` : '';
  return `Good ${part}${who}`;
}

function greetingLine() {
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

function feedUrl(mode, offset, limit = 20) {
  const params = new URLSearchParams({ mode, offset: String(offset), limit: String(limit) });
  if (mode === 'longreads') params.set('days', '45');
  return `/api/feed?${params}`;
}

async function loadSection(id, timeoutMs = 3000) {
  const task = (async () => {
    if (id === 'brief') return get(`/api/brief?size=${briefSize()}`, 60, true);
    if (id === 'shorts') return get('/api/feed?mode=top&limit=6&days=2', 45);
    if (id === 'daily') return loadDaily();
    if (id === 'top') return get('/api/feed?mode=top&limit=3&days=2', 45);
    if (id === 'picks') return get('/api/discover', 120);
    if (id === 'for-you') return get(feedUrl('for-you', 0), 20);
    if (id === 'sports' || id === 'my-sports') return get('/api/sports', 25);
    if (id === 'longreads') return get('/api/feed?mode=longreads&limit=8&days=45', 120);
    if (id === 'saved') return get('/api/saved', 0, true);
    if (id === 'research') return {};
    if (id.startsWith('topic:')) return get(`/api/feed?topic=${encodeURIComponent(id.slice(6))}&mode=top&limit=8&days=14`, 60);
    return {};
  })();
  if (!timeoutMs) return task;
  return Promise.race([task, new Promise((resolve) => setTimeout(() => resolve(null), timeoutMs))]);
}

export async function homeView(root, ctx) {
  const sections = activeSections();
  const viewerAge = Number(state.profile?.survey?.age || 13);
  const kidHidden = viewerAge <= 11 ? new Set(['world', 'politics', 'business']) : null;
  const progress = dailyProgress();
  const streakInfo = streak();
  const levelInfo = levels();

  root.innerHTML = html`
    <div class="today-bar">
      <div class="today-bar__main">
        <p class="today-bar__date">${new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric' }).format(new Date())}</p>
        <h1 class="today-bar__greeting">${greetingLine()}</h1>
        <p class="today-bar__meta">${todayLine()}</p>
      </div>
      <div class="today-bar__actions">
        ${streakInfo.count > 0 && prefs().show_reading_streak !== false ? html`<span class="pill-progress streak-pill" title="Daily streak">${streakInfo.count} day${streakInfo.count === 1 ? '' : 's'}</span>` : ''}
        <a class="pill-progress" href="/profile" data-link title="Level ${levelInfo.level} · ${levelInfo.xp} XP">
          <span class="progress" role="progressbar" aria-valuenow="${levelInfo.progress.percent}" aria-valuemin="0" aria-valuemax="100"><span style="width:${levelInfo.progress.percent}%"></span></span>
          Lv ${levelInfo.level} · ${levelInfo.xp} XP
        </a>
      </div>
    </div>

    <button class="home-search" id="home-search" type="button">
      ${raw(icons.search)}
      <span>Search 330+ sources, topics and your archive…</span>
      <kbd class="kbd">⌘K</kbd>
    </button>

    <div class="between" style="margin:.2rem 0 .2rem">
      <div class="chip-row" id="quick-links">
        <a class="chip chip--shorts" href="/reels" data-link>${raw(icons.play)} Shorts</a>
        ${followedTopics().filter((slug) => !kidHidden?.has(slug)).slice(0, 5).map((slug) => html`
          <a class="chip" href="/topic/${slug}" data-link>${topicLabel(slug)}</a>`)}
        ${followedTopics().includes('motorsport') ? '' : html`
          <a class="chip" href="/topic/motorsport" data-link>F1 &amp; motorsport</a>`}
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
      ${skeletonFeed(5)}
    </div>

    <div class="section" style="text-align:center">
      <button class="btn btn--ghost" id="add-section">${raw(icons.filter)} Add or reorder sections</button>
    </div>`;

  mountHomeSearch(root.querySelector('#home-search'));
  root.querySelector('#home-search').addEventListener('click', () => openPalette());
  root.querySelector('#customize-sections').addEventListener('click', () => openCustomizer(root, ctx));
  root.querySelector('#add-section').addEventListener('click', () => openCustomizer(root, ctx));
  bindRefresh(root, sections);

  // Load everything first, then paint once. This stops the page from shifting
  // under your finger while you scroll through sections.
  const entries = await Promise.all(sections.map(async (id) => {
    const slow = id === 'sports' || id === 'my-sports';
    return [id, await loadSection(id, slow ? 600 : 3000).catch(() => null)];
  }));
  const data = new Map(entries);
  const container = root.querySelector('#home-sections');
  if (!container) return;
  container.innerHTML = sections.map((id) => sectionMarkup(id, data.get(id))).filter(Boolean).join('');
  bindSectionActions(root, sections, data);
  bindDaily(root, data.get('daily'));

  // Sports is the slow one: a placeholder reserves its space and fills later,
  // which only moves content below it, never above.
  for (const id of ['sports', 'my-sports']) {
    if (!sections.includes(id)) continue;
    if (data.get(id)) continue;
    fillSportsSection(root, id);
  }
}

// ------------------------------------------------------------------ sections
function sectionMarkup(id, data) {
  const meta = sectionMeta(id);
  if (id === 'brief') return briefSection(data);
  if (id === 'shorts') return shortsSection(data);
  if (id === 'daily') return dailySection(data);
  if (id === 'top') return topSection(data);
  if (id === 'picks') return picksSection(data);
  if (id === 'for-you') return forYouSection(data, 'for-you');
  if (id === 'sports') return sportsSection(data);
  if (id === 'my-sports') return mySportsSection(data);
  if (id === 'longreads') return longreadsSection(data);
  if (id === 'saved') return savedSection(data);
  if (id === 'research') return researchSection();
  if (id.startsWith('topic:')) return topicSection(id.slice(6), data);
  return html`<section class="home-section" data-id="${id}"><div data-head></div><div data-body></div></section>`;
}

function sectionWrap(id, head, body) {
  return html`<section class="home-section" data-id="${id}"><div data-head>${raw(head || '')}</div><div data-body>${raw(body || '')}</div></section>`;
}

function briefSection(data) {
  if (!data) return sectionWrap('brief', '', skeletonFeed(1));
  const minutes = data.minutes || 2;
  const count = (data.stories || []).length;
  const progress = dailyProgress();
  return sectionWrap('brief', '', html`
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
    </div>`);
}

function topSection(data) {
  const items = (data?.items || []).slice(0, 3);
  const head = sectionHead('Top Stories', html`<a href="/?stream=top" data-link>More ${raw(icons.chevron)}</a>`, { sub: 'what the most outlets are covering' });
  if (!items.length) return sectionWrap('top', head, emptyState({ icon: '📰', title: 'No top stories yet', text: 'The next refresh will fill this in.' }));
  return sectionWrap('top', head, html`<div class="top-grid">${items.map((item) => topCard(item))}</div>`);
}

function picksSection(data) {
  const items = (data?.editors_picks || []).slice(0, 4);
  if (!items.length) return sectionWrap('picks', '', '');
  return sectionWrap('picks',
    sectionHead("Editor's picks", html`<a href="/discover" data-link>More ${raw(icons.chevron)}</a>`, { sub: 'full text readable in Pulse' }),
    rowsHtml(items, { seed: 'picks' }));
}

function briefSize() {
  const age = Number(state.profile?.survey?.age || 13);
  return age <= 8 ? 3 : age <= 11 ? 4 : 5;
}

function applyMood(list, mood) {
  const copy = [...list];
  if (mood === 'Hype') return copy.sort((a, b) => Number(b.breaking) - Number(a.breaking));
  if (mood === 'Deep') return copy.sort((a, b) => (b.reading_minutes || 0) - (a.reading_minutes || 0));
  if (mood === 'Chill') return copy.sort((a, b) => Number(a.breaking) - Number(b.breaking));
  if (mood === 'Light') {
    const light = new Set(['culture', 'entertainment', 'music', 'sports', 'motorsport']);
    return copy.sort((a, b) => Number(light.has(b.topic)) - Number(light.has(a.topic)));
  }
  if (mood === 'Just facts') {
    const facts = new Set(['world', 'politics', 'business', 'science', 'tech', 'health']);
    return copy.sort((a, b) => Number(facts.has(b.topic)) - Number(facts.has(a.topic)));
  }
  return copy;
}

function forYouSection(data, mode, items, hasMore, offset) {
  const list = items || applyMood(data?.items || [], items ? null : prefs().mood);
  const more = hasMore === undefined ? Boolean(data?.has_more) : hasMore;
  const startOffset = offset === undefined ? list.length : offset;
  const head = html`
    <div class="section-head" style="margin-top:1.6rem">
      <h2>For you</h2>
      <div class="segmented" role="tablist" aria-label="Feed stream">
        ${[['for-you', 'For you'], ['readable', 'Readable'], ['breaking', 'Breaking'], ['latest', 'Latest']].map(([id, label]) => html`
          <button type="button" role="tab" aria-selected="${mode === id}" class="${mode === id ? 'is-on' : ''}" data-mode="${id}">${label}</button>`)}
      </div>
    </div>`;
  if (!list.length) {
    return sectionWrap('for-you', head, emptyState({
      icon: '📡', title: 'Nothing in this stream yet',
      text: 'Try another tab, or search the whole archive.',
      action: '<button class="btn btn--primary" data-open-search>Search news</button>',
    }));
  }
  const body = html`
    <div id="for-you-list">${rowsHtml(list, { lead: true, seed: mode })}</div>
    <div class="feed-more">
      ${more ? html`<button class="btn btn--ghost" data-load-more="${startOffset}">Load more stories</button>` : html`<p class="tiny faint">You're caught up. The archive keeps growing — search it any time.</p>`}
    </div>`;
  return sectionWrap('for-you', head, body);
}

function topicSection(slug, data) {
  const meta = state.topicMap.get(slug);
  if (!meta) return '';
  const items = (data?.items || []).slice(0, 8);
  const head = sectionHead(`${meta.label}`, html`<a href="/topic/${slug}" data-link>See all ${raw(icons.chevron)}</a>`);
  if (!items.length) return sectionWrap(`topic:${slug}`, head, html`<div class="card card-pad"><p class="small muted">No fresh ${meta.label} stories yet — <a class="link" href="/topic/${slug}" data-link>browse the topic</a>.</p></div>`);
  return sectionWrap(`topic:${slug}`, head, rowsHtml(items, { lead: false, seed: slug }));
}

function longreadsSection(data) {
  const items = (data?.items || []).slice(0, 8);
  const head = sectionHead('Long reads', html`<a href="/?stream=longreads" data-link>More ${raw(icons.chevron)}</a>`, { sub: 'worth the time' });
  if (!items.length) return sectionWrap('longreads', head, html`<div class="card card-pad"><p class="small muted">Long reads appear once full text is extracted.</p></div>`);
  return sectionWrap('longreads', head, rowsHtml(items, { seed: 'longreads' }));
}

function savedSection(data) {
  const items = (data?.items || []).slice(0, 6);
  const head = sectionHead('Saved for later', html`<a href="/saved" data-link>Library ${raw(icons.chevron)}</a>`);
  if (!items.length) return sectionWrap('saved', head, html`<div class="card card-pad"><p class="small muted">Nothing saved yet. Tap the bookmark on any story to keep it for revision or a citation.</p></div>`);
  return sectionWrap('saved', head, rowsHtml(items, { lead: false, seed: 'saved' }));
}

function shortsSection(data) {
  const items = (data?.items || []).slice(0, 4);
  if (!items.length) return '';
  const lead = items[0];
  const head = sectionHead('Pulse Shorts', html`<a href="/reels" data-link>Open Shorts ${raw(icons.chevron)}</a>`, { sub: 'full-screen stories · watch time tunes For you' });
  return sectionWrap('shorts', head, html`
    <div class="shorts-home">
      <a class="shorts-home__lead" href="/reels?start=${lead.id}" data-link>
        <span class="shorts-home__fallback"><i>${topicIcon(lead.topic)}</i><b>${lead.topic_label || 'News'}</b></span>
        ${lead.image ? html`<img src="${lead.image}" alt="" loading="lazy">` : ''}
        <span class="shorts-home__shade"></span>
        <span class="shorts-home__play" aria-hidden="true">▶</span>
        <span class="shorts-home__copy">
          <span class="eyebrow">Pulse Shorts</span>
          <strong>${lead.title}</strong>
          <i>Tap to watch · double-tap to like</i>
        </span>
      </a>
      <div class="shorts-home__side">
        ${items.slice(1, 4).map((item) => html`
          <a class="shorts-home__tile" href="/reels?start=${item.id}" data-link>
            <span class="shorts-home__tile-fallback">${topicIcon(item.topic)}</span>
            ${item.image ? html`<img src="${item.image}" alt="" loading="lazy">` : ''}
            <span class="shorts-home__tile-shade"></span>
            <b>${item.title}</b>
            <i>${item.reading_minutes} min</i>
          </a>`)}
        <a class="shorts-home__all" href="/reels" data-link>All Shorts <span>→</span></a>
      </div>
    </div>`);
}

function researchSection() {
  return sectionWrap('research', '', html`
    <div class="card card-pad-lg" style="border-color:var(--line)">
      <div class="between">
        <div>
          <p class="eyebrow">For essays & projects</p>
          <h2 style="font-size:1.15rem;margin-top:.2rem">Research desk</h2>
          <p class="small muted" style="margin-top:.3rem">Turn saved stories into a bibliography in MLA, APA, Chicago or Harvard.</p>
        </div>
        <a class="btn btn--primary" href="/research" data-link>Open research ${raw(icons.chevron)}</a>
      </div>
    </div>`);
}

function sportsSection(data) {
  const events = (data?.events || []).slice(0, 8);
  const head = sectionHead(
    `Live & upcoming ${data?.live_count ? html`<span class="badge badge--live">${data.live_count} live</span>` : ''}`,
    html`<a href="/sports" data-link>All scores ${raw(icons.chevron)}</a>`,
  );
  if (!events.length) return sectionWrap('sports', head, html`<div class="card card-pad"><p class="small muted">No games scheduled right now. <a class="link" href="/sports" data-link>Open scores</a></p></div>`);
  return sectionWrap('sports', head, html`<div class="score-strip">${events.map((game) => scoreMini(game))}</div>`);
}

function mySportsSection(data) {
  const pinnedLeagues = new Set(prefs().pinned_sports || []);
  const teamIds = new Set((prefs().pinned_teams || []).map((team) => String(team.id)));
  if (!pinnedLeagues.size && !teamIds.size) return '';
  const games = (data?.events || []).filter((game) => pinnedLeagues.has(game.league)
    || game.competitors.some((team) => teamIds.has(String(team.id)))).slice(0, 5);
  const head = sectionHead('My sports', html`<a href="/sports" data-link>Open scores ${raw(icons.chevron)}</a>`,
    { sub: (prefs().pinned_teams || []).map((team) => team.abbr || team.name).slice(0, 4).join(' · ') || `${pinnedLeagues.size} leagues` });
  if (!games.length) return sectionWrap('my-sports', head, html`<div class="card card-pad"><p class="small muted">No games for your pinned teams today.</p></div>`);
  return sectionWrap('my-sports', head, html`<div class="score-strip">${games.map((game) => scoreMini(game))}</div>`);
}

async function fillSportsSection(root, id) {
  const shell = root.querySelector(`.home-section[data-id="${id}"]`);
  if (!shell) return;
  const body = shell.querySelector('[data-body]');
  if (body) body.innerHTML = html`<div class="sports-placeholder"><div class="skeleton skeleton--line" style="width:45%"></div><div class="skeleton" style="height:112px;margin-top:.5rem"></div></div>`;
  const data = await loadSection(id, 0).catch(() => null);
  if (!data) return;
  const markup = id === 'sports' ? sportsSection(data) : mySportsSection(data);
  const wrapper = document.createElement('div');
  wrapper.innerHTML = markup;
  const replacement = wrapper.firstElementChild;
  const current = root.querySelector(`.home-section[data-id="${id}"]`);
  if (replacement && current) current.replaceWith(replacement);
}

// -------------------------------------------------------------------- actions
function bindSectionActions(root, sections, data) {
  root.querySelectorAll('[data-open-search]').forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = '1';
    button.addEventListener('click', () => openPalette());
  });
  root.querySelectorAll('[data-mode]').forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = '1';
    button.addEventListener('click', () => loadStream(root, button.dataset.mode, 0));
  });
  root.querySelectorAll('[data-load-more]').forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = '1';
    button.addEventListener('click', async () => {
      const offset = Number(button.dataset.loadMore);
      button.disabled = true;
      button.textContent = 'Loading…';
      await loadStream(root, 'for-you', offset, { append: true });
    });
  });
  void sections;
  void data;
}

async function loadStream(root, mode, offset, { append = false } = {}) {
  const shell = root.querySelector('.home-section[data-id="for-you"]');
  if (!shell) return;
  const body = shell.querySelector('[data-body]');
  if (!append) body.innerHTML = skeletonFeed(3);
  try {
    const next = await get(feedUrl(mode, offset), 20);
    if (!append) {
      const wrapper = document.createElement('div');
      wrapper.innerHTML = forYouSection(null, mode, next.items, next.has_more, offset + next.items.length);
      shell.replaceWith(wrapper.firstElementChild);
      bindSectionActions(root, [], new Map());
      return;
    }
    const list = body.querySelector('#for-you-list');
    if (list && next.items?.length) {
      const start = list.querySelectorAll('.mcard').length;
      list.insertAdjacentHTML('beforeend', rowsHtml(next.items, { seed: `more-${start}` }).join(''));
    }
    const more = body.querySelector('[data-load-more]');
    if (next.has_more) {
      if (more) more.dataset.loadMore = String(offset + (next.items?.length || 0));
      else body.querySelector('.feed-more')?.insertAdjacentHTML('afterbegin', html`<button class="btn btn--ghost" data-load-more="${offset + (next.items?.length || 0)}">Load more stories</button>`);
    } else if (more) {
      more.outerHTML = html`<p class="tiny faint">You're caught up. The archive keeps growing — search it any time.</p>`;
    }
    bindSectionActions(root, [], new Map());
  } catch (err) {
    if (!append) toast(err.message, { type: 'bad' });
    else toast('Could not load more', { type: 'bad' });
  }
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
      await homeView(root, {});
      toast('Up to date', { type: 'good' });
    } catch (err) {
      toast(err.message, { type: 'bad' });
    } finally {
      button.disabled = false;
      button.classList.remove('spin');
    }
  });
  void sections;
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
