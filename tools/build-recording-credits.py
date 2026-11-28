#!/usr/bin/env python3
"""Build app/heritage-h60/credits.json: one recordist credit per tunable recording on all three bands.

  python3 tools/build-recording-credits.py

Read-only with respect to the catalogs (pilot.json stays frozen; credits are a sidecar keyed by record id).
Inputs:
  app/heritage-h60/full-inventory.json, band-90m.json, band-49m.json
  data/release/archive-org-item-metadata-2026-10-20.json   (Archive.org metadata service, October 20, 2026)
  data/release/sraa-item-descriptions-2026-10-20.json      (descriptions of the Shortwave Radio Audio Archive items)

Wording rules (shown under the revealed station details):
  "Recorded by X"  the source names X as the recordist: the Archive.org creator field of a personal upload,
                   "recorded by X" in the text, or a first-person post whose page author is X.
  "Shared by X"    the source says only that X contributed or shared the recording (SRAA "contributor ... shares").
  other phrasings  group or collection credits are quoted as the source gives them.
  "Recordist not named by the source"  when nothing names one. Names are never guessed.
"""
import json, re, sys, urllib.parse
from pathlib import Path

root = Path(__file__).resolve().parent.parent
app = root / "app/heritage-h60"
meta = json.loads((root / "data/release/archive-org-item-metadata-2026-10-20.json").read_text())
sraa = json.loads((root / "data/release/sraa-item-descriptions-2026-10-20.json").read_text())

LICENSES = {
    "by-nc/3.0": ("CC BY-NC 3.0", "https://creativecommons.org/licenses/by-nc/3.0/"),
    "zero/1.0": ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    "by-nd/4.0": ("CC BY-ND 4.0", "https://creativecommons.org/licenses/by-nd/4.0/"),
    "mark/1.0": ("Public Domain Mark 1.0", "https://creativecommons.org/publicdomain/mark/1.0/"),
}
SRAA_LICENSE = LICENSES["by-nc/3.0"]
OTSW = "On the Shortwaves (Jerry Berg), Radio Heritage Foundation mirror"
HIRAHARA = "From the DX recordings of Tetsuya Hirahara (Radio Nuevo Mundo)"

# Records whose source text needed reading by hand (October 20, 2026). Basis recorded alongside.
OVERRIDES = {
    # Shortwave Radio Audio Archive first-person posts; page author meta tag names the writer.
    (60, "20"): ("Recorded by Dan Robinson", "first-person post; page author Daniel Robinson"),
    (60, "109"): ("Recorded by Dan Robinson", "post says recorded in Washington, DC on an HQ-180A; page author Daniel Robinson"),
    (60, "21"): ("Recorded by Colin Newell", "first-person post; page author Colin Newell"),
    (90, "90M-0050"): ("Recorded by Dan Robinson", "first-person post; page author Daniel Robinson"),
    (90, "90M-0060"): ("Recorded by Colin Newell", "first-person post; page author Colin Newell"),
    (49, "49M-0002"): ("Recorded by Colin Newell", "first-person post; page author Colin Newell"),
    (49, "49M-0319"): ("Recorded by Dan Robinson", "first-person post; page author Daniel Robinson"),
    (49, "49M-0220"): ("Recorded by Al Sizer", "post says the broadcast was recorded by Al Sizer; shared by Dan Robinson"),
    (90, "90M-0051"): ("Recorded by Dan Robinson", "second copy of 90M-0050"),
    (49, "49M-0221"): ("Recorded by Al Sizer", "second copy of 49M-0220"),
    # Shortwave Radio Audio Archive pages (Squarespace audio) for 60 m: page text "Many thanks to SRAA contributor, Dan Greenall".
    (60, "2"): ("Shared by Dan Greenall", "SRAA page credits contributor Dan Greenall"),
    (60, "11"): ("Shared by Dan Greenall", "SRAA page credits contributor Dan Greenall"),
    (60, "12"): ("Shared by Dan Greenall", "SRAA page credits contributor Dan Greenall"),
    (60, "17"): ("Recorded by Dan Greenall", "60 m workbook note: recorded by Dan Greenall"),
    (60, "18"): ("Shared by Dan Greenall", "SRAA page credits contributor Dan Greenall"),
    (60, "19"): ("Shared by Dan Greenall", "SRAA page credits contributor Dan Greenall"),
    (60, "170"): ("Recorded by Dan Greenall", "SRAA page gives his reception location and receiver"),
    (60, "323"): ("Shared by David Goren", "SRAA page: David Goren cassette"),
    # Radio Heritage, On the Shortwaves (60 m rows carry no recordist field; credit from the archive text in notes).
    (60, "168"): ("Recorded by Henrik Klemetz", "archive text: recorded by Henrik Klemetz in Sweden"),
    (60, "267"): ("Recorded by Henrik Klemetz", "archive text: Henrik Klemetz, recorded while in Ecuador"),
    (60, "268"): ("Recorded by Henrik Klemetz", "archive text: submitted by Henrik Klemetz, who recorded it in Ecuador"),
    # Archive.org uploader name "Wireless Static" is Greg Shoom: the SRAA copies of the same recordings
    # ("Many thanks to SRAA contributor, Greg Shoom") and the item text ("Recorded ... Kingston, Ontario") agree.
    (49, "49M-0168"): ("Recorded by Greg Shoom", "SRAA copy credits Greg Shoom; Archive.org uploader name Wireless Static"),
    (49, "49M-0170"): ("Recorded by Greg Shoom", "SRAA copy credits Greg Shoom; Archive.org uploader name Wireless Static"),
    # Uploader-only item, no creator.
    (49, "49M-0074"): ("Recordist not named by the source", "Archive.org item uploaded by La Galena del Sur; no creator"),
}


