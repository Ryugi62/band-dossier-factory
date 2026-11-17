// Small DOM helpers: h() builds an element from attributes and children.
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'testid') el.setAttribute('data-testid', v);
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : String(v));
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function clear(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
}

export function replace(el, ...children) {
  clear(el);
  el.append(...children.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false));
}

// A message box with role=status (or alert), carrying a data-testid.
export function message(kind, testid, text, ...extra) {
  return h('div', { class: `notice notice-${kind}`, testid, role: kind === 'error' ? 'alert' : 'status' },
    h('span', { class: 'notice-text' }, text), ...extra);
}
