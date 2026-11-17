// `/dossiers/{domain}`: state, the six fields with value, status and citations; refresh and reload.
// Reads carry a sequence number and only a newer read may replace what is shown (latest read wins);
// while the dossier is building it is read again every second until it is ready or failed.
import { newKey, read, write, errorText } from '../api.js';
import { h, message, replace } from '../dom.js';
import {
  FIELDS, FIELD_LABELS, dataValue, formatTimestamp, formatValue, hostOf, providerLabel, statusLabel, unitsLabel,
} from '../format.js';

const POLL_MS = 1000;

export function notFound(main, raw) {
  replace(main, h('section', { class: 'panel empty', testid: 'dossier-not-found' },
    h('h1', {}, 'No dossier for this domain'),
    h('p', {}, `There is no dossier for “${raw}”. It may not have been researched yet, or the address is not a valid domain.`),
    h('a', { href: '/', class: 'btn btn-primary' }, 'Go to the dossier list')));
}

function citation(field, c, n) {
  return h('li', { class: 'citation', testid: `citation-${field}-${n}`, 'data-provider': c.provider },
    h('blockquote', { class: 'excerpt' }, h('p', {}, `“${c.excerpt}”`)),
    h('p', { class: 'citation-source' },
      h('a', { href: c.url, rel: 'noopener noreferrer', target: '_blank' }, hostOf(c.url)),
      h('span', { class: 'muted' }, ` · via ${providerLabel(c.provider)}`)));
}

function fieldCard(field, f) {
  const known = f.value !== null && f.value !== undefined;
  return h('article', { class: `field field-${f.status}`, testid: `field-${field}`, 'data-status': f.status },
    h('div', { class: 'field-head' },
      h('h3', { class: 'field-label' }, FIELD_LABELS[field]),
      h('span', { class: `pill pill-${f.status}` }, statusLabel(f.status)),
      f.status === 'contested'
        ? h('span', { class: 'contested-flag', testid: `field-contested-${field}` }, 'Sources disagree')
        : null),
    known
      ? h('p', { class: 'field-value', testid: `field-value-${field}`, 'data-value': dataValue(f.value) }, formatValue(field, f.value))
      : h('p', { class: 'field-value field-value-none' }, 'No supported value found'),
    h('ol', { class: 'citations', testid: `field-citations-${field}`, 'aria-label': `Sources for ${FIELD_LABELS[field]}` },
      f.citations.map((c, i) => citation(field, c, i + 1))));
}

export function dossierScreen(main, raw) {
  document.title = 'Dossier';
  const view = { data: null, applied: 0, seq: 0, poll: null, pendingRefresh: null };
  const top = h('section', { class: 'panel dossier-head' }, h('p', { class: 'loading' }, 'Loading dossier…'));
  const notices = h('div', { class: 'slot', 'aria-live': 'polite' });
  const fields = h('section', { class: 'fields', 'aria-label': 'Fields' });
  main.append(top, notices, fields);
  let path = `/dossiers/${encodeURIComponent(raw)}`;

  function stopPolling() {
    if (view.poll) clearInterval(view.poll);
    view.poll = null;
  }
  function startPolling() {
    if (!view.poll) view.poll = setInterval(load, POLL_MS);
  }

  async function load() {
    const mine = ++view.seq;
    let r;
    try {
      r = await read(path);
    } catch {
      if (mine > view.applied && !view.data) {
        replace(top, message('error', null, 'The dossier could not be loaded.',
          h('button', { type: 'button', class: 'btn btn-quiet', onclick: load }, 'Try again')));
      }
      return;
    }
    if (mine <= view.applied) return;  // an older read answered late
    view.applied = mine;
    if (r.status === 404 || r.status === 422) {
      stopPolling();
      notFound(main, raw);
      return;
    }
    if (r.status !== 200) return;
    view.data = r.body;
    path = `/dossiers/${encodeURIComponent(r.body.domain)}`;
    render();
    if (r.body.state === 'building') startPolling();
    else stopPolling();
  }

  async function refresh() {
    const d = view.data;
    if (!view.pendingRefresh) view.pendingRefresh = { key: newKey() };
    const attempt = view.pendingRefresh;
    const button = document.querySelector('[data-testid="dossier-refresh"]');
    if (button) { button.disabled = true; button.textContent = 'Refreshing…'; }
    const r = await write('POST', `/dossiers/${encodeURIComponent(d.domain)}/refresh`, { key: attempt.key });
    if (r.outcome === 'ok') {
      view.pendingRefresh = null;
      notices.replaceChildren();
      view.data = { ...view.data, state: r.body.state };
      view.applied = ++view.seq;  // reads sent before the refresh must not undo it
      render();
      load();
      startPolling();
      return;
    }
    if (button) { button.disabled = false; button.textContent = 'Refresh'; }
    if (r.outcome === 'uncertain') {
      notices.replaceChildren(message('uncertain', 'refresh-uncertain',
        'We could not confirm whether the refresh started. Press Refresh again to check — the same request is resent, so at most one build runs.'));
      return;
    }
    view.pendingRefresh = null;
    const text = r.status === 404 ? 'This dossier no longer exists, so it cannot be refreshed.'
      : errorText(r.body, 'The refresh was refused.');
    notices.replaceChildren(message('error', 'refresh-error', text));
  }

  function render() {
    const d = view.data;
    document.title = `${d.domain} — Dossier`;
    const building = d.state === 'building';
    replace(top,
      h('div', { class: 'dossier-title' },
        h('p', { class: 'eyebrow' }, 'Dossier'),
        h('h1', { class: 'domain', testid: 'dossier-domain' }, d.domain),
        h('div', { class: 'dossier-facts' },
          h('span', { class: `badge badge-${d.state}`, testid: 'dossier-state' }, d.state),
          building ? h('span', { class: 'muted building-note' }, 'Researching now; this page updates by itself.') : null,
          h('span', { class: 'muted', testid: 'dossier-spent', 'data-units': String(d.spent_units) }, unitsLabel(d.spent_units)),
          d.researched_at
            ? h('span', { class: 'muted', testid: 'dossier-researched-at' }, `Researched ${formatTimestamp(d.researched_at)}`)
            : null)),
      h('div', { class: 'actions' },
        h('button', { type: 'button', class: 'btn btn-primary', testid: 'dossier-refresh', onclick: refresh }, 'Refresh'),
        h('button', { type: 'button', class: 'btn btn-secondary', testid: 'dossier-reload', onclick: load }, 'Reload'),
        h('a', { class: 'btn btn-link', testid: 'dossier-evidence-link', href: `/dossiers/${encodeURIComponent(d.domain)}/evidence` },
          'All evidence')));
    if (d.state === 'failed' && !d.researched_at) {
      replace(fields, message('error', null, 'The research could not reach any source. Refresh to try again.'),
        FIELDS.map((f) => fieldCard(f, d.fields[f])));
      return;
    }
    replace(fields, FIELDS.map((f) => fieldCard(f, d.fields[f])));
  }

  load();
}
