import { get, post, patch, del } from '../api.js';
import {
  state, prefs, savePrefs, saveSurvey, record, setProfile, profileInitials,
  levels, streak, dailyProgress, topicLabel, followedTopics, THEMES,
} from '../store.js';
import {
  html, raw, icons, esc, toast, modal, confirmDialog, copyText, timeAgo, absDate,
  errorState, emptyState, compactNumber, number, toastProgress, confetti,
} from '../ui.js';
import { storyCard, rowsHtml, newsRows, sectionHead, emptyState as empty, skeletonFeed, stat, sourceDot } from '../components.js';
import { navigate } from '../router.js';
import { openLegend } from '../legend.js';

// ---------------------------------------------------------------- search
export async function searchView(root, ctx) {
  const q = ctx.query.q || '';
  const sort = ctx.query.sort || 'relevance';
  const topic = ctx.query.topic || '';
  const source = ctx.query.source || '';
  const range = ctx.query.range || '';
  const boot = state.boot || {};
  root.innerHTML = html`
    <h1 class="page-title">Search</h1>
    <p class="page-sub">Every article Pulse has ever fetched — ${compactNumber(boot.archive?.total)} stories${boot.archive?.earliest ? ` back to ${absDate(boot.archive.earliest, false)}` : ''}.</p>

    <form id="search-form" class="section" role="search" style="margin-top:1rem">
      <div class="hstack" style="gap:.5rem;flex-wrap:nowrap">
        <input type="search" id="q" name="q" value="${q}" placeholder="Try “climate”, “NBA”, “student loans”, topic:tech…" autofocus aria-label="Search the archive" style="flex:1">
        <button class="btn btn--primary" type="submit">${raw(icons.search)} Search</button>
      </div>
      <div class="hstack" style="gap:.45rem;margin-top:.6rem">
        <select id="f-topic" aria-label="Topic filter" style="width:auto;min-width:130px">
          <option value="">Any topic</option>
          ${(boot.topics || []).map((t) => html`<option value="${t.slug}" ${topic === t.slug ? 'selected' : ''}>${t.icon} ${t.label}</option>`)}
        </select>
        <select id="f-range" aria-label="Date range" style="width:auto;min-width:130px">
          <option value="">Any time</option>
          <option value="1" ${range === '1' ? 'selected' : ''}>Past 24 hours</option>
          <option value="7" ${range === '7' ? 'selected' : ''}>Past week</option>
          <option value="30" ${range === '30' ? 'selected' : ''}>Past month</option>
          <option value="365" ${range === '365' ? 'selected' : ''}>Past year</option>
        </select>
        <select id="f-sort" aria-label="Sort order" style="width:auto;min-width:130px">
          <option value="relevance" ${sort === 'relevance' ? 'selected' : ''}>Best match</option>
          <option value="newest" ${sort === 'newest' ? 'selected' : ''}>Newest first</option>
        </select>
        <a class="chip" href="/sources" data-link>Browse sources</a>
        <span class="tiny faint" id="search-hint"></span>
      </div>
    </form>

    <div id="suggest-slot" class="section" style="margin-top:.6rem"></div>
    <div id="results" class="section"></div>
    <div id="load-more" class="section"></div>`;

  const form = root.querySelector('#search-form');
  const submit = () => {
    const params = new URLSearchParams();
    const value = root.querySelector('#q').value.trim();
    if (value) params.set('q', value);
    const t = root.querySelector('#f-topic').value;
    const r = root.querySelector('#f-range').value;
    const s = root.querySelector('#f-sort').value;
    if (t) params.set('topic', t);
    if (r) params.set('range', r);
    if (s && s !== 'relevance') params.set('sort', s);
    if (source) params.set('source', source);
    navigate(`/search${params.toString() ? `?${params}` : ''}`);
  };
  form.addEventListener('submit', (event) => { event.preventDefault(); submit(); });
  root.querySelector('#f-topic').addEventListener('change', submit);
  root.querySelector('#f-range').addEventListener('change', submit);
  root.querySelector('#f-sort').addEventListener('change', submit);

  if (!q && !topic && !source) {
    renderSearchHome(root);
    return;
  }
  const since = range ? new Date(Date.now() - Number(range) * 86400000).toISOString() : '';
  await runSearch(root, { q, topic, source, since, sort, offset: 0, append: false });
}

function renderSearchHome(root) {
  const boot = state.boot || {};
  const popular = ['climate', 'NBA', 'artificial intelligence', 'student loans', 'election', 'space', 'mental health', 'World Cup'];
  root.querySelector('#results').innerHTML = html`
    <div class="card card-pad-lg">
      <h2 style="font-size:1rem">Try a topic</h2>
      <div class="hstack" style="margin-top:.6rem">
        ${popular.map((term) => html`<a class="chip" href="/search?q=${encodeURIComponent(term)}" data-link>${term}</a>`)}
      </div>
      <p class="tiny muted" style="margin-top:1rem">Advanced: <code class="mono">source:bbc</code>, <code class="mono">topic:tech</code>, <code class="mono">after:2025-01-01</code>, <code class="mono">-trump</code>.</p>
    </div>
    ${boot.archive ? html`
      <div class="section">${sectionHead('Archive by month')}
        <div class="tile-grid">
          ${(boot.archive.months || []).slice(0, 8).map((m) => html`
            <a class="tile" href="/search?q=&since=${m.month}-01&sort=newest" data-link>
              <span class="tile__icon">🗓️</span><span><span class="tile__label">${monthLabel(m.month)}</span><span class="tile__count">${compactNumber(m.n)} stories</span></span>
            </a>`)}
        </div>
      </div>` : ''}`;
}

function localGreeting() {
  const hour = new Date().getHours();
  const part = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening';
  const name = (state.profile?.name || '').trim();
  const who = name && name !== 'Student' ? `, ${name.split(' ')[0]}` : '';
  return `Good ${part}${who}`;
}

function monthLabel(value) {
  if (!/^\d{4}-\d{2}$/.test(value || '')) return value || '';
  const [year, month] = value.split('-');
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}

function highlight(text) {
  return esc(text || '')
    .replace(/\[\[([\s\S]*?)\]\]/g, '<mark>$1</mark>')
    .replace(/\[\[|\]\]/g, '');
}

