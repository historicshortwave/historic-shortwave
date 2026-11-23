#!/usr/bin/env python3
"""Browser checks for the Content Security Policy and the approved-archive audio check (added 2026-10-21).

  python3 tools/test-security.py --chrome PATH [--width PX]
Archive hosts are reachable in the first part, to prove real playback works under the policy. Every other
outside request is recorded and fails the test.
"""
import functools, http.server, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parent))
from receiver_tuning import tune_to

APP = Path(__import__("os").environ["HR64_APP"]).resolve() if __import__("os").environ.get("HR64_APP") else Path(__file__).resolve().parent.parent / "app" / "heritage-h60"
args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
chrome, width = opt("--chrome"), int(opt("--width", 1280))
# Approved archive hosts come from the page's own media-src (since 2026-11-12), so the test fits the preview
# (three archives) and the release (Archive.org only). "*.archive.org" matches any archive.org subdomain.
import re as _re
_csp = _re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', (APP / "index.html").read_text()).group(1)
JS_HOSTS = set(_re.findall(r"'([^']+)'", _re.search(r"APPROVED_AUDIO_HOSTS=\[([^\]]+)\]", (APP / "app.js").read_text()).group(1)))
ARCHIVES = tuple(h.replace("https://", "").replace("*.", "") for h in _re.search(r"media-src ([^;]+)", _csp).group(1).split())


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(APP)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{httpd.server_address[1]}"
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))
    if not cond: failures.append(name)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome, args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_context(viewport={"width": width, "height": 900}, reduced_motion="reduce").new_page()
    console, errors, outside, archive = [], [], [], []
    page.on("console", lambda m: console.append(m.text) if "Content Security Policy" in m.text else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    def route(r):
        u = r.request.url
        if u.startswith(BASE): return r.continue_()
        if any(h in u.split("/")[2] for h in ARCHIVES):
            archive.append(u); return r.continue_()
        outside.append(u); return r.abort()
    page.route("**/*", route)
    page.add_init_script("window.__v=[];document.addEventListener('securitypolicyviolation',e=>window.__v.push(e.violatedDirective+' '+e.blockedURI+' '+(e.sample||'')))")
    page.goto(BASE + "/index.html"); page.wait_for_timeout(700)

    csp = page.evaluate("document.querySelector('meta[http-equiv=Content-Security-Policy]')?.content||''")
    check("page carries a Content Security Policy", "default-src 'none'" in csp and "script-src 'self'" in csp, csp)
    media = set(_re.search(r"media-src ([^;]+)", csp).group(1).split())
    check("policy limits audio to the approved archives in app.js", media == {"https://" + h for h in JS_HOSTS} | {"https://*.archive.org"}, (media, JS_HOSTS))

    # A real session under the policy: static, one recording on each archive host, reveal, map, credits,
    # and theme.
    page.click("#power-button"); page.wait_for_timeout(2500)
    check("seasonal static loads under the policy", page.evaluate("seasonalNoise.status") == "ready", page.evaluate("seasonalNoise.status"))
    played = {}
    for band, khz in (("60m", "4800"), ("49m", "6010"), ("90m", "3205"), ("49m", "6025")):
        page.evaluate(f"selectBand('{band}')"); page.wait_for_timeout(600)
        tune_to(page, khz); page.wait_for_timeout(6000)
        a = page.evaluate("(()=>{const a=document.querySelector('audio');return a?{src:a.currentSrc,t:a.currentTime,err:a.error&&a.error.code}:null})()")
        if a and a["src"]:
            played[a["src"].split("/")[2]] = a
        page.click("#reveal-button"); page.wait_for_timeout(1500)
    # One Radio Heritage recording (49M-0001), chosen by clip so the third host is always covered (preview only;
    # the release holds Archive.org recordings only).
    if "www.radioheritage.com" in JS_HOSTS:
        page.evaluate("selectBand('49m')"); page.wait_for_timeout(600)
        tune_to(page, "5950"); page.wait_for_timeout(300)
        page.evaluate("(()=>{const s=document.getElementById('recording-select');s.value='rec-49m-0001';s.dispatchEvent(new Event('change'))})()")
        page.wait_for_timeout(6000)
        a = page.evaluate("(()=>{const a=document.querySelector('audio');return a?{src:a.currentSrc,t:a.currentTime,err:a.error&&a.error.code}:null})()")
        if a and a["src"]: played[a["src"].split("/")[2]] = a
        page.click("#reveal-button"); page.wait_for_timeout(1500)
    hosts = sorted(played)
    check(f"recordings play under the policy from every approved archive ({len(JS_HOSTS)})",
          any(h.endswith("archive.org") for h in hosts) and all(h in hosts for h in JS_HOSTS - {"archive.org"}) and all(v["t"] > 0 and not v["err"] for v in played.values()), played)
    check("reveal map draws under the policy", page.evaluate("!!document.querySelector('#reveal-panel svg path')"))
    check("credit line shows under the policy", page.locator("[data-testid=text-recording-credit]").count() == 1)
    if page.locator("#theme-button").count(): page.click("#theme-button"); page.wait_for_timeout(150); page.click("#theme-button")  # grey face only (new face has no night theme)
    check("no typed input anywhere (no text box, text area, form or editable area)",
          page.evaluate("document.querySelectorAll('input:not([type=range]),textarea,form,[contenteditable]').length") == 0)
    check("no policy violations in a full session", page.evaluate("window.__v") == [] and console == [], (page.evaluate("window.__v"), console[:3]))

    # Approved-archive check: tampered addresses are refused before any request is made.
    page.evaluate("selectBand('60m')"); page.wait_for_timeout(500)
    tune_to(page, "4800"); page.wait_for_timeout(400)
    for bad in ("https://evil.example/clip.mp3", "http://archive.org/download/x/x.mp3", "https://archive.org.evil.example/x.mp3",
                "https://user:pw@archive.org/download/x.mp3", "https://archive.org:8443/x.mp3", "javascript:alert(1)", "not a url"):
        outside.clear()
        page.evaluate("stopAudio()")
        page.evaluate("bad=>{state.selected={...state.selected,audioUrl:bad};}", bad)
        page.evaluate("play()"); page.wait_for_timeout(500)
        status = page.locator("#play-button").inner_text()
        desc = page.locator("#listening-description").inner_text()
        src = page.evaluate("document.querySelector('audio')?.getAttribute('src')")
        check(f"refuses {bad[:40]}", status == "Retry recording" and "not hosted on an approved archive" in desc and not src and outside == [], (status, desc[:80], src, outside))
    for good in ("https://archive.org/download/x/x.mp3", "https://ia800300.us.archive.org/1/items/x/x.mp3",
                 "https://www.radioheritage.com/otsw/x.mp3", "https://static1.squarespace.com/static/x.mp3"):
        ok = page.evaluate("u=>approvedAudioUrl(u)", good)
        expected = good.split("/")[2] in JS_HOSTS or good.split("/")[2].endswith(".archive.org")
        check(f"{'accepts' if expected else 'refuses (not approved in this build)'} {good[:45]}", ok is expected)
    check("no requests outside the site and the approved archives", outside == [], outside[:5])
    check("no page errors", not errors, errors)
    browser.close()
httpd.shutdown()
print(f"{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED'} at {width}px")
sys.exit(1 if failures else 0)
