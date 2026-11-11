import { get } from '../api.js?v=1.4.0';
import { state, prefs, savePrefs } from '../store.js?v=1.4.0';
import { html, raw, icons, toast, errorState, emptyState, timeAgo, absDate, proxyImg, modal } from '../ui.js?v=1.4.0';
import { sectionHead } from '../components.js?v=1.4.0';

let refreshTimer = null;
let currentFilter = 'all';
let currentLeague = 'all';
let pinnedSports = new Set();
let pinnedTeams = new Map();
let latestEvents = [];
let scoreRetries = 0;
let leaguesCatalog = [];

const FILTERS = [
  ['all', 'All'],
  ['pinned', '★ My sports'],
  ['live', 'Live'],
  ['pre', 'Upcoming'],
  ['post', 'Final'],
];

export async function sportsView(root, ctx) {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
  leaguesCatalog = state.boot?.sports?.leagues || [];
  pinnedSports = new Set(prefs().pinned_sports || []);
  pinnedTeams = new Map((prefs().pinned_teams || []).map((team) => [team.id, team]));
  if (!pinnedSports.size && !pinnedTeams.size) {
    // Convenience: start with the user's preferred leagues pinned.
    const defaults = prefs().sports_leagues || [];
    if (defaults.length) pinnedSports = new Set(defaults.slice(0, 3));
  }

  root.innerHTML = html`
    <div class="between">
      <div>
        <h1 class="page-title">Scores</h1>
        <p class="page-sub" id="sports-meta">Live scores, pinned teams and leagues.</p>
      </div>
      <div class="hstack">
        <button class="btn btn--sm btn--ghost" id="pin-manager">${raw(icons.filter)} Pin sports</button>
        <button class="btn btn--sm btn--ghost" id="sports-refresh">${raw(icons.refresh)} Refresh</button>
      </div>
    </div>

    <div id="pinned-bar" class="pinned-bar"></div>

    <div class="chip-row" style="margin:.9rem 0 .6rem" id="league-tabs">
      <button class="chip is-on" data-league="all">All sports</button>
      ${leaguesCatalog.map((league) => html`
        <button class="chip" data-league="${league.slug}">${league.emoji} ${league.label}</button>`)}
    </div>

    <div class="segmented" role="tablist" style="margin-bottom:1rem" id="filters">
      ${FILTERS.map(([id, label]) => html`
        <button type="button" data-filter="${id}" class="${currentFilter === id ? 'is-on' : ''}" role="tab" aria-selected="${currentFilter === id}">${label}</button>`)}
    </div>

    <div id="games-body">
      <div class="game-grid" aria-hidden="true">
        ${Array.from({ length: 4 }).map(() => html`<div class="game"><div class="skeleton skeleton--line" style="width:40%"></div><div class="skeleton skeleton--line" style="height:22px"></div><div class="skeleton skeleton--line" style="height:22px"></div></div>`)}
      </div>
    </div>
    <div id="sports-news"></div>`;

  root.querySelectorAll('[data-league]').forEach((button) => {
    button.addEventListener('click', () => {
      currentLeague = button.dataset.league;
      root.querySelectorAll('[data-league]').forEach((node) => node.classList.toggle('is-on', node === button));
      renderGames(root);
    });
  });
  root.querySelectorAll('[data-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      currentFilter = button.dataset.filter;
      root.querySelectorAll('[data-filter]').forEach((node) => node.classList.toggle('is-on', node === button));
      renderGames(root);
    });
  });
  root.querySelector('#pin-manager')?.addEventListener('click', () => openPinManager(root));
  root.querySelector('#sports-refresh')?.addEventListener('click', () => loadScores(root, true));

  renderPinnedBar(root);
  await loadScores(root, true);
  loadSportsNews(root);
  loadMotorsportNews(root);
  refreshTimer = setInterval(() => {
    if (!document.getElementById('games-body') || document.hidden) return;
    loadScores(root, true, { quiet: true });
  }, 30000);
  void ctx;
}

