import { get, post } from '../api.js';
import { state } from '../store.js';
import { html, raw, icons, toast, errorState, compactNumber, number } from '../ui.js';

const MILESTONES = [
  ['2.7', 'Watch', 'Publisher clips, 30 YouTube newsrooms, a video Shorts stream and a privacy-first player.'],
  ['2.6', 'Access', 'Emoji-free interface, five age bands, 54 widgets and a calmer welcome.'],
  ['2.5', 'Trust', 'Store-readiness, privacy and terms pages, account deletion, focus traps.'],
  ['2.4', 'Habit', 'Watch-time ranking, a shorter navigation and Shorts on the home page.'],
  ['2.0', 'Endless', 'A self-updating Shorts feed with live new-story detection.'],
];

const PRINCIPLES = [
  ['Read, don’t scroll', 'A two-minute brief, finite rows and a “you’re caught up” end state. The product is designed to be put down.'],
  ['Local first', 'The archive, reading history and settings live in SQLite on the reader’s server. No ad network, no data broker.'],
  ['Show the source', 'Every card explains whether the full text is readable here, a preview, or behind a subscription.'],
  ['Build for the classroom', 'Lesson plans, citations, quizzes and media-literacy prompts are first-class features, not add-ons.'],
  ['Make access visible', 'Five age bands, dyslexic-friendly type, high contrast, reduced motion and keyboard navigation.'],
  ['Measure honestly', 'The impact page reports what exists and what this reader did — never invented user counts.'],
];

function download(name, text) {
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function statCard(value, label, hint = '') {
  return html`
    <div class="founder-stat">
      <b>${value}</b>
      <span>${label}</span>
      ${hint ? html`<small>${hint}</small>` : ''}
    </div>`;
}

function bars(rows, { limit = 8, labelKey = 'label', valueKey = 'count' } = {}) {
  if (!rows?.length) return html`<p class="tiny faint">No data yet.</p>`;
  const max = Math.max(...rows.map((row) => Number(row[valueKey]) || 0), 1);
  return html`
    <div class="metric-bars">
      ${rows.slice(0, limit).map((row) => html`
        <div class="metric-row">
          <span>${row[labelKey]}</span>
          <div class="metric-track" aria-hidden="true"><i style="width:${Math.max(4, Math.round((Number(row[valueKey]) / max) * 100))}%"></i></div>
          <b>${compactNumber(row[valueKey])}</b>
        </div>`)}
    </div>`;
}

function founderHero(kicker, title, sub, actions = '') {
  return html`
    <section class="founder-hero">
      <p class="eyebrow">${kicker}</p>
      <h1>${title}</h1>
      <p class="founder-hero__sub">${sub}</p>
      ${actions ? html`<div class="founder-actions">${raw(actions)}</div>` : ''}
      <div class="founder-orbit" aria-hidden="true">
        <span class="founder-orbit__ring founder-orbit__ring--a"></span>
        <span class="founder-orbit__ring founder-orbit__ring--b"></span>
        <span class="founder-orbit__ring founder-orbit__ring--c"></span>
        <span class="founder-orbit__core">Pulse</span>
        <span class="founder-orbit__node" style="--x:82%;--y:18%">sources</span>
        <span class="founder-orbit__node" style="--x:12%;--y:34%">video</span>
        <span class="founder-orbit__node" style="--x:78%;--y:74%">archive</span>
        <span class="founder-orbit__node" style="--x:24%;--y:82%">classroom</span>
      </div>
    </section>`;
}

function caveat() {
  return html`
    <div class="founder-note">
      <b>Honest framing</b>
      <span>Pulse is a single-server student pilot. These figures describe the archive and this reader’s use; they are not a claim of millions of users.</span>
    </div>`;
}

async function loadImpact(root, retry) {
  try {
    return await get('/api/impact', 30);
  } catch (err) {
    errorState(root, err.message, retry);
    return null;
  }
}

function pipeline() {
  return html`
    <div class="pipeline">
      <div class="pipeline__node"><b>Feeds</b><span>488 feeds</span></div>
      <span class="pipeline__arrow" aria-hidden="true"></span>
      <div class="pipeline__node"><b>Extract</b><span>body + video</span></div>
      <span class="pipeline__arrow" aria-hidden="true"></span>
      <div class="pipeline__node"><b>Cluster</b><span>one story</span></div>
      <span class="pipeline__arrow" aria-hidden="true"></span>
      <div class="pipeline__node"><b>Rank</b><span>for this reader</span></div>
      <span class="pipeline__arrow" aria-hidden="true"></span>
      <div class="pipeline__node"><b>Reader</b><span>brief + archive</span></div>
    </div>
    <div class="pipeline__base"><span>SQLite + FTS5, append-only archive</span><span>no ads · no trackers · local-first</span></div>`;
}

function ring(value, label, detail = '') {
  return html`
    <div class="impact-ring" style="--value:${Math.max(0, Math.min(100, Number(value) || 0))}">
      <div class="impact-ring__disc"><b>${value}%</b><span>${label}</span></div>
      ${detail ? html`<small>${detail}</small>` : ''}
    </div>`;
}

function bindFounderMotion(root) {
  const nodes = root.querySelectorAll('.founder-stat, .founder-card, .principle, .timeline__row, .roadmap-card, .lesson-steps > div, .metric-row, .impact-ring');
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    nodes.forEach((node) => node.classList.add('is-in'));
    return;
  }
  if (!('IntersectionObserver' in window)) {
    nodes.forEach((node) => node.classList.add('is-in'));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-in');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  nodes.forEach((node, index) => {
    node.style.setProperty('--delay', `${Math.min(index * 35, 260)}ms`);
    observer.observe(node);
  });
}

