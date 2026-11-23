#!/usr/bin/env python3
"""Record what the receiver shows during a fixed 60 m script, for before/after comparison.

Usage (from the project root):
  python3 tools/regression-60m-snapshot.py OUT.json [--chrome PATH] [--app DIR] [--width PX]
  python3 tools/regression-60m-snapshot.py --compare BEFORE.json AFTER.json

The page is served from app/heritage-h60 on localhost. All external requests
(archive audio hosts, fonts) are blocked so runs are repeatable; recordings
therefore end in the receiver's normal playback-failure state.
Requires: pip install playwright (uses an installed Chromium via --chrome).
"""
import hashlib, json, sys, threading, functools, http.server, socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app" / "heritage-h60"
WIDTH = 1280

# The receiver accepts no typed input (Oct 29, 2026): the log, export and typed frequency
# box were removed, so the script tunes only with fixed controls. The readout is read from
# the new display, or from the old typed box when snapshotting an older copy.
IDS = ["receiver-status", "scope-label", "clip-id",
       "context-status", "listening-title", "listening-description", "recording-date",
       "recording-time", "guide-count", "catalog-status", "intro-description", "footer-mode",
       "review-count", "alternative-count", "reveal-panel",
       "static-description", "power-label", "play-button"]

SNAP_JS = """(ids) => {
  const $ = id => document.getElementById(id);
  const out = {};
  for (const id of ids) { const n = $(id); out[id] = n ? (n.value !== undefined && n.tagName !== 'BUTTON' && n.tagName !== 'OUTPUT' ? n.value : n.textContent) : null; }
  out.frequency = $('frequency-readout') ? $('frequency-readout').textContent : $('frequency-input').value;
  const q = s => [...document.querySelectorAll(s)].map(n => n.textContent);
  out.dialTop = q('.dial-top span'); out.dialBottom = q('.dial-bottom span'); out.bandEdges = q('.band-edges span');
  out.receiverDescription = document.querySelector('.receiver-description').childNodes[0].textContent + '|' + document.querySelector('.receiver-description small').textContent;
  const s = $('band-slider'); out.slider = [s.min, s.max, s.step, s.value];
  const k = $('tuning-knob'); out.knob = ['aria-valuemin','aria-valuemax','aria-valuenow','aria-valuetext'].map(a => k.getAttribute(a)).concat(k.style.transform);
  const g = [...$('guide-grid').children];
  out.guide = {count: g.length, first: g[0]?.textContent, last: g.at(-1)?.textContent,
    current: g.filter(b => b.classList.contains('current')).map(b => b.dataset.hz), disabled: g.filter(b => b.disabled).length,
    digest: g.map(b => b.dataset.hz + ':' + b.textContent).join('|')};
  out.altHidden = $('alternate-controls').hidden; out.altOptions = [...$('recording-select').options].map(o => o.textContent + '=' + o.value);
  out.altValue = $('recording-select').value; out.revealHidden = $('reveal-panel').hidden;
  out.reviewHidden = $('review-queue').hidden; out.reviewRows = $('review-body').children.length;
  out.reviewDigest = $('review-body').textContent;
  out.lamp = $('signal-lamp').className; out.power = $('power-button').getAttribute('aria-checked');
  out.disabled = ['play-button','restart-button','reveal-button','previous-recording','next-recording'].map(id => $(id).disabled);
  out.catalogSelect = [$('catalog-select').value, $('catalog-select').disabled];
  out.canvases = ['band-canvas','meter-canvas'].map(id => $(id).toDataURL());
  return out;
}"""

