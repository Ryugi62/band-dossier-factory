// Entry point: picks the screen for the current path and draws the shared layout around it.
import { session, signOutToLogin } from './api.js';
import { h, replace } from './dom.js';
import { loginScreen, signupScreen } from './views/auth.js';
import { listScreen } from './views/list.js';
import { dossierScreen } from './views/dossier.js';
import { evidenceScreen } from './views/evidence.js';
import { contestedScreen } from './views/contested.js';
import { setRenderer } from './nav.js';

function route(path) {
  if (path === '/login') return { screen: loginScreen, open: true };
  if (path === '/signup') return { screen: signupScreen, open: true };
  if (path === '/' || path === '') return { screen: listScreen, nav: 'list' };
  if (path === '/contested') return { screen: contestedScreen, nav: 'contested' };
  let m = path.match(/^\/dossiers\/([^/]+)\/evidence\/?$/);
  if (m) return { screen: evidenceScreen, arg: decodeURIComponent(m[1]), nav: 'list' };
  m = path.match(/^\/dossiers\/([^/]+)\/?$/);
  if (m) return { screen: dossierScreen, arg: decodeURIComponent(m[1]), nav: 'list' };
  return { screen: null };
}

function header(s, active) {
  const link = (href, label, key) => h('a', { href, class: `nav-link${active === key ? ' is-active' : ''}`,
    'aria-current': active === key ? 'page' : null }, label);
  const right = s
    ? h('div', { class: 'user' },
      h('span', { class: 'user-name', testid: 'current-user' }, h('span', { class: 'sr-label' }, 'Signed in as '), s.display_name),
      h('button', { type: 'button', class: 'btn btn-quiet', testid: 'logout-button', onclick: () => signOutToLogin() }, 'Log out'))
    : h('div', { class: 'user' }, link('/login', 'Log in', 'login'), link('/signup', 'Sign up', 'signup'));
  return h('header', { class: 'topbar' },
    h('div', { class: 'topbar-inner' },
      h('a', { href: '/', class: 'brand' }, h('span', { class: 'brand-mark', 'aria-hidden': 'true' }, 'D'), 'Dossier'),
      s ? h('nav', { class: 'nav', 'aria-label': 'Main' }, link('/', 'Dossiers', 'list'), link('/contested', 'Contested', 'contested')) : null,
      right));
}

function start() {
  const app = document.getElementById('app');
  const r = route(location.pathname);
  const s = session();
  if (!r.open && !s) {
    location.replace('/login');
    return;
  }
  const main = h('main', { id: 'main', class: 'main', tabindex: '-1' });
  replace(app, header(s, r.nav), main);
  if (!r.screen) {
    main.append(h('section', { class: 'panel empty' }, h('h1', {}, 'Page not found'),
      h('p', {}, 'There is nothing at this address. '), h('a', { href: '/' }, 'Back to the dossiers')));
    return;
  }
  r.screen(main, r.arg);
}

setRenderer(start);
start();