def clean_catalog_recordist(text):
    """Map the 90 m / 49 m catalog recordist field to display wording, or None to fall through."""
    if not text or text.startswith("Not stated"):
        return None
    t = text.strip()
    if t.startswith("Dave J. Valko"):
        return "Recorded by Dave J. Valko", "Archive.org creator field"
    if "Hirahara" in t:
        return HIRAHARA, "Radio Heritage page: The DX Recordings of Tetsuya Hirahara"
    if t.startswith("Larry Magne"):
        return "Mostly recorded by Larry Magne, per the source", "page: recordings mostly made by Larry Magne"
    if t.startswith("Jerry Berg"):
        return "From Jerry Berg's recordings", "page: a few audio clips from Jerry Berg"
    if t.startswith("Jun Kato"):
        return "Recorded by Jun Kato (NSB \"DX Time\")", "page: recorded in Japan by Jun Kato"
    if t.startswith("Colin Miller"):
        return "Recorded by Colin Miller (VE3CMT)", "Radio Heritage page: The DX Recordings of Colin Miller"
    m = re.match(r"([A-Z][\w.'-]+(?: [A-Z][\w.'-]+)+) \(SRAA contributor\)$", t)
    if m:
        return f"Shared by {m.group(1)}", "SRAA contributor credit"
    if re.match(r"^[A-Z][\w.'-]+(?: [A-Z][\w.'-]+)+$", t):
        return f"Recorded by {t}", "catalog recordist field"
    return None


def credit_for(band, r):
    u = urllib.parse.urlparse(r.get("audioUrl") or "")
    lic, via, basis, line = None, None, None, None
    if "archive.org" in u.netloc:
        item = u.path.split("/")[2]
        x = meta[item]
        lu = x.get("licenseurl") or ""
        for k, v in LICENSES.items():
            if k in lu:
                lic = v
        via = "Shortwave Radio Audio Archive, via Archive.org" if "shortwave-radio-audio-archive" in (x.get("collection") or []) else "Archive.org"
        creator = x.get("creator")
        if creator and creator != "Shortwave Radio Audio Archive":
            line, basis = f"Recorded by {creator}", "Archive.org creator field"
        elif item in sraa:
            d = sraa[item]
            m = re.search(r"contributo\w*,? ([A-Z][\w.]+(?: [A-Z][\w'-]+)+)", d)
            if m:
                line, basis = f"Shared by {m.group(1)}", "SRAA contributor credit"
            elif re.match(r"\s*by ([A-Z][\w.]+(?: [A-Z][\w'-]+)+)", d):
                line, basis = f"Recorded by {re.match(r'\s*by ([A-Z][\w.]+(?: [A-Z][\w-]+)+)', d).group(1)}", "SRAA post byline"
            elif "thanks to hb9gce" in d:
                line, basis = "Shared by HB9GCE", "SRAA credit"
    elif "squarespace" in u.netloc:
        via, lic = "Shortwave Radio Audio Archive", SRAA_LICENSE
    elif "radioheritage" in u.netloc:
        via = OTSW
        if "T_Hirahara" in (r.get("sourceUrl") or "") or "T_Hirahara" in u.path:
            line, basis = HIRAHARA, "Radio Heritage page: The DX Recordings of Tetsuya Hirahara"
        if "Colin_Miller" in (r.get("sourceUrl") or ""):
            line, basis = "Recorded by Colin Miller (VE3CMT)", "Radio Heritage page: The DX Recordings of Colin Miller"
    key = (int(band[:2]), str(r["inventoryId"]))
    if key in OVERRIDES:
        line, basis = OVERRIDES[key]
    if not line:
        cleaned = clean_catalog_recordist(r.get("recordist"))
        if cleaned:
            line, basis = cleaned
    if not line:
        line, basis = "Recordist not named by the source", "no recordist named"
    out = {"credit": line, "via": via, "basis": basis}
    if lic:
        out["license"] = {"label": lic[0], "url": lic[1]}
    return out


credits, counts = {}, {}
for f, band in [("full-inventory.json", "60m"), ("band-90m.json", "90m"), ("band-49m.json", "49m")]:
    for r in json.loads((app / f).read_text())["recordings"]:
        if not (r.get("testEligible", True) and r.get("frequencyHz")):
            continue
        c = credit_for(band, r)
        credits[r["id"]] = c
        counts[c["credit"]] = counts.get(c["credit"], 0) + 1
tunable = len(credits)
# 709 before the 2026-11-27 era extension to 1992 (60 m 323, 90 m 125, 49 m 261); now 384 + 154 + 295.
if tunable != 833:
    sys.exit(f"expected 833 tunable credits, got {tunable}")
# The frozen 60 m baseline can include records held in the full catalog (for example ID 24); credit those too.
pilot = json.loads((app / "pilot.json").read_text())["recordings"]
for r in pilot:
    if r["id"] not in credits:
        c = credit_for("60m", r)
        credits[r["id"]] = c
        counts[c["credit"]] = counts.get(c["credit"], 0) + 1
(app / "credits.json").write_text(json.dumps({
    "schemaVersion": 1, "generatedBy": "tools/build-recording-credits.py", "generated": "2026-10-20",
    "note": "Recordist credits shown after Reveal. Wording rules are in the generator. Not a rights clearance.",
    "credits": credits}, ensure_ascii=False, separators=(",", ":")))
print(json.dumps(dict(sorted(counts.items(), key=lambda kv: -kv[1])), indent=1, ensure_ascii=False))
