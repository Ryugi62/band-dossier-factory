// `/contested`: every contested field across all dossiers, by domain then field order.
import { listAll, read } from '../api.js';
import { h, message, replace } from '../dom.js';
import { FIELDS, FIELD_LABELS, dataValue, formatValue } from '../format.js';

function distinctValues(candidates) {
  const out = [];
  for (const c of candidates) {
    const v = typeof c.value === 'string' ? c.value.trim() : c.value;
    if (!out.some((x) => x === v)) out.push(v);
  }
  return out;
}

function item(domain, field, f) {
  return h('li', { class: 'list-item' },
    h('a', { href: `/dossiers/${encodeURIComponent(domain)}/evidence`, class: 'contested-link',
      testid: `contested-item-${domain}-${field}`, 'data-value': dataValue(f.value) },
    h('span', { class: 'contested-top' },
      h('span', { class: 'dossier-name' }, domain),
      h('span', { class: 'field-chip' }, FIELD_LABELS[field], h('span', { class: 'field-key' }, ` (${field})`))),
    h('span', { class: 'contested-values' },
      distinctValues(f.candidates).map((v) => h('span', { class: `value-chip${v === f.value ? ' is-selected' : ''}` },
        formatValue(field, v), v === f.value ? h('span', { class: 'chip-note' }, ' · selected') : null)))));
}

export async function contestedScreen(main) {
  document.title = 'Contested fields — Dossier';
  const body = h('div', { 'aria-live': 'polite' }, h('p', { class: 'loading' }, 'Loading contested fields…'));
  main.append(h('section', { class: 'panel' },
    h('h1', {}, 'Contested fields'),
    h('p', { class: 'lead' }, 'Fields whose sources disagree. Each shows every value found; the selected one is marked.'),
    body));
  let dossiers;
  try {
    const list = await listAll('');
    dossiers = await Promise.all(list.map(async (d) => (await read(`/dossiers/${encodeURIComponent(d.domain)}`)).body));
  } catch {
    replace(body, message('error', null, 'The contested fields could not be loaded. Reload the page to try again.'));
    return;
  }
  const rows = [];
  for (const d of dossiers.filter(Boolean).sort((a, b) => (a.domain < b.domain ? -1 : a.domain > b.domain ? 1 : 0))) {
    for (const f of FIELDS) {
      if (d.fields && d.fields[f] && d.fields[f].status === 'contested') rows.push(item(d.domain, f, d.fields[f]));
    }
  }
  if (!rows.length) {
    replace(body, h('div', { class: 'empty', testid: 'empty-contested' },
      h('p', { class: 'empty-title' }, 'No contested fields.'),
      h('p', { class: 'muted' }, 'Every researched field has sources that agree, or no source at all.')));
    return;
  }
  replace(body, h('ul', { class: 'contested-list', testid: 'contested-list' }, rows));
}
