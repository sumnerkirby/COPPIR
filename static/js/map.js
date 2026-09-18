// Owns the Leaflet map instance and whether it is locked.
//
// This module stays a leaf on purpose: it creates the map and hands it over,
// but registers none of the application's own handlers. Those live in app.js,
// because wiring them here would mean importing the features back and turning
// the dependency into a cycle.

import { showToast } from './toast.js';

let map = null;
let locked = false;

const ESRI_CANVAS = 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas';
const ESRI_OPTS = { maxNativeZoom: 16, maxZoom: 19 };

/** Build the map with its basemap and scale bar. Call once. */
export function createMap() {
  map = L.map('map', { zoomControl: true }).setView([39.5, -98.35], 5);

  // Esri splits this basemap into terrain and labels, so both go on. Note the
  // tile path is {z}/{y}/{x}, not the usual {z}/{x}/{y}.
  // Only cached to z16; past that Esri serves a light "no data" tile that
  // wrecks the dark theme, so cap requests there and let Leaflet upscale.
  L.tileLayer(`${ESRI_CANVAS}/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`, {
    ...ESRI_OPTS,
    attribution: 'Tiles &copy; <a href="https://www.esri.com/">Esri</a> &mdash; '
               + 'Esri, HERE, Garmin, &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> '
               + 'contributors, and the GIS user community',
  }).addTo(map);

  L.tileLayer(`${ESRI_CANVAS}/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
              ESRI_OPTS).addTo(map);

  L.control.scale({ imperial: true, metric: false, position: 'bottomright' }).addTo(map);

  return map;
}

/** The map instance. Null until createMap() has run. */
export function getMap() {
  return map;
}

export function isMapLocked() {
  return locked;
}

export function toggleMapLock() {
  locked = !locked;
  for (const handler of ['dragging', 'scrollWheelZoom', 'boxZoom', 'keyboard']) {
    locked ? map[handler].disable() : map[handler].enable();
  }
  const btn = document.getElementById('map-lock-btn');
  btn?.classList.toggle('btn-active', locked);
  if (btn) btn.textContent = locked ? 'LOCKED' : 'LOCK MAP';
  showToast(locked ? 'Map locked' : 'Map unlocked');
}
