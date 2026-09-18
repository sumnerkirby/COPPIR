import { createMap, getMap, toggleMapLock } from './js/map.js';
import {
  clearAllPins, clearFilter, filterPins, getPin, getPins, getVisiblePins, removePin,
  renderPin, renderCategoryToggles, setPinClickHandler, toggleCategoryLayer, toggleClusters,
} from './js/pins.js';
import {
  clearAllEdges, getEdges, removeEdgesTouching, renderEdge,
} from './js/edges.js';
import { resetTimer, toggleTimer } from './js/timer.js';
import {
  addMetric, adjustMetric, deleteMetric, loadCustomMetrics, promptMetricValue,
  renameMetric, toggleMetricsPanel,
} from './js/metrics.js';
import {
  addMeasurePoint, cancelActiveDraw, clearAllMarkup, clearMeasure, finishMeasure,
  initMapTools, isMeasuring, setMarkupColor, startDraw, toggleMeasure,
} from './js/maptools.js';
import {
  CATEGORY_ICONS, OPS_COLORS, OP_STATUS_BORDER, SECTORS, SECTOR_ZONE_COLORS,
  STATUS_COLORS, STATUS_SCORE, WHEEL_C,
} from './js/constants.js';
import {
  convexHull, darkenHex, debounce, escHtml, formatDist, haversineM,
  integrityColor, safeColor,
} from './js/utils.js';
import { showToast } from './js/toast.js';
import { apiPost, apiPut } from './js/api.js';

// ── Constants ──────────────────────────────────────────────────────────────

// Cmd on macOS, Ctrl everywhere else. The app ships as a .dmg, and only
// ctrlKey was ever checked, so none of these fired there -- Cmd+S reached the
// WebView's own save dialog instead.
const IS_MAC = /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent);
const ACCEL_LABEL = IS_MAC ? '\u2318' : 'Ctrl+';

/** Relabel the accelerator hints for the platform the app is actually on. */
function labelAccelerators() {
  document.querySelectorAll('[data-accel]').forEach(el => {
    const combo = ACCEL_LABEL + el.dataset.accel;
    if (el.hasAttribute('data-accel-label')) el.textContent = combo;
    else el.title = combo;
  });
}


// 19 matches the r attribute on the SVG circles used for sector and custom metric wheels.

// ── State ──────────────────────────────────────────────────────────────────
let sectorZonesVisible  = false;
let sectorZoneLayer     = null;
let zoneLabelMarkers    = [];
let undoStack        = null;
let heatLayer        = null;
let opsHeatLayer     = null;
let queryOrigin      = null;
let queryOriginMarker = null;
let thresholds    = [];
let searchResults = [];
let searchMarkers = [];
let ws;
let ctxLatLng   = null;
// Modal-based user input is implemented as Promises. These variables hold the
// resolve function while the modal is open; the confirm/cancel buttons call it.
let bulkResolve = null;
let nameResolve = null;
let panelHidden      = false;
let rightPanelOpen   = false;
let logOpen     = false;
let injectAlertTimer = null;
let searchCircle     = null;
// The map reframes itself on the first full_state that carries pins, and on an
// explicit scenario load. Doing it on every full_state would yank the view back
// from wherever the user was looking each time the websocket reconnected.
let hasFitted           = false;
let fitOnNextFullState  = false;

// ── Init ───────────────────────────────────────────────────────────────────
function boot() {
  initMap();
  connectWS();
  initKeyboard();
  initClock();
  setPinClickHandler(openPinModal);
  initDomHandlers();
  loadInjects();
  loadCustomMetrics();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}

function initDomHandlers() {
  // Was inline: onkeydown="if(e.key==='Enter')geoSearch()". Inline handlers
  // are given `event`, not `e`, so that threw ReferenceError every time and
  // Enter never searched -- you had to click GO.
  document.getElementById('loc-input')
    .addEventListener('keydown', ev => { if (ev.key === 'Enter') geoSearch(); });

  document.getElementById('bulk-cat')
    .addEventListener('change', () => refreshBulkPreview());
  document.getElementById('markup-color-picker')
    .addEventListener('change', ev => setMarkupColor(ev.target.value));
  document.getElementById('pin-filter-inp')
    .addEventListener('input', ev => filterPins(ev.target.value));
  // Filtering dims the misses but leaves the view where it was, so a match
  // off-screen stayed lost. Enter goes to whatever is still showing.
  document.getElementById('pin-filter-inp')
    .addEventListener('keydown', ev => {
      if (ev.key !== 'Enter') return;
      if (!fitToPins(getVisiblePins())) showToast('Nothing matches that filter');
    });
  document.getElementById('inj-spawn-on')
    .addEventListener('change', ev => {
      document.getElementById('inj-spawn-fields').style.display = ev.target.checked ? 'block' : 'none';
    });

  // Metric names are contenteditable and rendered on the fly. blur does not
  // bubble, so delegate the bubbling equivalent instead.
  document.addEventListener('focusout', ev => {
    const el = ev.target.closest('[data-rename-metric]');
    if (el) renameMetric(el.dataset.renameMetric, el.textContent.trim());
  });
}

function initMap() {
  // The map module builds the instance; the handlers below belong to the app,
  // which is why they are attached here rather than in that module.
  createMap();

  initMapTools();

  getMap().on('contextmenu', onRightClick);
  getMap().on('click', e => {
    hideCtx();
    if (isMeasuring()) addMeasurePoint(e.latlng);
  });
  getMap().on('dblclick', e => {
    if (isMeasuring()) { L.DomEvent.stop(e); finishMeasure(); }
  });
  getMap().on('zoomend', updateZoneLabelVisibility);
}

function initClock() {
  const el = document.getElementById('sitrep-clock');
  const tick = () => {
    const now = new Date();
    el.textContent = `${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')}`;
  };
  tick();
  setInterval(tick, 1000);
}

function initKeyboard() {
  labelAccelerators();
  document.addEventListener('keydown', e => {
    const accel = e.metaKey || e.ctrlKey;
    // e.key carries the shifted form, so Caps Lock alone used to break these.
    const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    if (accel && key === 's') { e.preventDefault(); openScenarioModal(); }
    if (accel && key === 'l') { e.preventDefault(); toggleLog(); }
    if (accel && key === 'z') { e.preventDefault(); undoAction(); }
    if (e.key === '?' && !e.target.matches('input,textarea,select')) openShortcuts();
    if (e.key === 'Escape') {
      if (cancelActiveDraw()) { /* a part-drawn shape was discarded */ }
      else if (isMeasuring()) { finishMeasure(); }
      else { closeAllModals(); }
    }
  });
  document.getElementById('log-action-inp').addEventListener('keydown', e => {
    if (e.key === 'Enter') addLogEntry();
  });
  document.getElementById('loc-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') geoSearch();
  });
}

// ── WebSocket ──────────────────────────────────────────────────────────────
function hideLoadingScreen() {
  const el = document.getElementById('loading-screen');
  if (!el) return;
  el.classList.add('fade-out');
  setTimeout(() => el.remove(), 600);
}

// Reconnect delay starts at 1s and doubles on each failure up to 30s.
// It resets to 1s on a successful connection so a brief outage recovers quickly.
let _wsDelay = 1000;
let _wsReconnectTimer = null;

function _setWsStatus(connected) {
  const el = document.getElementById('ws-status');
  if (!el) return;
  el.title    = connected ? 'Connected' : 'Reconnecting…';
  el.style.background = connected ? '#00ff41' : '#FF4444';
}

