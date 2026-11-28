#!/usr/bin/env python3
"""Browser checks for the BAND rotary switch (plan phase 3).

Run from the project root:
  python3 tools/test-band-switch.py --chrome PATH [--width PX]
External hosts are blocked, so recordings end in the normal playback-unavailable state.

New 3D receiver (HR64_APP=release/heritage-hr64-face; updated 2026-11-20 at Bill's request). Where the face differs by
design, the check follows the face:
- counts, alternatives and clip numbers come from its release catalogs (band-*.json), which are smaller than the
  development inventory, and its 60 m list is already the full list (no baseline/full selector, no review count);
- screen-reader wording is in kilocycles; status words are the one-line S-meter words;
- the power control is the lever switch (#power-button) only, with no OFF/ON words to click;
- Reveal is a filled, lit button rather than a framed one;
- there are no engraved band numbers to click (that check is skipped and reported as a note);
- the hidden receiver-description block is gone (tools/test-face.py checks that it stays gone).
"""
import functools, http.server, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parent))
from receiver_tuning import tune_to

ROOT = Path(__file__).resolve().parent.parent
APP = Path(__import__("os").environ["HR64_APP"]).resolve() if __import__("os").environ.get("HR64_APP") else ROOT / "app" / "heritage-h60"
args = sys.argv[1:]
chrome = args[args.index("--chrome") + 1] if "--chrome" in args else None
width = int(args[args.index("--width") + 1]) if "--width" in args else 1280
FACE = (APP / "face.js").exists()   # the new 3D receiver (release/heritage-hr64-face)
UNIT = "kilocycles" if FACE else "kilohertz"
if FACE:
    import json
    BAND = {b: json.loads((APP / f"band-{b}.json").read_text()) for b in ("60m", "90m", "49m")}
    def alternatives(band, hz): return sum(r["frequencyHz"] == hz for r in BAND[band]["recordings"])


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(APP)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
port = httpd.server_address[1]
BASE = f"http://127.0.0.1:{port}"
STATE = """() => { const $ = id => document.getElementById(id), k = $('band-knob');
  return { top: document.querySelector('.dial-top span').textContent, range: document.querySelector('.dial-top span:last-child').textContent,
    desc: document.querySelector('.receiver-description small')?.textContent ?? null, freq: $('frequency-readout').textContent,
    slider: [$('band-slider').min, $('band-slider').max, $('band-slider').value], knob: [k.getAttribute('aria-valuenow'), k.getAttribute('aria-valuetext'), k.style.transform],
    tuneKnob: [$('tuning-knob').getAttribute('aria-valuemin'), $('tuning-knob').getAttribute('aria-valuemax')],
    output: $('band-output').textContent, select: $('band-select').value, active: [...document.querySelectorAll('.band-mark.active')].map(m => m.dataset.band),
    clip: $('clip-id').textContent, scope: $('scope-label').textContent, guide: $('guide-count').textContent, catalogHidden: $('catalog-select') ? $('catalog-select').parentElement.hidden : null,
    status: $('catalog-status').textContent, receiver: $('receiver-status').textContent, alts: $('alternative-count').textContent,
    announce: $('band-announcement').textContent, review: $('review-count')?.textContent ?? null }; }"""
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))
    if not cond: failures.append(name)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome)
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    block = {"90m": False}
    def route(r):
        url = r.request.url
        if not url.startswith(BASE): return r.abort()
        if block["90m"] and url.endswith("/band-90m.json"): return r.abort()
        return r.continue_()
    page.route("**/*", route)
    page.goto(BASE + "/index.html"); page.wait_for_timeout(700)
    s = lambda: page.evaluate(STATE)
    wait = lambda ms=450: page.wait_for_timeout(ms)

    st = s()
    if FACE:
        check("starts on 60 m", st["top"] == "60 METERS" and st["knob"][0] == "2" and st["freq"] == "4900.0"
              and st["status"] == f"{BAND['60m']['counts']['total']} recordings on 60 m", st)
    else:
        check("starts on 60 m baseline", st["top"] == "60 METERS" and st["knob"][0] == "2" and st["active"] == ["60m"] and st["freq"] == "4900.0" and st["catalogHidden"] is False, st)
    # Interface edits, October 29, 2026: OFF/ON switch words, SPEEDX replaces WRTVH, highlighted Reveal.
    words = lambda: page.evaluate("[...document.querySelectorAll('.power-word')].map(w => w.textContent + (w.classList.contains('active') ? '*' : ''))")
    if not FACE: check("power switch reads OFF / ON with OFF lit at start", words() == ["OFF*", "ON"], words())
    links = page.evaluate("[...document.querySelectorAll('.research-buttons a')].map(a => a.textContent.trim().split(/\\s+/)[0] + '|' + a.href)")
    check("research links: FBIS, SPEEDX, NASWA; no WRTVH", [l.split('|')[0] for l in links] == ["FBIS", "SPEEDX", "NASWA"] and "https://www.worldradiohistory.com/Speedx.htm" in links[1] and "wrth" not in " ".join(links).lower(), links)
    if FACE:
        check("Reveal is a filled, highlighted button with its lamp", page.evaluate("getComputedStyle(document.getElementById('reveal-button')).backgroundColor") not in ("rgba(0, 0, 0, 0)", "transparent") and page.locator("#reveal-button .reveal-lamp").count() == 1)
        check("power switch starts OFF", page.get_attribute("#power-button", "aria-checked") == "false")
        page.click("#power-button"); wait(300)
        check("clicking the power switch turns the receiver on", page.get_attribute("#power-button", "aria-checked") == "true" and page.evaluate("state.power") is True)
        page.click("#power-button"); wait(300)
        check("clicking it again turns it off", page.get_attribute("#power-button", "aria-checked") == "false" and page.evaluate("state.power") is False)
    else:
        check("Reveal is a framed, highlighted button", page.evaluate("getComputedStyle(document.getElementById('reveal-button')).borderTopStyle") == "solid" and page.locator("#reveal-button .reveal-lamp").count() == 1)
        page.click("#power-label"); wait(300)
        check("clicking ON turns the receiver on and lights ON", page.get_attribute("#power-button", "aria-checked") == "true" and words() == ["OFF", "ON*"], words())
        page.click("#power-label"); wait(200)
        check("clicking ON again leaves it on", page.get_attribute("#power-button", "aria-checked") == "true")
        page.click("#power-off"); wait(300)
        check("clicking OFF turns it off", page.get_attribute("#power-button", "aria-checked") == "false" and words() == ["OFF*", "ON"], words())
    check("knob announces band and range", st["knob"][1] == f"60 meter band, 4700 to 5085 {UNIT}", st["knob"])

    # Failed catalog load reverts the switch and keeps 60 m.
    block["90m"] = True
    page.focus("#band-knob"); page.keyboard.press("ArrowLeft"); wait()
    st = s()
    check("failed 90 m load reverts to 60 m", st["top"] == "60 METERS" and st["knob"][0] == "2" and st["select"] == "60m" and "could not load" in st["announce"], st)
    block["90m"] = False

    # Keyboard: ArrowLeft -> 90 m.
    page.keyboard.press("ArrowLeft"); wait()
    st = s()
    check("ArrowLeft selects 90 m", st["top"] == "90 METERS" and st["range"] == "3.150–3.500 Mc/s" and st["slider"][:2] == ["3150", "3500"] and st["tuneKnob"] == ["3150", "3500"], st)
    check("90 m opens at default 3300 kHz", st["freq"] == "3300.0" and st["knob"][2] == "rotate(-50deg)" and st["output"] == "90 M", st)
    if FACE:
        c = BAND["90m"]["counts"]
        check(f"90 m catalog counts ({c['frequencies']} positions, {c['total']} recordings)", st["guide"] == f"{c['frequencies']} recording positions" and st["status"] == f"{c['total']} recordings on 90 m", st)
        check("90 m scope", st["scope"] == "90 METER COLLECTION", st)
    else:
        check("90 m catalog counts", st["guide"] == "77 recording positions" and st["status"] == "170 inventory entries · 154 tunable · 16 awaiting review" and st["review"] == "16", st)
        check("baseline selector hidden on 90 m", st["catalogHidden"] is True, st)
        check("90 m scope and description", st["scope"] == "90 METER COLLECTION" and st["desc"] == "90 METER ARCHIVE BAND", st)
    check("band change announced", st["announce"] == f"90 meter band, 3150 to 3500 {UNIT}", st["announce"])
    page.keyboard.press("ArrowLeft"); wait(200)
    check("90 m is the lowest stop (no wrap)", s()["top"] == "90 METERS")

    # Tune within 90 m, then End -> 49 m, Home -> 90 m remembers frequency.
    tune_to(page, "3325"); wait(200)
    n = alternatives("90m", 3325000) if FACE else 7
    st = s(); check(f"3325 kHz has {n} alternatives", st["alts"] == f"1 / {n}", st["alts"])
    page.focus("#band-knob"); page.keyboard.press("End"); wait()
    st = s(); check("End selects 49 m at 6100 kHz", st["top"] == "49 METERS" and st["freq"] == "6100.0" and st["knob"][0] == "3", st)
    page.keyboard.press("Home"); wait()
    st = s(); check("Home returns to 90 m at remembered 3325 kHz", st["top"] == "90 METERS" and st["freq"] == "3325.0", st)

    # Engraved number click (the face has no engraved band numbers; End selects 49 m instead).
    if FACE:
        print("NOTE the face has no engraved band numbers to click; that check is skipped")
        page.focus("#band-knob"); page.keyboard.press("End"); wait()
    else:
        page.click(".band-mark[data-band='49m']"); wait()
        st = s(); check("clicking 49 selects 49 m", st["top"] == "49 METERS" and st["active"] == ["49m"], st)
        check("focus moves to band knob after mark click", page.evaluate("document.activeElement.id") == "band-knob")
    tune_to(page, "6155"); wait(200)
    n = alternatives("49m", 6155000) if FACE else 9
    check(f"6155 kHz has {n} alternatives", s()["alts"] == f"1 / {n}", s()["alts"])

    # Plain selector under Alternative controls.
    page.evaluate("document.querySelector('.accessible-tuning, details.alt-controls').open = true")   # the face calls it details.alt-controls
    page.select_option("#band-select", "60m"); wait()
    st = s(); check("selector returns to 60 m at 4900 kHz", st["top"] == "60 METERS" and st["freq"] == "4900.0" and st["catalogHidden"] is (None if FACE else False), st)

    # Tuning to another band's frequency (band list, then slider).
    tune_to(page, "3480"); wait()
    st = s(); check("tuning to 3480 on 90 m selects the edge recording", st["top"] == "90 METERS" and st["freq"] == "3480.0" and st["clip"] == ("AUDIO CLIP" if FACE else "ARCHIVE CLIP") + " 90M-0141", st)

    # Drag the knob clockwise ~110 degrees from 90 m: should pass 60 and land on 49.
    page.locator("#band-knob").scroll_into_view_if_needed()
    box = page.locator("#band-knob").bounding_box(); cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    import math
    def at(deg, r=22): a = math.radians(deg - 90); return cx + r * math.cos(a), cy + r * math.sin(a)
    page.mouse.move(*at(-50)); page.mouse.down()
    for d in range(-50, 66, 5): page.mouse.move(*at(d)); page.wait_for_timeout(15)
    page.mouse.up(); wait(700)
    st = s(); check("drag clockwise snaps through 60 to 49 m", st["top"] == "49 METERS" and st["knob"][2] == "rotate(50deg)", st)
    page.locator("#band-knob").scroll_into_view_if_needed()
    box = page.locator("#band-knob").bounding_box(); cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(*at(50)); page.mouse.down()
    for d in range(50, 10, -5): page.mouse.move(*at(d)); page.wait_for_timeout(15)
    page.mouse.up(); wait(700)
    st = s(); check("drag 40 degrees back snaps to 60 m", st["top"] == "60 METERS", st)

    # Rapid switching: the last request wins.
    page.focus("#band-knob")
    for key in ["ArrowRight", "ArrowLeft", "ArrowLeft", "ArrowRight", "ArrowRight"]: page.keyboard.press(key)
    wait(900)
    st = s(); check("rapid keys settle on the last band (49 m)", st["top"] == "49 METERS" and st["select"] == "49m" and st["knob"][0] == "3", st)

    # Power on, switch band: audio for the old band stops, the new band's recording is selected.
    tune_to(page, "6155"); wait(200)
    page.click("#power-button"); wait(800)
    page.focus("#band-knob"); page.keyboard.press("ArrowLeft"); wait(900)
    # The 60 m dial was left at 4900 kHz. The development baseline lists clip 46 first there; the release catalog lists clip 1.
    want_clip, words_ok = ("AUDIO CLIP 1", ("AUDIO ERROR", "LOADING", "BUFFERING", "TUNED")) if FACE else ("ARCHIVE CLIP 46", ("PLAYBACK UNAVAILABLE", "LOADING ARCHIVE AUDIO", "RECORDING TUNED"))
    st = s(); check("powered band change selects the new band's recording", st["top"] == "60 METERS" and st["clip"] == want_clip and st["receiver"] in words_ok, st)
    check("no stray audio elements after switching", page.evaluate("document.querySelectorAll('audio').length") <= 1)
    page.click("#power-button"); wait(200)

    # No typed input anywhere on the page.
    check("no text box, text area or form on the page", page.evaluate("document.querySelectorAll('input:not([type=range]),textarea,form,[contenteditable]').length") == 0)
    page.focus("#band-knob"); page.keyboard.press("ArrowLeft"); wait()

    # Reset stays on the current band.
    page.click("#new-session"); page.click("#confirm-reset"); wait(300)
    st = s(); check("reset stays on 90 m at its default", st["top"] == "90 METERS" and st["freq"] == "3300.0", st)

    check("no page errors", not errors, errors)
    browser.close()
httpd.shutdown()
print(f"{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED'} at {width}px")
sys.exit(1 if failures else 0)
