import { html, raw, esc, timeAgo, absDate, compactNumber, icons, emptyState, proxyImg } from './ui.js';
export { emptyState };
import { topicLabel, topicIcon as topicEmoji } from './store.js';

export function hashHue(text) {
  let hash = 0;
  for (let i = 0; i < (text || '').length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) % 360;
  return hash;
}

export function sourceDot(source) {
  const hue = hashHue(source?.name || '');
  return html`<span class="src-dot" style="--h:${hue}" aria-hidden="true">${(source?.initials || source?.name || '?').slice(0, 2)}</span>`;
}

export function saveButton(item, { floating = true, label = false } = {}) {
  const on = item.saved ? 'is-on' : '';
  return html`<button class="icon-btn ${on} ${floating ? 'story-card__save' : ''}" type="button"
    data-action="toggle-save" data-id="${item.id}" aria-pressed="${item.saved ? 'true' : 'false'}"
    aria-label="${item.saved ? 'Remove from saved' : 'Save story'}" title="${item.saved ? 'Saved' : 'Save'}">
    ${raw(icons.bookmark)}${label ? html`<span class="small">${item.saved ? 'Saved' : 'Save'}</span>` : ''}
  </button>`;
}

export function reasonChips(item, max = 2) {
  const reasons = (item.reasons || []).filter(Boolean).slice(0, max);
  if (!reasons.length) return '';
  return html`<span class="hstack" style="gap:.3rem">${reasons.map((r) => html`<span class="reason">${r}</span>`)}</span>`;
}

export function accessInfo(item) {
  if (item.paywalled) {
    return { kind: 'locked', label: 'Subscription', title: 'The publisher requires a subscription for the full text' };
  }
  const full = item.has_full_text || item.content_state === 'extracted' || Number(item.word_count || 0) >= 240;
  if (full) {
    return { kind: 'full', label: 'Read here', title: 'Full article text is readable inside Pulse' };
  }
  return { kind: 'preview', label: 'Preview', title: 'Preview only — the full story opens at the publisher' };
}

export function accessPill(item, { compact = false } = {}) {
  const info = accessInfo(item);
  return html`<span class="access-pill access-pill--${info.kind}" title="${info.title}">
    <span class="access-dot" aria-hidden="true"></span>${compact ? '' : html`<span>${info.label}</span>`}
  </span>`;
}

export function storyKicker(item) {
  const source = item.source || {};
  return html`
    <div class="story-card__kicker">
      ${sourceDot(source)}
      <span class="tiny" style="font-weight:650;color:var(--text-2)">${source.name || 'Unknown'}</span>
      <span class="tiny faint" aria-hidden="true">·</span>
      <span class="tiny muted" title="${absDate(item.published_at || item.first_seen_at)}">${item.published_relative || timeAgo(item.published_at || item.first_seen_at)}</span>
      ${item.date_label === 'First seen' ? html`<span class="tiny faint">(first seen)</span>` : ''}
      ${item.breaking ? html`<span class="badge badge--breaking">Breaking</span>` : ''}
    </div>`;
}

export function videoBadge(item, cls = '') {
  if (!item?.video) return '';
  return html`<span class="video-badge ${cls}">${raw(icons.play)}<span>Video</span></span>`;
}

export function translatedBadge(item, { long = false } = {}) {
  const language = item?.language_name || 'another language';
  if (!item?.translated) {
    if (item?.language && item.language !== 'en') {
      return html`<span class="badge badge--translated" title="Translation is not available right now. The original article remains in ${language}.">Original: ${language}</span>`;
    }
    return '';
  }
  return html`<span class="badge badge--translated" title="Headline and overview translated into English. Full article remains in ${language}.">${long ? `Translated from ${language}` : 'Translated'}</span>`;
}

export function videoCard(item, { reels = false } = {}) {
  const href = reels ? `/reels?mode=video&start=${item.id}` : `/article/${item.id}`;
  return html`
    <article class="video-card" data-article-card="${item.id}">
      <a class="video-card__media" href="${href}" data-link aria-label="${item.title}">
        ${'' /* The fallback always sits behind the still, so a thumbnail the
               network filter or CDN blocks degrades to the topic mark instead
               of leaving an empty coloured rectangle. */}
        <span class="video-card__fallback" aria-hidden="true">${topicEmoji(item.topic) || 'N'}</span>
        ${item.image ? html`<img src="${item.image}" alt="" loading="lazy" decoding="async">` : ''}
        <span class="video-card__play" aria-hidden="true">${raw(icons.play)}</span>
        ${videoBadge(item, 'video-badge--solid')}
      </a>
      <div class="video-card__body">
        <div class="video-card__kicker">
          <span>${item.source?.name || ''}</span>
          <span class="faint">·</span>
          <span>${item.published_relative || ''}</span>
        </div>
        <h3 class="video-card__title"><a href="${href}" data-link>${item.title}</a></h3>
        <div class="video-card__meta">
          ${translatedBadge(item)}
          <span>${item.topic_label || topicLabel(item.topic)}</span>
          <span class="faint">·</span>
          <span>${item.video?.provider || 'Video'}</span>
        </div>
      </div>
    </article>`;
}

