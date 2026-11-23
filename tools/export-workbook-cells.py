#!/usr/bin/env python3
"""Read-only cached-value and formula-text export of project workbooks, for the checkpoint builder.

  python3 tools/export-workbook-cells.py OUT.json WORKBOOK.xlsx [WORKBOOK.xlsx ...]
Never writes to the workbooks. Values are the workbook's cached results (no recalculation).
"""
import datetime, hashlib, json, sys
from pathlib import Path
import openpyxl

root = Path(__file__).resolve().parent.parent
out, books = sys.argv[1], sys.argv[2:]

def cell(v):
    if v is None: return ""
    if isinstance(v, (datetime.datetime, datetime.date, datetime.time)): return v.isoformat()
    return v if isinstance(v, (int, float, str, bool)) else str(v)

result = []
for rel in books:
    p = root / rel
    data = p.read_bytes()
    if data.startswith(b"version https://git-lfs"): sys.exit(f"LFS placeholder, hydrate first: {rel}")
    values = openpyxl.load_workbook(p, data_only=True, read_only=False)
    formulas = openpyxl.load_workbook(p, data_only=False, read_only=False)
    sheets = []
    for ws in values.worksheets:
        wf = formulas[ws.title]
        rows = [[cell(c.value) for c in row] for row in ws.iter_rows()]
        while rows and all(v == "" for v in rows[-1]): rows.pop()
        f = {c.coordinate: c.value for row in wf.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")}
        sheets.append({"name": ws.title, "range": ws.dimensions, "rows": rows, "formulas": f})
    result.append({"file": rel, "sha256": hashlib.sha256(data).hexdigest(), "sheets": sheets})
Path(out).write_text(json.dumps({"workbooks": result}, ensure_ascii=False))
print(json.dumps([{"file": w["file"], "sheets": [(s["name"], s["range"], len(s["rows"]), len(s["formulas"])) for s in w["sheets"]]} for w in result], indent=1))