function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => {
    _wsDelay = 1000;
    _setWsStatus(true);
    hideLoadingScreen();
  };

  ws.onmessage = e => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'full_state') {
      clearAllPins();
      clearAllEdges();
      Object.values(msg.pins).forEach(renderPin);
      if (msg.edges)      { msg.edges.forEach(renderEdge); }
      if (msg.thresholds) { thresholds = msg.thresholds; renderThresholdList(); }
      if (msg.injects) { clearInjectList(); msg.injects.forEach(renderInjectItem); }
      if (msg.log)     { clearLogEntries(); msg.log.forEach(appendLogEntry); updateLogCount(msg.log.length); }
      // hasFitted only flips once a frame actually happened, so a session that
      // starts empty still gets framed by the first state that carries pins.
      if (fitOnNextFullState || !hasFitted) hasFitted = fitToPins() || hasFitted;
      fitOnNextFullState = false;
    } else if (msg.type === 'pin_add') {
      renderPin(msg.pin);
    } else if (msg.type === 'bulk_add') {
      msg.pins.forEach(renderPin);
    } else if (msg.type === 'pin_update') {
      renderPin(msg.pin);
      // re-render any edges touching this pin
      Object.values(getEdges()).forEach(ed => {
        if (ed.from_pid === msg.pin.id || ed.to_pid === msg.pin.id) renderEdge(ed);
      });
    } else if (msg.type === 'pin_delete') {
      // The server drops these too, but only broadcasts pin_delete,
      // so the page has to clear them itself.
      removePin(msg.pid);
      removeEdgesTouching(msg.pid);
    } else if (msg.type === 'edge_add') {
      renderEdge(msg.edge);
    } else if (msg.type === 'edge_delete') {
      removeEdge(msg.eid);
    } else if (msg.type === 'inject_queued') {
      renderInjectItem(msg.inject);
    } else if (msg.type === 'inject_delete') {
      document.getElementById(`inj-${msg.iid}`)?.remove();
    } else if (msg.type === 'inject_triggered') {
      renderInjectItem(msg.inject);
      clearAllPins(); Object.values(msg.pins).forEach(renderPin);
      if (msg.new_pin) renderPin(msg.new_pin);
      appendLogEntry(msg.log_entry);
      updateLogCount(document.querySelectorAll('.log-entry').length);
      showInjectAlert(msg.inject);
    } else if (msg.type === 'pins_cleared') {
      clearAllPins();
      clearAllEdges();
    } else if (msg.type === 'bulk_update') {
      msg.pins.forEach(p => {
        renderPin(p);
        Object.values(getEdges()).forEach(ed => {
          if (ed.from_pid === p.id || ed.to_pid === p.id) renderEdge(ed);
        });
      });
    } else if (msg.type === 'threshold_add') {
      thresholds.push(msg.threshold);
      renderThresholdList();
    } else if (msg.type === 'threshold_delete') {
      thresholds = thresholds.filter(t => t.id !== msg.tid);
      renderThresholdList();
    } else if (msg.type === 'log_entry') {
      appendLogEntry(msg.entry);
      updateLogCount(document.querySelectorAll('.log-entry').length);
    }
    updateSitrep();
    refreshBulkCategories();
    if (heatLayer)    { getMap().removeLayer(heatLayer);    heatLayer    = null; toggleHeatmap(); }
    if (opsHeatLayer) { getMap().removeLayer(opsHeatLayer); opsHeatLayer = null; toggleOpsHeatmap(); }
  };

  ws.onclose = () => {
    _setWsStatus(false);
    _wsReconnectTimer = setTimeout(connectWS, _wsDelay);
    _wsDelay = Math.min(_wsDelay * 2, 30000); // cap at 30s to avoid indefinite silence
  };
  ws.onerror = () => ws.close();
}

// ── Rendering ──────────────────────────────────────────────────────────────


// ── SITREP ─────────────────────────────────────────────────────────────────
// Debounced so that bulk imports (50+ pins arriving in rapid succession) do not
// trigger 50 full sitrep recalculations. One pass runs 80ms after the last update.
const updateSitrep = debounce(function _updateSitrep() {
  const all = Object.values(getPins());
  const cnt = { Compromised: 0, 'Under Investigation': 0, Contained: 0, Monitored: 0, Clean: 0 };
  all.forEach(p => { if (cnt[p.status] !== undefined) cnt[p.status]++; });

  document.getElementById('cnt-comp').textContent  = cnt['Compromised'];
  document.getElementById('cnt-invs').textContent  = cnt['Under Investigation'];
  document.getElementById('cnt-cont').textContent  = cnt['Contained'];
  document.getElementById('cnt-mon').textContent   = cnt['Monitored'];
  document.getElementById('cnt-cln').textContent   = cnt['Clean'];
  document.getElementById('cnt-total').textContent = all.length;

  const ops = { Healthy: 0, Degraded: 0, Critical: 0, Offline: 0 };
  all.forEach(p => { const k = p.op_status || 'Healthy'; if (k in ops) ops[k]++; });
  document.getElementById('cnt-hlth').textContent = ops['Healthy'];
  document.getElementById('cnt-deg').textContent  = ops['Degraded'];
  document.getElementById('cnt-crit').textContent = ops['Critical'];
  document.getElementById('cnt-off').textContent  = ops['Offline'];

  SECTORS.forEach(s => {
    const relevant = all.filter(p => s.cats.includes(p.category));
    const svg = document.querySelector(`#ww-${s.key} .wheel-svg`);
    if (!svg) return;

    if (!relevant.length) {
      setWheelPct(svg, null);
      return;
    }
    const avg = relevant.reduce((sum, p) => sum + (STATUS_SCORE[p.status] ?? 0), 0) / relevant.length;
    setWheelPct(svg, avg);
  });

  evaluateThresholds();
  updateSectorZones();
  renderCategoryToggles();
}, 80);

function setWheelPct(svg, pct) {
  const arc   = svg.querySelector('.arc');
  const label = svg.querySelector('.pct-text');
  if (pct === null) {
    arc.setAttribute('stroke-dasharray', `0 ${WHEEL_C}`);
    label.textContent = '--%';
    arc.setAttribute('stroke', '#336633');
    return;
  }
  const dash = (pct / 100) * WHEEL_C;
  arc.setAttribute('stroke-dasharray', `${dash} ${WHEEL_C}`);
  arc.setAttribute('stroke', integrityColor(pct));
  label.textContent = Math.round(pct) + '%';
}

/**
 * Frame the given pins, or every pin when none are given.
 * Returns false when there is nothing to frame, so callers can say so.
 */
function fitToPins(list) {
  const target = list ?? Object.values(getPins());
  if (!target.length) return false;
  getMap().fitBounds(L.latLngBounds(target.map(p => [p.lat, p.lon])),
                     { padding: [60, 60], maxZoom: 15 });
  return true;
}

// ── Right-click context menu ───────────────────────────────────────────────
function onRightClick(e) {
  ctxLatLng = e.latlng;
  const menu = document.getElementById('ctx-menu');
  menu.style.display = 'block';
  menu.style.left = e.originalEvent.clientX + 'px';
  menu.style.top  = e.originalEvent.clientY + 'px';
}

function hideCtx() {
  document.getElementById('ctx-menu').style.display = 'none';
}

async function ctxAdd(category) {
  hideCtx();
  const result = await promptName(category);
  if (!result) return;
  const r = await apiPost('/api/pins', {
    name: result.name,
    category,
    lat: ctxLatLng.lat,
    lon: ctxLatLng.lng,
    status: result.status,
    op_status: result.op_status || 'Healthy',
  });
  if (r?.id) pushUndo({ type: 'pin_add', pid: r.id });
}

// ── Name prompt modal ──────────────────────────────────────────────────────
function promptName(category) {
  document.getElementById('nm-hdr').textContent = `ADD ${category.toUpperCase()}`;
  document.getElementById('nm-name').value = '';
  document.getElementById('nm-status').value = 'Clean';
  document.getElementById('name-modal').style.display = 'flex';
  document.getElementById('nm-name').focus();
  return new Promise(res => { nameResolve = res; });
}

function resolveNameModal(confirmed) {
  document.getElementById('name-modal').style.display = 'none';
  if (!nameResolve) return;
  if (!confirmed) { nameResolve(null); nameResolve = null; return; }
  const name      = document.getElementById('nm-name').value.trim();
  const status    = document.getElementById('nm-status').value;
  const op_status = document.getElementById('nm-op-status').value;
  nameResolve(name ? { name, status, op_status } : null);
  nameResolve = null;
}
document.getElementById('nm-name').addEventListener('keydown', e => {
  if (e.key === 'Enter') resolveNameModal(true);
});

