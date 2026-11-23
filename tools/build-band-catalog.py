#!/usr/bin/env python3
"""Build staged 90 m and 49 m receiver catalogs from the candidate workbooks.

Phase 1 of design/three-band-receiver-plan.md. Reads only the "Core" and
"Band-edge" sheets, applies the recorded data rules, and writes:

  data/bands/band-90m.json
  data/bands/band-49m.json
  data/bands/band-catalog-review.json   (machine-readable review lists)

and installs identical copies of the two catalogs into app/heritage-h60/,
where the receiver's BAND switch loads them (private preview only).
Run from the project root:  python3 tools/build-band-catalog.py
"""
import hashlib, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "bands"
APP = ROOT / "app" / "heritage-h60"

BANDS = {
    "90m": {
        "workbook": "90-m-SWBC-Recordings-1969-1989-Candidates-1.xlsx",
        "sheets": {"Core 3200-3400 kHz": "core", "Band-edge": "edge"},
        "dialMinHz": 3150000, "dialMaxHz": 3500000, "defaultHz": 3300000,
        "label": "90 METERS", "nominal": "3200-3400 kHz",
    },
    "49m": {
        "workbook": "49-m-SWBC-Recordings-1945-2000-Candidates-1.xlsx",
        "sheets": {"Core 5950-6200 kHz": "core", "Band-edge": "edge"},
        "dialMinHz": 5850000, "dialMaxHz": 6350000, "defaultHz": 6100000,
        "label": "49 METERS", "nominal": "5950-6200 kHz",
    },
}
ERA = (1960, 1989)

# Frequencies that need an explicit decision (plan: "Data rules").
FREQUENCY_OVERRIDES = {
    "49M-0319": (6220.0, "Placed at 6220 kHz, the frequency in the on-air ID; QSL gives 6230 kHz."),
}

# Wording in "Possible duplicate of" that marks a true mirror (same recording),
# as opposed to "Possible only" (same station/frequency/year, different source).
MIRROR_WORDS = re.compile(
    r"same (file|recording|length)|same item file|sraa copy|overlaps|excerpt|copy of|mirror",
    re.I)
POSSIBLE_ONLY = re.compile(r"possible only|possibly", re.I)
CONF_RANK = {"High": 0, "Medium": 1, "Low": 2}
CERT_RANK = {"Exact label": 0, "Month only": 1, "Year only": 2, "Circa": 3, "Range": 4}


def parse_khz(raw):
    s = str(raw or "").strip()
    m = re.match(r"^(\d)\.(\d{3})\.(\d+)\s*MHz", s, re.I)        # 3.322.5 MHz
    if m:
        return float(f"{m.group(1)}{m.group(2)}.{m.group(3)}")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*MHz", s, re.I) or re.match(r"^(\d\.\d{2,3})$", s)
    if m:
        return round(float(m.group(1)) * 1000, 3)
    m = re.match(r"^(\d),(\d{3}(?:\.\d+)?)", s)                  # 3,290 khz
    if m:
        return float(m.group(1) + m.group(2))
    m = re.match(r"^(\d{4}(?:\.\d+)?)", s)                       # 3205 / 6248 (mix ...)
    if m:
        return float(m.group(1))
    return None


def seconds(dur):
    m = re.match(r"^(?:(\d+):)?(\d+):(\d{2})$", str(dur or "").strip())
    if not m:
        return 0
    h, mi, se = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
    return h * 3600 + mi * 60 + se


