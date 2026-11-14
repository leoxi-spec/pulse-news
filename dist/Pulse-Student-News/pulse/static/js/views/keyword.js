import { get } from '../api.js';
import { state } from '../store.js';
import { html, raw, icons, esc, compactNumber, number, absDate, errorState, emptyState } from '../ui.js';
import { sourceDot, translatedBadge } from '../components.js';

const TORONTO_TIME = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' });

function highlight(text, query) {
  const safe = esc(text || '');
  const terms = String(query || '').split(/\s+/).filter((term) => term.length > 1).slice(0, 4);
  if (!terms.length) return safe;
  try {
    const pattern = new RegExp(`(${terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
    return safe.replace(pattern, '<mark>$1</mark>');
  } catch {
    return safe;
  }
}

function itemMarkup(item, q) {
  const source = item.source || {};
  const date = item.published_relative || '';
  return html`
    <article class="keyword-hit" data-article-card="${item.id}">
      <a class="keyword-hit__media" href="/article/${item.id}" data-link aria-label="${item.title}">
        ${item.image ? html`<img src="${item.image}" alt="" loading="lazy" decoding="async">` : html`<span class="keyword-hit__monogram">${source.initials || 'N'}</span>`}
      </a>
      <div class="keyword-hit__body">
        <div class="keyword-hit__source">
          ${sourceDot(source)}
          <span>${source.name || ''}</span>
          ${translatedBadge(item)}
          ${date ? html`<span class="faint">·</span><span>${date}</span>` : ''}
        </div>
        <h2 class="keyword-hit__title"><a href="/article/${item.id}" data-link>${raw(highlight(item.title, q))}</a></h2>
        <div class="keyword-hit__meta">
          ${item.author ? html`<span>By ${esc(item.author)}</span><span class="faint">·</span>` : ''}
          <span>${item.reading_minutes || 1} min read</span>
          ${item.video ? html`<span class="video-badge video-badge--inline">${raw(icons.play)}<span>Video</span></span>` : ''}
          ${item.paywalled ? html`<span class="badge badge--muted">Subscription</span>` : ''}
        </div>
      </div>
      <a class="keyword-hit__arrow" href="/article/${item.id}" data-link aria-label="Open story">${raw(icons.chevron)}</a>
    </article>`;
}

function header(q, total, earliest) {
  return html`
    <div class="keyword-head">
      <div>
        <button class="article__back" type="button" data-keyword-back>${raw(icons.chevron)} Back</button>
        <p class="eyebrow">Keyword archive</p>
        <h1>“${q}”</h1>
        <p class="page-sub">Every article Pulse has fetched about this keyword — current reporting and the archive behind it.</p>
      </div>
      <form class="keyword-search" id="keyword-form" role="search">
        <input type="search" name="q" value="${q}" aria-label="Search another keyword" placeholder="Search another keyword">
        <button class="btn btn--primary" type="submit">${raw(icons.search)} Search</button>
      </form>
    </div>
    <div class="keyword-meta">
      <span><b>${number(total)}</b> article${total === 1 ? '' : 's'}</span>
      ${earliest ? html`<span class="faint">·</span><span>archive since ${TORONTO_TIME.format(new Date(earliest))}</span>` : ''}
      <span class="faint">·</span>
      <a href="/search?q=${encodeURIComponent(q)}" data-link>Advanced filters</a>
    </div>`;
}

function sortTabs(q, sort) {
  return html`
    <div class="chip-row keyword-tabs">
      <a class="chip ${sort === 'relevance' ? 'is-on' : ''}" href="/keyword?q=${encodeURIComponent(q)}&sort=relevance" data-link>Best match</a>
      <a class="chip ${sort === 'newest' ? 'is-on' : ''}" href="/keyword?q=${encodeURIComponent(q)}&sort=newest" data-link>Newest first</a>
      <span class="keyword-tabs__hint">${sort === 'newest' ? 'newest to oldest' : 'ranked by relevance'}</span>
    </div>`;
}

function facetsMarkup(facets) {
  const topics = facets?.topics || [];
  const sources = facets?.sources || [];
  if (!topics.length && !sources.length) return '';
  return html`
    <div class="keyword-facets">
      ${topics.map((topic) => html`<a class="chip" href="/topic/${topic.id}" data-link>${topic.label} <span class="faint">${topic.count}</span></a>`)}
      ${sources.map((source) => html`<a class="chip" href="/source/${source.id}" data-link>${source.name} <span class="faint">${source.count}</span></a>`)}
    </div>`;
}

export async function keywordView(root, ctx) {
  const q = (ctx.query.q || '').trim();
  const sort = ctx.query.sort === 'newest' ? 'newest' : 'relevance';
  if (!q) {
    root.innerHTML = emptyState({
      title: 'Start with a keyword',
      text: 'Search a person, place, team or idea to browse every archived story about it.',
      action: '<a class="btn btn--primary" href="/search" data-link>Search the archive</a>',
    });
    return;
  }
  const boot = state.boot || {};
  root.innerHTML = html`
    ${header(q, 0, boot.archive?.earliest)}
    ${sortTabs(q, sort)}
    <div id="keyword-facets"></div>
    <div id="keyword-results" class="keyword-list">
      ${Array.from({ length: 8 }).map(() => html`<div class="skeleton" style="height:112px;border-radius:12px"></div>`)}
    </div>
    <div id="keyword-load-more" class="section"></div>`;

  const bindForm = () => {
    root.querySelector('[data-keyword-back]')?.addEventListener('click', () => {
      if (window.history.length > 1) window.history.back();
      else window.location.href = '/';
    });
    root.querySelector('#keyword-form')?.addEventListener('submit', (event) => {
      event.preventDefault();
      const value = event.currentTarget.querySelector('input').value.trim();
      if (value) window.location.href = `/keyword?q=${encodeURIComponent(value)}`;
    });
  };
  bindForm();

  const results = root.querySelector('#keyword-results');
  const loadMore = root.querySelector('#keyword-load-more');
  let offset = 0;
  let total = 0;
  const append = (items, first) => {
    const markup = items.map((item) => itemMarkup(item, q)).join('');
    if (first) results.innerHTML = markup;
    else results.insertAdjacentHTML('beforeend', markup);
    offset += items.length;
  };

  const load = async () => {
    try {
      const data = await get(`/api/keyword?q=${encodeURIComponent(q)}&sort=${sort}&offset=${offset}&limit=24`, 30);
      total = data.total || 0;
      if (!data.items.length && offset === 0) {
        results.innerHTML = emptyState({
          title: 'No archived matches',
          text: `Nothing for “${q}” yet. Try a shorter phrase, a different spelling, or advanced search.`,
          action: `<a class="btn btn--primary" href="/search?q=${encodeURIComponent(q)}" data-link>Advanced search</a>`,
        });
        loadMore.innerHTML = '';
        return;
      }
      const current = root.querySelector('.keyword-head');
      if (current) {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = header(q, total, boot.archive?.earliest);
        current.replaceWith(wrapper.querySelector('.keyword-head'));
        const meta = root.querySelector('.keyword-meta');
        if (meta) meta.replaceWith(wrapper.querySelector('.keyword-meta'));
        bindForm();
      }
      root.querySelector('#keyword-facets').innerHTML = facetsMarkup(data.facets);
      append(data.items, offset === 0);
      loadMore.innerHTML = data.has_more
        ? html`<button class="btn btn--ghost btn--block" id="keyword-more">Load more (${number(total - offset)} left)</button>`
        : html`<p class="tiny faint" style="text-align:center">End of the archive for this keyword.</p>`;
      root.querySelector('#keyword-more')?.addEventListener('click', async (event) => {
        event.currentTarget.disabled = true;
        event.currentTarget.textContent = 'Loading…';
        await load();
      });
    } catch (err) {
      errorState(results, err.message, () => keywordView(root, ctx));
    }
  };
  await load();
}
