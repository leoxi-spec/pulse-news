// Pulse Shorts: a full-screen, one-story-per-swipe feed.
// Native scroll-snap does the heavy lifting, so it stays smooth on a phone.
import { get } from '../api.js';
import { html, raw, icons, toast, copyText, confetti } from '../ui.js';
import { state, record, toggleSave } from '../store.js';
import { navigate } from '../router.js';

const MODES = [
  ['for-you', 'For you'],
  ['latest', 'Latest'],
  ['readable', 'Readable'],
];
const AUTO_MS = 14000;

function reactionMap() {
  try { return JSON.parse(localStorage.getItem('pulse.reactions') || '{}'); } catch { return {}; }
}

function setReaction(articleId, emoji) {
  const map = reactionMap();
  map[articleId] = emoji;
  try { localStorage.setItem('pulse.reactions', JSON.stringify(map)); } catch { /* private mode */ }
}

export async function reelsView(root, ctx) {
  document.body.classList.add('reels-mode');
  const mode = MODES.some(([id]) => id === ctx.query.mode) ? ctx.query.mode : 'for-you';
  root.innerHTML = html`
    <div class="reels reels--loading">
      <div class="reels__loading">
        <span class="reels__spinner" aria-hidden="true"></span>
        <p>Finding stories worth a swipe…</p>
      </div>
    </div>`;

  let items = [];
  try {
    const data = await get(`/api/feed?mode=${mode}&limit=24&days=7`, 30);
    items = data.items || [];
  } catch (err) {
    root.innerHTML = html`
      <div class="reels reels--message">
        <button class="reel-icon-btn" data-close aria-label="Back to home">${raw(icons.close)}</button>
        <h2>Shorts could not load</h2>
        <p>${err.message || 'Try again in a moment.'}</p>
        <button class="btn btn--primary" data-close>Back to the feed</button>
      </div>`;
    root.querySelectorAll('[data-close]').forEach((button) => button.addEventListener('click', () => navigate('/')));
    return;
  }
  if (!items.length) {
    root.innerHTML = html`
      <div class="reels reels--message">
        <button class="reel-icon-btn" data-close aria-label="Back to home">${raw(icons.close)}</button>
        <h2>No stories to swipe yet</h2>
        <p>The next refresh will fill this up.</p>
        <button class="btn btn--primary" data-close>Back to the feed</button>
      </div>`;
    root.querySelectorAll('[data-close]').forEach((button) => button.addEventListener('click', () => navigate('/')));
    return;
  }

  root.innerHTML = html`
    <div class="reels" id="reels">
      <div class="reels__top">
        <button class="reel-icon-btn" data-close aria-label="Close shorts" title="Back to feed">${raw(icons.close)}</button>
        <div class="segmented reels__tabs" role="tablist" aria-label="Shorts mode">
          ${MODES.map(([id, label]) => html`
            <button type="button" role="tab" aria-selected="${mode === id}" class="${mode === id ? 'is-on' : ''}" data-mode="${id}">${label}</button>`)}
        </div>
        <div class="reels__tools">
          <button class="reel-pill" data-autoplay aria-pressed="false" title="Advance automatically">${raw(icons.play)} Auto</button>
          <button class="reel-icon-btn" data-sound aria-pressed="false" title="Read the active story aloud" aria-label="Sound">${raw(icons.sound)}</button>
        </div>
      </div>

      <div class="reels__bars" aria-hidden="true">
        ${items.map((_, index) => html`<span class="reel-bar" data-bar="${index}"><i></i></span>`)}
      </div>

      <div class="reels__track" id="reels-track">
        ${items.map((item, index) => reelCard(item, index))}
      </div>

      <div class="reels__hint" data-hint><span>Swipe up</span><b>↑</b></div>
    </div>`;

  bind(root, items, mode);
}

