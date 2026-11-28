#!/usr/bin/env python3
"""Build the new-face release (Phase 5c, owner approval 2026-11-16).

  python3 tools/build-release.py   # grey release first (unchanged; stays the fallback)
  python3 tools/build-face.py

Reads release/heritage-hr64 (the grey release) and tools/face-overlay, writes release/heritage-hr64-face.
The grey release, the frozen 60 m preview and the Cloudflare upload folder are not changed.
- Same recordings, catalogs, credits, maps, seasonal noise, security headers and receiver logic as the grey release.
- New page shell and 3D face (face.css, site.css, face-release.css, face.js, textures, Barlow Semi Condensed).
- app.js keeps every control id, keyboard step, screen-reader value and the capture-window rule; the edits below
  only hand drawing and MAIN TUNING's pointer feel to face.js and change visible kHz labels to KC.
"""
import re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT, OV = ROOT / "release" / "heritage-hr64", ROOT / "release" / "heritage-hr64-face", ROOT / "tools" / "face-overlay"

def one(text, old, new, what):
    n = text.count(old)
    assert n == 1, f"{what}: expected one match, found {n}"
    return text.replace(old, new)

def grab(text, pattern, what):
    m = re.findall(pattern, text, re.S)
    assert len(m) == 1, f"{what}: expected one match, found {len(m)}"
    return m[0]

if OUT.exists(): shutil.rmtree(OUT)
shutil.copytree(SRC, OUT, ignore=shutil.ignore_patterns("style.css", "faceplate-grey.css"))
for name in ("face.css", "site.css", "face-release.css", "face.js"): shutil.copy(OV / name, OUT / name)
shutil.copytree(OV / "textures", OUT / "textures")
for f in (OV / "fonts").iterdir(): shutil.copy(f, OUT / "vendor" / "fonts" / f.name)

# ---------- page ----------
src = (SRC / "index.html").read_text(encoding="utf-8")
header = grab(src, r'(  <header class="site-header">.*?</header>)', "header")
header = re.sub(r'\s*<nav aria-label="Main navigation">.*?</nav>', '', header, flags=re.S)   # About/Field notes move under the scene
intro = grab(src, r'<section class="intro">\s*<div>(<p class="eyebrow">.*?<p id="intro-description">.*?</p>)</div>', "intro")
research = grab(src, r'(<div class="research-desk">.*?</div></div>)', "research desk")
footer = grab(src, r'<footer><p>(.*?)</p>', "footer text")
dialogs = grab(src, r'(  <dialog id="about-dialog".*</dialog>)\s*</body>', "dialogs")
fills = {
    "CSP": grab(src, r'(<meta http-equiv="Content-Security-Policy"[^>]*>)', "CSP"),
    "DESCRIPTION": grab(src, r'(<meta name="description"[^>]*>)', "description"),
    "TITLE": grab(src, r'(<title>.*?</title>)', "title"),
    "HEADER": header, "INTRO": intro, "RESEARCH": research, "FOOTER_TEXT": footer,
}

# Field notes: Bill Martin's revision of 2026-11-19 (with approved fixes 1-4) replaces the grey face's text, including the
# earlier per-sentence edits for this face (decisions 1, 3, 5, 6, 10, the Barlow type credit and the iPhone volume line).
notes = (OV / "field-notes.html").read_text(encoding="utf-8")
notes = notes[notes.index("  <dialog"):].rstrip("\n")
old_notes = grab(dialogs, r'(  <dialog id="about-dialog".*?</dialog>)', "grey field notes")
d = one(dialogs, old_notes, notes, "field notes swap")
# About: Bill Martin's revision of 2026-11-19 replaces the grey face's About text (new face only).
about = (OV / "about.html").read_text(encoding="utf-8")
about = about[about.index("  <dialog"):].rstrip("\n")
old_about = grab(d, r'(  <dialog id="about-project-dialog".*?</dialog>)', "grey about")
d = one(d, old_about, about, "about swap")
# Reset window label: drop "BLIND" (Bill, 2026-11-19; the link under the scene reads "Reset Session").
d = one(d, '<p class="eyebrow">NEW BLIND SESSION</p>', '<p class="eyebrow">NEW SESSION</p>', "reset label")
# Accessibility draft 2026-11-20 (issue 2): the Field notes window had no name for screen readers; About already has one.
d = one(d, '<dialog id="about-dialog" class="notes-dialog">', '<dialog id="about-dialog" class="notes-dialog" aria-label="Field notes">', "field notes name")
fills["DIALOGS"] = d