// ── Location search ────────────────────────────────────────────────────────
async function geoSearch() {
  const q = document.getElementById('loc-input').value.trim();
  if (!q) return;
  const results = await apiPost('/api/geocode', { query: q });
  if (!results?.length) { showToast('Location not found'); return; }
  getMap().setView([parseFloat(results[0].lat), parseFloat(results[0].lon)], 13);
}

// ── OSM search ─────────────────────────────────────────────────────────────
async function osmSearch() {
  const cat    = document.getElementById('osm-cat').value;
  const radius = parseFloat(document.getElementById('osm-radius').value) || 15;
  const center = queryOrigin || getMap().getCenter();
  const statusEl  = document.getElementById('search-status');
  const loadingEl = document.getElementById('query-loading');
  const btn = document.getElementById('query-btn');

  clearSearch();
  statusEl.textContent = '';
  loadingEl.style.display = 'block';

  const radiusM = radius * 1609.34;
  searchCircle = L.circle(center, {
    radius: radiusM,
    color: '#00ff41', weight: 1,
    fillColor: '#00ff41', fillOpacity: 0.04,
    dashArray: '5 6', interactive: false,
  }).addTo(getMap());
  btn.textContent = 'QUERYING…';
  btn.disabled = true;

  let results;
  try {
    results = await apiPost('/api/search/osm', {
      lat: center.lat, lon: center.lng, radius_mi: radius, category: cat,
    });
  } finally {
    loadingEl.style.display = 'none';
    btn.textContent = 'QUERY';
    btn.disabled = false;
  }

  if (!results) { statusEl.textContent = 'Query failed — check toast for details'; return; }
  searchResults = results;
  statusEl.textContent = `${results.length} result${results.length !== 1 ? 's' : ''} found`;

  const list = document.getElementById('search-results');
  list.innerHTML = '';
  results.forEach(r => {
    const m = L.circleMarker([r.lat, r.lon], {
      radius: 6, color: '#6699ff', fillColor: '#3355cc', fillOpacity: 0.8, weight: 1,
    }).addTo(getMap()).bindTooltip(r.name);
    searchMarkers.push(m);

    const li = document.createElement('li');
    li.textContent = r.name;
    list.appendChild(li);
  });

  document.getElementById('pin-all-row').style.display = results.length ? 'block' : 'none';
}

function clearSearch() {
  searchMarkers.forEach(m => getMap().removeLayer(m));
  searchMarkers = [];
  searchResults = [];
  if (searchCircle) { getMap().removeLayer(searchCircle); searchCircle = null; }
  document.getElementById('search-results').innerHTML = '';
  document.getElementById('pin-all-row').style.display = 'none';
  document.getElementById('search-status').textContent = '';
}

// ── Bulk pin ───────────────────────────────────────────────────────────────
async function pinAll() {
  if (!searchResults.length) return;
  document.getElementById('bulk-count').textContent = `Pinning ${searchResults.length} location(s)`;
  document.getElementById('bm-status').value = 'Clean';
  document.getElementById('bm-color').value  = '#33CC33';
  document.getElementById('bulk-modal').style.display = 'flex';

  const result = await new Promise(res => { bulkResolve = res; });
  if (!result) return;

  const items = searchResults.map(r => ({ name: r.name, category: r.category, lat: r.lat, lon: r.lon }));
  await apiPost('/api/pins/bulk', { items, status: result.status, op_status: result.op_status || 'Healthy', pin_color: result.pinColor || null });
  clearSearch();
  showToast(`Pinned ${items.length} location(s)`);
}

function resolveBulk(confirmed) {
  document.getElementById('bulk-modal').style.display = 'none';
  if (!bulkResolve) return;
  if (!confirmed) { bulkResolve(null); bulkResolve = null; return; }
  bulkResolve({
    status:    document.getElementById('bm-status').value,
    op_status: document.getElementById('bm-op-status').value,
    pinColor:  document.getElementById('bm-color').value,
  });
  bulkResolve = null;
}

function setBulkColor(hex) {
  if (hex) document.getElementById('bm-color').value = hex;
}

// ── Pin edit modal ─────────────────────────────────────────────────────────
function openPinModal(pid) {
  const p = getPins()[pid];
  document.getElementById('em-pid').value       = pid;
  document.getElementById('em-name').value      = p.name;
  document.getElementById('em-cat').value       = p.category;
  document.getElementById('em-status').value    = p.status;
  document.getElementById('em-op-status').value = p.op_status || 'Healthy';
  document.getElementById('em-color').value     = p.pin_color || STATUS_COLORS[p.status]?.circle || '#33CC33';
  document.getElementById('em-notes').value     = p.notes || '';

  const history = (p.status_history || []).slice().reverse();
  const histEl  = document.getElementById('em-history');
  if (history.length < 2) {
    histEl.innerHTML = '<div class="history-entry"><span class="history-time">No changes recorded yet.</span></div>';
  } else {
    histEl.innerHTML = history.map((h, i) => {
      const prev = history[i + 1];
      const t    = new Date(h.timestamp);
      const ts   = `${t.getMonth()+1}/${t.getDate()} ${t.getHours().toString().padStart(2,'0')}:${t.getMinutes().toString().padStart(2,'0')}`;
      const col  = STATUS_COLORS[h.status]?.circle || '#888';
      const fromPart = prev
        ? `<span class="history-status" style="color:${STATUS_COLORS[prev.status]?.circle||'#888'}">${prev.status}</span><span class="history-arrow"> → </span>`
        : '';
      return `<div class="history-entry">
        <span class="history-time">${ts}</span>
        ${fromPart}<span class="history-status" style="color:${col}">${h.status}</span>
      </div>`;
    }).join('');
  }

  // populate link target dropdown
  const linkSel = document.getElementById('em-link-target');
  linkSel.innerHTML = '<option value="">— Select asset to link —</option>';
  Object.values(getPins())
    .filter(pp => pp.id !== pid)
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach(pp => {
      const o = document.createElement('option');
      o.value = pp.id; o.textContent = pp.name;
      linkSel.appendChild(o);
    });

  // show existing connections
  const linksEl = document.getElementById('em-links');
  const myEdges = Object.values(getEdges()).filter(e => e.from_pid === pid || e.to_pid === pid);
  if (!myEdges.length) {
    linksEl.innerHTML = '<div class="dim-txt" style="font-size:10px;padding:2px 0">No connections.</div>';
  } else {
    linksEl.innerHTML = myEdges.map(e => {
      const otherPid  = e.from_pid === pid ? e.to_pid : e.from_pid;
      const otherName = getPins()[otherPid]?.name || 'Unknown';
      const labelPart = e.label ? ` — ${escHtml(e.label)}` : '';
      return `<div class="link-entry">
        <span style="flex:1;font-size:10px">${escHtml(otherName)}${labelPart}</span>
        <button class="btn btn-danger" style="padding:1px 5px;font-size:9px" data-action="deletePinLink" data-args="${escHtml(JSON.stringify([e.id, pid]))}">✕</button>
      </div>`;
    }).join('');
  }

  document.getElementById('pin-modal').style.display = 'flex';
}

async function addPinLink() {
  const pid       = document.getElementById('em-pid').value;
  const targetPid = document.getElementById('em-link-target').value;
  if (!targetPid) { showToast('Select an asset to link to'); return; }
  const exists = Object.values(getEdges()).some(e =>
    (e.from_pid === pid && e.to_pid === targetPid) ||
    (e.from_pid === targetPid && e.to_pid === pid)
  );
  if (exists) { showToast('Already linked'); return; }
  await apiPost('/api/edges', { from_pid: pid, to_pid: targetPid, label: '', edge_type: 'connection' });
  openPinModal(pid);
}

async function deletePinLink(eid, pid) {
  await fetch(`/api/edges/${eid}`, { method: 'DELETE' });
  openPinModal(pid);
}

async function savePinEdit() {
  const pid  = document.getElementById('em-pid').value;
  const prev = { ...getPins()[pid] };
  const r = await apiPut(`/api/pins/${pid}`, {
    name:      document.getElementById('em-name').value.trim(),
    status:    document.getElementById('em-status').value,
    op_status: document.getElementById('em-op-status').value,
    pin_color: document.getElementById('em-color').value || null,
    notes:     document.getElementById('em-notes').value,
  });
  // Closing on a rejected save discarded the edit and left an undo entry that
  // pointed at a change the server never made.
  if (!r) return;
  pushUndo({ type: 'pin_update', pid, prev });
  closeModal('pin-modal');
}

