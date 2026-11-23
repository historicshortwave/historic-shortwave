#!/usr/bin/env python3
"""Browser checks that between-station static really plays and that its switch works, on all three bands.

  python3 tools/test-static-playback.py --chrome PATH
Also reproduces the October 20, 2026 failure (noise files served as Git LFS placeholders) to prove the
test catches it. Runs on the development receiver (default) or, with HR64_APP=release/heritage-hr64-face, on the
new 3D receiver (updated 2026-11-20 at Bill's request): its smaller 60 m release catalog has a recording at
4902.1 KC, so the between-recordings check uses the first empty dial step above 4902 found in the loaded catalog. Archive station audio is answered with a short local tone; other external hosts are blocked.
"""
import functools, http.server, io, math, socketserver, struct, sys, threading, wave
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parent))
from receiver_tuning import tune_to

APP = Path(__import__("os").environ["HR64_APP"]).resolve() if __import__("os").environ.get("HR64_APP") else Path(__file__).resolve().parent.parent / "app" / "heritage-h60"
args = sys.argv[1:]
chrome = args[args.index("--chrome") + 1] if "--chrome" in args else None
width = int(args[args.index("--width") + 1]) if "--width" in args else 1280
FACE = (APP / "face.js").exists()   # the new 3D receiver (release/heritage-hr64-face)
GAP = """k => { for (let hz = Math.round(k * 1000); hz < k * 1000 + 50000; hz += 100)
  if (!ReceiverCatalog.findGroup(state.groups, hz)) return hz / 1000; return null; }"""


def tone(seconds=6, rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(int(seconds * rate))))
    return buf.getvalue()


TONE = tone()
POINTER = b"version https://git-lfs.github.com/spec/v1\noid sha256:0000\nsize 601100\n"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(APP)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{httpd.server_address[1]}"
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))
    if not cond: failures.append(name)


NOISE = """() => ({ status: seasonalNoise.status, ctx: seasonalNoise.ctx && seasonalNoise.ctx.state,
  target: seasonalNoise.targetGain, gain: seasonalNoise.master ? seasonalNoise.master.gain.value : null,
  checked: document.getElementById('static-button').getAttribute('aria-checked'),
  out: document.getElementById('static-output').textContent, desc: document.getElementById('static-description').textContent,
  band: state.band, selected: state.selected && state.selected.id, media: state.mediaState })"""


def open_page(browser, placeholders=False):
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    def route(r):
        url = r.request.url
        if url.startswith(BASE):
            if placeholders and "/audio/seasonal/" in url and url.endswith(".mp3"):
                return r.fulfill(status=200, body=POINTER, headers={"Content-Type": "audio/mpeg"})
            return r.continue_()
        if r.request.resource_type == "media":
            return r.fulfill(status=200, body=TONE, headers={"Content-Type": "audio/wav"})
        return r.abort()
    page.route("**/*", route)
    page.goto(BASE + "/index.html"); page.wait_for_timeout(500)
    return page, errors


def tune_khz(page, khz):
    tune_to(page, khz, 900)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome, args=["--autoplay-policy=no-user-gesture-required"])

    # 1. Reproduce the bug: placeholder noise files leave the engine in error with no sound.
    page, _ = open_page(browser, placeholders=True)
    tune_khz(page, 4902); page.click("#power-button"); page.wait_for_timeout(2500)
    st = page.evaluate(NOISE)
    check("placeholder noise files are detected as a failure (bug reproduced)", st["status"] == "error" and not st["gain"], st)
    page.close()

    # 2. Real files: static plays between recordings on each band, and the switch turns it off and on.
    page, errors = open_page(browser)
    for band, gap_khz, station_khz in (("60m", 4902, 4900), ("90m", 3302, None), ("49m", 5952, None)):
        if band != "60m":
            page.evaluate(f"selectBand('{band}')"); page.wait_for_timeout(600)
        if FACE: gap_khz = page.evaluate(GAP, gap_khz)
        tune_khz(page, gap_khz)
        if not page.evaluate("state.power"): page.click("#power-button")
        page.wait_for_timeout(2500)
        st = page.evaluate(NOISE)
        check(f"{band}: static ready and audible between recordings ({st['gain'] and round(st['gain'], 3)})",
              st["status"] == "ready" and st["ctx"] == "running" and st["selected"] is None and st["gain"] and st["gain"] > 0.005
              and st["desc"].startswith("Seasonal static is on between recordings"), st)
        page.click("#static-button"); page.wait_for_timeout(700)
        st = page.evaluate(NOISE)
        check(f"{band}: switch turns static OFF (silent)", st["checked"] == "false" and st["out"] == "Off" and st["target"] == 0 and st["gain"] < 0.002
              and st["desc"].startswith("Static is off"), st)
        page.click("#static-button"); page.wait_for_timeout(900)
        st = page.evaluate(NOISE)
        check(f"{band}: switch turns static back ON", st["checked"] == "true" and st["out"] == "On" and st["gain"] > 0.005, st)
        if station_khz:
            tune_khz(page, station_khz); page.wait_for_timeout(1500)
            st = page.evaluate(NOISE)
            check(f"{band}: static silent at a playing recording", st["selected"] and st["media"] == "playing" and st["gain"] < 0.002, st)
    page.click("#power-button"); page.wait_for_timeout(700)
    st = page.evaluate(NOISE)
    check("standby silences static", st["gain"] < 0.002 and st["desc"].startswith("Receiver is in standby"), st)
    check("no page errors", not errors, errors)
    browser.close()
httpd.shutdown()
print(f"{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED'} at {width}px")
sys.exit(1 if failures else 0)
