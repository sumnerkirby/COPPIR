// Map drawing tools: freehand markup and click-to-measure.
//
// These live together because they are mutually exclusive interaction modes
// and each has to be able to cancel the other -- starting a shape stops a
// measurement, clearing markup clears the measurement line. Split across two
// modules they imported each other in a cycle, which was a hint that they are
// one concern rather than two.
//
// isMeasuring() is exported because the map click, double-click and Escape
// handlers in app.js need to know whether a measurement is running. Exporting
// the flag itself would not work: an imported binding is read-only for the
// importer, so it would read as stale the moment this module changed it.

import { getMap } from './map.js';
import { escHtml, formatDist, haversineM } from './utils.js';

// markup
let drawnItems = null;
let activeDrawer = null;
let markupColor = '#FF3333';

// measurement
let active = false;
let points = [];
let layer = null;
let markers = [];
let lastClick = 0;   // ignores the second click of a double-click

/** Attach the markup layer and its draw handlers. Call once, after createMap. */
export function initMapTools() {
  const map = getMap();
  drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);
  map.on('draw:created', e => {
    drawnItems.addLayer(e.layer);
    clearActiveDrawer();
  });
  map.on('draw:drawstop', clearActiveDrawer);
}

function clearActiveDrawer() {
  activeDrawer = null;
  document.querySelectorAll('.markup-btn').forEach(b => b.classList.remove('btn-active'));
}

/**
 * Cancel a shape that is part-drawn. Returns whether there was one, so the
 * Escape handler can fall through to the next thing if not.
 */
export function cancelActiveDraw() {
  if (!activeDrawer) return false;
  activeDrawer.disable();
  clearActiveDrawer();
  return true;
}

export function startDraw(mode, btnId) {
  if (isMeasuring()) toggleMeasure();
  if (activeDrawer) { activeDrawer.disable(); return; }

  const fill = { color: markupColor, weight: 2, fillColor: markupColor, fillOpacity: 0.15 };
  const line = { color: markupColor, weight: 2 };
  const drawers = {
    polyline:  () => new L.Draw.Polyline(getMap(),  { shapeOptions: line }),
    polygon:   () => new L.Draw.Polygon(getMap(),   { shapeOptions: fill }),
    rectangle: () => new L.Draw.Rectangle(getMap(), { shapeOptions: fill }),
    circle:    () => new L.Draw.Circle(getMap(),    { shapeOptions: fill }),
  };
  const drawer = drawers[mode]?.();
  if (!drawer) return;
  drawer.enable();
  activeDrawer = drawer;
  document.getElementById(btnId)?.classList.add('btn-active');
}

export function setMarkupColor(hex) {
  markupColor = hex;
  document.querySelectorAll('.markup-swatch').forEach(s => {
    s.classList.toggle('swatch-active', s.dataset.color === hex);
  });
  const picker = document.getElementById('markup-color-picker');
  if (picker && !picker.matches(':focus')) picker.value = hex;
}

export function clearAllMarkup() {
  if (drawnItems) drawnItems.clearLayers();
  clearMeasure();
}

export function isMeasuring() {
  return active;
}

export function toggleMeasure() {
  if (activeDrawer) { activeDrawer.disable(); }
  active = !active;
  const btn = document.getElementById('measure-btn');
  if (active) {
    btn?.classList.add('btn-active');
    getMap().getContainer().style.cursor = 'crosshair';
    getMap().doubleClickZoom.disable();
    document.getElementById('measure-result').textContent = 'Click points · Double-click or Esc to finish';
  } else {
    finishMeasure();
  }
}

export function addMeasurePoint(latlng) {
  const now = Date.now();
  if (now - lastClick < 250) return;
  lastClick = now;

  points.push(latlng);
  const dot = L.circleMarker(latlng, {
    radius: 4, color: '#FFDD00', fillColor: '#FFDD00',
    fillOpacity: 1, weight: 1, interactive: false,
  }).addTo(getMap());
  markers.push(dot);

  if (layer) { getMap().removeLayer(layer); layer = null; }
  if (points.length >= 2) {
    layer = L.polyline(points, {
      color: '#FFDD00', weight: 2, dashArray: '5 4', interactive: false,
    }).addTo(getMap());
    document.getElementById('measure-result').textContent = formatDist(totalMeasureDist());
  }
}

export function finishMeasure() {
  active = false;
  getMap().getContainer().style.cursor = '';
  getMap().doubleClickZoom.enable();
  document.getElementById('measure-btn')?.classList.remove('btn-active');
  if (points.length >= 2) {
    document.getElementById('measure-result').textContent = `Total: ${formatDist(totalMeasureDist())}`;
  } else {
    clearMeasure();
  }
}

export function clearMeasure() {
  if (layer) { getMap().removeLayer(layer); layer = null; }
  markers.forEach(m => getMap().removeLayer(m));
  markers = [];
  points = [];
  const el = document.getElementById('measure-result');
  if (el) el.textContent = '';
}

function totalMeasureDist() {
  let total = 0;
  for (let i = 1; i < points.length; i++)
    total += haversineM(points[i-1].lat, points[i-1].lng, points[i].lat, points[i].lng);
  return total;
}