async function deletePinDialog() {
  const pid      = document.getElementById('em-pid').value;
  const snapshot = { ...getPins()[pid] };
  closeModal('pin-modal');
  await fetch(`/api/pins/${pid}`, { method: 'DELETE' });
  pushUndo({ type: 'pin_delete', pin: snapshot });
}

function setColor(hex) {
  if (hex) document.getElementById('em-color').value = hex;
}

// ── Scenario manager ───────────────────────────────────────────────────────
async function openScenarioModal() {
  document.getElementById('scenario-name-inp').value = '';
  await refreshScenarioList();
  document.getElementById('scenario-modal').style.display = 'flex';
}

async function refreshScenarioList() {
  const names = await fetch('/api/scenarios').then(r => r.json());
  const list  = document.getElementById('scenario-list');
  const empty = document.getElementById('scenario-empty');
  list.innerHTML = '';
  if (!names.length) {
    empty.style.display = 'block';
    list.style.display  = 'none';
    return;
  }
  empty.style.display = 'none';
  list.style.display  = 'block';
  names.forEach(name => {
    const li = document.createElement('li');
    li.className = 'scenario-item';
    li.innerHTML = `
      <span class="scenario-item-name"><i class="fa-solid fa-file-lines" style="margin-right:6px;color:var(--fg-dim)"></i>${escHtml(name)}</span>
      <div class="scenario-item-actions">
        <button class="btn" style="padding:2px 8px;font-size:10px" data-action="loadScenario" data-args="${escHtml(JSON.stringify([name]))}">LOAD</button>
        <button class="btn btn-danger" style="padding:2px 7px;font-size:10px" data-action="deleteScenario" data-args="${escHtml(JSON.stringify([name]))}">&#10005;</button>
      </div>`;
    list.appendChild(li);
  });
}

async function saveScenario() {
  const name = document.getElementById('scenario-name-inp').value.trim();
  if (!name) { showToast('Enter a scenario name'); return; }
  const r = await apiPost('/api/scenarios/save', { name });
  if (r?.ok) {
    showToast(`Saved: ${r.name}`);
    await refreshScenarioList();
    document.getElementById('scenario-name-inp').value = '';
  }
}

async function loadScenario(name) {
  if (!confirm(`Load scenario "${name}"? Current session will be replaced.`)) return;
  // Set before the request: the broadcast can land before the response does.
  fitOnNextFullState = true;
  const r = await apiPost('/api/scenarios/load', { name });
  if (r?.ok) { showToast(`Loaded: ${r.name} (${r.count} pins)`); closeModal('scenario-modal'); }
  else fitOnNextFullState = false;
}

async function deleteScenario(name) {
  if (!confirm(`Delete scenario "${name}"?`)) return;
  await fetch(`/api/scenarios/${encodeURIComponent(name)}`, { method: 'DELETE' });
  await refreshScenarioList();
}

async function confirmClear() {
  if (!confirm('Start a new session? All current pins, injects, and log entries will be cleared.')) return;
  await fetch('/api/state/clear', { method: 'POST' });
  closeModal('scenario-modal');
  showToast('New session started');
}

// ── Panel toggles ──────────────────────────────────────────────────────────
function togglePanel() {
  panelHidden = !panelHidden;
  document.getElementById('panel').classList.toggle('hidden', panelHidden);
}

function toggleRightPanel() {
  rightPanelOpen = !rightPanelOpen;
  document.getElementById('right-panel').classList.toggle('open', rightPanelOpen);
  document.getElementById('tools-btn')?.classList.toggle('btn-active', rightPanelOpen);
}

// ── Modal helpers ──────────────────────────────────────────────────────────
function closeModal(id) { document.getElementById(id).style.display = 'none'; }

function closeAllModals() {
  ['pin-modal', 'bulk-modal', 'name-modal', 'create-inject-modal', 'scenario-modal', 'timeline-modal', 'shortcuts-modal'].forEach(closeModal);
  resolveNameModal(false);
  resolveBulk(false);
  hideCtx();
  dismissInjectAlert();
}

document.querySelectorAll('.modal-overlay').forEach(el => {
  el.addEventListener('click', e => {
    if (e.target === el) closeAllModals();
  });
});

// ── Toast ──────────────────────────────────────────────────────────────────

// ── API helpers ────────────────────────────────────────────────────────────
// ── Map Lock ───────────────────────────────────────────────────────────────

// ── Custom Metrics ─────────────────────────────────────────────────────────


// ── Map Markup ─────────────────────────────────────────────────────────────


// ── Measure Tool ───────────────────────────────────────────────────────────


// ── Declarative event wiring ───────────────────────────────────────────────
// Elements opt in with data-action, plus data-args when the handler takes
// parameters (a JSON array). A single delegated listener dispatches them.
//
// This replaces inline onclick attributes. Two reasons it is worth the
// indirection: markup no longer carries executable code, and dynamically
// inserted elements work without rebinding anything. It also means user data
// reaches the DOM as an escaped attribute value rather than being spliced
// into a string of JavaScript.
const ACTIONS = {
    addLogEntry, addMetric, addPinLink, addThreshold, adjustMetric,
  applyBulkOpStatus, applyBulkStatus, clearAllMarkup, clearAllPinsConfirm,
  clearFilter, clearQueryOrigin, clearSearch, closeModal, confirmClear,
  ctxAdd, deleteInject, deleteMetric, deletePinDialog, deletePinLink,
  deleteScenario, deleteThreshold, dismissInjectAlert, escHtml,
  exportBriefing, exportLog, geoSearch, hideCtx, loadScenario,
  openInjectModal, openScenarioModal, openShortcuts, openTimeline,
  osmSearch, pinAll, promptMetricValue, resetTimer, resolveBulk,
  resolveNameModal, saveInject, savePinEdit, saveScenario, setBulkColor,
  setColor, setMarkupColor, setQueryOrigin, startDraw, toggleCategoryLayer,
  toggleClusters, toggleHeatmap, toggleLog, toggleMapLock, toggleMeasure,
  toggleMetricsPanel, toggleOpsHeatmap, togglePanel, toggleRightPanel,
  toggleSectorZones, toggleTimer, triggerInject, undoAction, useMapCentreForInject
};

document.addEventListener('click', ev => {
  const el = ev.target.closest('[data-action]');
  if (!el) return;
  const fn = ACTIONS[el.dataset.action];
  if (!fn) { console.warn('unknown data-action:', el.dataset.action); return; }
  if (el.dataset.stopPropagation !== undefined) ev.stopPropagation();
  fn(...(el.dataset.args ? JSON.parse(el.dataset.args) : []));
});

// ── Color utilities ────────────────────────────────────────────────────────

// ── Inject queue ───────────────────────────────────────────────────────────
async function loadInjects() {
  const list = await fetch('/api/injects').then(r => r.json());
  clearInjectList();
  list.forEach(renderInjectItem);
}

function clearInjectList() {
  document.getElementById('inject-list').innerHTML = '';
}

