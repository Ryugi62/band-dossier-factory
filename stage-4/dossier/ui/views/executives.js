// The seventh field, `executives`, shown in its own markup: stage-2 test ids name only six fields (D30).
import { h } from '../dom.js';
import { formatDate, hostOf, kindLabel, providerLabel, statusLabel } from '../format.js';
import { originsLine } from './investors.js';

const TITLE_LABELS = { cfo: 'Chief financial officer', coo: 'Chief operating officer', cto: 'Chief technology officer' };

function quote(c, testid) {
  return h('li', { class: 'citation', testid, 'data-provider': c.provider },
    h('blockquote', { class: 'excerpt' }, h('p', {}, `“${c.excerpt}”`)),
    h('p', { class: 'citation-source' },
      h('a', { href: c.url, rel: 'noopener noreferrer', target: '_blank' }, hostOf(c.url)),
      h('span', { class: 'muted' }, ` · via ${providerLabel(c.provider)}`)));
}

export function timesLine(f) {
  if (f.value === null || f.value === undefined) return null;
  return h('p', { class: 'times muted' },
    f.true_from ? `Holds from ${formatDate(f.true_from)}` : 'No effective date stated',
    f.learned_at ? ` · learned ${formatDate(f.learned_at)}` : '');
}

// Dossier screen: members with their citations.
export function executivesCard(f) {
  const members = f.value || [];
  return h('article', { class: `field field-${f.status} executives`, testid: 'executives-panel', 'data-status': f.status },
    h('div', { class: 'field-head' },
      h('h3', { class: 'field-label' }, 'Executives'),
      h('span', { class: `pill pill-${f.status}` }, statusLabel(f.status)),
      f.status === 'contested' ? h('span', { class: 'contested-flag' }, 'Sources disagree') : null),
    members.length
      ? h('ul', { class: 'members' }, members.map((m) => h('li', { class: 'member', testid: `executive-${m.title}` },
        h('span', { class: 'member-title muted' }, TITLE_LABELS[m.title] || m.title),
        h('span', { class: 'member-name' }, m.name))))
      : h('p', { class: 'field-value field-value-none' }, 'No executive named by a source'),
    timesLine(f),
    originsLine(f),
    h('ol', { class: 'citations', 'aria-label': 'Sources for executives' },
      f.citations.map((c, i) => quote(c, `executives-citation-${i + 1}`))));
}

// Evidence screen: every candidate by title, in rank order.
export function executivesEvidence(f) {
  return h('section', { class: `panel evidence-field field-${f.status}`, testid: 'executives-evidence' },
    h('div', { class: 'section-head' },
      h('h2', {}, 'Executives'),
      h('span', { class: `pill pill-${f.status}` }, `${f.candidates.length} ${f.candidates.length === 1 ? 'candidate' : 'candidates'}`)),
    f.candidates.length
      ? h('ol', { class: 'candidates' }, f.candidates.map((c, i) => h('li', {
        class: `candidate${c.selected ? ' is-selected' : ''}`, testid: `executives-candidate-${i + 1}`,
        'data-title': c.title, 'data-value': c.value, 'data-selected': c.selected ? 'true' : 'false',
      },
      h('div', { class: 'candidate-head' },
        h('span', { class: 'candidate-value' }, `${c.value}`),
        h('span', { class: 'muted' }, TITLE_LABELS[c.title] || c.title),
        c.selected ? h('span', { class: 'pill pill-selected' }, 'Selected') : null),
      h('blockquote', { class: 'excerpt' }, h('p', {}, `“${c.excerpt}”`)),
      h('p', { class: 'citation-source muted' },
        h('a', { href: c.url, rel: 'noopener noreferrer', target: '_blank' }, hostOf(c.url)),
        ` · ${kindLabel(c.kind)} · ${c.true_from ? `holds from ${formatDate(c.true_from)}` : 'no effective date'}`))))
      : h('p', { class: 'empty muted' }, 'No page names an executive of this company.'));
}
