// Login and signup screens.
import { call, saveSession, errorText } from '../api.js';
import { h, message } from '../dom.js';
import { navigate } from '../nav.js';

function field(id, label, type, testid, autocomplete) {
  return h('div', { class: 'form-row' },
    h('label', { for: id }, label),
    h('input', { id, name: id, type, testid, autocomplete, required: true }));
}

function authForm(main, { title, lead, fields, submitLabel, submitTestid, path, collect, alt }) {
  const errorSlot = h('div', { class: 'slot' });
  const button = h('button', { type: 'submit', class: 'btn btn-primary btn-block', testid: submitTestid }, submitLabel);
  const form = h('form', { class: 'panel auth-panel', novalidate: true },
    h('h1', {}, title), h('p', { class: 'lead' }, lead), errorSlot, ...fields, button, alt);
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    button.disabled = true;
    button.textContent = 'Please wait…';
    errorSlot.replaceChildren();
    let r;
    try {
      r = await call('POST', path, { body: collect(), auth: false });
    } catch {
      r = { status: 0, body: null };
    }
    button.disabled = false;
    button.textContent = submitLabel;
    if (r.status === 200 || r.status === 201) {
      saveSession(r.body);
      navigate('/');
      return;
    }
    const fallback = r.status === 0 ? 'The service could not be reached. Try again.' : 'That did not work. Check the details and try again.';
    errorSlot.replaceChildren(message('error', 'auth-error', errorText(r.body, fallback)));
  });
  main.append(h('div', { class: 'auth-wrap' }, form));
}

export function loginScreen(main) {
  document.title = 'Log in — Dossier';
  authForm(main, {
    title: 'Log in',
    lead: 'Sign in to read and research company dossiers.',
    fields: [field('login-email', 'Email', 'email', 'login-email', 'username'),
      field('login-password', 'Password', 'password', 'login-password', 'current-password')],
    submitLabel: 'Log in',
    submitTestid: 'login-submit',
    path: '/auth/login',
    collect: () => ({ email: document.getElementById('login-email').value, password: document.getElementById('login-password').value }),
    alt: h('p', { class: 'alt' }, 'No account yet? ', h('a', { href: '/signup' }, 'Create one')),
  });
}

export function signupScreen(main) {
  document.title = 'Sign up — Dossier';
  authForm(main, {
    title: 'Create an account',
    lead: 'Every signed-in researcher sees the same dossiers.',
    fields: [field('signup-email', 'Email', 'email', 'signup-email', 'username'),
      field('signup-password', 'Password (at least 8 characters)', 'password', 'signup-password', 'new-password'),
      field('signup-display-name', 'Display name', 'text', 'signup-display-name', 'name')],
    submitLabel: 'Sign up',
    submitTestid: 'signup-submit',
    path: '/auth/signup',
    collect: () => ({
      email: document.getElementById('signup-email').value,
      password: document.getElementById('signup-password').value,
      display_name: document.getElementById('signup-display-name').value,
    }),
    alt: h('p', { class: 'alt' }, 'Already registered? ', h('a', { href: '/login' }, 'Log in')),
  });
}
