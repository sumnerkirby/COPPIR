// User-defined percentage wheels, kept in localStorage.
//
// These are the only state the server never sees, which is why they do not
// survive a scenario save/load -- worth knowing before treating them as part
// of the operational picture.

import { WHEEL_C } from './constants.js';
import { askValue } from './dialog.js';
import { escHtml, integrityColor, safeColor } from './utils.js';
import { showToast } from './toast.js';

let metrics = [];
let panelOpen = false;

export function loadCustomMetrics() {
  try { metrics = JSON.parse(localStorage.getItem('coppir_metrics') || '[]'); } catch { metrics = []; }
  renderMetrics();
}

function saveCustomMetrics() {
  localStorage.setItem('coppir_metrics', JSON.stringify(metrics));
}

export function toggleMetricsPanel() {
  panelOpen = !panelOpen;
  document.getElementById('metrics-panel').classList.toggle('open', panelOpen);
  document.getElementById('metrics-btn')?.classList.toggle('btn-active', panelOpen);
}

export function addMetric() {
  const name = document.getElementById('met-name').value.trim();
  const val  = document.getElementById('met-val').value.trim();
  if (!name) { showToast('Enter a metric name'); return; }
  metrics.push({ id: Date.now().toString(36), name, value: val || '0' });
  saveCustomMetrics();
  renderMetrics();
  document.getElementById('met-name').value = '';
  document.getElementById('met-val').value  = '';
}

export function deleteMetric(id) {
  metrics = metrics.filter(m => m.id !== id);
  saveCustomMetrics();
  renderMetrics();
}

export function adjustMetric(id, delta) {
  const m = metrics.find(m => m.id === id);
  if (!m) return;
  const n = parseFloat(m.value) || 0;
  m.value = String(Math.max(0, Math.min(100, Math.round(n + delta))));
  saveCustomMetrics();
  renderMetrics();
}

function editMetricValue(id, val) {
  const m = metrics.find(m => m.id === id);
  if (!m) return;
  const n = parseFloat(val);
  m.value = isNaN(n) ? '0' : String(Math.max(0, Math.min(100, Math.round(n))));
  saveCustomMetrics();
  renderMetrics();
}

export function renameMetric(id, name) {
  if (!name) return;
  const m = metrics.find(m => m.id === id);
  if (m) { m.name = name; saveCustomMetrics(); }
}

export async function promptMetricValue(id, current) {
  const val = await askValue({
    title: 'SET METRIC',
    label: 'Value (0–100)',
    value: String(current),
  });
  if (val === null) return;
  editMetricValue(id, val);
}

function renderMetrics() {
  const el = document.getElementById('metrics-list');
  if (!el) return;
  if (!metrics.length) {
    el.innerHTML = '<span class="dim-txt" style="font-size:10px;padding:4px 0">No metrics defined. Add one below.</span>';
    return;
  }
  el.innerHTML = metrics.map(m => {
    const pct  = Math.max(0, Math.min(100, parseFloat(m.value) || 0));
    const col  = safeColor(integrityColor(pct));
    const dash = (pct / 100) * WHEEL_C;
    return `<div class="metric-wheel-wrap">
      <svg class="wheel-svg" viewBox="0 0 50 50" data-action="promptMetricValue" data-args="${escHtml(JSON.stringify([m.id, Math.round(pct)]))}" style="cursor:pointer" title="Click to set value">
        <circle cx="25" cy="25" r="19" fill="none" stroke="#003300" stroke-width="7"/>
        <circle cx="25" cy="25" r="19" fill="none" stroke="${col}" stroke-width="7"
          stroke-dasharray="${dash} ${WHEEL_C}" transform="rotate(-90 25 25)"
          style="stroke-linecap:round;transition:stroke-dasharray 0.4s ease,stroke 0.4s ease"/>
        <text x="25" y="30" text-anchor="middle" style="fill:${col};font-family:var(--font);font-size:9px;font-weight:bold">${Math.round(pct)}%</text>
      </svg>
      <div class="metric-wheel-name" contenteditable="true"
           data-rename-metric="${escHtml(m.id)}"
           spellcheck="false">${escHtml(m.name)}</div>
      <div class="metric-wheel-controls">
        <button class="btn btn-dim metric-adj" data-action="adjustMetric" data-args="${escHtml(JSON.stringify([m.id, -5]))}">−</button>
        <button class="btn btn-dim metric-adj" data-action="adjustMetric" data-args="${escHtml(JSON.stringify([m.id, 5]))}">+</button>
        <button class="btn btn-danger metric-del" data-action="deleteMetric" data-args="${escHtml(JSON.stringify([m.id]))}">×</button>
      </div>
    </div>`;
  }).join('');
}