// ---------------------------------------------------------------- impact
export async function impactView(root) {
  root.innerHTML = founderHero(
    'Impact · live product data',
    'A small app with measurable habits.',
    'How much news is reachable, how widely it is sourced, what this reader actually finishes, and what the product refuses to do.',
  );
  const data = await loadImpact(root, () => impactView(root));
  if (!data) return;
  const p = data.product;
  const u = data.usage;
  const videos = data.video.total;
  const leanLabels = { left: 'Left', 'center-left': 'Centre-left', center: 'Centre', 'center-right': 'Centre-right', right: 'Right', state: 'State' };

  root.innerHTML = html`
    ${founderHero(
      'Impact · live product data',
      'A small app with measurable habits.',
      'How much news is reachable, how widely it is sourced, what this reader actually finishes, and what the product refuses to do.',
      `<button class="btn btn--primary" id="impact-download">${raw(icons.book)} Download impact report</button>
       <button class="btn" id="impact-print">${raw(icons.printer)} Print</button>
       <a class="btn" href="/about" data-link>About the project ${raw(icons.chevron)}</a>`,
    )}
    <div class="founder-stats">
      ${statCard(compactNumber(p.sources), 'sources', `${p.feeds} feeds`)}
      ${statCard(p.countries, 'countries', `${p.topics} topics`)}
      ${statCard(compactNumber(p.articles), 'articles archived', `${p.archive_years || '—'} years`)}
      ${statCard(compactNumber(videos), 'videos', 'publisher + YouTube')}
      ${statCard(compactNumber(p.readable), 'full-text stories', 'readable in-app')}
      ${statCard(compactNumber(u.server?.minutes || 0), 'minutes read', `across this server · you: ${u.minutes || 0}`)}
    </div>
    <div class="impact-ring-row">
      ${ring(100, 'privacy', 'no ads, no trackers')}
      ${ring(Math.round((p.feeds_ok / Math.max(1, p.feeds_total)) * 100), 'feed health', `${p.feeds_ok}/${p.feeds_total} live`)}
      ${ring(100, 'local', 'archive you own')}
    </div>
    ${caveat()}

    <div class="founder-grid">
      <section class="founder-card">
        <div class="founder-card__head"><h2>Content breadth</h2><span class="badge badge--topic">${p.topics_covered} topics live</span></div>
        ${bars(data.diversity.topics, { limit: 10 })}
      </section>
      <section class="founder-card">
        <div class="founder-card__head"><h2>Where the news comes from</h2><span class="badge badge--topic">${p.countries} countries</span></div>
        ${bars(data.diversity.countries, { limit: 10, labelKey: 'country', valueKey: 'n' })}
      </section>
      <section class="founder-card">
        <div class="founder-card__head"><h2>Editorial spread</h2><span class="badge badge--topic">catalogue view</span></div>
        ${bars(data.diversity.leans.map((row) => ({ ...row, label: leanLabels[row.lean] || row.lean })), { limit: 6, valueKey: 'n' })}
      </section>
      <section class="founder-card">
        <div class="founder-card__head"><h2>What this reader did</h2><span class="badge badge--topic">private</span></div>
        <div class="founder-mini-stats">
          <div><b>${compactNumber(u.articles || 0)}</b><span>stories opened</span></div>
          <div><b>${compactNumber(u.topics || 0)}</b><span>topics</span></div>
          <div><b>${compactNumber(u.sources || 0)}</b><span>sources</span></div>
          <div><b>${compactNumber(u.streak?.count || 0)}</b><span>day streak</span></div>
        </div>
        <p class="tiny muted" style="margin-top:.8rem">Reading time, quiz answers and citations stay on this server. Nothing is sent to an ad network.</p>
      </section>
    </div>

    <section class="founder-section">
      <div class="section-head"><h2>What this proves</h2><span class="tiny muted">for a college application, without the hype</span></div>
      <div class="principle-grid">
        <article class="principle"><h3>Content operations</h3><p>Ingesting ${p.feeds} feeds, classifying ${p.articles} articles, clustering stories and keeping ${p.feeds_ok}/${p.feeds_total} feeds healthy is an operations problem, not a mock-up.</p></article>
        <article class="principle"><h3>Media literacy</h3><p>Country, topic, ownership and editorial-lean context sit next to the story, so comparing coverage is one click instead of a research project.</p></article>
        <article class="principle"><h3>Technical depth</h3><p>SQLite FTS5, incremental ingestion, append-only archives, ${data.quality.tests} tests and zero third-party JavaScript frameworks.</p></article>
        <article class="principle"><h3>Product judgement</h3><p>A finite brief, a “caught up” state, honest access labels and a public roadmap show what was deliberately left out.</p></article>
      </div>
    </section>

    <section class="founder-section">
      <div class="section-head"><h2>Product quality</h2><span class="tiny muted">verified, not claimed</span></div>
      <div class="founder-grid founder-grid--three">
        <div class="founder-card"><h3>Engineering</h3><ul class="checklist"><li>${data.quality.tests} automated tests</li><li>${data.quality.third_party_js} third-party JS frameworks</li><li>${data.quality.runtime}</li><li>${data.quality.storage}</li></ul></div>
        <div class="founder-card"><h3>Privacy</h3><ul class="checklist"><li>${data.privacy.ads} ads</li><li>${data.privacy.trackers} trackers</li><li>${data.privacy.data_sold} data sold</li><li>${data.privacy.accounts_required ? 'Account required' : 'No account required'}</li></ul></div>
        <div class="founder-card"><h3>Reach</h3><ul class="checklist"><li>${p.countries} countries</li><li>${p.topics} topics</li><li>${compactNumber(videos)} videos</li><li>${p.archive_years || '—'} years of archive</li></ul></div>
      </div>
    </section>

    <section class="founder-section">
      <div class="section-head"><h2>How this is measured</h2><span class="tiny muted">reproducible</span></div>
      <div class="founder-card founder-card--wide">
        <p class="small muted">The report is generated from the same SQLite database the app serves. It counts rows, sources, topics, videos, full-text extraction and this profile’s own reading events. Re-run it any time with the button at the top of this page.</p>
        <div class="hstack" style="flex-wrap:wrap;margin-top:.8rem">
          <a class="btn btn--sm btn--ghost" href="/roadmap" data-link>${raw(icons.sparkle)} Roadmap and feedback</a>
          <a class="btn btn--sm btn--ghost" href="/classroom" data-link>${raw(icons.book)} Classroom toolkit</a>
        </div>
      </div>
    </section>`;

  const downloadReport = async () => {
    try {
      const report = await get('/api/impact/report', 20);
      download(report.filename || 'pulse-impact-report.md', report.markdown);
      toast('Impact report downloaded');
    } catch (err) { toast(err.message, { type: 'bad' }); }
  };
  root.querySelector('#impact-download')?.addEventListener('click', downloadReport);
  root.querySelector('#impact-print')?.addEventListener('click', () => window.print());
  bindFounderMotion(root);
}

