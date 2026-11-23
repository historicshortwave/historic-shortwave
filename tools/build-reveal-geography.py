#!/usr/bin/env python3
"""Build the Reveal Station map data (plan phase 5). Data only; nothing in the page reads it yet.

Writes app/heritage-h60/geo/:
  period-borders-1960-1989.json   CShapes 2.0 country polygons valid at any time 1960-1989,
                                  simplified for globe scale, each with exact start/end dates
  reveal-regions.json             Natural Earth 5.1.1 shapes for areas CShapes does not map
                                  (Soviet republics, micro-states, sub-national regions,
                                  approximate breakaway areas)
  reveal-geography.json           one entry per tunable recording on all three bands
  LICENSES.md                     attribution and terms for both datasets
and data/bands/reveal-geography-review.md (rows needing a decision or a source check).

Sources are downloaded once into a cache directory (default ~/.cache/hr64-geo):
  python3 tools/build-reveal-geography.py [--sources DIR]
Requires: pip install shapely pyshp
"""
import datetime as dt, hashlib, json, math, re, sys, urllib.request, zipfile
from collections import Counter, defaultdict
from pathlib import Path
import shapefile
from shapely.geometry import shape, mapping, MultiPolygon, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app" / "heritage-h60"
OUT = APP / "geo"
REVIEW_MD = ROOT / "data" / "bands" / "reveal-geography-review.md"
CATALOGS = [("60m", "full-inventory.json"), ("90m", "band-90m.json"), ("49m", "band-49m.json")]
SOURCES = {
    "cshapes": ("https://icr.ethz.ch/data/cshapes/CShapes-2.0.geojson", "CShapes-2.0.geojson"),
    "ne_units": ("https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_map_units.zip", "ne_10m_admin_0_map_units.zip"),
    "ne_admin1": ("https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip", "ne_10m_admin_1_states_provinces.zip"),
}
ERA = (dt.date(1960, 1, 1), dt.date(1989, 12, 31))
MARKER_KM2 = 3000          # highlights smaller than this also get a ring marker
USSR = 365

D = lambda s: dt.date.fromisoformat(s)

# Recording-era names for states whose name changed inside 1960-1989.
# Each list: (first day the label applies, label). The last entry applies until 1990.
ERA_NAMES = {
    434: [("1960-01-01", "Dahomey"), ("1975-11-30", "Benin")],
    439: [("1960-01-01", "Upper Volta"), ("1984-08-04", "Burkina Faso")],
    80:  [("1960-01-01", "British Honduras"), ("1973-06-01", "Belize (British colony)"), ("1981-09-21", "Belize")],
    490: [("1960-01-01", "Congo (Léopoldville / Kinshasa)"), ("1971-10-27", "Zaire")],
    484: [("1960-01-01", "Congo (Brazzaville)"), ("1970-01-03", "People's Republic of the Congo")],
    482: [("1960-01-01", "Central African Republic"), ("1976-12-04", "Central African Empire"), ("1979-09-21", "Central African Republic")],
    552: [("1960-01-01", "Southern Rhodesia"), ("1965-11-11", "Rhodesia"), ("1979-06-01", "Zimbabwe Rhodesia"), ("1980-04-18", "Zimbabwe")],
    780: [("1960-01-01", "Ceylon"), ("1972-05-22", "Sri Lanka")],
    572: [("1960-01-01", "Swaziland")],
    437: [("1960-01-01", "Ivory Coast (Côte d'Ivoire)")],
    565: [("1960-01-01", "South West Africa (Namibia), under South African administration")],
    522: [("1960-01-01", "French Somaliland"), ("1967-07-05", "French Territory of the Afars and the Issas"), ("1977-06-27", "Djibouti")],
    540: [("1960-01-01", "Angola (Portuguese overseas province)"), ("1975-11-11", "Angola")],
    541: [("1960-01-01", "Mozambique (Portuguese overseas province)"), ("1975-06-25", "Mozambique")],
    404: [("1960-01-01", "Portuguese Guinea"), ("1973-09-24", "Guinea-Bissau")],
    910: [("1960-01-01", "Territory of Papua and New Guinea (Australian administration)"), ("1975-09-16", "Papua New Guinea")],
    940: [("1960-01-01", "British Solomon Islands Protectorate"), ("1978-07-07", "Solomon Islands")],
    115: [("1960-01-01", "Surinam (Kingdom of the Netherlands)"), ("1975-11-25", "Surinam")],
    678: [("1960-01-01", "Yemen Arab Republic (North Yemen)")],
    680: [("1967-11-30", "People's Republic of Southern Yemen"), ("1970-11-30", "People's Democratic Republic of Yemen (South Yemen)")],
    260: [("1960-01-01", "West Germany (Federal Republic of Germany)")],
    # Plain display names where the CShapes name carries a historical alias.
    325: [("1960-01-01", "Italy")], 510: [("1960-01-01", "Tanganyika"), ("1964-04-26", "Tanzania")],
    120: [("1960-01-01", "French Guiana")], 640: [("1960-01-01", "Turkey")], 630: [("1960-01-01", "Iran")],
    360: [("1960-01-01", "Romania")], 775: [("1960-01-01", "Burma")], 811: [("1960-01-01", "Cambodia")],
    365: [("1960-01-01", "USSR")],
    315: [("1960-01-01", "Czechoslovakia")],
    411: [("1960-01-01", "Spanish Guinea"), ("1968-10-12", "Equatorial Guinea")],
    420: [("1960-01-01", "The Gambia")],
    580: [("1960-01-01", "Malagasy Republic"), ("1975-12-30", "Madagascar")],
    713: [("1960-01-01", "Taiwan (Republic of China)")],
    710: [("1960-01-01", "China (People's Republic)")],
}

