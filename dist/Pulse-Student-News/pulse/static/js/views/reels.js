// Pulse Shorts: a full-screen, one-story-per-swipe feed that never really ends.
// It pages through several ranked streams, appends more as you approach the
// end, polls for fresh stories, and lets you jump to what arrived since.
import { get } from '../api.js';
import { html, raw, icons, toast, copyText, confetti, haptic, modal } from '../ui.js';
import { state, prefs, record, toggleSave } from '../store.js';
import { navigate } from '../router.js';
import { applyVoice } from '../voice.js';

const MODES = [
  ['for-you', 'For you'],
  ['latest', 'Latest'],
  ['readable', 'Readable'],
  ['video', 'Video'],
];
const TOPICS = ['world', 'tech', 'science', 'sports', 'culture', 'business', 'politics', 'health', 'climate', 'education', 'motorsport'];
const AUTO_MS = 14000;
const POLL_MS = 45000;

function readLocal(key, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(key));
    return value === null || value === undefined ? fallback : value;
  } catch { return fallback; }
}

function reactionMap() {
  try { return JSON.parse(localStorage.getItem('pulse.reactions') || '{}'); } catch { return {}; }
}

function setReaction(articleId, emoji) {
  const map = reactionMap();
  map[articleId] = emoji;
  try { localStorage.setItem('pulse.reactions', JSON.stringify(map)); } catch { /* private mode */ }
}

function buildStreams(mode) {
  if (mode === 'video') {
    return [
      { mode: 'video', days: 60, offset: 0, done: false },
      { mode: 'video', topic: 'sports', days: 60, offset: 0, done: false },
      { mode: 'video', topic: 'world', days: 60, offset: 0, done: false },
      { mode: 'video', topic: 'science', days: 60, offset: 0, done: false },
      { mode: 'video', topic: 'tech', days: 60, offset: 0, done: false },
      { mode: 'video', topic: 'education', days: 60, offset: 0, done: false },
    ];
  }
  const streams = [
    { mode, days: 7 },
    { mode: 'latest', days: 3 },
    { mode: 'breaking', days: 3 },
    { mode: 'readable', days: 14 },
    ...TOPICS.map((topic) => ({ mode: 'latest', topic, days: 14 })),
  ];
  streams.forEach((stream) => { stream.offset = 0; stream.done = false; });
  return streams;
}