function reelCard(item, index) {
  const icon = state.topicMap.get(item.topic)?.icon || '📰';
  const reactions = reactionMap();
  const liked = Boolean(reactions[item.id]);
  return html`
    <section class="reel ${index === 0 ? 'is-active' : ''}" data-reel="${index}" data-article="${item.id}">
      <div class="reel__bg reel__bg--fallback" aria-hidden="true"><span>${icon}</span><b>${item.topic_label || ''}</b></div>
      ${item.image ? html`
        <img class="reel__bg reel__bg--img" src="${item.image}" alt="" ${index === 0 ? 'fetchpriority="high"' : 'loading="lazy"'} decoding="async">` : ''}
      <div class="reel__shade"></div>

      <div class="reel__content">
        <div class="reel__badges">
          <span class="badge badge--glass">${item.topic_label || 'News'}</span>
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
        <button class="reel-act" data-listen aria-label="Listen">${raw(icons.sound)}<span>Listen</span></button>
        <button class="reel-act" data-share aria-label="Share">${raw(icons.share)}<span>Share</span></button>
        <button class="reel-act reel-act--open" data-open aria-label="Open article">${raw(icons.external)}<span>Open</span></button>
      </div>

      <div class="reel__heart" aria-hidden="true">❤️</div>
      <div class="reel__swipe" aria-hidden="true">↑</div>
    </section>`;
}

