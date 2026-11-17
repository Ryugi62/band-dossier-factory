// `/`: research a domain, then the dossier list with search.
import { listAll, newKey, write, errorText } from '../api.js';
import { h, message, replace } from '../dom.js';
import { formatTimestamp } from '../format.js';

// The research request still awaiting a confirmed answer: retried with the same key and body.
let pending = null;

function researchForm() {
  const input = h('input', { id: 'research-domain', type: 'text', testid: 'research-domain', inputmode: 'url',
    autocomplete: 'off', spellcheck: 'false', placeholder: 'acme-robotics.test', 'aria-describedby': 'research-hint' });
  const button = h('button', { type: 'submit', class: 'btn btn-primary', testid: 'research-submit' }, 'Research');
  const slot = h('div', { class: 'slot', 'aria-live': 'polite' });
  const form = h('form', { class: 'panel research', novalidate: true },
    h('h1', {}, 'Company dossiers'),
    h('p', { class: 'lead' }, 'Research a company by its web domain. Each field shows the value its sources support and where it came from.'),
    h('div', { class: 'research-row' },
      h('div', { class: 'form-row grow' }, h('label', { for: 'research-domain' }, 'Company domain'), input,
        h('p', { id: 'research-hint', class: 'hint' }, 'For example acme-robotics.test — no https:// or path.')),
      button),
    slot);

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const domain = input.value;
    if (!pending || pending.body.domain !== domain) pending = { key: newKey(), body: { domain } };
    const attempt = pending;
    button.disabled = true;
    button.textContent = 'Starting…';
    const r = await write('POST', '/dossiers', { body: attempt.body, key: attempt.key });
    button.disabled = false;
    button.textContent = 'Research';
    if (r.outcome === 'ok') {
      pending = null;
      slot.replaceChildren();
      location.assign(`/dossiers/${encodeURIComponent(r.body.domain)}`);
      return;
    }
    if (r.outcome === 'uncertain') {
      slot.replaceChildren(message('uncertain', 'research-uncertain',
        'We could not confirm whether the research started. Press Research again to check — the same request is resent, so nothing is duplicated.'));
      return;
    }
    pending = null;
    const text = r.status === 422 ? 'That is not a valid domain. Enter a host name such as acme-robotics.test.'
      : errorText(r.body, 'The research request was refused.');
    slot.replaceChildren(message('error', 'research-error', text));
  });
  return form;
}

function item(d) {
  return h('li', { class: 'list-item' },
    h('a', { href: `/dossiers/${encodeURIComponent(d.domain)}`, class: 'dossier-link', testid: `dossier-item-${d.domain}`,
      'data-state': d.state },
      h('span', { class: 'dossier-main' },
        h('span', { class: 'dossier-name' }, d.legal_name || d.domain),
        d.legal_name ? h('span', { class: 'dossier-domain' }, d.domain) : null),
      h('span', { class: 'dossier-meta' },
        h('span', { class: `badge badge-${d.state}` }, d.state),
        h('span', { class: 'muted' }, d.researched_at ? `Researched ${formatTimestamp(d.researched_at)}` : 'Not researched yet'))));
}

export function listScreen(main) {
  document.title = 'Dossiers — Dossier';
  const search = h('input', { id: 'dossier-search', type: 'search', testid: 'dossier-search', autocomplete: 'off',
    placeholder: 'Domain or legal name' });
  const results = h('div', { class: 'results', 'aria-live': 'polite' }, h('p', { class: 'loading' }, 'Loading dossiers…'));
  main.append(researchForm(),
    h('section', { class: 'panel' },
      h('div', { class: 'section-head' }, h('h2', {}, 'All dossiers'),
        h('div', { class: 'form-row search-row' }, h('label', { for: 'dossier-search' }, 'Search dossiers'), search)),
      results));

  let seq = 0;
  async function load() {
    const mine = ++seq;
    const q = search.value;
    let items;
    try {
      items = await listAll(q);
    } catch {
      if (mine === seq) {
        replace(results, message('error', null, 'The dossiers could not be loaded.',
          h('button', { type: 'button', class: 'btn btn-quiet', onclick: load }, 'Try again')));
      }
      return;
    }
    if (mine !== seq) return;  // a later search has been sent: latest read wins
    if (!items.length) {
      replace(results, h('div', { class: 'empty', testid: 'empty-dossiers' },
        h('p', { class: 'empty-title' }, q ? 'No dossier matches this search.' : 'No dossiers yet.'),
        h('p', { class: 'muted' }, q ? 'Try part of a domain or a legal name.' : 'Research a domain above to create the first one.')));
      return;
    }
    replace(results, h('ul', { class: 'dossier-list', testid: 'dossier-list' }, items.map(item)));
  }
  let timer = null;
  search.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(load, 250);
  });
  load();
}