# Country labels (upper-cased) -> rule. Kinds:
#   country    CShapes polygon for gw on the recording date
#   region     Natural Earth shape(s) inside a CShapes context country (source names the region)
#   republic   Natural Earth successor-state shape clipped to the CShapes USSR polygon
#   territory  Natural Earth shape for an area CShapes does not map at all
#   union      the whole CShapes USSR polygon (republic not established)
#   none       no transmitter country established
C = lambda gw: {"kind": "country", "gw": gw}
RULES = {
    "AFGHANISTAN": C(700), "ALBANIA": C(339), "ANGOLA": C(540), "ARGENTINA": C(160), "AUSTRALIA": C(900),
    "AUSTRIA": C(305), "BENIN": C(434), "BOLIVIA": C(145), "BOTSWANA": C(571), "BRAZIL": C(140),
    "BURKINA FASO": C(439), "BELIZE": C(80), "BURUNDI": C(516), "CAMEROON": C(471), "CENTRAL AFRICAN REP.": C(482),
    "CHAD": C(483), "CHINA, PEOPLE'S REP.": C(710), "COLOMBIA": C(100), "CONGO, DEM. REP.": C(490),
    "CONGO, PEOPLE'S REP.": C(484), "COSTA RICA": C(94), "COTE D'IVOIRE": C(437), "CUBA": C(40), "CANADA": C(20),
    "CHILE": C(155), "COMOROS": C(581), "CZECHOSLOVAKIA": C(315), "DJIBOUTI": C(522), "DOMINICAN REP.": C(42),
    "DOMINICAN REPUBLIC": C(42), "ECUADOR": C(130), "ESWATINI": C(572), "SWAZILAND": C(572), "EQUATORIAL GUINEA": C(411),
    "FRENCH GUIANA": dict(C(120), suffix=" (France)"), "FRENCH POLYNESIA": dict(C(960), suffix=" (France)"),
    "MARTINIQUE": dict(C(66), suffix=" (France)"),
    "GABON": C(481), "GAMBIA": C(420), "GHANA": C(452), "GUATEMALA": C(90), "GUINEA": C(438), "GUINEA-BISSAU": C(404),
    "GUYANA": C(110), "HAITI": C(41), "HONDURAS": C(91), "INDIA": C(750), "INDONESIA": C(850), "ITALY": C(325),
    "JAPAN": C(740), "KENYA": C(501), "LESOTHO": C(570), "LIBERIA": C(450), "LEBANON": C(660), "LIBYA": C(620),
    "LUXEMBOURG": C(212), "MADAGASCAR": C(580), "MALI": C(432), "MAURITANIA": C(435), "MOZAMBIQUE": C(541),
    "MALAWI": C(553), "MALAYSIA": C(820), "MALTA": C(338), "MEXICO": C(70), "NAMIBIA": C(565), "NEPAL": C(790),
    "NIGER": C(436), "NETHERLANDS": C(210), "NICARAGUA": C(93), "NIGERIA": C(475), "PAKISTAN": C(770),
    "PAPUA NEW GUINEA": C(910), "PERU": C(135), "POLAND": C(290), "PORTUGAL": C(235), "RWANDA": C(517),
    "SAUDI ARABIA": C(670), "SENEGAL": C(433), "SOLOMON ISLANDS": C(940), "SOUTH AFRICA": C(560), "SRI LANKA": C(780),
    "SUDAN": C(625), "SURINAM": C(115), "SIERRA LEONE": C(451), "TANZANIA": C(510), "TOGO": C(461),
    "TAIWAN": C(713), "UNITED STATES OF AMERICA": C(2), "USA": C(2), "UNITED KINGDOM": C(200), "URUGUAY": C(165),
    "VENEZUELA": C(101), "YEMEN, REP. - NORTH": C(678), "YEMEN, REP. - SOUTH": C(680), "ZAMBIA": C(551),
    "ZIMBABWE": C(552), "ZIMBABWE (RHODESIA)": C(552), "CZECHOSLOVAKIA": C(315),
    "GERMANY": dict(C(260), basis="inferred", note="Before 1990 'Germany' is read as West Germany; the station is a West German broadcaster."),
    # Soviet republics: modern successor-state shape, clipped to the USSR outline of the date.
    "AZERBAIJAN": {"kind": "republic", "ne": ["unit:AZE"], "label": "Azerbaijan SSR", "shownAs": "present-day Azerbaijan"},
    "GEORGIA": {"kind": "republic", "ne": ["unit:GEG"], "label": "Georgian SSR", "shownAs": "present-day Georgia"},
    "KYRGYZSTAN": {"kind": "republic", "ne": ["unit:KGZ"], "label": "Kirghiz SSR", "shownAs": "present-day Kyrgyzstan"},
    "TAJIKISTAN": {"kind": "republic", "ne": ["unit:TJK"], "label": "Tajik SSR", "shownAs": "present-day Tajikistan"},
    "LATVIAN SSR": {"kind": "republic", "ne": ["unit:LVA"], "label": "Latvian SSR", "shownAs": "present-day Latvia"},
    "RUSSIAN FED. - KARELIA": {"kind": "republic", "ne": ["a1:RUS-2353"], "label": "Karelian ASSR (Russian SFSR)", "shownAs": "present-day Republic of Karelia"},
    "USSR": {"kind": "union", "gw": USSR, "label": "USSR (republic not established)", "basis": "not established",
             "review": "The source names only the USSR. A republic needs period evidence (for example a WRTH transmitter list)."},
    # Regions named by the source inside a period country.
    "AZORES": {"kind": "region", "gw": 235, "ne": ["a1:PRT-735"], "label": "Azores (Portugal)"},
    "ECUADOR - GALAPAGOS": {"kind": "region", "gw": 130, "ne": ["a1:ECU-1270"], "label": "Galápagos Islands (Ecuador)"},
    "EQUATORIAL GUINEA - RIO MUNI": {"kind": "region", "gw": 411, "ne": ["a1:GNQ-1468", "a1:GNQ-1469", "a1:GNQ-1470", "a1:GNQ-1471"],
                                     "label": "Río Muni (Equatorial Guinea)", "shownAs": "present-day mainland provinces"},
    "TANZANIA (ZANZIBAR)": {"kind": "region", "gw": 510, "ne": ["unit:TZZ"], "label": "Zanzibar (Tanzania)"},
    "INDONESIA - IRIAN JAYA": {"kind": "region", "gw": 850, "ne": ["a1:IDN-558", "a1:IDN-1933"], "label": "Irian Jaya (Indonesia)",
                               "eraBefore": ("1973-03-01", "West Irian (Indonesia)"), "shownAs": "present-day Papua and West Papua provinces"},
    "INDONESIA - JAWA": {"kind": "region", "gw": 850, "ne": ["a1:IDN-1226", "a1:IDN-1227", "a1:IDN-1223", "a1:IDN-1224", "a1:IDN-1233", "a1:IDN-540"], "label": "Java (Indonesia)"},
    "INDONESIA - MALUKU": {"kind": "region", "gw": 850, "ne": ["a1:IDN-554", "a1:IDN-538"], "label": "Maluku (Indonesia)"},
    "INDONESIA - SULAWESI": {"kind": "region", "gw": 850, "ne": ["a1:IDN-1237", "a1:IDN-1236", "a1:IDN-557", "a1:IDN-556", "a1:IDN-513", "a1:IDN-1837"], "label": "Sulawesi (Indonesia)"},
    "INDONESIA - SUMATERA": {"kind": "region", "gw": 850, "ne": ["a1:IDN-1136", "a1:IDN-381", "a1:IDN-539", "a1:IDN-492", "a1:IDN-1796", "a1:IDN-1930", "a1:IDN-1230", "a1:IDN-1225", "a1:IDN-1229", "a1:IDN-1231"], "label": "Sumatra (Indonesia)"},
    "PAPUA NEW GUINEA - PAPUA TERR.": {"kind": "region", "gw": 910, "ne": ["a1:PNG-1248", "a1:PNG-1244", "a1:PNG-1249", "a1:PNG-1254", "a1:PNG-1252", "a1:PNG-1256"],
                                       "label": "Papua (Papua New Guinea)", "eraBefore": ("1975-09-16", "Territory of Papua (Australian administration)"),
                                       "shownAs": "present-day southern provinces"},
    "INDONESIA (TIMOR)": {"kind": "region", "gw": 850, "ne": ["unit:TLS"], "label": "East Timor, under Indonesian administration (annexation not recognized by the UN)",
                          "shownAs": "present-day Timor-Leste", "note": "RRI Dili; Dili is in East Timor."},
    "BIAFRA (NIGERIA)": {"kind": "region", "gw": 475, "approximate": True,
                         "ne": ["a1:NGA-2841", "a1:NGA-2842", "a1:NGA-2857", "a1:NGA-2845", "a1:NGA-2847", "a1:NGA-2863", "a1:NGA-2862", "a1:NGA-2843", "a1:NGA-2844"],
                         "label": "Biafra (1967–70), approximate area of the former Eastern Region",
                         "note": "Shown as the 1967 Eastern Region; by 1969 Biafran-held territory was much smaller."},
    "AZAD KASHMIR": {"kind": "region", "gw": 770, "ne": ["a1:PAK-1109"], "label": "Azad Kashmir (Pakistan-administered Kashmir)", "approximate": True},
    # Areas CShapes does not map.
    "ANDORRA": {"kind": "territory", "ne": ["unit:AND"], "label": "Andorra"},
    "VATICAN": {"kind": "territory", "ne": ["unit:VAT"], "label": "Vatican City"},
    "ASCENSION ISLAND (UK)": {"kind": "territory", "ne": ["a1:SHN-Ascension"], "label": "Ascension Island (UK)"},
    "TURKS AND CAICOS ISLANDS": {"kind": "territory", "ne": ["unit:TCA"], "label": "Turks and Caicos Islands (UK)"},
    "MARSHALL ISLANDS": {"kind": "territory", "ne": ["unit:MHL"], "label": "Marshall Islands (in free association with the US from 1986)"},
}
RULES["SUMATRA (INDONESIA)"] = RULES["INDONESIA - SUMATERA"]
NONE_LABELS = {"(INTERNATIONAL WATERS)": "At sea (international waters)", "CLANDESTINE": "Clandestine station",
               "UNIDENTIFIED (LATIN AMERICA)": "Unidentified station", "NOT STATED (NICARAGUA TARGET)": "Transmitter location not stated",
               "NOT STATED (NICARAGUA)": "Transmitter location not stated"}

