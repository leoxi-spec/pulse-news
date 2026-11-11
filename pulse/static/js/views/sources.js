import { get, post } from '../api.js?v=1.4.0';
import { state, sourceOf, topicLabel, record } from '../store.js?v=1.4.0';
import { html, raw, icons, toast, errorState, emptyState, compactNumber, timeAgo } from '../ui.js?v=1.4.0';
import { sectionHead, storyCard, sourceDot, skeletonFeed } from '../components.js?v=1.4.0';

const LEAN_LABEL = {
  left: 'Left', 'center-left': 'Center-left', center: 'Center',
  'center-right': 'Center-right', right: 'Right', state: 'State-funded',
};

export async function sourcesView(root, ctx) {
  const boot = state.boot || {};
  const sources = boot.sources || [];
  root.innerHTML = html`
    <h1 class="page-title">Sources</h1>
    <p class="page-sub">${sources.length} publications from ${boot.catalog?.countries || '—'} countries. Follow the ones you trust, mute the rest.</p>
    <div id="health-banner" class="section"></div>
    <div class="hstack" style="margin:1rem 0">
      <input type="search" id="source-filter" placeholder="Filter sources by name or domain…" aria-label="Filter sources" style="max-width:340px">
      <select id="topic-filter" aria-label="Filter by topic" style="max-width:200px">
        <option value="">All topics</option>
        ${(boot.topics || []).map((topic) => html`<option value="${topic.slug}">${topic.label}</option>`)}
      </select>
      <select id="country-filter" aria-label="Filter by country" style="max-width:180px">
        <option value="">All countries</option>
        ${(boot.catalog?.countries_list || []).map((c) => html`<option value="${c.code}">${c.code} (${c.count})</option>`)}
      </select>
      <span class="tiny muted" id="source-count"></span>
    </div>
    <div id="source-list" class="tile-grid"></div>`;

  const followSet = new Set((state.profile?.survey?.sources) || []);
  const list = root.querySelector('#source-list');
  const countLabel = root.querySelector('#source-count');

  const draw = () => {
    const query = root.querySelector('#source-filter').value.trim().toLowerCase();
    const topic = root.querySelector('#topic-filter').value;
    const country = root.querySelector('#country-filter').value;
    const filtered = sources.filter((source) => {
      if (topic && !source.topics.includes(topic)) return false;
      if (country && source.country !== country) return false;
      if (query && !source.name.toLowerCase().includes(query) && !source.domain.toLowerCase().includes(query)) return false;
      return true;
    });
    countLabel.textContent = `${filtered.length} sources`;
    list.innerHTML = filtered.map((source) => html`
      <div class="card" style="padding:.85rem;display:flex;flex-direction:column;gap:.5rem">
        <a href="/source/${source.id}" data-link class="hstack" style="gap:.55rem;align-items:flex-start">
          ${sourceDot(source)}
          <span style="min-width:0">
            <span class="tile__label" style="font-size:.9rem;display:block">${source.name}</span>
            <span class="tiny muted">${source.domain} · ${source.country}</span>
          </span>
        </a>
        <div class="hstack" style="gap:.3rem">
          ${source.teen_friendly ? html`<span class="reason">teen-friendly</span>` : ''}
          ${source.paywall ? html`<span class="reason">subscription</span>` : ''}
          <span class="reason">${LEAN_LABEL[source.lean] || source.lean}</span>
        </div>
        <div class="hstack" style="gap:.3rem">
          ${source.topics.slice(0, 3).map((topicSlug) => html`<span class="tiny faint">${topicLabel(topicSlug)}</span>`)}
        </div>
        <button class="btn btn--sm ${followSet.has(source.id) ? '' : 'btn--ghost'}" data-follow="${source.id}">
          ${followSet.has(source.id) ? '✓ Following' : '+ Follow'}
        </button>
      </div>`).join('');
    list.querySelectorAll('[data-follow]').forEach((button) => {
      button.addEventListener('click', async () => {
        const id = button.dataset.follow;
        const on = !followSet.has(id);
        try {
          await post('/api/profile/follows', { kind: 'source', value: id, on });
          if (on) followSet.add(id); else followSet.delete(id);
          button.textContent = on ? '✓ Following' : '+ Follow';
          button.classList.toggle('btn--ghost', !on);
          toast(on ? 'Following — their stories rank higher for you' : 'Unfollowed');
        } catch (err) { toast(err.message, { type: 'bad' }); }
      });
    });
  };

  root.querySelector('#source-filter').addEventListener('input', draw);
  root.querySelector('#topic-filter').addEventListener('change', draw);
  root.querySelector('#country-filter').addEventListener('change', draw);
  draw();
  loadHealth(root);
  void ctx;
}

