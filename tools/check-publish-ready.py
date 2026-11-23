#!/usr/bin/env python3
"""Pre-publish check for the receiver folder. Run before every preview publish.
Also (since 2026-10-29): no typed input on the page. (Since 2026-10-21): self-hosted fonts, a privacy scan of the published folder, and agreement between the
Content Security Policy media-src list and APPROVED_AUDIO_HOSTS in app.js.

  python3 tools/check-publish-ready.py
Fails if any file under app/heritage-h60 is still a Git LFS pointer placeholder (the project copy can hold
placeholders for large files until they are hydrated with `pplx project files hydrate-lfs`), or if a seasonal
noise file listed in the manifest is missing or is not an MP3.
"""
import json, os, sys
from pathlib import Path

# Set HR64_APP to check another folder, e.g. the release build: HR64_APP=release/heritage-hr64
APP = Path(os.environ["HR64_APP"]).resolve() if os.environ.get("HR64_APP") else Path(__file__).resolve().parent.parent / "app" / "heritage-h60"
problems = []
for f in sorted(APP.rglob("*")):
    if f.is_file() and f.stat().st_size < 1024 and f.read_bytes().startswith(b"version https://git-lfs.github.com/spec/"):
        problems.append(f"LFS placeholder, not real content: {f.relative_to(APP)}")
seasonal = APP / "audio" / "seasonal"
names = set()
def walk(o):
    if isinstance(o, dict): [walk(v) for v in o.values()]
    elif isinstance(o, list): [walk(v) for v in o]
    elif isinstance(o, str) and o.endswith(".mp3") and "/" not in o and " " not in o: names.add(o)
walk(json.loads((seasonal / "manifest.json").read_text()))
for n in sorted(names):
    p = seasonal / n
    b = p.read_bytes()[:3] if p.exists() else b""
    if not p.exists(): problems.append(f"missing seasonal file: {n}")
    elif not (b == b"ID3" or b[:1] == b"\xff"): problems.append(f"seasonal file is not an MP3: {n}")
# Self-hosted fonts (since 2026-10-21): every file named in fonts.css must exist and be a real WOFF2 file,
# and the page must not load anything from a font service.
import re
fonts_css = APP / "vendor" / "fonts" / "fonts.css"
font_files = re.findall(r"url\(\./([^)]+\.woff2)\)", fonts_css.read_text()) if fonts_css.exists() else []
# New-face build (2026-11-16): Barlow Semi Condensed is listed in its own barlow.css; check those files the same way.
barlow_css = APP / "vendor" / "fonts" / "barlow.css"
if barlow_css.exists(): font_files += re.findall(r"url\(\./([^)]+\.woff2)\)", barlow_css.read_text())
if not font_files: problems.append("vendor/fonts/fonts.css missing or lists no fonts")
for n in sorted(set(font_files)):
    f = APP / "vendor" / "fonts" / n
    if not f.exists(): problems.append(f"missing font file: {n}")
    elif f.read_bytes()[:4] != b"wOF2": problems.append(f"font file is not WOFF2: {n}")
