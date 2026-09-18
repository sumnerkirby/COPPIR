// Pins: the assets on the map, how they are drawn, and what is visible.
//
// Clustering lives here too. It is not a separate feature so much as a display
// mode for these same markers -- renderPin, removePin and clearAllPins all
// have to know which of the two layers a marker currently belongs to.
//
// getPins() hands back the live record rather than a copy, because the SITREP,
// heatmaps, sector zones, export and bulk paths all iterate it on every
// update. Treat it as read-only; write through the functions here.

import { CATEGORY_ICONS, OP_STATUS_BORDER, STATUS_COLORS } from './constants.js';
import { getMap } from './map.js';
import { darkenHex, debounce, escHtml, safeColor } from './utils.js';

const pins = {};
const pinMarkers = {};
let filterQuery = '';
let hiddenCategories = new Set();
let clusterEnabled = false;
let clusterGroup = null;

// app.js decides what a pin click does; this module only reports it. Wiring the
// modal in directly would mean importing app.js back and creating a cycle.
let pinClicked = () => {};

export function setPinClickHandler(fn) {
  pinClicked = fn;
}

export function getPins() {
  return pins;
}

export function getPin(pid) {
  return pins[pid];
}

function makePinIcon(pin) {
  const col = safeColor(pin.pin_color || STATUS_COLORS[pin.status]?.circle || '#33CC33');
  const ops = OP_STATUS_BORDER[pin.op_status] || OP_STATUS_BORDER['Healthy'];
  const border = `${ops.width} ${ops.style} ${safeColor(ops.color)}`;
  const ico = CATEGORY_ICONS[pin.category] || 'fa-circle-dot';
  return L.divIcon({
    className: '',
    html: `<div class="pin-icon" style="background:${col};border:${border}"><i class="fa-solid ${escHtml(ico)}"></i></div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function tooltipHtml(pin) {
  return `<div>${escHtml(pin.name)}</div><div style="font-size:10px;opacity:0.8">`
       + `SEC: ${escHtml(pin.status)} &nbsp;·&nbsp; OPS: ${escHtml(pin.op_status || 'Healthy')}</div>`;
}

export function renderPin(pin) {
  pins[pin.id] = pin;
  const existing = pinMarkers[pin.id];

  if (existing) {
    // Reuse the marker. Dropping the layer and building a new one made Leaflet
    // tear down and re-insert a DOM node per pin on every update, which is
    // what a bulk status change over several hundred pins was paying for.
    existing.setIcon(makePinIcon(pin));
    existing.setLatLng([pin.lat, pin.lon]);
    existing.setTooltipContent(tooltipHtml(pin));
    // setIcon rebuilds the icon element, so the visibility styling goes with it.
    applyPinVisibility(pin.id);
    return;
  }

  const marker = L.marker([pin.lat, pin.lon], { icon: makePinIcon(pin) });
  marker.bindTooltip(tooltipHtml(pin),
      { permanent: false, direction: 'top', offset: [0, -8] })
    .on('click', () => pinClicked(pin.id));

  if (clusterEnabled && clusterGroup) clusterGroup.addLayer(marker);
  else marker.addTo(getMap());
  pinMarkers[pin.id] = marker;
  applyPinVisibility(pin.id);
}

/**
 * Bring the rendered set in line with an authoritative snapshot, keeping the
 * markers that survive it. The alternative -- clear everything, then draw it
 * all again -- is what full_state and inject_triggered used to do.
 */
export function syncPins(snapshot) {
  for (const pid of Object.keys(pins)) {
    if (!(pid in snapshot)) removePin(pid);
  }
  Object.values(snapshot).forEach(renderPin);
}

export function removePin(pid) {
  if (pinMarkers[pid]) {
    if (clusterEnabled && clusterGroup) clusterGroup.removeLayer(pinMarkers[pid]);
    else getMap().removeLayer(pinMarkers[pid]);
    delete pinMarkers[pid];
  }
  delete pins[pid];
}

export function clearAllPins() {
  Object.values(pinMarkers).forEach(m => {
    try { getMap().removeLayer(m); } catch {}
    try { if (clusterGroup) clusterGroup.removeLayer(m); } catch {}
  });
  if (clusterGroup) clusterGroup.clearLayers();
  // Emptied in place, not rebound: getPins() hands out this exact object, so
  // replacing it would strand every caller holding the previous one.
  for (const k of Object.keys(pinMarkers)) delete pinMarkers[k];
  for (const k of Object.keys(pins)) delete pins[k];
}

function matchesFilter(pin) {
  if (!filterQuery) return true;
  return pin.name.toLowerCase().includes(filterQuery)
      || pin.category.toLowerCase().includes(filterQuery);
}

/** The pins actually on show: matching the filter, in a visible category. */
export function getVisiblePins() {
  return Object.values(pins).filter(p => !hiddenCategories.has(p.category) && matchesFilter(p));
}

export function applyPinVisibility(pid) {
  const marker = pinMarkers[pid];
  const pin    = pins[pid];
  if (!marker || !pin) return;
  const catHidden  = hiddenCategories.has(pin.category);
  const filterMiss = !matchesFilter(pin);
  const opacity = catHidden ? 0 : filterMiss ? 0.1 : 1;
  marker.setOpacity(opacity);
  const el = marker.getElement?.();
  if (el) el.style.pointerEvents = (catHidden || filterMiss) ? 'none' : '';
}

export function filterPins(query) {
  filterQuery = query.toLowerCase().trim();
  let matched = 0;
  const total = Object.keys(pins).length;
  Object.values(pins).forEach(pin => {
    if (matchesFilter(pin) && !hiddenCategories.has(pin.category)) matched++;
    applyPinVisibility(pin.id);
  });
  const statusEl = document.getElementById('filter-status');
  statusEl.textContent = filterQuery
    ? `${matched} of ${total} pin${total !== 1 ? 's' : ''} match` : '';
}

export function clearFilter() {
  document.getElementById('pin-filter-inp').value = '';
  filterPins('');
}

export function toggleCategoryLayer(cat) {
  if (hiddenCategories.has(cat)) hiddenCategories.delete(cat);
  else hiddenCategories.add(cat);
  Object.values(pins).filter(p => p.category === cat).forEach(p => applyPinVisibility(p.id));
  renderCategoryToggles();
}

export const renderCategoryToggles = debounce(function _renderCategoryToggles() {
  const container = document.getElementById('cat-toggles');
  if (!container) return;
  const cats = [...new Set(Object.values(pins).map(p => p.category))].sort();
  if (!cats.length) {
    container.innerHTML = '<div class="dim-txt" style="font-size:10px;padding:2px 0">No assets pinned yet.</div>';
    return;
  }
  container.innerHTML = cats.map(cat => {
    const icon    = CATEGORY_ICONS[cat] || 'fa-circle-dot';
    const hidden  = hiddenCategories.has(cat);
    const count   = Object.values(pins).filter(p => p.category === cat).length;
    return `<button class="cat-toggle-btn${hidden ? ' cat-hidden' : ''}"
                    data-action="toggleCategoryLayer" data-args="${escHtml(JSON.stringify([cat]))}">
      <i class="fa-solid ${escHtml(icon)}"></i>
      <span class="cat-name">${escHtml(cat)}</span>
      <span class="cat-count">${count}</span>
    </button>`;
  }).join('');
}, 80);

export function toggleClusters() {
  clusterEnabled = !clusterEnabled;
  document.getElementById('cluster-btn')?.classList.toggle('btn-active', clusterEnabled);

  if (clusterEnabled) {
    if (!clusterGroup) {
      clusterGroup = L.markerClusterGroup({
        showCoverageOnHover: false,
        maxClusterRadius: 55,
        iconCreateFunction: c => L.divIcon({
          className: '',
          html: `<div class="cluster-icon">${c.getChildCount()}</div>`,
          iconSize: [36, 36], iconAnchor: [18, 18],
        }),
      });
      getMap().addLayer(clusterGroup);
    }
    Object.values(pinMarkers).forEach(m => { getMap().removeLayer(m); clusterGroup.addLayer(m); });
  } else {
    if (clusterGroup) {
      Object.values(pinMarkers).forEach(m => { clusterGroup.removeLayer(m); m.addTo(getMap()); });
      getMap().removeLayer(clusterGroup);
      clusterGroup = null;
    }
  }
}
