// Seasonal archive: every holiday palette and icon family in one place.
import { get } from '../api.js';
import { html } from '../ui.js';
import { sectionHead } from '../components.js';

function dateLabel(value) {
  if (!value) return 'Upcoming';
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function daysLabel(value) {
  if (!value) return '';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const date = new Date(`${value}T00:00:00`);
  const days = Math.round((date - today) / 86400000);
  if (days === 0) return 'today';
  if (days === 1) return 'tomorrow';
  if (days > 1) return `in ${days} days`;
  return 'archived';
}

export async function seasonsView(root) {
  root.innerHTML = html`<div class="page page--wide"><div class="skeleton-block" style="height:24rem"></div></div>`;
  let data;
  let now;
  try {
    [data, now] = await Promise.all([get('/api/seasons'), get('/api/season')]);
  } catch (err) {
    root.innerHTML = html`<div class="page"><div class="empty"><h2>Seasonal archive is unavailable</h2><p>${err.message}</p></div></div>`;
    return;
  }
  const activeId = now.active?.id || null;
  const next = now.next;
  const seasons = data.seasons || [];
  root.innerHTML = html`
    <div class="page page--wide seasonal-page">
      <header class="page-head">
        <div>
          <p class="eyebrow">The Pulse calendar</p>
          <h1>Every season has a Pulse.</h1>
          <p class="page-lede">Twenty-four holiday themes and matching app icons live here. Pulse switches automatically when the next holiday is within 1.5 weeks; when two windows overlap, the more significant holiday keeps the shared days.</p>
        </div>
      </header>

      <section class="season-now card card-pad">
        <div class="season-now__copy">
          <p class="eyebrow">${activeId ? 'Active now' : 'Regular edition'}</p>
          <h2>${activeId ? now.active.label : 'Pulse — normal'}</h2>
          <p class="muted small">${activeId
            ? now.active.blurb + ' · until ' + dateLabel(now.active.ends)
            : 'No holiday window is open. The classic purple mark is in use.'}</p>
          ${next ? html`<p class="tiny faint">Next: <b>${next.label}</b> · starts ${dateLabel(next.starts)} (${daysLabel(next.starts)})</p>` : ''}
        </div>
        <div class="season-now__art">${activeId
          ? html`<img src="${now.active.icon.small}" alt="${now.active.label} icon">`
          : html`<img src="/icons/icon-192-v24.png" alt="Pulse icon">`}</div>
      </section>

      ${sectionHead('The archive', '', { sub: `${seasons.length} holiday families` })}
      <div class="season-grid">
        ${seasons.map((season) => html`
          <article class="season-card ${season.id === activeId ? 'is-active' : ''}" style="--season-accent:${season.palette['--accent']};--season-accent-2:${season.palette['--accent-2']};--season-bg:${season.palette['--bg']}">
            <div class="season-card__top">
              <img src="${season.icon.small}" alt="${season.label} icon" loading="lazy" width="96" height="96">
              <div>
                <h3>${season.label}</h3>
                <p>${season.blurb}</p>
              </div>
            </div>
            <div class="season-card__foot">
              <span class="season-card__next">${season.next ? dateLabel(season.next.holiday) : 'Dates rotate yearly'}</span>
              <span class="season-card__dots"><i></i><i></i><i></i></span>
            </div>
            ${season.id === activeId ? html`<span class="badge badge--ai season-card__badge">Active</span>` : ''}
          </article>`)}
      </div>

      <p class="tiny faint seasonal-note">Holiday windows are local to this device. The icon archive is used by the installed app and the header mark; the regular icon returns between seasons. You can turn the automatic switch off in Profile &amp; settings.</p>
    </div>`;
}
