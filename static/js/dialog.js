// In-app replacements for window.confirm and window.prompt.
//
// The native dialogs are unstyled OS chrome in a deliberately themed app, they
// block the event loop, and pywebview's platform backends render them
// inconsistently. These follow the same promise-and-resolver shape the name
// and bulk modals already use: open the modal, hand back a promise, and let
// the footer buttons settle it.

let resolver = null;

function settle(value) {
  document.getElementById('ask-modal').style.display = 'none';
  if (!resolver) return;
  const done = resolver;
  resolver = null;
  done(value);
}

function open({ title, message, confirmLabel, danger, input }) {
  // A dialog opened over an unanswered one would strand the first promise.
  if (resolver) settle(input ? null : false);

  document.getElementById('ask-hdr').textContent = title;
  document.getElementById('ask-message').textContent = message || '';
  document.getElementById('ask-message').style.display = message ? 'block' : 'none';

  const ok = document.getElementById('ask-ok');
  ok.textContent = confirmLabel;
  ok.className = danger ? 'btn btn-danger' : 'btn';

  const row = document.getElementById('ask-input-row');
  const field = document.getElementById('ask-input');
  row.style.display = input ? 'block' : 'none';
  if (input) {
    document.getElementById('ask-input-lbl').textContent = input.label || '';
    field.value = input.value ?? '';
  }

  document.getElementById('ask-modal').style.display = 'flex';
  (input ? field : ok).focus();
  if (input) field.select();
}

/** Ask a yes/no question. Resolves true only if the user confirms. */
export function askConfirm({ title, message, confirmLabel = 'CONFIRM', danger = false }) {
  open({ title, message, confirmLabel, danger, input: null });
  return new Promise(res => { resolver = res; });
}

/** Ask for a value. Resolves the string, or null if the user backs out. */
export function askValue({ title, message, label, value, confirmLabel = 'SET' }) {
  open({ title, message, confirmLabel, danger: false, input: { label, value } });
  return new Promise(res => { resolver = res; });
}

/** Footer buttons, Escape and overlay clicks all land here. */
export function resolveAsk(confirmed) {
  const asking = document.getElementById('ask-input-row').style.display !== 'none';
  if (!confirmed) return settle(asking ? null : false);
  settle(asking ? document.getElementById('ask-input').value : true);
}

/** True while a dialog is waiting on an answer. */
export function isAsking() {
  return resolver !== null;
}
