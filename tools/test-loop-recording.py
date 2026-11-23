#!/usr/bin/env python3
"""Browser checks for Loop recording and the hidden band-conditions label.

  python3 tools/test-loop-recording.py --chrome PATH [--width PX]
Archive audio requests are answered with a 1.2-second local tone (or a 404 for the failure check),
so looping can be observed without reaching any external host.

New 3D receiver (HR64_APP=release/heritage-hr64-face; updated 2026-11-20 at Bill's request): the face uses the one-line
S-meter status words (ENDED, PLAYING, AUDIO ERROR) instead of RECORDING ENDED, ARCHIVE AUDIO and PLAYBACK UNAVAILABLE;
it has no receiver-description block at all; Reveal sits in its own row under the playback buttons; and its 60 m
release catalog has a recording at 4902.1 KC, so the no-recording check uses the first empty dial step above 4902.
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
WORD = {"ended": "ENDED", "playing": "PLAYING", "error": "AUDIO ERROR"} if FACE else \
       {"ended": "RECORDING ENDED", "playing": "ARCHIVE AUDIO", "error": "PLAYBACK UNAVAILABLE"}


def tone(seconds=1.2, rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(int(seconds * rate))))
    return buf.getvalue()


TONE = tone()


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(APP)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{httpd.server_address[1]}"
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))
    if not cond: failures.append(name)


ST = """() => { const b = document.getElementById('loop-button'), a = state.audio;
  return { pressed: b.getAttribute('aria-pressed'), label: b.textContent.trim(), disabled: b.disabled, loopAttr: a ? a.loop : null,
    media: state.mediaState, status: document.getElementById('receiver-status').textContent, play: document.getElementById('play-button').textContent,
    selected: state.selected?.id, t: a ? a.currentTime : null, desc: document.getElementById('listening-description').textContent }; }"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome, args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors, audio_hits, mode = [], [], {"fail": False}
    page.on("pageerror", lambda e: errors.append(str(e)))
    def route(r):
        url = r.request.url
        if url.startswith(BASE): return r.continue_()
        if r.request.resource_type == "media" or url.lower().split("?")[0].endswith((".mp3", ".ogg", ".wav", ".m4a")):
            audio_hits.append(url)
            if mode["fail"]: return r.fulfill(status=404, body="")
            return r.fulfill(status=200, body=TONE, headers={"Content-Type": "audio/wav", "Accept-Ranges": "none"})
        return r.abort()
    page.route("**/*", route)
    page.goto(BASE + "/index.html"); page.wait_for_timeout(600)
    s = lambda: page.evaluate(ST)
    wait = page.wait_for_timeout

    # Band conditions: gone from the face, still running underneath.
    check("band-conditions label removed from the face", page.locator("#band-conditions").count() == 0 and "Band conditions" not in
          (page.inner_text("body") if FACE else page.inner_text(".receiver-description")))
    ds = page.evaluate("Object.assign({}, document.getElementById('receiver').dataset)")
    check("seasonal conditions still computed (data on receiver)", ds.get("season") in ("winter", "spring", "summer", "autumn") and ds.get("seasonDate"), ds)
    page.goto(BASE + "/index.html?season=winter"); wait(500)
    ds2 = page.evaluate("Object.assign({}, document.getElementById('receiver').dataset)")
    check("?season= in the web address is ignored", ds2.get("season") == ds.get("season") and "seasonOverride" not in ds2, ds2)

    st = s()
    check("Loop defaults to OFF", st["pressed"] == "false" and st["label"].endswith("OFF") and not st["disabled"], st)
    order = page.evaluate("[...document.querySelectorAll('.playback-actions > button')].map(b => b.id)")
    if FACE:
        check("order: Play, Restart, Loop; Reveal in its own row below", order == ["play-button", "restart-button", "loop-button"]
              and page.locator(".reveal-row #reveal-button").count() == 1, order)
        gap = page.evaluate("(() => { for (let hz = 4902000; ; hz += 100) if (!ReceiverCatalog.findGroup(state.groups, hz)) return hz / 1000; })()")
    else:
        check("order: Play, Restart, Loop, Reveal", order == ["play-button", "restart-button", "loop-button", "reveal-button"], order)
        gap = 4902
    tune_to(page, str(gap)); wait(150)
    check("Loop disabled when no recording is tuned", s()["disabled"] is True)
    tune_to(page, "4900"); wait(150)

    # Loop off: the recording ends normally.
    page.click("#power-button"); wait(2600)
    st = s()
    check("loop off: recording ends (RECORDING ENDED, Replay)", st["media"] == "ended" and st["status"] == WORD["ended"] and st["play"] == "Replay recording", st)
    first = st["selected"]

    # Turning Loop on after the end does not start playback by itself.
    page.click("#loop-button"); wait(400)
    st = s()
    check("Loop ON: aria-pressed true, label ON, applied to audio", st["pressed"] == "true" and st["label"].endswith("ON") and st["loopAttr"] is True, st)
    check("turning Loop on after the end does not autoplay", st["media"] == "ended", st)
    check("description says Loop is on", "Loop is on" in st["desc"], st["desc"])

    # Loop on: replay and watch it wrap past the end at least twice.
    page.click("#play-button"); wait(200)
    page.evaluate("window.__wraps = 0; window.__last = 0; const a = state.audio; a.addEventListener('timeupdate', () => { const t = a.currentTime; if (t + 0.3 < window.__last) window.__wraps++; window.__last = t; }); a.addEventListener('ended', () => window.__ended = true);")
    wait(3600)
    st = s(); wraps = page.evaluate("window.__wraps"); ended = page.evaluate("!!window.__ended")
    check(f"loop on: recording repeats ({wraps} wraps in 3.6 s, no end)", wraps >= 2 and not ended and st["media"] == "playing" and st["status"] == WORD["playing"], (wraps, ended, st))
    check("loop never advances to another recording", st["selected"] == first, st)

    # Turning Loop off while playing lets it finish this pass and stop.
    page.click("#loop-button"); wait(2000)
    st = s()
    check("Loop off mid-play: finishes and ends", st["pressed"] == "false" and st["loopAttr"] is False and st["media"] == "ended", st)

    # The setting carries to the next recording (new audio element) until turned off.
    page.click("#loop-button")
    tune_to(page, "4840"); wait(400)
    st = s()
    check("Loop setting carries to the next recording", st["pressed"] == "true" and st["loopAttr"] is True and st["selected"] != first, st)

    # Failure with Loop on: unavailable once, no retry storm.
    mode["fail"] = True; before = len(audio_hits)
    tune_to(page, "4900"); wait(2500)
    st = s(); hits = len(audio_hits) - before
    check(f"failed recording with Loop on is not retried ({hits} request)", st["media"] == "error" and st["status"] == WORD["error"] and hits <= 2, (st, hits))
    mode["fail"] = False

    # New blind session turns Loop off.
    page.click("#power-button"); wait(100)
    page.click("#new-session"); page.click("#confirm-reset"); wait(300)
    st = s(); check("new blind session turns Loop off", st["pressed"] == "false" and st["label"].endswith("OFF"), st)

    # Keyboard: Space/Enter toggle it like any button.
    page.focus("#loop-button"); page.keyboard.press("Space"); wait(50)
    check("keyboard toggles Loop", s()["pressed"] == "true")
    check("no page errors", not errors, errors)
    browser.close()
httpd.shutdown()
print(f"{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED'} at {width}px")
sys.exit(1 if failures else 0)
