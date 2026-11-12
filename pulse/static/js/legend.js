// Reading key: explains every label and control without decorative symbols.
import { html, raw, modal } from './ui.js';

const GROUPS = [
  {
    title: 'Can I read it here?',
    items: [
      ['Read here', 'The full article text is stored and readable inside Pulse. Shown with a green dot.'],
      ['Preview', 'You get the summary and overview; the source link opens the publisher. Shown with an amber dot.'],
      ['Subscription', 'The publisher requires a paid subscription. Pulse shows the preview and links out. Shown with a grey dot.'],
    ],
  },
  {
    title: 'Overviews',
    items: [
      ['Auto summary', 'Extractive: sentences taken directly from the article. No model involved.'],
      ['AI overview', 'Only appears when the server operator has configured an AI provider; grounded in this article only.'],
      ['Why it matters', 'A consequence stated in the article, or a note on how many outlets covered it.'],
    ],
  },
  {
    title: 'Stories and coverage',
    items: [
      ['Breaking', 'Very recent and being reported by several outlets.'],
      ['Top story', 'Ranked highly by how many outlets are covering it.'],
      ['N outlets', 'How many separate publications covered the same event.'],
      ['Lean bar', 'Approximate editorial spread of the coverage. It is not a verdict on accuracy.'],
    ],
  },
  {
    title: 'Video',
    items: [
      ['Video badge', 'The story has a clip. Open it to watch without leaving Pulse.'],
      ['YouTube', 'Played through the privacy-enhanced youtube-nocookie.com player, only after you press play.'],
      ['Watch', 'A dedicated stream of newsroom clips, highlights and explainers.'],
    ],
  },
  {
    title: 'Scores',
    items: [
      ['Live', 'Game in progress; scores refresh every 30 seconds.'],
      ['Final', 'Game finished.'],
      ['Upcoming', 'Scheduled; times are shown in your local timezone.'],
      ['Followed', 'A team or league you follow, highlighted in the scoreboard.'],
    ],
  },
  {
    title: 'Your progress',
    items: [
      ['Streak', 'Consecutive days you read at least one story.'],
      ['XP and level', 'Earned by reading, saving, quizzes and completing briefs.'],
      ['Badge', 'Milestones such as a 7-day streak or 100 stories read.'],
      ['Saved', 'Stored in your library and available for citations.'],
    ],
  },
  {
    title: 'Actions',
    items: [
      ['Save', 'Keep a story for later, revision or a bibliography.'],
      ['Notes', 'Highlight a sentence and attach your own note.'],
      ['Cite', 'MLA, APA, Chicago, Harvard or BibTeX, with dates filled in.'],
      ['Quiz', 'Questions built from the article’s own sentences.'],
      ['Focus', 'Hides navigation for distraction-free reading.'],
      ['Source', 'Opens the original at the publisher.'],
    ],
  },
];

export function openLegend() {
  const body = document.createElement('div');
  body.innerHTML = html`
    <p class="small muted" style="margin-bottom:1rem">Every label in Pulse, explained. Reading labels appear on every card so you always know whether a story opens here or at the publisher.</p>
    <div class="legend-grid">
      ${GROUPS.map((group) => html`
        <section class="legend-group">
          <h3>${group.title}</h3>
          ${group.items.map(([label, description]) => html`
            <div class="legend-item">
              <span><b>${label}</b><span class="legend-item__desc">${description}</span></span>
            </div>`)}
        </section>`)}
    </div>
    <p class="tiny faint" style="margin-top:1rem">Keyboard: <kbd class="kbd">⌘K</kbd> search, <kbd class="kbd">/</kbd> search, <kbd class="kbd">?</kbd> this key, <kbd class="kbd">esc</kbd> close.</p>`;
  const box = modal({
    title: 'Reading key',
    wide: true,
    body,
    actions: [{ label: 'Got it', class: 'btn--primary' }],
  });
  void box;
  void raw;
}
