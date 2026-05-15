import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import tkintermapview
from geopy.geocoders import Nominatim
import ssl
import certifi
import requests
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BG_DEEP   = "#000a00"
BG_PANEL  = "#010e01"
BG_SITREP = "#000d00"
BG_INPUT  = "#000800"
FG_BRIGHT = "#00ff41"
FG_MED    = "#00cc33"
FG_DIM    = "#336633"
FG_TEXT   = "#99ffaa"
BORDER    = "#005500"
SEL_BG    = "#003a00"

BTN_STD    = {"bg": "black", "fg": FG_BRIGHT, "bd": 2}
BTN_DANGER = {"bg": "black", "fg": "#ff5555", "bd": 2}
BTN_BLUE   = {"bg": "black", "fg": "#6699ff", "bd": 2}
BTN_DIM    = {"bg": "black", "fg": FG_DIM,    "bd": 1}
BTN_SAVE   = {"bg": "black", "fg": "#00ff41", "bd": 2}

# ---------------------------------------------------------------------------
# Operational constants
# ---------------------------------------------------------------------------
STATUS_COLORS = {
    "Compromised":          {"circle": "#FF3333", "outside": "#AA0000", "fg": "#FF6666"},
    "Under Investigation":  {"circle": "#FFAA00", "outside": "#AA6600", "fg": "#FFCC55"},
    "Contained":            {"circle": "#FF6600", "outside": "#AA3300", "fg": "#FF9944"},
    "Monitored":            {"circle": "#3399FF", "outside": "#005599", "fg": "#66AAFF"},
    "Clean":                {"circle": "#33CC33", "outside": "#007700", "fg": "#66FF66"},
}
STATUS_SHORT = {
    "Compromised": "COMP", "Under Investigation": "INVS",
    "Contained": "CONT", "Monitored": "MON", "Clean": "CLN",
}
# Score used to calculate sector wheel integrity (0-100)
STATUS_SCORE = {
    "Clean": 100, "Monitored": 70, "Contained": 40,
    "Under Investigation": 15, "Compromised": 0,
}

RESPONDER_COLORS = {
    "IR Analyst":          {"circle": "#9933FF", "outside": "#5500AA"},
    "Forensics":           {"circle": "#CC33FF", "outside": "#880099"},
    "Law Enforcement":     {"circle": "#3366FF", "outside": "#002299"},
    "Management":          {"circle": "#888888", "outside": "#444444"},
    "Vendor / Contractor": {"circle": "#FF9900", "outside": "#995500"},
}

ASSET_TYPES = [
    "Server Farm / Data Center", "Office / Facility", "Network Device",
    "ISP / Telecom", "Cloud Provider", "Government",
    "Critical Infrastructure", "Other",
]

IR_OSM_QUERIES = {
    "Data Centers":         "nwr['telecom'='data_center']",
    "Hospitals":            "nwr['amenity'='hospital']",
    "Government Buildings": "nwr['building'='government']",
    "Police Stations":      "nwr['amenity'='police']",
    "Fire Stations":        "nwr['amenity'='fire_station']",
    "Power Plants":         "nwr['power'='plant']",
    "Universities":         "nwr['amenity'='university']",
    "Banks":                "nwr['amenity'='bank']",
}

MAP_STYLES = {
    "Dark Mode":        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    "OpenStreetMap":    "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "Google Standard":  "https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga",
    "Google Satellite": "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga",
    "Google Terrain":   "https://mt0.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}&s=Ga",
}

PIN_PRESETS = [
    "#FF3333", "#FF6600", "#FFAA00", "#FFFF00",
    "#33CC33", "#00FFFF", "#3399FF", "#9933FF",
    "#FF33CC", "#FFFFFF", "#888888", "#FF00FF",
]
PINNED_DEFAULT = {"circle": "#00ff41", "outside": "#007722"}