STEPS = [
    ("load", []),
    ("tune 4905", [("slider", "4905")]),
    ("tune 4845", [("slider", "4845")]),
    ("tune 4990.5", [("slider", "4990.5")]),
    ("plus x3 fine", [("click", "#tune-plus"), ("click", "#tune-plus"), ("click", "#tune-plus")]),
    ("coarse minus", [("click", "#step-coarse"), ("click", "#tune-minus"), ("click", "#step-fine")]),
    ("knob End", [("focus", "#tuning-knob"), ("press", "#tuning-knob", "End")]),
    ("knob Home", [("press", "#tuning-knob", "Home")]),
    ("knob arrows", [("press", "#tuning-knob", "ArrowUp"), ("press", "#tuning-knob", "PageUp")]),
    ("slider 5000", [("slider", "5000")]),
    ("guide first", [("click", "#guide-grid button:first-child")]),
    ("full inventory", [("select", "#catalog-select", "full"), ("wait", 600)]),
    ("full 4845", [("slider", "4845")]),
    ("next alt x2", [("click", "#next-recording"), ("click", "#next-recording")]),
    ("previous alt", [("click", "#previous-recording")]),
    ("back to pilot", [("select", "#catalog-select", "pilot"), ("wait", 400)]),
    ("full again (choice kept)", [("select", "#catalog-select", "full"), ("wait", 400)]),
    ("guide last", [("click", "#guide-grid button:last-child")]),
    ("reveal", [("click", "#reveal-button")]),
    ("tune 4845", [("slider", "4845")]),
    ("power on", [("click", "#power-button"), ("wait", 1800)]),
    ("power off", [("click", "#power-button"), ("wait", 300)]),
    ("reset", [("click", "#new-session"), ("click", "#confirm-reset"), ("wait", 300)]),
    ("after reset pilot", [("select", "#catalog-select", "pilot"), ("wait", 400)]),
]


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = functools.partial(Quiet, directory=str(APP))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def run(out, chrome):
    from playwright.sync_api import sync_playwright
    httpd = serve(); port = httpd.server_address[1]
    snaps = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome, args=["--autoplay-policy=no-user-gesture-required"])
        page = browser.new_page(viewport={"width": WIDTH, "height": 900})
        page.add_init_script("Date.now = (() => { const t = Date.UTC(2026, 9, 20, 16); return () => t; })();"
                             "const _D = Date; globalThis.Date = class extends _D { constructor(...a){ super(...(a.length?a:[Date.now()])); } static now(){ return _D.UTC(2026, 9, 20, 16); } };")
        page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(f"http://127.0.0.1:{port}") else r.abort())
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/index.html"); page.wait_for_timeout(800)
        for name, actions in STEPS:
            for a in actions:
                kind = a[0]
                if kind == "fill": page.fill(a[1], a[2])
                elif kind == "press": page.press(a[1], a[2])
                elif kind == "click": page.eval_on_selector(a[1], "n => n.click()")  # some controls sit in collapsed panels
                elif kind == "focus": page.focus(a[1])
                elif kind == "select": page.select_option(a[1], a[2])
                elif kind == "wait": page.wait_for_timeout(a[1])
                elif kind == "slider": page.eval_on_selector("#band-slider", "(n,v)=>{n.value=v;n.dispatchEvent(new Event('input',{bubbles:true}));}", a[1])
            page.wait_for_timeout(120)
            snap = page.evaluate(SNAP_JS, IDS)
            snap["canvases"] = [hashlib.sha256(c.encode()).hexdigest()[:16] for c in snap["canvases"]]
            snaps.append({"step": name, **snap})
        browser.close()
    httpd.shutdown()
    Path(out).write_text(json.dumps({"errors": errors, "steps": snaps}, ensure_ascii=False, indent=1))
    print(f"{len(snaps)} steps recorded, {len(errors)} page errors -> {out}")


def compare(a, b):
    A, B = json.loads(Path(a).read_text()), json.loads(Path(b).read_text())
    diffs = []
    if A["errors"] != B["errors"]: diffs.append(("page errors", A["errors"], B["errors"]))
    for sa, sb in zip(A["steps"], B["steps"]):
        for k in sorted(set(sa) | set(sb)):
            if sa.get(k) != sb.get(k): diffs.append((sa["step"], k, sa.get(k), sb.get(k)))
    if len(A["steps"]) != len(B["steps"]): diffs.append(("step count", len(A["steps"]), len(B["steps"])))
    for d in diffs: print("DIFF", json.dumps(d, ensure_ascii=False)[:600])
    print("IDENTICAL" if not diffs else f"{len(diffs)} differences", f"across {len(A['steps'])} steps")
    return 1 if diffs else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--compare":
        sys.exit(compare(args[1], args[2]))
    def option(name):
        if name in args:
            i = args.index(name); value = args[i + 1]; del args[i:i + 2]; return value
    chrome = option("--chrome")
    app_dir, width = option("--app"), option("--width")
    if app_dir: APP = Path(app_dir).resolve()
    if width: WIDTH = int(width)
    run(args[0], chrome)