# Per-recording decisions that differ from the country label alone.
OVERRIDES = {
    "49M-0058": {"kind": "republic", "ne": ["unit:UZB"], "label": "Uzbek SSR", "shownAs": "present-day Uzbekistan",
                 "basis": "transmitter locality stated", "note": "Source gives the transmitter locality as Tashkent."},
    # Owner-identified transmitter sites (October 20, 2026).
    "49M-0042": {"kind": "territory", "ne": ["unit:ACA"], "label": "Antigua (Antigua and Barbuda)", "basis": "owner identified relay site",
                 "note": "BBC World Service via its Antigua relay; the program is British, the transmitter was on Antigua."},
    "49M-0248": {"kind": "territory", "ne": ["a1:NLD-5149"], "label": "Bonaire (Netherlands Antilles, Kingdom of the Netherlands)",
                 "basis": "owner identified relay site",
                 "note": "Radio Netherlands via its Bonaire relay."},
    "49M-0250": {"kind": "territory", "ne": ["a1:NLD-5149"], "label": "Bonaire (Netherlands Antilles, Kingdom of the Netherlands)",
                 "basis": "owner identified relay site",
                 "note": "Radio Netherlands via its Bonaire relay."},
    "49M-0293": {"kind": "country", "gw": 91, "basis": "owner identified site",
                 "note": "Contra station targeting Nicaragua; transmitter in Honduras per the owner."},
}
# Rows where the labeled country may not be the transmitter country (relay use in the period).
RELAY_CHECK = {
    "49M-0042": "BBC World Service on 5975 kHz could have come from a UK site or an overseas relay.",
    "49M-0024": "Radio Canada International: Sackville, Canada, or a European relay.",
    "49M-0027": "Radio Canada International: Sackville, Canada, or a European relay.",
    "49M-0248": "Radio Netherlands: Dutch transmitters or the Bonaire/Madagascar relays.",
    "49M-0250": "Radio Netherlands: Dutch transmitters or the Bonaire/Madagascar relays.",
    "49M-0293": "Source notes the transmitter 'may have been in Honduras'; no highlight until confirmed.",
}

