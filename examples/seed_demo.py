"""Seed a running COPPIR instance with a demo incident scenario.

Builds a fictional incident in Washington DC: a SCADA compromise at a power
substation that cascades through a fiber cut into transit signalling, with the
surrounding assets at varying states of health. Used for the README screenshot,
and handy for poking at the interface without waiting on live Overpass queries.

Asset names and coordinates are real OpenStreetMap data. Everything else --
statuses, dependencies, injects, log entries -- is made up. Statuses are picked
so each sector wheel lands somewhere different, which puts the whole green-to-red
range in one screenshot.

    python run.py                     # one shell
    python examples/seed_demo.py      # another

This clears whatever is currently loaded. The result is saved as a scenario
named "DC Grid Incident Demo".
"""
import os
import sys
import time

import httpx

API = os.environ.get("COPPIR_API", "http://127.0.0.1:8000")

# (name, category, lat, lon, status, op_status)
PINS = [
    # Power — the epicenter of the incident
    ("Rosslyn Substation",            "Power Plants", 38.8968, -77.0719, "Under Investigation", "Critical"),
    ("Pepco Substation 4813",         "Power Plants", 38.9156, -77.0937, "Compromised",         "Critical"),
    ("Clarendon Substation",          "Power Plants", 38.8849, -77.1046, "Under Investigation", "Degraded"),
    ("Ballston Substation",           "Power Plants", 38.8850, -77.0984, "Under Investigation", "Degraded"),
    ("Crystal Substation",            "Power Plants", 38.8578, -77.0566, "Contained",           "Degraded"),
    ("Dominion Energy Control",       "Power Plants", 38.8865, -77.0876, "Monitored",           "Healthy"),
    # Medical
    ("Children's National Hospital",  "Hospitals", 38.9273, -77.0146, "Contained",           "Degraded"),
    ("GW Medical Faculty Associates", "Hospitals", 38.9051, -77.0505, "Under Investigation", "Critical"),
    ("Whitman-Walker Health",         "Hospitals", 38.9105, -77.0317, "Monitored",           "Healthy"),
    ("Kaiser Permanente Capitol Hill","Hospitals", 38.8993, -77.0040, "Clean",               "Healthy"),
    ("Unity Health Care Anacostia",   "Hospitals", 38.8631, -76.9837, "Monitored",           "Degraded"),
    ("MedStar Prompt Care",           "Hospitals", 38.9225, -77.0433, "Clean",               "Healthy"),
    # Government
    ("U.S. Department of State",      "Government Buildings", 38.8964, -77.0461, "Monitored",           "Healthy"),
    ("FBI Washington Field Office",   "Government Buildings", 38.8978, -77.0156, "Clean",               "Healthy"),
    ("U.S. EPA Headquarters",         "Government Buildings", 38.8940, -77.0289, "Monitored",           "Healthy"),
    ("Securities & Exchange Commission","Government Buildings", 38.8975, -77.0042, "Contained",         "Degraded"),
    ("Federal Communications Commission","Government Buildings", 38.9035, -77.0071, "Under Investigation","Degraded"),
    ("Dept. of Health & Human Services","Government Buildings", 38.8868, -77.0166, "Monitored",         "Healthy"),
    ("United States Mint",            "Government Buildings", 38.9003, -77.0237, "Clean",               "Healthy"),
    ("Government Publishing Office",  "Government Buildings", 38.8999, -77.0095, "Monitored",           "Healthy"),
    ("Dept. of Veterans Affairs",     "Government Buildings", 38.9010, -77.0231, "Clean",               "Healthy"),
    ("DC Chief Technology Officer",   "Government Buildings", 38.8795, -77.0030, "Contained",           "Degraded"),
    # Emergency — responders, largely intact
    ("DCFD Engine Co. 16",            "Fire Stations", 38.9033, -77.0300, "Clean",     "Healthy"),
    ("DCFD Engine Co. 3",             "Fire Stations", 38.8958, -77.0109, "Clean",     "Healthy"),
    ("DCFD Engine Co. 9",             "Fire Stations", 38.9173, -77.0375, "Monitored", "Healthy"),
    ("DC Fire & EMS Station 7",       "Fire Stations", 38.8769, -77.0112, "Clean",     "Degraded"),
    ("MPD Headquarters",              "Police Stations", 38.8940, -77.0192, "Clean",     "Healthy"),
    ("MPD First District HQ",         "Police Stations", 38.8769, -77.0128, "Clean",     "Healthy"),
    ("U.S. Park Police HQ",           "Police Stations", 38.8764, -77.0342, "Monitored", "Healthy"),
    ("MPD Fourth District Substation","Police Stations", 38.9327, -77.0257, "Clean",     "Healthy"),
    # Civilian — water
    ("McMillan Water Treatment Plant","Water Systems", 38.9244, -77.0163, "Under Investigation", "Critical"),
    ("DC Water & Sewer Authority",    "Water Systems", 38.9526, -77.0769, "Monitored",           "Healthy"),
    # Civilian — transport
    ("Washington Union Station",      "Transportation Hubs", 38.8984, -77.0059, "Contained",           "Degraded"),
    ("Metro Center Station",          "Transportation Hubs", 38.8983, -77.0286, "Under Investigation", "Degraded"),
    ("L'Enfant Plaza Station",        "Transportation Hubs", 38.8849, -77.0226, "Monitored",           "Healthy"),
    ("Gallery Place Station",         "Transportation Hubs", 38.8988, -77.0219, "Monitored",           "Healthy"),
    ("Reagan National Airport",       "Transportation Hubs", 38.8534, -77.0440, "Clean",               "Healthy"),
    ("Dupont Circle Station",         "Transportation Hubs", 38.9097, -77.0436, "Clean",               "Healthy"),
    # Civilian — telecom
    ("Arlington Wire Center",         "Telecom Infrastructure", 38.8850, -77.0964, "Monitored", "Degraded"),
    ("Verizon Central Office",        "Telecom Infrastructure", 38.9516, -77.0268, "Monitored", "Degraded"),
    ("WUSA-TV / WJLA-TV Tower",       "Telecom Infrastructure", 38.9503, -77.0798, "Clean",     "Healthy"),
    ("Hughes Memorial Tower",         "Telecom Infrastructure", 38.9630, -77.0267, "Monitored", "Healthy"),
    # Civilian — universities
    ("Georgetown University",         "Universities", 38.9089, -77.0742, "Clean",     "Healthy"),
    ("Howard University",             "Universities", 38.9159, -77.0184, "Monitored", "Healthy"),
    ("Gallaudet University",          "Universities", 38.9082, -76.9930, "Clean",     "Healthy"),
    ("Georgetown University Law",     "Universities", 38.8978, -77.0129, "Clean",     "Healthy"),
    ("George Washington University",  "Universities", 38.9021, -77.0510, "Monitored", "Healthy"),
    # Financial
    ("Industrial Bank",               "Banks", 38.8975, -77.0306, "Clean",     "Healthy"),
    ("Charles Schwab DC",             "Banks", 38.8996, -77.0272, "Monitored", "Healthy"),
    ("Bank-Fund Staff FCU",           "Banks", 38.8998, -77.0443, "Clean",     "Healthy"),
    ("Navy Federal Credit Union",     "Banks", 38.8974, -77.0706, "Clean",     "Healthy"),
    ("American Bank",                 "Banks", 38.9028, -77.0311, "Monitored", "Healthy"),
    # Data center — note: belongs to no sector in SECTORS
    ("CoreSite DC1",                  "Data Centers", 38.9029, -77.0291, "Under Investigation", "Critical"),
]

