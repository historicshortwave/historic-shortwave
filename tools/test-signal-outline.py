#!/usr/bin/env python3
"""Browser checks for the red signal outline on the tuned-frequency readout (plan phase 4).

The outline must be lit exactly when the S-meter is raised: receiver on and a
recording captured. This sweeps every 0.1 kHz dial step on all three bands
(full catalogs), with the receiver on and off, and checks the SIGNAL tab too.
Run from the project root:  python3 tools/test-signal-outline.py --chrome PATH [--width PX]

New 3D receiver (HR64_APP=release/heritage-hr64-face; updated 2026-11-20 at Bill's request): the face has no red
readout outline or SIGNAL tab (both sit in its hidden, aria-hidden compatibility block); the S-meter needle alone shows
signal. So on the face these checks read the needle off the drawn meter instead: "lit" means the needle stands above
0.2 of full scale (it rests at about 0.07 with the power on and no signal, and below zero when off). The full sweeps
compare the capture condition at every dial step and read the needle at a sample of captured and empty steps.
The face's 60 m release catalog is already the full list, so the baseline/full selector is skipped there.
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
# Needle position (0 to 1 of full scale) read from the drawn S-meter: the darkest ray in the outer part of the arc,
# using the same geometry as face.js drawMeter().
NEEDLE = """() => { const c = document.getElementById('meter'), x = c.getContext('2d'), w = c.width, h = c.height;
  const d = x.getImageData(0, 0, w, h).data, cx = w / 2, cy = h * .98, r = Math.min(h * .8, w * .5);
  let best = null, bestDark = -1;
  for (let v = -0.04; v <= 1.05; v += 0.005) { const a = -Math.PI / 2 + (v - .5) * 1.6; let dark = 0, n = 0;
    for (let t = .72; t <= .95; t += .01) { const px = Math.round(cx + Math.cos(a) * r * t), py = Math.round(cy + Math.sin(a) * r * t);
      if (px < 0 || py < 0 || px >= w || py >= h) continue; const i = (py * w + px) * 4; dark += 255 - (d[i] + d[i + 1] + d[i + 2]) / 3; n++; }
    if (n && dark / n > bestDark) { bestDark = dark / n; best = v; } }
  return best; }"""
# Every dial step on the current band, swept upward as SWEEP does: whether a recording is captured there, from the
# loaded catalog. A recording already captured is held a little past its own window while the dial moves away
# (findGroup's retain radius), so the previous step's group is passed along, as tune() does.
CAPTURE_MAP = """() => { const [min, max] = bounds(), out = []; let cur = null;
  for (let hz = min; hz <= max; hz += 100) { cur = ReceiverCatalog.findGroup(state.groups, hz, cur?.hz); out.push([hz, !!cur]); } return out; }"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


httpd = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(APP)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{httpd.server_address[1]}"
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))
    if not cond: failures.append(name)