async function runSearch(root, { q, topic, source, since, sort, offset, append }) {
  const results = root.querySelector('#results');
  const loadMore = root.querySelector('#load-more');
  if (!append) results.innerHTML = skeletonFeed(4);
  const params = new URLSearchParams({ q: q || '', limit: '24', offset: String(offset), sort });
  if (topic) params.set('topic', topic);
  if (source) params.set('source', source);
  if (since) params.set('since', since);
  try {
    const data = await get(`/api/search?${params}`, 15);
    const hint = root.querySelector('#search-hint');
    if (hint) hint.textContent = `${number(data.total)} result${data.total === 1 ? '' : 's'}`;
    if (!data.results.length) {
      results.innerHTML = empty({
        icon: '🔍',
        title: 'No matches yet',
        text: q ? `Nothing for “${q}” in this archive slice. Try fewer words, another spelling, or a wider date range.` : 'Nothing matched those filters.',
        action: `<a class="btn btn--ghost" href="/search" data-link>Reset search</a>`,
      });
      loadMore.innerHTML = '';
      return;
    }
    const rows = newsRows(data.results, { seed: `search-${offset}` })
      .flatMap((row) => (row.length === 4 ? [row.slice(0, 2), row.slice(2)] : [row]));
    const markup = rows.map((row) => html`
      <div class="news-row row-${row.length}">
        ${row.map((item) => html`
          <article class="card search-hit">
            <div class="hstack" style="gap:.35rem;flex-wrap:wrap">
              <span class="badge badge--topic">${item.topic_label}</span>
              <span class="tiny muted">${item.source_name}</span>
              <span class="tiny faint">·</span>
              <span class="tiny muted">${item.published_relative || ''}${item.date_label === 'First seen' ? ' (first seen)' : ''}</span>
              ${item.paywalled ? html`<span class="tiny faint" title="Subscription">🔒</span>` : ''}
            </div>
            <h3 class="search-hit__title"><a href="/article/${item.id}" data-link>${item.title}</a></h3>
            ${item.snippet ? html`<p class="search-hit__snippet">${raw(highlight(item.snippet))}</p>` : ''}
            <div class="hstack" style="gap:.5rem;margin-top:auto">
              <span class="tiny faint">${item.reading_minutes} min read${item.word_count ? ` · ${item.word_count} words` : ''}</span>
              ${item.story_id ? html`<span class="tiny faint">·</span><a class="tiny muted" style="text-decoration:underline;text-underline-offset:2px" href="/story/${item.story_id}" data-link>${item.story_source_count} outlets</a>` : ''}
            </div>
          </article>`)}
      </div>`).join('');
    if (append) results.insertAdjacentHTML('beforeend', markup);
    else results.innerHTML = markup;
    loadMore.innerHTML = data.has_more
      ? html`<button class="btn btn--ghost btn--block" id="more">Load more results (${number(data.total - offset - data.results.length)} left)</button>`
      : html`<p class="tiny faint" style="text-align:center">End of results. The archive keeps growing — check back after the next refresh.</p>`;
    loadMore.querySelector('#more')?.addEventListener('click', () => {
      runSearch(root, { q, topic, source, since, sort, offset: offset + data.results.length, append: true });
    });
  } catch (err) {
    errorState(results, err.message, () => runSearch(root, { q, topic, source, since, sort, offset, append }));
  }
}

// ----------------------------------------------------------------- saved
export async function savedView(root) {
  root.innerHTML = html`
    <h1 class="page-title">Saved</h1>
    <p class="page-sub">Your reading list, notes and study material.</p>
    <div class="section" id="collections"></div>
    <div id="saved-body">${skeletonFeed(3)}</div>`;
  try {
    const data = await get('/api/saved', 0, true);
    const collections = data.collections || [];
    root.querySelector('#collections').innerHTML = collections.length
      ? html`<div class="chip-row">${collections.map((c) => html`<span class="chip">${c.collection} <b>${c.n}</b></span>`)}</div>`
      : '';
    const body = root.querySelector('#saved-body');
    if (!data.items.length) {
      body.innerHTML = empty({
        icon: '🔖',
        title: 'Nothing saved yet',
        text: 'Tap the bookmark on any story to keep it here. Saved stories are great for exam revision and citations.',
        action: '<a class="btn btn--primary" href="/" data-link>Find something to read</a>',
      });
      return;
    }
    body.innerHTML = html`
      <div class="section">${sectionHead(`${data.items.length} saved stories`)}</div>
      <div class="news-rows">${rowsHtml(data.items, { lead: true, seed: 'saved' })}</div>`;
  } catch (err) {
    errorState(root.querySelector('#saved-body'), err.message, () => savedView(root));
  }
}

// ----------------------------------------------------------------- brief
export async function briefView(root) {
  root.innerHTML = html`
    <h1 class="page-title">Your brief</h1>
    <p class="page-sub">The handful of stories that matter today, in about two minutes.</p>
    <div id="brief-body" class="section">${skeletonFeed(3)}</div>`;
  try {
    const data = await get('/api/brief', 60, true);
    const body = root.querySelector('#brief-body');
    if (!data.stories?.length) {
      body.innerHTML = empty({ icon: '☕', title: 'No brief yet', text: 'Feeds are still filling up. Come back after the next refresh.', action: '<a class="btn btn--primary" href="/" data-link>Go to feed</a>' });
      return;
    }
    body.innerHTML = html`
      <div class="card card-pad-lg" style="background:var(--grad-soft);border-color:var(--line)">
        <div class="between">
          <div>
            <p class="eyebrow">${localGreeting()}</p>
            <h2 style="font-size:1.3rem;letter-spacing:-.02em;margin-top:.2rem">${data.stories.length} stories · ${data.minutes} min</h2>
          </div>
          <button class="btn btn--primary" id="complete-brief">${raw(icons.check)} I'm briefed</button>
        </div>
        <p class="tiny muted" style="margin-top:.5rem">Built from today's coverage, ranked for your interests. Tap a card to read the preview and overview.</p>
      </div>
      <div class="feed" style="margin-top:.9rem">
        ${briefRows(data.stories)}
      </div>`;
    root.querySelector('#complete-brief')?.addEventListener('click', async (event) => {
      event.target.disabled = true;
      try {
        const result = await post('/api/brief/complete', {});
        toastProgress(result.progress);
        toast('Brief complete — nice work', { type: 'good' });
      } catch (err) { toast(err.message, { type: 'bad' }); }
      event.target.textContent = '✓ Done';
    });
  } catch (err) {
    errorState(root.querySelector('#brief-body'), err.message, () => briefView(root));
  }
}

// ----------------------------------------------------------------- study
export async function studyView(root) {
  root.innerHTML = html`
    <h1 class="page-title">Study mode</h1>
    <p class="page-sub">Turn today's news into revision: quick quizzes, a jargon decoder and citation help.</p>
    <div id="study-quiz" class="section">${skeletonFeed(2)}</div>
    <div id="study-jargon" class="section"></div>
    <div id="study-extras" class="section"></div>
    <div class="section">
      ${sectionHead('Citation helper')}
      <div class="card card-pad-lg">
        <p class="small muted">Open any story and tap <b>Cite</b> for a ready-made MLA 9, APA 7, Chicago, Harvard or BibTeX reference — with the publisher's date and your access date filled in. The research desk does the same for every saved story at once.</p>
        <div class="hstack" style="margin-top:.7rem">
          <a class="btn btn--sm btn--primary" href="/research" data-link>Open research desk</a>
          <a class="btn btn--sm btn--ghost" href="/saved" data-link>My saved stories</a>
          <a class="btn btn--sm btn--ghost" href="/search?q=&sort=newest" data-link>Recent stories</a>
        </div>
      </div>
    </div>`;
  loadStudyQuiz(root);
  loadStudyJargon(root);
  loadStudyExtras(root);
}