// ----------------------------------------------------------------- about
export async function aboutView(root) {
  const data = await get('/api/impact', 30).catch(() => null);
  const p = data?.product || { sources: state.boot?.catalog?.sources || 366, countries: 51, topics: 20, videos: 0 };
  root.innerHTML = html`
    ${founderHero(
      'The project',
      'The news, without the noise.',
      'Pulse is an independent student-built news app: broad sourcing, a permanent archive, video, classroom tools and a business model that does not depend on attention.',
      `<a class="btn btn--primary" href="/impact" data-link>See the live impact report ${raw(icons.chevron)}</a>
       <button class="btn" id="press-kit">${raw(icons.book)} Download press kit</button>
       <a class="btn" href="/classroom" data-link>Classroom toolkit</a>`,
    )}
    <div class="founder-stats">
      ${statCard(compactNumber(p.sources), 'sources', `${p.feeds || '—'} feeds`)}
      ${statCard(p.countries, 'countries', `${p.topics} topics`)}
      ${statCard(compactNumber(p.videos || 0), 'videos', 'newsrooms + YouTube')}
      ${statCard(compactNumber(p.articles || 0), 'articles archived', 'append-only')}
    </div>

    <div class="founder-grid">
      <section class="founder-card founder-card--wide">
        <h2>The problem</h2>
        <p>Students are expected to know what is happening, compare sources and form an argument — often with a phone, a paywall and a feed designed to keep them scrolling. The result is a lot of noise and very little context.</p>
        <p>Teachers face the same problem from the other side: current events are valuable, but assembling a readable, sourced, ad-free lesson takes time they do not have.</p>
      </section>
      <section class="founder-card">
        <h2>The product</h2>
        <ul class="checklist">
          <li>A personalised front page with a finite two-minute brief</li>
          <li>${p.sources} sources, ${p.countries} countries, ${p.topics} topics</li>
          <li>Publisher and YouTube video in the article and in Shorts</li>
          <li>A permanent, searchable archive with citations</li>
          <li>Quizzes, study tools and a 45-minute classroom lesson</li>
        </ul>
      </section>
      <section class="founder-card">
        <h2>How it works</h2>
        <p>Python standard library on the server, SQLite with WAL and FTS5, and vanilla ES modules in the browser. Feeds are fetched incrementally, article bodies are extracted, stories are clustered, and the archive is append-only.</p>
        <p class="tiny muted">No Node build step. No third-party JavaScript framework. One machine can serve it.</p>
      </section>
    </div>

    <section class="founder-section">
      <div class="section-head"><h2>The system, end to end</h2><span class="tiny muted">one machine, no cloud bill</span></div>
      ${pipeline()}
    </section>

    <section class="founder-section">
      <div class="section-head"><h2>Product principles</h2><span class="tiny muted">what I said no to</span></div>
      <div class="principle-grid">
        ${PRINCIPLES.map(([title, text]) => html`<article class="principle"><h3>${title}</h3><p>${text}</p></article>`)}
      </div>
    </section>

    <section class="founder-section">
      <div class="section-head"><h2>Business model</h2><span class="tiny muted">small, honest, sustainable</span></div>
      <div class="founder-grid founder-grid--three">
        <article class="founder-card"><h3>Free for students</h3><p>No ads, no trackers and no paywall. The reader owns the archive and can export or delete their data.</p></article>
        <article class="founder-card"><h3>School pilot</h3><p>A future licence could cover teacher dashboards, class codes, offline packs and SSO. Schools pay for administration and support, not for student attention.</p></article>
        <article class="founder-card"><h3>Low cost to run</h3><p>One server, SQLite and static assets. No per-user cloud bill, no ad network and no data broker. The economics match the mission.</p></article>
      </div>
    </section>

    <section class="founder-section">
      <div class="section-head"><h2>What I learned</h2><span class="tiny muted">the short version</span></div>
      <div class="founder-grid">
        <article class="founder-card"><h3>Engineering</h3><p>Real feeds are messy. The work is in retries, date confidence, duplicate stories, extraction fallbacks and making a 40,000-article archive feel instant.</p></article>
        <article class="founder-card"><h3>Product</h3><p>The hardest feature is the end state. A news app that respects a student has to know when to say “you’re caught up” and stop.</p></article>
        <article class="founder-card"><h3>Research</h3><p>Every design choice — reading labels, age bands, citation tools — came from watching how students actually use news for class, not from a growth metric.</p></article>
      </div>
    </section>

    <section class="founder-section">
      <div class="section-head"><h2>Built in public</h2><span class="tiny muted">recent milestones</span></div>
      <div class="timeline">
        ${MILESTONES.map(([version, title, text]) => html`
          <div class="timeline__row">
            <b>${version}</b>
            <div><h3>${title}</h3><p>${text}</p></div>
          </div>`)}
      </div>
    </section>

    <section class="founder-section">
      <div class="founder-card founder-card--wide">
        <h2>Use the project</h2>
        <p class="small muted">Read the impact report, try a classroom lesson, vote on the roadmap, or send feedback. The press kit is a one-page summary you can share with a teacher, a newsroom or an admissions interviewer.</p>
        <div class="hstack" style="flex-wrap:wrap;margin-top:.8rem">
          <a class="btn btn--primary" href="/roadmap" data-link>Roadmap and feedback</a>
        </div>
      </div>
    </section>`;

  root.querySelector('#press-kit')?.addEventListener('click', async () => {
    try {
      const kit = await get('/api/press-kit', 20);
      download(kit.filename || 'pulse-press-kit.md', kit.markdown);
      toast('Press kit downloaded');
    } catch (err) { toast(err.message, { type: 'bad' }); }
  });
  bindFounderMotion(root);
}