# Owner decisions on flagged rows (October 20, 2026). An approved row keeps its mapping,
# drops its review flags and records the decision; these are band catalog ids, not changes to the catalogs.
APPROVED = {
    "49M-0108": {"decision": "West Germany confirmed by the owner."},
    "49M-0158": {"decision": "West Germany confirmed by the owner."},
    "49M-0220": {"decision": "Owner accepts the 1967 Eastern Region as the approximate Biafra area."},
    "49M-0338": {"decision": "Owner accepts the approximate Azad Kashmir area."},
    "49M-0024": {"decision": "Owner: transmitter at Sackville, New Brunswick.", "transmitterSite": "Sackville, New Brunswick, Canada"},
    "49M-0027": {"decision": "Owner: transmitter at Sackville, New Brunswick.", "transmitterSite": "Sackville, New Brunswick, Canada"},
    "49M-0042": {"decision": "Owner: BBC Antigua relay.", "transmitterSite": "Antigua (BBC Caribbean relay)"},
    "49M-0248": {"decision": "Owner: Radio Netherlands Bonaire relay.", "transmitterSite": "Bonaire relay"},
    "49M-0250": {"decision": "Owner: Radio Netherlands Bonaire relay.", "transmitterSite": "Bonaire relay"},
    "49M-0293": {"decision": "Owner: transmitter in Honduras.", "transmitterSite": "Honduras"},
    "49M-0072": {"decision": "Owner: Moscow or the whole USSR; the site is not confirmed, so the whole USSR is shown.",
                 "transmitterSite": "possibly the Moscow area (not confirmed)"},
    10: {"decision": "Owner: list timing as unknown, 1970s; show independent Angola; credit Dan Robinson as recordist.",
         "dateLabel": "1970s, timing unknown", "dateUsed": "1978-07-01", "dateBasis": "owner decision (post-independence Angola)",
         "recordist": "Dan Robinson"},
}


