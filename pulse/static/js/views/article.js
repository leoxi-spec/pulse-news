import { get, post, del } from '../api.js';
import { state, record, emit, savePrefs, prefs, toggleSave } from '../store.js';
import {
  html, raw, icons, esc, toast, modal, timeAgo, absDate, copyText, confirmDialog, confetti,
  errorState, toastProgress, setLoading,
} from '../ui.js';
import { sourceDot, leanBar, emptyState, accessInfo } from '../components.js';

const FONTS = [
  { id: 'serif', label: 'Serif' },
  { id: 'sans', label: 'Sans' },
  { id: 'dyslexic', label: 'Easy-read' },
];

export async function articleView(root, ctx) {
  const id = Number(ctx.params.id);
  if (!Number.isFinite(id)) {
    root.innerHTML = emptyState({ icon: '🔍', title: 'Bad article link', text: 'That article id is not valid.' });
    return;
  }
  root.innerHTML = html`
    <div class="article">
      <div class="skeleton skeleton--line" style="width:30%;margin-bottom:1rem"></div>
      <div class="skeleton" style="height:2.6rem;width:92%;margin-bottom:.7rem"></div>
      <div class="skeleton" style="height:2.6rem;width:70%;margin-bottom:1.4rem"></div>
      <div class="skeleton" style="height:280px;border-radius:16px;margin-bottom:1.4rem"></div>
      ${Array.from({ length: 6 }).map(() => html`<div class="skeleton skeleton--line" style="margin-bottom:.7rem"></div>`)}
    </div>`;

  let article;
  try {
    const data = await get(`/api/articles/${id}`, 30);
    article = data.article;
  } catch (err) {
    if (err.status === 404) {
      root.innerHTML = emptyState({
        icon: '🗞️',
        title: 'Article not found',
        text: 'It may have been removed from the archive, or the link is wrong.',
        action: '<a class="btn btn--primary" href="/" data-link>Back to feed</a>',
      });
    } else {
      errorState(root, err.message, () => articleView(root, ctx));
    }
    return;
  }

  const p = prefs();
  root.innerHTML = articleMarkup(article, p);
  bindArticle(root, article);
  renderStoryExtras(root, article);
  trackReading(article);
  loadOverview(root, article);
  if (article.notes?.length) renderNotes(root, article);
}

function articleMarkup(a, p) {
  const source = a.source || {};
  const blocks = a.blocks || [];
  const hasBody = blocks.length > 0;
  const dateLabel = a.date_label === 'First seen' ? 'First seen' : 'Published';
  const dateRel = a.published_relative || timeAgo(a.published_at || a.first_seen_at);

  return html`
    <div id="read-progress" style="position:fixed;top:0;left:0;height:3px;width:0;background:var(--grad);z-index:70;transition:width .1s linear"></div>
    <article class="article" data-article-id="${a.id}">
      <a class="article__back" href="javascript:history.back()">${raw(icons.chevron)} Back</a>
      <div class="article__kicker">
        <span class="badge badge--topic">${a.topic_label}</span>
        ${a.breaking ? html`<span class="badge badge--breaking">Breaking</span>` : ''}
        ${a.story?.source_count > 1 ? html`<span class="badge badge--topic">${a.story.source_count} outlets covering</span>` : ''}
      </div>

      <h1 class="article__title">${a.title}</h1>
      ${a.summary && a.summary !== a.title ? html`<p class="article__dek">${a.summary}</p>` : ''}

      <div class="article__byline">
        ${sourceDot(source)}
        <span><strong>${source.name}</strong></span>
        <span class="faint">·</span>
        <span title="${absDate(a.published_at || a.first_seen_at)}">${dateLabel} ${dateRel}</span>
        ${a.author ? html`<span class="faint">·</span><span>By ${a.author}</span>` : ''}
        <span class="faint">·</span>
        <span>${a.reading_minutes} min read</span>
        ${a.date_confidence === 'day' || a.date_confidence === 'inferred' ? html`<span class="faint" title="The publisher only provided a date, so the time of day is unknown">· date-only</span>` : ''}
      </div>

      ${renderAccessBanner(a)}
      <div class="story-facts" id="story-facts"></div>

      <div class="article__actions" role="toolbar" aria-label="Story actions">
        ${renderSaveButton(a)}
        <button class="btn" data-act="share">${raw(icons.share)} Share</button>
        <button class="btn" data-act="cite">${raw(icons.quote)} Cite</button>
        <button class="btn" data-act="quiz">${raw(icons.bolt)} Quiz</button>
        <button class="btn" data-act="notes">${raw(icons.note)} Notes</button>
        <button class="btn" data-act="listen" aria-pressed="false" title="Read this story aloud">${raw(icons.sound)} Listen</button>
        <span class="spacer"></span>
        <button class="btn" data-act="focus" title="Distraction-free reading">${raw(icons.eye)} Focus</button>
        <button class="btn" data-act="font" title="Reading font">${raw(icons.text)}</button>
        <a class="btn article__source-btn" href="${a.read_url}" target="_blank" rel="noopener noreferrer" title="Open at ${source.name}">${raw(icons.external)} Source</a>
      </div>
      <div class="reaction-bar" id="reaction-bar" aria-label="React to this story"></div>

      ${a.image ? html`<figure class="article__hero"><img src="${a.image}" alt="" fetchpriority="high" decoding="async"></figure>` : ''}

      <div id="overview-slot">
        <div class="overview">
          <div class="overview__head">
            <h2>${raw(icons.sparkle)} Overview</h2>
            <span class="badge badge--ai">Building…</span>
          </div>
          <div class="overview__body"><div class="skeleton skeleton--line" style="width:80%;margin-bottom:.5rem"></div><div class="skeleton skeleton--line" style="width:60%"></div></div>
        </div>
      </div>

      <div class="prose" id="prose" data-font="${document.body.classList.contains('font-serif') ? 'serif' : ''}">${renderBlocks(a, blocks)}</div>

      <div id="extras-slot"></div>

      ${!hasBody ? renderNoBody(a) : ''}

      <div class="article__foot">
        <div class="hstack" style="justify-content:space-between">
          <div class="hstack" style="gap:.5rem">
            <span class="tiny muted">From ${source.name}</span>
            <span class="tiny faint">·</span>
            <span class="tiny muted">${a.archive ? 'In your permanent archive' : ''}</span>
          </div>
          <a class="btn btn--sm btn--ghost" href="${a.read_url}" target="_blank" rel="noopener noreferrer">Read the original ${raw(icons.external)}</a>
        </div>
        <p class="tiny faint" style="margin-top:.8rem">
          Pulse stores a preview and summary for reading and search. Full rights stay with ${source.name}.
          ${a.source_about ? esc(a.source_about) : ''}
        </p>
      </div>

      <div id="notes-slot"></div>
      <div id="coverage-slot">${renderCoverage(a)}</div>
      <div id="quiz-slot"></div>
      <div id="related-slot">${renderRelated(a)}</div>
    </article>`;
}

