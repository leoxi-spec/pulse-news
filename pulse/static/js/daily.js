// Daily corner: the word, poll, debate, quiz, challenge and tiny rituals that
// make Pulse feel like a place to hang out rather than a wall of headlines.
import { get, post } from './api.js';
import { html, raw, icons, toast, confetti, copyText } from './ui.js';
import { prefs, savePrefs } from './store.js';
import { sectionHead } from './components.js';

const KEY = {
  votes: 'pulse.daily.votes',
  quiz: 'pulse.daily.quiz',
  challenge: 'pulse.daily.challenge',
  mood: 'pulse.daily.mood',
  glossary: 'pulse.glossary',
};

let cache = null;

export async function loadDaily() {
  if (cache) return cache;
  cache = await get('/api/daily', 20);
  return cache;
}

export function resetDaily() {
  cache = null;
}

function read(key, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(key));
    return value === null || value === undefined ? fallback : value;
  } catch { return fallback; }
}

function write(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
}

const MOODS = [
  ['😌', 'Chill', 'Calmer, slower stories'],
  ['⚡', 'Hype', 'Fast, breaking, big'],
  ['🧠', 'Deep', 'Explainers and long reads'],
  ['😂', 'Light', 'Fun, culture, weird'],
  ['😐', 'Just facts', 'Straight news only'],
];

// ------------------------------------------------------------------ markup
export function dailySection(data) {
  if (!data) return '';
  return html`
    <section class="home-section daily-section" data-id="daily">
      <div data-head>${sectionHead('Today', html`<span class="tiny muted">a little of everything</span>`, { sub: 'word · poll · quiz · challenge' })}</div>
      <div data-body>
        ${ticker(data.trending)}
        <div class="daily-grid">
          ${challengeCard(data.challenge)}
          ${wordCard(data.word)}
          ${pollCard(data.poll)}
          ${quizCard(data.quiz)}
          ${debateCard(data.debate)}
          ${wyrCard(data.wyr)}
          ${historyCard(data.history, data.history_label)}
          ${quoteCard(data.quote)}
          ${moodCard()}
        </div>
      </div>
    </section>`;
}

function ticker(trending) {
  const terms = (trending || []).slice(0, 8);
  if (!terms.length) return '';
  const items = terms.map((term) => html`<a href="/search?q=${encodeURIComponent(term.term)}" data-link>#${term.term}</a>`);
  return html`
    <div class="ticker" aria-label="Trending searches">
      <span class="ticker__label">${raw(icons.bolt)} Trending</span>
      <div class="ticker__track">
        <div class="ticker__run">${items}${items}</div>
      </div>
    </div>`;
}

function ring(percent) {
  return html`
    <span class="ring" style="--p:${Math.max(0, Math.min(100, percent))}" aria-hidden="true">
      <span>${percent}%</span>
    </span>`;
}

function challengeCard(challenge) {
  const claimed = read(KEY.challenge, {})[challenge?.date] === true;
  const complete = challenge && challenge.done === challenge.total;
  return html`
    <article class="daily-card daily-card--challenge">
      <div class="daily-card__top">
        <span class="daily-card__eyebrow">${raw(icons.bolt)} Daily challenge</span>
        ${ring(challenge?.percent || 0)}
      </div>
      <h3 class="daily-card__title">${complete ? 'Challenge complete 🎉' : 'Four tiny wins today'}</h3>
      <ul class="quest-list">
        ${(challenge?.tasks || []).map((task) => html`
          <li class="${task.done ? 'is-done' : ''}">
            <span class="quest-list__icon">${task.done ? '✅' : task.icon}</span>
            <span class="quest-list__label">${task.label}</span>
            <span class="quest-list__count">${task.now}/${task.target}</span>
          </li>`)}
      </ul>
      ${complete && !claimed ? html`<button class="btn btn--primary btn--sm" data-claim-challenge>Claim +25 XP</button>` : ''}
      ${claimed ? html`<p class="tiny faint">Claimed. See you tomorrow.</p>` : ''}
    </article>`;
}

function wordCard(word) {
  if (!word) return '';
  return html`
    <article class="daily-card daily-card--word">
      <span class="daily-card__eyebrow">${raw(icons.text)} Word of the day</span>
      <h3 class="daily-card__title">${word.word}</h3>
      <p class="daily-card__say">${word.say} · ${word.pos}</p>
      <p class="daily-card__body">${word.meaning}</p>
      <p class="daily-card__example">“${word.example}”</p>
      <button class="btn btn--sm btn--ghost" data-add-word="${word.word}">+ Add to study</button>
    </article>`;
}

