// The transient message strip along the bottom of the map.
//
// The timer is module-private, which is the point: before this it was one of
// the file-level `let`s that anything could reach.

let timer;

export function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(timer);
  timer = setTimeout(() => t.classList.remove('show'), 2800);
}
