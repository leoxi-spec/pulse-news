import { get, post } from '../api.js';
import { state, prefs } from '../store.js';
import { html, raw, icons, toast, errorState, emptyState, timeAgo, absDate, proxyImg } from '../ui.js';
import { sectionHead } from '../components.js';

let refreshTimer = null;
let currentFilter = 'all';
let currentLeague = 'all';
let followedTeams = new Set();

export async function sportsView(root, ctx) {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
  const leagues = state.boot?.sports?.leagues || [];
  followedTeams = new Set(prefs().teams || []);
  root.innerHTML = html`
    <div class="between">
      <div>
        <h1 class="page-title">Live scores</h1>
        <p class="page-sub" id="sports-meta">Scores update automatically every 30 seconds.</p>
      </div>
      <button class="btn btn--ghost btn--sm" id="sports-refresh">${raw(icons.refresh)} Refresh</button>
    </div>
    <div class="chip-row" style="margin:1rem 0" id="league-tabs">
      <button class="chip is-on" data-league="all">All sports</button>
      ${leagues.map((league) => html`<button class="chip" data-league="${league.slug}">${league.emoji} ${league.label}</button>`)}
    </div>
    <div class="segmented" role="tablist" style="margin-bottom:1rem">
      ${[['all', 'All'], ['live', 'Live'], ['pre', 'Upcoming'], ['post', 'Final']].map(([id, label]) => html`
        <button type="button" data-filter="${id}" class="${currentFilter === id ? 'is-on' : ''}" role="tab" aria-selected="${currentFilter === id}">${label}</button>`)}
      ${followedTeams.size ? html`<button type="button" data-filter="teams" class="${currentFilter === 'teams' ? 'is-on' : ''}" role="tab">★ My teams</button>` : ''}
    </div>
    <div id="games-body">${emptyState({ icon: '⏳', title: 'Loading scores', text: 'Talking to the scoreboard…' })}</div>
    <div id="sports-news"></div>`;

  root.querySelectorAll('[data-league]').forEach((button) => {
    button.addEventListener('click', () => {
      currentLeague = button.dataset.league;
      root.querySelectorAll('[data-league]').forEach((b) => b.classList.toggle('is-on', b === button));
      loadScores(root);
    });
  });
  root.querySelectorAll('[data-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      currentFilter = button.dataset.filter;
      root.querySelectorAll('[data-filter]').forEach((b) => b.classList.toggle('is-on', b === button));
      loadScores(root);
    });
  });
  root.querySelector('#sports-refresh')?.addEventListener('click', () => loadScores(root, true));
  await loadScores(root, true);
  loadSportsNews(root);
  refreshTimer = setInterval(() => {
    if (!document.getElementById('games-body') || document.hidden) return;
    loadScores(root, true, { quiet: true });
  }, 30000);
  void ctx;
}

async function loadScores(root, force = false, { quiet = false } = {}) {
  const body = root.querySelector('#games-body');
  if (!body) return;
  try {
    const query = currentLeague === 'all' ? '' : `?leagues=${encodeURIComponent(currentLeague)}${force ? '&force=1' : ''}`;
    const data = await get(`/api/sports${query}${currentLeague === 'all' && force ? '?force=1' : ''}`, 25, force);
    let events = data.events || [];
    if (currentFilter === 'live') events = events.filter((e) => e.is_live);
    else if (currentFilter === 'pre') events = events.filter((e) => e.status.state === 'pre');
    else if (currentFilter === 'post') events = events.filter((e) => e.status.state === 'post');
    else if (currentFilter === 'teams') events = events.filter((e) => e.competitors.some((c) => followedTeams.has(c.id)));
    const meta = root.querySelector('#sports-meta');
    if (meta) {
      const live = (data.events || []).filter((e) => e.is_live).length;
      meta.textContent = `${live} live now · ${(data.events || []).length} games · updated ${timeAgo(data.fetched_at)}`;
    }
    if (!events.length) {
      body.innerHTML = emptyState({
        icon: '🏟️',
        title: currentFilter === 'live' ? 'No games are live right now' : 'Nothing scheduled here',
        text: 'Try another league or check upcoming games. Scores refresh every 30 seconds.',
      });
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
      ${currentLeague === 'all' ? html`<div class="feed__divider">${league.toUpperCase()}</div>` : ''}
      ${list.map((game) => gameCard(game))}`).join('');
    body.querySelectorAll('[data-team]').forEach((button) => {
      button.addEventListener('click', async (event) => {
        event.preventDefault();
        const teamId = button.dataset.team;
        const on = !followedTeams.has(teamId);
        try {
          await post('/api/profile/follows', { kind: 'team', value: teamId, on });
          if (on) followedTeams.add(teamId); else followedTeams.delete(teamId);
          button.classList.toggle('is-on', on);
          button.textContent = on ? '★' : '☆';
          toast(on ? 'Team followed — games will surface here' : 'Team unfollowed');
        } catch (err) { toast(err.message, { type: 'bad' }); }
      });
    });
  } catch (err) {
    if (!quiet) errorState(body, err.message, () => loadScores(root, true));
  }
}

function gameCard(game) {
  const phase = game.status.state;
  const teams = [...game.competitors].sort((a, b) => (a.home === b.home ? 0 : a.home ? 1 : -1));
  return html`
    <div class="game ${game.is_live ? 'is-live' : ''}">
      <div class="game__teams">
        ${teams.map((team) => html`
          <div class="game__team ${team.winner ? 'is-winner' : phase === 'post' ? 'is-loser' : ''}">
            ${team.logo ? html`<img src="${proxyImg(team.logo)}" alt="" loading="lazy" decoding="async">` : ''}
            <a href="/search?q=${encodeURIComponent(team.name)}" data-link>${team.name}</a>
            ${team.record ? html`<span class="game__record">${team.record}</span>` : ''}
            <button class="icon-btn" style="width:26px;height:26px;margin-left:.2rem" data-team="${team.id}"
              aria-label="Follow ${team.name}" title="Follow ${team.name}">${followedTeams.has(team.id) ? '★' : '☆'}</button>
          </div>`)}
      </div>
      ${phase === 'pre' ? '' : html`<div>
        ${teams.map((team) => html`<div class="game__score" style="${team.winner ? '' : 'color:var(--muted)'}">${team.score ?? 0}</div>`)}
      </div>`}
      <div class="game__meta">
        ${game.is_live ? html`<span class="badge badge--live">Live</span>` : html`<span class="badge badge--topic">${phase === 'post' ? 'Final' : 'Upcoming'}</span>`}
        <span>${game.status.detail || ''}</span>
        ${game.venue ? html`<span>· ${game.venue}</span>` : ''}
        ${game.broadcasts?.length ? html`<span>· ${game.broadcasts.join(', ')}</span>` : ''}
      </div>
    </div>`;
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
