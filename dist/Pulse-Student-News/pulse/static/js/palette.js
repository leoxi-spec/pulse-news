// Command palette: search news, jump to topics/sources, run quick actions.
import { get } from './api.js';
import { html, raw, icons, debounce, toast } from './ui.js';
import { navigate } from './router.js';
import { state, topicLabel } from './store.js';

const ACTIONS = [
  { id: 'home', label: 'Home feed', hint: 'Your personalised front page', icon: 'home', path: '/' },
  { id: 'brief', label: 'Two-minute brief', hint: 'The day in five stories', icon: 'bolt', path: '/brief' },
  { id: 'reels', label: 'Pulse Shorts', hint: 'Full-screen, one swipe per story', icon: 'play', path: '/reels' },
  { id: 'videos', label: 'Watch video', hint: 'Newsroom clips and YouTube explainers', icon: 'play', path: '/videos' },
  { id: 'discover', label: 'Explore topics', hint: 'All sections and trending', icon: 'compass', path: '/discover' },
  { id: 'sports', label: 'Live scores', hint: 'NBA, NFL, football and more', icon: 'trophy', path: '/sports' },
  { id: 'study', label: 'Study mode', hint: 'Quiz, flashcards, jargon', icon: 'book', path: '/study' },
  { id: 'research', label: 'Research & citations', hint: 'Build a bibliography', icon: 'quote', path: '/research' },
  { id: 'sources', label: 'Sources directory', hint: '366 outlets and feed health', icon: 'filter', path: '/sources' },
  { id: 'saved', label: 'Saved stories', hint: 'Your reading list', icon: 'bookmark', path: '/saved' },
  { id: 'about', label: 'About the project', hint: 'Story, principles, press kit', icon: 'info', path: '/about' },
  { id: 'impact', label: 'Impact report', hint: 'Live product and reading metrics', icon: 'sparkle', path: '/impact' },
  { id: 'classroom', label: 'Classroom toolkit', hint: 'A 45-minute news literacy lesson', icon: 'book', path: '/classroom' },
  { id: 'arcade', label: 'Arcade', hint: 'Fifteen small games and brain breaks', icon: 'game', path: '/arcade' },
  { id: 'roadmap', label: 'Roadmap & feedback', hint: 'Vote and send product feedback', icon: 'note', path: '/roadmap' },
  { id: 'profile', label: 'Profile & settings', hint: 'Themes, goals, AI, data', icon: 'user', path: '/profile' },
  { id: 'random', label: 'Surprise me', hint: 'Open a random story from the archive', icon: 'sparkle' },
];

let root = null;
let input = null;
let results = null;
let items = [];
let active = 0;
let openFlag = false;
let searchAbort = null;

function recent() {
  try { return JSON.parse(localStorage.getItem('pulse.recent') || '[]').slice(0, 6); }
  catch { return []; }
}

function remember(query) {
  const value = (query || '').trim();
  if (value.length < 2) return;
  const list = recent().filter((item) => item.toLowerCase() !== value.toLowerCase());
  list.unshift(value);
  try { localStorage.setItem('pulse.recent', JSON.stringify(list.slice(0, 12))); } catch { /* ignore */ }
}