EDGES = [
    ("Rosslyn Substation",             "GW Medical Faculty Associates", "primary feed"),
    ("Rosslyn Substation",             "Arlington Wire Center",         "primary feed"),
    ("Pepco Substation 4813",          "Metro Center Station",          "traction power"),
    ("Arlington Wire Center",          "Metro Center Station",          "SCADA backhaul"),
    ("McMillan Water Treatment Plant", "Children's National Hospital",  "potable supply"),
    ("Clarendon Substation",           "Ballston Substation",           "grid tie"),
    ("CoreSite DC1",                   "Federal Communications Commission", "hosted services"),
    ("Washington Union Station",       "Metro Center Station",          "transfer link"),
]

INJECTS = [
    dict(title="SCADA Compromise — Rosslyn", severity="critical", fire=True,
         description="Unauthorized breaker operation observed at Rosslyn Substation. "
                     "Operator workstation isolated; vendor remote access revoked.",
         target="Rosslyn Substation", target_status="Compromised"),
    dict(title="Fiber Cut — Arlington Wire Center", severity="critical", fire=True,
         description="Redundant fiber pair severed during substation response. "
                     "Metro SCADA backhaul failed over to degraded secondary path.",
         target="Arlington Wire Center", target_status="Compromised"),
    dict(title="Ransom Note — Water Authority", severity="warning", fire=False,
         description="Encrypted note delivered to McMillan plant HMI. No process impact "
                     "confirmed. Awaiting forensic image before status change.",
         target="McMillan Water Treatment Plant", target_status="Compromised"),
    dict(title="Secondary Grid Failure", severity="critical", fire=False,
         description="Contingency: loss of Clarendon tie would island the Ballston load "
                     "pocket and drop three downstream feeders.",
         target="Clarendon Substation", target_status="Compromised"),
    dict(title="Press Inquiry — Regional Outage", severity="info", fire=False,
         description="Regional outlet requesting comment on rolling outages. "
                     "Route to PIO; no operational impact.",
         target=None, target_status=None),
]