if re.search(r"fonts\.(googleapis|gstatic)\.com", (APP / "index.html").read_text()): problems.append("index.html still loads Google Fonts")
# Privacy scan (since 2026-10-21): the published folder must hold only site files. No email addresses,
# rights tables, permission letters or trackers, and only the file types the site uses.
ALLOWED_TYPES = {".html", ".css", ".js", ".json", ".svg", ".mp3", ".woff2", ".txt", ".md"}
BLOCKED_NAMES = re.compile(r"(rights|permission|tracker|letter|email|valko|\.eml$|\.csv$|\.xlsx?$|\.docx?$|\.pdf$)", re.I)
EMAIL = re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
# Allowlist (2026-11-16, approved by Bill): the project's public contact address may appear, but only in
# index.html (the About section). Any other address, or this one in any other file, still fails.
ALLOWED_EMAILS = {b"historicshortwave@gmail.com": {"index.html"}}
IMAGE_FILES = {"textures/cabinet.png": b"\x89PNG", "textures/panel.png": b"\x89PNG", "textures/desk.jpg": b"\xff\xd8\xff\xe0"}
for f in sorted(APP.rglob("*")):
    if not f.is_file(): continue
    rel = str(f.relative_to(APP))
    # New-face build (2026-11-16): the three panel/cabinet/desk textures are the only images allowed, and must be real PNG/JPEG files.
    if rel in IMAGE_FILES:
        if not f.read_bytes()[:4] == IMAGE_FILES[rel]: problems.append(f"texture is not the expected image type: {rel}")
    elif f.suffix.lower() not in ALLOWED_TYPES and rel != "_headers": problems.append(f"file type not allowed in the published folder: {rel}")
    if BLOCKED_NAMES.search(f.name) and not rel.startswith("vendor/"): problems.append(f"private-looking file in the published folder: {rel}")
    if f.suffix.lower() in {".html", ".css", ".js", ".json", ".svg", ".txt", ".md"}:
        for m in EMAIL.findall(f.read_bytes()):
            if rel in ALLOWED_EMAILS.get(m.lower(), ()): continue
            problems.append(f"email address in {rel}: {m.decode(errors='replace')}")
# Security rule and approved-archive list must agree (since 2026-10-21).
html = (APP / "index.html").read_text()
csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html)
if not csp: problems.append("index.html has no Content Security Policy")
else:
    media = re.search(r"media-src ([^;]+)", csp.group(1))
    csp_hosts = set(h.replace("https://", "") for h in (media.group(1).split() if media else []))
    js = (APP / "app.js").read_text()
    m = re.search(r"APPROVED_AUDIO_HOSTS=\[([^\]]+)\]", js)
    js_hosts = set(re.findall(r"'([^']+)'", m.group(1))) if m else set()
    if not js_hosts: problems.append("app.js has no APPROVED_AUDIO_HOSTS list")
    if "*.archive.org" not in csp_hosts or (js_hosts - csp_hosts): problems.append(f"media-src {sorted(csp_hosts)} does not cover APPROVED_AUDIO_HOSTS {sorted(js_hosts)}")
    if csp_hosts - js_hosts - {"*.archive.org"}: problems.append(f"media-src allows hosts the receiver does not approve: {sorted(csp_hosts - js_hosts - {'*.archive.org'})}")
    for f in [n for n in ["pilot.json", "full-inventory.json", "band-90m.json", "band-60m.json", "band-49m.json"] if (APP / n).exists()]:
        for r in json.loads((APP / f).read_text())["recordings"]:
            u = r.get("audioUrl") or ""
            host = re.match(r"https://([^/:]+)/", u)
            if u and not (host and (host.group(1) in js_hosts or host.group(1).endswith(".archive.org"))):
                problems.append(f"recording on an unapproved host: {f} {r.get('inventoryId')} {u[:60]}")
# No typed input (since 2026-10-29): the receiver reads only its fixed controls. Publishing fails if the page
# gains a text box, text area, form or editable area, or if any script reads the web address, the page
# fragment, cookies, browser storage, the clipboard or messages from other windows.
for tag in re.findall(r"<input\b[^>]*>", html):
    if not re.search(r'type="range"', tag): problems.append(f"typed input on the page: {tag[:80]}")
for pat, what in ((r"<textarea\b", "text area"), (r"<form\b", "form"), (r"contenteditable", "editable area")):
    if re.search(pat, html, re.I): problems.append(f"{what} on the page")
for js_file in sorted(APP.glob("*.js")):
    src = js_file.read_text()
    for pat, what in ((r"location\.(search|hash|href)|URLSearchParams", "reads the web address"),
                      (r"document\.cookie", "reads cookies"), (r"localStorage|sessionStorage|indexedDB", "uses browser storage"),
                      (r"navigator\.clipboard", "reads the clipboard"), (r"addEventListener\(\s*['\"]message|onmessage", "accepts window messages"),
                      (r"\bprompt\(", "asks for typed text")):
        if re.search(pat, src): problems.append(f"{js_file.name} {what}")