export async function reelsView(root, ctx) {
  document.body.classList.add('reels-mode');
  const mode = MODES.some(([id]) => id === ctx.query.mode) ? ctx.query.mode : 'for-you';
  const startId = Number(ctx.query.start) || 0;
  root.innerHTML = html`
    <div class="reels reels--loading">
      <div class="reels__loading">
        <span class="reels__spinner" aria-hidden="true"></span>
        <p>Finding stories worth a swipe…</p>
      </div>
    </div>`;

  let items = [];
  const seen = new Set();
  const streams = buildStreams(mode);
  let streamIndex = 0;
  let initialError = null;

  const fetchNext = async () => {
    for (let attempt = 0; attempt < streams.length * 2; attempt += 1) {
      while (streamIndex < streams.length && streams[streamIndex].done) streamIndex += 1;
      if (streamIndex >= streams.length) return [];
      const stream = streams[streamIndex];
      const params = new URLSearchParams({
        mode: stream.mode, limit: '18', offset: String(stream.offset), days: String(stream.days),
      });
      if (stream.topic) params.set('topic', stream.topic);
      let data;
      try {
        data = await get(`/api/feed?${params}`, 20);
      } catch (err) {
        initialError = err;
        stream.done = true;
        streamIndex += 1;
        continue;
      }
      stream.offset += data.items?.length || 0;
      if (!data.has_more) {
        stream.done = true;
        streamIndex += 1;
      }
      const fresh = (data.items || []).filter((item) => !seen.has(item.id));
      if (fresh.length) return fresh;
    }
    return [];
  };

  try {
    while (items.length < 9) {
      const page = await fetchNext();
      if (!page.length) break;
      page.forEach((item) => { seen.add(item.id); items.push(item); });
    }
  } catch (err) {
    initialError = err;
  }

  // Deep links from a home card must start on that exact short, even if it
  // is outside the first page of the stream.
  if (startId && !items.some((item) => Number(item.id) === Number(startId))) {
    try {
      const data = await get(`/api/articles/${startId}`, 15);
      if (data?.article) {
        items.unshift(data.article);
        seen.add(Number(startId));
      }
    } catch { /* fall through to the normal stream */ }
  }

  if (!items.length) {
    root.innerHTML = html`
      <div class="reels reels--message">
        <button class="reel-icon-btn" data-close aria-label="Back to home">${raw(icons.close)}</button>
        <h2>Shorts could not load</h2>
        <p>${initialError?.message || 'Try again in a moment.'}</p>
        <button class="btn btn--primary" data-close>Back to the feed</button>
      </div>`;
    root.querySelectorAll('[data-close]').forEach((button) => button.addEventListener('click', () => navigate('/')));
    return;
  }

  root.innerHTML = html`
    <div class="reels" id="reels">
      <div class="reels__progress" aria-hidden="true"><i data-progress></i></div>

      <div class="reels__top">
        <button class="reel-icon-btn" data-close aria-label="Close shorts" title="Back to feed">${raw(icons.close)}</button>
        <div class="segmented reels__tabs" role="tablist" aria-label="Shorts mode">
          ${MODES.map(([id, label]) => html`
            <button type="button" role="tab" aria-selected="${mode === id}" class="${mode === id ? 'is-on' : ''}" data-mode="${id}">${label}</button>`)}
        </div>
        <div class="reels__tools">
          <button class="reels__live" data-live type="button" title="Check for new stories" aria-label="Check for new stories"><i></i></button>
          <span class="reels__count" data-count title="Story number">1</span>
          <button class="reel-pill" data-autoplay aria-pressed="false" title="Advance automatically">${raw(icons.play)} Auto</button>
          <button class="reel-icon-btn" data-sound aria-pressed="false" title="Read the active story aloud" aria-label="Sound">${raw(icons.sound)}</button>
        </div>
      </div>

      <button class="reels__fresh" data-fresh hidden aria-live="polite">0 new stories <span>↑</span></button>

      <div class="reels__track" id="reels-track">
        ${items.map((item) => reelCard(item))}
        ${loaderCard()}
      </div>

      <div class="reels__hint" data-hint><span>Swipe up</span><b>↑</b></div>
    </div>`;

  bind(root, items, mode, streams, fetchNext, seen, startId);
}

function reelCard(item) {
  const icon = state.topicMap.get(item.topic)?.label ? (state.topicMap.get(item.topic).label.match(/[A-Za-z]/g) || ['N']).slice(0, 2).join('').toUpperCase() : 'N';
  const liked = Boolean(reactionMap()[item.id]);
  const video = item.video;
  const fileVideo = video?.kind === 'file';
  return html`
    <section class="reel" data-article="${item.id}">
      <div class="reel__bg reel__bg--fallback" aria-hidden="true"><span class="reel__monogram">${icon}</span><b>${item.topic_label || ''}</b></div>
      ${item.image ? html`
        <img class="reel__bg reel__bg--img" src="${item.image}" alt="" loading="lazy" decoding="async">` : ''}
      ${fileVideo ? html`
        <video class="reel__bg reel__video" data-reel-video src="${video.url}" poster="${item.image || ''}" muted loop playsinline preload="metadata" tabindex="0" aria-label="Video. Tap or press M to toggle sound."></video>
        <span class="reel__sound-hint" data-sound-hint>Tap video for sound</span>` : ''}
      ${video && !fileVideo ? html`
        <button class="reel__video-play" type="button" data-reel-play aria-label="Play video">
          ${raw(icons.play)}<span>${video.provider || 'Video'}</span>
        </button>` : ''}
      <div class="reel__shade"></div>

      <div class="reel__content">
        <div class="reel__badges">
          <span class="badge badge--glass">${item.topic_label || 'News'}</span>
          ${video ? html`<span class="badge badge--glass">Video</span>` : ''}
          ${item.breaking ? html`<span class="badge badge--breaking">Breaking</span>` : ''}
          ${item.story?.source_count > 1 ? html`<span class="badge badge--glass">${item.story.source_count} outlets</span>` : ''}
        </div>
        <h2 class="reel__title">${item.title}</h2>
        ${item.preview ? html`<p class="reel__preview">${item.preview}</p>` : ''}
        <div class="reel__meta">
          <span>${item.source?.name || ''}</span><span aria-hidden="true">·</span>
          <span>${item.published_relative || ''}</span><span aria-hidden="true">·</span>
          <span>${item.reading_minutes} min</span>
        </div>
        ${(item.reasons || []).length ? html`
          <div class="reel__why">${item.reasons.slice(0, 2).map((reason) => html`<span>${reason}</span>`)}</div>` : ''}
        <button class="reel__read" data-open>Read the whole story ${raw(icons.chevron)}</button>
      </div>

      <div class="reel__rail">
        <button class="reel-act ${liked ? 'is-on' : ''}" data-like aria-pressed="${liked}" aria-label="Like">
          ${raw(icons.heart)}<span>${liked ? 'Liked' : 'Like'}</span>
        </button>
        <button class="reel-act ${item.saved ? 'is-on' : ''}" data-save aria-pressed="${Boolean(item.saved)}" aria-label="Save">
          ${raw(icons.bookmark)}<span>${item.saved ? 'Saved' : 'Save'}</span>
        </button>
        ${!video ? html`<button class="reel-act" data-listen aria-label="Listen">${raw(icons.sound)}<span>Listen</span></button>` : ''}
        <button class="reel-act" data-share aria-label="Share">${raw(icons.share)}<span>Share</span></button>
        <button class="reel-act reel-act--open" data-open aria-label="Open article">${raw(icons.external)}<span>Open</span></button>
      </div>

      <div class="reel__heart" aria-hidden="true">${raw(icons.heart)}</div>
    </section>`;
}