function pollCard(poll) {
  if (!poll) return '';
  const votes = read(KEY.votes, {});
  const chosen = votes[poll.id];
  return html`
    <article class="daily-card daily-card--poll">
      <span class="daily-card__eyebrow">${raw(icons.bolt)} Your take</span>
      <h3 class="daily-card__title">${poll.question}</h3>
      <div class="opt-list" data-poll="${poll.id}">
        ${poll.options.map((option, index) => html`
          <button type="button" class="opt ${chosen === index ? 'is-on' : ''}" data-poll-option="${index}">
            <span class="opt__dot"></span>${option}
          </button>`)}
      </div>
      <p class="daily-card__note" data-poll-note>${typeof chosen === 'number' ? `You picked “${poll.options[chosen]}”. Saved on this device.` : 'Pick one — there is no wrong answer.'}</p>
    </article>`;
}

function debateCard(debate) {
  if (!debate) return '';
  const votes = read(KEY.votes, {});
  const side = votes[debate.id];
  return html`
    <article class="daily-card daily-card--debate">
      <span class="daily-card__eyebrow">${raw(icons.quote)} Debate club</span>
      <h3 class="daily-card__title">${debate.motion}</h3>
      <div class="opt-list" data-debate="${debate.id}">
        <button type="button" class="opt ${side === 'for' ? 'is-on' : ''}" data-debate-side="for"><span class="opt__dot"></span>I'm for it</button>
        <button type="button" class="opt ${side === 'against' ? 'is-on' : ''}" data-debate-side="against"><span class="opt__dot"></span>I'm against it</button>
      </div>
      <p class="daily-card__note" data-debate-note>${side ? (side === 'for' ? debate.for : debate.against) : 'Pick a side, then see the strongest argument for it.'}</p>
    </article>`;
}

function wyrCard(wyr) {
  if (!wyr) return '';
  const votes = read(KEY.votes, {});
  const side = votes[wyr.id];
  return html`
    <article class="daily-card daily-card--wyr">
      <span class="daily-card__eyebrow">${raw(icons.sparkle)} Would you rather…</span>
      <div class="opt-list" data-wyr="${wyr.id}">
        <button type="button" class="opt opt--big ${side === 'a' ? 'is-on' : ''}" data-wyr-side="a">${wyr.a}</button>
        <button type="button" class="opt opt--big ${side === 'b' ? 'is-on' : ''}" data-wyr-side="b">${wyr.b}</button>
      </div>
      <p class="daily-card__note" data-wyr-note>${side ? 'Locked in. Defend it in the group chat.' : 'No explanation needed. Just vibes.'}</p>
    </article>`;
}

function quizCard(quiz) {
  const questions = quiz?.questions || [];
  if (!questions.length) return '';
  return html`
    <article class="daily-card daily-card--quiz">
      <div class="daily-card__top">
        <span class="daily-card__eyebrow">${raw(icons.sparkle)} News IQ</span>
        <span class="tiny faint" data-quiz-step>1 / ${questions.length}</span>
      </div>
      <div data-quiz-body></div>
    </article>`;
}

function historyCard(items, label = 'On this day') {
  if (!items?.length) return '';
  return html`
    <article class="daily-card daily-card--history">
      <span class="daily-card__eyebrow">${raw(icons.refresh)} ${label}</span>
      <h3 class="daily-card__title">${label === 'On this day' ? 'Same day, earlier years' : 'From the archive'}</h3>
      <div class="mini-list">
        ${items.slice(0, 2).map((item) => html`
          <a class="mini-story" href="/article/${item.id}" data-link>
            ${item.image ? html`<img src="${item.image}" alt="" loading="lazy">` : html`<span class="mini-story__fallback">🗓️</span>`}
            <span class="mini-story__text">
              <b>${item.title}</b>
              <i>${item.source?.name || ''} · ${item.published_relative}</i>
            </span>
          </a>`)}
      </div>
    </article>`;
}

