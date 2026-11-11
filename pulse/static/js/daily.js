// Daily corner: the word, poll, debate, quiz, challenge and tiny rituals that
// make Pulse feel like a place to hang out rather than a wall of headlines.
import { get, post } from './api.js';
import { html, raw, icons, toast, confetti, copyText, modal } from './ui.js';
import { state, prefs, savePrefs, dailyProgress, streak, levels } from './store.js';
import { sectionHead } from './components.js';
import { chooseAnimation, chooseNoise, setNoiseVolume } from './ambient.js';
import { navigate } from './router.js';

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

const DEFAULT_WIDGETS = ['challenge', 'word', 'poll', 'quiz', 'top3', 'photo', 'journal', 'streak'];

function widgetOrder() {
  const saved = Array.isArray(prefs().widgets) ? prefs().widgets : [];
  const valid = saved.filter((id) => WIDGETS.some((widget) => widget.id === id));
  return valid.length ? valid : DEFAULT_WIDGETS;
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
  const order = widgetOrder();
  const cards = order
    .map((id) => WIDGETS.find((widget) => widget.id === id))
    .filter(Boolean)
    .map((widget) => widget.render(data))
    .filter(Boolean);
  return html`
    <section class="home-section daily-section" data-id="daily">
      <div data-head>${sectionHead('Today', html`<button class="btn btn--sm btn--ghost" data-customize-widgets>${raw(icons.filter)} Edit widgets</button>`, { sub: `${cards.length} of ${WIDGETS.length} widgets · make it yours` })}</div>
      <div data-body>
        ${ticker(data.trending)}
        ${cards.length ? html`<div class="daily-grid">${cards}</div>` : html`
          <div class="card card-pad-lg" style="text-align:center">
            <p class="daily-card__title">Your Today board is empty</p>
            <p class="small muted" style="margin:.3rem 0 .8rem">Pick the widgets you want — word games, scores, quizzes, quotes, whatever.</p>
            <button class="btn btn--primary" data-customize-widgets>Choose widgets</button>
          </div>`}
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

// --------------------------------------------------------- extra widgets
function miniStory(item, { time = true } = {}) {
  if (!item) return '';
  return html`
    <a class="mini-story" href="/article/${item.id}" data-link>
      ${item.image ? html`<img src="${item.image}" alt="" loading="lazy">` : html`<span class="mini-story__fallback">📰</span>`}
      <span class="mini-story__text">
        <b>${item.title}</b>
        <i>${item.source?.name || ''}${time ? ` · ${item.reading_minutes || 1} min` : ''}</i>
      </span>
    </a>`;
}

function newCard(className, eyebrow, title, body, extra = '') {
  return html`
    <article class="daily-card ${className}">
      <span class="daily-card__eyebrow">${raw(eyebrow)}</span>
      ${title ? html`<h3 class="daily-card__title">${title}</h3>` : ''}
      ${body}
      ${extra}
    </article>`;
}

function top3Card(data) {
  const items = (data.widgets?.top || []).slice(0, 3);
  if (!items.length) return '';
  return newCard('', icons.bolt, 'Top 3 right now', html`<div class="mini-list">${items.map((item) => miniStory(item))}</div>`);
}

function quickCard(data) {
  const items = (data.widgets?.quick || []).slice(0, 2);
  if (!items.length) return '';
  return newCard('', icons.bolt, 'Under 2 minutes', html`<div class="mini-list">${items.map((item) => miniStory(item))}</div>`, html`<p class="daily-card__note">Short enough for the bus.</p>`);
}

function longReadCard(data) {
  const item = (data.widgets?.long || [])[0];
  if (!item) return '';
  return newCard('', icons.book, 'Long read of the day', html`
    <a class="mini-story" href="/article/${item.id}" data-link>
      ${item.image ? html`<img src="${item.image}" alt="" loading="lazy">` : html`<span class="mini-story__fallback">📖</span>`}
      <span class="mini-story__text"><b>${item.title}</b><i>${item.reading_minutes || 6} min · ${item.source?.name || ''}</i></span>
    </a>`, html`<p class="daily-card__note">${item.preview || ''}</p>`);
}

function goodCard(data) {
  const item = (data.widgets?.good || [])[0];
  if (!item) return '';
  return newCard('daily-card--good', icons.sparkle, 'One good thing', html`${miniStory(item)}`, html`<p class="daily-card__note">No crisis, no doomscroll — just something that went right.</p>`);
}

function photoCard(data) {
  const item = (data.widgets?.photo || [])[0];
  if (!item) return '';
  return newCard('daily-card--photo', icons.eye, 'Photo of the day', html`
    <a class="widget-photo" href="/article/${item.id}" data-link>
      <img src="${item.image}" alt="" loading="lazy">
      <span>${item.title}</span>
    </a>`, html`<p class="daily-card__note">${item.source?.name || ''}</p>`);
}

function topicCard(data) {
  const topic = data.widgets?.topic;
  if (!topic?.items?.length) return '';
  return newCard('', icons.compass, `${topic.topic_label} spotlight`, html`<div class="mini-list">${topic.items.map((item) => miniStory(item))}</div>`, html`<a class="daily-card__note" href="/topic/${topic.topic}" data-link>See all ${topic.topic_label} →</a>`);
}

function sourceCard(data) {
  const source = data.widgets?.source;
  const items = source?.items || [];
  if (!items.length) return '';
  return newCard('', icons.compass, items[0].source?.name || 'Source spotlight', html`<div class="mini-list">${items.map((item) => miniStory(item))}</div>`, html`<p class="daily-card__note">A different outlet to try today.</p>`);
}

function mostCoveredCard(data) {
  const item = (data.widgets?.most || [])[0];
  if (!item) return '';
  return newCard('', icons.fire, 'Everyone is covering this', html`${miniStory(item)}`, html`<p class="daily-card__note">${item.story?.source_count || 1} newsrooms have this story.</p>`);
}

function sportsCard(data) {
  const items = (data.widgets?.sports || []).slice(0, 2);
  if (!items.length) return '';
  return newCard('', icons.trophy, 'Sports quick hits', html`<div class="mini-list">${items.map((item) => miniStory(item))}</div>`);
}

function f1Card(data) {
  const items = (data.widgets?.motorsport || []).slice(0, 2);
  if (!items.length) return '';
  return newCard('', icons.fire, '🏎️ F1 & motorsport', html`<div class="mini-list">${items.map((item) => miniStory(item))}</div>`);
}

function scienceCard(data) {
  const item = (data.widgets?.science || [])[0];
  if (!item) return '';
  return newCard('', icons.sparkle, 'Science spark', html`${miniStory(item)}`);
}

function cultureCard(data) {
  const item = (data.widgets?.culture || [])[0];
  if (!item) return '';
  return newCard('', icons.sparkle, 'Culture pick', html`${miniStory(item)}`);
}

function numbersCard(data) {
  const number = data.widgets?.number;
  if (!number) return '';
  return newCard('daily-card--number', icons.bolt, 'Number of the day', html`
    <p class="widget-number">${number.value}</p>
    <p class="daily-card__body">${number.context}</p>
    <a class="daily-card__note" href="/article/${number.item.id}" data-link>Read the story →</a>`);
}

function scrambleCard(data) {
  const word = data.word?.word;
  if (!word) return '';
  const letters = word.split('');
  const day = new Date().getDate();
  for (let i = letters.length - 1; i > 0; i -= 1) {
    const j = (i * 7 + day) % (i + 1);
    [letters[i], letters[j]] = [letters[j], letters[i]];
  }
  const scrambled = letters.join(' ').toUpperCase();
  return newCard('daily-card--game', icons.sparkle, 'Unscramble the word', html`
    <p class="widget-scramble">${scrambled}</p>
    <form class="widget-game-form" data-scramble-form>
      <input data-scramble-input autocomplete="off" placeholder="Your answer" aria-label="Unscramble the word">
      <button class="btn btn--sm btn--primary" type="submit">Check</button>
    </form>
    <p class="daily-card__note" data-scramble-note>Hint: it is today’s word of the day.</p>`);
}

function guessCard(data) {
  const item = (data.widgets?.top || [])[0];
  if (!item) return '';
  const correct = item.topic_label;
  const options = [correct];
  for (const topic of state.topicMap.values()) {
    if (options.length >= 4) break;
    if (topic.label !== correct && !options.includes(topic.label)) options.push(topic.label);
  }
  return newCard('daily-card--game', icons.bolt, 'Which section is this?', html`
    <p class="widget-headline">${item.title}</p>
    <div class="opt-list" data-guess data-answer="${correct}">
      ${options.map((option) => html`<button type="button" class="opt" data-guess-option="${option}"><span class="opt__dot"></span>${option}</button>`)}
    </div>
    <p class="daily-card__note" data-guess-note>Guess before you tap.</p>`);
}

function thisOrThatCard(data) {
  const items = (data.widgets?.top || []).slice(0, 2);
  if (items.length < 2) return '';
  const saved = read(KEY.votes, {})[`that-${items[0].id}-${items[1].id}`];
  return newCard('daily-card--game', icons.sparkle, 'Which would you read first?', html`
    <div class="opt-list" data-that="${items[0].id}-${items[1].id}">
      ${items.map((item, index) => html`
        <button type="button" class="opt opt--big ${saved === index ? 'is-on' : ''}" data-that-side="${index}">${item.title}</button>`)}
    </div>
    <p class="daily-card__note">No wrong answer. Tap one to lock it in.</p>`);
}

function journalCard() {
  const store = read('pulse.journal', {});
  const todayKey = new Date().toISOString().slice(0, 10);
  const entry = store[todayKey] || {};
  return newCard('daily-card--journal', icons.note, 'Two-second journal', html`
    <div class="mood-row" data-journal-moods>
      ${['😊', '😐', '😴', '😤', '🤯', '🥳'].map((emoji) => html`
        <button type="button" class="mood ${entry.emoji === emoji ? 'is-on' : ''}" data-journal-mood="${emoji}" aria-label="${emoji}">${emoji}</button>`)}
    </div>
    <textarea data-journal-note rows="2" placeholder="One line about today…" style="margin-top:.4rem">${entry.note || ''}</textarea>
    <button class="btn btn--sm btn--ghost" data-journal-save>Save today</button>
    <p class="daily-card__note" data-journal-status>${entry.emoji ? 'Saved on this device.' : 'Private. Stays on this device.'}</p>`);
}

function streakWidget() {
  const s = streak();
  const progress = dailyProgress();
  return newCard('daily-card--streak', icons.fire, `${s.count}-day streak`, html`
    <div class="widget-stat-row">
      <div><b>${progress.read}</b><span>read today</span></div>
      <div><b>${progress.goal}</b><span>goal</span></div>
    </div>
    <div class="progress"><span style="width:${progress.percent}%"></span></div>`, html`<p class="daily-card__note">${progress.percent >= 100 ? 'Goal smashed. 🔥' : 'One more story keeps it alive.'}</p>`);
}

function xpWidget() {
  const l = levels();
  return newCard('', icons.bolt, `Level ${l.level}`, html`
    <div class="widget-xp">
      ${ring(l.progress.percent)}
      <div><b>${l.xp} XP</b><span>${l.progress.needed - l.progress.into} XP to next</span></div>
    </div>`);
}

function badgeWidget() {
  const badges = state.profile?.badges || [];
  const earned = badges.filter((badge) => badge.earned);
  const next = badges.find((badge) => !badge.earned);
  if (!badges.length) return '';
  return newCard('', icons.trophy, `${earned.length} badges earned`, html`
    ${next ? html`
      <div class="badge-spot">
        <span class="badge-spot__icon">${next.icon}</span>
        <span><b>${next.label}</b><i>${next.hint}</i></span>
      </div>` : html`<p class="daily-card__body">You have them all. Absolute legend.</p>`}`, html`<a class="daily-card__note" href="/profile" data-link>See the collection →</a>`);
}

let miniTimer = null;

function timerWidget() {
  return newCard('daily-card--timer', icons.clock, '5-minute focus', html`
    <div class="widget-timer" data-timer-time>5:00</div>
    <div class="hstack">
      <button class="btn btn--sm btn--primary" data-timer-start>Start</button>
      <button class="btn btn--sm btn--ghost" data-timer-reset>Reset</button>
    </div>
    <p class="daily-card__note" data-timer-note>One tiny task. Phone face down.</p>`);
}

const SLANG_WORDS = [
  ['rizz', 'Charm or flirting skill.'],
  ['sigma', 'A lone-wolf type, usually ironic.'],
  ['sus', 'Suspicious.'],
  ['mid', 'Average or disappointing.'],
  ['slay', 'Do really well.'],
  ['delulu', 'Delusional, usually about a crush.'],
  ['cooked', 'In trouble, or exhausted.'],
  ['aura', 'The vibe or reputation you give off.'],
  ['moots', 'Mutual followers.'],
  ['lowkey', 'Quietly / kind of.'],
  ['highkey', 'Openly / very much.'],
  ['GOAT', 'Greatest of all time.'],
];

function slangWidget() {
  const [term, meaning] = SLANG_WORDS[new Date().getDate() % SLANG_WORDS.length];
  return newCard('', icons.text, 'Slang of the day', html`<p class="widget-slang">${term}</p><p class="daily-card__body">${meaning}</p>`);
}

function nextCard(data) {
  const item = (data.widgets?.next || [])[0];
  if (!item) return '';
  return newCard('', icons.compass, 'Read next', html`${miniStory(item)}`);
}

const TIPS = [
  'A headline is a claim, not a fact. Open the story before you share it.',
  'Two outlets repeating the same wire copy is not two sources.',
  'A photo can be old. Reverse-image search it before believing the caption.',
  'Numbers need units. “Millions” of what, exactly?',
  'If a story makes you furious, that is exactly when to check it.',
  'Look for who is quoted, who is not, and who benefits.',
  'A chart without a labeled axis is decoration, not evidence.',
  '“Sources say” is a start, not a finish.',
  'Screenshots are easy to fake. Find the original post.',
  'A correction is a good sign — it means someone checked.',
  'Opinion pieces are allowed to have opinions. News should show its work.',
  'When a story says “experts”, ask which experts and what they studied.',
];

function tipWidget() {
  return newCard('', icons.info, 'Media literacy tip', html`<p class="daily-card__body">${TIPS[new Date().getDate() % TIPS.length]}</p>`);
}

const ANIMATION_OPTIONS = [
  ['theme', 'Theme'], ['rain', 'Rain'], ['snow', 'Snow'], ['meteors', 'Meteors'],
  ['birds', 'Birds'], ['stars', 'Stars'], ['fireflies', 'Fireflies'], ['petals', 'Petals'], ['none', 'Off'],
];
const NOISE_OPTIONS = [['off', 'Off'], ['white', 'White'], ['pink', 'Pink'], ['brown', 'Brown'], ['rain', 'Rain'], ['waves', 'Waves'], ['wind', 'Wind']];

function ambienceWidget() {
  const p = prefs();
  return newCard('daily-card--ambience', icons.sound, 'Ambience', html`
    <p class="tiny muted">Make the page feel like your room.</p>
    <div class="chip-row" style="margin-top:.4rem">
      ${ANIMATION_OPTIONS.map(([id, label]) => html`
        <button class="chip ${p.animation === id ? 'is-on' : ''}" data-anim="${id}">${label}</button>`)}
    </div>
    <div class="chip-row" style="margin-top:.35rem">
      ${NOISE_OPTIONS.map(([id, label]) => html`
        <button class="chip ${p.noise === id ? 'is-on' : ''}" data-noise="${id}">${label}</button>`)}
    </div>
    <input type="range" data-noise-volume min="0" max="100" value="${Math.round((p.noise_volume || .35) * 100)}" aria-label="Noise volume" style="margin-top:.5rem">
    <p class="daily-card__note">Sound starts when you tap a noise.</p>`);
}

const WIDGETS = [
  { id: 'challenge', label: 'Daily challenge', icon: '⚡', render: (d) => challengeCard(d.challenge) },
  { id: 'word', label: 'Word of the day', icon: '🔤', render: (d) => wordCard(d.word) },
  { id: 'poll', label: 'Your take poll', icon: '🗳️', render: (d) => pollCard(d.poll) },
  { id: 'quiz', label: 'News IQ quiz', icon: '🧠', render: (d) => quizCard(d.quiz) },
  { id: 'debate', label: 'Debate club', icon: '💬', render: (d) => debateCard(d.debate) },
  { id: 'wyr', label: 'Would you rather', icon: '🤔', render: (d) => wyrCard(d.wyr) },
  { id: 'history', label: 'On this day', icon: '🗓️', render: (d) => historyCard(d.history, d.history_label) },
  { id: 'quote', label: 'Quote', icon: '❝', render: (d) => quoteCard(d.quote) },
  { id: 'mood', label: 'Mood check', icon: '🌈', render: () => moodCard() },
  { id: 'top3', label: 'Top 3 right now', icon: '🔥', render: top3Card },
  { id: 'quick', label: 'Under 2 minutes', icon: '⚡', render: quickCard },
  { id: 'longread', label: 'Long read of the day', icon: '📖', render: longReadCard },
  { id: 'good', label: 'One good thing', icon: '✨', render: goodCard },
  { id: 'photo', label: 'Photo of the day', icon: '📷', render: photoCard },
  { id: 'topic', label: 'Topic spotlight', icon: '🧭', render: topicCard },
  { id: 'source', label: 'Source spotlight', icon: '🏛️', render: sourceCard },
  { id: 'most', label: 'Most covered', icon: '📣', render: mostCoveredCard },
  { id: 'sports', label: 'Sports quick hits', icon: '🏆', render: sportsCard },
  { id: 'f1', label: 'F1 & motorsport', icon: '🏎️', render: f1Card },
  { id: 'science', label: 'Science spark', icon: '🔬', render: scienceCard },
  { id: 'culture', label: 'Culture pick', icon: '🎭', render: cultureCard },
  { id: 'numbers', label: 'Number of the day', icon: '🔢', render: numbersCard },
  { id: 'scramble', label: 'Word scramble', icon: '🔤', render: scrambleCard },
  { id: 'guess', label: 'Which section?', icon: '🎯', render: guessCard },
  { id: 'thisorthat', label: 'This or that', icon: '🤔', render: thisOrThatCard },
  { id: 'journal', label: 'Two-second journal', icon: '📝', render: journalCard },
  { id: 'streak', label: 'Streak & goal', icon: '🔥', render: () => streakWidget() },
  { id: 'xp', label: 'Level progress', icon: '⚡', render: () => xpWidget() },
  { id: 'badge', label: 'Badge spotlight', icon: '🏅', render: () => badgeWidget() },
  { id: 'timer', label: '5-minute focus', icon: '⏱️', render: () => timerWidget() },
  { id: 'slang', label: 'Slang of the day', icon: '💬', render: () => slangWidget() },
  { id: 'next', label: 'Read next', icon: '➡️', render: nextCard },
  { id: 'tip', label: 'Media literacy tip', icon: '💡', render: () => tipWidget() },
  { id: 'ambience', label: 'Ambience', icon: '🎧', render: () => ambienceWidget() },
];

export const WIDGET_COUNT = WIDGETS.length;
export const DEFAULT_WIDGET_IDS = DEFAULT_WIDGETS;

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
  bindWidgetEditor(root, data);
  bindScramble(root, data);
  bindGuess(root);
  bindThisOrThat(root);
  bindJournal(root);
  bindTimer(root);
  bindAmbience(root);
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


// --------------------------------------------------------- widget editor
function rerenderWidgets(root, data) {
  const section = root.querySelector('.daily-section');
  if (!section) return;
  const shell = document.createElement('div');
  shell.innerHTML = String(dailySection(data));
  const fresh = shell.firstElementChild;
  section.replaceWith(fresh);
  bindDaily(root, data);
}

function bindWidgetEditor(root, data) {
  root.querySelectorAll('[data-customize-widgets]').forEach((button) => {
    button.addEventListener('click', () => openWidgetEditor(root, data));
  });
}

export function openWidgetEditor(root, data = null) {
  let chosen = [...widgetOrder()];
  const byId = new Map(WIDGETS.map((widget) => [widget.id, widget]));
  const current = () => chosen.map((id) => byId.get(id)).filter(Boolean);
  const available = () => WIDGETS.filter((widget) => !chosen.includes(widget.id));

  const body = html`
    <div class="widget-editor">
      <p class="small muted">Pick what shows on your Today board. Put the fun stuff first — you can change it any time.</p>
      <div class="widget-editor__cols">
        <div>
          <h4 class="widget-editor__title">On your board <span class="tiny faint">${chosen.length}</span></h4>
          <div data-editor-chosen></div>
        </div>
        <div>
          <h4 class="widget-editor__title">Available <span class="tiny faint">${WIDGETS.length - chosen.length}</span></h4>
          <div data-editor-available></div>
        </div>
      </div>
    </div>`;

  const { close } = modal({
    title: 'Edit Today widgets',
    body,
    wide: true,
    actions: [
      { label: 'Cancel', class: 'btn--ghost' },
      {
        label: 'Save board',
        class: 'btn--primary',
        onClick: async () => {
          if (!chosen.length) { toast('Keep at least one widget on the board.', { type: 'bad' }); return false; }
          await savePrefs({ widgets: chosen });
          close();
          if (data && root.querySelector('.daily-section')) rerenderWidgets(root, data);
          toast(`${chosen.length} widgets saved${data ? '' : ' — open Home to see them'}`);
          return true;
        },
      },
    ],
  });

  const chosenEl = document.querySelector('[data-editor-chosen]');
  const availableEl = document.querySelector('[data-editor-available]');

  const paint = () => {
    chosenEl.innerHTML = html`
      ${current().map((widget, index) => html`
        <div class="widget-row is-on">
          <span class="widget-row__icon">${widget.icon}</span>
          <span class="widget-row__label">${widget.label}</span>
          <button type="button" class="widget-row__btn" data-editor-up="${widget.id}" aria-label="Move up" ${index === 0 ? 'disabled' : ''}>↑</button>
          <button type="button" class="widget-row__btn" data-editor-down="${widget.id}" aria-label="Move down" ${index === chosen.length - 1 ? 'disabled' : ''}>↓</button>
          <button type="button" class="widget-row__btn widget-row__btn--remove" data-editor-remove="${widget.id}" aria-label="Remove">✕</button>
        </div>`)}`;
    availableEl.innerHTML = html`
      ${available().map((widget) => html`
        <div class="widget-row">
          <span class="widget-row__icon">${widget.icon}</span>
          <span class="widget-row__label">${widget.label}</span>
          <button type="button" class="btn btn--sm btn--ghost" data-editor-add="${widget.id}">+ Add</button>
        </div>`)}`;
    chosenEl.querySelectorAll('[data-editor-up]').forEach((button) => {
      button.addEventListener('click', () => {
        const index = chosen.indexOf(button.dataset.editorUp);
        if (index > 0) { [chosen[index - 1], chosen[index]] = [chosen[index], chosen[index - 1]]; paint(); }
      });
    });
    chosenEl.querySelectorAll('[data-editor-down]').forEach((button) => {
      button.addEventListener('click', () => {
        const index = chosen.indexOf(button.dataset.editorDown);
        if (index >= 0 && index < chosen.length - 1) {
          [chosen[index + 1], chosen[index]] = [chosen[index], chosen[index + 1]];
          paint();
        }
      });
    });
    chosenEl.querySelectorAll('[data-editor-remove]').forEach((button) => {
      button.addEventListener('click', () => { chosen = chosen.filter((id) => id !== button.dataset.editorRemove); paint(); });
    });
    availableEl.querySelectorAll('[data-editor-add]').forEach((button) => {
      button.addEventListener('click', () => { chosen.push(button.dataset.editorAdd); paint(); });
    });
  };
  paint();
}

// ------------------------------------------------------------- widget binds
function bindScramble(root, data) {
  const form = root.querySelector('[data-scramble-form]');
  if (!form || !data.word) return;
  const input = root.querySelector('[data-scramble-input]');
  const note = root.querySelector('[data-scramble-note]');
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (input.value.trim().toLowerCase() === data.word.word.toLowerCase()) {
      note.textContent = 'Correct! Word of the day: ' + data.word.word;
      confetti(30);
      input.disabled = true;
    } else {
      note.textContent = 'Not quite — try again.';
      input.select();
    }
  });
}

function bindGuess(root) {
  const box = root.querySelector('[data-guess]');
  if (!box) return;
  const note = root.parentElement.querySelector('[data-guess-note]') || root.querySelector('[data-guess-note]');
  box.querySelectorAll('[data-guess-option]').forEach((button) => {
    button.addEventListener('click', () => {
      const correct = button.dataset.guessOption === box.dataset.answer;
      button.classList.toggle('is-on', true);
      box.querySelectorAll('[data-guess-option]').forEach((node) => {
        node.disabled = true;
        if (node.dataset.guessOption === box.dataset.answer) node.classList.add('is-correct');
        else if (node === button) node.classList.add('is-wrong');
      });
      if (note) note.textContent = correct ? 'Yep — that is the section.' : `It was ${box.dataset.answer}.`;
      if (correct) confetti(20);
    });
  });
}

function bindThisOrThat(root) {
  const box = root.querySelector('[data-that]');
  if (!box) return;
  box.querySelectorAll('[data-that-side]').forEach((button) => {
    button.addEventListener('click', () => {
      const votes = read(KEY.votes, {});
      votes[`that-${box.dataset.that}`] = Number(button.dataset.thatSide);
      write(KEY.votes, votes);
      box.querySelectorAll('[data-that-side]').forEach((node) => node.classList.toggle('is-on', node === button));
      confetti(12);
    });
  });
}

function bindJournal(root) {
  const moods = root.querySelector('[data-journal-moods]');
  if (!moods) return;
  const note = root.querySelector('[data-journal-note]');
  const status = root.querySelector('[data-journal-status]');
  let chosen = root.querySelector('[data-journal-mood].is-on')?.dataset.journalMood || '';
  moods.querySelectorAll('[data-journal-mood]').forEach((button) => {
    button.addEventListener('click', () => {
      chosen = button.dataset.journalMood;
      moods.querySelectorAll('[data-journal-mood]').forEach((node) => node.classList.toggle('is-on', node === button));
    });
  });
  root.querySelector('[data-journal-save]')?.addEventListener('click', () => {
    const store = read('pulse.journal', {});
    const key = new Date().toISOString().slice(0, 10);
    store[key] = { emoji: chosen, note: note.value.trim().slice(0, 280) };
    write('pulse.journal', store);
    if (status) status.textContent = 'Saved. Same time tomorrow?';
    toast('Journal saved on this device');
  });
}

function bindTimer(root) {
  const timeEl = root.querySelector('[data-timer-time]');
  if (!timeEl) return;
  if (miniTimer) { clearInterval(miniTimer); miniTimer = null; }
  let remaining = 5 * 60;
  let running = false;
  const note = root.querySelector('[data-timer-note]');
  const paint = () => { timeEl.textContent = `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`; };
  const start = root.querySelector('[data-timer-start]');
  start?.addEventListener('click', () => {
    if (running) {
      clearInterval(miniTimer); miniTimer = null; running = false; start.textContent = 'Resume'; return;
    }
    running = true; start.textContent = 'Pause';
    miniTimer = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(miniTimer); miniTimer = null; running = false; remaining = 0; paint();
        start.textContent = 'Start';
        if (note) note.textContent = 'Done. Stretch, water, one more?';
        confetti(40);
        toast('5 minutes done');
      } else paint();
    }, 1000);
  });
  root.querySelector('[data-timer-reset]')?.addEventListener('click', () => {
    clearInterval(miniTimer); miniTimer = null; running = false; remaining = 5 * 60;
    paint(); start.textContent = 'Start'; if (note) note.textContent = 'One tiny task. Phone face down.';
  });
  paint();
}

function bindAmbience(root) {
  const card = root.querySelector('.daily-card--ambience');
  if (!card) return;
  card.querySelectorAll('[data-anim]').forEach((button) => {
    button.addEventListener('click', async () => {
      card.querySelectorAll('[data-anim]').forEach((node) => node.classList.toggle('is-on', node === button));
      await chooseAnimation(button.dataset.anim);
    });
  });
  card.querySelectorAll('[data-noise]').forEach((button) => {
    button.addEventListener('click', async () => {
      card.querySelectorAll('[data-noise]').forEach((node) => node.classList.toggle('is-on', node === button));
      await chooseNoise(button.dataset.noise);
    });
  });
  const volume = card.querySelector('[data-noise-volume]');
  volume?.addEventListener('change', async () => {
    const value = Number(volume.value) / 100;
    setNoiseVolume(value);
    await savePrefs({ noise_volume: value }).catch(() => {});
  });
}