// ------------------------------------------------------------- classroom
export async function classroomView(root) {
  root.innerHTML = html`
    ${founderHero(
      'Classroom toolkit',
      'One class period. One news habit.',
      'A 45-minute lesson that uses today’s news to practise reading, source comparison, discussion and citation. Printable, ad-free and adaptable for ages 11–18.',
      `<button class="btn btn--primary" id="print-lesson">${raw(icons.printer)} Print the lesson</button>
       <a class="btn" href="/brief" data-link>Open today’s brief ${raw(icons.chevron)}</a>
       <a class="btn" href="/roadmap" data-link>Pilot feedback</a>`,
    )}
    <div class="founder-grid">
      <section class="founder-card founder-card--wide">
        <div class="founder-card__head"><h2>The 45-minute lesson</h2><span class="badge badge--topic">Teacher-ready</span></div>
        <div class="lesson-steps">
          <div><b>5 min</b><h3>Warm-up</h3><p>Ask: what is one story you have heard about this week, and where did you hear it? Write the sources on the board.</p></div>
          <div><b>10 min</b><h3>Read</h3><p>Students open the two-minute brief and choose one story. They note the publisher, date, main claim and one fact they can verify.</p></div>
          <div><b>10 min</b><h3>Compare</h3><p>Open the story’s coverage timeline. Compare two outlets: what is the same, what is different, and what does each lead with?</p></div>
          <div><b>10 min</b><h3>Discuss</h3><p>Use the discussion questions below in pairs or small groups. Require one citation from the article in every answer.</p></div>
          <div><b>10 min</b><h3>Exit ticket</h3><p>Write a three-sentence summary in your own words, then generate an MLA and APA citation in Pulse.</p></div>
        </div>
      </section>
      <section class="founder-card">
        <h2>Discussion questions</h2>
        <ol class="numbered">
          <li>What is the central claim, and which sentence supports it most directly?</li>
          <li>Who is quoted, and who is missing from the story?</li>
          <li>How does the headline frame the story differently from the first paragraph?</li>
          <li>What would change your mind about this story?</li>
          <li>Why might another outlet cover it differently?</li>
        </ol>
      </section>
      <section class="founder-card">
        <h2>Media-literacy checklist</h2>
        <ul class="checklist">
          <li>I can name the publisher and the date.</li>
          <li>I found the original claim, not just a screenshot.</li>
          <li>I checked whether the story is news, analysis or opinion.</li>
          <li>I compared at least two outlets.</li>
          <li>I looked for the evidence behind the strongest number.</li>
          <li>I can explain what the story does not tell me.</li>
        </ul>
      </section>
    </div>

    <section class="founder-section">
      <div class="section-head"><h2>Citation drill</h2><span class="tiny muted">practice, not plagiarism</span></div>
      <div class="founder-grid">
        <article class="founder-card"><h3>MLA 9</h3><p class="citation-sample">Author. “Title.” <i>Publisher</i>, date, URL.</p><p class="tiny muted">Use the Cite button on any article; Pulse fills in the date and publisher.</p></article>
        <article class="founder-card"><h3>APA 7</h3><p class="citation-sample">Author. (Year, Month Day). Title. <i>Publisher</i>. URL</p><p class="tiny muted">Switch styles in the article’s Cite dialog; copy or download the bibliography.</p></article>
        <article class="founder-card"><h3>Discussion routine</h3><p class="citation-sample">Claim → Evidence → Interpretation → Question</p><p class="tiny muted">Students state a claim, cite a line, explain its meaning, then ask what is still unresolved.</p></article>
      </div>
    </section>

    <section class="founder-section">
      <div class="founder-card founder-card--wide">
        <h2>Run a pilot</h2>
        <p class="small muted">Try the lesson with one class, then send feedback through the roadmap. The next build is prioritised around teacher and student responses, not vanity metrics.</p>
        <div class="hstack" style="flex-wrap:wrap;margin-top:.8rem">
          <a class="btn" href="/about" data-link>About the project</a>
        </div>
      </div>
    </section>`;
  root.querySelector('#print-lesson')?.addEventListener('click', () => window.print());
  bindFounderMotion(root);
}