def years(date):
    return [int(y) for y in re.findall(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)", str(date or ""))]


def clean_country(row):
    norm = row.get("Country (normalized, for Summary)")
    if norm:
        return str(norm).strip()
    raw = str(row.get("Country as labeled") or "").strip()
    raw = re.sub(r"\s*\((folder/section|section heading|file-name prefix)\)\s*$", "", raw, flags=re.I)
    if raw.isupper() and len(raw) > 3:
        raw = raw.title().replace("Ssr", "SSR").replace("Usa", "USA")
    return raw


def text(v):
    return None if v is None else str(v).strip()


def load(band, cfg):
    wb = openpyxl.load_workbook(SRC / cfg["workbook"], read_only=True, data_only=True)
    rows = []
    for sheet, scope in cfg["sheets"].items():
        data = list(wb[sheet].iter_rows(values_only=True))
        head = [h for h in data[0]]
        for r in data[1:]:
            if not r or not r[0]:
                continue
            d = {h: v for h, v in zip(head, r) if h}
            d["_scope"] = scope
            rows.append(d)
    return rows


def build(band, cfg):
    rows = load(band, cfg)
    by_id = {r["Candidate ID"]: r for r in rows}
    flags = defaultdict(list)
    recs = []
    for r in rows:
        cid = r["Candidate ID"]
        khz = parse_khz(r["Frequency kHz as labeled"])
        reasons, notes = [], []
        if cid in FREQUENCY_OVERRIDES:
            khz, why = FREQUENCY_OVERRIDES[cid]
            notes.append(why)
            flags["frequency_override"].append(cid)
        if khz is None:
            reasons.append("frequency_review")
        hz = None if khz is None else int(round(khz * 10)) * 100   # snap to the 0.1 kHz dial step
        if khz is not None and abs(hz - khz * 1000) >= 1:
            flags["frequency_snapped"].append(f"{cid}: {r['Frequency kHz as labeled']} -> {hz/1000:.1f}")
        if hz is not None and not (cfg["dialMinHz"] <= hz <= cfg["dialMaxHz"]):
            reasons.append("outside_dial")
        if str(r.get("Recording type") or "").startswith("Compilation"):
            reasons.append("compilation_segment_review")
        ys = years(r.get("Date"))
        if not ys or min(ys) < ERA[0] or max(ys) > ERA[1]:
            reasons.append("outside_era")
        if not str(r.get("Audio link check") or "").startswith("Resolves"):
            flags["audio_link_failed"].append(cid)
        conf = str(r.get("Confidence") or "")
        if conf.startswith("Low"):
            flags["low_confidence"].append(f"{cid}: {conf}")
        num = int(re.search(r"(\d+)$", cid).group(1))
        recs.append({
            "id": f"rec-{band}-{num:04d}",
            "inventoryId": cid,
            "sortKey": num,
            "band": band,
            "frequencyHz": hz,
            "frequencyLabel": text(r["Frequency kHz as labeled"]),
            "station": text(r.get("Station normalized")) or text(r.get("Station as labeled")),
            "stationAsLabeled": text(r.get("Station as labeled")),
            "country": clean_country(r),
            "countryAsLabeled": text(r.get("Country as labeled")),
            "date": text(r.get("Date")),
            "certainty": text(r.get("Date certainty")),
            "time": text(r.get("Time as labeled")),
            "timeBasis": text(r.get("Time basis")),
            "duration": text(r.get("Duration")),
            "audioUrl": text(r.get("Listen/download URL")),
            "sourceUrl": text(r.get("Item/page URL")),
            "collection": text(r.get("Source collection/site")),
            "recordist": text(r.get("Recordist/uploader")),
            "transmitterLocality": text(r.get("Transmitter locality")),
            "recordingType": text(r.get("Recording type")),
            "rights": text(r.get("Rights/license as stated")),
            "confidence": conf or None,
            "scope": r["_scope"],
            "evidence": text(r.get("Notes")),
            "duplicateNote": text(r.get("Possible duplicate of")),
            "notes": " ".join(notes) or None,
            "mapKey": None,
            "publicationReview": "pending",
            "reviewReasons": reasons,
        })

    # Mirror duplicates: cluster rows that name each other as the same recording,
    # among rows not already held, and keep one copy per cluster.
    live = {x["inventoryId"]: x for x in recs if not x["reviewReasons"]}
    parent = {k: k for k in live}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for cid, x in live.items():
        note = x["duplicateNote"] or ""
        if not note or POSSIBLE_ONLY.search(note) or not MIRROR_WORDS.search(note):
            continue
        # Only the first ID is the one the note's wording describes; later IDs
        # are cross-references that may be "possibly the same" recordings.
        refs = re.findall(r"\b\d\dM-\d{4}\b", note)[:1]
        for other in refs:
            if other in live and live[other]["frequencyHz"] == x["frequencyHz"]:
                parent[find(cid)] = find(other)
            elif other in live:
                flags["mirror_frequency_conflict"].append(f"{cid} ~ {other}")
    clusters = defaultdict(list)
    for k in live:
        clusters[find(k)].append(live[k])
    merges = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        def rank(x):
            # Working link first, then the longest copy (an excerpt never
            # replaces the full recording), then the stronger evidence.
            return (0 if not str(by_id[x["inventoryId"]].get("Audio link check") or "").startswith("Fails") else 1,
                    -seconds(x["duration"]),
                    CONF_RANK.get(str(x["confidence"]).split(" ")[0], 3),
                    CERT_RANK.get(x["certainty"], 5),
                    0 if x["timeBasis"] == "UTC/GMT stated" else 1,
                    0 if str(x["audioUrl"]).lower().endswith(".mp3") else 1,
                    x["sortKey"])
        members.sort(key=rank)
        keep, rest = members[0], members[1:]
        for d in rest:
            d["reviewReasons"].append("mirror_duplicate")
            d["notes"] = ((d["notes"] or "") + f" Same recording as {keep['inventoryId']}, which is kept.").strip()
        keep["notes"] = ((keep["notes"] or "") + " Also posted as " + ", ".join(d["inventoryId"] for d in rest) + ".").strip()
        merges.append({"kept": keep["inventoryId"], "held": [d["inventoryId"] for d in rest],
                       "station": keep["station"], "frequencyHz": keep["frequencyHz"]})

    for x in recs:
        x["testEligible"] = not x["reviewReasons"]
        del x["duplicateNote"]
    recs.sort(key=lambda x: x["sortKey"])
    tun = [x for x in recs if x["testEligible"]]
    reason_counts = Counter(r for x in recs for r in x["reviewReasons"])
    digest = hashlib.sha256((SRC / cfg["workbook"]).read_bytes()).hexdigest()
    payload = {
        "schemaVersion": "1.2-band",
        "name": f"Heritage HR-64: {cfg['label'].title()} Staged Catalog",
        "status": "private_preview_receiver_catalog",
        "band": band, "bandLabel": cfg["label"], "nominalBand": cfg["nominal"],
        "era": f"{ERA[0]}-{ERA[1]}",
        "sourceWorkbook": cfg["workbook"], "workbookSha256": digest,
        "order": "fixed_ascending_candidate_number",
        "dialMinHz": cfg["dialMinHz"], "dialMaxHz": cfg["dialMaxHz"], "defaultHz": cfg["defaultHz"],
        "counts": {
            "total": len(recs), "tunable": len(tun), "held": len(recs) - len(tun),
            "core": sum(x["scope"] == "core" for x in recs),
            "edge": sum(x["scope"] == "edge" for x in recs),
            "tunableCore": sum(x["scope"] == "core" for x in tun),
            "tunableEdge": sum(x["scope"] == "edge" for x in tun),
            "frequencies": len({x["frequencyHz"] for x in tun}),
            "byReason": dict(sorted(reason_counts.items())),
        },
        "recordings": recs,
    }
    review = {"merges": merges, "flags": {k: v for k, v in flags.items()}}
    return payload, review


def main():
    out_review = {}
    for band, cfg in BANDS.items():
        payload, review = build(band, cfg)
        text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
        (SRC / f"band-{band}.json").write_text(text)
        (APP / f"band-{band}.json").write_text(text)
        out_review[band] = review
        print(band, json.dumps(payload["counts"]))
    (SRC / "band-catalog-review.json").write_text(json.dumps(out_review, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    sys.exit(main())
