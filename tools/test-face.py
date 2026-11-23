#!/usr/bin/env python3
"""Browser checks for the new-face release (release/heritage-hr64-face).

  cd release/heritage-hr64-face && python3 -m http.server 8766 &
  python3 tools/test-face.py [--chrome PATH] [--engine chromium|webkit] [--shots DIR]

--engine webkit runs the same checks in Playwright's WebKit (the Safari engine). This replaces the separate copy kept in
handoff/session-2026-11-19/test-helpers/test-face-webkit.py. In WebKit the two <select> lists log style-src CSP messages
(WebKit's own list styling); they are harmless and are reported apart from real page errors.
Checks added 2026-11-19 for Bill's answers: A2 clicks stop at power-off, A3 STANDBY lit dimly, A4 larger lettering at
760-1000 px, A6 reset keeps the band, A7/A9 kilocycles, KC details line, tab title, hidden band label gone, A14 no HTML
comments, C4 listener notes, C6 1969-1989 nameplate and borders file.

Archive audio is blocked in the test, so a captured recording shows LOADING or AUDIO ERROR; that is expected.
"""
import argparse, sys
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser(); ap.add_argument("--chrome"); ap.add_argument("--shots", default="/tmp/face-shots")
ap.add_argument("--url", default="http://127.0.0.1:8766/index.html"); ap.add_argument("--engine", default="chromium", choices=("chromium", "webkit"))
a = ap.parse_args()
import os; os.makedirs(a.shots, exist_ok=True)
fails = []
def check(ok, what):
    print(("PASS " if ok else "FAIL ") + what)
    if not ok: fails.append(what)

