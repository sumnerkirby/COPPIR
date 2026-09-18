// Shared lookup tables. Values only -- nothing here reads or writes state.
//
// The status colours are duplicated in style.css. Changing one means changing
// the other; folding them into CSS custom properties is worth doing separately.

export const STATUS_COLORS = {
  'Compromised':         { circle: '#FF3333', outside: '#AA0000' },
  'Under Investigation': { circle: '#FFAA00', outside: '#AA6600' },
  'Contained':           { circle: '#FF6600', outside: '#AA3300' },
  'Monitored':           { circle: '#3399FF', outside: '#005599' },
  'Clean':               { circle: '#33CC33', outside: '#007700' },
};

export const STATUS_SCORE = { Clean: 100, Monitored: 70, Contained: 40, 'Under Investigation': 15, Compromised: 0 };

export const SECTORS = [
  { key: 'medical',    cats: ['Hospitals'] },
  { key: 'government', cats: ['Government Buildings'] },
  { key: 'power',      cats: ['Power Plants'] },
  { key: 'emergency',  cats: ['Fire Stations', 'Police Stations'] },
  { key: 'civilian',   cats: ['Water Systems', 'Transportation Hubs', 'Telecom Infrastructure', 'Universities', 'Data Centers'] },
  { key: 'financial',  cats: ['Banks'] },
];

export const WHEEL_C = 2 * Math.PI * 19;

// Border style carries operational status alongside the colour. Every entry
// used to say 'solid', so the ring was colour and nothing else.
export const OP_STATUS_BORDER = {
  'Healthy':  { color: '#00FF41', style: 'solid',  width: '3px' },
  'Degraded': { color: '#FFD700', style: 'dashed', width: '3px' },
  'Critical': { color: '#FF4500', style: 'double', width: '4px' },
  'Offline':  { color: '#666666', style: 'dotted', width: '3px' },
};

// A second cue for security status. Compromised, Contained and Under
// Investigation are red, orange and amber -- close enough that colour alone
// does not separate them for a red-green colour-blind reader, which is a poor
// property for the thing the whole picture is meant to communicate.
export const STATUS_GLYPH = {
  'Compromised':         '\u2715',   // ✕
  'Under Investigation': '?',
  'Contained':           '\u25AA',   // ▪
  'Monitored':           '\u25E6',   // ◦
  'Clean':               '\u2713',   // ✓
};

export const SECTOR_ZONE_COLORS = {
  medical:    '#3399FF',
  government: '#AA88FF',
  power:      '#FFDD00',
  emergency:  '#FF4444',
  civilian:   '#00CCAA',
  financial:  '#FFB000',
};

export const CATEGORY_ICONS = {
  'Hospitals':              'fa-hospital',
  'Government Buildings':   'fa-landmark',
  'Power Plants':           'fa-bolt',
  'Fire Stations':          'fa-fire',
  'Police Stations':        'fa-shield-halved',
  'Water Systems':          'fa-droplet',
  'Transportation Hubs':    'fa-plane',
  'Telecom Infrastructure': 'fa-tower-cell',
  'Data Centers':           'fa-database',
  'Universities':           'fa-graduation-cap',
  'Banks':                  'fa-building-columns',
  'Asset':                  'fa-server',
  'Responder':              'fa-user-shield',
  'POI':                    'fa-location-dot',
};

export const OPS_COLORS = {
  'Healthy':  '#00FF41',
  'Degraded': '#FFD700',
  'Critical': '#FF4500',
  'Offline':  '#888888',
};