const SLANG = [
  ['rizz', 'Charm or flirting skill — “he has zero rizz”.'],
  ['sigma', 'A lone-wolf type, usually said ironically.'],
  ['bet', 'Okay / deal / you got it.'],
  ['no cap', 'I am not lying. “Cap” means a lie.'],
  ['bussin', 'Really good, usually about food.'],
  ['mid', 'Average or disappointing.'],
  ['sus', 'Suspicious or sketchy.'],
  ['flex', 'To show off something you have.'],
  ['ghosting', 'Disappearing from a chat without explanation.'],
  ['ick', 'A sudden feeling of cringe about someone.'],
  ['slay', 'Doing something exceptionally well.'],
  ['vibe check', 'Reading the mood of a room or situation.'],
  ['touch grass', 'Go outside; you have been online too long.'],
  ['delulu', 'Delusional, usually about a crush or a plan.'],
  ['glazing', 'Over-the-top flattery.'],
  ['aura', 'The reputation or energy you give off.'],
  ['brainrot', 'Content that melts your attention span.'],
  ['cooked', 'In trouble, or completely exhausted.'],
  ['yap', 'To talk a lot about nothing much.'],
  ['moots', 'Mutuals — people you follow who follow you back.'],
  ['ratio', 'A reply with more likes than the original post.'],
  ['fr', 'For real.'],
  ['lowkey', 'Slightly / quietly / kind of.'],
  ['highkey', 'Openly / very much.'],
  ['GOAT', 'Greatest of all time.'],
  ['main character energy', 'Acting like the story is about you.'],
];

let focusTimer = null;

function loadStudyExtras(root) {
  const slot = root.querySelector('#study-extras');
  if (!slot) return;
  let words = [];
  try { words = JSON.parse(localStorage.getItem('pulse.glossary') || '[]'); } catch { words = []; }
  slot.innerHTML = html`
    ${sectionHead('Focus tools', html`<span class="tiny muted">made for homework nights</span>`)}
    <div class="study-tools">
      <div class="card card-pad">
        <div class="between"><h3 class="extras-card__title">⏱️ Focus timer</h3><span class="tiny faint">25 min</span></div>
        <div class="focus-ring" data-focus-ring style="--p:0"><span data-focus-time>25:00</span></div>
        <div class="hstack" style="margin-top:.7rem">
          <button class="btn btn--sm btn--primary" data-focus-toggle>Start</button>
          <button class="btn btn--sm btn--ghost" data-focus-reset>Reset</button>
        </div>
        <p class="tiny faint" data-focus-note style="margin-top:.5rem">One Pomodoro. Phone face down.</p>
      </div>
      <div class="card card-pad">
        <div class="between"><h3 class="extras-card__title">📚 Your words</h3><span class="tiny faint">${words.length}</span></div>
        ${words.length ? html`
          <div class="word-list">
            ${words.slice(0, 8).map((entry) => html`<div class="word-row"><b>${entry.word}</b><span>${entry.meaning}</span></div>`)}
          </div>` : html`
          <p class="tiny muted">Add words from the <a class="link" href="/" data-link>Today</a> card and they show up here for revision.</p>`}
      </div>
    </div>
    <div class="card card-pad" style="margin-top:.7rem">
      <div class="between"><h3 class="extras-card__title">💬 Slang decoder</h3><span class="tiny faint">${SLANG.length} terms</span></div>
      <input type="search" id="slang-search" placeholder="Type a word or meaning…" style="margin:.5rem 0 .7rem" aria-label="Search slang">
      <div id="slang-list"></div>
    </div>`;

  const timeEl = slot.querySelector('[data-focus-time]');
  const ringEl = slot.querySelector('[data-focus-ring]');
  const toggle = slot.querySelector('[data-focus-toggle]');
  const reset = slot.querySelector('[data-focus-reset]');
  const note = slot.querySelector('[data-focus-note]');
  let remaining = 25 * 60;
  let running = false;
  const paint = () => {
    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;
    timeEl.textContent = `${minutes}:${String(seconds).padStart(2, '0')}`;
    ringEl.style.setProperty('--p', String(Math.round((1 - remaining / 1500) * 100)));
  };
  toggle.addEventListener('click', () => {
    if (running) {
      clearInterval(focusTimer);
      focusTimer = null;
      running = false;
      toggle.textContent = 'Resume';
      note.textContent = 'Paused. Pick it back up when you are ready.';
      return;
    }
    running = true;
    toggle.textContent = 'Pause';
    note.textContent = 'Focus mode. You got this.';
    focusTimer = setInterval(() => {
      if (!document.body.contains(slot)) { clearInterval(focusTimer); return; }
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(focusTimer);
        focusTimer = null;
        running = false;
        remaining = 0;
        paint();
        toggle.textContent = 'Start';
        note.textContent = 'Done. Stretch, drink water, then one more?';
        confetti(60);
        toast('25 minutes done — take a 5-minute break.');
      } else {
        paint();
      }
    }, 1000);
  });
  reset.addEventListener('click', () => {
    clearInterval(focusTimer);
    focusTimer = null;
    running = false;
    remaining = 25 * 60;
    paint();
    toggle.textContent = 'Start';
    note.textContent = 'One Pomodoro. Phone face down.';
  });
  paint();

  const list = slot.querySelector('#slang-list');
  const search = slot.querySelector('#slang-search');
  const paintSlang = (query = '') => {
    const q = query.trim().toLowerCase();
    const found = SLANG.filter(([term, meaning]) => `${term} ${meaning}`.toLowerCase().includes(q));
    list.innerHTML = found.length
      ? html`<div class="slang-list">${found.map(([term, meaning]) => html`<div class="slang-row"><b>${term}</b><span>${meaning}</span></div>`)}</div>`
      : html`<p class="tiny faint">No match. Try another spelling.</p>`;
  };
  search.addEventListener('input', () => paintSlang(search.value));
  paintSlang();
}

function briefCard(item, index) {
  return html`
    <article class="card brief-card" data-article-card="${item.id}">
      <div class="hstack" style="gap:.4rem">
        <span class="badge badge--topic">${index + 1}</span>
        <span class="tiny muted">${item.source?.name || ''}</span>
        <span class="tiny faint">·</span>
        <span class="tiny muted">${item.published_relative}</span>
        ${item.story?.source_count > 1 ? html`<span class="tiny faint">· ${item.story.source_count} outlets</span>` : ''}
      </div>
      <h3 class="brief-card__title"><a href="/article/${item.id}" data-link>${item.title}</a></h3>
      <p class="brief-card__preview">${item.preview || ''}</p>
    </article>`;
}

function briefRows(stories) {
  const rows = [];
  rows.push(html`<div class="news-row row-1">${briefCard(stories[0], 0)}</div>`);
  for (let index = 1; index < stories.length; index += 2) {
    const pair = stories.slice(index, index + 2);
    rows.push(html`<div class="news-row row-${pair.length}">${pair.map((item, offset) => briefCard(item, index + offset))}</div>`);
  }
  return rows;
}