page = (OV / "index.template.html").read_text(encoding="utf-8")
for key, value in fills.items(): page = one(page, "{{%s}}" % key, value, f"template {key}")
assert "{{" not in page, "unfilled template placeholder"
# Bill's answers of 2026-11-19 (A9): the tab title is "Historic Shortwave" only.
page = one(page, "<title>Historic Shortwave | Archive Receiver</title>", "<title>Historic Shortwave</title>", "tab title")
# Recording dates read 1969-1992 (era extended from 1989 on 2026-11-27; the release data; Bill's date changes of 2026-11-19 and C6): the intro line and the
# page description still carried the grey face's 1960-1992.
page = one(page, "/</span> 1960-1992 COLLECTION</p>", "/</span> 1969-1992 COLLECTION</p>", "intro years")
page = one(page, "90, 60 and 49 meter bands, 1960-1992.", "90, 60 and 49 meter bands, 1969-1992.", "description years")
# A14: no HTML comments in the published page (they named internal build folders).
page = re.sub(r"\s*<!--.*?-->", "", page, flags=re.S)
assert "<!--" not in page, "HTML comment left in the page"
(OUT / "index.html").write_text(page, encoding="utf-8")

# ---------- app.js ----------
app = (SRC / "app.js").read_text(encoding="utf-8")
app = one(app, "function draw() {\n", "function draw() {\n  if(window.HSFace){window.HSFace.update();return;}\n", "draw hand-off")
app = one(app, "  rotary(knob,()=>state.hz,tune,bounds,()=>state.step===100?12000:120000);",
          "  if(!window.HSFace)rotary(knob,()=>state.hz,tune,bounds,()=>state.step===100?12000:120000);  // new face: speed-sensitive tuning in face.js",
          "tuning rotary")
app = one(app, "  $('go-receiver').onclick=", "  if($('go-receiver'))$('go-receiver').onclick=", "nav button")
app = one(app, "  $('theme-button').onclick=", "  if($('theme-button'))$('theme-button').onclick=", "theme button")   # decision 7: no night theme
app = one(app, "low.textContent=`${min/1000} kHz`;high.textContent=`${max/1000} kHz`", "low.textContent=`${min/1000} KC`;high.textContent=`${max/1000} KC`", "band edges")
app = one(app, "strong.textContent=frequency(g.hz)+' kHz';", "strong.textContent=frequency(g.hz)+' KC';", "band guide")
# Review 2026-11 F8: the engraving on this face reads AF GAIN.
app = one(app, "Turn AUDIO GAIN clockwise to hear the receiver.", "Turn AF GAIN clockwise to hear the receiver.", "gain wording 1")
app = one(app, "AUDIO GAIN controls its volume;", "AF GAIN controls its volume;", "gain wording 2")
# Review 2026-11 F9: with no catalog loaded, switching on or tuning keeps NO CATALOG instead of replacing it with NO SIGNAL.
app = one(app, "if(state.selected)await play();else status('NO SIGNAL');", "if(state.selected)await play();else status(state.records.length?'NO SIGNAL':'NO CATALOG');", "power-on status")
app = one(app, "else if(!next) status('NO SIGNAL');", "else if(!next) status(state.records.length?'NO SIGNAL':'NO CATALOG');", "tune status")
# Review 2026-11 F10: do not rewrite an unchanged status word (the node is a live region).
app = one(app, "function status(text) { $('receiver-status').textContent=text; }", "function status(text) { const node=$('receiver-status'); if(node.textContent!==text) node.textContent=text; }", "status rewrite")
# iPhone audio (approved 2026-11-19): one reusable audio element, unlocked by the first tap, so recordings
# reached by tuning are not refused by the iOS gesture rule. New face only; the grey face is unchanged.
def count(text, old, new, k, what):
    n = text.count(old)
    assert n == k, f"{what}: expected {k} matches, found {n}"
    return text.replace(old, new)