def fetch(cache, key):
    url, name = SOURCES[key]
    path = cache / name
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        print("downloading", url)
        urllib.request.urlretrieve(url, path)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def km2(geom):
    total = 0.0
    for poly in getattr(geom, "geoms", [geom]):
        if poly.is_empty: continue
        total += poly.area * math.cos(math.radians(poly.centroid.y)) * 12364.0
    return total


def clean(geom, tol, digits, keep_km2=None):
    """Simplify for globe scale; drop slivers from large shapes; never drop a shape entirely."""
    geom = make_valid(geom)
    polys = [g for g in getattr(geom, "geoms", [geom]) if isinstance(g, Polygon) and not g.is_empty]
    for g in getattr(geom, "geoms", []):
        if isinstance(g, MultiPolygon): polys += list(g.geoms)
    total = sum(km2(p) for p in polys)
    out = []
    for p in polys:
        if keep_km2 and total > 50000 and km2(p) < keep_km2: continue
        s = p.simplify(tol, preserve_topology=True) if km2(p) > 200 else p
        out.append(s if not s.is_empty else p)
    if not out: out = polys
    # d3-geo reads rings on the sphere: exterior rings must run clockwise, holes counter-clockwise.
    out = [orient(p, sign=-1.0) for p in out]
    g = MultiPolygon(out) if len(out) > 1 else out[0]
    def rnd(c): return [round(c[0], digits), round(c[1], digits)]
    m = mapping(g)
    def walk(x):
        if isinstance(x[0], (int, float)): return rnd(x)
        return [walk(y) for y in x]
    m = {"type": m["type"], "coordinates": walk(m["coordinates"])}
    return m