async function loadStudyQuiz(root) {
  const slot = root.querySelector('#study-quiz');
  try {
    const feed = await get('/api/feed?mode=top&limit=10&days=3', 60);
    const items = feed.items || [];
    const quizReady = items.filter((item) => item.has_full_text).slice(0, 4);
    if (!quizReady.length) {
      slot.innerHTML = items.length ? html`
        ${sectionHead('Study with a story')}
        <div class="card card-pad-lg">
          <p class="small muted">Questions appear once a story's full text is available. These are ready to read:</p>
          <div class="row-list" style="margin-top:.6rem">
            ${items.slice(0, 3).map((item) => html`
              <div class="row">
                <div class="row__body">
                  <a class="row__title" href="/article/${item.id}" data-link>${item.title}</a>
                  <div class="row__meta"><span>${item.source?.name}</span><span>·</span><span>${item.reading_minutes} min</span></div>
                </div>
              </div>`)}
          </div>
        </div>` : '';
      return;
    }
    const article = quizReady[0];
    const quiz = await get(`/api/articles/${article.id}/quiz`, 120);
    if (!quiz.questions?.length) { slot.innerHTML = ''; return; }
    slot.innerHTML = html`
      ${sectionHead('Daily quiz', html`<a href="/article/${article.id}" data-link>Read the story ${raw(icons.chevron)}</a>`)}
      <div class="card card-pad-lg">
        <p class="tiny muted" style="margin-bottom:.8rem">Based on “${article.title}” · ${article.source.name}</p>
        ${quiz.questions.slice(0, 3).map((question, qIndex) => html`
          <div class="quiz__q" data-q="${qIndex}" data-article="${article.id}">
            <p>${qIndex + 1}. ${question.question}</p>
            <div class="quiz__options">
              ${question.options.map((option, oIndex) => html`
                <button class="quiz__opt" data-option="${oIndex}" data-answer="${question.answer_index}">
                  <b>${String.fromCharCode(65 + oIndex)}</b><span>${option}</span>
                </button>`)}
            </div>
            <div class="quiz__explain" hidden>${question.explain || ''}</div>
          </div>`)}
      </div>`;
    slot.querySelectorAll('.quiz__opt').forEach((button) => {
      button.addEventListener('click', async () => {
        const group = button.closest('.quiz__q');
        if (group.dataset.answered) return;
        group.dataset.answered = '1';
        const answer = Number(button.dataset.answer);
        const chosen = Number(button.dataset.option);
        const correct = answer === chosen;
        group.querySelectorAll('.quiz__opt').forEach((opt, index) => {
          opt.classList.toggle('is-right', index === answer);
          opt.classList.toggle('is-wrong', index === chosen && !correct);
        });
        group.querySelector('.quiz__explain').hidden = false;
        try {
          const result = await post(`/api/articles/${group.dataset.article}/quiz-result`, { correct, selected: chosen });
          toastProgress(result.progress);
        } catch { /* ignore */ }
      });
    });
  } catch {
    slot.innerHTML = '';
  }
}

async function loadStudyJargon(root) {
  const slot = root.querySelector('#study-jargon');
  try {
    const feed = await get('/api/feed?mode=top&limit=6&days=2', 60);
    const ids = (feed.items || []).slice(0, 3).map((item) => item.id);
    const details = await Promise.all(ids.map((id) => get(`/api/articles/${id}`, 30).catch(() => null)));
    const terms = new Map();
    details.forEach((data) => {
      (data?.article?.jargon || []).forEach((term) => {
        if (!terms.has(term.term)) terms.set(term.term, term.definition);
      });
    });
    const fromCoverage = terms.size > 0;
    if (!terms.size) {
      STARTER_JARGON.forEach(([term, definition]) => terms.set(term, definition));
    }
    const list = [...terms.entries()].slice(0, 10);
    slot.innerHTML = html`
      ${sectionHead('Jargon decoder', fromCoverage ? '<span class="tiny muted">from today’s coverage</span>' : '<span class="tiny muted">the essentials</span>')}
      <div class="grid-2">
        ${list.slice(0, 6).map(([term, definition]) => html`
          <div class="term"><dt>${term}</dt><dd>${definition}</dd></div>`)}
      </div>
      <div class="section">
        ${sectionHead('Flashcards', '<span class="tiny muted">tap a card to flip</span>')}
        <div class="flash-grid">
          ${list.slice(0, 8).map(([term, definition]) => html`
            <div class="flashcard" data-flip tabindex="0" role="button" aria-label="Flashcard: ${term}">
              <div class="flashcard__inner">
                <div class="flashcard__face flashcard__face--front"><b>${term}</b></div>
                <div class="flashcard__face flashcard__face--back">${definition}</div>
              </div>
            </div>`)}
        </div>
      </div>`;
    slot.querySelectorAll('[data-flip]').forEach((card) => {
      const flip = () => card.classList.toggle('is-flipped');
      card.addEventListener('click', flip);
      card.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); flip(); } });
    });
  } catch { slot.innerHTML = ''; }
}

const STARTER_JARGON = [
  ['Inflation', 'The rate at which prices rise. At 3%, something costing $100 last year costs about $103 now.'],
  ['Tariff', 'A tax a country charges on goods imported from another country.'],
  ['Ceasefire', 'An agreement to stop fighting, usually temporary and often monitored by outsiders.'],
  ['Coalition', 'A government formed when several parties team up because no single party won enough seats.'],
  ['Indictment', 'A formal charge saying someone is suspected of a crime and should face trial.'],
  ['Monetary policy', 'Central-bank decisions about interest rates and the money supply.'],
  ['Peer review', 'Experts checking a study before it is published.'],
  ['Net zero', 'Removing as many greenhouse gases as you emit.'],
];

