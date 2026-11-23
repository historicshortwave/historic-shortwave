#!/usr/bin/env python3
"""Proves tools/check-publish-ready.py catches deliberate breakage (review A6, 2026-11-12).

  python3 tools/test-publish-check.py
Copies the release, applies one breakage per copy, and expects the check to fail; the unmodified release and
preview must pass. The first seven are the reviewer's mutations; the next three break the release headers;
the last three test the contact-email allowlist (2026-11-16).
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
REL, PRE, CHECK = ROOT / "release" / "heritage-hr64", ROOT / "app" / "heritage-h60", ROOT / "tools" / "check-publish-ready.py"
def run(folder):
    return subprocess.run([sys.executable, str(CHECK)], env={**os.environ, "HR64_APP": str(folder)}, capture_output=True, text=True)
def append(f, text): f.write_text(f.read_text() + text)
def json_edit(f, fn): d = json.loads(f.read_text()); fn(d); f.write_text(json.dumps(d))
def first_license(d): next(v for v in d["credits"].values() if "license" in v)["license"]["url"] = "javascript:alert(1)"
MUTATIONS = {
    "innerHTML in app.js": lambda a: append(a / "app.js", "\ndocument.body.innerHTML='<b>x</b>';\n"),
    "javascript: license URL": lambda a: json_edit(a / "credits.json", first_license),
    "http: sourceUrl": lambda a: json_edit(a / "band-90m.json", lambda d: d["recordings"][0].update(sourceUrl="http://archive.org/details/x")),
    "script-created text input": lambda a: append(a / "app.js", "\ndocument.body.append(document.createElement('input'));\n"),
    "outside script in index.html": lambda a: (a / "index.html").write_text((a / "index.html").read_text().replace("</head>", '<script src="https://cdn.example.com/x.js"></script></head>', 1)),
    "eval plus image beacon": lambda a: append(a / "app.js", "\neval('1');new Image().src='https://tracker.example.net/p.gif';\n"),
    "sendBeacon": lambda a: append(a / "app.js", "\nnavigator.sendBeacon('https://collect.example.org/', 'x');\n"),
    "missing _headers": lambda a: (a / "_headers").unlink(),
    "headers policy drifted": lambda a: (a / "_headers").write_text((a / "_headers").read_text().replace("object-src 'none'; ", "")),
    "open CORS not removed": lambda a: (a / "_headers").write_text((a / "_headers").read_text().replace("  ! Access-Control-Allow-Origin\n", "")),
    "other email in index.html": lambda a: (a / "index.html").write_text((a / "index.html").read_text().replace("</body>", "<p>someone.else@example.com</p></body>", 1)),
    "contact email outside index.html": lambda a: append(a / "app.js", "\n// historicshortwave@gmail.com\n"),
    "contact email in a data file": lambda a: json_edit(a / "credits.json", lambda d: d.update(contact="historicshortwave@gmail.com")),
    # D2 (2026-11-19): the preview-only host in the page policy, in _headers, or both, as the preview copy has it.
    "preview host in page policy": lambda a: (a / "index.html").write_text((a / "index.html").read_text().replace("connect-src 'self'", "connect-src 'self' https://sites.pplx.app", 1)),
    "preview host in _headers": lambda a: (a / "_headers").write_text((a / "_headers").read_text().replace("connect-src 'self'", "connect-src 'self' https://sites.pplx.app", 1)),
}
# The allowed address in index.html must pass.
POSITIVE = {
    "contact email in index.html passes": lambda a: (a / "index.html").write_text((a / "index.html").read_text().replace("</body>", '<p><a href="mailto:historicshortwave@gmail.com">historicshortwave@gmail.com</a></p></body>', 1)),
}
failures = 0
for name, folder in (("unmodified release passes", REL), ("unmodified preview passes", PRE)):
    ok = run(folder).returncode == 0; failures += not ok; print(("PASS " if ok else "FAIL ") + name)
# D2 (2026-11-19): the new face passes, and its preview-only copy (if built) is rejected.
FACE, HOSTCOPY = ROOT / "release" / "heritage-hr64-face", ROOT / "release" / "heritage-hr64-face-preview-host"
if FACE.exists():
    ok = run(FACE).returncode == 0; failures += not ok; print(("PASS " if ok else "FAIL ") + "unmodified new face passes")
if HOSTCOPY.exists():
    r = run(HOSTCOPY); ok = r.returncode != 0 and "sites.pplx.app" in r.stdout; failures += not ok
    print(("PASS " if ok else "FAIL ") + "preview-only copy is rejected")
tmp = Path(tempfile.mkdtemp())
for i, (name, mutate) in enumerate(MUTATIONS.items()):
    copy = tmp / f"m{i}"; shutil.copytree(REL, copy); mutate(copy)
    r = run(copy); ok = r.returncode != 0
    failures += not ok
    print(("PASS " if ok else "FAIL ") + f"caught: {name}" + (f"  -> {r.stdout.strip().splitlines()[0][:90]}" if ok else ""))
for i, (name, mutate) in enumerate(POSITIVE.items()):
    copy = tmp / f"p{i}"; shutil.copytree(REL, copy); mutate(copy)
    r = run(copy); ok = r.returncode == 0
    failures += not ok
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {r.stdout.strip()[:200]}"))
shutil.rmtree(tmp)
print("ALL PASS" if not failures else f"{failures} FAILED"); sys.exit(1 if failures else 0)
