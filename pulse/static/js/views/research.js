import { get, post } from '../api.js';
import { html, raw, icons, toast, modal, copyText, errorState, emptyState, absDate } from '../ui.js';
import { sectionHead } from '../components.js';

const STYLE_LABELS = { mla: 'MLA 9', apa: 'APA 7', chicago: 'Chicago', harvard: 'Harvard', bibtex: 'BibTeX', plain: 'Plain' };

export async function researchView(root, ctx) {
  let style = ['mla', 'apa', 'chicago', 'harvard', 'bibtex'].includes(ctx.query.style) ? ctx.query.style : 'mla';
  const manual = [];
  root.innerHTML = html`
    <div class="research-hero">
      <p class="eyebrow">For essays, projects & debates</p>
      <h1>Research desk</h1>
      <p class="muted small" style="margin-top:.4rem;max-width:60ch">Every story you save can become a properly formatted source. Pick a style, copy the list, and add anything else you're citing by hand.</p>
    </div>

    <div class="between" style="margin:1.1rem 0 .3rem">
      <div class="segmented" id="style-picker" role="tablist" aria-label="Citation style">
        ${Object.entries(STYLE_LABELS).map(([id, label]) => html`
          <button type="button" role="tab" aria-selected="${style === id}" class="${style === id ? 'is-on' : ''}" data-style="${id}">${label}</button>`)}
      </div>
      <div class="research-actions">
        <button class="btn btn--sm btn--ghost" id="add-source">${raw(icons.note)} Add a source</button>
        <button class="btn btn--sm btn--ghost" id="copy-all">${raw(icons.quote)} Copy all</button>
        <button class="btn btn--sm btn--ghost" id="download">${raw(icons.external)} Download</button>
      </div>
    </div>

    <div id="research-body" class="section">
      <div class="skeleton skeleton--card" style="height:120px"></div>
    </div>
    <div id="manual-slot" class="section"></div>
    <div class="card card-pad" style="margin-top:1.4rem;border-style:dashed">
      <p class="tiny muted"><b>Before you submit:</b> check each entry against your school's citation guide. Pulse fills in the publisher's date and today's access date, but always verify the author and title. Paywalled and preview-only sources are still citable — the citation links to the original.</p>
    </div>`;

  let current = null;

  async function load() {
    const body = root.querySelector('#research-body');
    body.innerHTML = html`<div class="skeleton skeleton--card" style="height:140px"></div>`;
    try {
      current = await get(`/api/research/bibliography?style=${style}&include_notes=1`, 0, true);
      renderBody();
    } catch (err) {
      errorState(body, err.message, load);
    }
  }

  function renderBody() {
    const body = root.querySelector('#research-body');
    if (!current) return;
    if (!current.entries.length && !manual.length) {
      body.innerHTML = emptyState({
        icon: '📚',
        title: 'No sources yet',
        text: 'Save a story from the feed and it will appear here, formatted and ready to paste. You can also add a book or website by hand.',
        action: '<a class="btn btn--primary" href="/" data-link>Find a story</a>',
      });
      return;
    }
    body.innerHTML = html`
      ${sectionHead(`${current.entries.length + manual.length} saved source${current.entries.length + manual.length === 1 ? '' : 's'}`, html`<span class="tiny muted">${STYLE_LABELS[style]}</span>`)}
      <div class="stack-sm">
        ${current.entries.map((entry, index) => html`
          <div class="citation-item card card-pad">
            <div class="citation-item__head">
              <span class="citation-item__title">${index + 1}. ${entry.title}</span>
              <span class="hstack" style="gap:.3rem">
                <a class="btn btn--sm btn--ghost" href="/article/${entry.article_id}" data-link>Open</a>
                <button class="btn btn--sm btn--ghost" data-copy="${index}">Copy</button>
              </span>
            </div>
            <div class="citation-box">${entry.citation}</div>
            <div class="citation-item__source" style="margin-top:.35rem">${entry.source}${entry.collection ? ` · ${entry.collection}` : ''}</div>
          </div>`)}
        ${manual.map((entry, index) => html`
          <div class="citation-item card card-pad">
            <div class="citation-item__head">
              <span class="citation-item__title">${current.entries.length + index + 1}. ${entry.fields.title}</span>
              <button class="btn btn--sm btn--ghost" data-copy-manual="${index}">Copy</button>
            </div>
            <div class="citation-box">${entry.citations[style] || entry.citations.mla}</div>
            <div class="citation-item__source" style="margin-top:.35rem">Added manually</div>
          </div>`)}
      </div>
      ${current.notes?.length ? html`
        <div class="section">
          ${sectionHead('Quotes from your notes', html`<span class="tiny muted">${current.notes.length}</span>`)}
          <div class="stack-sm">
            ${current.notes.map((note) => html`
              <div class="card card-pad">
                ${note.quote ? html`<div class="note__quote">“${note.quote}”</div>` : ''}
                <div class="small">${note.body}</div>
                <div class="citation-item__source" style="margin-top:.4rem">${note.citation}</div>
              </div>`)}
          </div>
        </div>` : ''}`;

    body.querySelectorAll('[data-copy]').forEach((button) => {
      button.addEventListener('click', async () => {
        const entry = current.entries[Number(button.dataset.copy)];
        const ok = await copyText(entry.citation);
        toast(ok ? 'Citation copied' : 'Copy failed', { type: ok ? 'good' : 'bad' });
      });
    });
    body.querySelectorAll('[data-copy-manual]').forEach((button) => {
      button.addEventListener('click', async () => {
        const entry = manual[Number(button.dataset.copyManual)];
        const ok = await copyText(entry.citations[style] || entry.citations.mla);
        toast(ok ? 'Citation copied' : 'Copy failed', { type: ok ? 'good' : 'bad' });
      });
    });
  }

  function combinedText() {
    const parts = [];
    if (current) parts.push(...current.entries.map((entry) => entry.citation));
    manual.forEach((entry) => parts.push(entry.citations[style] || entry.citations.mla));
    return parts.join('\n\n');
  }

  root.querySelectorAll('[data-style]').forEach((button) => {
    button.addEventListener('click', () => {
      style = button.dataset.style;
      root.querySelectorAll('[data-style]').forEach((node) => {
        node.classList.toggle('is-on', node === button);
        node.setAttribute('aria-selected', String(node === button));
      });
      load();
    });
  });

  root.querySelector('#copy-all').addEventListener('click', async () => {
    const text = combinedText();
    if (!text) { toast('Nothing to copy yet', { type: 'bad' }); return; }
    const ok = await copyText(text);
    toast(ok ? 'Bibliography copied' : 'Copy failed', { type: ok ? 'good' : 'bad' });
  });

  root.querySelector('#download').addEventListener('click', () => {
    const text = combinedText();
    if (!text) { toast('Nothing to download yet', { type: 'bad' }); return; }
    const extension = style === 'bibtex' ? 'bib' : 'txt';
    const blob = new Blob([text + '\n'], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `pulse-bibliography-${style}.${extension}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    toast('Bibliography downloaded', { type: 'good' });
  });

  root.querySelector('#add-source').addEventListener('click', () => openManual(style));

  function openManual(defaultStyle) {
    const form = document.createElement('div');
    form.innerHTML = html`
      <div class="stack-sm">
        <label class="tiny muted" for="m-title">Title *</label>
        <input id="m-title" type="text" placeholder="Article, chapter or page title" maxlength="300">
        <div class="grid-2">
          <div><label class="tiny muted" for="m-author">Author</label><input id="m-author" type="text" placeholder="Jane Doe" maxlength="200"></div>
          <div><label class="tiny muted" for="m-outlet">Publisher / site</label><input id="m-outlet" type="text" placeholder="Example Press" maxlength="200"></div>
        </div>
        <div class="grid-2">
          <div><label class="tiny muted" for="m-date">Date</label><input id="m-date" type="date"></div>
          <div><label class="tiny muted" for="m-url">URL</label><input id="m-url" type="url" placeholder="https://…" maxlength="1200"></div>
        </div>
        <p class="tiny faint">Books and offline sources: leave the URL empty and put the publisher in “Publisher”.</p>
      </div>`;
    modal({
      title: 'Add a source',
      wide: true,
      body: form,
      actions: [
        { label: 'Cancel', class: 'btn--ghost' },
        {
          label: 'Add citation',
          class: 'btn--primary',
          onClick: async () => {
            const title = form.querySelector('#m-title').value.trim();
            if (title.length < 2) { toast('Add a title first', { type: 'bad' }); return false; }
            try {
              const result = await post('/api/research/cite', {
                title,
                author: form.querySelector('#m-author').value.trim(),
                outlet: form.querySelector('#m-outlet').value.trim(),
                published_at: form.querySelector('#m-date').value || '',
                url: form.querySelector('#m-url').value.trim(),
              });
              manual.push({
                fields: {
                  title,
                  author: form.querySelector('#m-author').value.trim(),
                  outlet: form.querySelector('#m-outlet').value.trim(),
                  published_at: form.querySelector('#m-date').value || '',
                  url: form.querySelector('#m-url').value.trim(),
                },
                citations: result.citations,
              });
              renderBody();
              toast('Source added', { type: 'good' });
            } catch (err) {
              toast(err.message, { type: 'bad' });
              return false;
            }
            return true;
          },
        },
      ],
    });
    void defaultStyle;
  }

  await load();
  void absDate;
}