# Release data (since 2026-11-12, review A1): the release catalogs, credits and map data carry only the fields the
# receiver reads. Internal curation fields and working names stay in the private preview, which this part skips.
release_mode = (APP / "band-60m.json").exists() and not (APP / "full-inventory.json").exists()
if release_mode:
    RECORD_FIELDS = {"id", "inventoryId", "sortKey", "frequencyHz", "frequencyLabel", "station", "country", "date", "time",
                     "notes", "sourceUrl", "audioUrl", "additionalReferences"}
    BLOCKED_TEXT = ("publicationReview", "workbookSha256", "sourceWorkbook", "HR-64", "User-authorized", '"rights"', '"evidence"')
    for name in ("band-90m.json", "band-60m.json", "band-49m.json"):
        d = json.loads((APP / name).read_text())
        extra_top = set(d) - {"band", "bandLabel", "dialMinHz", "dialMaxHz", "defaultHz", "counts", "recordings"}
        if extra_top: problems.append(f"{name} carries unused catalog fields: {sorted(extra_top)}")
        extra = {k for r in d["recordings"] for k in r} - RECORD_FIELDS
        if extra: problems.append(f"{name} carries internal recording fields: {sorted(extra)}")
    for f in [APP / "band-90m.json", APP / "band-60m.json", APP / "band-49m.json", APP / "credits.json", APP / "geo" / "reveal-geography.json"]:
        text = f.read_text()
        for t in BLOCKED_TEXT:
            if t in text: problems.append(f"internal text {t} in {f.relative_to(APP)}")
# Code and link rules (since 2026-11-12, review A6). First-party scripts may not write HTML from strings, run code
# from strings, send data out or create typed inputs; the page loads only its own files; scripts name no outside
# hosts beyond the archive and the map-credit links; and every URL in the recording data is HTTPS.
UNSAFE_JS = ((r"\.innerHTML\b|\.outerHTML\b|insertAdjacentHTML|document\.write", "writes HTML from strings"),
             (r"\beval\s*\(|new\s+Function\b|set(Timeout|Interval)\(\s*['\"`]", "runs code from strings"),
             (r"sendBeacon|XMLHttpRequest|WebSocket|EventSource", "can send data to another site"),
             (r"createElement\(\s*['\"`](input|textarea|form)['\"`]", "creates a typed-input element"),
             (r"fetch\(\s*['\"`](https?:)?//", "fetches from an outside host"))
JS_HOSTS = {"archive.org", "www.w3.org", "creativecommons.org", "icr.ethz.ch", "www.naturalearthdata.com"}
for js_file in sorted(APP.glob("*.js")):
    src = js_file.read_text()
    for pat, what in UNSAFE_JS:
        if re.search(pat, src): problems.append(f"{js_file.name} {what}")
    for host in set(re.findall(r"https?://([A-Za-z0-9.-]+)", src)):
        if host not in JS_HOSTS and not host.endswith(".archive.org"): problems.append(f"{js_file.name} names an outside host: {host}")
for tag in re.findall(r"<(?:script|link|img|iframe|audio|video|source|embed|object|track)\b[^>]*>", html, re.I):
    for attr in re.findall(r"\b(?:src|href|data)\s*=\s*[\"']([^\"']*)", tag):
        if not (attr.startswith("./") or re.match(r"^[A-Za-z0-9_][\w./-]*$", attr)): problems.append(f"index.html loads a file that is not on the site: {tag[:90]}")
# Review 2026-11 F11: stylesheets, inline code, referenced files, SVG files and station names (owner rule 3).
for css_file in sorted(APP.rglob("*.css")):
    css, rel = css_file.read_text(), str(css_file.relative_to(APP))
    if re.search(r"@import\b", css): problems.append(f"{rel} uses @import")
    for target in re.findall(r"url\(\s*['\"]?([^'\")\s]+)", css):
        if re.match(r"(?i)^(https?:)?//|^data:", target): problems.append(f"{rel} loads a file that is not on the site: {target[:70]}")
        elif not (css_file.parent / target).resolve().is_file(): problems.append(f"{rel} names a missing file: {target[:70]}")
