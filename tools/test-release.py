#!/usr/bin/env python3
"""Checks for the release build in release/heritage-hr64 (built by tools/build-release.py).

  python3 tools/test-release.py --chrome PATH [--width PX] [--shots DIR]
Data: the release holds exactly the Archive.org recordings cleared in the rights table, each with a credit
and a map entry. Page: no test-catalog switch or review table; every band loads its single catalog; every
dial position plays a release recording; Reveal shows the recordist credit. External hosts are blocked.
"""
import csv, functools, http.server, json, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from receiver_tuning import tune_to

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "release" / "heritage-hr64"
args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
chrome, width, shots = opt("--chrome"), int(opt("--width", 1280)), opt("--shots")
failures = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[:300]}"))
    if not cond: failures.append(name)

rights = list(csv.DictReader(open(ROOT / "data/release/recording-rights-2026-10-20.csv", encoding="utf-8")))
expected = {r["Audio URL"] for r in rights if r["Audio host"] == "Archive.org" and r["Status"].startswith(("Licensed:", "Permission granted:"))}
excluded = {r["Audio URL"] for r in rights} - expected
cats = {b: json.loads((APP / f"band-{b}.json").read_text()) for b in ("90m", "60m", "49m")}
recs = [r for c in cats.values() for r in c["recordings"]]
urls = [r["audioUrl"] for r in recs]
credits = json.loads((APP / "credits.json").read_text())["credits"]
geo = json.loads((APP / "geo/reveal-geography.json").read_text())["entries"]
check("release holds exactly the cleared Archive.org recordings", set(urls) == expected and len(urls) == len(set(urls)) == 670, (len(urls), len(expected)))
check("no excluded recording URL anywhere in the build", not any(u in (APP / f).read_text() for f in ("band-90m.json", "band-60m.json", "band-49m.json", "credits.json") for u in list(excluded)[:400]))
check("every recording is on archive.org", all(u.startswith("https://archive.org/") for u in urls))
check("no review-only entries", all(r.get("testEligible") is not False for r in recs))
check("every recording has a credit and a map entry", all(r["id"] in credits and r["id"] in geo for r in recs))
check("credits and map hold nothing extra", set(credits) == set(geo) == {r["id"] for r in recs}, (len(credits), len(geo)))
check("pilot and test catalogs removed", not (APP / "pilot.json").exists() and not (APP / "full-inventory.json").exists())
counts = {b: (len(c["recordings"]), len({r["frequencyHz"] for r in c["recordings"]})) for b, c in cats.items()}

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(APP)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{httpd.server_address[1]}"

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome)
    page = browser.new_context(viewport={"width": width, "height": 900}, reduced_motion="reduce").new_page()
    errors, csp = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: csp.append(m.text) if "Content Security Policy" in m.text else None)
    page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(BASE) else route.abort())
    page.goto(BASE + "/index.html"); page.wait_for_function("state.records.length > 0", timeout=15000)
    ui = page.evaluate("""() => ({sel: !!document.getElementById('catalog-select'), rq: !!document.getElementById('review-queue'),
      text: document.body.innerText, status: document.getElementById('catalog-status').textContent, footer: document.getElementById('footer-mode').textContent,
      guide: document.getElementById('guide-count').textContent, band: state.band, mode: state.mode})""")
    check("no test-catalog switch", not ui["sel"])
    check("no review-only table", not ui["rq"])
    check("no pilot, baseline or test-mode wording", not any(w in ui["text"].lower() for w in ("twenty", "pilot", "test catalog", "full inventory", "curator preview")), [w for w in ("twenty","pilot","test catalog","full inventory","curator preview") if w in ui["text"].lower()])
    check("starts on 60 m with the release catalog", ui["band"] == "60m" and ui["mode"] == "full" and ui["status"] == f"{counts['60m'][0]} recordings on 60 m", ui)
    check("footer names the collection", ui["footer"] == "HISTORIC SHORTWAVE / 60 METER COLLECTION", ui["footer"])
    for band in ("90m", "49m", "60m"):
        tune_to(page, {"90m": 3300, "60m": 4900, "49m": 6100}[band], wait_ms=300)
        page.wait_for_function("b => state.band === b && state.records.length > 0", arg=band, timeout=10000)
        st = page.evaluate("""() => ({n: state.records.length, g: state.groups.length, status: document.getElementById('catalog-status').textContent,
          guide: document.getElementById('guide-count').textContent})""")
        check(f"{band} loads {counts[band][0]} recordings at {counts[band][1]} positions",
              st["n"] == counts[band][0] and st["g"] == counts[band][1] and st["status"] == f"{counts[band][0]} recordings on {band.replace('m',' m')}" and st["guide"] == f"{counts[band][1]} recording positions", st)
        bad = page.evaluate("""() => { const out = [];
          for (const g of state.groups) { tune(g.hz); if (!state.selected || !g.records.some(r => r.id === state.selected.id)) out.push(g.hz); } return out; }""")
        check(f"{band}: every dial position selects a release recording", not bad, bad[:5])
    # Between recordings: static is audible and Loop is disabled (powered on, real seasonal files).
    page.evaluate("document.getElementById('power-button').click()"); page.wait_for_timeout(300)
    for band in ("60m", "90m", "49m"):
        hzs = sorted({r["frequencyHz"] for r in cats[band]["recordings"]})
        gap = max(zip(hzs, hzs[1:]), key=lambda a: a[1] - a[0]); gap_khz = round((gap[0] + gap[1]) / 2000, 1)
        tune_to(page, gap_khz, wait_ms=2500)
        st = page.evaluate("""() => ({sel: state.selected && state.selected.id, target: seasonalNoise.targetGain, status: seasonalNoise.status,
          loop: document.getElementById('loop-button').disabled})""")
        check(f"{band}: static audible and Loop disabled at {gap_khz} kHz", st["sel"] is None and st["target"] > 0 and st["loop"] is True, st)
    page.evaluate("document.getElementById('power-button').click()"); page.wait_for_timeout(200)
    # Reveal a Dave Valko recording: R. Lesotho, 4800 kHz, 1981-03-14.
    lesotho = next(r for r in cats["60m"]["recordings"] if r["frequencyHz"] == 4800000 and r["date"] == "1981-03-14")
    page.evaluate("document.getElementById('power-button').click()")
    tune_to(page, 4800, wait_ms=200)
    page.evaluate("""id => { const s = document.getElementById('recording-select'); if (state.selected?.id !== id) { s.value = id; s.dispatchEvent(new Event('change')); } }""", lesotho["id"])
    page.wait_for_timeout(200)
    page.evaluate("document.getElementById('reveal-button').click()")
    page.wait_for_selector("#reveal-panel [data-testid=text-recording-credit]", timeout=5000)
    page.wait_for_selector("[data-testid=reveal-map] svg", timeout=10000)
    rv = page.evaluate("() => ({credit: document.querySelector('#reveal-panel [data-testid=text-recording-credit]').innerText, panel: document.getElementById('reveal-panel').innerText})")
    check("Reveal shows the Valko credit", "Recorded by Dave J. Valko" in rv["credit"] and "Archive.org" in rv["credit"], rv["credit"])
    check("Reveal shows the station", "Lesotho" in rv["panel"], rv["panel"][:200])
    if shots:
        page.wait_for_timeout(400); page.screenshot(path=f"{shots}/release-{width}-reveal.png", full_page=True)
        page.evaluate("window.scrollTo(0,0)"); page.screenshot(path=f"{shots}/release-{width}-top.png")
    check("no page errors", not errors, errors[:3])
    check("no security-policy violations", not csp, csp[:3])
    browser.close()
httpd.shutdown()
print(f"{'ALL PASS' if not failures else str(len(failures)) + ' FAILED'} at {width} px")
sys.exit(1 if failures else 0)