# 1. One audio player for the whole visit, unlocked by the first tap or key press.
app = one(app, "function status(text) {",
"""// iPhone Safari lets an audio element start only from a tap, or after a tap has started or loaded that same element.
// The receiver therefore keeps ONE element for the whole visit, unlocks it on the first tap or key press, and swaps
// each recording's source into it, so a recording reached by turning the knob can start without another tap.
const player=document.createElement('audio'); player.preload='metadata'; player.style.display='none'; document.body.append(player);
let audioUnlocked=false;
function unlockAudio(){ if(audioUnlocked) return; audioUnlocked=true; if(!player.getAttribute('src')) player.load(); }
for(const type of ['pointerup','touchend','click','keydown']) document.addEventListener(type,unlockAudio,{capture:true});
function status(text) {""", "1 shared player")

# 2. stopAudio: detach the recording from the player instead of discarding the element.
app = one(app, "  const audio=state.audio; state.audio=null; state.mediaState='idle';",
               "  const audio=state.audio; state.audio=null; state.audioToken=null; state.mediaState='idle';", "2a stop token")
app = one(app, "    audio.pause(); audio.removeAttribute('src'); audio.load(); audio.remove();",
               "    state.audioAbort?.abort(); state.audioAbort=null;\n    audio.pause(); audio.removeAttribute('src'); audio.load();", "2b keep element")

# 3. The 15-second loading timeout belongs to one recording.
app = one(app, "  state.loadTimer=setTimeout(()=>{\n    if(state.audio===audio && ",
               "  const token=state.audioToken;\n  state.loadTimer=setTimeout(()=>{\n    if(state.audioToken===token && state.audio===audio && ", "3 timeout token")

# 4. makeAudio: reuse the player; this recording's listeners are all removed when it stops.
app = one(app, "  const audio=document.createElement('audio'); audio.preload='metadata'; audio.volume=state.gain; audio.loop=state.loop;\n  audio.setAttribute('aria-label',`Audio clip ${recording.inventoryId}`); audio.style.display='none'; document.body.append(audio);\n  state.audio=audio;\n  const current=()=> state.audio===audio && state.selected?.id===recording.id;",
"""  const audio=player, token={}, abort=new AbortController(), on={signal:abort.signal};
  state.audioAbort=abort; state.audioToken=token; delete audio.dataset.refused;
  audio.volume=state.gain; audio.loop=state.loop; audio.setAttribute('aria-label',`Audio clip ${recording.inventoryId}`);
  state.audio=audio;
  const current=()=> state.audioToken===token && state.selected?.id===recording.id;""", "4a reuse player")
s, e = app.index("function makeAudio()"), app.index("async function play()")
m = app[s:e]
m = one(m, "clock(audio.duration); });", "clock(audio.duration); },on);", "4b loadedmetadata")
m = one(m, "audio.currentTime/audio.duration*100;});", "audio.currentTime/audio.duration*100;},on);", "4c timeupdate")
m = count(m, "\n  }});", "\n  }},on);", 3, "4d playing/pause/ended")
m = one(m, "\n  });\n  audio.addEventListener('error'", "\n  },on);\n  audio.addEventListener('error'", "4e waiting/stalled")
m = one(m, "could not play this file.');});", "could not play this file.');},on);", "4f error")
assert m.count("addEventListener(") == m.count(",on);") , "every listener in makeAudio carries the signal"
app = app[:s] + m + app[e:]

# 5. play(): a refused or aborted start counts only for the recording that asked for it.
app = one(app, "  makeAudio(); const audio=state.audio;", "  makeAudio(); const audio=state.audio, token=state.audioToken;", "5a play token")
app = one(app, "catch(error) {if(state.audio===audio&&state.power&&", "catch(error) {if(state.audioToken===token&&state.audio===audio&&state.power&&", "5b play catch")
# Bill's answers of 2026-11-19 (A7): kilocycles, not kilohertz, in screen-reader text as well as on the face.
app = one(app, "frequency(state.hz)+' kilohertz'", "frequency(state.hz)+' kilocycles'", "tuning valuetext")
app = one(app, "${band.maxHz/1000} kilohertz`", "${band.maxHz/1000} kilocycles`", "band valuetext")
# A9: station details after Reveal read KC. The archive's own label, when it differs, is still quoted unchanged.
app = one(app, "? `${khz} kHz` : `${khz} kHz (labeled", "? `${khz} KC` : `${khz} KC (labeled", "details KC")
# A9: the hidden "60 METER ARCHIVE BAND" element is gone from the page; app.js no longer writes to it.
app = one(app, "  document.querySelector('.receiver-description small').textContent=band.description;\n", "", "band description")
# Bill, 2026-11-19: the recording picker shows a shortened date so long date notes fit a phone. The full date note
# is unchanged in the catalog and still shows on the Recording Date line and in the station details after Reveal.
# Rule: inside the brackets keep only the first qualifier when it is circa, probable, possibly or winter, and drop any
# other bracketed note; a two-day range within one month reads 1971-12-24/25.
app = one(app, "option.textContent=`Clip ${r.inventoryId} · ${r.date}`;select.append(option);",
          "option.textContent=`Clip ${r.inventoryId} · ${pickerDate(r.date)}`;option.title=r.date;select.append(option);", "picker date")