function quoteCard(quote) {
  if (!quote) return '';
  return html`
    <article class="daily-card daily-card--quote">
      <span class="daily-card__eyebrow">${raw(icons.quote)} Quote</span>
      <blockquote>“${quote.text}”</blockquote>
      <p class="daily-card__say">— ${quote.by}</p>
      <button class="btn btn--sm btn--ghost" data-copy-quote>Copy</button>
    </article>`;
}

function moodCard() {
  const saved = read(KEY.mood, null) || prefs().mood || '';
  return html`
    <article class="daily-card daily-card--mood">
      <span class="daily-card__eyebrow">${raw(icons.sparkle)} Mood check</span>
      <h3 class="daily-card__title">What do you need today?</h3>
      <div class="mood-row">
        ${MOODS.map(([emoji, label, hint]) => html`
          <button type="button" class="mood ${saved === label ? 'is-on' : ''}" data-mood="${label}" title="${hint}" aria-label="${label}: ${hint}">
            <span>${emoji}</span><i>${label}</i>
          </button>`)}
      </div>
      <p class="daily-card__note" data-mood-note>${saved ? `Feed mood: ${saved}` : 'Sets the tone for your feed.'}</p>
    </article>`;
}

// ------------------------------------------------------------------ binding
export function bindDaily(root, data) {
  if (!data) return;
  bindChallenge(root, data.challenge);
  bindWord(root, data.word);
  bindPoll(root, data.poll);
  bindDebate(root, data.debate);
  bindWyr(root, data.wyr);
  bindQuiz(root, data.quiz);
  bindQuote(root, data.quote);
  bindMood(root);
}

function bindChallenge(root, challenge) {
  const button = root.querySelector('[data-claim-challenge]');
  if (!button || !challenge) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await post('/api/events', { kind: 'challenge_complete' });
      const claimed = read(KEY.challenge, {});
      claimed[challenge.date] = true;
      write(KEY.challenge, claimed);
      confetti(70);
      toast('+25 XP — challenge complete!', { type: 'good' });
      button.replaceWith(Object.assign(document.createElement('p'), { className: 'tiny faint', textContent: 'Claimed. See you tomorrow.' }));
    } catch (err) {
      button.disabled = false;
      toast(err.message || 'Could not claim just yet.', { type: 'bad' });
    }
  });
}

function bindWord(root, word) {
  const button = root.querySelector('[data-add-word]');
  if (!button || !word) return;
  button.addEventListener('click', () => {
    const list = read(KEY.glossary, []);
    if (!list.some((entry) => entry.word === word.word)) {
      list.unshift({ word: word.word, meaning: word.meaning, added: new Date().toISOString() });
      write(KEY.glossary, list.slice(0, 200));
      toast(`“${word.word}” added to Study`, { type: 'good' });
      button.textContent = '✓ In Study';
      button.disabled = true;
    } else {
      toast('Already in Study');
    }
  });
}

function bindPoll(root, poll) {
  const box = root.querySelector('[data-poll]');
  if (!box || !poll) return;
  const note = box.parentElement.querySelector('[data-poll-note]');
  box.querySelectorAll('[data-poll-option]').forEach((button) => {
    button.addEventListener('click', () => {
      const index = Number(button.dataset.pollOption);
      const votes = read(KEY.votes, {});
      votes[poll.id] = index;
      write(KEY.votes, votes);
      box.querySelectorAll('.opt').forEach((node) => node.classList.toggle('is-on', node === button));
      note.textContent = `You picked “${poll.options[index]}”. Saved on this device.`;
      confetti(18);
    });
  });
}

function bindDebate(root, debate) {
  const box = root.querySelector('[data-debate]');
  if (!box || !debate) return;
  const note = box.parentElement.querySelector('[data-debate-note]');
  box.querySelectorAll('[data-debate-side]').forEach((button) => {
    button.addEventListener('click', () => {
      const side = button.dataset.debateSide;
      const votes = read(KEY.votes, {});
      votes[debate.id] = side;
      write(KEY.votes, votes);
      box.querySelectorAll('.opt').forEach((node) => node.classList.toggle('is-on', node === button));
      note.textContent = side === 'for' ? debate.for : debate.against;
    });
  });
}

