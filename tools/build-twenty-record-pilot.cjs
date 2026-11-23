const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'data/pilot/inventory-snapshot.json'), 'utf8'));
const ids = [348,162,117,168,63,114,98,160,35,325,46,253,47,191,24,172,259,87,7,346];
const recordings = ids.map(id => {
  const r = catalog.records.find(r => r.inventory_id === id);
  if (!r || !r.classification.qualified_inventory || r.normalization.numeric_frequency_mentions_hz.length !== 1) throw Error('Ineligible selection '+id);
  return {
    id: r.recording_id, inventoryId: id, frequencyHz: r.normalization.frequency_sort_key_hz,
    frequencyLabel: r.source.frequency_label, station: r.source.station_label,
    date: r.source.recording_date_label, time: r.source.time_label,
    certainty: r.source.date_certainty, audioUrl: r.source.audio_url,
    sourceUrl: r.source.archive_page, collection: r.source.collection,
    notes: r.source.notes, country: r.classification.naswa_entity,
    scope: r.classification.qualified_core_band ? 'core' : 'exception',
    evidence: r.classification.evidence_label,
    publicationReview: 'pending',
  };
});
if (new Set(recordings.map(r=>r.frequencyHz)).size !== 20) throw Error('Twenty distinct carriers required');
if (recordings[0].frequencyHz!==4700100 || recordings.at(-1).frequencyHz!==5081000) throw Error('Full range not covered');
const payload = {
  schemaVersion: '1.0', name: 'Heritage H-60: Twenty Recording Pilot',
  status: 'private_source_hosted_design_preview_not_public_release',
  workbookSha256: catalog.workbook_sha256,
  selectionMethod: 'Twenty distinct documented carriers near evenly spaced range targets; endpoints retained; 4765 chosen to include August 1961. No frequency relocation.',
  dialMinHz: 4700000, dialMaxHz: 5085000,
  recordings,
};
const dir = path.join(root,'app','heritage-h60');
fs.mkdirSync(dir,{recursive:true});
fs.writeFileSync(path.join(dir,'pilot.json'),JSON.stringify(payload,null,2)+'\n');
fs.writeFileSync(path.join(root,'data','pilot','twenty-record-design-playlist.json'),JSON.stringify(payload,null,2)+'\n');
const rows=recordings.map((r,i)=>`| ${i+1} | ${r.inventoryId} | ${r.frequencyLabel} | ${r.station} | ${r.date} | ${r.time || 'not documented'} | ${r.scope} ([archive item](${r.sourceUrl})) |`).join('\n');
fs.writeFileSync(path.join(root,'design','pilot','twenty-record-playlist.md'),`# Heritage H-60: Twenty Recording Pilot Playlist\n\nExactly twenty distinct carriers span 4700.1–5081.0 kHz, the full range of the 349-record database. Selection favors near-even frequency coverage while retaining original reported frequencies; 4765 kHz includes the August 1961 recording. This is a proposed private, source-hosted design-preview playlist, not a rights-reviewed public launch manifest.\n\n| Slot | Stable inventory ID | kHz | Original station label | Date label | Reported UTC label | Scope and evidence |\n|---|---|---|---|---|---|---|\n${rows}\n\nAll selected rows are inventory-qualified. Four are approved band-edge exceptions (4700.1, 4719, 4740 and 5081 kHz); the preview opens with the extension enabled to fulfill full-range exploration. The core-band switch limits the active range to 4750–5060 kHz. Unknown and multiple reported times are preserved, not converted to recording-start times.\n\nELWA provisional ID 349 and the unsegmented WWVH compilation ID 167 are intentionally not added as a twenty-first item. Their design rules remain in the specification and they can replace a pilot slot after explicit review. No other deferred recordings were added, and no original audio was copied into the app.\n`);
console.log(JSON.stringify({count:recordings.length,minHz:recordings[0].frequencyHz,maxHz:recordings.at(-1).frequencyHz,inventoryIds:ids},null,2));
