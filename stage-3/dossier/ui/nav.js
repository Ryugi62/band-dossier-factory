// In-page navigation: change the address and draw the new screen without reloading the document.
let draw = () => {};

export function setRenderer(fn) {
  draw = fn;
  window.addEventListener('popstate', () => draw());
}

export function navigate(path) {
  history.pushState(null, '', path);
  draw();
}