function renderAccessBanner(a) {
  const access = accessInfo(a);
  if (access.kind === 'full') {
    return html`
      <div class="reader-banner reader-banner--full">
        <span class="reader-banner__icon" aria-hidden="true">${access.icon}</span>
        <div><b>Full story available here</b><span>You can read the complete article inside Pulse — no need to leave the app.</span></div>
        ${a.read_url ? html`<a class="btn btn--sm btn--ghost" href="${a.read_url}" target="_blank" rel="noopener noreferrer">Original ${raw(icons.external)}</a>` : ''}
      </div>`;
  }
  if (access.kind === 'locked') {
    return html`
      <div class="reader-banner reader-banner--locked">
        <span class="reader-banner__icon" aria-hidden="true">${access.icon}</span>
        <div><b>Subscription required at ${a.source.name}</b><span>This is the publisher's preview. Pulse shows you the overview, coverage and full metadata, then links to the source.</span></div>
        <a class="btn btn--sm btn--primary" href="${a.read_url}" target="_blank" rel="noopener noreferrer">Read at source ${raw(icons.external)}</a>
      </div>`;
  }
  return html`
    <div class="reader-banner reader-banner--preview">
      <span class="reader-banner__icon" aria-hidden="true">${access.icon}</span>
      <div><b>Preview only</b><span>Pulse has the summary and overview. The full article is at ${a.source.name}.</span></div>
      <a class="btn btn--sm btn--primary" href="${a.read_url}" target="_blank" rel="noopener noreferrer">Read at source ${raw(icons.external)}</a>
    </div>`;
}

function renderSaveButton(a) {
  return html`<button class="btn ${a.saved_collection ? 'is-on' : ''}" data-act="save" aria-pressed="${a.saved_collection ? 'true' : 'false'}">
    ${raw(icons.bookmark)} <span data-save-label>${a.saved_collection ? 'Saved' : 'Save'}</span>
  </button>`;
}

function renderBlocks(a, blocks) {
  if (!blocks.length) return '';
  return raw(blocks.map((block, index) => {
    const text = esc(block.text);
    if (block.type === 'h2' || block.type === 'h3' || block.type === 'h4') {
      const tag = block.type === 'h4' ? 'h3' : block.type;
      return `<${tag} id="block-${index}">${text}</${tag}>`;
    }
    if (block.type === 'li') return `<li id="block-${index}">${text}</li>`;
    if (block.type === 'blockquote') return `<blockquote id="block-${index}">${text}</blockquote>`;
    if (block.type === 'p') return `<p id="block-${index}">${text}</p>`;
    return '';
  }).join(''));
}