app = one(app, "function renderAlternatives() {",
"""function pickerDate(date) {
  let d=String(date||'').replace(/\\s*\\(([^)]*)\\)/g,(all,note)=>{const first=note.split(';')[0].trim();return /^(circa|probable|possibly|winter)$/.test(first)?` (${first})`:'';});
  d=d.replace(/^(\\d{4}-\\d{2})-(\\d{2})\\/\\1-(\\d{2})$/,'$1-$2/$3');
  return d||String(date||'');
}
function renderAlternatives() {""", "picker date helper")
# ---------- accessibility for blind listeners (draft 2026-11-20, not yet approved) ----------
# Issue 3: the status word is still written at once to #receiver-status (tests and the on-page text read it), but it is
# spoken from a separate live region only once it has held steady: 0.7 s for most words, 2 s for LOADING and BUFFERING,
# so a recording that starts quickly is announced as PLAYING alone. A word is not spoken twice in a row.
app = one(app, "function status(text) { const node=$('receiver-status'); if(node.textContent!==text) node.textContent=text; }",
"""let spokenStatus='', statusTimer=null;
function status(text) {
  const node=$('receiver-status'); if(node.textContent===text) return; node.textContent=text;
  clearTimeout(statusTimer);
  statusTimer=setTimeout(()=>{ if(node.textContent===text&&text!==spokenStatus){ spokenStatus=text; $('status-announcement').textContent=text; } }, /^(LOADING|BUFFERING)$/.test(text)?2000:700);
}""", "a11y calm status")
# Issue 3: the "1 / 6" count is a status region; write it only when it changes.
app = one(app, "  $('alternative-count').textContent=`${index+1} / ${records.length}`;",
               "  {const count=`${index+1} / ${records.length}`; if($('alternative-count').textContent!==count) $('alternative-count').textContent=count;}", "a11y count rewrite")
# Issue 1: after Reveal, move focus to the station heading so a screen reader reads it (no scroll jump for sighted users).
# The panel is rebuilt when the credits arrive and when tuning inside the capture window, so a heading that had focus
# gets it back after each rebuild.
app = one(app, "  $('reveal-button').onclick=()=>{if(state.selected){state.revealed.add(state.selected.id);renderRecording();}};",
               "  $('reveal-button').onclick=()=>{if(state.selected){state.revealed.add(state.selected.id);state.focusStation=true;renderRecording();}};", "a11y reveal focus")
app = one(app, "  panel.replaceChildren(); panel.hidden=!r||!state.revealed.has(r.id);",
               "  const refocus=state.focusStation||(document.activeElement?.tagName==='H3'&&panel.contains(document.activeElement)); state.focusStation=false;\n  panel.replaceChildren(); panel.hidden=!r||!state.revealed.has(r.id);", "a11y refocus check")
app = one(app, "    const title=document.createElement('h3'); title.textContent=r.station; panel.append(title);",
               "    const title=document.createElement('h3'); title.textContent=r.station; title.tabIndex=-1; panel.append(title);", "a11y heading focusable")
app = one(app, "  if('mediaSession' in navigator) navigator.mediaSession.metadata=",
               "  if(refocus&&!panel.hidden) panel.querySelector('h3')?.focus({preventScroll:true});\n  if('mediaSession' in navigator) navigator.mediaSession.metadata=", "a11y refocus")
# Issue 5: KC is spoken as kilocycles; the visible text is unchanged.
app = one(app, "    b.append(strong,small);b.onclick=()=>tune(g.hz);",
               "    b.setAttribute('aria-label',`${frequency(g.hz)} kilocycles, ${small.textContent}`);\n    b.append(strong,small);b.onclick=()=>tune(g.hz);", "a11y guide KC")
app = one(app, "  $('band-slider').value=state.hz/1000;\n",
               "  $('band-slider').value=state.hz/1000; $('band-slider').setAttribute('aria-valuetext',frequency(state.hz)+' kilocycles');\n", "a11y slider KC")
