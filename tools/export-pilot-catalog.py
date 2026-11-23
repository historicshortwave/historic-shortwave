"""Run via xlsx_repl. Export private staging data, never approve or publish audio."""

import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import openpyxl

ROOT = Path(os.environ.get(
    "SHORTWAVE_PROJECT_FILES",
    str(Path(__file__).resolve().parent.parent),
))
WORKBOOK = ROOT / "60m_SWBC_recordings_1960-1989.xlsx"
OUTPUT = ROOT / "data" / "pilot"
OUTPUT.mkdir(parents=True, exist_ok=True)
book = openpyxl.load_workbook(WORKBOOK, data_only=True)
master = book["60m SWBC recordings 1960-89"]
summary = book["NASWA Country Summary"]
assert master.max_column == 21
assert master.cell(1, 1).value == "#"
metrics_names = [
    "qualified_naswa_entities_including_exceptions",
    "qualified_core_band_naswa_entities",
    "nominal_naswa_entities",
    "qualified_inventory_records",
    "held_inventory_records",
    "total_inventory_records",
]
metrics = dict(zip(metrics_names, [summary.cell(r, 3).value for r in range(4, 10)]))
assert all(isinstance(value, int) for value in metrics.values()), "Recalculate formula caches before export"
timestamp = datetime.now(timezone.utc).isoformat()
records = []
ids = set()
order = []
for row_index, cells in enumerate(master.iter_rows(min_row=2, values_only=True), 2):
    (inventory_id, station, frequency, date_label, time_label, certainty,
     audio, page, collection, notes, entity, continent, locality, edition,
     status, qualified, mapping_notes, definition, evidence, scope, core) = cells
    assert isinstance(inventory_id, int) and inventory_id not in ids
    ids.add(inventory_id)
    assert qualified in ("Yes", "No") and core in ("Yes", "No")
    q = qualified == "Yes"
    expected_core = q and scope == "Core 4750-5060 kHz"
    assert (core == "Yes") == expected_core, f"Bad U cache for ID {inventory_id}"
    # These are frequency mentions, not confirmed carriers. Ignore explanatory years.
    mentions = sorted({
        int(Decimal(token) * 1000)
        for token in re.findall(r"\d+(?:\.\d+)?", str(frequency))
        if Decimal("4000") <= Decimal(token) <= Decimal("6000")
    })
    assert mentions, f"No sortable frequency label for ID {inventory_id}"
    order.append(min(mentions))
    blockers = [
        "metadata_publication_review_pending",
        "rights_access_review_pending",
        "media_playback_seek_review_pending",
        "segment_applicability_review_pending",
    ]
    if not q:
        blockers.append("inventory_hold")
    if inventory_id == 167:
        blockers.append("wwvh_compilation_cut_points_unverified")
    if inventory_id == 349:
        blockers.extend(["proposed_frequency_not_clip_verified", "placement_time_not_recording_time"])
    records.append({
        "recording_id": f"rec-{inventory_id:06d}",
        "inventory_id": inventory_id,
        "source_workbook": {
            "file": WORKBOOK.name, "sheet": master.title, "worksheet_row": row_index,
        },
        "source": {
            "station_label": station, "frequency_label": frequency,
            "recording_date_label": date_label, "time_label": time_label,
            "date_certainty": certainty, "audio_url": audio, "archive_page": page,
            "collection": collection, "notes": notes,
        },
        "classification": {
            "naswa_entity": entity, "continent": continent, "transmitter_locality": locality,
            "naswa_edition": edition, "status_label": status, "qualified_inventory": q,
            "mapping_notes": mapping_notes, "definition_url": definition,
            "evidence_label": evidence, "frequency_scope_label": scope,
            "qualified_core_band": expected_core,
        },
        "normalization": {
            "numeric_frequency_mentions_hz": mentions,
            "frequency_sort_key_hz": min(mentions),
            "frequency_review_required": True,
            "multiple_numeric_frequency_mentions": len(mentions) > 1,
            "frequency_mention_basis": "provisional_assumption" if inventory_id == 349 else "unreviewed_source_label",
            "approved_carrier_hz": None,
            "recording_date_normalization_status": "unreviewed",
            "recording_time_meaning": "unreviewed",
            "confirmed_recording_start_gmt": None,
            "continuous_time_mapping_verified": False,
        },
        "curation": {
            "metadata_review": "pending", "rights_access_review": "pending",
            "media_review": "pending", "segment_review": "pending",
            "reviewer": None, "reviewed_at": None,
        },
        "publication": {
            "standard_mode_inventory_candidate": q,
            "publish_eligible": False,
            "blockers": blockers,
        },
    })
