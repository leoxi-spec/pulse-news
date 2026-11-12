// Plain-language privacy and terms for a self-hosted Pulse instance.
import { html, raw, icons } from '../ui.js';

function legalShell(title, updated, body) {
  return html`
    <article class="legal">
      <a class="article__back" href="/" data-link>${raw(icons.chevron)} Back to feed</a>
      <p class="eyebrow">Pulse</p>
      <h1>${title}</h1>
      <p class="page-sub">Last updated ${updated}</p>
      ${body}
      <p class="legal__foot">
        <a href="/privacy" data-link>Privacy</a> ·
        <a href="/terms" data-link>Terms</a> ·
        <a href="mailto:support@pulse.local">Contact the operator</a>
      </p>
    </article>`;
}

export function privacyView(root) {
  root.innerHTML = legalShell('Privacy', '11 November 2026', html`
    <section><h2>The short version</h2>
      <p>Pulse is a self-hosted news reader. It has no ads, no third-party analytics, no tracking pixels and no data brokers. The archive and your profile live in a SQLite database on the server you are using — not in a cloud account owned by us.</p>
    </section>
    <section><h2>What is stored</h2>
      <ul>
        <li><b>Reading data:</b> which stories you open, how long you spend, saves, notes, highlights, searches, topics you follow and your reading goal.</li>
        <li><b>Profile:</b> the name you choose, age band, interests, theme and accessibility settings.</li>
        <li><b>Email account (optional):</b> your email address, a PBKDF2 password hash, account creation time, last sign-in time and the linked profile id. Your password itself is never stored.</li>
        <li><b>Session cookie:</b> a random token so you stay signed in for up to 30 days.</li>
        <li><b>News archive:</b> article titles, summaries, extracted text, images and source metadata fetched from publishers.</li>
      </ul>
    </section>
    <section><h2>Cookies</h2>
      <p>Only essential cookies are used: a profile id, a session token if you sign in, and an access token only if the operator has protected this server with one. There are no advertising or analytics cookies.</p>
    </section>
    <section><h2>Video</h2>
      <p>Publisher clips play from the publisher's own player. YouTube videos use the privacy-enhanced <b>youtube-nocookie.com</b> domain and only load when you press play; after that, YouTube's own privacy policy applies. Pulse does not preload or track video playback.</p>
    </section>
    <section><h2>Email accounts and age</h2>
      <p>Email accounts are not exposed in this build. If the operator enables them later, they are for readers aged 13 and over; under-13 readers use guest mode. Email addresses would be recorded but not verified because this self-hosted build has no mail server.</p>
    </section>
    <section><h2>News content</h2>
      <p>Pulse shows previews and, where extraction succeeds, article text for personal reading and study. Copyright and all other rights remain with each publisher. Images are fetched through this server only to display them in the app. “Read the original” always links to the publisher.</p>
    </section>
    <section><h2>AI overviews</h2>
      <p>AI is optional and off unless the operator configures a provider. When enabled, the article text needed for an overview may be sent to that provider. The default summaries are extractive: sentences taken from the article itself, generated on this server.</p>
    </section>
    <section><h2>Your choices</h2>
      <p>You can export your data from Profile, delete individual notes and saves, reset your profile, and delete your account from the Account page. Account deletion removes your email, profile, saves, notes and reading events from this server; the shared news archive remains. Clearing your browser storage removes guest data on that device.</p>
    </section>
    <section><h2>Children</h2>
      <p>Junior and Kids modes filter violent and hard-news stories, hide subscription-only links and simplify the interface. They do not create email accounts for under-13 readers. Parents and guardians can review the age setting from Profile.</p>
    </section>
    <section><h2>Retention and contact</h2>
      <p>Reading data remains until you delete it. Server backups, if the operator makes them, may persist for a short period outside the app. This page is operated by whoever runs this Pulse server; replace the contact address below with a real one before publishing the app.</p>
    </section>
  `);
}

export function termsView(root) {
  root.innerHTML = legalShell('Terms', '11 November 2026', html`
    <section><h2>Using Pulse</h2>
      <p>Pulse is a personal news reader for reading, studying and research. You may use it for personal, non-commercial purposes. Do not use it to redistribute publisher content, scrape at scale, harass people or break the law.</p>
    </section>
    <section><h2>News and accuracy</h2>
      <p>Stories come from third-party publishers. Pulse does not write or independently verify them. Summaries and overviews are aids, not substitutes for the original reporting. Always check the publisher and the date before relying on a claim.</p>
    </section>
    <section><h2>Accounts</h2>
      <p>You are responsible for keeping your password safe. Accounts are for ages 13 and over. Do not share an account in a way that exposes someone else’s reading history. The first account on a server becomes the admin and can see the account list.</p>
    </section>
    <section><h2>Availability</h2>
      <p>This is a self-hosted service provided as-is, without warranties. Feeds, images and scores can fail because publishers or sports providers change their systems. The operator may change, suspend or remove the service.</p>
    </section>
    <section><h2>Content rights</h2>
      <p>All article text, photographs, logos and trademarks belong to their owners. Pulse stores previews and extracted text to make reading and search possible; it does not claim ownership. If you are a rights holder, contact the operator to have content removed.</p>
    </section>
    <section><h2>Changes</h2>
      <p>These terms may change as the app develops. Continued use after a change means you accept the updated terms.</p>
    </section>
  `);
}