export function storyCard(item, { compact = false } = {}) {
  const hasImage = Boolean(item.image) && !compact;
  const outlets = item.story?.source_count > 1
    ? html`<span class="tiny faint">·</span><span class="tiny muted">${item.story.source_count} outlets</span>`
    : '';
  return html`
    <article class="card story-card ${hasImage ? '' : 'story-card--noimg'}" data-article-card="${item.id}">
      <a class="card__link" href="/article/${item.id}" data-link aria-label="${item.title}">
        <div class="story-card__body">
          ${storyKicker(item)}
          <h3 class="story-card__title">${item.title}</h3>
          ${item.preview ? html`<p class="story-card__summary">${item.preview}</p>` : ''}
          <div class="story-card__foot">
            ${accessPill(item)}
            ${translatedBadge(item)}
            <span class="tiny faint">·</span>
            <span class="tiny muted">${item.reading_minutes} min read</span>
            <span class="tiny faint">·</span>
            <span class="tiny muted">${item.topic_label || topicLabel(item.topic)}</span>
            ${outlets}
            ${reasonChips(item)}
          </div>
        </div>
        ${hasImage ? html`<div class="story-card__media"><img class="story-card__img" src="${item.image}" alt="" loading="lazy" decoding="async" width="150" height="108">${videoBadge(item, 'video-badge--card')}</div>` : ''}
      </a>
      ${saveButton(item)}
    </article>`;
}

export function heroCard(item, { label = 'Top story' } = {}) {
  if (!item) return '';
  return html`
    <article class="hero" data-article-card="${item.id}">
      ${item.image ? html`<img class="hero__img" src="${item.image}" alt="" fetchpriority="high" decoding="async">` : html`<div class="hero__img" style="background:var(--grad)"></div>`}
      <div class="hero__shade"></div>
      <div class="hero__body">
        <div class="hero__top">
          ${item.breaking ? html`<span class="badge badge--breaking">Breaking</span>` : html`<span class="badge badge--glass">${label}</span>`}
          <span class="badge badge--glass">${item.topic_label || topicLabel(item.topic)}</span>
          ${item.story?.source_count > 2 ? html`<span class="badge badge--glass">${item.story.source_count} outlets covering</span>` : ''}
          ${videoBadge(item, 'video-badge--glass')}
        </div>
        <h2 class="hero__title"><a href="/article/${item.id}" data-link>${item.title}</a></h2>
        ${item.preview ? html`<p class="hero__summary">${item.preview}</p>` : ''}
        <div class="hero__meta">
          <span>${item.source?.name || ''}</span>
          <span aria-hidden="true">·</span>
          <span title="${absDate(item.published_at || item.first_seen_at)}">${item.published_relative || timeAgo(item.published_at || item.first_seen_at)}</span>
          <span aria-hidden="true">·</span>
          <span>${item.reading_minutes} min read</span>
          ${accessPill(item)}
          ${item.reasons?.length ? html`<span class="badge badge--glass">${item.reasons[0]}</span>` : ''}
        </div>
      </div>
    </article>`;
}

export function isFreshBreaking(item) {
  if (!item.breaking) return false;
  const stamp = item.published_at || item.first_seen_at;
  if (!stamp) return false;
  const age = Date.now() - new Date(stamp).getTime();
  return age >= 0 && age < 90 * 60 * 1000;
}

