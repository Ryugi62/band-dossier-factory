// The eighth field, `investors`, in its own markup (stage-2 test ids name only six fields, D45),
// and the corroboration line every field card shows (origins standing behind the value).
import { h } from '../dom.js';
import { formatDate, hostOf, kindLabel, providerLabel, statusLabel } from '../format.js';
import { timesLine } from './executives.js';

export function originsLine(f) {
  if (f.value === null || f.value === undefined || !f.origins) return null;
  const n = f.origins.length;
  const label = f.corroborated ? 'Corroborated' : n >= 2 ? 'Not fully corroborated' : 'Single source';
  return h('p', { class: `origins-line ${f.corroborated ? 'is-corroborated' : 'is-single'}` },
    h('span', { class: 'origins-badge' }, label),
    ` ${n} independent ${n === 1 ? 'origin' : 'origins'}: ${f.origins.join(', ')}`,
    f.corroborated_since ? ` · since ${formatDate(f.corroborated_since)}` : '');
}

export function investorsCard(f) {
  const names = f.value || [];
  return h('article', { class: `field field-${f.status} investors`, testid: 'investors-panel', 'data-status': f.status },
    h('div', { class: 'field-head' },
      h('h3', { class: 'field-label' }, 'Investors'),
      h('span', { class: `pill pill-${f.status}` }, statusLabel(f.status))),
    names.length
      ? h('ul', { class: 'members' }, names.map((n) => h('li', { class: 'member', testid: 'investor-member' },
        h('span', { class: 'member-name' }, n))))
      : h('p', { class: 'field-value field-value-none' },
        'No investor confirmed by a company page, a filing or two independent sources'),
    timesLine(f),
    originsLine(f),
    h('ol', { class: 'citations', 'aria-label': 'Sources for investors' },
      f.citations.map((c, i) => h('li', { class: 'citation', testid: `investors-citation-${i + 1}`, 'data-provider': c.provider },
        h('blockquote', { class: 'excerpt' }, h('p', {}, `“${c.excerpt}”`)),
        h('p', { class: 'citation-source' },
          h('a', { href: c.url, rel: 'noopener noreferrer', target: '_blank' }, hostOf(c.url)),
          h('span', { class: 'muted' }, ` · via ${providerLabel(c.provider)}`))))));
}

export function investorsEvidence(f) {
  return h('section', { class: `panel evidence-field field-${f.status}`, testid: 'investors-evidence' },
    h('div', { class: 'section-head' },
      h('h2', {}, 'Investors'),
      h('span', { class: `pill pill-${f.status}` }, `${f.candidates.length} ${f.candidates.length === 1 ? 'candidate' : 'candidates'}`)),
    h('p', { class: 'muted' }, 'A name is an investor when a company page or a filing names it, or two independent origins do.'),
    f.candidates.length
      ? h('ol', { class: 'candidates' }, f.candidates.map((c, i) => h('li', {
        class: `candidate${c.selected ? ' is-selected' : ''}`, testid: `investors-candidate-${i + 1}`,
        'data-value': c.value, 'data-selected': c.selected ? 'true' : 'false', 'data-origin': c.origin || '',
      },
      h('div', { class: 'candidate-head' },
        h('span', { class: 'candidate-value' }, c.value),
        c.selected ? h('span', { class: 'pill pill-selected' }, 'Investor') : h('span', { class: 'muted' }, 'Not confirmed')),
      h('blockquote', { class: 'excerpt' }, h('p', {}, `“${c.excerpt}”`)),
      h('p', { class: 'citation-source muted' },
        h('a', { href: c.url, rel: 'noopener noreferrer', target: '_blank' }, hostOf(c.url)),
        ` · ${kindLabel(c.kind)} · origin ${c.origin || hostOf(c.url)}`,
        c.true_from ? ` · holds from ${formatDate(c.true_from)}` : ''))))
      : h('p', { class: 'empty muted' }, 'No page names an investor of this company.'));
}