LOG = [
    ("Incident declared — regional grid anomaly across NCR", None),
    ("IR team dispatched to Rosslyn Substation", "Rosslyn Substation"),
    ("Mutual aid requested from Dominion Energy Control", "Dominion Energy Control"),
    ("Hospital diversion protocol activated for GW", "GW Medical Faculty Associates"),
    ("Forensic image requested for McMillan plant HMI", "McMillan Water Treatment Plant"),
    ("PIO briefed; holding statement prepared", None),
]

THRESHOLDS = [
    dict(name="Grid Integrity Critical", sector="power",   below_pct=40, severity="critical"),
    dict(name="Medical Capacity Watch",  sector="medical", below_pct=50, severity="warning"),
]

with httpx.Client(timeout=30) as c:
    try:
        c.get(f"{API}/api/pins", timeout=3).raise_for_status()
    except httpx.HTTPError:
        sys.exit(f"No COPPIR instance reachable at {API}. Start one with: python run.py")

    c.post(f"{API}/api/state/clear").raise_for_status()

    ids = {}
    for name, cat, lat, lon, st, op in PINS:
        r = c.post(f"{API}/api/pins", json=dict(name=name, category=cat, lat=lat, lon=lon,
                                                status=st, op_status=op))
        r.raise_for_status()
        ids[name] = r.json()["id"]
    print(f"pins:       {len(ids)}")

    n = 0
    for a, b, label in EDGES:
        r = c.post(f"{API}/api/edges", json=dict(from_pid=ids[a], to_pid=ids[b],
                                                 label=label, edge_type="dependency"))
        r.raise_for_status(); n += 1
    print(f"edges:      {n}")

    fired = queued = 0
    for inj in INJECTS:
        body = dict(title=inj["title"], description=inj["description"], severity=inj["severity"])
        if inj["target"]:
            body["target_pid"] = ids[inj["target"]]
            body["target_status"] = inj["target_status"]
        r = c.post(f"{API}/api/injects", json=body); r.raise_for_status()
        iid = r.json()["id"]
        if inj["fire"]:
            c.post(f"{API}/api/injects/{iid}/trigger").raise_for_status()
            fired += 1; time.sleep(0.2)
        else:
            queued += 1
    print(f"injects:    {fired} fired, {queued} queued")

    for t in THRESHOLDS:
        c.post(f"{API}/api/thresholds", json=t).raise_for_status()
    print(f"thresholds: {len(THRESHOLDS)}")

    for action, asset in LOG:
        body = dict(action=action)
        if asset:
            body["asset_name"] = asset
            body["asset_pid"] = ids[asset]
        c.post(f"{API}/api/log", json=body).raise_for_status()
    print(f"log:        {len(LOG)} manual entries")

    r = c.post(f"{API}/api/scenarios/save", json=dict(name="DC Grid Incident Demo"))
    r.raise_for_status()
    print("scenario:  ", r.json())