function isPinnedTeam(id) {
  return pinnedTeams.has(String(id));
}

function renderPinnedBar(root) {
  const slot = root.querySelector('#pinned-bar');
  if (!slot) return;
  const leagueChips = [...pinnedSports].map((slug) => {
    const league = leaguesCatalog.find((item) => item.slug === slug);
    if (!league) return '';
    return html`
      <span class="pin-chip pin-chip--league" data-pin-league="${slug}">
        <button class="pin-chip__body" data-filter-league="${slug}" title="Show ${league.label}">
          <span aria-hidden="true">${league.emoji}</span>${league.label}
        </button>
        <button class="pin-chip__x" data-unpin-league="${slug}" aria-label="Unpin ${league.label}">×</button>
      </span>`;
  });
  const teamChips = [...pinnedTeams.values()].map((team) => html`
    <span class="pin-chip pin-chip--team" data-pin-team="${team.id}">
      <button class="pin-chip__body" data-filter-team="${team.id}" title="Show ${team.name}">
        ${team.logo ? html`<img src="${proxyImg(team.logo)}" alt="" loading="lazy">` : html`<span class="pin-chip__dot">${(team.abbr || team.name || '?').slice(0, 2)}</span>`}
        ${team.abbr || team.name}
      </button>
      <button class="pin-chip__x" data-unpin-team="${team.id}" aria-label="Unpin ${team.name}">×</button>
    </span>`);
  slot.innerHTML = html`
    <div class="pinned-bar__label">Pinned</div>
    <div class="pinned-bar__chips">
      ${leagueChips}
      ${teamChips}
      ${(!pinnedSports.size && !pinnedTeams.size) ? html`<span class="tiny muted">Pin a league or team to see it first — like Apple News' My Sports.</span>` : ''}
      <button class="pin-chip pin-chip--add" id="pinned-add">+ Add</button>
    </div>`;
  slot.querySelector('#pinned-add')?.addEventListener('click', () => openPinManager(root));
  slot.querySelectorAll('[data-unpin-league]').forEach((button) => {
    button.addEventListener('click', async () => {
      pinnedSports.delete(button.dataset.unpinLeague);
      await persistPins();
      renderPinnedBar(root);
      renderGames(root);
    });
  });
  slot.querySelectorAll('[data-unpin-team]').forEach((button) => {
    button.addEventListener('click', async () => {
      pinnedTeams.delete(button.dataset.unpinTeam);
      await persistPins();
      renderPinnedBar(root);
      renderGames(root);
    });
  });
  slot.querySelectorAll('[data-filter-league]').forEach((button) => {
    button.addEventListener('click', () => {
      currentLeague = button.dataset.filterLeague;
      currentFilter = 'all';
      root.querySelectorAll('[data-league]').forEach((node) => node.classList.toggle('is-on', node.dataset.league === currentLeague));
      root.querySelectorAll('[data-filter]').forEach((node) => node.classList.toggle('is-on', node.dataset.filter === 'all'));
      renderGames(root);
      document.getElementById('games-body')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
  slot.querySelectorAll('[data-filter-team]').forEach((button) => {
    button.addEventListener('click', () => {
      currentLeague = 'all';
      currentFilter = 'pinned';
      root.querySelectorAll('[data-league]').forEach((node) => node.classList.toggle('is-on', node.dataset.league === 'all'));
      root.querySelectorAll('[data-filter]').forEach((node) => node.classList.toggle('is-on', node.dataset.filter === 'pinned'));
      renderGames(root);
      document.getElementById('games-body')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

async function persistPins() {
  try {
    await savePrefs({
      pinned_sports: [...pinnedSports],
      pinned_teams: [...pinnedTeams.values()],
    });
  } catch (err) {
    toast(err.message, { type: 'bad' });
  }
}

async function loadScores(root, force = false, { quiet = false } = {}) {
  const body = root.querySelector('#games-body');
  if (!body) return;
  try {
    const query = currentLeague === 'all' ? '' : `?leagues=${encodeURIComponent(currentLeague)}${force ? '&force=1' : ''}`;
    const data = await get(`/api/sports${query}${currentLeague === 'all' && force ? '?force=1' : ''}`, 25, force);
    latestEvents = data.events || [];
    scoreRetries = data.partial ? scoreRetries + 1 : 0;
    const meta = root.querySelector('#sports-meta');
    if (meta) {
      const live = latestEvents.filter((event) => event.is_live).length;
      meta.textContent = `${live} live now · ${latestEvents.length} games · updated ${timeAgo(data.fetched_at)}`;
    }
    renderGames(root);
    if (data.partial && scoreRetries <= 3) {
      setTimeout(() => {
        if (document.getElementById('games-body') && !document.hidden) {
          loadScores(root, true, { quiet: true });
        }
      }, 4000);
    }
  } catch (err) {
    if (!quiet) errorState(body, err.message, () => loadScores(root, true));
  }
}

function filteredEvents() {
  let events = latestEvents;
  if (currentFilter === 'live') events = events.filter((event) => event.is_live);
  else if (currentFilter === 'pre') events = events.filter((event) => event.status.state === 'pre');
  else if (currentFilter === 'post') events = events.filter((event) => event.status.state === 'post');
  else if (currentFilter === 'pinned') {
    events = events.filter((event) => pinnedSports.has(event.league)
      || event.competitors.some((team) => pinnedTeams.has(String(team.id))));
  }
  if (currentLeague !== 'all') events = events.filter((event) => event.league === currentLeague);
  return events;
}

function renderGames(root) {
  const body = root.querySelector('#games-body');
  if (!body) return;
  const events = filteredEvents();
  if (!events.length) {
    body.innerHTML = emptyState({
      icon: currentFilter === 'pinned' ? '📌' : '🏟️',
      title: currentFilter === 'pinned' ? 'No pinned games right now' : 'Nothing scheduled here',
      text: currentFilter === 'pinned'
        ? 'Pin teams or leagues and their games will collect here. Scores refresh every 30 seconds.'
        : 'Try another league or check upcoming games.',
      action: currentFilter === 'pinned' ? '<button class="btn btn--primary" id="empty-pin">Pin sports</button>' : '',
    });
    body.querySelector('#empty-pin')?.addEventListener('click', () => openPinManager(root));
    return;
  }
  const groups = currentLeague === 'all'
    ? Object.entries(events.reduce((acc, event) => {
      const label = event.league || 'other';
      (acc[label] = acc[label] || []).push(event);
      return acc;
    }, {}))
    : [['', events]];
  body.innerHTML = groups.map(([league, list]) => html`
    ${currentLeague === 'all' ? html`<div class="feed__divider">${leagueLabel(league)}</div>` : ''}
    <div class="game-grid">${list.map((game) => gameCard(game))}</div>`).join('');
  body.querySelectorAll('[data-pin-team]').forEach((button) => {
    button.addEventListener('click', async () => {
      const teamId = button.dataset.pinTeam;
      const team = {
        id: String(teamId),
        name: button.dataset.teamName || 'Team',
        abbr: button.dataset.teamAbbr || '',
        logo: button.dataset.teamLogo || '',
        league: button.dataset.teamLeague || '',
      };
      if (pinnedTeams.has(teamId)) pinnedTeams.delete(teamId);
      else pinnedTeams.set(teamId, team);
      await persistPins();
      renderPinnedBar(root);
      renderGames(root);
      toast(pinnedTeams.has(teamId) ? `${team.name} pinned to My sports` : `${team.name} unpinned`);
    });
  });
}

function leagueLabel(slug) {
  const league = leaguesCatalog.find((item) => item.slug === slug);
  return league ? `${league.emoji} ${league.label}` : slug.toUpperCase();
}

function gameCard(game) {
  const phase = game.status.state;
  const teams = [...game.competitors].sort((a, b) => (a.home === b.home ? 0 : a.home ? 1 : -1));
  return html`
    <article class="game ${game.is_live ? 'is-live' : ''}">
      <div class="game__top">
        ${game.is_live ? html`<span class="badge badge--live">Live</span>` : html`<span class="badge badge--topic">${phase === 'post' ? 'Final' : 'Upcoming'}</span>`}
        <span class="game__status">${game.status.detail || ''}</span>
        <span class="game__league">${leagueLabel(game.league)}</span>
      </div>
      <div class="game__teams">
        ${teams.map((team) => {
          const pinned = isPinnedTeam(team.id);
          return html`
            <div class="game__team ${team.winner ? 'is-winner' : phase === 'post' ? 'is-loser' : ''}">
              ${team.logo ? html`<img src="${proxyImg(team.logo)}" alt="" loading="lazy" decoding="async">` : html`<span class="game__logo-fallback">${(team.abbr || team.name || '?').slice(0, 3)}</span>`}
              <span class="game__name">${team.name}</span>
              ${team.record ? html`<span class="game__record">${team.record}</span>` : ''}
              <span class="game__score">${phase === 'pre' ? '' : (team.score ?? 0)}</span>
              <button class="pin-btn ${pinned ? 'is-on' : ''}" data-pin-team="${team.id}"
                data-team-name="${team.name}" data-team-abbr="${team.abbr || team.short || ''}"
                data-team-logo="${team.logo || ''}" data-team-league="${game.league}"
                aria-pressed="${pinned}" aria-label="${pinned ? 'Unpin' : 'Pin'} ${team.name}" title="${pinned ? 'Unpin' : 'Pin'} ${team.name}">
                ${pinned ? '★' : '☆'}
              </button>
            </div>`;
        })}
      </div>
      <div class="game__meta">
        ${game.date && phase === 'pre' ? html`<span>${absDate(game.date)}</span>` : ''}
        ${game.venue ? html`<span>· ${game.venue}</span>` : ''}
        ${game.broadcasts?.length ? html`<span>· ${game.broadcasts.join(', ')}</span>` : ''}
      </div>
    </article>`;
}

function openPinManager(root) {
  const body = document.createElement('div');
  const teams = new Map();
  latestEvents.forEach((event) => {
    event.competitors.forEach((team) => {
      if (team.id) teams.set(String(team.id), { id: String(team.id), name: team.name, abbr: team.abbr || team.short, logo: team.logo || '', league: event.league });
    });
  });
  let leagueSelection = new Set(pinnedSports);
  let teamSelection = new Set(pinnedTeams.keys());
  let query = '';

  const box = modal({
    title: 'Pin sports',
    wide: true,
    body,
    actions: [
      { label: 'Cancel', class: 'btn--ghost' },
      {
        label: 'Save pins',
        class: 'btn--primary',
        onClick: async () => {
          pinnedSports = new Set(leagueSelection);
          pinnedTeams = new Map([...teamSelection].map((id) => [id, teams.get(id)]).filter(([, team]) => team));
          await persistPins();
          renderPinnedBar(root);
          renderGames(root);
          toast('My sports updated', { type: 'good' });
          return true;
        },
      },
    ],
  });
  paint();

  function paint() {
    const filtered = [...teams.values()].filter((team) => {
      if (!query) return true;
      const haystack = `${team.name} ${team.abbr}`.toLowerCase();
      return haystack.includes(query.toLowerCase());
    });
    body.innerHTML = html`
      <p class="small muted" style="margin-bottom:.5rem">Leagues and teams you pin appear first on Scores and can show up on your front page.</p>
      <p class="tiny muted" style="margin:.7rem 0 .35rem">Leagues</p>
      <div class="choice-grid">
        ${leaguesCatalog.map((league) => html`
          <button class="choice ${leagueSelection.has(league.slug) ? 'is-on' : ''}" data-league-toggle="${league.slug}">
            <span class="choice__icon">${league.emoji}</span><span>${league.label}</span>
          </button>`)}
      </div>
      <p class="tiny muted" style="margin:1rem 0 .35rem">Teams playing today</p>
      <input type="search" id="pin-search" placeholder="Search teams…" value="${query}" aria-label="Search teams">
      <div class="stack-sm" style="margin-top:.5rem;max-height:34vh;overflow:auto">
        ${filtered.length ? filtered.map((team) => html`
          <button class="pin-row ${teamSelection.has(team.id) ? 'is-on' : ''}" data-team-toggle="${team.id}">
            ${team.logo ? html`<img src="${proxyImg(team.logo)}" alt="" loading="lazy">` : html`<span class="pin-row__dot">${(team.abbr || '?').slice(0, 2)}</span>`}
            <span class="pin-row__name">${team.name}<span class="pin-row__league">${leagueLabel(team.league)}</span></span>
            <span class="pin-row__state">${teamSelection.has(team.id) ? '★ Pinned' : '☆ Pin'}</span>
          </button>`) : html`<p class="small muted" style="padding:.7rem">No teams match “${query}”.</p>`}
      </div>`;
    body.querySelectorAll('[data-league-toggle]').forEach((button) => {
      button.addEventListener('click', () => {
        const slug = button.dataset.leagueToggle;
        if (leagueSelection.has(slug)) leagueSelection.delete(slug); else leagueSelection.add(slug);
        paint();
      });
    });
    body.querySelectorAll('[data-team-toggle]').forEach((button) => {
      button.addEventListener('click', () => {
        const id = button.dataset.teamToggle;
        if (teamSelection.has(id)) teamSelection.delete(id); else teamSelection.add(id);
        paint();
      });
    });
    const search = body.querySelector('#pin-search');
    search.addEventListener('input', () => {
      query = search.value;
      paint();
      const next = body.querySelector('#pin-search');
      if (next) { next.focus(); next.setSelectionRange(query.length, query.length); }
    });
  }
  void box;
  void sectionHead;
}

async function loadMotorsportNews(root) {
  const slot = root.querySelector('#sports-news');
  if (!slot) return;
  try {
    const data = await get('/api/feed?topic=motorsport&mode=latest&limit=6&days=14', 90);
    if (!data.items?.length) return;
    const block = document.createElement('div');
    block.className = 'section';
    block.innerHTML = html`
      <div class="section-head"><h2>🏎️ Formula 1 & motorsport</h2>
        <a href="/topic/motorsport" data-link>All motorsport ${raw(icons.chevron)}</a></div>
      <div class="topic-grid">
        ${data.items.slice(0, 3).map((item) => html`
          <a class="card" href="/article/${item.id}" data-link style="display:block;overflow:hidden">
            ${item.image ? html`<img src="${item.image}" alt="" loading="lazy" style="width:100%;height:140px;object-fit:cover">` : ''}
            <div style="padding:.7rem .8rem">
              <div class="tiny muted">${item.source.name} · ${item.published_relative}</div>
              <div style="font-weight:700;font-size:.9rem;line-height:1.3;margin-top:.25rem">${item.title}</div>
            </div>
          </a>`)}
      </div>`;
    slot.prepend(block);
  } catch { /* optional */ }
}

async function loadSportsNews(root) {
  const slot = root.querySelector('#sports-news');
  try {
    const data = await get('/api/feed?topic=sports&mode=latest&limit=8&days=3', 60);
    if (!data.items?.length) { slot.innerHTML = ''; return; }
    slot.innerHTML = html`
      <div class="section">
        ${sectionHead('Sports stories', html`<a href="/topic/sports" data-link>All sports ${raw(icons.chevron)}</a>`)}
        <div class="row-list card card-pad">
          ${data.items.map((item) => html`
            <div class="row">
              ${item.image ? html`<img class="row__img" src="${item.image}" alt="" loading="lazy" decoding="async">` : ''}
              <div class="row__body">
                <a class="row__title" href="/article/${item.id}" data-link>${item.title}</a>
                <div class="row__meta"><span>${item.source.name}</span><span>·</span><span>${item.published_relative}</span></div>
              </div>
            </div>`)}
        </div>
      </div>`;
  } catch { slot.innerHTML = ''; }
}