export function seededRandom(seed) {
  let h = 1779033703 ^ String(seed || '').length;
  for (let i = 0; i < String(seed || '').length; i += 1) {
    h = Math.imul(h ^ String(seed).charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return () => {
    h = Math.imul(h ^ (h >>> 16), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

export function newsRows(items, { lead = false, seed = '' } = {}) {
  const rng = seededRandom(seed);
  const rows = [];
  let pool = [...items];
  let index = 0;
  if (lead && pool.length >= 5) {
    const imageIndex = pool.findIndex((item) => Boolean(item.image));
    const leadIndex = imageIndex >= 0 ? imageIndex : 0;
    const [leadItem] = pool.splice(leadIndex, 1);
    rows.push([leadItem]);
    index = 0;
  }
  while (index < pool.length) {
    const remaining = pool.length - index;
    const roll = rng();
    let size = roll < 0.42 ? 4 : roll < 0.76 ? 3 : 2;
    if (remaining <= 4) {
      rows.push(pool.slice(index));
      break;
    }
    if (remaining - size === 1) size -= 1;
    rows.push(pool.slice(index, index + size));
    index += size;
  }
  return rows;
}

export function rowsHtml(items, { lead = false, seed = '' } = {}) {
  return newsRows(items, { lead, seed }).map((row) => {
    const size = row.length === 1 ? 'lead' : row.length === 2 ? 'medium' : 'small';
    return html`<div class="news-row row-${row.length}">${row.map((item) => mosaicCard(item, { size }))}</div>`;
  });
}

export function mosaicCard(item, { size = 'small' } = {}) {
  const showSummary = size === 'lead';
  const hasImage = Boolean(item.image);
  return html`
    <article class="mcard mcard--${size} ${hasImage ? '' : 'mcard--noimg'}">
      ${hasImage ? html`
        <a class="mcard__media" href="/article/${item.id}" data-link aria-label="${item.title}">
          <span class="media-fallback" aria-hidden="true">
            <b>${item.source?.initials || topicEmoji(item.topic) || 'N'}</b>
            <i>${item.source?.name || ''}</i>
          </span>
          <img class="mcard__img" src="${item.image}" alt="" loading="lazy" decoding="async">
          ${item.image_count > 1 ? html`<span class="photo-count photo-count--card">${raw(icons.camera)} ${item.image_count}</span>` : ''}
          ${videoBadge(item, 'video-badge--card')}
          ${isFreshBreaking(item) && !hasImage ? '' : isFreshBreaking(item) ? html`<span class="badge badge--breaking mcard__flag">Breaking</span>` : ''}
        </a>` : ''}
      ${hasImage ? '' : html`
        <div class="mcard__noimg-banner" aria-hidden="true">
          <span>${item.source?.initials || topicEmoji(item.topic) || 'N'}</span>
          <b>${item.topic_label || item.source?.name || ''}</b>
        </div>`}
      <div class="mcard__body">
        <div class="mcard__kicker">
          ${hasImage ? '' : html`<span class="mcard__dot" aria-hidden="true">${item.source?.initials || topicEmoji(item.topic) || 'N'}</span>`}
          <span>${item.source?.name || ''}</span>
          ${translatedBadge(item)}
          ${item.story?.source_count > 1 ? html`<span class="faint">·</span><span>${item.story.source_count} outlets</span>` : ''}
          ${!hasImage && isFreshBreaking(item) ? html`<span class="badge badge--breaking">Breaking</span>` : ''}
          ${!hasImage ? videoBadge(item, 'video-badge--inline') : ''}
        </div>
        <h3 class="mcard__title"><a href="/article/${item.id}" data-link>${item.title}</a></h3>
        ${showSummary && item.preview ? html`<p class="mcard__summary">${item.preview}</p>` : ''}
        <div class="mcard__meta">
          ${accessPill(item)}
          <span class="faint">·</span>
          <span>${item.published_relative}</span>
          <span class="faint">·</span>
          <span>${item.reading_minutes} min</span>
        </div>
      </div>
      ${saveButton(item)}
    </article>`;
}

export function topCard(item) {
  return html`
    <article class="top-card ${item.image ? '' : 'top-card--noimg'}">
      ${item.image ? html`
        <a href="/article/${item.id}" data-link aria-label="${item.title}" class="top-card__media">
          <span class="media-fallback" aria-hidden="true">
            <b>${item.source?.initials || topicEmoji(item.topic) || 'N'}</b>
            <i>${item.source?.name || ''}</i>
          </span>
          <img class="top-card__img" src="${item.image}" alt="" loading="eager" decoding="async">
          ${item.image_count > 1 ? html`<span class="photo-count photo-count--card">${raw(icons.camera)} ${item.image_count}</span>` : ''}
          ${videoBadge(item, 'video-badge--card')}
        </a>` : html`
        <a class="top-card__banner" href="/article/${item.id}" data-link aria-label="${item.title}">
          <span aria-hidden="true">${item.source?.initials || topicEmoji(item.topic) || 'N'}</span>
          <b>${item.topic_label || ''}</b>
        </a>`}
      <div class="top-card__body">
        <div class="top-card__source">
          <span>${item.source?.name || ''}</span>
          ${translatedBadge(item)}
          ${item.story?.source_count > 1 ? html`<span class="faint">·</span><span>${item.story.source_count} outlets</span>` : ''}
        </div>
        <h3 class="top-card__title"><a href="/article/${item.id}" data-link>${item.title}</a></h3>
        ${item.preview ? html`<p class="top-card__preview">${item.preview}</p>` : ''}
        <div class="top-card__meta">
          ${accessPill(item)}
          <span class="faint">·</span>
          <span>${item.published_relative}</span>
          <span class="faint">·</span>
          <span>${item.reading_minutes} min</span>
        </div>
      </div>
    </article>`;
}

export function hCard(item) {
  return html`
    <article class="hcard">
      <a href="/article/${item.id}" data-link aria-label="${item.title}">
        ${item.image
          ? html`<img class="hcard__img" src="${item.image}" alt="" loading="lazy" decoding="async">`
          : html`<div class="hcard__img media-placeholder" aria-hidden="true"><span>${item.source?.initials || topicEmoji(item.topic) || 'N'}</span></div>`}
      </a>
      <div class="hcard__body">
        <h3 class="hcard__title"><a href="/article/${item.id}" data-link>${item.title}</a></h3>
        <div class="hcard__meta">
          ${accessPill(item)}
          ${translatedBadge(item)}
          <span>${item.source?.name || ''}</span>
          <span class="faint">·</span>
          <span>${item.published_relative}</span>
        </div>
      </div>
    </article>`;
}

export function sectionHead(title, action = '', { sub = '' } = {}) {
  return html`
    <div class="section-head">
      <h2>${title}${sub ? html` <span class="small muted" style="font-weight:400">${sub}</span>` : ''}</h2>
      ${raw(action)}
    </div>`;
}

export function scoreMini(game) {
  const competitors = [...(game.competitors || [])].sort((a, b) => (a.home === b.home ? 0 : a.home ? 1 : -1));
  const state = game.status?.state || 'pre';
  return html`
    <a class="score-mini ${game.is_live ? 'is-live' : ''}" href="/sports#${game.league || ''}">
      <div class="score-mini__top">
        <span>${game.is_live ? '● LIVE' : state === 'post' ? 'Final' : 'Upcoming'}</span>
        <span>${(game.league || '').toUpperCase()}</span>
      </div>
      ${competitors.map((team) => html`
        <div class="score-mini__row">
          <span class="score-mini__team">
            ${team.logo ? html`<img src="${proxyImg(team.logo)}" alt="" loading="lazy">` : ''}
            <span>${team.abbr || team.short || team.name}</span>
          </span>
          <span class="score-mini__score">${state === 'pre' ? '–' : esc(team.score ?? 0)}</span>
        </div>`)}
      <div class="tiny muted">${game.status?.detail || ''}</div>
    </a>`;
}

export function leanBar(leans = {}) {
  const total = Object.values(leans).reduce((sum, n) => sum + n, 0);
  if (!total) return '';
  const order = ['left', 'center-left', 'center', 'center-right', 'right', 'state'];
  return html`
    <div class="lean-bar" role="img" aria-label="Approximate editorial spread of coverage">
      ${order.filter((k) => leans[k]).map((k) => html`<span class="lean-${k}" style="width:${(leans[k] / total) * 100}%"></span>`)}
    </div>`;
}

export function topicTile(topic) {
  return html`
    <a class="tile" href="/topic/${topic.slug}" data-link>
      <span class="tile__icon" aria-hidden="true">${topicEmoji(topic.slug)}</span>
      <span>
        <span class="tile__label">${topic.label}</span>
        <span class="tile__count">${compactNumber(topic.count)} stories${topic.relative ? ` · ${topic.relative}` : ''}</span>
      </span>
    </a>`;
}


export function skeletonFeed(count = 5) {
  return html`<div class="feed" aria-hidden="true">
    ${Array.from({ length: count }).map(() => html`
      <div class="card" style="padding:1rem;display:flex;gap:1rem">
        <div style="flex:1" class="stack-sm">
          <div class="skeleton skeleton--line" style="width:32%"></div>
          <div class="skeleton skeleton--line" style="width:88%;height:18px"></div>
          <div class="skeleton skeleton--line" style="width:70%"></div>
          <div class="skeleton skeleton--line" style="width:24%"></div>
        </div>
        <div class="skeleton" style="width:130px;height:96px;border-radius:12px"></div>
      </div>`)}
  </div>`;
}

export function stat(value, label) {
  return html`<div class="stat"><div class="stat__value">${value}</div><div class="stat__label">${label}</div></div>`;
}

export function readTimeChip(minutes) {
  return html`<span class="tiny muted hstack" style="gap:.25rem">${raw(icons.clock)}${minutes} min</span>`;
}

export function topicChips(topics, { active = '', base = '/topic' } = {}) {
  return html`<div class="chip-row" role="tablist">
    ${topics.map((t) => html`<a class="chip ${active === t.slug ? 'is-on' : ''}" href="${base}/${t.slug}" data-link role="tab">${t.label}</a>`)}
  </div>`;
}