function loaderCard() {
  return html`
    <section class="reel reel--loader" data-loader>
      <div class="reel__loader">
        <span class="reels__spinner" aria-hidden="true"></span>
        <p data-loader-text>Loading more stories…</p>
        <button class="btn btn--sm btn--ghost" data-retry hidden>Check for new stories</button>
      </div>
    </section>`;
}

function openVideoModal(item) {
  const video = item.video;
  if (!video?.embed) return;
  const origin = encodeURIComponent(window.location.origin);
  const referrer = encodeURIComponent(window.location.href);
  const wrap = document.createElement('div');
  wrap.className = 'video-modal';
  const iframe = document.createElement('iframe');
  iframe.src = `${video.embed}${video.embed.includes('?') ? '&' : '?'}autoplay=1&rel=0&playsinline=1&origin=${origin}&widget_referrer=${referrer}`;
  iframe.title = item.title;
  iframe.referrerPolicy = 'strict-origin-when-cross-origin';
  iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen';
  iframe.allowFullscreen = true;
  wrap.appendChild(iframe);
  if (video.url) {
    const link = document.createElement('a');
    link.className = 'video-modal__link';
    link.href = video.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = `Open on ${video.provider || 'the source'}`;
    wrap.appendChild(link);
  }
  modal({ title: item.title, wide: true, body: wrap });
}

