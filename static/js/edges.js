// Edges: the dependency lines drawn between two pins.
//
// Depends on pins.js for endpoint coordinates, and nothing depends on this in
// return. Clearing an edge when its pin disappears is coordinated in app.js
// rather than from inside pins.js, which keeps that one-way.

import { getMap } from './map.js';
import { getPins } from './pins.js';

const edges = {};
const edgeLayers = {};
let edgesVisible = true;

export function getEdges() {
  return edges;
}

/** Drop every edge touching a pin. Called when that pin is removed. */
export function removeEdgesTouching(pid) {
  for (const eid of Object.keys(edges)) {
    if (edges[eid].from_pid === pid || edges[eid].to_pid === pid) removeEdge(eid);
  }
}

export function renderEdge(edge) {
  if (edgeLayers[edge.id]) { getMap().removeLayer(edgeLayers[edge.id]); }
  edges[edge.id] = edge;
  const allPins = getPins();
  const fromPin = allPins[edge.from_pid];
  const toPin   = allPins[edge.to_pid];
  if (!fromPin || !toPin) return;

  const line = L.polyline([[fromPin.lat, fromPin.lon], [toPin.lat, toPin.lon]], {
    color: '#00ff41', weight: 1.5, opacity: edgesVisible ? 0.7 : 0,
    dashArray: '6 4', interactive: edgesVisible,
  }).addTo(getMap());

  line.bindTooltip(
    `<div style="font-size:10px">${fromPin.name} <b>→</b> ${toPin.name}${edge.label ? '<br><span style="opacity:.7">' + edge.label + '</span>' : ''}</div>`,
    { sticky: true }
  );
  line.on('click', e => {
    L.DomEvent.stopPropagation(e);
    if (confirm(`Delete connection:\n${fromPin.name} → ${toPin.name}?`)) {
      fetch(`/api/edges/${edge.id}`, { method: 'DELETE' });
    }
  });

  edgeLayers[edge.id] = line;
}

export function removeEdge(eid) {
  if (edgeLayers[eid]) { getMap().removeLayer(edgeLayers[eid]); delete edgeLayers[eid]; }
  delete edges[eid];
}

export function clearAllEdges() {
  Object.keys(edgeLayers).forEach(eid => { getMap().removeLayer(edgeLayers[eid]); });
  // Emptied in place for the same reason as pins: getEdges() returns this object.
  for (const k of Object.keys(edgeLayers)) delete edgeLayers[k];
  for (const k of Object.keys(edges)) delete edges[k];
}
