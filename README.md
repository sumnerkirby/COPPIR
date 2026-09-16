# COPPIR

**Common Operational Picture Program for Incident Response**

COPPIR is a local desktop application for building and managing a live common operational picture during incident response training exercises. It runs entirely on a single machine with no internet account or cloud dependency required.

---

## Contents

- [Getting Started](#getting-started)
- [The Map](#the-map)
- [Pins](#pins)
- [Connections](#connections)
- [SITREP Strip](#sitrep-strip)
- [Custom Metrics](#custom-metrics)
- [Decision Log](#decision-log)
- [Injects](#injects)
- [Alert Thresholds](#alert-thresholds)
- [Map Markup](#map-markup)
- [Measure Tool](#measure-tool)
- [Sector Zones](#sector-zones)
- [Heatmaps](#heatmaps)
- [Scenarios](#scenarios)
- [Export](#export)
- [Keyboard Shortcuts](#keyboard-shortcuts)

---

## Getting Started

### Running from source

```bash
pip install fastapi uvicorn httpx pydantic pywebview
python run.py
```

### Running a built package

- **macOS:** Open `COPPIR-mac.dmg`, drag COPPIR to Applications, double-click to launch. On first launch, if macOS blocks it: System Settings > Privacy & Security > Open Anyway.
- **Windows:** Extract `COPPIR-windows.zip`, open the `COPPIR` folder, double-click `COPPIR.exe`. If SmartScreen warns, click More Info > Run Anyway.
- **Linux:** Extract `COPPIR-linux.tar.gz` and run `./COPPIR-linux/COPPIR` from a terminal.

The app opens a dark-themed desktop window. A loading screen displays briefly while the internal server starts, then the map loads automatically.

---

## The Map

The full-screen map is the primary workspace. It uses Esri's Dark Gray Canvas basemap, which requires no API key. Tiles are cached by the provider through zoom 16 and upscaled beyond that, so street-level zoom stays on-theme.

**Navigation**

- Click and drag to pan
- Scroll wheel or trackpad to zoom
- Right-click anywhere on the map to open the context menu for quick pin placement

**Lock Map**

The toolbar includes a **LOCK MAP** button. When locked, the map cannot be panned or zoomed. Use this when drawing markup shapes so accidental drags do not move the map instead of completing the shape.

**Scale bar**

A distance scale in miles is displayed in the bottom-right corner.

---

## Pins

Pins represent assets, responders, or points of interest on the map.

### Placing pins

**Right-click menu** — right-click any map location to place a pin of a specific category (Asset, Responder, POI, or infrastructure type). A dialog prompts for a name.

**Search and place** — use the Location Search panel to find an address with the geocoder, then click a result to drop a pin there.

**OSM Import** — use the OSM Query panel to search for real-world infrastructure within a radius: hospitals, government buildings, power plants, fire stations, police stations, data centers, universities, banks, water systems, transportation hubs, or telecom infrastructure. Results appear in a list; select any or all and click **PIN ALL** to place them on the map.

### Pin appearance

Each pin's icon encodes two pieces of status information simultaneously:

- **Fill color** — reflects security status (green = Clean, blue = Monitored, orange = Contained, amber = Under Investigation, red = Compromised). A custom color can override this.
- **Border color** — reflects operational status (bright green = Healthy, yellow = Degraded, red = Critical, grey = Offline).

### Editing a pin

Click any pin to open the edit modal. From there you can:

- Rename the pin or change its category
- Update **Security Status**: Clean, Monitored, Contained, Under Investigation, Compromised
- Update **Operational Status**: Healthy, Degraded, Critical, Offline
- Set a custom pin color (overrides the status-based color)
- Add freeform notes
- View the full status change history for that pin
- Manage connections to other pins (see Connections)
- Delete the pin

### Bulk status update

The **Bulk Status** panel lets you apply a security or operational status to all pins in a category at once. Useful for simulating a sector-wide event during an exercise.

### Filtering and searching

The filter bar at the top of the toolbar searches pin names in real time and hides non-matching pins. The category toggles at the bottom of the toolbar show or hide all pins of a specific type.

---

## Connections

Pins can be connected to each other to represent dependencies, communication links, or relationships.

- Open a pin's edit modal and use the **Link to asset** dropdown to create a connection.
- Connections are drawn as lines on the map. They update position automatically if either endpoint pin is moved.
- Connections can be removed from the edit modal of either pin.

---

## SITREP Strip

The strip across the top of the screen provides a live summary of the operational picture.

**Security Status counts** — running totals of pins in each status (Compromised, Under Investigation, Contained, Monitored, Clean) plus a total count.

**Operational Status counts** — running totals of pins in each operational state (Healthy, Degraded, Critical, Offline).

**Sector integrity wheels** — one arc wheel per sector shows the mean integrity score of all pins belonging to that sector's infrastructure categories. Integrity is derived from security status: Clean = 100%, Monitored = 70%, Contained = 40%, Under Investigation = 15%, Compromised = 0%. The arc color shifts from green to yellow to red as integrity falls.

| Sector | Categories |
|---|---|
| Medical | Hospitals |
| Government | Government Buildings |
| Power | Power Plants |
| Emergency | Fire Stations, Police Stations |
| Civilian | Water Systems, Transportation Hubs, Telecom Infrastructure, Universities |
| Financial | Banks |

Counts and wheels update automatically whenever any pin changes. During large imports they are debounced so the interface stays responsive.

---

## Custom Metrics

The **METRICS** button in the toolbar opens a panel of user-defined percentage wheels. These track anything not covered by the sector wheels — resource availability, comms readiness, personnel status, or any other percentage-based metric relevant to the exercise.

- **Add** a metric with the input at the bottom of the panel
- **Adjust** a wheel's value with the − and + buttons (increments of 5%)
- **Click the wheel** to type in an exact value
- **Rename** a metric by clicking its label and typing
- **Delete** a metric with the × button

Custom metrics are saved to `localStorage` and persist across sessions.

---

## Decision Log

The **LOG** button opens the decision log panel. All actions that change the operational picture are automatically recorded here with a timestamp. Entries are also created manually.

**Automatic entries** are created when:
- An inject is triggered (labeled AUTO)

**Manual entries** are created from the log panel:
- Type an action description in the text field
- Optionally select a specific asset the entry relates to
- Press Enter or click **LOG**

The log auto-scrolls to the latest entry. If you scroll up to review history, auto-scroll pauses and resumes when you scroll back to the bottom.

---

## Injects

Injects are pre-planned scenario events that can be queued and fired at any time during an exercise. They are authored in advance and triggered by the exercise controller.

### Creating an inject

Open the **Injects** panel and click **+ NEW INJECT**. Fill in:

- **Title** — short label shown in the inject list
- **Description** — full event text, logged when triggered
- **Severity** — Info, Warning, or Critical (controls the color of the alert banner)
- **Target pin** (optional) — an existing asset to be affected
- **New status** (optional) — the status the target pin will be changed to when fired
- **New pin** (optional) — a new asset to be created on the map when fired

### Firing an inject

Click the **FIRE** button next to a queued inject. The following happen simultaneously:

1. The target pin's status is updated (if configured)
2. A new pin is placed on the map (if configured)
3. A log entry is appended automatically
4. All connected clients receive the update in real time
5. A colored alert banner appears on screen briefly

Once fired, an inject is marked as triggered with a timestamp and cannot be fired again.

---

## Alert Thresholds

Thresholds watch a sector's integrity and trigger a visual alert when it falls below a configured level.

Open the **Thresholds** panel to create a rule:

- **Name** — label for the threshold
- **Sector** — which sector to watch (or All)
- **Below %** — the integrity percentage that triggers the alert
- **Severity** — Info, Warning, or Critical

When a sector's integrity drops below the threshold, a warning indicator appears in the SITREP strip for that sector. Multiple thresholds can be configured for the same sector at different levels.

---

## Map Markup

The **MAP MARKUP** section of the toolbar provides drawing tools for annotating the map with shapes and lines. These are visual overlays only and are not saved with scenarios.

| Tool | Use |
|---|---|
| Polygon | Draw a filled area boundary |
| Rectangle | Draw a rectangular zone |
| Circle | Draw a circular area |
| Line | Draw a freeform polyline |
| Marker | Place a simple map marker |

A color picker sets the color for new shapes. **CLEAR ALL** removes all markup at once.

Lock the map before drawing to prevent accidental panning.

---

## Measure Tool

The **MEASURE** button activates a click-to-measure mode. Click points on the map to build a path; the cumulative distance updates with each click. Double-click or press Escape to finish. The measurement is displayed on the map and removed automatically when you start a new measurement.

---

## Sector Zones

The **SECTOR ZONES** toggle draws translucent colored overlay circles on the map centered on the geographic centroid of each sector's pins. Circle color reflects the sector's current integrity. Hover a zone to see a tooltip listing the assets and their current statuses. Zone labels appear at zoom levels where they are readable and hide at street-level zoom.

---

## Heatmaps

Two heatmap modes visualize pin density spatially:

- **HEAT MAP** — intensity based on security status severity (compromised pins contribute more heat)
- **OPS HEAT MAP** — intensity based on operational status (offline and critical pins contribute more heat)

Both are toggled on and off and rebuild automatically whenever pins change.

---

## Scenarios

Scenarios save and restore the complete state of a session: all pins, edges, injects, thresholds, and the decision log.

**Saving** — open the scenario modal (toolbar or Ctrl+S), enter a name, and click **SAVE**.

**Loading** — select a saved scenario from the list and click **LOAD**. The current session is replaced.

**Deleting** — click the X next to a scenario in the list.

Scenario files are stored as JSON in a `scenarios/` folder next to the application. They can be copied between machines.

---

## Export

**Export Log (CSV)** — downloads the full decision log as a CSV file suitable for after-action reporting.

**Export Briefing** — generates a standalone HTML document containing a SITREP summary table, sector integrity scores, a full pin inventory with statuses, and the last 30 log entries. The file can be opened in any browser and printed.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+S | Open scenario save/load modal |
| Ctrl+L | Toggle decision log panel |
| Ctrl+Z | Undo last pin placement |
| Escape | Cancel active drawing, finish measure, or close modal |
| ? | Show keyboard shortcut reference |

---

## Connection Status

A small dot in the top-left corner next to the clock shows the WebSocket connection status. Green means the interface is live and receiving updates. Red means the connection was lost and the app is attempting to reconnect automatically. No data is lost during a brief disconnect; the server holds state and sends a full sync when the connection is restored.