# Station details and listener notes keep "KC" as written: a hidden "kilocycles" there would change the copied text and
# the paragraph the credit tests read. Field notes explains that KC means kilocycles.
(OUT / "app.js").write_text(app, encoding="utf-8")

# ---------- listener notes (C4, approved 2026-11-19) ----------
# The 25 working-style notes in design/release/release-notes-review-2026-11-12.md: project bookkeeping dropped, date and
# frequency cautions kept in plain words, "Also posted as ..." row numbers removed (the panel then shows its usual
# "Original archive labels preserved."). Each old note must match exactly, so the build stops if the data changes.
# Frequencies in the project's own notes read KC (A7). Archive URLs are kept unchanged.
NOTES = {
    "90m": {"rec-90m-0050": ("Also posted as 90M-0051.", None), "rec-90m-0054": ("Also posted as 90M-0052.", None),
            "rec-90m-0077": ("Also posted as 90M-0076.", None), "rec-90m-0121": ("Also posted as 90M-0120.", None),
            "rec-90m-0122": ("Also posted as 90M-0123.", None)},
    "49m": {"rec-49m-0042": ("Also posted as 49M-0041.", None), "rec-49m-0058": ("Also posted as 49M-0059.", None),
            "rec-49m-0168": ("Also posted as 49M-0169.", None), "rec-49m-0170": ("Also posted as 49M-0171.", None),
            "rec-49m-0220": ("Also posted as 49M-0221.", None),
            "rec-49m-0319": ("Placed at 6220 kHz, the frequency in the on-air ID; QSL gives 6230 kHz.",
                             "Placed at 6220 KC, the frequency in the on-air ID; QSL gives 6230 KC.")},
    "60m": {
        "rec-000004": ("Recorded by Dan Robinson. From user inventory", "Recorded by Dan Robinson."),
        "rec-000010": ("Recorded by Dan Robinson, Levittown PA (HQ-180A); frequency drifted; noise reduction applied. 5033 kHz is within 4750-5060 band. Timing unknown within the 1970s (owner decision 2026-10-20; earlier listed as \"circa; WRTH 1978 era\").",
                       "Recorded by Dan Robinson, Levittown PA (HQ-180A); frequency drifted; noise reduction applied. Exact date unknown within the 1970s."),
        "rec-000015": ("Recorded by Dan Robinson (Hammarlund HQ-180C). Listed as a candidate in user inventory; audio URL located here",
                       "Recorded by Dan Robinson (Hammarlund HQ-180C)."),
        "rec-000020": ("East Coast N. America reception. From user inventory", "East Coast N. America reception."),
        "rec-000021": ("5075 kHz is just above the 4750-5060 kHz band edge, but the contributor describes reception on a 60 m dipole; borderline",
                       "5075 KC is just above the 4750–5060 KC broadcast band; the recordist describes reception on a 60 meter dipole."),
        "rec-000050": ("Recorded by Colin Newell, British Columbia; frequency from file name. From user inventory",
                       "Recorded by Colin Newell, British Columbia; frequency taken from the file name."),
        "rec-000051": ("CC0 (Brett Saylor collection); date from file name. Same item has r_colosal_ID_4-79 files (likely April 1979, unconfirmed). From user inventory",
                       "CC0 (Brett Saylor collection); date taken from the file name. The same archive item has files named r_colosal_ID_4-79 (likely April 1979, unconfirmed)."),
        "rec-000052": ("CC0; as above. From user inventory", "CC0 (Brett Saylor collection); date taken from the file name."),
        "rec-000060": ("Date inferred from file name only; frequency per other Colosal files in item",
                       "Date inferred from the file name only; frequency taken from other Radio Colosal files in the same archive item."),
        "rec-000061": ("Date inferred from file name only", "Date inferred from the file name only."),
        "rec-000117": ("Below the 4750 kHz band edge (tropical-band neighbor); added at user request", "Just below the 4750 KC band edge (a tropical-band neighbor)."),
        "rec-000131": ("Below the 4750 kHz band edge (tropical-band neighbor); added at user request; s-off ID and El Condor Pasa",
                       "Just below the 4750 KC band edge (a tropical-band neighbor); sign-off ID and El Condor Pasa."),
        "rec-000162": ("Below the 4750 kHz band edge (tropical-band neighbor); added at user request", "Just below the 4750 KC band edge (a tropical-band neighbor)."),
        "rec-000252": ("Max Thomas, Indianapolis, Panasonic RF-2600. Description gives no date; date only from item date field. Frequency is the recordist label 4810v; other archive entries list this station on 4910/4911, so treat the frequency label with caution.",
                       "Max Thomas, Indianapolis, Panasonic RF-2600. The archive description gives no date; the date comes only from the archive item's date field. The frequency is the recordist's label, 4810v; other archive entries list this station on 4910 or 4911, so treat the frequency with caution."),
        "rec-000253": ("Max Thomas, Indianapolis, Panasonic RF-2600. Description says \"January 29 0008 UTC\"; year comes only from the item date field. Duplicate upload: https://archive.org/details/radio-quito-4920-shortwave (one row only).",
                       "Max Thomas, Indianapolis, Panasonic RF-2600. The archive description says \"January 29 0008 UTC\"; the year comes only from the archive item's date field. The same recording is also posted at https://archive.org/details/radio-quito-4920-shortwave."),
    }}
