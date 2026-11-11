import { get } from '../api.js';
import { state, record } from '../store.js';
import { navigate } from '../router.js';
import { html, raw, icons, toast, errorState, emptyState, compactNumber, timeAgo, absDate } from '../ui.js';
import { heroCard, storyCard, rowsHtml, sectionHead, topicTile, emptyState as empty, leanBar, skeletonFeed, sourceDot } from '../components.js';

export async function discoverView(root) {
  root.classList.add('view--wide');
  root.innerHTML = html`
    <h1 class="page-title">Explore</h1>
    <p class="page-sub">Every topic, every outlet, every story you've ever seen. ${compactNumber(state.boot?.archive?.total)} articles and counting.</p>
    <div id="discover-body">${skeletonFeed(4)}</div>`;

  let data;
  try {
    data = await get('/api/discover', 60);
  } catch (err) {
    errorState(root.querySelector('#discover-body'), err.message, () => discoverView(root));
    return;
  }
  const body = root.querySelector('#discover-body');
  body.innerHTML = html`
    ${sectionHead('Topics', html`<a href="/sources" data-link>All sources ${raw(icons.chevron)}</a>`)}
    <div class="tile-grid">${data.topics.map(topicTile)}</div>

    ${data.trending?.length ? html`
      <div class="section">
        ${sectionHead('Trending across outlets', html`<a href="/?stream=top" data-link>More ${raw(icons.chevron)}</a>`)}
        <div class="card card-pad">
          <div class="row-list">
            ${data.trending.map((story, index) => html`
              <div class="row">
                <span class="row__rank">${index + 1}</span>
                ${story.lead?.image ? html`<img class="row__img" src="${story.lead.image}" alt="" loading="lazy" decoding="async">` : ''}
                <div class="row__body">
                  <a class="row__title" href="/article/${story.lead.id}" data-link>${story.title}</a>
                  <div class="row__meta">
                    <span class="badge badge--topic">${story.topic_label}</span>
                    <span>${story.source_count} outlets</span>
                    <span aria-hidden="true">·</span>
                    <span>${story.relative}</span>
                    ${story.breaking ? html`<span class="badge badge--breaking">Breaking</span>` : ''}
                  </div>
                </div>
              </div>`)}
          </div>
        </div>
      </div>` : ''}

    ${data.editors_picks?.length ? html`
      <div class="section">
        ${sectionHead('Worth your time', '<span class="tiny muted">full text available in-app</span>')}
        <div class="news-rows">${rowsHtml(data.editors_picks, { seed: 'discover-picks' })}</div>
      </div>` : ''}

    ${data.longreads?.length ? html`
      <div class="section">
        ${sectionHead('Long reads', html`<a href="/?stream=longreads" data-link>More ${raw(icons.chevron)}</a>`)}
        <div class="news-rows">${rowsHtml(data.longreads.slice(0, 4), { seed: 'discover-long' })}</div>
      </div>` : ''}

    ${data.sources?.length ? html`
      <div class="section">
        ${sectionHead('Sources publishing right now', html`<a href="/sources" data-link>Directory ${raw(icons.chevron)}</a>`)}
        <div class="tile-grid">
          ${data.sources.map((source) => html`
            <a class="tile" href="/source/${source.id}" data-link>
              ${sourceDot(source)}
              <span>
                <span class="tile__label" style="font-size:.86rem">${source.name}</span>
                <span class="tile__count">${source.recent} stories · ${source.country}</span>
              </span>
            </a>`)}
        </div>
      </div>` : ''}

    <div class="section">
      ${sectionHead('The archive', html`<a href="/archive" data-link>Browse ${raw(icons.chevron)}</a>`)}
      <div class="card card-pad-lg">
        <p class="small muted">${data.archive.note}</p>
        <div class="stat-grid" style="margin-top:.9rem">
          <div class="stat"><div class="stat__value">${compactNumber(data.archive.total)}</div><div class="stat__label">articles archived</div></div>
          <div class="stat"><div class="stat__value">${compactNumber(data.archive.sources)}</div><div class="stat__label">outlets seen</div></div>
          <div class="stat"><div class="stat__value">${data.archive.earliest ? absDate(data.archive.earliest, false) : '—'}</div><div class="stat__label">oldest story</div></div>
        </div>
      </div>
    </div>`;
  root.classList.remove('view--wide');
}

export async function topicView(root, ctx) {
  const slug = ctx.params.slug;
  const meta = state.topicMap.get(slug);
  if (!meta) {
    root.innerHTML = empty({ icon: '🧭', title: 'Unknown topic', text: 'That topic does not exist in this edition.', action: '<a class="btn btn--primary" href="/discover" data-link>Explore topics</a>' });
    return;
  }
  const mode = ['for-you', 'top', 'latest'].includes(ctx.query.mode) ? ctx.query.mode : 'for-you';
  root.innerHTML = html`
    <div class="hstack" style="gap:.6rem">
      <span style="font-size:2rem" aria-hidden="true">${meta.icon}</span>
      <div>
        <h1 class="page-title" style="font-size:1.7rem">${meta.label}</h1>
        <p class="page-sub">The latest from ${state.boot?.catalog?.sources || 0} sources, ranked for you.</p>
      </div>
    </div>
    <div class="between" style="margin:1rem 0">
      <div class="segmented" role="tablist">
        ${[['for-you', 'For you'], ['top', 'Top'], ['latest', 'Latest']].map(([id, label]) => html`
          <button type="button" class="${mode === id ? 'is-on' : ''}" data-mode="${id}" role="tab" aria-selected="${mode === id}">${label}</button>`)}
      </div>
      <a class="chip" href="/?stream=for-you" data-link>← Full feed</a>
    </div>
    <div id="topic-body">${skeletonFeed(4)}</div>`;

  root.querySelectorAll('[data-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      const url = `/topic/${slug}${button.dataset.mode === 'for-you' ? '' : `?mode=${button.dataset.mode}`}`;
      navigate(url);
    });
  });

  loadTopicFeed(root, slug, mode, 0, false);
}