function bind(root, items, mode) {
  const reels = [...root.querySelectorAll('.reel')];
  const track = root.querySelector('#reels-track');
  const bars = [...root.querySelectorAll('.reel-bar')];
  const hint = root.querySelector('[data-hint]');
  const autoButton = root.querySelector('[data-autoplay]');
  const soundButton = root.querySelector('[data-sound]');
  const recorded = new Set();
  let active = 0;
  let auto = false;
  let autoTimer = null;
  let soundOn = false;
  let utterance = null;
  let cleaned = false;

  const stopSpeech = () => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    utterance = null;
    root.querySelectorAll('[data-listen]').forEach((button) => {
      button.classList.remove('is-on');
      button.querySelector('span').textContent = 'Listen';
    });
  };

  const speak = (item, button = null) => {
    if (!('speechSynthesis' in window)) return;
    stopSpeech();
    const text = `${item.title}. ${(item.preview || '').slice(0, 420)}`;
    utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.03;
    utterance.lang = 'en-US';
    utterance.onend = () => {
      if (button) { button.classList.remove('is-on'); button.querySelector('span').textContent = 'Listen'; }
    };
    utterance.onerror = () => {
      if (button) { button.classList.remove('is-on'); button.querySelector('span').textContent = 'Listen'; }
    };
    button?.classList.add('is-on');
    if (button) button.querySelector('span').textContent = 'Pause';
    window.speechSynthesis.speak(utterance);
  };

  const paintBars = (index) => {
    bars.forEach((bar, i) => {
      const fill = bar.firstElementChild;
      bar.classList.toggle('is-seen', i < index);
      bar.classList.toggle('is-active', i === index);
      if (i < index) {
        fill.style.transition = 'none';
        fill.style.width = '100%';
      } else if (i > index) {
        fill.style.transition = 'none';
        fill.style.width = '0%';
      } else if (!auto) {
        fill.style.transition = 'none';
        fill.style.width = '100%';
      }
    });
  };

  const aimAuto = () => {
    if (!auto) return;
    const fill = bars[active]?.firstElementChild;
    if (!fill) return;
    fill.style.transition = 'none';
    fill.style.width = '0%';
    requestAnimationFrame(() => {
      fill.style.transition = `width ${AUTO_MS}ms linear`;
      fill.style.width = '100%';
    });
  };

  const scheduleAuto = () => {
    clearTimeout(autoTimer);
    if (!auto) return;
    autoTimer = setTimeout(() => {
      if (active >= reels.length - 1) {
        auto = false;
        autoButton.classList.remove('is-on');
        autoButton.setAttribute('aria-pressed', 'false');
        autoButton.innerHTML = html`${raw(icons.play)} Auto`;
        toast('That’s the last one — you’re caught up.');
        return;
      }
      go(active + 1);
    }, AUTO_MS);
  };

  const setActive = (index) => {
    if (cleaned || index === active) return;
    active = index;
    reels.forEach((reel, i) => reel.classList.toggle('is-active', i === index));
    paintBars(index);
    hint?.classList.add('is-gone');
    const item = items[index];
    if (item && !recorded.has(item.id)) {
      recorded.add(item.id);
      record('view', { articleId: item.id, silent: true }).catch(() => {});
    }
    stopSpeech();
    if (soundOn && item) speak(item);
    if (auto) { aimAuto(); scheduleAuto(); }
    const next = items[index + 1];
    if (next?.image) {
      const preload = new Image();
      preload.src = next.image;
    }
  };

  const go = (index) => {
    if (index < 0 || index >= reels.length) return;
    track.scrollTo({ top: index * track.clientHeight, behavior: 'smooth' });
  };

  root.querySelectorAll('[data-close]').forEach((button) => {
    button.addEventListener('click', () => navigate('/'));
  });
  reels.forEach((reel) => {
    reel.querySelectorAll('.reel__bg--img').forEach((img) => {
      img.addEventListener('error', () => { img.style.display = 'none'; });
    });
  });

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting && Number(entry.target.dataset.reel) !== active) {
        setActive(Number(entry.target.dataset.reel));
      }
    });
  }, { root: track, threshold: 0.55 });
  reels.forEach((reel) => observer.observe(reel));

  const like = (reel, item, button = null) => {
    const liked = Boolean(reactionMap()[item.id]);
    const next = !liked;
    setReaction(item.id, next ? '❤️' : null);
    item.__liked = next;
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
      navigator.vibrate?.(8);
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
      if (saved) { confetti(8); navigator.vibrate?.(6); }
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

  reels.forEach((reel, index) => {
    const item = items[index];
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

    let lastTap = 0;
    reel.addEventListener('click', (event) => {
      if (event.target.closest('button, a')) return;
      const now = Date.now();
      if (now - lastTap < 320) like(reel, item);
      lastTap = now;
    });
  });

  track.addEventListener('scroll', () => hint?.classList.add('is-gone'), { passive: true, once: true });

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
    if (auto) { aimAuto(); scheduleAuto(); } else { clearTimeout(autoTimer); paintBars(active); }
  });

  soundButton.addEventListener('click', () => {
    soundOn = !soundOn;
    soundButton.classList.toggle('is-on', soundOn);
    soundButton.setAttribute('aria-pressed', String(soundOn));
    if (soundOn) { speak(items[active]); toast('Sound on — reading the active story'); }
    else stopSpeech();
  });

  const onKey = (event) => {
    if (!document.body.contains(root.querySelector('.reels'))) return;
    if (event.target.matches('input, textarea')) return;
    if (event.key === 'ArrowDown' || event.key === 'j') { event.preventDefault(); go(active + 1); }
    else if (event.key === 'ArrowUp' || event.key === 'k') { event.preventDefault(); go(active - 1); }
    else if (event.key === 'l') { event.preventDefault(); like(reels[active], items[active]); }
    else if (event.key === 's') { event.preventDefault(); save(reels[active], items[active]); }
    else if (event.key === 'm') { event.preventDefault(); soundButton.click(); }
    else if (event.key === ' ') { event.preventDefault(); autoButton.click(); }
    else if (event.key === 'Escape') { navigate('/'); }
  };
  document.addEventListener('keydown', onKey);

  const cleanup = () => {
    cleaned = true;
    observer.disconnect();
    clearTimeout(autoTimer);
    document.removeEventListener('keydown', onKey);
    stopSpeech();
  };

  // The SPA replaces #view's children; watch for that instead of leaking the
  // keyboard handler and timers into the next page.
  const watcher = new MutationObserver(() => {
    if (!root.querySelector('.reels')) {
      watcher.disconnect();
      cleanup();
    }
  });
  watcher.observe(root, { childList: true });

  paintBars(0);
  const first = items[0];
  if (first) {
    recorded.add(first.id);
    record('view', { articleId: first.id, silent: true }).catch(() => {});
  }
}
