// `/dossiers/{domain}/evidence`: every candidate of every field, in the API's rank order.
import { read } from '../api.js';
import { h, message, replace } from '../dom.js';
import { FIELDS, FIELD_LABELS, dataValue, formatDate, formatValue, hostOf, kindLabel, providerLabel } from '../format.js';
import { notFound } from './dossier.js';

function candidate(field, c, n) {
  return h('li', {
    class: `candidate${c.selected ? ' is-selected' : ''}`, testid: `candidate-${field}-${n}`,
    'data-value': dataValue(c.value), 'data-provider': c.provider, 'data-kind': c.kind || '', 'data-url': c.url,
    'data-published-at': c.published_at || '', 'data-selected': c.selected ? 'true' : 'false',
  },
  h('div', { class: 'candidate-head' },
    h('span', { class: 'candidate-value' }, formatValue(field, c.value)),
    c.selected ? h('span', { class: 'pill pill-selected' }, 'Selected') : null),
  h('blockquote', { class: 'excerpt' }, h('p', {}, `“${c.excerpt}”`)),
  h('dl', { class: 'candidate-meta' },
    h('div', {}, h('dt', {}, 'Source'), h('dd', {}, h('a', { href: c.url, rel: 'noopener noreferrer', target: '_blank' }, hostOf(c.url)))),
    h('div', {}, h('dt', {}, 'Page kind'), h('dd', {}, kindLabel(c.kind))),
    h('div', {}, h('dt', {}, 'Published'), h('dd', {}, c.published_at ? formatDate(c.published_at) : 'No publication date')),
    h('div', {}, h('dt', {}, 'Served by'), h('dd', {}, providerLabel(c.provider))),
    h('div', {}, h('dt', {}, 'Retrieved'), h('dd', {}, c.retrieved_at ? formatDate(c.retrieved_at) : '—'))));
}

function fieldSection(field, f) {
  return h('section', { class: `panel evidence-field field-${f.status}` },
    h('div', { class: 'section-head' },
      h('h2', {}, FIELD_LABELS[field]),
      h('span', { class: `pill pill-${f.status}` }, `${f.candidates.length} ${f.candidates.length === 1 ? 'candidate' : 'candidates'}`)),
    f.candidates.length
      ? h('ol', { class: 'candidates', testid: `evidence-${field}` }, f.candidates.map((c, i) => candidate(field, c, i + 1)))
      : h('div', { testid: `evidence-${field}`, class: 'candidates' },
        h('p', { class: 'empty muted', testid: `evidence-empty-${field}` }, 'No page supports a value for this field.')));
}

export async function evidenceScreen(main, raw) {
  document.title = 'Evidence — Dossier';
  const head = h('section', { class: 'panel' }, h('p', { class: 'loading' }, 'Loading evidence…'));
  main.append(head);
  let r;
  try {
    r = await read(`/dossiers/${encodeURIComponent(raw)}`);
  } catch {
    replace(head, message('error', null, 'The evidence could not be loaded. Reload the page to try again.'));
    return;
  }
  if (r.status === 404 || r.status === 422) {
    notFound(main, raw);
    return;
  }
  if (r.status !== 200) {
    replace(head, message('error', null, 'The evidence could not be loaded.'));
    return;
  }
  const d = r.body;
  document.title = `Evidence for ${d.domain} — Dossier`;
  replace(head,
    h('p', { class: 'eyebrow' }, 'Evidence'),
    h('h1', { class: 'domain' }, d.domain),
    h('p', { class: 'lead' }, 'Every value a source supports, ranked by the selection rule: company sites and filings first, then news, then aggregators; newer pages first.'),
    h('a', { href: `/dossiers/${encodeURIComponent(d.domain)}`, class: 'btn btn-link' }, '← Back to the dossier'));
  main.append(...FIELDS.map((f) => fieldSection(f, d.fields[f])));
}