function renderNoBody(a) {
  if (a.paywalled) {
    return html`
      <div class="paywall">
        <h3>🔒 The full story is at ${a.source.name}</h3>
        <p>This outlet requires a subscription for the full text. Pulse can still show you the preview, the overview, related coverage and the archive metadata — and you can open the original any time.</p>
        <a class="btn btn--primary" href="${a.read_url}" target="_blank" rel="noopener noreferrer">Continue at ${a.source.name} ${raw(icons.external)}</a>
      </div>`;
  }
  return html`
    <div class="paywall">
      <h3>📄 Preview available</h3>
      <p>Pulse could not extract the full text from ${a.source.name}'s page, so this is the publisher's own summary. The original is one tap away.</p>
      <a class="btn btn--primary" href="${a.read_url}" target="_blank" rel="noopener noreferrer">Read at ${a.source.name} ${raw(icons.external)}</a>
    </div>`;
}

function renderCoverage(a) {
  const coverage = a.coverage || {};
  const others = (coverage.articles || []).filter(Boolean);
  if (!others.length) return '';
  const leans = coverage.leans || {};
  return html`
    <section class="coverage">
      <div class="section-head" style="margin-top:0">
        <h2>How other outlets covered it</h2>
        <span class="tiny muted">${coverage.sources} source${coverage.sources === 1 ? '' : 's'}</span>
      </div>
      ${leanBar(leans)}
      <p class="tiny faint" style="margin-top:-.4rem;margin-bottom:.8rem">${coverage.note || ''}</p>
      <div class="row-list">
        ${others.slice(0, 8).map((item) => html`
          <div class="row">
            <div class="row__body">
              <a class="row__title" href="/article/${item.id}" data-link>${item.title}</a>
              <div class="row__meta">
                <span>${item.source}</span>
                <span aria-hidden="true">·</span>
                <span>${item.published_relative}</span>
                <span aria-hidden="true">·</span>
                <span>${item.lean}</span>
                ${item.paywall ? html`<span title="Paywalled">🔒</span>` : ''}
              </div>
            </div>
          </div>`)}
      </div>
    </section>`;
}

function renderRelated(a) {
  const related = a.related || [];
  if (!related.length) return '';
  return html`
    <section class="related section">
      <div class="section-head" style="margin-top:0"><h2>Keep reading</h2></div>
      <div class="row-list">
        ${related.map((item) => html`
          <div class="row">
            ${item.image ? html`<img class="row__img" src="${item.image}" alt="" loading="lazy" decoding="async">` : ''}
            <div class="row__body">
              <a class="row__title" href="/article/${item.id}" data-link>${item.title}</a>
              <div class="row__meta"><span>${item.source}</span><span aria-hidden="true">·</span><span>${item.published_relative}</span><span aria-hidden="true">·</span><span>${item.reading_minutes} min</span></div>
            </div>
          </div>`)}
      </div>
    </section>`;
}

function renderNotes(root, article, notes = null) {
  const list = notes || article.notes || [];
  const slot = root.querySelector('#notes-slot');
  if (!slot) return;
  if (!list.length) { slot.innerHTML = ''; return; }
  slot.innerHTML = html`
    <section class="section">
      <div class="section-head" style="margin-top:0"><h2>Your notes</h2><span class="tiny muted">${list.length}</span></div>
      ${list.map((note) => html`
        <div class="note" data-note="${note.id}">
          ${note.quote ? html`<div class="note__quote">“${note.quote}”</div>` : ''}
          <div class="note__body">${note.body}</div>
          <div class="note__meta">
            <span>${timeAgo(note.created_at)}</span>
            <button class="link" data-del-note="${note.id}" style="background:none;border:0;font-size:.72rem">Delete</button>
          </div>
        </div>`)}
    </section>`;
  slot.querySelectorAll('[data-del-note]').forEach((button) => {
    button.addEventListener('click', async () => {
      const noteId = button.dataset.delNote;
      try {
        await del(`/api/notes/${noteId}`);
        button.closest('.note')?.remove();
        toast('Note deleted');
      } catch (err) { toast(err.message, { type: 'bad' }); }
    });
  });
}

const REACTIONS = [['🔥', 'Hype'], ['😮', 'Whoa'], ['😂', 'Funny'], ['😢', 'Sad'], ['💡', 'Learned']];