function bind(root, initialItems, mode, streams, fetchNext, seen, startId = 0) {
  const track = root.querySelector('#reels-track');
  const loader = root.querySelector('[data-loader]');
  const loaderText = root.querySelector('[data-loader-text]');
  const retry = root.querySelector('[data-retry]');
  const hint = root.querySelector('[data-hint]');
  const fresh = root.querySelector('[data-fresh]');
  const countEl = root.querySelector('[data-count]');
  const live = root.querySelector('[data-live]');
  const autoButton = root.querySelector('[data-autoplay]');
  const soundButton = root.querySelector('[data-sound]');
  const progressFill = root.querySelector('[data-progress]');

  const items = [...initialItems];
  const pending = [];
  let loading = false;
  let noMore = false;
  let active = 0;
  let auto = Boolean(prefs().autoplay_shorts);
  let autoTimer = null;
  let pollTimer = null;
  let soundOn = Boolean(prefs().shorts_sound);
  let utterance = null;
  let cleaned = false;
  let lastTap = 0;
  let activeStarted = performance.now();

  const saveDwell = (keepalive = false) => {
    const item = items[active];
    if (!item) return;
    const seconds = Math.min(180, (performance.now() - activeStarted) / 1000);
    activeStarted = performance.now();
    if (seconds < 1) return;
    const value = Math.round(seconds * 10) / 10;
    try {
      if (keepalive) {
        fetch('/api/events', {
          method: 'POST',
          keepalive: true,
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-Pulse-Client': 'web' },
          body: JSON.stringify({ kind: 'dwell', article_id: item.id, value }),
        }).catch(() => {});
      } else {
        record('dwell', { articleId: item.id, value }).catch(() => {});
      }
      const watch = readLocal('pulse.watch', {});
      watch[item.id] = { seconds: value, topic: item.topic, title: item.title, at: Date.now() };
      const keys = Object.keys(watch);
      if (keys.length > 240) delete watch[keys[0]];
      localStorage.setItem('pulse.watch', JSON.stringify(watch));
    } catch { /* ignore */ }
  };

  const realReels = () => [...track.querySelectorAll('.reel:not(.reel--loader)')];

  const refreshIndices = () => {
    realReels().forEach((reel, index) => { reel.dataset.reel = String(index); });
  };

  const stopSpeech = () => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    utterance = null;
    realReels().forEach((reel) => {
      const button = reel.querySelector('[data-listen]');
      if (button) { button.classList.remove('is-on'); button.querySelector('span').textContent = 'Listen'; }
    });
  };

  const speak = (item, button = null) => {
    if (!('speechSynthesis' in window)) return;
    stopSpeech();
    utterance = applyVoice(new SpeechSynthesisUtterance(`${item.title}. ${(item.preview || '').slice(0, 420)}`));
    utterance.onend = () => {
      if (button) { button.classList.remove('is-on'); button.querySelector('span').textContent = 'Listen'; }
    };
    button?.classList.add('is-on');
    if (button) button.querySelector('span').textContent = 'Pause';
    window.speechSynthesis.speak(utterance);
  };

  const paintProgress = () => {
    countEl.textContent = String(active + 1);
    if (!auto) {
      progressFill.style.transition = 'none';
      progressFill.style.width = '100%';
    }
  };

  const aimAuto = () => {
    if (!auto) return;
    progressFill.style.transition = 'none';
    progressFill.style.width = '0%';
    requestAnimationFrame(() => {
      progressFill.style.transition = `width ${AUTO_MS}ms linear`;
      progressFill.style.width = '100%';
    });
  };

  const stopAuto = () => {
    auto = false;
    clearTimeout(autoTimer);
    autoButton.classList.remove('is-on');
    autoButton.setAttribute('aria-pressed', 'false');
    autoButton.innerHTML = html`${raw(icons.play)} Auto`;
    progressFill.style.transition = 'none';
    progressFill.style.width = '100%';
  };

  let activeVideo = null;
  const syncVideo = (index) => {
    if (activeVideo) activeVideo.pause();
    activeVideo = null;
    const reel = realReels()[index];
    const hint = reel?.querySelector('[data-sound-hint]');
    if (hint) {
      hint.classList.remove('is-gone');
      hint.style.animation = 'none';
      void hint.offsetWidth;
      hint.style.animation = '';
    }
    const video = reel?.querySelector('video[data-reel-video]');
    if (video) {
      video.muted = true;
      if (video.readyState >= 2) video.classList.add('is-ready');
      video.play().catch(() => {});
      activeVideo = video;
    }
  };

  const go = (index) => {
    if (index < 0) return;
    track.scrollTo({ top: index * track.clientHeight, behavior: 'smooth' });
  };

  const scheduleAuto = () => {
    clearTimeout(autoTimer);
    if (!auto) return;
    autoTimer = setTimeout(async () => {
      if (active >= items.length - 1) {
        await loadMore();
        if (items.length > active + 1) go(active + 1);
        else { stopAuto(); toast('You’re all caught up for now — new stories land soon.'); }
        return;
      }
      go(active + 1);
    }, AUTO_MS);
  };

  const setActive = (index) => {
    if (cleaned || index === active) return;
    saveDwell();
    active = index;
    activeStarted = performance.now();
    realReels().forEach((reel, i) => reel.classList.toggle('is-active', i === index));
    syncVideo(index);
    paintProgress();
    hint?.classList.add('is-gone');
    const item = items[index];
    if (item) record('view', { articleId: item.id, silent: true }).catch(() => {});
    stopSpeech();
    if (soundOn && item) speak(item);
    if (auto) { aimAuto(); scheduleAuto(); }
    const next = items[index + 1];
    if (next?.image) { const preload = new Image(); preload.src = next.image; }
    maybeLoadMore();
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) setActive(Number(entry.target.dataset.reel));
    });
  }, { root: track, threshold: 0.55 });

  const bindReel = (reel, item) => {
    if (reel.dataset.bound) return;
    reel.dataset.bound = '1';
    reel.querySelectorAll('[data-like]').forEach((button) => button.addEventListener('click', (event) => {
      event.stopPropagation();
      like(reel, item, button);
    }));
    reel.querySelector('[data-save]')?.addEventListener('click', (event) => { event.stopPropagation(); save(reel, item); });
    reel.querySelector('[data-share]')?.addEventListener('click', (event) => { event.stopPropagation(); share(item); });
    reel.querySelector('[data-listen]')?.addEventListener('click', (event) => {
      event.stopPropagation();
      const button = event.currentTarget;
      if (button.classList.contains('is-on')) { stopSpeech(); return; }
      speak(item, button);
    });
    reel.querySelectorAll('[data-open]').forEach((button) => button.addEventListener('click', (event) => {
      event.stopPropagation();
      navigate(`/article/${item.id}`);
    }));
    const reelVideo = reel.querySelector('video[data-reel-video]');
    reelVideo?.addEventListener('loadeddata', () => reelVideo.classList.add('is-ready'), { once: true });
    reelVideo?.addEventListener('error', (event) => {
      event.currentTarget.style.display = 'none';
    });
    reel.querySelectorAll('[data-reel-play]').forEach((button) => button.addEventListener('click', (event) => {
      event.stopPropagation();
      openVideoModal(item);
    }));
    reel.querySelectorAll('.reel__bg--img').forEach((img) => {
      img.addEventListener('error', () => { img.style.display = 'none'; });
    });
    let soundTimer = null;
    const toggleSound = () => {
      const video = reel.querySelector('video[data-reel-video]');
      if (!video) return;
      video.muted = !video.muted;
      if (!video.muted) video.play().catch(() => {});
      reel.querySelector('[data-sound-hint]')?.classList.add('is-gone');
      toast(video.muted ? 'Video muted' : 'Video sound on');
    };
    reel.addEventListener('click', (event) => {
      if (event.target.closest('button, a')) return;
      const isFileVideo = item.video?.kind === 'file';
      const now = Date.now();
      if (now - lastTap < 320) {
        clearTimeout(soundTimer);
        like(reel, item);
        lastTap = now;
        return;
      }
      lastTap = now;
      if (isFileVideo) {
        clearTimeout(soundTimer);
        soundTimer = setTimeout(toggleSound, 280);
      }
    });
    reel.querySelector('video[data-reel-video]')?.addEventListener('keydown', (event) => {
      if (event.key === 'm' || event.key === 'M' || event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleSound();
      }
    });
  };

  const like = (reel, item, button = null) => {
    const liked = Boolean(reactionMap()[item.id]);
    const next = !liked;
    setReaction(item.id, next ? 'liked' : null);
    const heart = reel.querySelector('.reel__heart');
    if (heart && next) {
      heart.classList.remove('is-pop');
      void heart.offsetWidth;
      heart.classList.add('is-pop');
    }
    const likeButton = button || reel.querySelector('[data-like]');
    if (likeButton) {
      likeButton.classList.toggle('is-on', next);
      likeButton.setAttribute('aria-pressed', String(next));
      likeButton.querySelector('span').textContent = next ? 'Liked' : 'Like';
    }
    if (next) {
      record('like', { articleId: item.id }).catch(() => {});
      confetti(14);
      haptic(8);
    }
  };

  const save = async (reel, item) => {
    try {
      const { saved } = await toggleSave({ id: item.id, saved: Boolean(item.saved) });
      item.saved = saved;
      const button = reel.querySelector('[data-save]');
      button.classList.toggle('is-on', saved);
      button.setAttribute('aria-pressed', String(saved));
      button.querySelector('span').textContent = saved ? 'Saved' : 'Save';
      toast(saved ? 'Saved to your library' : 'Removed from saved');
      if (saved) { confetti(8); haptic(6); }
    } catch (err) {
      toast(err.message || 'Could not save this one.', { type: 'bad' });
    }
  };

  const share = async (item) => {
    const url = `${window.location.origin}/article/${item.id}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: item.title, text: item.preview || item.title, url });
        return;
      }
      await copyText(url);
      toast('Link copied');
    } catch { /* user cancelled */ }
  };

  const renderFresh = () => {
    if (!pending.length) { fresh.hidden = true; live.classList.remove('is-new'); return; }
    fresh.hidden = false;
    fresh.innerHTML = html`${pending.length} new ${pending.length === 1 ? 'story' : 'stories'} <span>↑</span>`;
  };

  const appendItems = (list) => {
    if (!list.length || cleaned) return;
    const before = items.length;
    // If the loader is what the reader is looking at, move them onto the first
    // new story. If we are only prefetching ahead, leave their place alone.
    const loaderVisible = loader.getBoundingClientRect().top < track.clientHeight * 0.6;
    loader.insertAdjacentHTML('beforebegin', list.map(reelCard).join(''));
    list.forEach((item) => {
      seen.add(item.id);
      items.push(item);
      const pendingIndex = pending.findIndex((row) => row.id === item.id);
      if (pendingIndex >= 0) pending.splice(pendingIndex, 1);
    });
    renderFresh();
    const added = realReels().slice(before);
    added.forEach((reel, index) => {
      bindReel(reel, list[index]);
      observer.observe(reel);
    });
    refreshIndices();
    paintProgress();
    if (loaderVisible) track.scrollTo({ top: before * track.clientHeight, behavior: 'instant' });
  };

  const prependItems = (list) => {
    if (!list.length || cleaned) return;
    const batch = list.filter((item) => !items.some((row) => row.id === item.id));
    if (!batch.length) return;
    list = batch;
    const first = track.querySelector('.reel');
    const height = track.clientHeight;
    first.insertAdjacentHTML('beforebegin', list.map(reelCard).join(''));
    list.forEach((item) => { seen.add(item.id); items.unshift(item); });
    const added = realReels().slice(0, list.length);
    added.forEach((reel, index) => {
      bindReel(reel, items[index]);
      observer.observe(reel);
    });
    refreshIndices();
    active += list.length;
    track.scrollTop += list.length * height;
    paintProgress();
    if (auto) { aimAuto(); scheduleAuto(); }
  };

  const loadMore = async () => {
    if (loading || noMore || cleaned) return [];
    loading = true;
    loader.classList.remove('is-done');
    loaderText.textContent = 'Loading more stories…';
    retry.hidden = true;
    try {
      const page = await fetchNext();
      if (page.length) {
        appendItems(page);
        return page;
      }
      noMore = true;
      loader.classList.add('is-done');
      loaderText.textContent = 'You’re all caught up for now. New stories land every few minutes.';
      retry.hidden = false;
    } catch {
      loaderText.textContent = 'Could not load more right now.';
      retry.hidden = false;
    } finally {
      loading = false;
    }
    return [];
  };

  const maybeLoadMore = () => {
    if (!loading && !noMore && active >= items.length - 4) loadMore();
  };

  const poll = async (manual = false) => {
    if (cleaned || (document.hidden && !manual)) return;
    try {
      const data = await get(`/api/feed?mode=latest&limit=12&days=1&_=${Date.now()}`, 15);
      if (cleaned) return;
      const newcomers = (data.items || []).filter((item) => !seen.has(item.id) && !pending.some((row) => row.id === item.id));
      if (!newcomers.length) {
        if (manual) toast('You’re up to date — new stories land every few minutes.');
        return;
      }
      pending.push(...newcomers.slice(0, 20));
      live.classList.add('is-new');
      renderFresh();
      hint?.classList.add('is-gone');
      noMore = false;
      loader.classList.remove('is-done');
      loaderText.textContent = 'Loading more stories…';
    } catch { /* offline is fine */ }
  };

  const loaderObserver = new IntersectionObserver((entries) => {
    // Seeing the loader means there is nothing left to swipe: always load,
    // even when the last active story is far behind (e.g. a direct jump).
    if (entries.some((entry) => entry.isIntersecting)) loadMore();
  }, { root: track, threshold: 0.4 });
  loaderObserver.observe(loader);

  realReels().forEach((reel, index) => {
    bindReel(reel, items[index]);
    observer.observe(reel);
  });
  refreshIndices();
  realReels()[0]?.classList.add('is-active');
  syncVideo(0);

  track.addEventListener('scroll', () => hint?.classList.add('is-gone'), { passive: true, once: true });

  fresh.addEventListener('click', () => {
    if (!pending.length) return;
    const batch = pending.splice(0, pending.length);
    prependItems(batch);
    fresh.hidden = true;
    live.classList.remove('is-new');
    track.scrollTo({ top: 0, behavior: 'smooth' });
  });

  retry.addEventListener('click', () => { noMore = false; loadMore(); });
  live.addEventListener('click', () => poll(true));
  const onVisible = () => { if (document.visibilityState === 'visible') poll(); };
  document.addEventListener('visibilitychange', onVisible);

  root.querySelectorAll('[data-close]').forEach((button) => {
    button.addEventListener('click', () => navigate('/'));
  });
  root.querySelectorAll('[data-mode]').forEach((button) => {
    button.addEventListener('click', () => {
      if (button.dataset.mode === mode) return;
      navigate(`/reels${button.dataset.mode === 'for-you' ? '' : `?mode=${button.dataset.mode}`}`);
    });
  });

  autoButton.addEventListener('click', () => {
    auto = !auto;
    autoButton.classList.toggle('is-on', auto);
    autoButton.setAttribute('aria-pressed', String(auto));
    autoButton.innerHTML = html`${raw(auto ? icons.pause : icons.play)} ${auto ? 'Auto on' : 'Auto'}`;
    if (auto) { aimAuto(); scheduleAuto(); } else { stopAuto(); }
  });

  soundButton.addEventListener('click', () => {
    soundOn = !soundOn;
    soundButton.classList.toggle('is-on', soundOn);
    soundButton.setAttribute('aria-pressed', String(soundOn));
    if (soundOn) { speak(items[active]); toast('Sound on — reading the active story'); }
    else stopSpeech();
  });

  const onKey = (event) => {
    if (cleaned || !root.querySelector('.reels')) return;
    if (event.target.matches('input, textarea')) return;
    if (event.key === 'ArrowDown' || event.key === 'j') { event.preventDefault(); go(active + 1); }
    else if (event.key === 'ArrowUp' || event.key === 'k') { event.preventDefault(); go(active - 1); }
    else if (event.key === 'l') { event.preventDefault(); like(realReels()[active], items[active]); }
    else if (event.key === 's') { event.preventDefault(); save(realReels()[active], items[active]); }
    else if (event.key === 'm') { event.preventDefault(); soundButton.click(); }
    else if (event.key === ' ') { event.preventDefault(); autoButton.click(); }
    else if (event.key === 'Escape') { navigate('/'); }
  };
  document.addEventListener('keydown', onKey);

  const onVisibility = () => {
    if (document.hidden) saveDwell(true);
    else activeStarted = performance.now();
  };
  document.addEventListener('visibilitychange', onVisibility);
  const onUnload = () => saveDwell(true);
  window.addEventListener('pagehide', onUnload);

  if (startId) {
    const target = items.findIndex((item) => item.id === startId);
    if (target > 0) {
      requestAnimationFrame(() => {
        track.scrollTo({ top: target * track.clientHeight, behavior: 'instant' });
        setActive(target);
      });
    }
  }
  try {
    if (!sessionStorage.getItem('pulse.reels.watchHint')) {
      sessionStorage.setItem('pulse.reels.watchHint', '1');
      toast('For You learns from how long you watch each story');
    }
  } catch { /* ignore */ }

  const cleanup = () => {
    cleaned = true;
    observer.disconnect();
    loaderObserver.disconnect();
    clearTimeout(autoTimer);
    clearInterval(pollTimer);
    saveDwell(true);
    if (activeVideo) { activeVideo.pause(); activeVideo = null; }
    document.removeEventListener('keydown', onKey);
    document.removeEventListener('visibilitychange', onVisibility);
    window.removeEventListener('pagehide', onUnload);
    stopSpeech();
  };

  const watcher = new MutationObserver(() => {
    if (!root.querySelector('.reels')) { watcher.disconnect(); cleanup(); }
  });
  watcher.observe(root, { childList: true });

  if (auto) {
    autoButton.classList.add('is-on');
    autoButton.setAttribute('aria-pressed', 'true');
    autoButton.innerHTML = html`${raw(icons.pause)} Auto on`;
    aimAuto();
    scheduleAuto();
  }
  if (soundOn) soundButton.classList.add('is-on');
  paintProgress();
  if (items[0]) record('view', { articleId: items[0].id, silent: true }).catch(() => {});
  maybeLoadMore();
  pollTimer = setInterval(poll, POLL_MS);
}
