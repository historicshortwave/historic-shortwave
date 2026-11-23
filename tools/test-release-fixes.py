#!/usr/bin/env python3
"""Regression checks for the November 12, 2026 review fixes (Phases 1 and 2) in the release build.

  python3 tools/test-release-fixes.py --chrome PATH

Archive.org requests are answered with the bundled seasonal-noise MP3 (no internet needed), as in the reviewer's
probes in handoff/review-2026-11-12/review-probes/.
A1 release data carries only receiver fields; A2 a "stalled" event during buffered playback keeps PLAYING, while a
host that never answers still reaches AUDIO ERROR; A3 Reset with no recording at the default frequency hides the
reveal panel and disables Restart, with no page error; A4 the hint is restored after a successful Retry, reads
differently once revealed, and the button says Pause while loading; A5 a non-web license URL shows as plain text.
"""
import functools, http.server, json, shutil, socketserver, sys, tempfile, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
REL = ROOT / "release" / "heritage-hr64"
args = sys.argv[1:]
chrome = args[args.index("--chrome") + 1] if "--chrome" in args else None
failures = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[:300]}"))
    if not cond: failures.append(name)

# A1: data checks
FIELDS = {"id", "inventoryId", "sortKey", "frequencyHz", "frequencyLabel", "station", "country", "date", "time",
          "notes", "sourceUrl", "audioUrl", "additionalReferences"}
for b in ("90m", "60m", "49m"):
    d = json.loads((REL / f"band-{b}.json").read_text())
    check(f"A1 {b} catalog holds only receiver fields", {k for r in d["recordings"] for k in r} <= FIELDS)
    check(f"A1 {b} has no band-edge working note", not any("User-authorized" in (r.get("notes") or "") for r in d["recordings"]))
for f in ("credits.json", "geo/reveal-geography.json"):
    t = (REL / f).read_text()
    check(f"A1 {f} has no internal text", not any(s in t for s in ("HR-64", "generatedBy", "needsReview", '"basis"', '"decision"')))

# Copy with javascript: license URLs for A5
tmp = Path(tempfile.mkdtemp()); bad = tmp / "rel"; shutil.copytree(REL, bad)
c = json.loads((bad / "credits.json").read_text())
for v in c["credits"].values():
    if "license" in v: v["license"]["url"] = "javascript:window.__pwned=1"
(bad / "credits.json").write_text(json.dumps(c))

MP3 = (REL / "audio/seasonal/summer-bed.mp3").read_bytes()
def serve(folder):
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(folder)))
    threading.Thread(target=h.serve_forever, daemon=True).start()
    return h, f"http://127.0.0.1:{h.server_address[1]}"
mode = {"v": "ok"}
def router(base):
    def route(r):
        u = r.request.url
        if u.startswith(base): return r.continue_()
        if "archive.org" in u.split("/")[2]:
            if mode["v"] == "ok": return r.fulfill(status=200, headers={"content-type": "audio/mpeg"}, body=MP3)
            if mode["v"] == "404": return r.fulfill(status=404, body="no")
            if mode["v"] == "hang": return
        return r.abort()
    return route
S = """()=>({status:document.getElementById('receiver-status').textContent, ms:state.mediaState, play:document.getElementById('play-button').textContent,
  desc:document.getElementById('listening-description').textContent})"""

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=chrome, args=["--autoplay-policy=no-user-gesture-required"])
    h, base = serve(REL)
    page = br.new_context(viewport={"width": 1280, "height": 900}).new_page(); errs = []
    page.on("pageerror", lambda e: errs.append(str(e))); page.route("**/*", router(base))
    page.goto(base + "/index.html"); page.wait_for_function("state.records.length>0")
    page.click("#power-button"); page.wait_for_timeout(3000)
    check("A2 setup: recording is playing", page.evaluate(S)["ms"] == "playing", page.evaluate(S))
    page.evaluate("state.audio.dispatchEvent(new Event('stalled'))"); page.wait_for_timeout(16500)
    s = page.evaluate(S); check("A2 a stalled event during buffered playback keeps PLAYING", s["ms"] == "playing" and s["status"] == "PLAYING", s)
    # A4: revealed hint
    page.click("#reveal-button"); page.wait_for_timeout(500)
    check("A4 hint changes after Reveal", page.evaluate(S)["desc"].startswith("The station is revealed"), page.evaluate(S))
    # A4: retry restores hint
    mode["v"] = "404"; page.evaluate("tune(state.groups[40].hz)"); page.wait_for_timeout(3000)
    s = page.evaluate(S); check("A4 setup: 404 shows AUDIO ERROR", s["ms"] == "error", s)
    mode["v"] = "ok"; page.click("#play-button"); page.wait_for_timeout(3000)
    s = page.evaluate(S); check("A4 the hint is restored after a successful Retry", s["ms"] == "playing" and s["desc"].startswith("Listen for a voice"), s)
    # A4: loading label, then A2: genuine hang still fails
    mode["v"] = "hang"; page.evaluate("tune(state.groups[75].hz)"); page.wait_for_timeout(1500)
    s = page.evaluate(S); check("A4 the button says Pause while a recording loads", s["ms"] in ("loading", "buffering") and s["play"] == "Pause recording", s)
    page.wait_for_timeout(30000)
    s = page.evaluate(S); check("A2 a host that never answers still reaches AUDIO ERROR", s["ms"] == "error" and s["status"] == "AUDIO ERROR", s)
    # A3: reset with an empty default frequency
    mode["v"] = "ok"; page.evaluate("tune(state.groups[10].hz)"); page.wait_for_timeout(800); page.click("#reveal-button"); page.wait_for_timeout(500)
    empty = page.evaluate("(()=>{for(let hz=4700000;hz<5085000;hz+=100){if(!ReceiverCatalog.findGroup(state.groups,hz))return hz;}})()")
    page.evaluate(f"BANDS['60m'].defaultHz={empty}"); page.click("#new-session"); page.click("#confirm-reset"); page.wait_for_timeout(600)
    r = page.evaluate("({sel:state.selected, hidden:document.getElementById('reveal-panel').hidden, restart:document.getElementById('restart-button').disabled})")
    check("A3 Reset with no recording at the default hides the reveal panel and disables Restart", r["sel"] is None and r["hidden"] and r["restart"], r)
    page.evaluate("document.getElementById('restart-button').onclick()"); page.wait_for_timeout(300)
    check("A3 no page errors", not errs, errs)
    h.shutdown()
    # A5
    h, base = serve(bad)
    page = br.new_context().new_page(); page.route("**/*", router(base))
    page.goto(base + "/index.html"); page.wait_for_function("state.records.length>0")
    page.click("#reveal-button")
    for _ in range(100):
        if page.evaluate("(()=>{const c=document.querySelector('.recording-credit');return !!c && !c.classList.contains('is-pending')})()"): break
        page.wait_for_timeout(100)
    lic = page.evaluate("({links:document.querySelectorAll('.recording-credit a').length, text:document.querySelector('.recording-credit').innerText})")
    check("A5 a javascript: license URL is shown as plain text, not a link", lic["links"] == 0 and "CC" in lic["text"], lic)
    h.shutdown(); br.close()
shutil.rmtree(tmp)
print("ALL PASS" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