// --------------------------------------------------------------- roadmap
export async function roadmapView(root) {
  root.innerHTML = founderHero(
    'Roadmap · build it with me',
    'The next version is a conversation.',
    'Vote on what matters, request a source, or tell me what broke. Feedback is stored in this server’s database and read before the next release.',
  );
  const data = await get('/api/roadmap', 30).catch((err) => {
    errorState(root, err.message, () => roadmapView(root));
    return null;
  });
  if (!data) return;
  root.innerHTML = html`
    ${founderHero(
      'Roadmap · build it with me',
      'The next version is a conversation.',
      'Vote on what matters, request a source, or tell me what broke. Feedback is stored in this server’s database and read before the next release.',
      `<a class="btn btn--primary" href="#feedback">${raw(icons.note)} Send feedback</a>
       <a class="btn" href="/impact" data-link>Impact report ${raw(icons.chevron)}</a>`,
    )}
    <div class="founder-stats">
      ${statCard(data.items.length, 'roadmap items', 'public')}
      ${statCard(compactNumber(data.items.reduce((sum, item) => sum + item.votes, 0)), 'votes', 'this server')}
      ${statCard('0', 'accounts required', 'local-first')}
    </div>
    <div class="roadmap-list">
      ${data.items.map((item) => html`
        <article class="roadmap-card" data-roadmap="${item.id}">
          <div class="roadmap-card__head">
            <div>
              <span class="badge badge--topic">${item.area}</span>
              <span class="badge ${item.stage === 'Now' ? 'badge--breaking' : 'badge--muted'}">${item.stage}</span>
            </div>
            <button class="vote-btn ${item.voted ? 'is-on' : ''}" data-vote="${item.id}" aria-pressed="${item.voted}">
              ${raw(icons.sparkle)} <b data-votes>${item.votes}</b><span>${item.voted ? 'Voted' : 'Vote'}</span>
            </button>
          </div>
          <h3>${item.title}</h3>
          <p>${item.summary}</p>
        </article>`)}
    </div>
    <section class="founder-section" id="feedback">
      <div class="section-head"><h2>Send feedback</h2><span class="tiny muted">feature, bug, source, classroom pilot</span></div>
      <form class="feedback-form" id="feedback-form">
        <label>Category
          <select name="category">
            ${Object.entries(data.categories).map(([id, label]) => html`<option value="${id}">${label}</option>`)}
          </select>
        </label>
        <label>What should change?
          <textarea name="message" rows="5" maxlength="4000" placeholder="A source that should be included, a bug, or a classroom idea…" required></textarea>
        </label>
        <label>Email (optional)
          <input name="email" type="email" maxlength="200" placeholder="Only if you want a reply">
        </label>
        <div class="hstack" style="align-items:center;justify-content:space-between;flex-wrap:wrap">
          <span class="tiny faint">Stored on this server only. No account, no newsletter.</span>
          <button class="btn btn--primary" type="submit">${raw(icons.note)} Send feedback</button>
        </div>
      </form>
    </section>`;

  root.querySelectorAll('[data-vote]').forEach((button) => {
    button.addEventListener('click', async () => {
      const card = button.closest('[data-roadmap]');
      const next = !button.classList.contains('is-on');
      button.disabled = true;
      try {
        const result = await post('/api/roadmap/vote', { id: button.dataset.vote, on: next });
        button.classList.toggle('is-on', result.item.voted);
        button.setAttribute('aria-pressed', String(result.item.voted));
        button.querySelector('[data-votes]').textContent = String(result.item.votes);
        button.querySelector('span').textContent = result.item.voted ? 'Voted' : 'Vote';
        if (card) card.classList.toggle('is-voted', result.item.voted);
        toast(result.item.voted ? 'Vote counted' : 'Vote removed');
      } catch (err) {
        toast(err.message, { type: 'bad' });
      } finally {
        button.disabled = false;
      }
    });
  });

  root.querySelector('#feedback-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const result = await post('/api/feedback', {
        category: form.category.value,
        message: form.message.value,
        email: form.email.value,
      });
      form.reset();
      toast(`Feedback sent — ${result.total} total on this server`);
    } catch (err) {
      toast(err.message, { type: 'bad' });
    } finally {
      button.disabled = false;
    }
  });
  bindFounderMotion(root);
}