def parse_date(text):
    """Return (start, end, point, basis) for the free-text date forms used in the catalogs."""
    s = str(text or "")
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})/(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        a, b = D(f"{m[1]}-{m[2]}-{m[3]}"), D(f"{m[4]}-{m[5]}-{m[6]}")
        return a, b, a + (b - a) / 2, "range"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        d = D(m[0]); return d, d, d, "exact"
    m = re.match(r"^(\d{4})-(\d{2})", s)
    if m:
        a = dt.date(int(m[1]), int(m[2]), 1)
        b = (a.replace(day=28) + dt.timedelta(days=4)); b = b - dt.timedelta(days=b.day)
        return a, b, a + (b - a) / 2, "month"
    w = re.search(r"WRTH (19\d\d) era", s)
    m = re.search(r"(\d{4})s", s)
    if m and w:
        a, b = dt.date(int(m[1]), 1, 1), dt.date(int(m[1]) + 9, 12, 31)
        return a, b, dt.date(int(w[1]), 7, 1), "decade (WRTH edition year used)"
    if m:
        a, b = dt.date(int(m[1]), 1, 1), dt.date(int(m[1]) + 9, 12, 31)
        return a, b, a + (b - a) / 2, "decade"
    ys = [int(y) for y in re.findall(r"(?<!\d)(19\d\d)(?!\d)", s)]
    if len(ys) >= 2:
        a, b = dt.date(min(ys), 1, 1), dt.date(max(ys), 12, 31)
        return a, b, a + (b - a) / 2, "range"
    if ys:
        a, b = dt.date(ys[0], 1, 1), dt.date(ys[0], 12, 31)
        return a, b, dt.date(ys[0], 7, 1), "year"
    return None, None, None, "none"


def era_name(gw, day, fallback):
    names = ERA_NAMES.get(gw)
    if not names: return fallback
    label = names[0][1]
    for start, text in names:
        if day >= D(start): label = text
    return label


def main():
    args = sys.argv[1:]
    cache = Path(args[args.index("--sources") + 1]) if "--sources" in args else Path.home() / ".cache" / "hr64-geo"
    cs_path, mu_zip, a1_zip = fetch(cache, "cshapes"), fetch(cache, "ne_units"), fetch(cache, "ne_admin1")
    for z in (mu_zip, a1_zip):
        target = cache / z.stem
        if not target.exists(): zipfile.ZipFile(z).extractall(target)

    # --- CShapes: every polygon valid at some point in 1960-1989 ---
    period = []
    for f in json.loads(cs_path.read_text())["features"]:
        p = f["properties"]
        start = dt.date(p["gwsyear"], p["gwsmonth"], p["gwsday"])
        end = dt.date(p["gweyear"], p["gwemonth"], p["gweday"])
        if end < ERA[0] or start > ERA[1]: continue
        g = make_valid(shape(f["geometry"]))
        period.append({"id": f"cs:{p['gwcode']}:{start.isoformat()}", "gw": p["gwcode"], "name": p["cntry_name"],
                       "start": start.isoformat(), "end": end.isoformat(), "_geom": g})
    by_gw = defaultdict(list)
    for x in period: by_gw[x["gw"]].append(x)

    def polygon_on(gw, day):
        for x in by_gw.get(gw, []):
            if D(x["start"]) <= day <= D(x["end"]): return x
        return None

    # --- Natural Earth fallback shapes ---
    def records(shp):
        r = shapefile.Reader(str(shp)); names = [x[0] for x in r.fields[1:]]
        for sr in r.iterShapeRecords():
            yield dict(zip(names, sr.record)), shape(sr.shape.__geo_interface__)
    ne = {}
    for rec, g in records(cache / mu_zip.stem / "ne_10m_admin_0_map_units.shp"):
        ne[f"unit:{rec['GU_A3']}"] = (rec["NAME"], g)
    for rec, g in records(cache / a1_zip.stem / "ne_10m_admin_1_states_provinces.shp"):
        ne[f"a1:{rec['adm1_code']}"] = (rec["name"], g)
        if rec["adm0_a3"] == "SHN": ne[f"a1:SHN-{rec['name']}"] = (rec["name"], g)

    # --- Entries for every tunable recording ---
    entries, review, decided, regions_needed = {}, [], [], {}
    counts = Counter()
    for band, file in CATALOGS:
        for r in json.loads((APP / file).read_text())["recordings"]:
            if not r.get("testEligible"): continue
            label = str(r["country"]).strip(); key = label.upper()
            start, end, day, date_basis = parse_date(r.get("date"))
            pre = APPROVED.get(r["inventoryId"]) if band == "60m" else APPROVED.get(str(r["inventoryId"]))
            if pre and pre.get("dateUsed"): day = D(pre["dateUsed"])  # owner-chosen date drives the border lookup
            rule = dict(OVERRIDES.get(r["inventoryId"]) or RULES.get(key) or {})
            e = {"band": band, "inventoryId": r["inventoryId"], "countryLabel": label,
                 "date": r.get("date"), "dateUsed": day.isoformat() if day else None, "dateBasis": date_basis}
            flags = []
            if key in NONE_LABELS and not rule:
                e.update(kind="none", eraLabel=NONE_LABELS[key], highlight=None, basis="not established", confidence="none")
            elif not rule:
                raise SystemExit(f"No map rule for country label {label!r} ({r['inventoryId']})")
            else:
                kind = rule["kind"]; e["kind"] = kind
                e["basis"] = rule.get("basis", "country as labeled in source")
                e["confidence"] = "approximate" if rule.get("approximate") else ("medium" if e["basis"] in ("inferred",) else "high")
                if kind == "union": e["confidence"] = "low"
                gw = rule.get("gw", USSR if kind == "republic" else None)
                ctx = polygon_on(gw, day) if gw else None
                if gw and not ctx: raise SystemExit(f"No CShapes polygon for gw {gw} on {day} ({r['inventoryId']})")
                e["context"] = ctx["id"] if ctx else None
                if kind in ("country", "union"):
                    e["highlight"] = {"source": "cshapes", "ids": [ctx["id"]]}
                    e["eraLabel"] = rule.get("label") or era_name(gw, day, ctx["name"]) + rule.get("suffix", "")
                else:
                    region_id = "ne:" + "+".join(rule["ne"]) + (f"@{ctx['id']}" if kind == "republic" else "")
                    regions_needed[region_id] = (rule["ne"], ctx if kind == "republic" else None)
                    e["highlight"] = {"source": "natural-earth", "ids": [region_id]}
                    lab = rule["label"]
                    if rule.get("eraBefore") and day < D(rule["eraBefore"][0]): lab = rule["eraBefore"][1]
                    e["eraLabel"] = lab
                if rule.get("shownAs"): e["shownAs"] = rule["shownAs"]
                # border change inside an uncertain date range
                if gw and start and end and start != end and not (pre and pre.get("dateUsed")):
                    a, b = polygon_on(gw, max(start, ERA[0])), polygon_on(gw, min(end, ERA[1]))
                    if a and b and a["id"] != b["id"]:
                        flags.append(f"CShapes changes its {ctx['name']} entry (border or status) within the recording's date range ({r.get('date')}); shown as on {day.isoformat()}.")
                if rule.get("review"): flags.append(rule["review"])
            if rule.get("note"): e["note"] = rule["note"]
            if r["inventoryId"] in RELAY_CHECK:
                flags.append("Relay check: " + RELAY_CHECK[r["inventoryId"]])
                if e.get("confidence") == "high": e["confidence"] = "medium"
            if e["basis"] == "inferred": flags.append(rule.get("note", "Country inferred."))
            if e["kind"] in ("region", "republic", "territory") and rule.get("approximate"): flags.append("Approximate area; caption says so.")
            ok = APPROVED.get(r["inventoryId"]) if band == "60m" else APPROVED.get(str(r["inventoryId"]))
            if ok:
                e["decision"] = ok["decision"]; e["decided"] = "2026-10-20"
                for k in ("dateLabel", "dateUsed", "dateBasis", "recordist", "transmitterSite"):
                    if k in ok: e[k] = ok[k]
                if e.get("confidence") == "medium":
                    e["confidence"] = "high"
                    if e["basis"] == "inferred": e["basis"] = "owner confirmed"
                    elif ok.get("transmitterSite") and e["basis"] == "country as labeled in source": e["basis"] = "owner confirmed site"
                decided.append((band, r, e)); flags = []
            e["review"] = flags
            if flags: review.append((band, r, e))
            entries[r["id"]] = e
            counts[e["kind"]] += 1

    # --- Build fallback region shapes ---
    regions = {}
    for rid, (parts, clip) in regions_needed.items():
        missing = [p for p in parts if p not in ne]
        if missing: raise SystemExit(f"Natural Earth feature(s) not found: {missing}")
        g = unary_union([make_valid(ne[p][1]) for p in parts])
        if clip is not None:
            clipped = g.intersection(clip["_geom"])
            if km2(clipped) > 0.8 * km2(g): g = clipped
        regions[rid] = {"id": rid, "parts": parts, "names": [ne[p][0] for p in parts], "_geom": g}

    # Area, center and marker flags; then serialise.
    def finish(item, tol, digits):
        g = item.pop("_geom")
        a = km2(g); item["areaKm2"] = round(a)
        c = g.representative_point() if a < 20000 else g.centroid
        item["center"] = [round(c.x, 2), round(c.y, 2)]
        item["marker"] = a < MARKER_KM2
        small = a < 2000
        item["geometry"] = clean(g, 0 if small else tol, 4 if small else digits, keep_km2=400)
        return item
    period_out = [finish(x, 0.06, 2) for x in period]
    region_out = {k: finish(v, 0.02, 3) for k, v in regions.items()}
    for e in entries.values():
        h = e.get("highlight")
        if not h: e["marker"] = False; continue
        src = {x["id"]: x for x in period_out} if h["source"] == "cshapes" else region_out
        e["marker"] = any(src[i]["marker"] for i in h["ids"])
        e["center"] = src[h["ids"][0]]["center"]

    OUT.mkdir(parents=True, exist_ok=True)
    meta = lambda name: {"generatedBy": "tools/build-reveal-geography.py", "generated": dt.date.today().isoformat(), "name": name}
    (OUT / "period-borders-1960-1989.json").write_text(json.dumps({
        **meta("Period country borders 1960-1989 (simplified)"),
        "source": "CShapes 2.0, ETH Zurich ICR", "sourceUrl": SOURCES["cshapes"][0], "sourceSha256": sha(cs_path),
        "license": "CC BY-NC-SA 4.0", "licenseUrl": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        "attribution": "Borders: CShapes 2.0 (Schvitz et al. 2022), CC BY-NC-SA 4.0", "modified": "Filtered to 1960-1989, simplified, coordinates rounded, ring direction re-ordered",
        "simplification": "Douglas-Peucker 0.06 degrees for shapes over 200 km2, coordinates rounded to 0.01 degrees; islands under 400 km2 dropped from countries over 50,000 km2",
        "features": period_out}, ensure_ascii=False, separators=(",", ":")))
    (OUT / "reveal-regions.json").write_text(json.dumps({
        **meta("Fallback highlight shapes for areas CShapes does not map"),
        "source": "Natural Earth 5.1.1 (admin-0 map units, admin-1 states and provinces)",
        "sourceUrls": [SOURCES["ne_units"][0], SOURCES["ne_admin1"][0]],
        "sourceSha256": {"ne_units": sha(mu_zip), "ne_admin1": sha(a1_zip)},
        "license": "Public domain", "attribution": "Made with Natural Earth",
        "note": "Soviet-republic shapes are present-day successor states clipped to the CShapes USSR outline of the date.",
        "regions": region_out}, ensure_ascii=False, separators=(",", ":")))
    (OUT / "reveal-geography.json").write_text(json.dumps({
        **meta("Reveal Station map entry for every tunable recording"),
        "keyedBy": "recording id (rec-...) across full-inventory.json, band-90m.json and band-49m.json",
        "counts": dict(sorted(counts.items())), "needsReview": len(review), "decided": len(decided),
        "entries": entries}, ensure_ascii=False, separators=(",", ":")))
    (OUT / "LICENSES.md").write_text("""# Map data licenses

- `period-borders-1960-1989.json` is derived from **CShapes 2.0** (International Conflict Research, ETH Zurich): <https://icr.ethz.ch/data/cshapes/>.
  It is licensed **CC BY-NC-SA 4.0**: attribution required, no commercial use, and derived files must carry the same license.
  License statement from the CShapes page: "CShapes by Schvitz, Rüegger, Girardin, Cederman, Weidmann, Gleditsch is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License." License text: <https://creativecommons.org/licenses/by-nc-sa/4.0/>.
  Cite: Schvitz, Guy, Seraina Rüegger, Luc Girardin, Lars-Erik Cederman, Nils Weidmann, and Kristian Skrede Gleditsch. 2022. "Mapping The International System, 1886-2017: The CShapes 2.0 Dataset." Journal of Conflict Resolution 66(1): 144–61.
  Modified: this file keeps only shapes valid in 1960–1989, simplifies them for globe-scale display, rounds coordinates and re-orders ring direction for d3-geo. It is licensed CC BY-NC-SA 4.0, the same as the source.
  The map card shows "Borders: CShapes 2.0 (Schvitz et al.), simplified, CC BY-NC-SA 4.0 · Map credits", with "CShapes 2.0" linked to the CShapes page and the license name linked to the license. "Map credits" opens Field notes at the full citation and the list of changes.
- `reveal-regions.json` is derived from **Natural Earth** 5.1.1 (<https://www.naturalearthdata.com/>), which is in the public domain. Credit: "Made with Natural Earth".
- Both are simplified for globe-scale display and are not suitable for measurement.
""")

    # --- Review report ---
    lines = ["# HR-64: Reveal Map Geography — Review List", "",
             f"Built {dt.date.today().isoformat()} by `tools/build-reveal-geography.py`. {len(entries)} tunable recordings across three bands; "
             f"{len(review)} need a decision or a source check. Everything else maps directly from the country as labeled.", "",
             "| Kind | Recordings |", "|---|---:|"]
    names = {"country": "Period country (CShapes)", "region": "Region named by the source (Natural Earth inside a period country)",
             "republic": "Soviet republic or ASSR (Natural Earth, clipped to the USSR)", "territory": "Area CShapes does not map (Natural Earth)",
             "union": "Whole USSR, republic not established", "none": "No transmitter country established"}
    for k in ["country", "region", "republic", "territory", "union", "none"]:
        lines.append(f"| {names[k]} | {counts.get(k, 0)} |")
    lines += ["", "## Rows needing a decision or source check", "", "| Band | Clip | Station | Country as labeled | Map shows | Why |", "|---|---|---|---|---|---|"]
    for band, r, e in sorted(review, key=lambda x: (x[0], str(x[1]['inventoryId']))):
        lines.append(f"| {band.replace('m', ' m')} | {r['inventoryId']} | {r['station'][:60]} | {r['country']} | {e['eraLabel']} | {' '.join(e['review'])} |")
    lines += ["", f"## Decided by the owner ({len(decided)})", "", "| Band | Clip | Station | Map shows | Decision |", "|---|---|---|---|---|"]
    for band, r, e in sorted(decided, key=lambda x: (x[0], str(x[1]['inventoryId']))):
        lines.append(f"| {band.replace('m', ' m')} | {r['inventoryId']} | {r['station'][:60]} | {e['eraLabel']} | {e['decision']} |")
    nohl = [(b, r, e) for b, r, e in [(e['band'], None, e) for e in entries.values()] if e["kind"] == "none"]
    lines += ["", f"## No highlight ({len(nohl)})", "",
              "These show the caption only: " + ", ".join(sorted(f"{e['inventoryId']} ({e['eraLabel'].lower()})" for _, _, e in nohl)) + ".", ""]
    REVIEW_MD.write_text("\n".join(lines) + "\n")
    sizes = {p.name: p.stat().st_size for p in OUT.iterdir()}
    print(json.dumps({"entries": len(entries), "counts": counts, "review": len(review), "periodPolygons": len(period_out),
                      "regions": len(region_out), "bytes": sizes}, default=str))


if __name__ == "__main__":
    main()
