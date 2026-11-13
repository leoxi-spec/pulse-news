import { get } from '../api.js';
import { state } from '../store.js';
import { html, raw, icons, compactNumber, number, absDate, errorState, emptyState } from '../ui.js';
import { rowsHtml, sectionHead } from '../components.js';

function keywordHero(q, total, earliest) {
  return html`
    <div class="keyword-head">
      <div>
        <p class="eyebrow">Keyword archive</p>
        <h1>“${q}”</h1>
        <p class="page-sub">Every article Pulse has ever fetched about this keyword — current reporting and the archive behind it.</p>
      </div>
      <form class="keyword-search" id="keyword-form" role="search">
        <input type="search" name="q" value="${q}" aria-label="Search another keyword" placeholder="Search another keyword">
        <button class="btn btn--primary" type="submit">${raw(icons.search)} Search</button>
      </form>
    </div>
    <div class="keyword-meta">
      <span><b>${number(total)}</b> article${total === 1 ? '' : 's'}</span>
      ${earliest ? html`<span class="faint">·</span><span>archive reaches back to ${absDate(earliest, false)}</span>` : ''}
      <span class="faint">·</span>
      <a href="/search?q=${encodeURIComponent(q)}" data-link>Advanced filters</a>
    </div>`;
}

function sortTabs(q, sort) {
  return html`
    <div class="chip-row" style="margin:.9rem 0 .2rem">
      <a class="chip ${sort === 'relevance' ? 'is-on' : ''}" href="/keyword?q=${encodeURIComponent(q)}&sort=relevance" data-link>Best match</a>
      <a class="chip ${sort === 'newest' ? 'is-on' : ''}" href="/keyword?q=${encodeURIComponent(q)}&sort=newest" data-link>Newest first</a>
      <a class="chip" href="/search?q=${encodeURIComponent(q)}" data-link>${raw(icons.filter)} Filters</a>
    </div>`;
}

function facetMarkup(facets) {
  if (!facets) return '';
  return html`
    <div class="keyword-facets">
      ${(facets.topics || []).map((topic) => html`<a class="chip" href="/topic/${topic.id}" data-link>${topic.label} <span class="faint">${topic.count}</span></a>`)}
      ${(facets.sources || []).map((source) => html`<a class="chip" href="/source/${source.id}" data-link>${source.name} <span class="faint">${source.count}</span></a>`)}
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
    ${keywordHero(q, 0, boot.archive?.earliest)}
    ${sortTabs(q, sort)}
    <div id="keyword-facets"></div>
    <div id="keyword-results" class="section">${rowsHtml([], { lead: true })}</div>
    <div id="keyword-load-more" class="section"></div>`;

  const bindKeywordForm = () => {
    root.querySelector('#keyword-form')?.addEventListener('submit', (event) => {
      event.preventDefault();
      const value = event.currentTarget.querySelector('input').value.trim();
      if (value) window.location.href = `/keyword?q=${encodeURIComponent(value)}`;
    });
  };
  bindKeywordForm();

  const results = root.querySelector('#keyword-results');
  const loadMore = root.querySelector('#keyword-load-more');
  results.innerHTML = html`<div class="news-rows">${Array.from({ length: 4 }).map(() => html`<div class="skeleton" style="height:180px;border-radius:16px"></div>`)}</div>`;

  let offset = 0;
  let total = 0;
  const append = (items, first) => {
    const markup = html`<div class="news-rows">${rowsHtml(items, { lead: first, seed: `keyword-${q}-${offset}` })}</div>`;
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
          text: `Nothing for “${q}” yet. Try a shorter phrase, a different spelling, or the advanced search.`,
          action: `<a class="btn btn--primary" href="/search?q=${encodeURIComponent(q)}" data-link>Advanced search</a>`,
        });
        loadMore.innerHTML = '';
        return;
      }
      const hero = root.querySelector('.keyword-head');
      if (hero) {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = keywordHero(q, total, boot.archive?.earliest);
        const nextHead = wrapper.querySelector('.keyword-head');
        const nextMeta = wrapper.querySelector('.keyword-meta');
        const meta = root.querySelector('.keyword-meta');
        if (nextHead) hero.replaceWith(nextHead);
        if (nextMeta && meta) meta.replaceWith(nextMeta);
        bindKeywordForm();
      }
      root.querySelector('#keyword-facets').innerHTML = facetMarkup(data.facets);
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
