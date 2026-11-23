#!/usr/bin/env python3
"""Build the public-release version of the receiver (owner request, 2026-11-07).

  python3 tools/build-release.py

Reads the private preview in app/heritage-h60 and writes release/heritage-hr64. The preview is not changed.
- Keeps only recordings cleared in data/release/recording-rights-2026-10-20.csv that are hosted on
  Archive.org: Dave J. Valko's (email permission, 2026-11-01) plus items with a license on the item.
  Licensed recordings on other hosts and everything still needing permission are left out.
- Removes the 60 m twenty-record baseline and the TEST CATALOG switch; every band has one catalog.
- Drops review-only entries (holds, compilations, second copies, out-of-era) and their review table.
- Limits playback and the security policy to archive.org.
- Removes credits and map entries for recordings that are not in the release.
"""
import csv, json, re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "app" / "heritage-h60", ROOT / "release" / "heritage-hr64"
RIGHTS = ROOT / "data" / "release" / "recording-rights-2026-10-20.csv"
CLEARED = ("Licensed:", "Permission granted:")

rights = {r["Audio URL"]: r for r in csv.DictReader(open(RIGHTS, encoding="utf-8"))}
def cleared(rec):
    r = rights.get(rec.get("audioUrl"))
    return bool(r) and r["Audio host"] == "Archive.org" and r["Status"].startswith(CLEARED)

if OUT.exists(): shutil.rmtree(OUT)
shutil.copytree(SRC, OUT, ignore=shutil.ignore_patterns("pilot.json", "full-inventory.json", "band-90m.json", "band-49m.json"))

kept_ids, summary = set(), {}
RECORD_FIELDS = ("id", "inventoryId", "sortKey", "frequencyHz", "frequencyLabel", "station", "country", "date", "time",
                 "notes", "sourceUrl", "audioUrl", "additionalReferences")