if re.search(r"<script\b(?![^>]*\bsrc=)", html, re.I): problems.append("index.html has an inline script")
if re.search(r"<style\b", html, re.I): problems.append("index.html has an inline style block")
if re.search(r"<[^>]+\sstyle\s*=", html, re.I): problems.append("index.html has an inline style attribute (the security rule blocks it)")
if re.search(r"<[^>]+\son[a-z]+\s*=", html, re.I): problems.append("index.html has an inline event handler")
for tag in re.findall(r"<(?:script|link)\b[^>]*>", html, re.I):
    for attr in re.findall(r"\b(?:src|href)\s*=\s*[\"']([^\"']*)", tag):
        if attr.startswith("./") and not (APP / attr[2:]).is_file(): problems.append(f"index.html names a missing file: {attr}")
for svg_file in sorted(APP.rglob("*.svg")):
    svg = svg_file.read_text(errors="replace")
    if re.search(r"<script\b|\son[a-z]+\s*=|href\s*=\s*[\"'](?!#)", svg, re.I): problems.append(f"SVG file carries script or an outside link: {svg_file.relative_to(APP)}")
stations = set()
for name in ("band-90m.json", "band-60m.json", "band-49m.json"):
    if (APP / name).exists(): stations |= {str(r.get("station") or "").strip() for r in json.loads((APP / name).read_text())["recordings"]}
page_text = {f.name: f.read_text(errors="replace") for f in [APP / "index.html", *sorted(APP.glob("*.js")), *sorted(APP.glob("*.css"))] if f.exists()}
for station in sorted(n for n in stations if len(n) >= 6):
    for fname, text in page_text.items():
        if station in text: problems.append(f"station name appears outside the catalog: {station!r} in {fname}")
def url_fields(o, key=None, out=None):
    out = [] if out is None else out
    if isinstance(o, dict): [url_fields(v, k, out) for k, v in o.items()]
    elif isinstance(o, list): [url_fields(v, key, out) for v in o]
    elif isinstance(o, str) and key and key.lower().endswith("url"): out.append(o)
    return out
for name in ["pilot.json", "full-inventory.json", "band-90m.json", "band-60m.json", "band-49m.json", "credits.json"]:
    if (APP / name).exists():
        for u in url_fields(json.loads((APP / name).read_text())):
            if not re.match(r"https://[A-Za-z0-9.-]+(/|$)", u): problems.append(f"{name} has a non-HTTPS address: {u[:70]}")
# Release headers (since 2026-11-12): the build writes _headers with the page's policy plus frame-ancestors 'none'.
if release_mode:
    hdr = (APP / "_headers").read_text() if (APP / "_headers").exists() else ""
    if not hdr: problems.append("release has no _headers file")
    else:
        page_csp = csp.group(1).rstrip("; ") if csp else ""
        if f"Content-Security-Policy: {page_csp}; frame-ancestors 'none'" not in hdr: problems.append("_headers policy does not match the page's policy")
        for need in ("X-Frame-Options: DENY", "X-Content-Type-Options: nosniff", "Strict-Transport-Security:", "! Access-Control-Allow-Origin"):
            if need not in hdr: problems.append(f"_headers is missing: {need}")
    if csp and "data:" in csp.group(1): problems.append("page policy still allows data: sources")
# Preview-only copy (D2, approved by Bill 2026-11-19): the Perplexity preview host needs https://sites.pplx.app in the
# security rule; a publishable folder must never carry it, in the page, in _headers or in any other site file.
for f in sorted(APP.rglob("*")):
    if f.is_file() and (f.suffix.lower() in {".html", ".css", ".js", ".json", ".svg", ".txt", ".md"} or f.name == "_headers"):
        if b"sites.pplx.app" in f.read_bytes(): problems.append(f"preview-only host sites.pplx.app in {f.relative_to(APP)} (this is the preview copy, not a publishable package)")
print("\n".join(problems) if problems else f"PUBLISH READY: no placeholders; {len(names)} seasonal noise files are real MP3s; {len(set(font_files))} font files are real WOFF2; privacy scan clean; security rule matches the approved archives; no typed input" + ("; release data holds only receiver fields; headers match the page" if release_mode else "") + "; no unsafe code or outside loads")
sys.exit(1 if problems else 0)
