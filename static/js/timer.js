// The exercise clock in the SITREP strip.
//
// Entirely self-contained: four values that nothing outside this module reads.

let elapsed = 0;
let running = false;
let interval = null;
let startRef = null;

export function toggleTimer() {
  running ? pauseTimer() : startTimer();
}

function startTimer() {
  running  = true;
  startRef = Date.now() - elapsed;
  interval = setInterval(tickTimer, 500);
  document.getElementById('timer-btn').textContent = 'PAUSE';
  document.getElementById('timer-display').classList.add('timer-running');
  document.getElementById('timer-display').classList.remove('timer-paused');
}

function pauseTimer() {
  running  = false;
  elapsed  = Date.now() - startRef;
  clearInterval(interval);
  document.getElementById('timer-btn').textContent = 'RESUME';
  document.getElementById('timer-display').classList.remove('timer-running');
  document.getElementById('timer-display').classList.add('timer-paused');
}

export function resetTimer() {
  clearInterval(interval);
  running = false; elapsed = 0; startRef = null;
  const d = document.getElementById('timer-display');
  d.textContent = '00:00:00';
  d.classList.remove('timer-running', 'timer-paused');
  document.getElementById('timer-btn').textContent = 'START';
}

function tickTimer() {
  const ms = Date.now() - startRef;
  const h  = Math.floor(ms / 3600000);
  const m  = Math.floor((ms % 3600000) / 60000);
  const s  = Math.floor((ms % 60000) / 1000);
  document.getElementById('timer-display').textContent =
    `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}
