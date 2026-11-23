#!/usr/bin/env python3
"""Make a PRIVATE-PREVIEW-ONLY copy of the new-face build that loads its data on the Perplexity preview host.

Why: the preview host (sites.pplx.app) sends `Content-Security-Policy: sandbox ...` without allow-same-origin, so the
page runs with an opaque ("null") origin. Safari's engine (WebKit) then matches nothing to `connect-src 'self'` and
blocks every data download: band catalogs, credits, reveal-map geography and the seasonal-noise files ("NO CATALOG").
Chrome is unaffected. Fonts, images, scripts and Archive.org audio are not affected.

What this does: copies release/heritage-hr64-face/ to release/heritage-hr64-face-preview-host/ and adds the preview
host's address to connect-src only, in the page's security rule and in _headers. Nothing else changes.

Never upload this folder to Cloudflare or any public host. The release build stays the source for publication.
Note (Nov 18): check-publish-ready does NOT currently reject this copy; it does not check connect-src sources.

Usage: python3 tools/build-preview-host.py
"""
import pathlib, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "release" / "heritage-hr64-face"
DST = ROOT / "release" / "heritage-hr64-face-preview-host"
HOST = "https://sites.pplx.app"
OLD = "connect-src 'self';"
NEW = f"connect-src 'self' {HOST};"

if not (SRC / "index.html").exists():
    sys.exit(f"missing {SRC}; run tools/build-face.py first")
if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
for name in ("index.html", "_headers"):
    f = DST / name
    text = f.read_text(encoding="utf-8")
    if text.count(OLD) != 1:
        sys.exit(f"{name}: expected exactly one \"{OLD}\", found {text.count(OLD)}; nothing safe to change")
    f.write_text(text.replace(OLD, NEW), encoding="utf-8")
print(f"built {DST.relative_to(ROOT)} (connect-src adds {HOST}; private preview only)")