function readabilityOf(text) {
  const words = text.match(/[A-Za-z’'-]+/g) || [];
  if (words.length < 60) return { label: 'Quick read', help: 'Short piece' };
  const sentences = Math.max(1, (text.match(/[.!?]+/g) || []).length);
  const syllables = words.reduce((total, word) => {
    const lower = word.toLowerCase();
    return total + Math.max(1, (lower.match(/[aeiouy]+/g) || []).length - (lower.endsWith('e') ? 1 : 0));
  }, 0);
  let score = 206.835 - 1.015 * (words.length / sentences) - 84.6 * (syllables / words.length);
  score = Math.max(0, Math.min(100, score));
  const label = score >= 65 ? 'Easy read' : score >= 45 ? 'Moderate read' : 'Dense read';
  return { label, help: `Flesch reading ease ${Math.round(score)}/100` };
}

const POSITIVE = new Set(('win wins won boost boosts growth success successful agree agreement hope improve improved record breakthrough recovery support celebrate rise gain safe peace progress best top').split(' '));
const NEGATIVE = new Set(('war killed kill death dead crisis fall fell drop loss lose lost attack threat risk fear crash decline cut cuts strike protest inflation layoff layoffs damage hate abuse fail failed warning concern danger').split(' '));

function toneOf(text) {
  const tokens = text.toLowerCase().match(/[a-z']+/g) || [];
  let positive = 0;
  let negative = 0;
  for (const token of tokens) {
    if (POSITIVE.has(token)) positive += 1;
    if (NEGATIVE.has(token)) negative += 1;
  }
  if (positive > negative * 1.4) return { label: 'Upbeat tone', icon: '🌤️' };
  if (negative > positive * 1.4) return { label: 'Critical tone', icon: '🌧️' };
  return { label: 'Neutral tone', icon: '🌥️' };
}

function numbersOf(text) {
  const out = [];
  for (const sentence of text.split(/(?<=[.!?])\s+/)) {
    if (sentence.length < 35 || sentence.length > 260) continue;
    const match = sentence.match(/(?:[$£€]\s?)?\d[\d,.]*\s?(?:%|percent|million|billion|trillion|bn|km|kg|°c|years?|months?|days?|hours?|people|students?|seats?|votes?|goals?|points?|miles?)/i);
    if (!match) continue;
    out.push({ value: match[0].trim(), context: sentence.trim().slice(0, 150) });
    if (out.length >= 4) break;
  }
  return out;
}

function classQuestions(article) {
  const stop = new Set(['The', 'This', 'That', 'After', 'Before', 'Why', 'How', 'What', 'When', 'Where', 'Who', 'New', 'One', 'Two', 'Three', 'First', 'Last', 'From', 'With', 'And']);
  const names = [...new Set((article.title.match(/\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?\b/g) || [])
    .filter((name) => !stop.has(name.split(' ')[0])))].slice(0, 2);
  const who = names[0] || 'the main person';
  return [
    `What does ${who} want — and who stands to lose?`,
    'Which number in this story would you check first, and where would you look?',
    `If you had 30 seconds with ${article.source?.name || 'the reporter'}, what would you ask?`,
  ];
}

function reactionMap() {
  try { return JSON.parse(localStorage.getItem('pulse.reactions') || '{}'); } catch { return {}; }
}

function renderStoryExtras(root, article) {
  const text = (article.blocks || []).map((block) => block.text).join(' ');
  const facts = root.querySelector('#story-facts');
  const bar = root.querySelector('#reaction-bar');
  const slot = root.querySelector('#extras-slot');
  if (!text) return;

  if (facts) {
    const read = readabilityOf(text);
    const tone = toneOf(text);
    const reasons = (article.reasons || []).slice(0, 2);
    facts.innerHTML = html`
      <span class="fact-pill" title="${read.help}">${raw(icons.text)} ${read.label}</span>
      <span class="fact-pill" title="Rough tone estimate from the story's own words">${tone.icon} ${tone.label}</span>
      ${reasons.map((reason) => html`<span class="fact-pill fact-pill--why" title="Why Pulse included this">${reason}</span>`)}`;
  }

  if (bar) {
    const stored = reactionMap()[article.id];
    bar.innerHTML = html`
      <span class="reaction-bar__label">React</span>
      ${REACTIONS.map(([emoji, label]) => html`
        <button type="button" class="reaction ${stored === emoji ? 'is-on' : ''}" data-reaction="${emoji}" title="${label}" aria-label="${label}">${emoji}</button>`)}
      <span class="reaction-bar__note" data-reaction-note>${stored ? `You reacted ${stored}` : ''}</span>`;
    bar.querySelectorAll('[data-reaction]').forEach((button) => {
      button.addEventListener('click', () => {
        const emoji = button.dataset.reaction;
        const map = reactionMap();
        map[article.id] = map[article.id] === emoji ? null : emoji;
        try { localStorage.setItem('pulse.reactions', JSON.stringify(map)); } catch { /* ignore */ }
        bar.querySelectorAll('[data-reaction]').forEach((node) => node.classList.toggle('is-on', node === button && Boolean(map[article.id])));
        const note = bar.querySelector('[data-reaction-note]');
        if (note) note.textContent = map[article.id] ? `You reacted ${emoji}` : '';
        if (map[article.id]) confetti(8);
      });
    });
  }

  if (slot) {
    const numbers = numbersOf(text);
    const questions = classQuestions(article);
    slot.innerHTML = html`
      <section class="section extras">
        <div class="section-head" style="margin-top:1.5rem"><h2>Go deeper</h2><span class="tiny muted">made from this story</span></div>
        <div class="extras-grid">
          ${numbers.length ? html`
            <div class="card card-pad">
              <h3 class="extras-card__title">🔢 By the numbers</h3>
              <ul class="numbers-list">
                ${numbers.map((number) => html`<li><b>${number.value}</b><span>${number.context}</span></li>`)}
              </ul>
            </div>` : ''}
          <div class="card card-pad">
            <h3 class="extras-card__title">🗣️ Three questions for class</h3>
            <ol class="class-list">
              ${questions.map((question) => html`<li>${question}</li>`)}
            </ol>
          </div>
        </div>
      </section>`;
  }
}

function speechChunks(article) {
  const parts = [article.title, article.summary || ''];
  for (const block of article.blocks || []) {
    if (['p', 'li', 'blockquote', 'h2', 'h3', 'h4'].includes(block.type) && block.text) parts.push(block.text);
  }
  const text = parts.filter(Boolean).join('. ')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!text) return [];
  const sentences = text.match(/[^.!?]+[.!?]*/g) || [text];
  const chunks = [];
  let current = '';
  for (const sentence of sentences) {
    if (current && (current + sentence).length > 230) { chunks.push(current.trim()); current = sentence; }
    else current += sentence;
  }
  if (current.trim()) chunks.push(current.trim());
  return chunks;
}

function onListen(button, article) {
  const synth = window.speechSynthesis;
  if (!synth || typeof SpeechSynthesisUtterance === 'undefined') {
    toast('This browser cannot read stories aloud.', { type: 'bad' });
    return;
  }
  const mode = button.dataset.mode || 'idle';
  const setMode = (next, label) => {
    button.dataset.mode = next;
    button.setAttribute('aria-pressed', next === 'playing' ? 'true' : 'false');
    button.innerHTML = html`${raw(next === 'playing' ? icons.pause : icons.sound)} ${label}`;
  };
  if (mode === 'playing') {
    synth.pause();
    setMode('paused', 'Resume');
    return;
  }
  if (mode === 'paused') {
    synth.resume();
    setMode('playing', 'Pause');
    return;
  }
  const chunks = speechChunks(article);
  if (!chunks.length) { toast('There is not enough text to read aloud yet.'); return; }
  synth.cancel();
  let index = 0;
  let stopped = false;
  const finish = () => {
    if (stopped) return;
    stopped = true;
    setMode('idle', 'Listen');
  };
  const speakNext = () => {
    if (stopped) return;
    if (index >= chunks.length) { finish(); toast('Finished reading'); return; }
    const utterance = new SpeechSynthesisUtterance(chunks[index]);
    utterance.rate = Math.min(2, Math.max(0.6, Number(prefs().listen_rate) || 1.02));
    utterance.pitch = 1;
    utterance.lang = 'en-US';
    utterance.onend = () => { index += 1; speakNext(); };
    utterance.onerror = (event) => {
      if (event.error === 'interrupted' || event.error === 'canceled') { finish(); return; }
      finish();
      toast('Read aloud stopped.', { type: 'bad' });
    };
    synth.speak(utterance);
  };
  setMode('playing', 'Pause');
  speakNext();
}

function bindArticle(root, article) {
  const prose = root.querySelector('#prose');

  root.querySelectorAll('[data-act]').forEach((button) => {
    button.addEventListener('click', () => {
      const act = button.dataset.act;
      if (act === 'save') return onSave(button, article);
      if (act === 'share') return onShare(article);
      if (act === 'cite') return onCite(article);
      if (act === 'quiz') return onQuiz(article, root);
      if (act === 'notes') return onAddNote(article, root);
      if (act === 'listen') return onListen(button, article);
      if (act === 'focus') return toggleFocus();
      if (act === 'font') return cycleFont();
    });
  });

  // Text selection → highlight / note popover.
  const menu = document.getElementById('selection-menu');
  let selectionText = '';
  const hideMenu = () => { menu.hidden = true; menu.innerHTML = ''; };

  const showMenu = (event) => {
    const selection = window.getSelection();
    const text = selection?.toString().trim();
    if (!text || text.length < 3 || !prose || !selection.anchorNode || !prose.contains(selection.anchorNode)) {
      hideMenu();
      return;
    }
    selectionText = text.slice(0, 600);
    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    menu.innerHTML = html`
      <button type="button" data-sel="mark">🖍 Highlight</button>
      <button type="button" data-sel="note">✍️ Note</button>
      <button type="button" data-sel="copy">Copy</button>`;
    menu.hidden = false;
    const top = rect.top + window.scrollY - 46;
    menu.style.top = `${Math.max(8, top)}px`;
    menu.style.left = `${Math.min(window.innerWidth - 240, Math.max(8, rect.left))}px`;
    menu.querySelectorAll('[data-sel]').forEach((button) => {
      button.addEventListener('click', async () => {
        const action = button.dataset.sel;
        if (action === 'mark') {
          try {
            const mark = document.createElement('mark');
            mark.textContent = selectionText;
            mark.title = 'Highlighted in Pulse';
            range.deleteContents();
            range.insertNode(mark);
            toast('Highlighted', { type: 'good' });
          } catch { toast('Could not highlight that selection', { type: 'bad' }); }
        } else if (action === 'copy') {
          await copyText(selectionText);
          toast('Copied');
        } else {
          openNoteModal(article, root, selectionText);
        }
        hideMenu();
        selection.removeAllRanges();
      });
    });
  };

  if (prose) {
    prose.addEventListener('mouseup', (event) => setTimeout(() => showMenu(event), 10));
    prose.addEventListener('touchend', (event) => setTimeout(() => showMenu(event), 20));
  }
  document.addEventListener('click', (event) => {
    if (!menu.hidden && !menu.contains(event.target) && !prose?.contains(event.target)) hideMenu();
  });
  window.addEventListener('scroll', hideMenu, { passive: true });

  // Track reading progress and award a "read" once.
  const bar = root.querySelector('#read-progress');
  window.addEventListener('scroll', () => {
    if (!bar) return;
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const percent = max > 0 ? Math.min(100, (window.scrollY / max) * 100) : 0;
    bar.style.width = `${percent}%`;
  }, { passive: true });
}

async function onSave(button, article) {
  try {
    const { saved } = await toggleSave({ id: article.id, saved: Boolean(article.saved_collection) });
    article.saved_collection = saved ? 'Saved' : null;
    button.classList.toggle('is-on', saved);
    button.setAttribute('aria-pressed', saved ? 'true' : 'false');
    const label = button.querySelector('[data-save-label]');
    if (label) label.textContent = saved ? 'Saved' : 'Save';
    toast(saved ? 'Saved to your library' : 'Removed from saved');
    if (saved) confetti(10);
  } catch (err) {
    toast(err.message, { type: 'bad' });
  }
}

async function onShare(article) {
  const shareUrl = `${window.location.origin}/article/${article.id}`;
  const shareData = { title: article.title, text: article.preview || article.title, url: shareUrl };
  try {
    if (navigator.share) {
      await navigator.share(shareData);
      record('share', { articleId: article.id });
      return;
    }
  } catch { /* user cancelled or unsupported */ }
  const ok = await copyText(shareUrl);
  toast(ok ? 'Link copied' : 'Could not copy the link', { type: ok ? 'good' : 'bad' });
  if (ok) record('share', { articleId: article.id });
}

async function onCite(article) {
  const { modal: box } = modal({
    title: 'Cite this story',
    wide: true,
    body: html`<div class="stack-sm" id="cite-list"><div class="skeleton skeleton--line"></div><div class="skeleton skeleton--line" style="width:70%"></div></div>`,
    actions: [{ label: 'Done', class: 'btn--ghost' }],
  });
  const list = box.querySelector('#cite-list');
  try {
    const data = await get(`/api/articles/${article.id}/citations`, 60);
    list.innerHTML = data.styles.map((style) => html`
      <div>
        <div class="citation-label">${style.label} <span class="faint" style="text-transform:none;letter-spacing:0">· ${style.hint}</span></div>
        <div class="citation-box" id="cite-${style.id}">${data.citations[style.id]}</div>
        <button class="btn btn--sm btn--ghost" style="margin-top:.35rem" data-copy="${style.id}">Copy ${style.label}</button>
      </div>`).join('');
    list.querySelectorAll('[data-copy]').forEach((button) => {
      button.addEventListener('click', async () => {
        const text = data.citations[button.dataset.copy];
        const ok = await copyText(text);
        toast(ok ? 'Citation copied' : 'Copy failed', { type: ok ? 'good' : 'bad' });
      });
    });
  } catch (err) {
    list.innerHTML = html`<p class="muted small">${err.message}</p>`;
  }
}

async function onQuiz(article, root) {
  const slot = root.querySelector('#quiz-slot');
  if (slot.dataset.loaded) { slot.scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
  slot.innerHTML = html`<section class="section"><div class="section-head"><h2>Test yourself</h2></div><div class="skeleton" style="height:120px"></div></section>`;
  try {
    const quiz = await get(`/api/articles/${article.id}/quiz`, 120);
    if (!quiz.questions?.length) {
      slot.innerHTML = html`<section class="section"><div class="section-head"><h2>Test yourself</h2></div><div class="card card-pad"><p class="small muted">Not enough extractable text for a quiz on this one — try a longer article.</p></div></section>`;
      return;
    }
    slot.dataset.loaded = '1';
    slot.innerHTML = html`
      <section class="section">
        <div class="section-head">
          <h2>Test yourself</h2>
          <span class="badge ${quiz.engine === 'ai' ? 'badge--ai' : 'badge--topic'}">${quiz.engine === 'ai' ? 'AI quiz' : 'Auto quiz'}</span>
        </div>
        <div class="card card-pad-lg">
          ${quiz.questions.map((question, qIndex) => html`
            <div class="quiz__q" data-q="${qIndex}">
              <p>${qIndex + 1}. ${question.question}</p>
              <div class="quiz__options">
                ${question.options.map((option, oIndex) => html`
                  <button class="quiz__opt" data-option="${oIndex}" data-answer="${question.answer_index}" data-qindex="${qIndex}">
                    <b>${String.fromCharCode(65 + oIndex)}</b><span>${option}</span>
                  </button>`)}
              </div>
              <div class="quiz__explain" hidden></div>
            </div>`)}
          <p class="tiny faint" style="margin-top:.6rem">${quiz.note || (quiz.engine === 'ai' ? 'Questions generated from this article only — check them against the text.' : 'Questions are built from the article’s own sentences.')}</p>
        </div>
      </section>`;

    slot.querySelectorAll('.quiz__opt').forEach((button) => {
      button.addEventListener('click', async () => {
        const group = button.closest('.quiz__q');
        if (group.dataset.answered) return;
        group.dataset.answered = '1';
        const correctIndex = Number(button.dataset.answer);
        const chosen = Number(button.dataset.option);
        const correct = chosen === correctIndex;
        group.querySelectorAll('.quiz__opt').forEach((option, index) => {
          option.classList.toggle('is-right', index === correctIndex);
          option.classList.toggle('is-wrong', index === chosen && !correct);
        });
        const explain = group.querySelector('.quiz__explain');
        if (explain) {
          const text = quiz.questions[Number(button.dataset.qindex)].explain;
          explain.textContent = text || '';
          explain.hidden = !text;
        }
        try {
          const result = await post(`/api/articles/${article.id}/quiz-result`, {
            correct,
            question: quiz.questions[Number(button.dataset.qindex)].question,
            selected: chosen,
          });
          toastProgress(result.progress);
        } catch { /* offline-friendly */ }
      });
    });
  } catch (err) {
    slot.innerHTML = html`<section class="section"><div class="card card-pad"><p class="small muted">${err.message}</p></div></section>`;
  }
}

function openNoteModal(article, root, quote = '') {
  const body = document.createElement('div');
  body.innerHTML = html`
    ${quote ? html`<div class="note__quote" style="margin-bottom:.7rem">“${quote}”</div>` : ''}
    <label class="tiny muted" for="note-body" style="display:block;margin-bottom:.35rem">Your note</label>
    <textarea id="note-body" placeholder="What stood out? Why does it matter? A question to ask in class…"></textarea>`;
  const { close } = modal({
    title: 'Add a note',
    body,
    actions: [
      { label: 'Cancel', class: 'btn--ghost' },
      {
        label: 'Save note',
        class: 'btn--primary',
        onClick: async () => {
          const text = body.querySelector('#note-body').value.trim();
          if (text.length < 2) { toast('Write something first', { type: 'bad' }); return false; }
          try {
            await post(`/api/articles/${article.id}/notes`, { body: text, quote });
            const data = await get(`/api/articles/${article.id}`, 0, true);
            article.notes = data.article.notes;
            renderNotes(root, article);
            const progress = await record('note', { articleId: article.id });
            toastProgress(progress);
            toast('Note saved', { type: 'good' });
          } catch (err) {
            toast(err.message, { type: 'bad' });
            return false;
          }
          return true;
        },
      },
    ],
  });
  void close;
}

function onAddNote(article, root) {
  openNoteModal(article, root, '');
  record('open', { articleId: article.id, silent: true });
}

async function toggleFocus() {
  document.body.classList.toggle('focus-mode');
  const on = document.body.classList.contains('focus-mode');
  toast(on ? 'Focus mode on — press Esc to exit' : 'Focus mode off');
}

async function cycleFont() {
  const current = prefs().font || 'sans';
  const index = FONTS.findIndex((font) => font.id === current);
  const next = FONTS[(index + 1) % FONTS.length];
  try {
    await savePrefs({ font: next.id });
    const prose = document.getElementById('prose');
    if (prose) prose.dataset.font = next.id === 'serif' ? 'serif' : '';
    toast(`Reading font: ${next.label}`);
  } catch (err) { toast(err.message, { type: 'bad' }); }
}

async function loadOverview(root, article) {
  const slot = root.querySelector('#overview-slot');
  if (!slot) return;
  try {
    const overview = await get(`/api/articles/${article.id}/overview`, 300);
    slot.innerHTML = overviewMarkup(overview, article);
    bindOverview(root, article, overview);
  } catch (err) {
    slot.innerHTML = html`<div class="overview"><div class="overview__body"><p class="small muted">Overview unavailable: ${err.message}</p></div></div>`;
  }
}

function overviewMarkup(overview, article) {
  const isAI = overview.engine === 'ai';
  const badge = isAI
    ? html`<span class="badge badge--ai">${raw(icons.sparkle)} AI overview</span>`
    : html`<span class="badge badge--topic">Auto summary</span>`;
  const meta = isAI
    ? html`<span class="tiny faint">${overview.model || 'model'} · grounded in this article</span>`
    : html`<span class="tiny faint">extractive · built from the article's own sentences</span>`;
  return html`
    <section class="overview" id="overview-card">
      <div class="overview__head">
        <h2>${badge}</h2>
        ${meta}
        <span class="spacer" style="flex:1"></span>
        <button class="btn btn--sm btn--ghost" data-act="simplify">${raw(icons.text)} Explain simply</button>
      </div>
      <div class="overview__body">
        ${overview.summary && overview.summary.trim() !== (article.summary || '').trim()
          ? html`<p class="overview__summary">${overview.summary}</p>`
          : ''}
        ${overview.key_points?.length ? html`
          <ul class="overview__points">
            ${overview.key_points.map((point) => html`<li><span>${point}</span></li>`)}
          </ul>` : ''}
        ${overview.why_it_matters ? html`
          <div class="term" style="margin-top:.9rem">
            <dt>Why it matters</dt>
            <dd>${overview.why_it_matters}</dd>
          </div>` : ''}
        ${overview.terms?.length ? html`
          <div class="overview__terms">
            ${overview.terms.map((term) => html`<dl class="term"><dt>${term.term}</dt><dd>${term.definition}</dd></dl>`)}
          </div>` : ''}
        <div id="simplify-slot"></div>
        <p class="overview__note">
          ${raw(icons.info)}
          <span>${overview.warning || (isAI
            ? 'AI overviews are generated from this article only and can still be wrong. Always check the original before citing.'
            : 'This summary is assembled from sentences in the article — no AI model, no added facts.')}</span>
        </p>
      </div>
    </section>`;
}

function bindOverview(root, article, overview) {
  const button = root.querySelector('[data-act="simplify"]');
  if (!button) return;
  button.addEventListener('click', async () => {
    const slot = root.querySelector('#simplify-slot');
    if (!slot) return;
    if (slot.dataset.loaded) { slot.innerHTML = ''; slot.dataset.loaded = ''; return; }
    slot.innerHTML = html`<div class="skeleton skeleton--line" style="margin-top:1rem"></div>`;
    try {
      const explained = await get(`/api/articles/${article.id}/explain`, 300);
      slot.dataset.loaded = '1';
      slot.innerHTML = html`
        <div class="term" style="margin-top:1rem;background:var(--surface-2)">
          <dt>In plain English <span class="tiny faint">· ${explained.engine === 'ai' ? 'AI rewrite' : 'simplified'}</span></dt>
          <dd style="font-size:.86rem;line-height:1.6">${explained.text}</dd>
          ${explained.jargon?.length ? html`
            <div class="overview__terms">
              ${explained.jargon.map((term) => html`<dl class="term" style="background:var(--surface)"><dt>${term.term}</dt><dd>${term.definition}</dd></dl>`)}
            </div>` : ''}
          ${explained.warning ? html`<p class="tiny faint" style="margin-top:.5rem">${explained.warning}</p>` : ''}
        </div>`;
    } catch (err) {
      slot.innerHTML = html`<p class="small muted">${err.message}</p>`;
    }
  });
  void overview;
}

let readTimer = null;
function trackReading(article) {
  if (readTimer) clearTimeout(readTimer);
  record('open', { articleId: article.id, silent: true });
  const started = Date.now();
  let awarded = false;
  const award = () => {
    if (awarded) return;
    awarded = true;
    const seconds = Math.max(12, Math.round((Date.now() - started) / 1000));
    record('read', { articleId: article.id, value: seconds }).then((progress) => {
      if (progress) toastProgress(progress);
    });
  };
  readTimer = setTimeout(award, 22000);
  const onScroll = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    if (max > 0 && window.scrollY / max > 0.45) {
      award();
      window.removeEventListener('scroll', onScroll);
    }
  };
  window.addEventListener('scroll', onScroll, { passive: true });
}