# Sector wheels: each maps to one or more OSM categories
SECTORS = [
    {"key": "medical",    "label": "MEDICAL SVC",   "cats": ["Hospitals"]},
    {"key": "government", "label": "GOVT INFRA",    "cats": ["Government Buildings"]},
    {"key": "power",      "label": "POWER GRID",    "cats": ["Power Plants"]},
    {"key": "emergency",  "label": "EMERGENCY SVC", "cats": ["Fire Stations", "Police Stations"]},
    {"key": "info_env",   "label": "INFO ENV",      "cats": ["Data Centers", "Universities", "Banks"]},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def darken_hex(hex_color, factor=0.55):
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


def integrity_color(pct):
    """Red(0%) → Yellow(50%) → Green(100%)."""
    pct = max(0.0, min(100.0, pct))
    if pct >= 50:
        r = int(255 * (1.0 - (pct - 50) / 50.0))
        g = 200
    else:
        r = 220
        g = int(200 * pct / 50.0)
    return f"#{r:02x}{g:02x}00"


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class COPApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IRCOP")
        self.root.geometry("1440x920")
        self.root.configure(bg=BG_DEEP)

        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        self.geolocator = Nominatim(user_agent="ircop_v1", ssl_context=ssl_ctx)

        self.assets      = {}
        self.responders  = {}
        self.osm_markers = []
        self.pinned      = {}
        self._id_counter = 0
        self.placing_mode = None

        self._apply_ttk_theme()
        self._build_menubar()
        self._build_topbar()
        self._build_main()
        self._build_sitrep()
        self._build_log()

        self.root.bind("<Escape>",    lambda _: self._set_mode(None))
        self.root.bind("<Control-s>", lambda _: self._save())
        self.root.bind("<Control-o>", lambda _: self._load())

        self._update_sitrep()
        self._log("IRCOP online. Right-click map to place assets or responders.")

    # -----------------------------------------------------------------------
    # Theme
    # -----------------------------------------------------------------------
    def _apply_ttk_theme(self):
        s = ttk.Style()
        s.theme_use("default")
        s.configure("TCombobox", fieldbackground=BG_INPUT, background="black",
                    foreground=FG_BRIGHT, selectbackground=SEL_BG,
                    selectforeground=FG_BRIGHT, arrowcolor=FG_MED)
        s.map("TCombobox",
              fieldbackground=[("readonly", BG_INPUT)],
              foreground=[("readonly", FG_BRIGHT)],
              selectbackground=[("readonly", SEL_BG)])
        s.configure("TScrollbar", background="black",
                    troughcolor=BG_DEEP, arrowcolor=FG_MED)

    def _new_id(self):
        self._id_counter += 1
        return self._id_counter

    # -----------------------------------------------------------------------
    # Button factory
    # -----------------------------------------------------------------------
    def _btn(self, parent, label, cmd, style=None, width=None,
             font_size=11, side=None, padx=4, pady=0):
        s = style or BTN_STD
        kw = dict(
            text=label, command=cmd,
            bg=s["bg"], fg=s["fg"],
            activebackground="#001a00", activeforeground=FG_BRIGHT,
            font=("Helvetica", font_size, "bold"),
            relief="raised", bd=s.get("bd", 2),
            padx=10, pady=5, cursor="hand2",
        )
        if width:
            kw["width"] = width
        b = tk.Button(parent, **kw)
        if side is not None:
            b.pack(side=side, padx=padx, pady=pady)
        return b

    # -----------------------------------------------------------------------
    # Menu bar
    # -----------------------------------------------------------------------
    def _build_menubar(self):
        mb = tk.Menu(self.root)
        self.root.config(menu=mb)

        fm = tk.Menu(mb, tearoff=0, bg=BG_PANEL, fg=FG_TEXT,
                     activebackground=SEL_BG, activeforeground=FG_BRIGHT)
        fm.add_command(label="Save COP    Ctrl+S", command=self._save)
        fm.add_command(label="Load COP    Ctrl+O", command=self._load)
        fm.add_separator()
        fm.add_command(label="Quit", command=self.root.quit)
        mb.add_cascade(label="File", menu=fm)

        vm = tk.Menu(mb, tearoff=0, bg=BG_PANEL, fg=FG_TEXT,
                     activebackground=SEL_BG, activeforeground=FG_BRIGHT)
        sm = tk.Menu(vm, tearoff=0, bg=BG_PANEL, fg=FG_TEXT,
                     activebackground=SEL_BG, activeforeground=FG_BRIGHT)
        for name in MAP_STYLES:
            sm.add_command(label=name, command=lambda n=name: self._set_map_style(n))
        vm.add_cascade(label="Map Style", menu=sm)
        mb.add_cascade(label="View", menu=vm)

        em = tk.Menu(mb, tearoff=0, bg=BG_PANEL, fg=FG_TEXT,
                     activebackground=SEL_BG, activeforeground=FG_BRIGHT)
        em.add_command(label="Clear All Markers", command=self._clear_all)
        em.add_command(label="Clear Log",         command=self._clear_log)
        mb.add_cascade(label="Exercise", menu=em)

    # -----------------------------------------------------------------------
    # Top bar
    # -----------------------------------------------------------------------
    def _build_topbar(self):
        top = tk.Frame(self.root, bg=BG_PANEL, pady=8)
        top.pack(fill="x")

        tk.Label(top, text="[ IRCOP ]", fg=FG_BRIGHT, bg=BG_PANEL,
                 font=("Courier", 15, "bold")).pack(side="left", padx=(12, 8))
        tk.Frame(top, bg=BORDER, width=2).pack(side="left", fill="y", padx=6)

        self.location_entry = tk.Entry(
            top, width=24, font=("Helvetica", 12),
            bg=BG_INPUT, fg=FG_BRIGHT, insertbackground=FG_BRIGHT,
            relief="sunken", bd=2)
        self.location_entry.pack(side="left", padx=(4, 4))
        self.location_entry.bind("<Return>", self._search_location)

        self._btn(top, "GO", self._search_location, side="left", padx=2)
        tk.Frame(top, bg=BORDER, width=2).pack(side="left", fill="y", padx=8)

        self._btn(top, "+ ASSET",
                  lambda: self._set_mode("asset"),
                  style={"bg": "black", "fg": "#ff5555", "bd": 2},
                  side="left", padx=4)
        self._btn(top, "+ RESPONDER",
                  lambda: self._set_mode("responder"),
                  style=BTN_BLUE, side="left", padx=4)
        self._btn(top, "BROWSE",
                  lambda: self._set_mode(None),
                  style=BTN_DIM, side="left", padx=4)

        tk.Frame(top, bg=BORDER, width=2).pack(side="left", fill="y", padx=8)
        self.mode_label = tk.Label(top, text="MODE: BROWSE",
                                   fg=FG_MED, bg=BG_PANEL,
                                   font=("Courier", 12, "bold"))
        self.mode_label.pack(side="left", padx=6)

        tk.Label(top, text="Esc=browse  |  right-click map to place",
                 fg=FG_DIM, bg=BG_PANEL,
                 font=("Helvetica", 9)).pack(side="right", padx=12)

    # -----------------------------------------------------------------------
    # Main area (map + sidebar)
    # -----------------------------------------------------------------------
    def _build_main(self):
        main = tk.Frame(self.root, bg=BG_DEEP)
        main.pack(fill="both", expand=True)

        self.map_widget = tkintermapview.TkinterMapView(
            main, width=980, height=520, corner_radius=0)
        self.map_widget.pack(side="left", fill="both", expand=True)
        self.map_widget.set_position(38.8951, -77.0364)
        self.map_widget.set_zoom(11)
        self.map_widget.set_tile_server(MAP_STYLES["Dark Mode"], max_zoom=19)

        self.map_widget.add_right_click_menu_command(
            label="Add Asset Here",
            command=lambda c: self._show_asset_dialog(c[0], c[1]),
            pass_coords=True)
        self.map_widget.add_right_click_menu_command(
            label="Add Responder Here",
            command=lambda c: self._show_responder_dialog(c[0], c[1]),
            pass_coords=True)
        self.map_widget.add_left_click_map_command(self._on_map_click)

        sidebar = tk.Frame(main, bg=BG_PANEL, width=340)
        sidebar.pack(side="right", fill="y")
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

    def _build_sidebar(self, parent):
        def hdr(text, color=FG_BRIGHT):
            tk.Label(parent, text=text, bg=BG_PANEL, fg=color,
                     font=("Courier", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 3))

        def divider():
            tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=6, pady=4)

        hdr(">> STATUS LEGEND")
        leg = tk.Frame(parent, bg=BG_PANEL)
        leg.pack(fill="x", padx=14, pady=(0, 4))
        for status, info in STATUS_COLORS.items():
            row = tk.Frame(leg, bg=BG_PANEL)
            row.pack(anchor="w", pady=2)
            tk.Label(row, text="■", fg=info["circle"], bg=BG_PANEL,
                     font=("Helvetica", 12)).pack(side="left")
            tk.Label(row, text=f"  {status}", fg=FG_TEXT, bg=BG_PANEL,
                     font=("Helvetica", 10)).pack(side="left")

        divider()
        hdr(">> IR INFRASTRUCTURE")

        row1 = tk.Frame(parent, bg=BG_PANEL)
        row1.pack(fill="x", padx=8, pady=(0, 4))
        self.osm_var = tk.StringVar(value=list(IR_OSM_QUERIES.keys())[0])
        ttk.Combobox(row1, textvariable=self.osm_var,
                     values=list(IR_OSM_QUERIES.keys()),
                     state="readonly", width=22).pack(side="left", padx=(0, 6))
        self._btn(row1, "FIND", self._find_ir_infra,
                  side="left", font_size=10, padx=2)

        divider()
        hdr(">> PINNED LOCATIONS", FG_BRIGHT)

        row2 = tk.Frame(parent, bg=BG_PANEL)
        row2.pack(fill="x", padx=8, pady=(0, 4))
        self._btn(row2, "PIN ALL RESULTS", self._pin_all_osm,
                  side="left", font_size=9, padx=2)
        self._btn(row2, "CLR RESULTS", self._clear_osm_markers,
                  style=BTN_DANGER, side="left", font_size=9, padx=4)

        row3 = tk.Frame(parent, bg=BG_PANEL)
        row3.pack(fill="x", padx=8, pady=(0, 4))
        self._btn(row3, "CLR ALL PINS", self._clear_pinned,
                  style=BTN_DANGER, side="left", font_size=9, padx=2)
        self.pin_count_label = tk.Label(row3, text="0 pinned",
                                        bg=BG_PANEL, fg=FG_DIM,
                                        font=("Helvetica", 9))
        self.pin_count_label.pack(side="left", padx=8)

        lf = tk.Frame(parent, bg=BG_DEEP,
                      highlightthickness=1, highlightbackground=BORDER)
        lf.pack(fill="both", expand=True, padx=6, pady=2)
        self.pinned_list = tk.Listbox(
            lf, bg=BG_DEEP, fg=FG_TEXT, font=("Courier", 9),
            selectbackground=SEL_BG, selectforeground=FG_BRIGHT,
            borderwidth=0, highlightthickness=0, activestyle="none")
        psb = ttk.Scrollbar(lf, command=self.pinned_list.yview)
        self.pinned_list.configure(yscrollcommand=psb.set)
        psb.pack(side="right", fill="y")
        self.pinned_list.pack(fill="both", expand=True)
        self.pinned_list.bind("<Double-Button-1>", self._goto_pinned)
        self.pinned_list.bind("<Delete>", self._delete_selected_pinned)

        tk.Label(parent, text="  dbl-click: center map   Del: remove",
                 bg=BG_PANEL, fg=FG_DIM, font=("Helvetica", 8)
                 ).pack(anchor="w", padx=8, pady=(2, 4))

    # -----------------------------------------------------------------------
    # SITREP panel (count strip + sector wheels)
    # -----------------------------------------------------------------------
    def _build_sitrep(self):
        panel = tk.Frame(self.root, bg=BG_SITREP,
                         highlightthickness=1, highlightbackground=BORDER)
        panel.pack(fill="x")

        # — Count strip —
        count_row = tk.Frame(panel, bg=BG_SITREP)
        count_row.pack(fill="x", padx=12, pady=(6, 2))

        tk.Label(count_row, text="SITREP:", bg=BG_SITREP, fg=FG_DIM,
                 font=("Courier", 10, "bold")).pack(side="left", padx=(0, 8))

        self._sitrep_labels = {}
        for status, info in STATUS_COLORS.items():
            lbl = tk.Label(count_row, text=f"■ {STATUS_SHORT[status]}: 0",
                           bg=BG_SITREP, fg=info["fg"],
                           font=("Courier", 11, "bold"))
            lbl.pack(side="left", padx=8)
            self._sitrep_labels[status] = lbl

        tk.Frame(count_row, bg=BORDER, width=1).pack(side="left", fill="y", padx=6)
        self._resp_sitrep = tk.Label(count_row, text="RESP: 0",
                                     bg=BG_SITREP, fg="#9966FF",
                                     font=("Courier", 11, "bold"))
        self._resp_sitrep.pack(side="left", padx=8)

        self._pins_sitrep = tk.Label(count_row, text="PINS: 0",
                                     bg=BG_SITREP, fg=FG_MED,
                                     font=("Courier", 11, "bold"))
        self._pins_sitrep.pack(side="left", padx=8)

        self._sitrep_ts = tk.Label(count_row, text="", bg=BG_SITREP, fg=FG_DIM,
                                   font=("Courier", 8))
        self._sitrep_ts.pack(side="right")

        # — Sector wheels —
        wheels_row = tk.Frame(panel, bg=BG_SITREP)
        wheels_row.pack(fill="x", padx=8, pady=(4, 8))

        self._wheel_canvases = {}
        for sector in SECTORS:
            col = tk.Frame(wheels_row, bg=BG_SITREP)
            col.pack(side="left", expand=True)
            cv = tk.Canvas(col, width=110, height=115,
                           bg=BG_SITREP, highlightthickness=0)
            cv.pack()
            self._wheel_canvases[sector["key"]] = cv

    def _redraw_wheel(self, key, pct):
        cv = self._wheel_canvases[key]
        cv.delete("all")
        label = next(s["label"] for s in SECTORS if s["key"] == key)
        cx, cy, r, rw = 55, 48, 38, 11

        # Background ring
        cv.create_arc(cx-r, cy-r, cx+r, cy+r, start=0, extent=359.9,
                      style="arc", outline="#1a2a1a", width=rw)

        if pct is None:
            cv.create_text(cx, cy, text="N/A", fill="#334433",
                           font=("Courier", 9, "bold"))
        else:
            color = integrity_color(pct)
            extent = 359.9 * pct / 100.0
            if extent > 0:
                cv.create_arc(cx-r, cy-r, cx+r, cy+r,
                              start=90, extent=-extent,
                              style="arc", outline=color, width=rw)
            cv.create_text(cx, cy, text=f"{int(pct)}%",
                           fill=color, font=("Courier", 10, "bold"))

        cv.create_text(cx, cy+r+14, text=label, fill=FG_TEXT,
                       font=("Courier", 8, "bold"))

    def _update_sitrep(self):
        counts = {s: 0 for s in STATUS_COLORS}
        for a in self.assets.values():
            counts[a["status"]] = counts.get(a["status"], 0) + 1
        for status, lbl in self._sitrep_labels.items():
            lbl.config(text=f"■ {STATUS_SHORT[status]}: {counts[status]}")
        self._resp_sitrep.config(text=f"RESP: {len(self.responders)}")
        self._pins_sitrep.config(text=f"PINS: {len(self.pinned)}")
        self._sitrep_ts.config(text=datetime.now().strftime("%H:%M:%S"))

        for sector in SECTORS:
            key  = sector["key"]
            cats = sector["cats"]
            scored = [p for p in self.pinned.values()
                      if p.get("category") in cats and p.get("status") in STATUS_SCORE]
            pct = (sum(STATUS_SCORE[p["status"]] for p in scored) / len(scored)
                   if scored else None)
            self._redraw_wheel(key, pct)

    # -----------------------------------------------------------------------
    # Log
    # -----------------------------------------------------------------------
    def _build_log(self):
        wrap = tk.Frame(self.root, bg=BG_PANEL,
                        highlightthickness=1, highlightbackground=BORDER)
        wrap.pack(fill="x")
        hdr = tk.Frame(wrap, bg=BG_PANEL)
        hdr.pack(fill="x")
        tk.Label(hdr, text=">> INCIDENT LOG", bg=BG_PANEL, fg=FG_BRIGHT,
                 font=("Courier", 10, "bold")).pack(side="left", padx=10, pady=4)
        self._btn(hdr, "Clear Log", self._clear_log,
                  style=BTN_DIM, font_size=9, side="right", padx=8, pady=2)

        self.log_text = tk.Text(
            wrap, height=5, bg=BG_DEEP, fg=FG_MED,
            font=("Courier", 10), state="disabled", wrap="word",
            insertbackground=FG_BRIGHT, relief="flat")
        lsb = ttk.Scrollbar(wrap, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")
        self.log_text.pack(fill="x", padx=6, pady=(0, 6))

    # -----------------------------------------------------------------------
    # Mode / style
    # -----------------------------------------------------------------------
    def _set_mode(self, mode):
        self.placing_mode = mode
        self.mode_label.config(text={
            None:        "MODE: BROWSE",
            "asset":     "MODE: PLACE ASSET  (click map)",
            "responder": "MODE: PLACE RESPONDER  (click map)",
        }[mode])

    def _set_map_style(self, name):
        url = MAP_STYLES.get(name)
        if url:
            self.map_widget.set_tile_server(url, max_zoom=22)

    def _on_map_click(self, coords):
        if self.placing_mode is None:
            return
        lat, lon = coords
        if self.placing_mode == "asset":
            self._show_asset_dialog(lat, lon)
        elif self.placing_mode == "responder":
            self._show_responder_dialog(lat, lon)

    # -----------------------------------------------------------------------
    # Dialog helpers
    # -----------------------------------------------------------------------
    def _dlg_lbl(self, parent, text):
        tk.Label(parent, text=text, bg=BG_PANEL, fg=FG_DIM,
                 font=("Helvetica", 10)).pack(anchor="w", padx=16, pady=(10, 2))

    def _dlg_entry(self, parent, default=""):
        e = tk.Entry(parent, font=("Helvetica", 12), width=36,
                     bg=BG_INPUT, fg=FG_BRIGHT, insertbackground=FG_BRIGHT,
                     relief="sunken", bd=2)
        e.insert(0, default)
        e.pack(padx=16)
        return e

    def _dlg_combo(self, parent, values, default):
        v = tk.StringVar(value=default)
        ttk.Combobox(parent, textvariable=v, values=values,
                     state="readonly", width=35).pack(padx=16)
        return v

    def _color_picker_row(self, parent, var):
        """Swatch row + AUTO + CUSTOM + live preview. Mutates var in place."""
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(padx=16, anchor="w", pady=2)
        for preset in PIN_PRESETS:
            tk.Button(row, bg=preset, width=2, height=1,
                      relief="raised", bd=2, cursor="hand2",
                      command=lambda c=preset: var.set(c)).pack(side="left", padx=1)
        self._btn(row, "AUTO", lambda: var.set(""),
                  style=BTN_DIM, font_size=9, side="left", padx=4)

        def pick():
            res = colorchooser.askcolor(color=var.get() or "#00ff41",
                                        title="Choose Pin Color", parent=parent)
            if res[1]:
                var.set(res[1])

        self._btn(row, "CUSTOM", pick, style=BTN_STD, font_size=9,
                  side="left", padx=4)
        preview = tk.Label(row, text="  ◆ ", bg=BG_PANEL,
                           fg=var.get() or FG_DIM, font=("Helvetica", 16))
        preview.pack(side="left", padx=6)

        def _upd(*_):
            c = var.get()
            try:
                preview.config(fg=c if c else FG_DIM)
            except tk.TclError:
                pass

        var.trace_add("write", _upd)

    # -----------------------------------------------------------------------
    # Asset dialog
    # -----------------------------------------------------------------------
    def _show_asset_dialog(self, lat, lon, asset_id=None):
        editing  = asset_id is not None
        existing = self.assets.get(asset_id, {})

        dlg = tk.Toplevel(self.root)
        dlg.title("Edit Asset" if editing else "Add Asset")
        dlg.geometry("460x430")
        dlg.grab_set()
        dlg.configure(bg=BG_PANEL)
        dlg.resizable(False, False)

        self._dlg_lbl(dlg, "Asset Name / IP / Hostname:")
        name_f = self._dlg_entry(dlg, existing.get("name", ""))

        self._dlg_lbl(dlg, "Asset Type:")
        type_v = self._dlg_combo(dlg, ASSET_TYPES, existing.get("type", ASSET_TYPES[0]))

        self._dlg_lbl(dlg, "Status:")
        status_v = self._dlg_combo(dlg, list(STATUS_COLORS.keys()),
                                   existing.get("status", "Under Investigation"))

        self._dlg_lbl(dlg, "Notes:")
        notes_f = self._dlg_entry(dlg, existing.get("notes", ""))

        self._dlg_lbl(dlg, "Pin Color:  presets | CUSTOM | AUTO = status color")
        pin_color_var = tk.StringVar(value=existing.get("pin_color", "") or "")
        self._color_picker_row(dlg, pin_color_var)

        tk.Label(dlg, text=f"  {lat:.5f}, {lon:.5f}",
                 bg=BG_PANEL, fg=FG_DIM, font=("Courier", 9)
                 ).pack(anchor="w", padx=16, pady=(8, 0))

        btn_row = tk.Frame(dlg, bg=BG_PANEL)
        btn_row.pack(pady=12)

        def on_save():
            name  = name_f.get().strip() or "UNNAMED"
            color = pin_color_var.get().strip() or None
            if editing:
                self._update_asset(asset_id, name, type_v.get(),
                                   status_v.get(), notes_f.get().strip(), color)
            else:
                self._add_asset(lat, lon, name, type_v.get(),
                                status_v.get(), notes_f.get().strip(), color)
            dlg.destroy()

        def on_delete():
            if messagebox.askyesno("Remove Asset",
                                   f"Remove '{existing.get('name')}'?", parent=dlg):
                self._remove_asset(asset_id)
                dlg.destroy()

        self._btn(btn_row, "Save",   on_save,    style=BTN_SAVE,   width=9, side="left", padx=8)
        self._btn(btn_row, "Cancel", dlg.destroy,style=BTN_DIM,    width=9, side="left", padx=8)
        if editing:
            self._btn(btn_row, "Delete", on_delete, style=BTN_DANGER, width=9, side="left", padx=8)
        name_f.focus_set()

    # -----------------------------------------------------------------------
    # Responder dialog
    # -----------------------------------------------------------------------
    def _show_responder_dialog(self, lat, lon, resp_id=None):
        editing  = resp_id is not None
        existing = self.responders.get(resp_id, {})

        dlg = tk.Toplevel(self.root)
        dlg.title("Edit Responder" if editing else "Add Responder")
        dlg.geometry("460x310")
        dlg.grab_set()
        dlg.configure(bg=BG_PANEL)
        dlg.resizable(False, False)

        self._dlg_lbl(dlg, "Name / Callsign:")
        name_f = self._dlg_entry(dlg, existing.get("name", ""))

        self._dlg_lbl(dlg, "Role:")
        role_v = self._dlg_combo(dlg, list(RESPONDER_COLORS.keys()),
                                 existing.get("role", "IR Analyst"))

        self._dlg_lbl(dlg, "Notes:")
        notes_f = self._dlg_entry(dlg, existing.get("notes", ""))

        tk.Label(dlg, text=f"  {lat:.5f}, {lon:.5f}",
                 bg=BG_PANEL, fg=FG_DIM, font=("Courier", 9)
                 ).pack(anchor="w", padx=16, pady=(10, 0))

        btn_row = tk.Frame(dlg, bg=BG_PANEL)
        btn_row.pack(pady=14)

        def on_save():
            name = name_f.get().strip() or "UNNAMED"
            if editing:
                self._update_responder(resp_id, name, role_v.get(), notes_f.get().strip())
            else:
                self._add_responder(lat, lon, name, role_v.get(), notes_f.get().strip())
            dlg.destroy()

        def on_delete():
            if messagebox.askyesno("Remove Responder",
                                   f"Remove '{existing.get('name')}'?", parent=dlg):
                self._remove_responder(resp_id)
                dlg.destroy()

        self._btn(btn_row, "Save",   on_save,     style=BTN_SAVE,   width=9, side="left", padx=8)
        self._btn(btn_row, "Cancel", dlg.destroy, style=BTN_DIM,    width=9, side="left", padx=8)
        if editing:
            self._btn(btn_row, "Delete", on_delete, style=BTN_DANGER, width=9, side="left", padx=8)
        name_f.focus_set()

    # -----------------------------------------------------------------------
    # Pinned location dialogs
    # -----------------------------------------------------------------------
    def _show_pinned_dialog(self, pid):
        """Edit an individual pinned location: name, status, color, notes."""
        if pid not in self.pinned:
            return
        p = self.pinned[pid]

        dlg = tk.Toplevel(self.root)
        dlg.title("Edit Pinned Location")
        dlg.geometry("460x410")
        dlg.grab_set()
        dlg.configure(bg=BG_PANEL)
        dlg.resizable(False, False)

        self._dlg_lbl(dlg, "Name:")
        name_f = self._dlg_entry(dlg, p.get("name", ""))

        self._dlg_lbl(dlg, "Status:")
        status_v = self._dlg_combo(dlg, list(STATUS_COLORS.keys()),
                                   p.get("status", "Monitored"))

        self._dlg_lbl(dlg, "Pin Color:  presets | CUSTOM | AUTO = status color")
        pin_color_var = tk.StringVar(value=p.get("pin_color", "") or "")
        self._color_picker_row(dlg, pin_color_var)

        self._dlg_lbl(dlg, "Notes:")
        notes_f = self._dlg_entry(dlg, p.get("notes", ""))

        tk.Label(dlg,
                 text=f"  {p['lat']:.5f}, {p['lon']:.5f}  [{p.get('category', '')}]",
                 bg=BG_PANEL, fg=FG_DIM, font=("Courier", 9)
                 ).pack(anchor="w", padx=16, pady=(8, 0))

        btn_row = tk.Frame(dlg, bg=BG_PANEL)
        btn_row.pack(pady=12)

        def on_save():
            name      = name_f.get().strip() or p.get("name", "Unnamed")
            status    = status_v.get()
            pin_color = pin_color_var.get().strip() or None
            notes     = notes_f.get().strip()
            p.update({"name": name, "status": status,
                      "pin_color": pin_color, "notes": notes})
            p["marker"].delete()
            p["marker"] = self._make_pinned_marker(
                pid, p["lat"], p["lon"], name, status, pin_color)
            self._refresh_pinned_list()
            self._update_sitrep()
            self._log(f"[PIN] Updated: {name} -> {status}")
            dlg.destroy()

        def on_delete():
            if messagebox.askyesno("Remove Pin",
                                   f"Remove '{p['name']}'?", parent=dlg):
                p["marker"].delete()
                del self.pinned[pid]
                self._refresh_pinned_list()
                self._update_sitrep()
                self._log(f"[PIN] Removed: {p['name']}")
                dlg.destroy()

        self._btn(btn_row, "Save",   on_save,     style=BTN_SAVE,   width=9, side="left", padx=8)
        self._btn(btn_row, "Cancel", dlg.destroy, style=BTN_DIM,    width=9, side="left", padx=8)
        self._btn(btn_row, "Delete", on_delete,   style=BTN_DANGER, width=9, side="left", padx=8)
        name_f.focus_set()

    def _show_bulk_pin_dialog(self):
        """Choose status + color for bulk pinning. Returns dict or None."""
        count    = len(self.osm_markers)
        category = self.osm_var.get()
        result   = {"confirmed": False}

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Pin {count} Results")
        dlg.geometry("460x270")
        dlg.grab_set()
        dlg.configure(bg=BG_PANEL)
        dlg.resizable(False, False)

        tk.Label(dlg, text=f"Pin  {count}  {category}  locations",
                 bg=BG_PANEL, fg=FG_BRIGHT,
                 font=("Courier", 12, "bold")).pack(pady=(16, 2))

        self._dlg_lbl(dlg, "Status for all:")
        status_v = self._dlg_combo(dlg, list(STATUS_COLORS.keys()), "Monitored")

        self._dlg_lbl(dlg, "Pin color  (optional — blank = use status color):")
        pin_color_var = tk.StringVar(value="")
        self._color_picker_row(dlg, pin_color_var)

        btn_row = tk.Frame(dlg, bg=BG_PANEL)
        btn_row.pack(pady=14)

        def on_confirm():
            result["status"]    = status_v.get()
            result["pin_color"] = pin_color_var.get().strip() or None
            result["confirmed"] = True
            dlg.destroy()

        self._btn(btn_row, f"PIN ALL {count}", on_confirm,
                  style=BTN_SAVE, width=14, side="left", padx=8)
        self._btn(btn_row, "Cancel", dlg.destroy,
                  style=BTN_DIM, width=9, side="left", padx=8)

        dlg.wait_window()
        return result if result["confirmed"] else None

    # -----------------------------------------------------------------------
    # Asset CRUD
    # -----------------------------------------------------------------------
    def _resolve_asset_colors(self, status, pin_color):
        if pin_color:
            return {"circle": pin_color, "outside": darken_hex(pin_color)}
        return STATUS_COLORS[status]

    def _make_asset_marker(self, asset_id, lat, lon, name, status, pin_color=None):
        c = self._resolve_asset_colors(status, pin_color)
        return self.map_widget.set_marker(
            lat, lon, text=name,
            marker_color_circle=c["circle"],
            marker_color_outside=c["outside"],
            command=lambda m, aid=asset_id: self._show_asset_dialog(
                self.assets[aid]["lat"], self.assets[aid]["lon"], aid),
        )

    def _add_asset(self, lat, lon, name, atype, status, notes, pin_color=None):
        aid    = self._new_id()
        marker = self._make_asset_marker(aid, lat, lon, name, status, pin_color)
        self.assets[aid] = dict(name=name, type=atype, status=status, notes=notes,
                                lat=lat, lon=lon, pin_color=pin_color, marker=marker,
                                added=datetime.now().isoformat())
        self._log(f"[ASSET]     + {name} | {atype} | {status}")
        self._update_sitrep()
        self._set_mode(None)

    def _update_asset(self, aid, name, atype, status, notes, pin_color=None):
        a = self.assets[aid]
        a["marker"].delete()
        a["marker"] = self._make_asset_marker(aid, a["lat"], a["lon"], name, status, pin_color)
        a.update(name=name, type=atype, status=status, notes=notes, pin_color=pin_color)
        self._log(f"[ASSET]     ~ {name} -> {status}")
        self._update_sitrep()

    def _remove_asset(self, aid):
        a = self.assets.pop(aid)
        a["marker"].delete()
        self._log(f"[ASSET]     - {a['name']} removed")
        self._update_sitrep()

    # -----------------------------------------------------------------------
    # Responder CRUD
    # -----------------------------------------------------------------------
    def _make_responder_marker(self, resp_id, lat, lon, name, role):
        c = RESPONDER_COLORS[role]
        return self.map_widget.set_marker(
            lat, lon, text=f"[{name}]",
            marker_color_circle=c["circle"],
            marker_color_outside=c["outside"],
            command=lambda m, rid=resp_id: self._show_responder_dialog(
                self.responders[rid]["lat"], self.responders[rid]["lon"], rid),
        )

    def _add_responder(self, lat, lon, name, role, notes):
        rid    = self._new_id()
        marker = self._make_responder_marker(rid, lat, lon, name, role)
        self.responders[rid] = dict(name=name, role=role, notes=notes,
                                    lat=lat, lon=lon, marker=marker,
                                    added=datetime.now().isoformat())
        self._log(f"[RESPONDER] + {name} | {role}")
        self._update_sitrep()
        self._set_mode(None)

    def _update_responder(self, rid, name, role, notes):
        r = self.responders[rid]
        r["marker"].delete()
        r["marker"] = self._make_responder_marker(rid, r["lat"], r["lon"], name, role)
        r.update(name=name, role=role, notes=notes)
        self._log(f"[RESPONDER] ~ {name} -> {role}")
        self._update_sitrep()

    def _remove_responder(self, rid):
        r = self.responders.pop(rid)
        r["marker"].delete()
        self._log(f"[RESPONDER] - {r['name']} removed")
        self._update_sitrep()

    # -----------------------------------------------------------------------
    # OSM search
    # -----------------------------------------------------------------------
    def _find_ir_infra(self):
        self._clear_osm_markers()
        category = self.osm_var.get()
        query_tag = IR_OSM_QUERIES.get(category)
        if not query_tag:
            return
        lat, lon = self.map_widget.get_position()
        s, n, w, e = lat-.05, lat+.05, lon-.05, lon+.05
        q = f"[out:json][timeout:25];\n{query_tag}({s},{w},{n},{e});\nout center;"
        try:
            self._log(f"[OSM] Searching: {category} ...")
            resp = requests.get("https://overpass-api.de/api/interpreter",
                                params={"data": q},
                                headers={"User-Agent": "ircop_v1"}, timeout=30)
            if resp.status_code == 200:
                count = 0
                for el in resp.json().get("elements", []):
                    elat = el.get("lat") or el.get("center", {}).get("lat")
                    elon = el.get("lon") or el.get("center", {}).get("lon")
                    if elat and elon:
                        name = el.get("tags", {}).get("name", "Unnamed")
                        self.osm_markers.append(
                            self.map_widget.set_marker(elat, elon, text=name))
                        count += 1
                self._log(f"[OSM] Found {count} {category} — click PIN ALL RESULTS to keep")
            elif resp.status_code == 429:
                self._log("[OSM] Rate limited — wait 60s and retry.")
            else:
                self._log(f"[OSM] Error {resp.status_code}")
        except requests.exceptions.Timeout:
            self._log("[OSM] Request timed out.")
        except Exception as exc:
            self._log(f"[OSM] Error: {exc}")

    def _clear_osm_markers(self):
        for m in self.osm_markers:
            m.delete()
        self.osm_markers.clear()

    # -----------------------------------------------------------------------
    # Pinning
    # -----------------------------------------------------------------------
    def _make_pinned_marker(self, pid, lat, lon, name, status=None, pin_color=None):
        if pin_color:
            circle  = pin_color
            outside = darken_hex(pin_color)
        elif status and status in STATUS_COLORS:
            circle  = STATUS_COLORS[status]["circle"]
            outside = STATUS_COLORS[status]["outside"]
        else:
            circle  = PINNED_DEFAULT["circle"]
            outside = PINNED_DEFAULT["outside"]
        return self.map_widget.set_marker(
            lat, lon, text=name,
            marker_color_circle=circle,
            marker_color_outside=outside,
            command=lambda m, p=pid: self._show_pinned_dialog(p),
        )

    def _pin_all_osm(self):
        if not self.osm_markers:
            self._log("[PIN] No search results to pin.")
            return
        batch = self._show_bulk_pin_dialog()
        if batch is None:
            return
        category  = self.osm_var.get()
        status    = batch["status"]
        pin_color = batch["pin_color"]
        count     = 0
        for m in self.osm_markers:
            pid  = self._new_id()
            name = m.text or "Unnamed"
            lat, lon = m.position
            m.delete()
            marker = self._make_pinned_marker(pid, lat, lon, name, status, pin_color)
            self.pinned[pid] = dict(name=name, category=category,
                                    lat=lat, lon=lon, status=status,
                                    pin_color=pin_color, notes="",
                                    pinned_at=datetime.now().isoformat(),
                                    marker=marker)
            count += 1
        self.osm_markers.clear()
        self._refresh_pinned_list()
        self._update_sitrep()
        self._log(f"[PIN] Pinned {count} {category} as [{status}]")

    def _clear_pinned(self):
        if not self.pinned:
            return
        if messagebox.askyesno("Clear Pins",
                               f"Remove all {len(self.pinned)} pinned locations?"):
            for p in self.pinned.values():
                p["marker"].delete()
            self.pinned.clear()
            self._refresh_pinned_list()
            self._update_sitrep()
            self._log("[PIN] All pinned locations cleared")

    def _refresh_pinned_list(self):
        self.pinned_list.delete(0, "end")
        for p in self.pinned.values():
            ind = STATUS_SHORT.get(p.get("status"), "----")
            clr = "*" if p.get("pin_color") else " "
            self.pinned_list.insert(
                "end",
                f"[{ind:<4}]{clr} {p['name'][:24]:<24}  {p.get('category','')[:10]}")
        self.pin_count_label.config(text=f"{len(self.pinned)} pinned")

    def _goto_pinned(self, _event):
        sel = self.pinned_list.curselection()
        if not sel:
            return
        pid = list(self.pinned.keys())[sel[0]]
        p   = self.pinned[pid]
        self.map_widget.set_position(p["lat"], p["lon"])
        self.map_widget.set_zoom(16)
        self._log(f"[NAV] -> {p['name']}")

    def _delete_selected_pinned(self, _event):
        sel = self.pinned_list.curselection()
        if not sel:
            return
        pid = list(self.pinned.keys())[sel[0]]
        p   = self.pinned.pop(pid)
        p["marker"].delete()
        self._refresh_pinned_list()
        self._update_sitrep()
        self._log(f"[PIN] Removed: {p['name']}")

    # -----------------------------------------------------------------------
    # Navigation
    # -----------------------------------------------------------------------
    def _search_location(self, *_):
        query = self.location_entry.get().strip()
        if not query:
            return
        try:
            loc = self.geolocator.geocode(query)
            if loc:
                self.map_widget.set_position(loc.latitude, loc.longitude)
                self.map_widget.set_zoom(13)
                self._log(f"[NAV] -> {query} ({loc.latitude:.4f}, {loc.longitude:.4f})")
            else:
                self._log(f"[NAV] Not found: {query}")
        except Exception as exc:
            self._log(f"[NAV] Error: {exc}")

    # -----------------------------------------------------------------------
    # Exercise actions
    # -----------------------------------------------------------------------
    def _clear_all(self):
        if not messagebox.askyesno("Clear All",
                                   "Remove all assets, responders, and pins?"):
            return
        for a in self.assets.values():    a["marker"].delete()
        for r in self.responders.values(): r["marker"].delete()
        for p in self.pinned.values():    p["marker"].delete()
        self.assets.clear()
        self.responders.clear()
        self.pinned.clear()
        self._clear_osm_markers()
        self._refresh_pinned_list()
        self._update_sitrep()
        self._log("[EXERCISE] All markers cleared")

    # -----------------------------------------------------------------------
    # Save / Load
    # -----------------------------------------------------------------------
    def _save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("IRCOP State", "*.json"), ("All Files", "*.*")],
            title="Save COP State")
        if not path:
            return
        ak = ("name", "type", "status", "notes", "lat", "lon", "pin_color", "added")
        rk = ("name", "role", "notes", "lat", "lon", "added")
        pk = ("name", "category", "lat", "lon", "pinned_at", "status", "pin_color", "notes")
        data = {
            "saved_at":   datetime.now().isoformat(),
            "assets":     {str(k): {key: v.get(key) for key in ak} for k, v in self.assets.items()},
            "responders": {str(k): {key: v.get(key) for key in rk} for k, v in self.responders.items()},
            "pinned":     {str(k): {key: v.get(key) for key in pk} for k, v in self.pinned.items()},
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self._log(f"[SAVE] {path}  ({len(self.assets)}A / {len(self.responders)}R / {len(self.pinned)}P)")

    def _load(self):
        path = filedialog.askopenfilename(
            filetypes=[("IRCOP State", "*.json"), ("All Files", "*.*")],
            title="Load COP State")
        if not path:
            return
        for a in self.assets.values():    a["marker"].delete()
        for r in self.responders.values(): r["marker"].delete()
        for p in self.pinned.values():    p["marker"].delete()
        self.assets.clear(); self.responders.clear(); self.pinned.clear()
        self._clear_osm_markers()

        with open(path) as f:
            data = json.load(f)

        for k, a in data.get("assets", {}).items():
            aid    = int(k)
            self._id_counter = max(self._id_counter, aid)
            status = a.get("status", "Under Investigation")
            if status not in STATUS_COLORS:
                status = "Under Investigation"
            pc     = a.get("pin_color")
            marker = self._make_asset_marker(aid, a["lat"], a["lon"], a["name"], status, pc)
            self.assets[aid] = {**a, "status": status, "pin_color": pc, "marker": marker}

        for k, r in data.get("responders", {}).items():
            rid    = int(k)
            self._id_counter = max(self._id_counter, rid)
            role   = r.get("role", "IR Analyst")
            if role not in RESPONDER_COLORS:
                role = "IR Analyst"
            marker = self._make_responder_marker(rid, r["lat"], r["lon"], r["name"], role)
            self.responders[rid] = {**r, "role": role, "marker": marker}

        for k, p in data.get("pinned", {}).items():
            pid    = int(k)
            self._id_counter = max(self._id_counter, pid)
            status = p.get("status")
            pc     = p.get("pin_color")
            marker = self._make_pinned_marker(pid, p["lat"], p["lon"], p["name"], status, pc)
            self.pinned[pid] = {**p, "marker": marker}

        self._refresh_pinned_list()
        self._update_sitrep()
        self._log(f"[LOAD] {path}  ({len(self.assets)}A / {len(self.responders)}R / {len(self.pinned)}P)")

    # -----------------------------------------------------------------------
    # Log
    # -----------------------------------------------------------------------
    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = COPApp(root)
    root.mainloop()