function ensureRoot() {
  if (root) return;
  root = document.createElement('div');
  root.className = 'palette-root';
  root.hidden = true;
  root.innerHTML = html`
    <div class="palette" role="dialog" aria-modal="true" aria-label="Search Pulse">
      <div class="palette__box">
        <div class="palette__input-row">
          ${raw(icons.search)}
          <input id="palette-input" type="search" placeholder="Search news, topics, sources…" autocomplete="off" spellcheck="false" aria-label="Search news">
          <kbd class="kbd">esc</kbd>
        </div>
        <div class="palette__results" id="palette-results"></div>
        <div class="palette__footer">
          <span><kbd class="kbd">↑</kbd><kbd class="kbd">↓</kbd> navigate</span>
          <span><kbd class="kbd">↵</kbd> open</span>
          <span><kbd class="kbd">esc</kbd> close</span>
        </div>
      </div>
    </div>`;
  document.body.append(root);
  input = root.querySelector('#palette-input');
  results = root.querySelector('#palette-results');

  root.addEventListener('mousedown', (event) => {
    if (event.target === root) close();
  });
  input.addEventListener('input', debounce(() => query(input.value), 160));
  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown') { event.preventDefault(); move(1); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); move(-1); }
    else if (event.key === 'Enter') {
      event.preventDefault();
      const selected = items[active];
      if (selected) activate(selected);
      else if (input.value.trim()) goSearch();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      close();
    }
  });
  results.addEventListener('click', (event) => {
    const node = event.target.closest('[data-index]');
    if (!node) return;
    const item = items[Number(node.dataset.index)];
    if (item) activate(item);
  });
  results.addEventListener('mousemove', (event) => {
    const node = event.target.closest('[data-index]');
    if (!node) return;
    active = Number(node.dataset.index);
    paintActive();
  });
}

function sectionLabel(label) {
  return html`<div class="palette__section">${label}</div>`;
}

function itemMarkup(item, index) {
  const icon = item.kind === 'action' ? icons[item.icon] || icons.chevron
    : item.kind === 'topic' ? null
    : item.kind === 'source' ? null
    : icons.search;
  return html`
    <button class="palette__item ${index === active ? 'is-active' : ''}" data-index="${index}" type="button">
      <span class="palette__icon">${item.kind === 'topic' ? (item.slug || 'T').slice(0, 2).toUpperCase() : item.kind === 'source' ? (item.initials || 'S') : raw(icon || icons.search)}</span>
      <span class="palette__body">
        <span class="palette__label">${item.label}</span>
        <span class="palette__hint">${item.hint}</span>
      </span>
      ${item.kind === 'headline' ? html`<span class="palette__badge">${topicLabel(item.topic)}</span>` : ''}
    </button>`;
}

async function query(value) {
  const text = (value || '').trim();
  if (text.length < 2) { renderDefault(); return; }
  if (searchAbort) searchAbort.abort();
  searchAbort = new AbortController();
  results.innerHTML = html`<div class="palette__loading">Searching the archive…</div>`;
  try {
    const data = await get(`/api/search/suggest?q=${encodeURIComponent(text)}`, 10, true);
    const next = [];
    const groups = [];
    if (data.headlines?.length) {
      groups.push(sectionLabel('Headlines'));
      data.headlines.forEach((headline) => {
        next.push({ kind: 'headline', label: headline.title, hint: headline.source, id: headline.id, topic: headline.topic });
      });
    }
    if (data.topics?.length) {
      groups.push(sectionLabel('Topics'));
      data.topics.forEach((topic) => next.push({ kind: 'topic', label: topic.label, hint: 'Topic', slug: topic.slug }));
    }
    if (data.sources?.length) {
      groups.push(sectionLabel('Sources'));
      data.sources.forEach((source) => next.push({ kind: 'source', label: source.name, hint: source.domain, id: source.id, initials: (source.name || '?').slice(0, 2).toUpperCase() }));
    }
    groups.push(sectionLabel('Action'));
    next.push({ kind: 'search', label: `Search “${text}”`, hint: 'Full keyword landing', query: text });

    items = next;
    active = 0;
    let index = 0;
    const htmlParts = [];
    let groupIndex = 0;
    const total = items.length;
    // rebuild markup with section headers inline
    const sections = [];
    if (data.headlines?.length) sections.push(['Headlines', items.filter((i) => i.kind === 'headline')]);
    if (data.topics?.length) sections.push(['Topics', items.filter((i) => i.kind === 'topic')]);
    if (data.sources?.length) sections.push(['Sources', items.filter((i) => i.kind === 'source')]);
    sections.push(['Search', items.filter((i) => i.kind === 'search')]);
    for (const [label, group] of sections) {
      htmlParts.push(sectionLabel(label));
      for (const item of group) {
        item.index = index;
        htmlParts.push(itemMarkup(item, index));
        index += 1;
      }
    }
    void total; void groupIndex;
    results.innerHTML = htmlParts.join('');
  } catch (err) {
    results.innerHTML = html`<div class="palette__empty">Search failed: ${err.message}</div>`;
  }
}