function renderInjectItem(inj) {
  const list = document.getElementById('inject-list');
  document.getElementById(`inj-${inj.id}`)?.remove();
  const li = document.createElement('li');
  li.id = `inj-${inj.id}`;
  li.className = `inject-item sev-${inj.severity}${inj.triggered_at ? ' triggered' : ''}`;
  const desc = inj.description.slice(0, 90);
  li.innerHTML = `
    <div class="inject-item-title">${escHtml(inj.title)}</div>
    <div class="dim-txt" style="font-size:10px">${escHtml(desc)}${inj.description.length > 90 ? '…' : ''}</div>
    <div class="inject-item-actions">
      ${!inj.triggered_at
        ? `<button class="btn btn-danger" style="padding:2px 8px;font-size:10px" data-action="triggerInject" data-args="${escHtml(JSON.stringify([inj.id]))}">&#9654; FIRE</button>`
        : `<span class="dim-txt" style="font-size:10px">&#10003; FIRED ${escHtml(inj.triggered_at.slice(11,19))}</span>`}
      <button class="btn btn-dim" style="padding:2px 7px;font-size:10px" data-action="deleteInject" data-args="${escHtml(JSON.stringify([inj.id]))}">&#10005;</button>
    </div>`;
  list.appendChild(li);
}

async function triggerInject(iid) {
  const r = await fetch(`/api/injects/${iid}/trigger`, { method: 'POST' });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    showToast(err.detail || 'Failed to fire inject');
  }
}

async function deleteInject(iid) {
  await fetch(`/api/injects/${iid}`, { method: 'DELETE' });
  document.getElementById(`inj-${iid}`)?.remove();
}

function openInjectModal() {
  document.getElementById('inj-title').value = '';
  document.getElementById('inj-desc').value  = '';
  document.getElementById('inj-sev').value   = 'warning';
  document.getElementById('inj-target-status').value = '';
  const sel = document.getElementById('inj-target-pin');
  sel.innerHTML = '<option value="">— None —</option>';
  Object.values(getPins()).sort((a,b) => a.name.localeCompare(b.name)).forEach(p => {
    const o = document.createElement('option');
    o.value = p.id; o.textContent = p.name;
    sel.appendChild(o);
  });
  document.getElementById('inj-spawn-on').checked = false;
  document.getElementById('inj-spawn-fields').style.display = 'none';
  document.getElementById('inj-spawn-name').value = '';
  document.getElementById('inj-spawn-cat').value = 'Asset';
  document.getElementById('inj-spawn-status').value = 'Under Investigation';
  useMapCentreForInject();
  document.getElementById('create-inject-modal').style.display = 'flex';
}

function useMapCentreForInject() {
  const c = getMap().getCenter();
  document.getElementById('inj-spawn-lat').value = c.lat.toFixed(5);
  document.getElementById('inj-spawn-lon').value = c.lng.toFixed(5);
}

async function saveInject() {
  const title = document.getElementById('inj-title').value.trim();
  if (!title) { showToast('Title required'); return; }
  const pid    = document.getElementById('inj-target-pin').value || null;
  const status = document.getElementById('inj-target-status').value || null;

  let newPin = null;
  if (document.getElementById('inj-spawn-on').checked) {
    const lat = parseFloat(document.getElementById('inj-spawn-lat').value);
    const lon = parseFloat(document.getElementById('inj-spawn-lon').value);
    const spawnName = document.getElementById('inj-spawn-name').value.trim();
    if (!spawnName) { showToast('Name the asset this inject places'); return; }
    if (Number.isNaN(lat) || Number.isNaN(lon)) { showToast('Set coordinates for the new asset'); return; }
    newPin = {
      name: spawnName, lat, lon,
      category: document.getElementById('inj-spawn-cat').value,
      status:   document.getElementById('inj-spawn-status').value,
    };
  }

  const r = await apiPost('/api/injects', {
    title,
    description:   document.getElementById('inj-desc').value.trim(),
    severity:      document.getElementById('inj-sev').value,
    target_pid:    pid,
    target_status: status,
    new_pin: newPin,
  });
  if (!r) return;   // apiPost has already surfaced the reason
  closeModal('create-inject-modal');
  showToast('Inject queued');
}

// ── Inject alert ───────────────────────────────────────────────────────────
function showInjectAlert(inj) {
  document.getElementById('inject-alert-title').textContent = inj.title;
  document.getElementById('inject-alert-desc').textContent  = inj.description;
  const bar = document.getElementById('inject-alert-bar');
  bar.className = inj.severity;
  bar.id = 'inject-alert-bar';
  document.getElementById('inject-alert').style.display = 'flex';
  let secs = 15;
  const timerEl = document.getElementById('inject-alert-timer');
  timerEl.textContent = `Auto-dismiss in ${secs}s`;
  clearInterval(injectAlertTimer);
  injectAlertTimer = setInterval(() => {
    secs--;
    timerEl.textContent = `Auto-dismiss in ${secs}s`;
    if (secs <= 0) dismissInjectAlert();
  }, 1000);
}

function dismissInjectAlert() {
  clearInterval(injectAlertTimer);
  document.getElementById('inject-alert').style.display = 'none';
}

// ── Decision log ───────────────────────────────────────────────────────────
function toggleLog() {
  logOpen = !logOpen;
  document.getElementById('log-panel').classList.toggle('open', logOpen);
  document.getElementById('log-chevron').textContent = logOpen ? '▼' : '▲';
  if (logOpen) { refreshLogPinSelect(); scrollLogToBottom(); }
}

function clearLogEntries() {
  document.getElementById('log-entries').innerHTML = '';
  _logUserScrolled = false;
}

let _logUserScrolled = false;

function _initLogScroll() {
  const c = document.getElementById('log-entries');
  if (!c || c._scrollBound) return; // guard against attaching the listener more than once
  c._scrollBound = true;
  c.addEventListener('scroll', () => {
    // 32px threshold (~half a log row) avoids toggling when the scroll position
    // is already at the bottom but hasn't settled yet due to fractional pixels.
    const atBottom = c.scrollHeight - c.scrollTop - c.clientHeight < 32;
    _logUserScrolled = !atBottom;
  });
}

function appendLogEntry(entry) {
  _initLogScroll();
  const container = document.getElementById('log-entries');
  const el = document.createElement('div');
  el.className = 'log-entry';
  const t = new Date(entry.timestamp);
  const ts = `${t.getHours().toString().padStart(2,'0')}:${t.getMinutes().toString().padStart(2,'0')}:${t.getSeconds().toString().padStart(2,'0')}`;
  const autoTag = entry.auto ? `<span class="log-auto-tag">AUTO</span>` : '';
  const asset = entry.asset_name ? `<span class="log-asset-lbl"> &mdash; ${escHtml(entry.asset_name)}</span>` : '';
  const notesText = entry.notes ? entry.notes.slice(0, 60) : '';
  const notes = notesText ? `<span class="log-asset-lbl" style="margin-left:4px">[${escHtml(notesText)}]</span>` : '';
  el.innerHTML = `
    <span class="log-time">${ts}</span>
    ${autoTag}
    <span class="log-action">${escHtml(entry.action)}${asset}${notes}</span>`;
  container.appendChild(el);
  if (!_logUserScrolled) scrollLogToBottom();
}

function scrollLogToBottom() {
  const c = document.getElementById('log-entries');
  c.scrollTop = c.scrollHeight;
  _logUserScrolled = false;
}

function updateLogCount(n) {
  document.getElementById('log-count').textContent = `${n} entr${n === 1 ? 'y' : 'ies'}`;
}

function refreshLogPinSelect() {
  const sel = document.getElementById('log-pin-sel');
  sel.innerHTML = '<option value="">— No specific asset —</option>';
  Object.values(getPins()).sort((a,b) => a.name.localeCompare(b.name)).forEach(p => {
    const o = document.createElement('option');
    o.value = p.id; o.textContent = p.name;
    sel.appendChild(o);
  });
}

async function addLogEntry() {
  const action = document.getElementById('log-action-inp').value.trim();
  if (!action) return;
  const pid  = document.getElementById('log-pin-sel').value || null;
  const name = pid ? (getPins()[pid]?.name || null) : null;
  await apiPost('/api/log', { action, asset_name: name, asset_pid: pid, notes: '' });
  document.getElementById('log-action-inp').value = '';
}

// ── Bulk status ────────────────────────────────────────────────────────────
function refreshBulkCategories() {
  const sel = document.getElementById('bulk-cat');
  if (!sel) return;
  const current = sel.value;
  const cats = [...new Set(Object.values(getPins()).map(p => p.category))].sort();
  sel.innerHTML = '<option value="">— All categories —</option>';
  cats.forEach(c => {
    const o = document.createElement('option');
    o.value = c; o.textContent = c;
    if (c === current) o.selected = true;
    sel.appendChild(o);
  });
  refreshBulkPreview();
}

function refreshBulkPreview() {
  const cat = document.getElementById('bulk-cat')?.value || '';
  const count = Object.values(getPins()).filter(p => !cat || p.category === cat).length;
  const catLabel = cat || 'all categories';
  document.getElementById('bulk-preview').textContent =
    `${count} pin${count !== 1 ? 's' : ''} in ${catLabel}`;
}

async function clearAllPinsConfirm() {
  const count = Object.keys(getPins()).length;
  if (!count) { showToast('No pins to delete'); return; }
  if (!confirm(`Delete all ${count} pin(s) and topology links? This cannot be undone.`)) return;
  await fetch('/api/pins', { method: 'DELETE' });
}

async function applyBulkStatus() {
  const cat    = document.getElementById('bulk-cat').value || null;
  const status = document.getElementById('bulk-status-sel').value;
  const count  = Object.values(getPins()).filter(p => !cat || p.category === cat).length;
  if (!count) { showToast('No matching pins'); return; }
  const label = cat || 'all categories';
  if (!confirm(`Set ${count} pin(s) in "${label}" → SEC: "${status}"?`)) return;
  const r = await apiPost('/api/pins/bulk-status', { category: cat, status });
  if (r?.ok) showToast(`Updated ${r.count} pin(s) → ${status}`);
}

async function applyBulkOpStatus() {
  const cat       = document.getElementById('bulk-cat').value || null;
  const op_status = document.getElementById('bulk-op-sel').value;
  const count     = Object.values(getPins()).filter(p => !cat || p.category === cat).length;
  if (!count) { showToast('No matching pins'); return; }
  const label = cat || 'all categories';
  if (!confirm(`Set ${count} pin(s) in "${label}" → OPS: "${op_status}"?`)) return;
  const r = await apiPost('/api/pins/bulk-status', { category: cat, op_status });
  if (r?.ok) showToast(`Updated ${r.count} pin(s) → ${op_status}`);
}

/** Hand the browser a generated file to save. */
function downloadBlob(text, filename, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function stamp() {
  return new Date().toISOString().slice(0, 19).replace(/:/g, '-');
}

function exportLog() {
  fetch('/api/log').then(r => r.json()).then(entries => {
    const rows = [['Timestamp','Action','Asset','Notes']];
    entries.forEach(e => rows.push([e.timestamp, e.action, e.asset_name, e.notes]));
    const csv = rows.map(r => r.map(csvField).join(',')).join('\n');
    downloadBlob(csv, `coppir_log_${stamp()}.csv`, 'text/csv');
  });
}

/** Quote every field. Only two of the four were quoted, so a comma or a
 *  newline in an asset name shifted every column after it. */
function csvField(v) {
  return `"${String(v ?? '').replace(/"/g, '""')}"`;
}