assert order == sorted(order), "Master sheet is not sorted by numeric frequency"
qualified_records = [r for r in records if r["classification"]["qualified_inventory"]]
core_records = [r for r in records if r["classification"]["qualified_core_band"]]
counts = {
    "qualified_naswa_entities_including_exceptions": len({
        r["classification"]["naswa_entity"] for r in qualified_records
        if r["classification"]["naswa_entity"] is not None
    }),
    "qualified_core_band_naswa_entities": len({
        r["classification"]["naswa_entity"] for r in core_records
        if r["classification"]["naswa_entity"] is not None
    }),
    "nominal_naswa_entities": len({
        r["classification"]["naswa_entity"] for r in records
        if r["classification"]["naswa_entity"] is not None
    }),
    "qualified_inventory_records": len(qualified_records),
    "held_inventory_records": len(records) - len(qualified_records),
    "total_inventory_records": len(records),
}
assert counts == metrics, (counts, metrics)
exceptions = [r["inventory_id"] for r in qualified_records if not r["classification"]["qualified_core_band"]]
elwa = next(r for r in records if r["inventory_id"] == 349)
assert "0600" in elwa["source"]["time_label"]
assert not elwa["classification"]["qualified_inventory"]
assert all(not r["publication"]["publish_eligible"] for r in records)
header = {
    "schema_version": "1.1",
    "generated_at_utc": timestamp,
    "workbook_file": WORKBOOK.name,
    "workbook_sha256": hashlib.sha256(WORKBOOK.read_bytes()).hexdigest(),
    "recording_year_scope": {"from": 1960, "to": 1989, "complete_year_coverage_claimed": False},
    "band_scope": {
        "core_hz": [4750000, 5060000],
        "proposed_extended_interface_hz": [4700000, 5085000],
    },
}
catalog = {
    **header,
    "visibility": "private_curator_staging_not_frontend_safe",
    "inventory_metrics": metrics,
    "qualified_core_band_records": len(core_records),
    "qualified_exception_inventory_ids": exceptions,
    "records": records,
}
standard = {
    **header,
    "status": "awaiting_explicit_publication_review",
    "approved_by": None,
    "approved_at": None,
    "recordings": [],
    "warning": "Do not auto-fill from qualified inventory. Later approved release manifests must use a separate non-generated path.",
}
overlay = {
    **header,
    "visibility": "private_curator_staging",
    "enabled_by_default": False,
    "required_user_action": "Include provisional reconstructions",
    "placements": [{
        "recording_id": "rec-000349",
        "inventory_id": 349,
        "carrier_hz": 4770000,
        "carrier_basis": "historical_channel_documented_but_unverified_for_clip",
        "receiver_placement_gmt": "0600",
        "approximate": True,
        "time_basis": "owner_approved_provisional_receiver_placement",
        "confirmed_recording_start_gmt": None,
        "calculated_broadcast_gmt_enabled": False,
        "count_in_qualified_totals": False,
        "publish_eligible": False,
        "rights_access_review": "pending",
        "media_review": "pending",
        "pre_reveal_disclosure": {
            "frequency": "Provisional placement: 4770 kHz",
            "date": "Recording year: 1971",
            "recording_time": "Recording GMT: not documented",
            "receiver_time": "Approximate receiver placement: 0600 GMT",
        },
        "evidence_urls": [
            "https://archive.org/details/elwa-monrovia-liberia-1970",
            "https://www.worldradiohistory.com/Archive-DX/NASWA/70s/FRENDX-1973-12.pdf",
            "https://www.worldradiohistory.com/Archive-Speedx/70s/Speedx-1974-02.pdf",
        ],
    }],
}
validation = {
    **header,
    "result": "passed_staging_import_checks_not_publication_review",
    "checks": {
        "unique_stable_inventory_ids": True,
        "ascending_frequency_order": True,
        "cached_summary_metrics_reconciled": True,
        "all_core_flag_caches_consistent": True,
        "all_holds_excluded_from_standard_candidacy": True,
        "no_automatic_publication_approvals": True,
        "elwa_0600_assumption_separate_and_uncounted": True,
        "original_workbook_modified": False,
    },
    "inventory_metrics": metrics,
    "qualified_core_band_records": len(core_records),
    "qualified_band_edge_records": len(exceptions),
    "standard_launch_approved_records": 0,
    "provisional_overlay_publication_approved_records": 0,
    "held_inventory_ids": [r["inventory_id"] for r in records if not r["classification"]["qualified_inventory"]],
    "audio_playback_tested_by_this_export": False,
    "rights_review_completed_by_this_export": False,
}
for filename, payload in [
    ("inventory-snapshot.json", catalog),
    ("standard-launch-manifest.json", standard),
    ("provisional-placement-overlay.json", overlay),
    ("import-validation-report.json", validation),
]:
    (OUTPUT / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "generated_files": [str(path.relative_to(ROOT)) for path in sorted(OUTPUT.glob("*.json"))],
    "inventory_metrics": metrics,
    "qualified_core_band_records": len(core_records),
    "qualified_exception_records": len(exceptions),
    "launch_approved_records": 0,
    "workbook_unchanged": True,
}, indent=2))