function renderDefault() {
  const next = [];
  const parts = [];
  const recents = recent();
  if (recents.length) {
    parts.push(sectionLabel('Recent searches'));
    recents.forEach((value) => next.push({ kind: 'recent', label: value, hint: 'Search again', query: value }));
  }
  parts.push(sectionLabel('Jump to'));
  ACTIONS.forEach((action) => next.push({ kind: 'action', ...action }));
  items = next;
  active = 0;
  parts.push(sectionLabel('Jump to'));
  let index = 0;
  const actionItems = items.filter((item) => item.kind === 'action');
  const recentItems = items.filter((item) => item.kind === 'recent');
  const out = [];
  if (recentItems.length) {
    out.push(sectionLabel('Recent searches'));
    recentItems.forEach((item) => { out.push(itemMarkup(item, index)); index += 1; });
  }
  out.push(sectionLabel('Jump to'));
  actionItems.forEach((item) => { out.push(itemMarkup(item, index)); index += 1; });
  // Ensure indices align with `items` ordering (recent first, actions second).
  items = [...recentItems, ...actionItems];
  results.innerHTML = out.join('');
}

function paintActive() {
  results.querySelectorAll('.palette__item').forEach((node) => {
    node.classList.toggle('is-active', Number(node.dataset.index) === active);
  });
  const node = results.querySelector(`.palette__item[data-index="${active}"]`);
  node?.scrollIntoView({ block: 'nearest' });
}

function move(delta) {
  if (!items.length) return;
  active = (active + delta + items.length) % items.length;
  paintActive();
}

function goSearch() {
  const value = input.value.trim();
  if (!value) return;
  remember(value);
  close();
  navigate(`/keyword?q=${encodeURIComponent(value)}`);
}

function activate(item) {
  if (!item) return;
  if (item.kind === 'headline') { close(); navigate(`/article/${item.id}`); return; }
  if (item.kind === 'topic') { close(); navigate(`/topic/${item.slug}`); return; }
  if (item.kind === 'source') { close(); navigate(`/source/${item.id}`); return; }
  if (item.kind === 'action' && item.id === 'random') {
    close();
    get('/api/random', 5)
      .then((data) => { if (data.id) navigate(`/article/${data.id}`); })
      .catch(() => toast('Could not pick a story just now.'));
    return;
  }
  if (item.kind === 'action') { close(); navigate(item.path); return; }
  if (item.kind === 'recent' || item.kind === 'search') {
    remember(item.query);
    close();
    navigate(`/keyword?q=${encodeURIComponent(item.query)}`);
  }
}

export function open(initial = '') {
  ensureRoot();
  root.hidden = false;
  document.body.classList.add('no-scroll');
  openFlag = true;
  input.value = initial;
  renderDefault();
  if (initial.trim().length >= 2) query(initial);
  requestAnimationFrame(() => input.focus());
}

export function close() {
  if (!root) return;
  root.hidden = true;
  document.body.classList.remove('no-scroll');
  openFlag = false;
  input.value = '';
}

export function toggle() {
  if (openFlag) close(); else open();
}

export function bindShortcuts() {
  document.addEventListener('keydown', (event) => {
    const target = event.target;
    const typing = target instanceof HTMLElement && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      toggle();
      return;
    }
    if (event.key === '/' && !typing && !openFlag) {
      event.preventDefault();
      open();
    }
  });
}

export function mountHomeSearch(node) {
  if (!node) return;
  node.addEventListener('click', (event) => {
    event.preventDefault();
    open();
  });
  node.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      open();
    }
  });
  void state;
  void toast;
}