// ── Network topology ───────────────────────────────────────────────────────


// ── Incident timeline ──────────────────────────────────────────────────────
function openTimeline() {
  fetch('/api/log').then(r => r.json()).then(entries => {
    renderTimeline(entries);
    document.getElementById('timeline-modal').style.display = 'flex';
  });
}

function renderTimeline(entries) {
  const container = document.getElementById('timeline-track');
  container.innerHTML = '';

  if (!entries.length) {
    container.innerHTML = '<div class="dim-txt" style="padding:24px;text-align:center">No log entries yet.</div>';
    return;
  }

  const sorted = [...entries].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  const t0 = new Date(sorted[0].timestamp).getTime();
  const t1 = new Date(sorted[sorted.length - 1].timestamp).getTime();
  const span = t1 - t0 || 1;
  const MIN_W = 800;
  const W = Math.max(MIN_W, sorted.length * 90);
  const PAD = 60;

  const rail = document.createElement('div');
  rail.className = 'timeline-rail';
  rail.style.width = W + 'px';

  const line = document.createElement('div');
  line.className = 'timeline-line';
  rail.appendChild(line);

  sorted.forEach((entry, i) => {
    const pct = span > 0 ? (new Date(entry.timestamp).getTime() - t0) / span : 0;
    const x = PAD + pct * (W - PAD * 2);
    const t = new Date(entry.timestamp);
    const ts = `${t.getHours().toString().padStart(2,'0')}:${t.getMinutes().toString().padStart(2,'0')}`;
    const color = entry.auto ? '#FFAA00' : '#00ff41';
    const side  = i % 2 === 0 ? 'above' : 'below';

    const dot = document.createElement('div');
    dot.className = `timeline-dot tl-${side}`;
    dot.style.left = x + 'px';
    dot.title = `${entry.timestamp}\n${entry.action}${entry.notes ? '\n' + entry.notes : ''}`;
    const actionSnip = escHtml(entry.action.slice(0, 35));
    dot.innerHTML = `
      <div class="tl-label">${ts} — ${actionSnip}${entry.action.length > 35 ? '…' : ''}</div>
      <div class="tl-circle" style="background:${safeColor(color)}"></div>
      <div class="tl-stem"></div>`;
    rail.appendChild(dot);
  });

  container.appendChild(rail);
}

// ── Alert thresholds ───────────────────────────────────────────────────────
function renderThresholdList() {
  const list = document.getElementById('threshold-list');
  if (!list) return;
  list.innerHTML = '';
  if (!thresholds.length) {
    list.innerHTML = '<li class="dim-txt" style="padding:6px 0;font-size:10px">No thresholds set.</li>';
    return;
  }
  thresholds.forEach(t => {
    const li = document.createElement('li');
    li.className = 'threshold-item';
    li.id = `thr-${t.id}`;
    const sevColor = t.severity === 'critical' ? '#FF4444' : t.severity === 'warning' ? '#FFAA00' : '#6699ff';
    li.innerHTML = `
      <span style="flex:1;font-size:10px;color:var(--fg-text)">${escHtml(t.name)}</span>
      <span class="dim-txt" style="font-size:9px;margin:0 6px">${escHtml(t.sector)} &lt;${t.below_pct}%</span>
      <span style="width:8px;height:8px;border-radius:50%;background:${safeColor(sevColor)};display:inline-block;margin-right:5px"></span>
      <button class="btn btn-danger" style="padding:1px 5px;font-size:9px" data-action="deleteThreshold" data-args="${escHtml(JSON.stringify([t.id]))}">✕</button>`;
    list.appendChild(li);
  });
}

async function addThreshold() {
  const name     = document.getElementById('thr-name').value.trim();
  const sector   = document.getElementById('thr-sector').value;
  const belowPct = parseInt(document.getElementById('thr-pct').value) || 50;
  const severity = document.getElementById('thr-sev').value;
  if (!name) { showToast('Threshold name required'); return; }
  const r = await apiPost('/api/thresholds', { name, sector, below_pct: belowPct, severity });
  if (r) {
    document.getElementById('thr-name').value = '';
    showToast('Threshold added');
  }
}

async function deleteThreshold(tid) {
  await fetch(`/api/thresholds/${tid}`, { method: 'DELETE' });
}

function evaluateThresholds() {
  clearThresholdBadges();
  const all = Object.values(getPins());

  thresholds.forEach(thr => {
    let relevant;
    if (thr.sector === 'all') {
      relevant = all;
    } else {
      const sectorDef = SECTORS.find(s => s.key === thr.sector);
      if (!sectorDef) return;
      relevant = all.filter(p => sectorDef.cats.includes(p.category));
    }
    if (!relevant.length) return;
    const score = relevant.reduce((s, p) => s + (STATUS_SCORE[p.status] ?? 0), 0) / relevant.length;
    if (score < thr.below_pct) {
      addWheelBadge(thr.sector, thr.severity);
    }
  });
}

function addWheelBadge(sector, severity) {
  const wrapId = sector === 'all' ? null : `ww-${sector}`;
  if (!wrapId) return;
  const wrap = document.getElementById(wrapId);
  if (!wrap || wrap.querySelector('.wheel-alert')) return;
  const badge = document.createElement('div');
  badge.className = `wheel-alert alert-${severity}`;
  wrap.appendChild(badge);
}

function clearThresholdBadges() {
  document.querySelectorAll('.wheel-alert').forEach(b => b.remove());
}

// ── Exercise timer ─────────────────────────────────────────────────────────