SWEEP = """() => {
  // Calls the receiver's own tune(); compares the outline with the S-meter condition.
  const w = document.getElementById('digital-window'), tab = document.getElementById('signal-legend');
  const [min, max] = bounds(); let steps = 0, lit = 0, mismatches = [];
  for (let hz = min; hz <= max; hz += 100) {
    tune(hz); steps++;
    const meterUp = !!(state.power && state.selected?.id), on = w.classList.contains('has-signal');
    if (on) lit++;
    if (on !== meterUp || tab.hidden === on) mismatches.push(hz);
  }
  clearTimeout(state.timer);
  return {steps, lit, mismatches: mismatches.slice(0, 10), mismatchCount: mismatches.length};
}"""
OUTLINE = "() => ({on: document.getElementById('digital-window').classList.contains('has-signal'), tab: !document.getElementById('signal-legend').hidden, meter: !!(state.power && state.selected?.id)})"

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome)
    page = browser.new_context(viewport={"width": width, "height": 900}, **({"reduced_motion": "reduce"} if FACE else {})).new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(BASE) else r.abort())
    page.goto(BASE + "/index.html"); page.wait_for_timeout(700)
    wait = lambda ms=400: page.wait_for_timeout(ms)
    def o():
        if not FACE: return page.evaluate(OUTLINE)
        wait(350)   # let the needle settle (reduced motion: about 50 ms time constant)
        up = page.evaluate(NEEDLE) > 0.2
        return {"on": up, "tab": up, "meter": page.evaluate("!!(state.power && state.selected?.id)")}

    check("off at load (receiver standby, on a recording)", o() == {"on": False, "tab": False, "meter": False}, o())
    if FACE:
        check("SIGNAL tab is hidden from screen readers (inside the face's aria-hidden compatibility block)",
              page.evaluate("!!document.getElementById('signal-legend').closest('[aria-hidden=true]')"))
    else:
        check("SIGNAL tab is hidden from screen readers", page.get_attribute("#signal-legend", "aria-hidden") == "true")
    page.click("#power-button"); wait()
    check("lights when power goes on at 4900.0 kHz", o() == {"on": True, "tab": True, "meter": True}, o())
    off_khz = 4900.5
    if FACE:   # the release catalog's groups near 4900 are closer together, so its capture window there is narrower
        # 2026-11-27: a 4899.8 kHz recording (clip 398) leaves 4900.0 a capture radius under one 0.1 kHz dial step, so the
        # check uses the first group from 4900 kHz up whose window reaches at least one step off center.
        off_khz = page.evaluate("(() => { const g = state.groups.find(x => x.hz >= 4900000 && x.radius >= 100); return (g.hz + Math.floor(Math.min(500, g.radius) / 100) * 100) / 1000; })()")
    tune_to(page, str(off_khz)); wait(150)
    check(f"still lit {off_khz - 4900:.1f} kHz off-center, inside the capture window", o()["on"] and o()["meter"], o())
    gap_khz = 4902
    if FACE:   # 4902.1 kHz is a recording in the release catalog; use the first empty step above 4902
        gap_khz = page.evaluate("(() => { for (let hz = 4902000; ; hz += 100) if (!ReceiverCatalog.findGroup(state.groups, hz, state.group?.hz)) return hz / 1000; })()")
    tune_to(page, str(gap_khz)); wait(150)
    check(f"off between recordings ({gap_khz:.1f} kHz)", o() == {"on": False, "tab": False, "meter": False}, o())
    tune_to(page, "4900"); wait(900)
    st = page.text_content("#receiver-status")
    check("stays lit when the recording cannot play", o()["on"] and st == ("AUDIO ERROR" if FACE else "PLAYBACK UNAVAILABLE"), (o(), st))
    page.click("#power-button"); wait(150)
    check("goes off with the power", o() == {"on": False, "tab": False, "meter": False}, o())

    # Shared frequency: moving between alternatives keeps the outline.
    if not FACE: page.select_option("#catalog-select", "full"); wait(600)
    page.click("#power-button"); wait(200)
    tune_to(page, "4845"); wait(150)
    lit = [o()["on"]]
    for _ in range(3): page.eval_on_selector("#next-recording", "n => n.click()"); wait(120); lit.append(o()["on"])
    check("lit throughout alternatives at 4845 kHz", all(lit), lit)

    # Full sweeps, power on and off, every band.
    for band in ["60m", "90m", "49m"]:
        page.evaluate(f"selectBand('{band}')"); wait(700)
        if band == "60m" and not FACE: page.select_option("#catalog-select", "full"); wait(500)
        for power in (True, False):
            if page.evaluate("state.power") != power: page.click("#power-button"); wait(150)
            if FACE:
                cap = page.evaluate(CAPTURE_MAP)
                r = page.evaluate(SWEEP.replace("w.classList.contains('has-signal')", "meterUp").replace("tab.hidden === on", "false"))
                check(f"{band} sweep, power {'on' if power else 'off'}: S-meter condition follows capture at all {r['steps']} steps",
                      r["steps"] == len(cap) and r["lit"] == (sum(c for _, c in cap) if power else 0), (r, sum(c for _, c in cap)))
                hit = [hz for hz, c in cap if c]; miss = [hz for hz, c in cap if not c]
                sample = [(hz, True) for hz in hit[::max(1, len(hit) // 8)][:8]] + [(hz, False) for hz in miss[::max(1, len(miss) // 8)][:8]]
                bad = []
                for hz, captured in sample:
                    # The sweep map carries the retain radius of the step below; a direct jump does not (2026-11-27: 49M-0272 at
                    # 6187.8 kHz holds 6188.7 only on the upward sweep). Expect what tune() itself will find from the current group.
                    captured = page.evaluate(f"!!ReceiverCatalog.findGroup(state.groups, {hz}, state.group?.hz)")
                    page.evaluate(f"tune({hz})"); up = o()["on"]
                    if up != (captured and power): bad.append((hz, captured, up))
                check(f"{band} needle, power {'on' if power else 'off'}: {'up only where captured' if power else 'never up'} ({len(sample)} sampled steps)", not bad, bad)
                continue
            r = page.evaluate(SWEEP)
            if power:
                check(f"{band} sweep, power on: outline matches S-meter at all {r['steps']} steps ({r['lit']} lit)", r["mismatchCount"] == 0 and r["lit"] > 0, r)
            else:
                check(f"{band} sweep, power off: never lit ({r['steps']} steps)", r["mismatchCount"] == 0 and r["lit"] == 0, r)

    # Band change while powered: lit on the new band's default recording, off if none.
    if not page.evaluate("state.power"): page.click("#power-button"); wait(150)
    tune_to(page, "3302"); wait(700)
    check("typed 3302 kHz (no recording) switches band with outline off", page.text_content(".dial-top span") == "90 METERS" and not o()["on"], o())
    page.evaluate("state.bandHz.set('60m', 4900000)")  # the 60 m sweep left it at 5085 kHz, where there is no recording
    page.focus("#band-knob"); page.keyboard.press("ArrowRight"); wait(700)
    check("powered switch to 60 m at a recording (4900 kHz) lights it", o() == {"on": True, "tab": True, "meter": True}, o())
    page.keyboard.press("ArrowRight"); wait(700)
    check("powered switch to 49 m (left at 6350 kHz by the sweep, no recording) follows the meter", o()["on"] == o()["meter"], o())

    check("no page errors", not errors, errors)
    browser.close()
httpd.shutdown()
print(f"{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED'} at {width}px")
sys.exit(1 if failures else 0)