async function loadHealth(root) {
  const slot = root.querySelector('#health-banner');
  try {
    const data = await get('/api/source-health', 60);
    const summary = data.summary || {};
    const failing = (data.feeds || []).filter((feed) => feed.consecutive_failures > 0).slice(0, 8);
    slot.innerHTML = html`
      <div class="card card-pad">
        <div class="between">
          <div>
            <h2 style="font-size:.95rem">Feed health</h2>
            <p class="tiny muted" style="margin-top:.2rem">${summary.healthy}/${summary.total} feeds responding. ${summary.blocked} blocked or unreadable (publisher or network) — those sources stay in the catalogue and keep retrying.</p>
          </div>
          <button class="btn btn--sm btn--ghost" id="refresh-feeds">${raw(icons.refresh)} Refresh all feeds</button>
        </div>
        ${failing.length ? html`
          <details style="margin-top:.8rem">
            <summary class="tiny muted" style="cursor:pointer">Show feeds that are currently failing (${failing.length})</summary>
            <div class="row-list" style="margin-top:.203rem">
              ${failing.map((feed) => html`
                <div class="row">
                  <div class="row__body">
                    <div class="row__title" style="font-size:.82rem">${feed.source_name} <span class="faint">· ${feed.topic}</span></div>
                    <div class="row__meta"><span class="mono tiny">${(feed.last_error || '').slice(0, 90)}</span></div>
                  </div>
                  <span class="tiny faint">${feed.consecutive_failures}×</span>
                </div>`)}
            </div>
          </details>` : ''}
      </div>`;
    slot.querySelector('#refresh-feeds')?.addEventListener('click', async (event) => {
      event.target.disabled = true;
      try {
        await post('/api/ingest/refresh', {});
        toast('Refresh started — feeds update in the background', { type: 'good' });
      } catch (err) { toast(err.message, { type: 'bad' }); }
      setTimeout(() => { event.target.disabled = false; }, 4000);
    });
  } catch {
    slot.innerHTML = '';
  }
}

export async function sourceView(root, ctx) {
  const id = ctx.params.id;
  root.innerHTML = skeletonFeed(3);
  try {
    const data = await get(`/api/sources/${encodeURIComponent(id)}`, 30);
    const source = data.source;
    const followed = (state.profile?.survey?.sources || []).includes(source.id);
    root.innerHTML = html`
      <a class="article__back" href="/sources" data-link>${raw(icons.chevron)} All sources</a>
      <div class="hstack" style="gap:.8rem;align-items:flex-start">
        ${sourceDot(source)}
        <div>
          <h1 class="page-title" style="font-size:1.7rem">${source.name}</h1>
          <p class="page-sub">${source.about || ''}</p>
        </div>
      </div>
      <div class="hstack" style="margin:1rem 0;gap:.4rem">
        <a class="chip" href="https://${source.domain}" target="_blank" rel="noopener noreferrer">${source.domain} ${raw(icons.external)}</a>
        <span class="chip">${LEAN_LABEL[source.lean] || source.lean}</span>
        <span class="chip">${source.country}</span>
        ${source.paywall ? html`<span class="chip">subscription</span>` : html`<span class="chip">free to read</span>`}
        ${source.topics.map((topic) => html`<a class="chip" href="/topic/${topic}" data-link>${topicLabel(topic)}</a>`)}
        <button class="btn btn--sm ${followed ? '' : 'btn--ghost'}" id="follow-source">${followed ? '✓ Following' : '+ Follow'}</button>
      </div>
      <div class="stat-grid">
        <div class="stat"><div class="stat__value">${compactNumber(data.archive_count)}</div><div class="stat__label">stories in archive</div></div>
        <div class="stat"><div class="stat__value">${data.feeds.length}</div><div class="stat__label">feeds</div></div>
        <div class="stat"><div class="stat__value">${data.articles.length}</div><div class="stat__label">recent</div></div>
      </div>
      <div class="section">
        ${sectionHead('Recent stories')}
        <div class="feed">${data.articles.map((item) => storyCard(item)) || emptyState({ icon: '📭', title: 'No recent stories', text: 'This source has nothing in the last 30 days on this network.' })}</div>
      </div>
      <details class="section">
        <summary class="small muted" style="cursor:pointer">Feed diagnostics</summary>
        <div class="row-list">
          ${data.feeds.map((feed) => html`
            <div class="row">
              <div class="row__body">
                <div class="row__title" style="font-size:.8rem;font-family:ui-monospace,monospace">${feed.url}</div>
                <div class="row__meta">
                  <span>${feed.topic}</span>
                  <span>·</span>
                  <span>${feed.last_success_at ? `last ok ${timeAgo(feed.last_success_at)}` : 'never fetched'}</span>
                  ${feed.last_error ? html`<span>·</span><span style="color:var(--bad)">${feed.last_error.slice(0, 70)}</span>` : ''}
                </div>
              </div>
            </div>`)}
        </div>
      </details>`;

    root.querySelector('#follow-source')?.addEventListener('click', async (event) => {
      const on = !followed;
      try {
        await post('/api/profile/follows', { kind: 'source', value: source.id, on });
        event.target.textContent = on ? '✓ Following' : '+ Follow';
        event.target.classList.toggle('btn--ghost', !on);
        toast(on ? 'Following' : 'Unfollowed');
      } catch (err) { toast(err.message, { type: 'bad' }); }
    });
    record('view', { silent: true });
    void sourceOf;
  } catch (err) {
    errorState(root, err.message, () => sourceView(root, ctx));
  }
}