// ── Undo ───────────────────────────────────────────────────────────────────
function pushUndo(action) {
  undoStack = action;
  const btn = document.getElementById('undo-btn');
  if (btn) btn.disabled = false;
}

function clearUndo() {
  undoStack = null;
  const btn = document.getElementById('undo-btn');
  if (btn) btn.disabled = true;
}

async function undoAction() {
  if (!undoStack) return;
  const action = undoStack;
  clearUndo();

  if (action.type === 'pin_add') {
    await fetch(`/api/pins/${action.pid}`, { method: 'DELETE' });
    showToast('Undo: pin removed');
  } else if (action.type === 'pin_delete') {
    const p = action.pin;
    await apiPost('/api/pins', {
      name: p.name, category: p.category, lat: p.lat, lon: p.lon,
      status: p.status, op_status: p.op_status || 'Healthy',
      pin_color: p.pin_color || null, notes: p.notes || '',
    });
    showToast('Undo: pin restored');
  } else if (action.type === 'pin_update') {
    const p = action.prev;
    await apiPut(`/api/pins/${action.pid}`, {
      name: p.name, status: p.status, op_status: p.op_status || 'Healthy',
      pin_color: p.pin_color || null, notes: p.notes || '',
    });
    showToast('Undo: pin reverted');
  }
}

// ── Pin visibility (category hide + search filter combined) ────────────────


// ── Category layer toggles ─────────────────────────────────────────────────


// ── Shortcuts modal ────────────────────────────────────────────────────────
function openShortcuts() {
  document.getElementById('shortcuts-modal').style.display = 'flex';
}

// ── Query origin lock ──────────────────────────────────────────────────────
function setQueryOrigin() {
  clearQueryOrigin(false);
  queryOrigin = getMap().getCenter();
  queryOriginMarker = L.marker([queryOrigin.lat, queryOrigin.lng], {
    icon: L.divIcon({
      className: '',
      html: `<div class="origin-marker"><i class="fa-solid fa-crosshairs"></i></div>`,
      iconSize: [30, 30], iconAnchor: [15, 15],
    }),
    zIndexOffset: 1000,
    interactive: false,
  }).addTo(getMap()).bindTooltip('Query origin (locked)');

  document.getElementById('origin-coords').textContent =
    `${queryOrigin.lat.toFixed(4)}, ${queryOrigin.lng.toFixed(4)}`;
  document.getElementById('origin-info').style.display = 'flex';
  document.getElementById('set-origin-btn').textContent = 'REPIN';
  showToast('Origin locked — queries will use this point');
}

function clearQueryOrigin(toast = true) {
  if (queryOriginMarker) { getMap().removeLayer(queryOriginMarker); queryOriginMarker = null; }
  queryOrigin = null;
  document.getElementById('origin-info').style.display = 'none';
  document.getElementById('set-origin-btn').textContent = 'PIN ORIGIN';
  if (toast) showToast('Origin cleared — queries use map center');
}

// ── Health aura layer ──────────────────────────────────────────────────────
function toggleHeatmap() {
  const btn = document.getElementById('heatmap-btn');
  if (heatLayer) {
    getMap().removeLayer(heatLayer);
    heatLayer = null;
    btn?.classList.remove('btn-active');
    return;
  }
  const all = Object.values(getPins());
  if (!all.length) { showToast('No pins to visualize'); return; }

  if (!getMap().getPane('healthPane')) {
    const pane = getMap().createPane('healthPane');
    pane.style.zIndex = 350;
    pane.style.filter = 'blur(14px)';
  }

  heatLayer = L.layerGroup();
  all.forEach(p => {
    const col = STATUS_COLORS[p.status]?.circle || '#33CC33';
    // circleMarker uses pixel radius — stays visible at any zoom level
    L.circleMarker([p.lat, p.lon], {
      radius: 22,
      stroke: false,
      fillColor: col,
      fillOpacity: 0.72,
      interactive: false,
      pane: 'healthPane',
    }).addTo(heatLayer);
  });
  heatLayer.addTo(getMap());
  btn?.classList.add('btn-active');
}

// ── Operational health map ─────────────────────────────────────────────────

function toggleOpsHeatmap() {
  const btn = document.getElementById('ops-heatmap-btn');
  if (opsHeatLayer) {
    getMap().removeLayer(opsHeatLayer);
    opsHeatLayer = null;
    btn?.classList.remove('btn-active');
    return;
  }
  const all = Object.values(getPins());
  if (!all.length) { showToast('No pins to visualize'); return; }

  if (!getMap().getPane('opsPane')) {
    const pane = getMap().createPane('opsPane');
    pane.style.zIndex = 351;
    pane.style.filter = 'blur(14px)';
  }

  opsHeatLayer = L.layerGroup();
  all.forEach(p => {
    const col = OPS_COLORS[p.op_status || 'Healthy'] || '#00FF41';
    L.circleMarker([p.lat, p.lon], {
      radius: 22,
      stroke: false,
      fillColor: col,
      fillOpacity: 0.72,
      interactive: false,
      pane: 'opsPane',
    }).addTo(opsHeatLayer);
  });
  opsHeatLayer.addTo(getMap());
  btn?.classList.add('btn-active');
}

// ── Cluster layer ──────────────────────────────────────────────────────────


// ── Sector bounding zones ──────────────────────────────────────────────────
function toggleSectorZones() {
  sectorZonesVisible = !sectorZonesVisible;
  document.getElementById('zones-btn')?.classList.toggle('btn-active', sectorZonesVisible);
  if (!sectorZonesVisible) {
    if (sectorZoneLayer) { getMap().removeLayer(sectorZoneLayer); sectorZoneLayer = null; }
    zoneLabelMarkers = [];
  } else {
    updateSectorZones();
  }
}

function updateZoneLabelVisibility() {
  // Labels are legible at country/state/metro zoom; hide at street level (zoom > 11)
  const show = getMap().getZoom() <= 11;
  zoneLabelMarkers.forEach(m => {
    const el = m.getElement?.();
    if (!el) return;
    el.style.opacity       = show ? '1' : '0';
    el.style.pointerEvents = show ? '' : 'none';
    el.style.transition    = 'opacity 0.25s ease';
  });
}

