#!/usr/bin/env python3
"""Browser checks for the recordist credit line under the revealed station details.

  python3 tools/test-recording-credits.py --chrome PATH [--width PX]
External hosts are blocked; recordings end in the normal playback-unavailable state.

New 3D receiver (HR64_APP=release/heritage-hr64-face; updated 2026-11-20 at Bill's request): the release ships
band-60m.json in place of full-inventory.json, shows frequencies in KC, and holds 550 of the inventory's recordings.
Sample recordings that are not in the release are replaced by release recordings picked from the release data for
the same purpose (the first recording of each band and credit source; a label written in MHz, one written with a
comma, and one plain). The release has no Radio Heritage recordings (every credit names its recordist) and no
separate 60 m baseline list, so those two checks are reported as notes there.
"""
import functools, http.server, json, socketserver, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
APP = Path(__import__("os").environ["HR64_APP"]).resolve() if __import__("os").environ.get("HR64_APP") else ROOT / "app" / "heritage-h60"
args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
chrome, width = opt("--chrome"), int(opt("--width", 1280))
FACE = (APP / "face.js").exists()   # the new 3D receiver (release/heritage-hr64-face)
UNIT = "KC" if FACE else "kHz"
CREDITS = json.loads((APP / "credits.json").read_text())["credits"]
RECS = {}
for f in ["band-60m.json" if FACE else "full-inventory.json", "band-90m.json", "band-49m.json"]:
    for r in json.loads((APP / f).read_text())["recordings"]:
        RECS[r["id"]] = r
        if FACE: r["band"] = f[5:8]   # release band files do not repeat the band on each recording


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(APP)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{httpd.server_address[1]}"
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))
    if not cond: failures.append(name)


def rid(band, inv):
    return next(k for k, r in RECS.items() if (r.get("band") or "60m") == band and str(r["inventoryId"]) == str(inv))