function bindWyr(root, wyr) {
  const box = root.querySelector('[data-wyr]');
  if (!box || !wyr) return;
  const note = box.parentElement.querySelector('[data-wyr-note]');
  box.querySelectorAll('[data-wyr-side]').forEach((button) => {
    button.addEventListener('click', () => {
      const side = button.dataset.wyrSide;
      const votes = read(KEY.votes, {});
      votes[wyr.id] = side;
      write(KEY.votes, votes);
      box.querySelectorAll('.opt').forEach((node) => node.classList.toggle('is-on', node === button));
      note.textContent = `Locked in: ${side === 'a' ? wyr.a : wyr.b}. Defend it in the group chat.`;
      confetti(14);
    });
  });
}

function bindQuiz(root, quiz) {
  const body = root.querySelector('[data-quiz-body]');
  const step = root.querySelector('[data-quiz-step]');
  const questions = quiz?.questions || [];
  if (!body || !questions.length) return;
  let index = 0;
  let score = 0;
  let answered = false;

  const paint = () => {
    const question = questions[index];
    answered = false;
    if (step) step.textContent = `${index + 1} / ${questions.length}`;
    body.innerHTML = html`
      <p class="quiz-q">Which outlet published this?</p>
      <p class="quiz-headline">“${question.headline}”</p>
      <div class="opt-list">
        ${question.options.map((option, optionIndex) => html`
          <button type="button" class="opt" data-quiz-option="${optionIndex}">
            <span class="opt__dot"></span>${option}
          </button>`)}
      </div>
      <p class="daily-card__note" data-quiz-note>Trust your news memory.</p>`;
    body.querySelectorAll('[data-quiz-option]').forEach((button) => {
      button.addEventListener('click', () => answer(Number(button.dataset.quizOption), button));
    });
  };

  const answer = (choice, button) => {
    if (answered) return;
    answered = true;
    const question = questions[index];
    const correct = choice === question.answer;
    body.querySelectorAll('[data-quiz-option]').forEach((node, nodeIndex) => {
      node.disabled = true;
      if (nodeIndex === question.answer) node.classList.add('is-correct');
      else if (node === button) node.classList.add('is-wrong');
    });
    const note = body.querySelector('[data-quiz-note]');
    if (correct) {
      score += 1;
      note.textContent = `Correct — ${question.source}.`;
      confetti(12);
    } else {
      note.textContent = `It was ${question.source}.`;
    }
    post('/api/events', { kind: 'quiz_attempt', article_id: question.article_id }).catch(() => {});
    if (correct) post('/api/events', { kind: 'quiz_correct', article_id: question.article_id }).catch(() => {});
    const next = document.createElement('button');
    next.className = 'btn btn--sm btn--primary';
    next.style.marginTop = '.6rem';
    next.textContent = index + 1 >= questions.length ? 'See score' : 'Next question';
    next.addEventListener('click', () => {
      index += 1;
      if (index >= questions.length) finish();
      else paint();
    });
    note.after(next);
  };

  const finish = () => {
    if (step) step.textContent = `${questions.length} / ${questions.length}`;
    const perfect = score === questions.length;
    if (perfect) confetti(90);
    body.innerHTML = html`
      <p class="quiz-q">You scored</p>
      <p class="quiz-score">${score}<span>/${questions.length}</span></p>
      <p class="daily-card__note">${perfect ? 'Perfect. You actually read the news.' : 'Not bad — play again tomorrow for a new set.'}</p>
      <button type="button" class="btn btn--sm btn--ghost" data-quiz-retry>Play again</button>`;
    body.querySelector('[data-quiz-retry]')?.addEventListener('click', () => {
      index = 0; score = 0; paint();
    });
  };

  paint();
}

function bindQuote(root, quote) {
  const button = root.querySelector('[data-copy-quote]');
  if (!button || !quote) return;
  button.addEventListener('click', async () => {
    await copyText(`“${quote.text}” — ${quote.by}`);
    toast('Quote copied');
  });
}

function bindMood(root) {
  const note = root.querySelector('[data-mood-note]');
  root.querySelectorAll('[data-mood]').forEach((button) => {
    button.addEventListener('click', () => {
      const mood = button.dataset.mood;
      write(KEY.mood, mood);
      root.querySelectorAll('[data-mood]').forEach((node) => node.classList.toggle('is-on', node === button));
      if (note) note.textContent = `Feed mood: ${mood}`;
      savePrefs({ mood }).catch(() => {});
      toast(`Mood set: ${mood}`);
    });
  });
}