function clusterPinsByDistance(pinList, maxMeters) {
  const n = pinList.length;
  const parent = pinList.map((_, i) => i);
  const find = i => { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
  for (let i = 0; i < n; i++)
    for (let j = i + 1; j < n; j++)
      if (haversineM(pinList[i].lat, pinList[i].lon, pinList[j].lat, pinList[j].lon) <= maxMeters)
        parent[find(i)] = find(j);
  const groups = {};
  pinList.forEach((p, i) => { const r = find(i); (groups[r] = groups[r] || []).push(p); });
  return Object.values(groups);
}

function updateSectorZones() {
  if (!sectorZonesVisible) return;
  if (sectorZoneLayer) { getMap().removeLayer(sectorZoneLayer); sectorZoneLayer = null; }
  sectorZoneLayer = L.layerGroup();
  zoneLabelMarkers = [];
  const all = Object.values(getPins());
  const MAX_M = 1609; // 1 mile

  SECTORS.forEach(s => {
    const relevant = all.filter(p => s.cats.includes(p.category));
    if (!relevant.length) return;
    const color = SECTOR_ZONE_COLORS[s.key] || '#ffffff';
    const clusters = clusterPinsByDistance(relevant, MAX_M);

    clusters.forEach(cluster => {
      const cx = cluster.reduce((a, p) => a + p.lat, 0) / cluster.length;
      const cy = cluster.reduce((a, p) => a + p.lon, 0) / cluster.length;

      // Radius = max dist from centroid to any pin, minimum 400m, plus 350m buffer
      let maxDist = 400;
      cluster.forEach(p => {
        const d = haversineM(cx, cy, p.lat, p.lon);
        if (d > maxDist) maxDist = d;
      });
      const radius = maxDist + 350;

      // Avg security score for tooltip coloring
      const avgScore = cluster.reduce((sum, p) => sum + (STATUS_SCORE[p.status] ?? 0), 0) / cluster.length;
      const scoreColor = integrityColor(avgScore);
      const scoreText  = Math.round(avgScore) + '%';

      // Interactive circle — click to see assets
      const circle = L.circle([cx, cy], {
        radius,
        color,
        weight: 2,
        opacity: 0.75,
        fillColor: color,
        fillOpacity: 0.08,
        dashArray: '7 5',
        interactive: true,
      });
      const assetLines = cluster
        .map(p => `<span style="color:${safeColor(STATUS_COLORS[p.status]?.circle||'#888')}">${escHtml(p.name)}</span> — ${escHtml(p.status)}`)
        .join('<br>');
      circle.bindTooltip(
        `<div style="font-size:10px;min-width:120px">
          <b style="color:${color}">${s.key.toUpperCase()}</b>
          &nbsp;<span style="color:${scoreColor}">${scoreText}</span><br>
          ${assetLines}
        </div>`,
        { sticky: true }
      );
      circle.addTo(sectorZoneLayer);

      // Label at centroid — hidden at street zoom, visible at metro/country zoom
      const labelHtml = `
        <div class="zone-label" style="color:${color};text-shadow:0 0 8px ${color}99">
          <div class="zone-label-name">${s.key.toUpperCase()}</div>
          <div class="zone-label-score" style="color:${scoreColor}">${scoreText} · ${cluster.length}</div>
        </div>`;
      const labelMarker = L.marker([cx, cy], {
        icon: L.divIcon({
          className: '',
          html: labelHtml,
          iconSize: [80, 28], iconAnchor: [40, 14],
        }),
        interactive: false, zIndexOffset: -200,
      });
      labelMarker.addTo(sectorZoneLayer);
      zoneLabelMarkers.push(labelMarker);
    });
  });

  sectorZoneLayer.addTo(getMap());
  updateZoneLabelVisibility();
}

// ── Export briefing ────────────────────────────────────────────────────────
async function exportBriefing() {
  const all = Object.values(getPins());
  const cnt = { Compromised: 0, 'Under Investigation': 0, Contained: 0, Monitored: 0, Clean: 0 };
  all.forEach(p => { if (cnt[p.status] !== undefined) cnt[p.status]++; });
  const ops = { Healthy: 0, Degraded: 0, Critical: 0, Offline: 0 };
  all.forEach(p => { const k = p.op_status || 'Healthy'; if (k in ops) ops[k]++; });

  let sectorRows = '';
  SECTORS.forEach(s => {
    const relevant = all.filter(p => s.cats.includes(p.category));
    if (!relevant.length) {
      sectorRows += `<tr><td>${s.key.toUpperCase()}</td><td style="color:#555">—</td><td style="color:#555">no assets</td></tr>`;
      return;
    }
    const avg = relevant.reduce((sum, p) => sum + (STATUS_SCORE[p.status] ?? 0), 0) / relevant.length;
    const col = avg >= 70 ? '#66FF66' : avg >= 40 ? '#FFAA00' : '#FF4444';
    sectorRows += `<tr><td>${s.key.toUpperCase()}</td><td style="color:${col};font-weight:bold">${Math.round(avg)}%</td><td>${relevant.length} asset(s)</td></tr>`;
  });

  let pinRows = '';
  [...all].sort((a,b) => a.name.localeCompare(b.name)).forEach(p => {
    const sc = safeColor(STATUS_COLORS[p.status]?.circle || '#888');
    const oc = safeColor(OP_STATUS_BORDER[p.op_status || 'Healthy']?.color || '#888');
    pinRows += `<tr>
      <td>${escHtml(p.name)}</td><td style="color:#aaa">${escHtml(p.category)}</td>
      <td style="color:${sc}">${escHtml(p.status)}</td>
      <td style="color:${oc}">${escHtml(p.op_status || 'Healthy')}</td>
    </tr>`;
  });

  const log = await fetch('/api/log').then(r => r.json()).catch(() => []);
  let logRows = '';
  log.slice(-30).forEach(e => {
    const t = new Date(e.timestamp);
    const ts = `${t.getHours().toString().padStart(2,'0')}:${t.getMinutes().toString().padStart(2,'0')}`;
    const autoTag = e.auto ? '<span style="color:#555;font-size:10px"> [AUTO]</span>' : '';
    logRows += `<tr><td style="color:#555;white-space:nowrap">${ts}</td><td>${escHtml(e.action)}${autoTag}</td><td style="color:#555">${escHtml(e.asset_name||'')}</td></tr>`;
  });

  const now = new Date();
  const html = `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><title>COPPIR SITREP &mdash; ${now.toISOString().slice(0,10)}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Courier New', monospace; background: #000a00; color: #99ffaa; padding: 30px 40px; }
  h1 { color: #00ff41; font-size: 22px; letter-spacing: 4px; border-bottom: 2px solid #005500; padding-bottom: 10px; margin-bottom: 6px; }
  h2 { color: #00cc33; font-size: 11px; letter-spacing: 3px; margin: 22px 0 8px; border-left: 3px solid #005500; padding-left: 8px; }
  p.ts { color: #336633; font-size: 11px; margin-bottom: 16px; }
  table { border-collapse: collapse; width: 100%; font-size: 12px; }
  th { color: #336633; text-align: left; border-bottom: 1px solid #005500; padding: 5px 10px; font-size: 10px; letter-spacing: 1px; }
  td { padding: 5px 10px; border-bottom: 1px solid #002200; color: #99ffaa; }
  tr:last-child td { border-bottom: none; }
  @media print {
    body { background: white !important; color: #111 !important; }
    h1,h2 { color: #111 !important; border-color: #ccc !important; }
    td,th { color: #333 !important; border-color: #ddd !important; }
  }
</style></head><body>
<h1>COPPIR &mdash; SITUATION REPORT</h1>
<p class="ts">Generated: ${now.toISOString().replace('T',' ').slice(0,19)} UTC &nbsp;|&nbsp; ${all.length} asset(s) tracked &nbsp;|&nbsp; ${Object.keys(getEdges()).length} network link(s)</p>
<h2>SECURITY STATUS</h2>
<table><tr><th>COMPROMISED</th><th>UNDER INVESTIGATION</th><th>CONTAINED</th><th>MONITORED</th><th>CLEAN</th></tr>
<tr>
  <td style="color:#FF6666">${cnt.Compromised}</td>
  <td style="color:#FFCC55">${cnt['Under Investigation']}</td>
  <td style="color:#FF9944">${cnt.Contained}</td>
  <td style="color:#66AAFF">${cnt.Monitored}</td>
  <td style="color:#66FF66">${cnt.Clean}</td>
</tr></table>
<h2>OPERATIONAL STATUS</h2>
<table><tr><th>HEALTHY</th><th>DEGRADED</th><th>CRITICAL</th><th>OFFLINE</th></tr>
<tr>
  <td style="color:#00FF41">${ops.Healthy}</td>
  <td style="color:#FFD700">${ops.Degraded}</td>
  <td style="color:#FF4500">${ops.Critical}</td>
  <td style="color:#666">${ops.Offline}</td>
</tr></table>
<h2>SECTOR INTEGRITY</h2>
<table><tr><th>SECTOR</th><th>SCORE</th><th>ASSETS</th></tr>${sectorRows}</table>
<h2>ASSET INVENTORY (${all.length})</h2>
<table><tr><th>NAME</th><th>CATEGORY</th><th>SEC STATUS</th><th>OPS STATUS</th></tr>${pinRows || '<tr><td colspan="4" style="color:#555">No assets pinned.</td></tr>'}</table>
<h2>DECISION LOG (last 30)</h2>
<table><tr><th>TIME</th><th>ACTION</th><th>ASSET</th></tr>${logRows || '<tr><td colspan="3" style="color:#555">No entries.</td></tr>'}</table>
</body></html>`;

  // Some of pywebview's platform backends have no pop-up support at all, which
  // is exactly where this matters: the packaged app is how most people run it.
  // Fall back to saving the file rather than dead-ending on a toast.
  const w = window.open('', '_blank');
  if (w) {
    w.document.write(html);
    w.document.close();
    setTimeout(() => w.print(), 600);
    return;
  }
  const filename = `coppir_sitrep_${stamp()}.html`;
  downloadBlob(html, filename, 'text/html');
  showToast(`Saved ${filename}`);
}
