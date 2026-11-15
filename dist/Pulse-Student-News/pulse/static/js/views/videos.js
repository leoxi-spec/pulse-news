import { get } from '../api.js';
import { html, raw, icons, modal, errorState, emptyState } from '../ui.js';
import { videoCard } from '../components.js';

const FILTERS = [
  { id: '', label: 'All' },
  { id: 'news', label: 'News' },
  { id: 'sports', label: 'Sports' },
  { id: 'science', label: 'Science' },
  { id: 'tech', label: 'Tech' },
  { id: 'education', label: 'Learning' },
  { id: 'motorsport', label: 'Formula 1' },
];

function playerBody(item) {
  const video = item.video;
  if (!video) return '';
  const wrap = document.createElement('div');
  wrap.className = 'video-modal';
  if (video.kind === 'file' && video.url) {
    const node = document.createElement('video');
    node.controls = true;
    node.autoplay = true;
    node.playsInline = true;
    node.src = video.url;
    if (item.image) node.poster = item.image;
    const showUnavailable = () => {
      wrap.innerHTML = '';
      const box = document.createElement('div');
      box.className = 'video-unavailable';
      box.innerHTML = '<b>This clip is unavailable</b><span>The publisher\'s video file did not load.</span>';
      const link = document.createElement('a');
      link.className = 'btn btn--sm';
      link.href = `/article/${item.id}`;
      link.textContent = 'Open the story';
      box.appendChild(link);
      wrap.appendChild(box);
    };
    if (node.error) showUnavailable();
    else node.addEventListener('error', showUnavailable, { once: true });
    wrap.appendChild(node);
  } else if (video.embed) {
    const origin = encodeURIComponent(window.location.origin);
    const referrer = encodeURIComponent(window.location.href);
    const iframe = document.createElement('iframe');
    iframe.src = `${video.embed}${video.embed.includes('?') ? '&' : '?'}autoplay=1&rel=0&playsinline=1&origin=${origin}&widget_referrer=${referrer}`;
    iframe.title = item.title;
    iframe.referrerPolicy = 'strict-origin-when-cross-origin';
    iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen';
    iframe.allowFullscreen = true;
    iframe.className = 'video-embed';
    wrap.appendChild(iframe);
  }
  if (video.url) {
    const link = document.createElement('a');
    link.href = video.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.className = 'video-modal__link';
    link.textContent = `Open on ${video.provider || 'the source'}`;
    wrap.appendChild(link);
  }
  return wrap;
}

function openPlayer(item) {
  if (!item?.video) return;
  modal({
    title: item.title,
    wide: true,
    body: playerBody(item),
  });
}

function leadMarkup(item) {
  if (!item) return '';
  return html`
    <article class="video-lead" data-article-card="${item.id}">
      <button class="video-lead__media" type="button" data-play="${item.id}" aria-label="Play ${item.title}">
        ${item.image ? html`<img src="${item.image}" alt="" fetchpriority="high" decoding="async">` : html`<span class="video-lead__fallback" aria-hidden="true">${item.topic_label || 'Video'}</span>`}
        <span class="video-lead__shade" aria-hidden="true"></span>
        <span class="video-lead__play" aria-hidden="true">${raw(icons.play)}</span>
        <span class="video-badge video-badge--solid">${raw(icons.play)}<span>Video</span></span>
      </button>
      <div class="video-lead__body">
        <div class="video-lead__kicker">
          <span>${item.source?.name || ''}</span>
          <span class="faint">·</span>
          <span>${item.published_relative || ''}</span>
          <span class="faint">·</span>
          <span>${item.video?.provider || 'Video'}</span>
        </div>
        <h2><a href="/article/${item.id}" data-link>${item.title}</a></h2>
        ${item.preview ? html`<p>${item.preview}</p>` : ''}
        <div class="video-lead__actions">
          <button class="btn btn--primary" type="button" data-play="${item.id}">${raw(icons.play)} Play video</button>
          <a class="btn" href="/article/${item.id}" data-link>Read the story ${raw(icons.chevron)}</a>
        </div>
      </div>
    </article>`;
}

export async function videosView(root, ctx) {
  const topic = ctx.query.topic || '';
  const active = FILTERS.find((filter) => filter.id === topic) || FILTERS[0];
  root.innerHTML = html`
    <div class="page-head page-head--videos">
      <div>
        <div class="eyebrow">Watch</div>
        <h1>News that moves.</h1>
        <p class="page-head__sub">Video from newsrooms, leagues, space agencies and the creators who explain the world best.</p>
      </div>
      <div class="video-filters" role="tablist" aria-label="Video topics">
        ${FILTERS.map((filter) => html`
          <a class="chip ${filter.id === active.id ? 'is-active' : ''}" href="/videos${filter.id ? `?topic=${filter.id}` : ''}" data-link role="tab" aria-selected="${filter.id === active.id}">${filter.label}</a>`)}
      </div>
    </div>
    <div id="videos-body">
      <div class="video-grid">${Array.from({ length: 6 }).map(() => html`<div class="skeleton" style="height:260px;border-radius:18px"></div>`)}</div>
    </div>`;

  let data;
  try {
    data = await get(`/api/videos?limit=25&topic=${encodeURIComponent(topic)}`, 30);
  } catch (err) {
    errorState(root.querySelector('#videos-body'), err.message, () => videosView(root, ctx));
    return;
  }
  const body = root.querySelector('#videos-body');
  if (!body) return;
  if (!data.items?.length) {
    body.innerHTML = emptyState({
      title: 'No video here yet',
      text: 'The next refresh will bring clips from this topic. Try another filter or check back in a few minutes.',
      action: '<a class="btn btn--primary" href="/videos" data-link>All videos</a>',
    });
    return;
  }
  const [lead, ...rest] = data.items;
  body.innerHTML = html`
    ${leadMarkup(lead)}
    <div class="video-grid" id="video-grid">${rest.map((item) => videoCard(item))}</div>
    <div class="video-more">
      ${data.has_more ? html`<button class="btn" id="video-more" type="button">${raw(icons.refresh)} Load more videos</button>` : html`<span class="tiny faint">You have reached the end of this stream.</span>`}
    </div>`;

  const byId = new Map(data.items.map((item) => [String(item.id), item]));
  body.querySelectorAll('[data-play]').forEach((button) => {
    button.addEventListener('click', () => openPlayer(byId.get(button.dataset.play)));
  });

  let offset = data.items.length;
  const more = body.querySelector('#video-more');
  more?.addEventListener('click', async () => {
    more.disabled = true;
    more.textContent = 'Loading…';
    try {
      const next = await get(`/api/videos?limit=24&offset=${offset}&topic=${encodeURIComponent(topic)}`, 30);
      const grid = body.querySelector('#video-grid');
      next.items.forEach((item) => {
        byId.set(String(item.id), item);
        grid.insertAdjacentHTML('beforeend', videoCard(item).toString());
      });
      offset += next.items.length;
      if (!next.has_more) {
        more.remove();
        body.querySelector('.video-more').innerHTML = '<span class="tiny faint">You have reached the end of this stream.</span>';
      } else {
        more.disabled = false;
        more.innerHTML = `${raw(icons.refresh)} Load more videos`;
      }
    } catch (err) {
      more.disabled = false;
      more.textContent = 'Try again';
    }
  });
}