// --------------------------------------------------------------- profile
export async function profileView(root, ctx) {
  const profile = state.profile || {};
  const level = levels();
  const streakInfo = streak();
  const today = dailyProgress();
  const p = prefs();
  const boot = state.boot || {};
  const statsData = await get('/api/profile/stats', 0, true).catch(() => null);
  const stats = statsData?.stats || {};
  const badges = stats.badges || profile.badges || [];
  const weekly = stats.weekly || [];
  const days = [];
  for (let i = 6; i >= 0; i -= 1) {
    const d = new Date(); d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    const found = weekly.find((w) => w.day === key);
    days.push({ key, label: d.toLocaleDateString(undefined, { weekday: 'short' }), count: found?.read_count || 0 });
  }
  const maxDay = Math.max(1, ...days.map((d) => d.count));
  const heat = [];
  for (let i = 27; i >= 0; i -= 1) {
    const d = new Date(); d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    const found = weekly.find((w) => w.day === key);
    heat.push({ key, count: found?.read_count || 0 });
  }
  const heatMax = Math.max(1, ...heat.map((d) => d.count));

  root.innerHTML = html`
    <div class="card card-pad-lg">
      <div class="profile-head">
        <div class="avatar" aria-hidden="true">${profileInitials()}</div>
        <div style="flex:1;min-width:0">
          <div class="hstack" style="gap:.5rem">
            <h1 class="profile-head__name">${profile.name || 'Student'}</h1>
            <button class="btn btn--sm btn--ghost" id="edit-name">Edit</button>
          </div>
          <p class="tiny muted">Level ${level.level} · ${level.title} · ${number(level.xp)} XP</p>
        </div>
        <div class="hstack">
          ${p.show_reading_streak !== false ? html`<span class="pill-progress streak-pill">🔥 ${streakInfo.count} day${streakInfo.count === 1 ? '' : 's'}</span>` : ''}
          <span class="pill-progress">Today ${today.read}/${today.goal}</span>
        </div>
      </div>
      <div class="level-bar">
        <div class="level-bar__labels"><span>${level.progress.into} / ${level.progress.needed} XP to level ${level.level + 1}</span><span>${level.progress.percent}%</span></div>
        <div class="progress"><span style="width:${level.progress.percent}%"></span></div>
      </div>
    </div>

    <div class="section">
      ${sectionHead('This week')}
      <div class="card card-pad-lg">
        <div class="week">
          ${days.map((day) => html`
            <div class="week__day">
              <div class="week__bar">${day.count ? html`<span style="height:${Math.max(6, (day.count / maxDay) * 100)}%"></span>` : ''}</div>
              <span>${day.label}</span>
            </div>`)}
        </div>
      </div>
    </div>

    <div class="section">
      ${sectionHead('Reading heatmap', html`<span class="tiny muted">last 28 days</span>`)}
      <div class="card card-pad">
        <div class="heatmap">
          ${heat.map((day) => html`<span class="heat-cell" style="--v:${(day.count / heatMax).toFixed(2)}" title="${day.key}: ${day.count} stories"></span>`)}
        </div>
        <div class="between" style="margin-top:.45rem">
          <span class="tiny faint">Less</span><span class="tiny faint">More</span>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="stat-grid">
        ${stat(number(stats.reads || 0), 'stories read')}
        ${stat(number(stats.minutes || 0), 'minutes read')}
        ${stat(number(stats.topics || 0), 'topics explored')}
        ${stat(number(stats.sources || 0), 'outlets read')}
      </div>
    </div>

    <div class="section">
      ${sectionHead('Badges')}
      <div class="badge-grid">
        ${badges.map((badge) => html`
          <div class="badge-tile ${badge.earned ? 'is-earned' : ''}" title="${badge.hint}">
            <div class="badge-tile__icon">${badge.icon}</div>
            <div class="badge-tile__label">${badge.label}</div>
          </div>`)}
      </div>
    </div>

    ${stats.topic_breakdown?.length ? html`
      <div class="section">
        ${sectionHead('What you read')}
        <div class="card card-pad">
          ${stats.topic_breakdown.slice(0, 6).map((row) => {
            const max = stats.topic_breakdown[0].count || 1;
            return html`<div style="margin-bottom:.55rem">
              <div class="between" style="font-size:.8rem"><span>${topicLabel(row.topic)}</span><span class="muted">${row.count}</span></div>
              <div class="progress" style="margin-top:.25rem"><span style="width:${Math.round((row.count / max) * 100)}%"></span></div>
            </div>`;
          })}
        </div>
      </div>` : ''}

    <div class="section" id="settings">
      ${sectionHead('Settings')}

      <h3 class="small muted" style="margin:.6rem 0 .4rem">Appearance</h3>
      <div class="settings-group">
        <div class="settings-row" style="display:block">
          <div style="margin-bottom:.6rem"><div class="settings-row__label">Theme</div><div class="settings-row__hint">Ten palettes. Auto follows your device; Mono is pure grayscale; Rose and Ocean are light.</div></div>
          <div class="theme-grid">
            ${THEMES.map((theme) => html`
              <button class="theme-swatch ${p.theme === theme.id ? 'is-on' : ''}" data-pref="theme" data-value="${theme.id}" aria-pressed="${p.theme === theme.id}">
                <span class="theme-swatch__preview" style="background:${theme.bg};--swatch-text:${theme.text};--swatch-grad:${theme.grad}"></span>
                <span class="theme-swatch__label">${theme.label}</span>
              </button>`)}
          </div>
        </div>
        <div class="settings-row">
          <div><div class="settings-row__label">Reading font</div><div class="settings-row__hint">Easy-read uses a dyslexia-friendly stack.</div></div>
          <div class="segmented">
            ${[['sans', 'Sans'], ['serif', 'Serif'], ['dyslexic', 'Easy-read']].map(([id, label]) => html`
              <button data-pref="font" data-value="${id}" class="${p.font === id ? 'is-on' : ''}">${label}</button>`)}
          </div>
        </div>
        <div class="settings-row">
          <div><div class="settings-row__label">Text size</div><div class="settings-row__hint">${['XS', 'S', 'M', 'L', 'XL'][Number(p.text_size) || 1]}</div></div>
          <div class="segmented">
            ${[0, 1, 2, 3, 4].map((size) => html`<button data-pref="text_size" data-value="${size}" class="${Number(p.text_size) === size ? 'is-on' : ''}">${size + 1}</button>`)}
          </div>
        </div>
        <div class="settings-row">
          <div><div class="settings-row__label">Reduce motion</div><div class="settings-row__hint">Turn off animated transitions.</div></div>
          <button class="switch ${p.reduce_motion ? 'is-on' : ''}" data-toggle="reduce_motion" aria-pressed="${p.reduce_motion}"></button>
        </div>
        <div class="settings-row">
          <div><div class="settings-row__label">High contrast</div><div class="settings-row__hint">Stronger text and border contrast.</div></div>
          <button class="switch ${p.high_contrast ? 'is-on' : ''}" data-toggle="high_contrast" aria-pressed="${p.high_contrast}"></button>
        </div>
      </div>

      <h3 class="small muted" style="margin:1rem 0 .4rem">Reading & AI</h3>
      <div class="settings-group">
        <div class="settings-row">
          <div><div class="settings-row__label">Preferred length</div><div class="settings-row__hint">Shapes which stories rank higher.</div></div>
          <div class="segmented">
            ${[['short', 'Short'], ['medium', 'Mixed'], ['long', 'Long']].map(([id, label]) => html`
              <button data-pref="reading_length" data-value="${id}" class="${p.reading_length === id ? 'is-on' : ''}">${label}</button>`)}
          </div>
        </div>
        <div class="settings-row">
          <div><div class="settings-row__label">AI overviews</div><div class="settings-row__hint">${boot.ai?.enabled ? `Connected to ${boot.ai.model}. Summaries are grounded in each article only.` : 'No provider configured — overviews use an extractive summary instead. Set PULSE_AI_BASE_URL to enable.'}</div></div>
          <button class="switch ${p.ai_overview ? 'is-on' : ''}" data-toggle="ai_overview" aria-pressed="${p.ai_overview}"></button>
        </div>
        <div class="settings-row">
          <div><div class="settings-row__label">Hide paywalled stories</div><div class="settings-row__hint">Keep subscription-only links out of your feed.</div></div>
          <button class="switch ${p.hide_paywalled ? 'is-on' : ''}" data-toggle="hide_paywalled" aria-pressed="${p.hide_paywalled}"></button>
        </div>
        <div class="settings-row">
          <div><div class="settings-row__label">Daily goal</div><div class="settings-row__hint">${today.goal} stories a day</div></div>
          <div class="hstack">
            <button class="btn btn--sm btn--ghost" data-goal="-1">−</button>
            <span class="mono">${today.goal}</span>
            <button class="btn btn--sm btn--ghost" data-goal="1">+</button>
          </div>
        </div>
      </div>

      <h3 class="small muted" style="margin:1rem 0 .4rem">Notifications</h3>
      <div class="settings-group">
        <div class="settings-row">
          <div><div class="settings-row__label">Breaking alerts</div><div class="settings-row__hint">In-app banner when a story you follow breaks.</div></div>
          <button class="switch ${p.notify_breaking ? 'is-on' : ''}" data-toggle="notify_breaking" aria-pressed="${p.notify_breaking}"></button>
        </div>
        <div class="settings-row">
          <div><div class="settings-row__label">Interests</div><div class="settings-row__hint">${Object.keys(profile.survey?.topics || {}).length} topics · ${profile.survey?.sources?.length || 0} sources followed</div></div>
          <button class="btn btn--sm btn--ghost" id="edit-interests">Edit</button>
        </div>
      </div>

      <h3 class="small muted" style="margin:1rem 0 .4rem">Data</h3>
      <div class="settings-group">
        <div class="settings-row">
          <div><div class="settings-row__label">Export my data</div><div class="settings-row__hint">Profile, saves, notes and activity as JSON.</div></div>
          <button class="btn btn--sm btn--ghost" id="export">Download</button>
        </div>
        <div class="settings-row">
          <div><div class="settings-row__label">Reset profile</div><div class="settings-row__hint">Deletes your profile, saves and history. The article archive is shared and stays.</div></div>
          <button class="btn btn--sm btn--danger" id="reset">Reset</button>
        </div>
      </div>

      <div class="card card-pad" style="margin-top:1rem">
        <p class="tiny muted">
          Pulse ${boot.app?.version || ''} · ${compactNumber(boot.stats?.articles)} articles · ${boot.catalog?.sources} sources · ${boot.feed_health?.healthy}/${boot.feed_health?.total} feeds healthy<br>
          Server time ${absDate(boot.app?.server_time)}. Scores by ESPN. Headlines belong to their publishers.
        </p>
        <div class="hstack" style="margin-top:.7rem">
          <button class="btn btn--sm btn--ghost" id="open-legend">Key to symbols</button>
          <a class="btn btn--sm btn--ghost" href="/research" data-link>Research desk</a>
        </div>
      </div>
    </div>`;

  bindProfile(root, p, today, profile);
  if (ctx?.query?.focus === 'settings') {
    setTimeout(() => root.querySelector('#settings')?.scrollIntoView({ behavior: 'smooth' }), 60);
  }
}