GOTO = """async ([band, id, hz]) => {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  if (state.band !== band) { selectBand(band); for (let i = 0; i < 60 && state.band !== band; i++) await wait(50); }
  if (band === '60m' && state.mode !== 'full') { const s = document.getElementById('catalog-select'); s.value = 'full'; s.dispatchEvent(new Event('change')); for (let i = 0; i < 60 && state.mode !== 'full'; i++) await wait(50); }
  tune(hz); await wait(50);
  const sel = document.getElementById('recording-select');
  if (state.selected?.id !== id) { sel.value = id; sel.dispatchEvent(new Event('change')); await wait(50); }
  return state.selected?.id;
}"""
CREDIT = r"""() => { const p = document.querySelector('#reveal-panel [data-testid=text-recording-credit]'); if (!p) return null;
  const prev = p.previousElementSibling;
  return { text: p.innerText.trim(), links: [...p.querySelectorAll('a')].map(a => [a.textContent, a.href, a.target, a.rel]),
    afterDetails: !!prev && prev.tagName === 'P' && / (kHz|KC)( \(labeled “[^”]*”\))? · /.test(prev.textContent), hidden: document.getElementById('reveal-panel').hidden }; }"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome)
    page = browser.new_context(viewport={"width": width, "height": 900}, reduced_motion="reduce").new_page()
    errors, credit_requests, block = [], [], {"credits": False}
    page.on("pageerror", lambda e: errors.append(str(e)))
    def route(r):
        url = r.request.url
        if not url.startswith(BASE): return r.abort()
        if url.endswith("/credits.json"):
            credit_requests.append(url)
            if block["credits"]: return r.abort()
        return r.continue_()
    page.route("**/*", route)
    page.goto(BASE + "/index.html"); page.wait_for_timeout(600)
    reveal = lambda: page.evaluate("document.getElementById('reveal-button').click()")
    def go(band, inv):
        k = rid(band, inv); page.evaluate(GOTO, [band, k, RECS[k]["frequencyHz"]]); return k

    # Baseline 60 m (default) before any reveal: nothing about credits is loaded or shown.
    page.evaluate("tune(4800000)"); page.wait_for_timeout(200)
    check("no credit request before the first reveal", credit_requests == [], credit_requests)
    check("no credit line while the station is hidden", page.evaluate(CREDIT) is None)

    # Failure path, then retry on the next reveal.
    block["credits"] = True
    k = go("60m", 10); reveal(); page.wait_for_timeout(500)
    c = page.evaluate(CREDIT)
    check("credit load failure says unavailable", c and c["text"] == "Recording credit unavailable right now.", c)
    block["credits"] = False
    page.evaluate("document.getElementById('restart-button')"); go("60m", 20); go("60m", 10); reveal(); page.wait_for_timeout(600)
    c = page.evaluate(CREDIT)
    check("clip 10 credit after retry: Dan Robinson, SRAA, CC BY-NC 3.0",
          c and c["text"] == "Recorded by Dan Robinson · Shortwave Radio Audio Archive, via Archive.org · CC BY-NC 3.0", c)
    check("credit sits directly under the station details", c and c["afterDetails"], c)
    check("license link opens the license in a new tab", c and c["links"] == [["CC BY-NC 3.0", "https://creativecommons.org/licenses/by-nc/3.0/", "_blank", "noopener noreferrer"]], c)

    # Samples on every band and every source type.
    samples = [("60m", 117), ("60m", 168), ("60m", 169), ("60m", 275), ("90m", "90M-0001"), ("90m", "90M-0100"),
               ("49m", "49M-0220"), ("49m", "49M-0001"), ("49m", "49M-0266")]
    if FACE:   # keep the samples that are in the release, then add the first recording of each band and credit source
        have = {(r["band"], str(r["inventoryId"])) for r in RECS.values()}
        samples = [x for x in samples if (x[0], str(x[1])) in have]; seen = set()
        for k, r in RECS.items():
            key = (r["band"], CREDITS[k].get("via"))
            if key not in seen:
                seen.add(key)
                if (r["band"], r["inventoryId"]) not in samples: samples.append((r["band"], r["inventoryId"]))
    for band, inv in samples:
        k = go(band, inv); reveal(); page.wait_for_timeout(250)
        exp = CREDITS[k]
        want = exp["credit"] + (" · " + exp["via"] if exp.get("via") else "") + (" · " + exp["license"]["label"] if exp.get("license") else "")
        c = page.evaluate(CREDIT)
        check(f"{band} {inv}: {exp['credit']}", c and c["text"] == want and c["afterDetails"], (c, want))
    # Frequency labels written in MHz or with commas show the dial kHz, with the archive label quoted once.
    freq_cases = [("49m", "49M-0079", " · 6010 kHz (labeled “6.010MHz”) · "), ("90m", "90M-0050", " · 3290 kHz (labeled “3,290 khz”) · "),
                  ("49m", "49M-0001", None)]
    if FACE:   # 49M-0079 and 49M-0001 are not in the release: a label in MHz, the comma label, and a plain label
        plain = next(r for r in RECS.values() if r["band"] == "49m" and str(r.get("frequencyLabel") or "").strip() == str(r["frequencyHz"] // 1000))
        freq_cases = [("49m", "49M-0042", " · 5975 KC (labeled “5.975 MHz”) · "), ("90m", "90M-0050", " · 3290 KC (labeled “3,290 khz”) · "),
                      ("49m", plain["inventoryId"], None)]
    for band, inv, want in freq_cases:
        k = go(band, inv); reveal(); page.wait_for_timeout(200)
        d = page.evaluate("document.querySelector('#reveal-panel h3 + p, #reveal-panel p').textContent")
        if want is None:
            want = f" · {RECS[k]['frequencyHz'] // 1000} {UNIT} · "
        check(f"{band} {inv} frequency shows {want.strip(' ·')}", want in d and "MHz kHz" not in d and "khz kHz" not in d, d)
    if FACE:
        unnamed = [k for k in RECS if "not named" in CREDITS[k]["credit"]]
        print(f"NOTE no release recording comes from Radio Heritage; credits without a named recordist: {len(unnamed)}")
    else:
        check("Radio Heritage recording without a named recordist says so",
              CREDITS[rid("49m", "49M-0001")]["credit"] == "Recordist not named by the source")

    # Concealment: the credit never names the station, and hides with the station.
    hidden_inv = "90M-0004"
    if FACE:   # 90M-0004 is not in the release: the first 90 m recording this test has not revealed
        hidden_inv = next(r["inventoryId"] for r in RECS.values() if r["band"] == "90m" and ("90m", r["inventoryId"]) not in samples)
    k = go("90m", hidden_inv); page.wait_for_timeout(150)
    c = page.evaluate(CREDIT)
    check("credit hidden on an unrevealed recording", c is None, c)
    leaks = [k for k, cr in CREDITS.items() if k in RECS and RECS[k]["station"].lower() in (cr["credit"] + " " + (cr.get("via") or "")).lower()]
    check("no credit text contains its own station name", leaks == [], leaks[:5])
    if FACE:
        check(f"credits cover every release recording ({len(RECS)})", all(k in CREDITS for k in RECS))
    else:
        check("credits cover every tunable recording and the baseline", all(k in CREDITS for k, r in RECS.items() if r.get("testEligible", True) and r.get("frequencyHz")) and "rec-000024" in CREDITS)
    check("credits file loaded once after the retry", len(credit_requests) == 2, credit_requests)
    check("no page errors", not errors, errors)
    browser.close()
httpd.shutdown()
print(f"{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED'} at {width}px")
sys.exit(1 if failures else 0)