import json
changed = 0
for band, edits in NOTES.items():
    f = OUT / f"band-{band}.json"; data = json.loads(f.read_text(encoding="utf-8"))
    recs = {r["id"]: r for r in data["recordings"]}
    for rid, (old, new) in edits.items():
        assert recs[rid].get("notes") == old, f"note for {rid} changed in the source: {recs[rid].get('notes')!r}"
        if new is None: recs[rid].pop("notes")
        else: recs[rid]["notes"] = new
        changed += 1
    f.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
assert changed == 26, changed   # the 25 reviewed notes plus the KC wording of rec-49m-0319

# ---------- period borders 1969-1992 (C6, approved 2026-11-19; extended to 1992 on 2026-11-27) ----------
# The grey release's borders file covers 1960-1992. The new face keeps only shapes in effect at some point in
# 1969-1992, the recording years, in geo/period-borders-1969-1992.json. A shape that ended before 1969 can never be drawn
# for these recordings; the build checks that every map highlight still exists and every map date falls in 1969-1992.
geo = OUT / "geo"; old_geo = geo / "period-borders-1960-1992.json"
borders = json.loads(old_geo.read_text(encoding="utf-8"))
assert borders["name"] == "Period country borders 1960-1992 (simplified)"
kept = [f for f in borders["features"] if f["end"] >= "1969-01-01" and f["start"] <= "1992-12-31"]
borders.update(name="Period country borders 1969-1992 (simplified)", features=kept,
               modified="Filtered to 1969-1992, simplified, coordinates rounded, ring direction re-ordered")
ids = {f["id"] for f in kept}
entries = json.loads((geo / "reveal-geography.json").read_text(encoding="utf-8"))["entries"]
for band in ("90m", "60m", "49m"):
    for r in json.loads((OUT / f"band-{band}.json").read_text(encoding="utf-8"))["recordings"]:
        e = entries.get(r["id"])
        if not e: continue
        if e.get("dateUsed"): assert "1969-01-01" <= e["dateUsed"] <= "1992-12-31", f"map date outside 1969-1992: {r['id']} {e['dateUsed']}"
        h = e.get("highlight")
        if h and h["source"] == "cshapes": assert set(h["ids"]) <= ids, f"map highlight dropped by the 1969 filter: {r['id']}"
old_geo.unlink()
(geo / "period-borders-1969-1992.json").write_text(json.dumps(borders, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
lic = (geo / "LICENSES.md").read_text(encoding="utf-8")
lic = one(lic, "`period-borders-1960-1992.json`", "`period-borders-1969-1992.json`", "licenses file name")
lic = one(lic, "keeps only shapes valid in 1960–1992", "keeps only shapes valid in 1969–1992", "licenses years")
(geo / "LICENSES.md").write_text(lic, encoding="utf-8")
rm = (OUT / "reveal-map.js").read_text(encoding="utf-8")
rm = one(rm, "// Data: geo/period-borders-1960-1992.json", "// Data: geo/period-borders-1969-1992.json", "map comment")
rm = one(rm, "loadJson('./geo/period-borders-1960-1992.json')", "loadJson('./geo/period-borders-1969-1992.json')", "map file")
(OUT / "reveal-map.js").write_text(rm, encoding="utf-8")

for name in ("style.css", "faceplate-grey.css"): assert name not in page
print(f"built {OUT.relative_to(ROOT)}")