let topicObserver = null;

async function loadTopicFeed(root, slug, mode, offset, append) {
  const body = root.querySelector('#topic-body');
  if (!body) return;
  if (topicObserver) { topicObserver.disconnect(); topicObserver = null; }
  if (!append) body.innerHTML = skeletonFeed(4);
  try {
    const data = await get(`/api/feed?topic=${encodeURIComponent(slug)}&mode=${mode}&offset=${offset}&limit=24&days=14`, 30);
    const items = data.items || [];
    if (!items.length) {
      body.innerHTML = empty({ icon: '📭', title: 'No stories here yet', text: 'This topic will fill up as feeds are ingested. Try Latest or search.', action: '<a class="btn btn--ghost" href="/discover" data-link>Explore</a>' });
      return;
    }
    if (!append) {
      body.innerHTML = html`<div class="news-rows" id="topic-list">${rowsHtml(items, { lead: true, seed: `${slug}-${mode}` })}</div><div id="topic-sentinel" style="height:1px"></div>`;
    } else {
      root.querySelector('#topic-list')?.insertAdjacentHTML('beforeend', rowsHtml(items, { seed: `${slug}-${offset}` }).join(''));
    }
    if (data.has_more) {
      const sentinel = root.querySelector('#topic-sentinel');
      if (sentinel) {
        topicObserver = new IntersectionObserver((entries) => {
          if (entries.some((e) => e.isIntersecting)) {
            topicObserver?.disconnect();
            loadTopicFeed(root, slug, mode, offset + items.length, true);
          }
        }, { rootMargin: '500px 0px' });
        topicObserver.observe(sentinel);
      }
    }
  } catch (err) {
    if (!append) errorState(body, err.message, () => loadTopicFeed(root, slug, mode, offset, false));
  }
}

export async function storyView(root, ctx) {
  const id = Number(ctx.params.id);
  root.innerHTML = skeletonFeed(3);
  try {
    const { story } = await get(`/api/stories/${id}`, 30);
    const articles = story.articles || [];
    const lead = articles[articles.length - 1] || articles[0];
    root.innerHTML = html`
      <a class="article__back" href="/" data-link>${raw(icons.chevron)} Back to feed</a>
      <span class="badge badge--topic">${story.topic_label}</span>
      <h1 class="page-title" style="margin:.6rem 0">${story.title}</h1>
      <p class="page-sub">${story.source_count} outlets · ${story.article_count} article${story.article_count === 1 ? '' : 's'} · last update ${story.relative}</p>
      ${Object.keys(story.leans || {}).length ? html`
        <div style="margin:1rem 0">
          <p class="tiny muted">Approximate editorial spread of the coverage</p>
          ${leanBar(story.leans)}
        </div>` : ''}
      <div class="news-rows" style="margin-top:1rem">
        ${rowsHtml(articles.slice().reverse(), { seed: `story-${id}` })}
      </div>`;
    if (lead) record('view', { storyId: id, silent: true });
    void heroCard;
  } catch (err) {
    errorState(root, err.message, () => storyView(root, ctx));
  }
}

export async function archiveView(root) {
  root.innerHTML = html`
    <h1 class="page-title">Archive</h1>
    <p class="page-sub">Pulse keeps every article it has ever ingested. Search reaches all of it.</p>
    <div id="archive-body" class="section">${skeletonFeed(2)}</div>`;
  try {
    const data = await get('/api/archive', 120);
    const months = data.months || [];
    const summary = data.summary || {};
    const body = root.querySelector('#archive-body');
    body.innerHTML = html`
      <div class="card card-pad-lg">
        <div class="stat-grid">
          <div class="stat"><div class="stat__value">${compactNumber(summary.total)}</div><div class="stat__label">articles</div></div>
          <div class="stat"><div class="stat__value">${compactNumber(summary.sources)}</div><div class="stat__label">sources</div></div>
          <div class="stat"><div class="stat__value">${summary.earliest ? absDate(summary.earliest, false) : '—'}</div><div class="stat__label">oldest</div></div>
        </div>
        <div class="hstack" style="margin-top:1rem">
          <a class="btn btn--primary" href="/search?q=&sort=newest" data-link>Search the archive</a>
          <a class="btn btn--ghost" href="/discover" data-link>Browse topics</a>
        </div>
      </div>
      ${months.length ? html`
        <div class="section">
          ${sectionHead('By month')}
          <div class="tile-grid">
            ${months.map((month) => html`
              <a class="tile" href="/search?q=&since=${month.month}-01&sort=newest" data-link>
                <span class="tile__icon">🗓️</span>
                <span><span class="tile__label">${month.month}</span><span class="tile__count">${compactNumber(month.n)} stories</span></span>
              </a>`)}
          </div>
        </div>` : ''}`;
  } catch (err) {
    errorState(root.querySelector('#archive-body'), err.message, () => archiveView(root));
  }
}