with sync_playwright() as p:
    b = p.webkit.launch() if a.engine == "webkit" else (p.chromium.launch(executable_path=a.chrome) if a.chrome else p.chromium.launch())
    WEBKIT_SELECT_CSP = lambda m: a.engine == "webkit" and "style-src" in m
    for width, height in ((1440, 1000), (390, 844)):
        ctx = b.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
        pg = ctx.new_page(); errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
        pg.on("requestfailed", lambda r: errors.append("request failed: " + r.url) if "archive.org" not in r.url else None)
        pg.route("**/*archive.org/**", lambda r: r.abort())
        pg.goto(a.url); pg.wait_for_function("document.querySelector('#catalog-status').textContent.includes('recordings')", timeout=15000)
        pg.wait_for_timeout(600)
        tag = f"[{width}]"
        check(pg.evaluate("!!window.HSFace && typeof state==='object'"), f"{tag} face bridge loaded")
        # Bill's answers, 2026-11-19: labels and wording (A7, A9, A14, C6)
        check(pg.title() == "Historic Shortwave", f"{tag} tab title is Historic Shortwave ({pg.title()})")
        check("<!--" not in pg.content(), f"{tag} no HTML comments in the page")
        check(not pg.evaluate("/1960-1989|1960 to 1989/.test(document.documentElement.outerHTML)"), f"{tag} recording years read 1969-1989 throughout the page")
        check(pg.evaluate("!document.querySelector('.receiver-description') && !document.body.innerHTML.includes('ARCHIVE BAND')"), f"{tag} hidden archive-band label removed")
        plate = pg.locator('#receiver .nameplate')
        check("1969-1989" in plate.inner_text() and "1969 to 1989" in plate.get_attribute('aria-label'), f"{tag} nameplate reads 1969-1989")
        vt = [pg.locator(s).get_attribute('aria-valuetext') for s in ('#tuning-knob', '#band-knob')]
        check(all(v.endswith("kilocycles") for v in vt), f"{tag} knob screen-reader values in kilocycles ({vt})")
        check(not pg.evaluate("/kilohertz|kHz|megahertz|MHz/.test(document.body.innerText)"), f"{tag} no kHz/MHz wording in the visible page")
        # A3: STANDBY is drawn dimly on the S-meter plate while the power is off
        # (the canvas is cleared whenever the scene is resized and repainted on the next frame, so allow up to 3 s)
        try: pg.wait_for_function("""(()=>{const c=document.getElementById('meter'),x=c.getContext('2d'),w=c.width,h=c.height;
          const d=x.getImageData(Math.round(w*.25),Math.round(h*.82),Math.round(w*.5),Math.round(h*.17)).data;let n=0;
          for(let i=0;i<d.length;i+=4)if(d[i]>70&&d[i]-d[i+2]>15)n++;return n>20;})()""", timeout=3000)
        except Exception: pass
        lit = pg.evaluate("""(()=>{const c=document.getElementById('meter'),x=c.getContext('2d'),w=c.width,h=c.height;
          const d=x.getImageData(Math.round(w*.25),Math.round(h*.82),Math.round(w*.5),Math.round(h*.17)).data;let n=0;
          for(let i=0;i<d.length;i+=4)if(d[i]>70&&d[i]-d[i+2]>15)n++;return n;})()""")
        check(lit > 20, f"{tag} STANDBY shown dimly on the S-meter while off ({lit} lettering pixels)")
        check(pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1"), f"{tag} no sideways overflow")
        check(pg.locator('#tuning-knob').get_attribute('aria-valuetext') is not None, f"{tag} tuning knob has a screen-reader value")
        pg.screenshot(path=f"{a.shots}/off-{width}.png", full_page=False)
        # power
        pg.click('#power-button'); pg.wait_for_timeout(500)
        check(pg.evaluate("state.power===true"), f"{tag} power on")
        st = pg.text_content('#receiver-status').strip()
        check(st in ("NO SIGNAL", "TUNED", "LOADING", "BUFFERING", "AUDIO ERROR", "PLAYING"), f"{tag} status word after power on ({st})")
        # keyboard tuning
        hz = pg.evaluate("state.hz"); pg.focus('#tuning-knob'); pg.keyboard.press('ArrowUp'); pg.wait_for_timeout(50)
        check(pg.evaluate("state.hz") == hz + 100, f"{tag} arrow key tunes 0.1 KC")
        pg.keyboard.press('PageUp'); pg.wait_for_timeout(50)
        check(pg.evaluate("state.hz") == hz + 5100, f"{tag} Page key tunes 5 KC")
        # drag tuning (slow): a quarter turn should move about 1.25 KC
        box = pg.locator('#tuning-knob').bounding_box(); cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2; r = box['width'] * .35
        import math
        hz = pg.evaluate("state.hz"); pg.mouse.move(cx + r, cy); pg.mouse.down()
        for i in range(1, 41):
            ang = i / 40 * math.pi / 2; pg.mouse.move(cx + r * math.cos(ang), cy + r * math.sin(ang)); pg.wait_for_timeout(16)
        pg.mouse.up(); pg.wait_for_timeout(100); moved = pg.evaluate("state.hz") - hz
        check(500 <= moved <= 2500, f"{tag} slow quarter turn clockwise tunes up about 1.25 KC ({moved} Hz)")
        # fast spin covers much more
        hz = pg.evaluate("state.hz"); pg.mouse.move(cx + r, cy); pg.mouse.down()
        for i in range(1, 13):
            ang = -i / 12 * math.pi * 1.5; pg.mouse.move(cx + r * math.cos(ang), cy + r * math.sin(ang)); pg.wait_for_timeout(8)
        pg.mouse.up(); pg.wait_for_timeout(1500); moved = hz - pg.evaluate("state.hz")
        check(moved > 10000, f"{tag} fast counter-clockwise spin tunes down quickly ({moved} Hz)")
        # band switching
        pg.focus('#band-knob'); pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(800)
        check(pg.evaluate("state.band") == '49m', f"{tag} band knob key selects 49 m")
        pg.evaluate("document.querySelector('details.alt-controls').open=true")
        pg.select_option('#band-select', '90m'); pg.wait_for_timeout(800)
        check(pg.evaluate("state.band") == '90m', f"{tag} band list selects 90 m")
        edges = pg.evaluate("[...document.querySelectorAll('.band-edges span')].map(s=>s.textContent)")
        check(edges == ['3150 KC', '3500 KC'], f"{tag} slider edges in KC ({edges})")
        # gain
        g = pg.evaluate("state.gain"); pg.focus('#gain-knob'); pg.keyboard.press('PageUp'); pg.wait_for_timeout(50)
        check(abs(pg.evaluate("state.gain") - min(1, g + .1)) < 1e-6, f"{tag} gain knob Page key")
        # slider and capture
        pg.evaluate("document.querySelector('details.alt-controls').open=true")
        target = pg.evaluate("state.records.find(r=>r.frequencyHz>=BANDS['90m'].minHz).frequencyHz")
        pg.evaluate(f"(()=>{{const s=document.getElementById('band-slider');s.value={target}/1000;s.dispatchEvent(new Event('input'))}})()")
        pg.wait_for_timeout(700)
        check(pg.evaluate("!!state.selected"), f"{tag} tuning to a recording captures it")
        st = pg.text_content('#receiver-status').strip()
        check(st in ("TUNED", "LOADING", "BUFFERING", "AUDIO ERROR", "PLAYING"), f"{tag} status with a recording ({st})")
        pg.wait_for_timeout(900)
        check(pg.evaluate("HSFace&&true") and pg.evaluate("state.selected!==null"), f"{tag} recording stays captured")
        pg.screenshot(path=f"{a.shots}/tuned-{width}.png", full_page=False)
        pg.screenshot(path=f"{a.shots}/full-{width}.png", full_page=True)
        # reveal
        pg.click('#reveal-button'); pg.wait_for_timeout(1200)
        check(pg.evaluate("!document.getElementById('reveal-panel').hidden"), f"{tag} reveal shows the station panel")
        det = pg.evaluate("[...document.querySelectorAll('#reveal-panel p')].map(p=>p.textContent).find(t=>t.includes(' · '))||''")
        check(" KC" in det and "kHz" not in det.split("labeled")[0], f"{tag} station details read KC ({det[:60]})")
        pg.locator('#reveal-panel').scroll_into_view_if_needed(); pg.wait_for_timeout(300)
        pg.screenshot(path=f"{a.shots}/reveal-{width}.png", full_page=False)
        # dialogs
        pg.click('#about-button'); check(pg.evaluate("document.getElementById('about-dialog').open"), f"{tag} field notes open"); pg.keyboard.press('Escape')
        pg.click('#about-project-button'); check(pg.evaluate("document.getElementById('about-project-dialog').open"), f"{tag} about opens"); pg.keyboard.press('Escape')
        # A2: mechanical clicks only while the power is on (count the click's filter nodes on the receiver's audio context)
        pg.evaluate("""(()=>{window.__clicks=0;const AC=state.ctx;if(!AC)return;const f=AC.createBiquadFilter.bind(AC);
          AC.createBiquadFilter=(...a)=>{window.__clicks++;return f(...a);};})()""")
        running = pg.evaluate("!!state.ctx && state.ctx.state==='running'")
        if running:
            pg.focus('#band-knob'); pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(800)
            check(pg.evaluate("window.__clicks") > 0, f"{tag} band detent clicks while on")
        else: check(False, f"{tag} receiver audio context running for the click checks")
        pg.click('#power-button'); pg.wait_for_timeout(300)
        before = pg.evaluate("window.__clicks")
        pg.focus('#band-knob'); pg.keyboard.press('ArrowLeft'); pg.wait_for_timeout(800)
        check(pg.evaluate("state.power===false") and pg.evaluate("window.__clicks") == before, f"{tag} no clicks after power-off (switch or band detent)")
        band = pg.evaluate("state.band")
        pg.click('#new-session'); pg.click('#confirm-reset'); pg.wait_for_timeout(300)
        check(pg.evaluate("state.power===false && state.revealed.size===0"), f"{tag} reset returns to a blind session")
        check(pg.evaluate("state.band") == band, f"{tag} reset keeps the current band ({band})")
        known = [e for e in errors if WEBKIT_SELECT_CSP(e)]; errors = [e for e in errors if not WEBKIT_SELECT_CSP(e)]
        if known: print(f"NOTE {tag} {len(known)} known WebKit select-list style-src message(s), not counted")
        check(not errors, f"{tag} no page errors {errors[:3]}")
        ctx.close()
    # A4: lettering enlarged between 760 and 1000 px wide (iPad portrait); unchanged at desktop width
    for width, want in ((900, 16), (1440, 12)):
        ctx = b.new_context(viewport={"width": width, "height": 1100}, device_scale_factor=1); pg = ctx.new_page()
        pg.route("**/*archive.org/**", lambda r: r.abort()); pg.goto(a.url); pg.wait_for_timeout(1200)
        size = pg.evaluate("parseFloat(getComputedStyle(document.querySelector('#tuning-label')).fontSize)")
        check(size == want, f"[{width}] engraved lettering {size}px (expect {want})")
        check(pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1"), f"[{width}] no sideways overflow")
        pg.screenshot(path=f"{a.shots}/lettering-{width}.png", full_page=False)
        ctx.close()
    # C4 and C6: release data
    ctx = b.new_context(); pg = ctx.new_page(); base = a.url.rsplit("/", 1)[0]
    notes = []
    for band in ("90m", "60m", "49m"):
        notes += [r.get("notes") or "" for r in pg.request.get(f"{base}/band-{band}.json").json()["recordings"]]
    bad = [n for n in notes if any(s in n for s in ("From user inventory", "added at user request", "Also posted as", "user inventory", "owner decision", "borderline", "one row only"))]
    check(not bad, f"listener notes free of project bookkeeping ({len(bad)} left)")
    check(not [n for n in notes if "kHz" in n.replace("Khz", "").split("https://")[0]], "project notes use KC, not kHz (archive URLs aside)")
    geo = pg.request.get(f"{base}/geo/period-borders-1969-1989.json")
    check(geo.ok and all(f["end"] >= "1969-01-01" for f in geo.json()["features"]), "borders file covers 1969-1989 only")
    check(pg.request.get(f"{base}/geo/period-borders-1960-1989.json").status == 404, "old 1960-1989 borders file not shipped")
    ctx.close()
    b.close()
print(f"\n{len(fails)} failed" if fails else "\nall passed"); sys.exit(1 if fails else 0)