function bindProfile(root, p, today, profile) {
  root.querySelectorAll('[data-pref]').forEach((button) => {
    button.addEventListener('click', async () => {
      const key = button.dataset.pref;
      const rawValue = button.dataset.value;
      const value = key === 'text_size' ? Number(rawValue) : rawValue;
      try {
        await savePrefs({ [key]: value });
        button.parentElement.querySelectorAll('button').forEach((b) => b.classList.toggle('is-on', b === button));
      } catch (err) { toast(err.message, { type: 'bad' }); }
    });
  });
  root.querySelectorAll('[data-toggle]').forEach((button) => {
    button.addEventListener('click', async () => {
      const key = button.dataset.toggle;
      const value = !(p[key]);
      button.classList.toggle('is-on', value);
      button.setAttribute('aria-pressed', String(value));
      p[key] = value;
      try { await savePrefs({ [key]: value }); } catch (err) { toast(err.message, { type: 'bad' }); }
    });
  });
  root.querySelectorAll('[data-goal]').forEach((button) => {
    button.addEventListener('click', async () => {
      const next = Math.max(1, Math.min(30, Number(today.goal) + Number(button.dataset.goal)));
      try {
        await savePrefs({ daily_goal: next });
        toast(`Daily goal: ${next} stories`);
        profileView(root, {});
      } catch (err) { toast(err.message, { type: 'bad' }); }
    });
  });
  root.querySelector('#edit-name')?.addEventListener('click', () => {
    const input = document.createElement('input');
    input.type = 'text';
    input.value = profile.name || '';
    input.maxLength = 40;
    const { close } = modal({
      title: 'Your name',
      body: input,
      actions: [
        { label: 'Cancel', class: 'btn--ghost' },
        {
          label: 'Save',
          class: 'btn--primary',
          onClick: async () => {
            try {
              const result = await patch('/api/profile', { name: input.value.trim() || 'Student' });
              setProfile(result.profile);
              navigate('/profile');
            } catch (err) { toast(err.message, { type: 'bad' }); return false; }
            return true;
          },
        },
      ],
    });
    void close;
  });
  root.querySelector('#edit-interests')?.addEventListener('click', () => navigate('/onboarding?edit=1'));
  root.querySelector('#open-legend')?.addEventListener('click', () => openLegend());
  root.querySelector('#export')?.addEventListener('click', async () => {
    try {
      const data = await get('/api/profile/export', 0, true);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `pulse-export-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      toast('Export downloaded', { type: 'good' });
    } catch (err) { toast(err.message, { type: 'bad' }); }
  });
  root.querySelector('#reset')?.addEventListener('click', async () => {
    const ok = await confirmDialog('This deletes your profile, saves, notes and reading history. The shared article archive is not affected.', { title: 'Reset your profile?', confirmLabel: 'Reset', danger: true });
    if (!ok) return;
    try {
      const result = await post('/api/profile/reset', {});
      setProfile(result.profile);
      toast('Profile reset');
      navigate('/onboarding', { replace: true });
    } catch (err) { toast(err.message, { type: 'bad' }); }
  });
}

// ------------------------------------------------------------- onboarding
const ONBOARD_STEPS = ['welcome', 'grade', 'topics', 'sources', 'reading', 'extras'];
const DRAFT_KEY = 'pulse.onboarding';

export async function onboardingView(root, ctx) {
  const editing = ctx.query.edit === '1';
  const boot = state.boot || {};
  const existing = state.profile?.survey || {};
  let draft = {
    name: state.profile?.name || '',
    topics: { ...(existing.topics || {}) },
    sources: [...(existing.sources || [])],
    grade: existing.grade || '',
    goals: [...(existing.goals || [])],
    reading_length: existing.reading_length || prefs().reading_length || 'medium',
    region: existing.region || '',
    keywords: [...(existing.keywords || [])],
  };
  try {
    const saved = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || 'null');
    if (saved && !editing) draft = { ...draft, ...saved };
  } catch { /* ignore */ }
  let step = editing ? 2 : 0;
  const persist = () => {
    try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft)); } catch { /* ignore */ }
  };

  const selectedTopicCount = () => Object.values(draft.topics).filter((v) => Number(v) > 0).length;
  const renderStep = () => {
    const key = ONBOARD_STEPS[step];
    const selectedTopics = selectedTopicCount();
    root.innerHTML = html`
      <div class="onboarding">
        <div class="onboarding__top">
          <a class="brand" href="/" data-link><span class="brand__pulse"><span></span><span></span><span></span><span></span></span><span class="brand__name">Pulse</span></a>
          <div class="onboarding__dots" aria-label="Step ${step + 1} of ${ONBOARD_STEPS.length}">
            ${ONBOARD_STEPS.map((_, index) => html`<span class="onboarding__dot ${index <= step ? 'is-on' : ''}"></span>`)}
          </div>
          ${editing ? html`<button class="btn btn--sm btn--ghost" id="cancel-edit">Cancel</button>` : html`<span class="tiny faint">${step + 1}/${ONBOARD_STEPS.length}</span>`}
        </div>
        <div id="step-body"></div>
        <div class="onboarding__foot">
          <button class="btn btn--ghost" id="back" ${step === 0 && !editing ? 'disabled' : ''}>Back</button>
          <div class="hstack">
            ${key === 'sources' ? html`<button class="btn btn--ghost" id="skip">Skip this step</button>` : ''}
            ${!editing && step < ONBOARD_STEPS.length - 1 ? html`<button class="btn btn--ghost" id="skip-setup" title="Start with a general feed — you can personalise later">Skip setup</button>` : ''}
            <button class="btn btn--primary" id="next">${step === ONBOARD_STEPS.length - 1 ? 'Finish and build my feed' : 'Continue'}</button>
          </div>
        </div>
      </div>`;

    const body = root.querySelector('#step-body');
    body.innerHTML = stepMarkup(key, draft, boot, selectedTopics, editing);
    bindStep(key, body, draft, persist);

    root.querySelector('#back').addEventListener('click', () => {
      if (step === 0) return;
      step -= 1;
      renderStep();
    });
    root.querySelector('#skip')?.addEventListener('click', () => { step += 1; renderStep(); });
    const skipAll = () => finish({ skipped: true });
    root.querySelector('#skip-setup')?.addEventListener('click', skipAll);
    root.querySelector('#skip-welcome')?.addEventListener('click', skipAll);
    root.querySelector('#cancel-edit')?.addEventListener('click', () => navigate('/profile'));
    root.querySelector('#next').addEventListener('click', async () => {
      if (key === 'topics' && selectedTopicCount() < 3 && !editing) {
        toast('Pick at least 3 topics so the feed has something to work with', { type: 'bad' });
        return;
      }
      if (key === 'welcome') {
        draft.name = body.querySelector('#name')?.value.trim().slice(0, 40) || 'Student';
      }
      persist();
      if (step < ONBOARD_STEPS.length - 1) {
        step += 1;
        renderStep();
        return;
      }
      await finish();
    });
  };

  const finish = async ({ skipped = false } = {}) => {
    const buttons = root.querySelectorAll('button');
    buttons.forEach((button) => { button.disabled = true; });
    const primary = root.querySelector('#next');
    if (primary) primary.textContent = 'Building your feed…';
    // Sensible starting weights when someone skips: a broad front page rather
    // than an empty one. The ranker refines this from what they read.
    const fallbackTopics = { world: 2, tech: 2, sports: 2, science: 1, culture: 1 };
    const topics = Object.keys(draft.topics).length ? draft.topics : fallbackTopics;
    const survey = {
      topics,
      sources: draft.sources,
      keywords: draft.keywords,
      grade: draft.grade,
      goals: draft.goals,
      reading_length: draft.reading_length || 'medium',
      region: draft.region,
      daily_goal: prefs().daily_goal || 5,
      experience: 'some',
      completed_at: new Date().toISOString(),
      skipped,
    };
    try {
      await saveSurvey(survey, { onboarded: true, name: draft.name || 'Student' });
      await savePrefs({ reading_length: survey.reading_length });
      try { sessionStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
      toast(skipped ? 'Starting with a general feed — personalise any time in Profile' : 'Your feed is ready', { type: 'good' });
      navigate('/', { replace: true });
    } catch (err) {
      toast(err.message, { type: 'bad' });
      buttons.forEach((button) => { button.disabled = false; });
      if (primary) primary.textContent = 'Finish and build my feed';
    }
  };

  renderStep();
}

function stepMarkup(key, draft, boot, selectedTopics, editing = false) {
  if (key === 'welcome') {
    return html`
      <h1>News that keeps up<br>with you.</h1>
      <p class="onboarding__sub">${boot.catalog?.sources || 300} sources, live scores, AI overviews and a permanent archive. Two minutes of setup and the feed is yours.</p>
      <div class="onboarding__body">
        <label class="tiny muted" for="name" style="display:block;margin-bottom:.35rem">What should we call you?</label>
        <input id="name" type="text" maxlength="40" placeholder="First name or nickname" value="${draft.name}" autocomplete="given-name">
        <div class="grid-3" style="margin-top:1.2rem">
          <div class="card card-pad"><div style="font-size:1.3rem">🗞️</div><b class="small">300+ sources</b><p class="tiny muted">Every major outlet, all topics.</p></div>
          <div class="card card-pad"><div style="font-size:1.3rem">✨</div><b class="small">Overviews</b><p class="tiny muted">Know the story before you commit.</p></div>
          <div class="card card-pad"><div style="font-size:1.3rem">🏆</div><b class="small">Live scores</b><p class="tiny muted">NBA, NFL, football and more.</p></div>
        </div>
        <p class="tiny faint" style="margin-top:1rem">Everything stays on your device. No ads, no tracking, no account required.</p>
        ${!editing ? html`<p class="small muted" style="margin-top:.9rem">In a hurry? <button class="link" id="skip-welcome" style="background:none;border:0;font:inherit">Skip the survey</button> and start with a general feed — you can personalise it any time from Profile.</p>` : ''}
      </div>`;
  }
  if (key === 'grade') {
    return html`
      <h1>What are you studying?</h1>
      <p class="onboarding__sub">We use this to tune reading level and suggest study features. It never changes which facts you see.</p>
      <div class="onboarding__body">
        <div class="choice-grid">
          ${[['middle', 'Middle school', 'Ages 11–14'], ['9', 'Grade 9', ''], ['10', 'Grade 10', ''], ['11', 'Grade 11', ''], ['12', 'Grade 12', ''], ['uni', 'University', ''], ['other', 'Something else', '']].map(([id, label, sub]) => html`
            <button class="choice ${draft.grade === id ? 'is-on' : ''}" data-grade="${id}">
              <span class="choice__icon">🎓</span><span>${label}${sub ? html`<span class="choice__sub">${sub}</span>` : ''}</span>
            </button>`)}
        </div>
      </div>`;
  }
  if (key === 'topics') {
    return html`
      <h1>What do you actually care about?</h1>
      <p class="onboarding__sub">Pick at least 3. Tap twice for “love it” — that doubles its weight in your feed. You can change this any time.</p>
      <div class="onboarding__body">
        <div class="choice-grid">
          ${(boot.topics || []).map((topic) => {
            const level = Number(draft.topics[topic.slug] || 0);
            return html`
              <button class="choice ${level ? 'is-on' : ''}" data-topic="${topic.slug}" aria-pressed="${level > 0}">
                <span class="choice__icon">${topic.icon}</span>
                <span>${topic.label}<span class="choice__sub">${level === 0 ? 'tap to add' : level === 1 ? 'interested' : 'love it'}</span></span>
              </button>`;
          })}
        </div>
        <p class="small muted" style="margin-top:.8rem">${selectedTopics} selected${selectedTopics < 3 ? ' · add a couple more' : ' ✓'}</p>
      </div>`;
  }
  if (key === 'sources') {
    const all = (boot.sources || []).slice();
    const preferred = all.filter((s) => s.teen_friendly || s.country === 'US' || s.country === 'GB').slice(0, 42);
    return html`
      <h1>Any outlets you trust?</h1>
      <p class="onboarding__sub">Optional. Follow a few to boost them — or skip and let the ranking learn from what you read.</p>
      <div class="onboarding__body">
        <div class="choice-grid">
          ${preferred.map((source) => html`
            <button class="choice ${draft.sources.includes(source.id) ? 'is-on' : ''}" data-source="${source.id}" aria-pressed="${draft.sources.includes(source.id)}">
              <span class="choice__icon" aria-hidden="true">${(source.initials || '?')}</span>
              <span style="min-width:0">${source.name}<span class="choice__sub">${source.domain} · ${source.country}</span></span>
            </button>`)}
        </div>
        <p class="tiny faint" style="margin-top:.8rem">${draft.sources.length} followed. ${boot.sources?.length ? `${boot.sources.length} total in the directory.` : ''}</p>
      </div>`;
  }
  if (key === 'reading') {
    return html`
      <h1>How do you like to read?</h1>
      <p class="onboarding__sub">This sets your default reading length and daily goal. The feed mixes formats so you're not stuck in one lane.</p>
      <div class="onboarding__body">
        <div class="choice-grid">
          ${[['short', 'Quick hits', 'under 4 minutes'], ['medium', 'A mix', '4–8 minutes'], ['long', 'Deep dives', '8+ minutes']].map(([id, label, sub]) => html`
            <button class="choice ${draft.reading_length === id ? 'is-on' : ''}" data-reading="${id}">
              <span class="choice__icon">${id === 'short' ? '⚡' : id === 'medium' ? '⚖️' : '📖'}</span><span>${label}<span class="choice__sub">${sub}</span></span>
            </button>`)}
        </div>
        <p class="tiny muted" style="margin:1.2rem 0 .4rem">What are you using the news for?</p>
        <div class="choice-grid">
          ${['exam prep', 'current events class', 'writing & debate', 'college apps', 'general knowledge', 'science & tech', 'sports', 'culture'].map((goal) => html`
            <button class="choice ${draft.goals.includes(goal) ? 'is-on' : ''}" data-goal="${goal}">
              <span class="choice__icon">${goal === 'exam prep' ? '📝' : goal === 'writing & debate' ? '🗣️' : goal === 'college apps' ? '🎓' : goal === 'sports' ? '🏀' : goal === 'culture' ? '🎬' : '✨'}</span>
              <span>${goal}</span>
            </button>`)}
        </div>
      </div>`;
  }
  return html`
    <h1>Last bits.</h1>
    <p class="onboarding__sub">Where you are helps us surface local and regional coverage. Notifications are in-app only.</p>
    <div class="onboarding__body">
      <label class="tiny muted" for="region" style="display:block;margin-bottom:.35rem">Your region</label>
      <select id="region">
        <option value="">Prefer not to say</option>
        ${['US', 'GB', 'CA', 'AU', 'NZ', 'IE', 'IN', 'PK', 'NG', 'ZA', 'KE', 'SG', 'PH', 'JP', 'KR', 'DE', 'FR', 'ES', 'IT', 'NL', 'BR', 'MX', 'AR'].map((code) => html`
          <option value="${code}" ${draft.region === code ? 'selected' : ''}>${code}</option>`)}
      </select>
      <p class="tiny muted" style="margin:1.2rem 0 .4rem">Keywords you want to track (optional)</p>
      <input id="keywords" type="text" placeholder="e.g. climate policy, basketball, film" value="${draft.keywords.join(', ')}">
      <div class="settings-group" style="margin-top:1.2rem">
        <div class="settings-row">
          <div><div class="settings-row__label">Breaking news alerts</div><div class="settings-row__hint">A subtle in-app banner when something big breaks.</div></div>
          <button class="switch is-on" data-extra-toggle="notify_breaking" aria-pressed="true"></button>
        </div>
        <div class="settings-row">
          <div><div class="settings-row__label">AI overviews</div><div class="settings-row__hint">${boot.ai?.enabled ? 'On — summaries use the provider you configured.' : 'Off on this server. You still get extractive summaries.'}</div></div>
          <button class="switch ${boot.ai?.enabled ? 'is-on' : ''}" data-extra-toggle="ai_overview" aria-pressed="${boot.ai?.enabled ? 'true' : 'false'}"></button>
        </div>
      </div>
      <p class="tiny faint" style="margin-top:1rem">You can export or delete everything from your profile at any time.</p>
    </div>`;
}

function bindStep(key, body, draft, persist) {
  if (key === 'welcome') {
    body.querySelector('#name')?.addEventListener('input', (event) => { draft.name = event.target.value; persist(); });
  }
  if (key === 'grade') {
    body.querySelectorAll('[data-grade]').forEach((button) => {
      button.addEventListener('click', () => {
        draft.grade = button.dataset.grade;
        body.querySelectorAll('[data-grade]').forEach((b) => b.classList.toggle('is-on', b === button));
        persist();
      });
    });
  }
  if (key === 'topics') {
    body.querySelectorAll('[data-topic]').forEach((button) => {
      button.addEventListener('click', () => {
        const slug = button.dataset.topic;
        const next = (Number(draft.topics[slug] || 0) + 1) % 3;
        if (next === 0) delete draft.topics[slug]; else draft.topics[slug] = next;
        button.classList.toggle('is-on', next > 0);
        button.setAttribute('aria-pressed', String(next > 0));
        button.querySelector('.choice__sub').textContent = next === 0 ? 'tap to add' : next === 1 ? 'interested' : 'love it';
        const count = Object.values(draft.topics).filter((v) => Number(v) > 0).length;
        const label = body.querySelector('.small.muted');
        if (label) label.textContent = `${count} selected${count < 3 ? ' · add a couple more' : ' ✓'}`;
        persist();
      });
    });
  }
  if (key === 'sources') {
    body.querySelectorAll('[data-source]').forEach((button) => {
      button.addEventListener('click', () => {
        const id = button.dataset.source;
        const index = draft.sources.indexOf(id);
        if (index >= 0) draft.sources.splice(index, 1); else draft.sources.push(id);
        button.classList.toggle('is-on', index < 0);
        button.setAttribute('aria-pressed', String(index < 0));
        const note = body.querySelector('.tiny.faint');
        if (note) note.textContent = `${draft.sources.length} followed.`;
        persist();
      });
    });
  }
  if (key === 'reading') {
    body.querySelectorAll('[data-reading]').forEach((button) => {
      button.addEventListener('click', () => {
        draft.reading_length = button.dataset.reading;
        body.querySelectorAll('[data-reading]').forEach((b) => b.classList.toggle('is-on', b === button));
        persist();
      });
    });
    body.querySelectorAll('[data-goal]').forEach((button) => {
      button.addEventListener('click', () => {
        const goal = button.dataset.goal;
        const index = draft.goals.indexOf(goal);
        if (index >= 0) draft.goals.splice(index, 1); else draft.goals.push(goal);
        button.classList.toggle('is-on', index < 0);
        persist();
      });
    });
  }
  if (key === 'extras') {
    body.querySelector('#region')?.addEventListener('change', (event) => { draft.region = event.target.value; persist(); });
    body.querySelector('#keywords')?.addEventListener('input', (event) => {
      draft.keywords = event.target.value.split(',').map((k) => k.trim()).filter(Boolean).slice(0, 12);
      persist();
    });
    body.querySelectorAll('[data-extra-toggle]').forEach((button) => {
      button.addEventListener('click', () => {
        const on = !button.classList.contains('is-on');
        button.classList.toggle('is-on', on);
        button.setAttribute('aria-pressed', String(on));
        savePrefs({ [button.dataset.extraToggle]: on }).catch(() => {});
      });
    });
  }
}

export function viewNotFound(root, path) {
  root.innerHTML = empty({
    icon: '🧭',
    title: 'Page not found',
    text: `There is nothing at ${path}. Try the feed, discover or search.`,
    action: '<a class="btn btn--primary" href="/" data-link>Back to feed</a>',
  });
}