# Owner decision 2026-11-12: this working note is replaced by the standard "Original archive labels preserved." line
# (the app's default when a record has no note); any archive title note that follows it is kept.
BAND_EDGE_NOTE = "User-authorized band-edge exception, added 2026-10-10. Outside 4750-5060 kHz; excluded from strict core-band count."
band_edge_notes = []
for band, src in (("90m", "band-90m.json"), ("60m", "full-inventory.json"), ("49m", "band-49m.json")):
    data = json.loads((SRC / src).read_text())
    recs = [r for r in data["recordings"] if r.get("testEligible") is not False and cleared(r)]
    # 2026-11-12 review A1 (owner approved Phase 1): publish only the fields the receiver reads. Internal curation
    # fields (publicationReview, rights, evidence, confidence, recordist, collection, ...) stay in the private preview.
    recs = [{k: r[k] for k in RECORD_FIELDS if k in r} for r in recs]
    for r in recs:
        n = r.get("notes") or ""
        if BAND_EDGE_NOTE in n:
            band_edge_notes.append(r["id"])
            n = n.replace(BAND_EDGE_NOTE, "").strip()
            if n: r["notes"] = n
            else: r.pop("notes", None)
    kept_ids |= {r["id"] for r in recs}
    meta = {"band": data.get("band"), "bandLabel": data.get("bandLabel"), "dialMinHz": data.get("dialMinHz"),
            "dialMaxHz": data.get("dialMaxHz"), "defaultHz": data.get("defaultHz")}
    if band == "60m": meta.update(band="60m", bandLabel="60 METERS", dialMinHz=4700000, dialMaxHz=5085000, defaultHz=4900000)
    data = {**meta, "counts": {"total": len(recs), "tunable": len(recs), "frequencies": len({r["frequencyHz"] for r in recs})}, "recordings": recs}
    (OUT / f"band-{band}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    summary[band] = (len(data["recordings"]), len({r["frequencyHz"] for r in recs}))

if len(band_edge_notes) != 7: raise SystemExit(f"expected 7 band-edge working notes, found {len(band_edge_notes)}")
credits = json.loads((OUT / "credits.json").read_text())
CREDIT_FIELDS = ("credit", "via", "license")
credits = {"credits": {k: {f: v[f] for f in CREDIT_FIELDS if f in v} for k, v in credits["credits"].items() if k in kept_ids}}
# Credit spelling corrections (owner-approved). The preview keeps the source wording; only the release changes.
# 2026-11-16: the SRAA post for 49M-0042 spells the contributor "Laskoski" once in its text, but SRAA tags that
# post, and all of his other posts, "Tom Laskowski" (same South Bend, Indiana location and Sony ICF-2001).
CREDIT_CORRECTIONS = {"rec-49m-0042": ("Shared by Tom Laskoski", "Shared by Tom Laskowski")}
for rid, (old, new) in CREDIT_CORRECTIONS.items():
    if rid in credits["credits"]:
        assert credits["credits"][rid]["credit"] == old, f"credit correction for {rid} no longer matches the source"
        credits["credits"][rid]["credit"] = new
(OUT / "credits.json").write_text(json.dumps(credits, ensure_ascii=False, separators=(",", ":")))
geo = json.loads((OUT / "geo" / "reveal-geography.json").read_text())
GEO_FIELDS = ("inventoryId", "kind", "eraLabel", "date", "dateUsed", "dateBasis", "dateLabel", "confidence", "highlight",
              "center", "marker", "shownAs", "transmitterSite")
geo = {"entries": {k: {f: v[f] for f in GEO_FIELDS if f in v} for k, v in geo["entries"].items() if k in kept_ids}}
(OUT / "geo" / "reveal-geography.json").write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")))

def edit(path, pairs):
    s = path.read_text()
    for old, new in pairs:
        n = s.count(old)
        if n != 1: raise SystemExit(f"{path.name}: expected one match, found {n}: {old[:70]}")
        s = s.replace(old, new)
    path.write_text(s)

total = sum(n for n, _ in summary.values())
edit(OUT / "app.js", [
    ("catalogs:{pilot:'./pilot.json', full:'./full-inventory.json'}, defaultMode:'pilot',\n    staticHint:'try 4905.0 kHz in the twenty-record baseline'},",
     "catalogs:{full:'./band-60m.json'}, defaultMode:'full', staticHint:null},"),
    ("mode:'pilot', catalogs:", "mode:'full', catalogs:"),
    ("const APPROVED_AUDIO_HOSTS=['archive.org','www.radioheritage.com','static1.squarespace.com'];", "const APPROVED_AUDIO_HOSTS=['archive.org'];"),
    ("  $('catalog-select').parentElement.hidden=!band.catalogs.pilot;\n", ""),
    ("  $('catalog-select').value=mode;$('catalog-select').disabled=false;\n", ""),
    ("$('intro-description').textContent=mode==='pilot'?'Twenty historical recordings. Tune the band and listen for an identification.':'Full-inventory resilience test. Tune the band and use neutral clip selectors where recordings share a frequency.';",
     "$('intro-description').textContent='Historical recordings at their original frequencies. Tune the band, listen for an identification, then reveal the station.';"),
    ("$('footer-mode').textContent=mode==='pilot'?'Twenty-record pilot':'Full-inventory private test';", "$('footer-mode').textContent=`HERITAGE HR-64 / ${currentBand().collection}`;"),
    ("  const review=data.recordings.filter(r=>r.testEligible===false);\n", "  /* Release build: no review-only entries. */\n  const review=[];\n"),
    ("  $('review-queue').hidden=!review.length;$('review-count').textContent=review.length;$('review-body').replaceChildren();\n", ""),
    ("    $('review-body').append(tr);\n", ""),
    ("`Loading ${mode==='full'?'full inventory':'twenty-record baseline'}…`", "'Loading recordings…'"),
    ("'The baseline catalog could not load. Reload this page to retry.'", "'The recordings could not load. Reload this page to retry.'"),
    ("    $('catalog-select').value=state.mode;\n", ""),
    ("const statusText=(mode,data)=>{const tunable=data.recordings.filter(r=>r.testEligible!==false).length;return mode==='pilot'?'20 recordings · baseline preserved':`${data.recordings.length} inventory entries · ${tunable} tunable · ${data.recordings.length-tunable} awaiting review`;};",
     "const statusText=(mode,data)=>`${data.recordings.length} recordings on ${bandShort(currentBand().id)}`;"),
    ("  $('catalog-select').onchange=e=>switchCatalog(e.target.value);\n", ""),
])
edit(OUT / "index.html", [
    ("Tune a historical shortwave receiver with a twenty-record baseline and a full-inventory test mode. Listen for an identification, then reveal the station.",
     "Tune a historical shortwave receiver across the 90, 60 and 49 meter bands, 1960–1989. Listen for an identification, then reveal the station."),
    ("PILOT NO. 01 <span>/</span> 1960–1989 COLLECTION", "90 · 60 · 49 METERS <span>/</span> 1960–1989 COLLECTION"),
    ("Twenty recordings. Three decades. Tune, listen, identify.", "Historical recordings at their original frequencies. Tune the band, listen for an identification, then reveal the station."),
    ("CURATOR PREVIEW<small>", "ARCHIVE AUDIO<small>"),
    ('aria-label="Receiver test catalog"', 'aria-label="Recordings on this band"'),
    ('<div><label for="catalog-select">TEST CATALOG</label><select id="catalog-select" disabled data-testid="select-catalog"><option value="pilot">Twenty-record baseline</option><option value="full">Full inventory test</option></select></div>\n', ""),
    ("Loading twenty-record baseline…", "Loading recordings…"),
    ('<span id="guide-count">20 recording positions</span>', '<span id="guide-count"></span>'),
    ("HERITAGE HR-64 / TWENTY-RECORD BASELINE", "HERITAGE HR-64"),
    ("On 60 meters, start with the twenty-record baseline or select full inventory; 90 and 49 meters always use their full 1960–1989 catalogs, with compilations, second copies and (on 49 meters) recordings outside 1960–1989 held for review. Shared frequencies",
     f"The receiver holds {total} recordings from 1960-1989: {summary['90m'][0]} on 90 meters, {summary['60m'][0]} on 60 meters and {summary['49m'][0]} on 49 meters. Shared frequencies"),
    ("    <p>Full mode retains all 349 entries, with existing holds, conflicting frequencies and compilation segments in a review-only queue. The twenty-record baseline is unchanged. Short clips are retained pending the owner's individual listening review.</p>\n", ""),
    ("Original audio plays directly from archive hosts. Public-release rights, attribution and host reliability still require review. Source URLs and technical inspection may expose station identity.",
     "Original audio plays directly from the Internet Archive; nothing is copied to this site. Each recording is used with its recordist's permission or under the license shown in its credit. Source URLs and technical inspection may expose station identity."),
    ("media-src https://archive.org https://*.archive.org https://www.radioheritage.com https://static1.squarespace.com;", "media-src https://archive.org https://*.archive.org;"),
])
s = (OUT / "index.html").read_text()
s2 = re.sub(r'\s*<details id="review-queue" hidden>.*?</details>', "", s, count=1, flags=re.S)
assert s2 != s; (OUT / "index.html").write_text(s2)

# Faceplate and ABOUT panel (owner approved the faceplate 2026-11-08 ; ABOUT text from his 2026-11-16 revisions).
OVL = ROOT / "tools" / "release-overlay"
shutil.copy(OVL / "faceplate-grey.css", OUT / "faceplate-grey.css")
strip = lambda t: re.sub(r"<!--.*?-->\n?", "", t, flags=re.S)
s = (OUT / "index.html").read_text()
s, n = re.subn(r'        <div class="brand-name">.*?<span class="model-name">HR-64</span>\n        </div>\n', lambda m: strip((OVL / "nameplate.html").read_text()), s, count=1, flags=re.S)
assert n == 1, "nameplate block not found"
s, n = re.subn(r"<p>Heritage HR-64 is an original GR-64-inspired interface[^<]*</p>",
    "<p>This receiver is an original design. Its grey panel and nameplate recall military and commercial receivers of the 1950s and 1960s; it is not a product of, or endorsed by, any receiver maker. The dial and S-meter are simulated, not measured RF reception.</p>", s, count=1)
assert n == 1, "design paragraph not found"
(OUT / "index.html").write_text(s)
edit(OUT / "index.html", [
    ("<title>Heritage HR-64 | Shortwave Archive Receiver</title>", "<title>Historic Shortwave | Archive Receiver</title>"),
    ('aria-label="Heritage HR-64 historical receiver"', 'aria-label="Historic Shortwave receiver"'),
    ('<span id="footer-mode">HERITAGE HR-64</span>', '<span id="footer-mode">HISTORIC SHORTWAVE</span>'),
    ('  <link rel="stylesheet" href="./style.css">\n', '  <link rel="stylesheet" href="./style.css">\n  <link rel="stylesheet" href="./faceplate-grey.css">\n'),
    ('<button id="about-button" data-testid="nav-about">Field notes</button>',
     '<button id="about-project-button" data-testid="nav-about-project">About</button>\n      <button id="about-button" data-testid="nav-about">Field notes</button>'),
    ('  <dialog id="reset-dialog"', strip((OVL / "about-dialog.html").read_text()) + '  <dialog id="reset-dialog"'),
])
edit(OUT / "app.js", [
    ("`HERITAGE HR-64 / ${currentBand().collection}`", "`HISTORIC SHORTWAVE / ${currentBand().collection}`"),
    ("  $('about-button').onclick=()=>$('about-dialog').showModal();\n",
     "  $('about-button').onclick=()=>$('about-dialog').showModal();\n  $('about-project-button').onclick=()=>$('about-project-dialog').showModal();\n"),
])

# 2026-11-08 revisions: one-line S-meter status, centered Reveal station, intro wording.
STATUS = [("'BUFFERING ARCHIVE AUDIO'", "'BUFFERING'"), ("'LOADING ARCHIVE AUDIO'", "'LOADING'"), ("'OUTSIDE RECEIVER RANGE'", "'OUT OF RANGE'"),
          ("'BETWEEN RECORDINGS'", "'NO SIGNAL'"), ("'RECORDING TUNED'", "'TUNED'"), ("'CATALOG UNAVAILABLE'", "'NO CATALOG'"),
          ("'PLAYBACK UNAVAILABLE'", "'AUDIO ERROR'"), ("'ARCHIVE AUDIO'", "'PLAYING'"), ("'RECORDING ENDED'", "'ENDED'"),
          ("'RECORDING PAUSED'", "'PAUSED'"), ("'RECEIVER STANDBY'", "'STANDBY'")]
a = (OUT / "app.js").read_text()
for old, new in STATUS:
    assert old in a, old
    a = a.replace(old, new)
a = a.replace("listen for an identification, then reveal the station.'", "listen for an identification, then reveal the station to confirm the station ID and its location.'")
(OUT / "app.js").write_text(a)
REVEAL = '<button id="reveal-button" class="reveal-button" data-testid="button-reveal"><i class="reveal-lamp" aria-hidden="true"></i>Reveal station <span aria-hidden="true">↗</span></button>'
edit(OUT / "index.html", [
    ('data-testid="status-receiver" aria-live="polite">RECEIVER STANDBY</span>', 'data-testid="status-receiver" aria-live="polite">STANDBY</span>'),
    (REVEAL + "</div>", "</div>"),
    ('<span id="duration">--:--</span></div>\n', '<span id="duration">--:--</span></div>\n        <div class="reveal-row">' + REVEAL + '</div>\n'),
    ("Tune the band, listen for an identification, then reveal the station.</p>", "Tune the band, listen for an identification, then reveal the station to confirm the station ID and its location.</p>"),
    ("Listen for an identification, then reveal the station.\"", "Listen for an identification, then reveal the station to confirm the station ID and its location.\""),
    ("Loop recording, between Restart and Reveal station, is off by default", "Loop recording, next to Restart, is off by default"),
])
# Remove the four panel screws; the nameplate carries the only screws (2026-11-08).
edit(OUT / "index.html", [('      <i class="screw screw-tl" aria-hidden="true"></i><i class="screw screw-tr" aria-hidden="true"></i><i class="screw screw-bl" aria-hidden="true"></i><i class="screw screw-br" aria-hidden="true"></i>\n', "")])
# 2026-11-12 review fixes, Phase 2 (owner approved; release build only, the preview is unchanged).
edit(OUT / "app.js", [
    # A2: a "stalled" event while audio is still playing from its buffer no longer stops the recording.
    ("  for(const event of ['waiting','stalled'])audio.addEventListener(event,()=>{\n    if(current()&&",
     "  for(const event of ['waiting','stalled'])audio.addEventListener(event,()=>{\n    if(event==='stalled'&&audio.readyState>=3)return; // data is buffered; playback is not interrupted\n    if(current()&&"),
    # A2: if buffering was shown but time is advancing with data available, return to the playing state.
    ("  audio.addEventListener('timeupdate',()=>{if(!current()) return; ",
     "  audio.addEventListener('timeupdate',()=>{if(!current()) return; if(state.mediaState==='buffering'&&!audio.paused&&audio.readyState>=3){clearTimeout(state.loadTimer);mediaStatus('playing','PLAYING');$('play-button').textContent='Pause recording';} "),
    # A4: the listening hint depends on whether the station is revealed, and is restored when playback (re)starts.
    ("  $('listening-description').textContent=r?'Listen for a voice identification and decide for yourself before revealing the station.':'Turn the tuning knob or use the band guide to find an archive recording.';\n",
     "  $('listening-description').textContent=listeningHint(r);\n"),
    ("  if(r) $('listening-description').textContent+=state.loop?' Loop is on: this recording repeats until you turn Loop off.':'';\n", ""),
    ("function renderRecording() {\n",
     "function listeningHint(r) {\n  if(!r) return 'Turn the tuning knob or use the band guide to find an archive recording.';\n"
     "  const base=state.revealed.has(r.id)?'The station is revealed below. Listen again, or tune on to find another recording.':'Listen for a voice identification and decide for yourself before revealing the station.';\n"
     "  return base+(state.loop?' Loop is on: this recording repeats until you turn Loop off.':'');\n}\nfunction renderRecording() {\n"),
    # A4: while a recording loads, the button already pauses it, so it says so; the hint replaces any earlier error or ended text.
    ("  mediaStatus('loading','LOADING');watchLoading(audio);\n",
     "  mediaStatus('loading','LOADING');watchLoading(audio);$('play-button').textContent='Pause recording';$('listening-description').textContent=listeningHint(state.selected);\n"),
    # A5: license links must be ordinary web addresses, like the other reference links; otherwise the label shows as text.
    ("  if(c.license){const a=document.createElement('a');a.href=c.license.url;",
     "  if(c.license){let u=null;try{u=new URL(c.license.url);}catch{}\n    if(!u||!['https:','http:'].includes(u.protocol)){p.append(' · ',c.license.label);return p;}\n    const a=document.createElement('a');a.href=u.href;"),
    # A3: Restart does nothing without a selected recording; Reset always re-renders, clearing any revealed station.
    ("  $('restart-button').onclick=()=>{if(state.audio)", "  $('restart-button').onclick=()=>{if(!state.selected)return;if(state.audio)"),
    ("updatePower();tune(currentBand().defaultHz);$('reset-dialog').close();};", "updatePower();tune(currentBand().defaultHz);renderRecording();renderAlternatives();$('reset-dialog').close();};"),
])
# 2026-11-12 review Phase 3 (owner approved): drop the unused data: image source, and build _headers into the release
# from the overlay template, carrying the page's own policy (one source) plus frame-ancestors 'none'.
# Site text revisions (owner-approved 2026-11-15/16). Avoid confusion with the Shortwave Radio Audio Archive
# (shortwavearchive.com): no "Shortwave Archive" naming. "Archival" wording, AUDIO CLIP and the new footer.
# Date ranges use a hyphen (1960-1989) per the owner. Source names in credits are not changed here.
edit(OUT / "index.html", [
    ('aria-label="Shortwave Archive home"', 'aria-label="Historic Shortwave home"'),
    ('aria-label="Shortwave Archive emblem"', 'aria-label="Historic Shortwave emblem"'),
    ("<span>SHORTWAVE ARCHIVE<small>THE HISTORICAL LISTENING ROOM</small></span>",
     '<span class="site-title">A Simulated Shortwave Receiver presenting Archival Audio Recordings<small>THE HISTORICAL LISTENING ROOM</small></span>'),
    ("<div>ARCHIVE AUDIO<small>Original audio, played from archive hosts.</small></div>", "<div>ARCHIVAL AUDIO</div>"),
    ("90 · 60 · 49 METERS <span>/</span> 1960–1989 COLLECTION", "90 · 60 · 49 METERS <span>/</span> 1960-1989 COLLECTION"),
    ("across the 90, 60 and 49 meter bands, 1960–1989.", "across the 90, 60 and 49 meter bands, 1960-1989."),
    ('<span id="clip-id" data-testid="text-clip">ARCHIVE SIGNAL</span>', '<span id="clip-id" data-testid="text-clip">AUDIO CLIP</span>'),
    ("<p>A curated historical band, not simultaneous reception. Recording times are source labels, not the current clock.</p>",
     "<p>Recording times are drawn from original audio source labels, not the current clock.</p>"),
])
edit(OUT / "app.js", [
    ("audio.setAttribute('aria-label',`Archive clip ${recording.inventoryId}`);", "audio.setAttribute('aria-label',`Audio clip ${recording.inventoryId}`);"),
    ("$('clip-id').textContent=r?`ARCHIVE CLIP ${r.inventoryId}`:'ARCHIVE SIGNAL';", "$('clip-id').textContent=r?`AUDIO CLIP ${r.inventoryId}`:'AUDIO CLIP';"),
    ("title:r?`Archive clip ${r.inventoryId}`:'Shortwave archive'", "title:r?`Audio clip ${r.inventoryId}`:'Historic Shortwave'"),
])
edit(OUT / "index.html", [("img-src 'self' data:;", "img-src 'self';")])
page_csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', (OUT / "index.html").read_text()).group(1)
tmpl = "".join(l for l in (OVL / "_headers.template").read_text().splitlines(True) if not l.startswith("#"))
assert tmpl.count("{CSP}") == 1
(OUT / "_headers").write_text(tmpl.replace("{CSP}", page_csp.rstrip("; ") + "; frame-ancestors 'none'"))
print(f"Release written to {OUT.relative_to(ROOT)}: {total} recordings", summary)
