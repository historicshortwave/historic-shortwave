// Read-only inventory/app audit. Outputs an assessment, never a playback manifest.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'data/pilot/inventory-snapshot.json')));
const digest = crypto.createHash('sha256').update(fs.readFileSync(path.join(root, catalog.workbook_file))).digest('hex');
if (digest !== catalog.workbook_sha256) throw new Error('Inventory snapshot is stale');
const records = catalog.records;
const singles = records.filter(r => r.normalization.numeric_frequency_mentions_hz.length === 1);
const qualifiedSingles = singles.filter(r => r.classification.qualified_inventory);
function grouped(rows) {
  const map = new Map();
  for (const r of rows) {
    const hz = r.normalization.numeric_frequency_mentions_hz[0];
    if (!map.has(hz)) map.set(hz, []);
    map.get(hz).push(r);
  }
  return [...map].sort((a,b) => a[0]-b[0]).map(([hz,rs]) => ({
    frequency_hz: hz, frequency_khz: hz/1000, count: rs.length,
    records: rs.map(r => ({
      id: r.recording_id, inventory_id: r.inventory_id,
      sheet_row: r.source_workbook.worksheet_row,
      station: r.source.station_label, date: r.source.recording_date_label,
      qualified_inventory: r.classification.qualified_inventory,
      source_page: r.source.archive_page
    }))
  }));
}
function totals(groups) {
  const shared = groups.filter(g => g.count>1);
  return {
    single_frequency_records: groups.reduce((n,g)=>n+g.count,0),
    distinct_frequencies: groups.length,
    shared_frequency_groups: shared.length,
    recordings_in_shared_groups: shared.reduce((n,g)=>n+g.count,0),
    extra_recordings_beyond_one_per_frequency: groups.reduce((n,g)=>n+g.count-1,0)
  };
}
function flatten(r) {
  return {
    id:r.recording_id, inventoryId:r.inventory_id,
    frequencyHz:r.normalization.frequency_sort_key_hz,
    frequencyLabel:r.source.frequency_label, station:r.source.station_label,
    date:r.source.recording_date_label, time:r.source.time_label,
    certainty:r.source.date_certainty, audioUrl:r.source.audio_url,
    sourceUrl:r.source.archive_page, collection:r.source.collection,
    notes:r.source.notes, country:r.classification.naswa_entity,
    scope:r.classification.qualified_core_band?'core':'exception',
    evidence:r.classification.evidence_label, publicationReview:'pending'
  };
}
const allGroups=grouped(singles), qualifiedGroups=grouped(qualifiedSingles);
const hosts={};
for(const r of records) {
  const host=new URL(r.source.audio_url).hostname;
  hosts[host]=(hosts[host]||0)+1;
}
const multi=records.filter(r=>r.normalization.numeric_frequency_mentions_hz.length>1)
  .map(r=>({id:r.inventory_id,station:r.source.station_label,frequency:r.source.frequency_label}));
const held=records.filter(r=>!r.classification.qualified_inventory);
const duplicates=new Map();
for(const r of records) {
  if(!duplicates.has(r.source.audio_url))duplicates.set(r.source.audio_url,[]);
  duplicates.get(r.source.audio_url).push(r.inventory_id);
}
const byteSize=rs=>Buffer.byteLength(JSON.stringify({recordings:rs.map(flatten)},null,2));
const audit={
  audited_on:'2026-10-11',workbook_sha256:digest,workbook_unchanged:true,
  runtime_changes:false,performance_benchmark_performed:false,
  total_records:records.length,qualified_records:records.length-held.length,held_records:held.length,
  all_single_frequency:totals(allGroups),qualified_single_frequency:totals(qualifiedGroups),
  multiple_frequency_labels:multi,audio_hosts:hosts,
  flat_metadata_estimate_bytes_all:byteSize(records),
  flat_metadata_estimate_bytes_qualified_single:byteSize(qualifiedSingles),
  shared_audio_urls:[...duplicates].filter(([url,ids])=>ids.length>1).map(([url,ids])=>({url,ids})),
  all_single_frequency_groups:allGroups,qualified_single_frequency_groups:qualifiedGroups
};
const esc=s=>String(s??'Not documented').replace(/\|/g,'\\|').replace(/\n/g,' ');
let report=`# Full-Inventory Receiver Proof-of-Concept Assessment

Assessment date: 11 October 2026. This is a read-only assessment of the current receiver and the 349-record master inventory, not implementation approval or a public-release clearance. The twenty-record pilot, HR-64 visual preview, workbook and audio files are unchanged, and QSLs remain deferred.

## Recommendation

Expanding the private receiver to exercise the full inventory is a manageable, moderate change, not a new receiver architecture. The import work is straightforward because a current normalized snapshot already contains all 349 master rows and original audio links. The main engineering work is making same-frequency alternatives reachable, respecting review holds and frequency ambiguities, and improving loading/error feedback.

Do not merely replace the twenty-record playlist with every row. Add a reversible full-inventory test mode, retain the twenty-record mode as a regression baseline, and keep one active audio stream. A frequency-group selector and neutral “Another recording” control can expose alternatives without station-name spoilers.

This is a single-user catalog/resilience proof of concept, not a concurrent-user load test. Public release still requires the existing audio-access, rights, attribution, content and metadata reviews; deferring QSL rights does not resolve the separate audio requirements.

## Inventory and same-frequency findings

The inventory snapshot matches the current workbook SHA-256, \`${digest}\`. All inventory-derived values below come from the main “60m SWBC recordings 1960-89” sheet, A2:U350, as preserved in that snapshot. Column A is stable ID, B station, C frequency, D date, G audio URL, P inventory eligibility, and T/U band classification; the appendix retains sheet-row traceability.

| Measure | All single-frequency rows | Inventory-qualified single-frequency rows |
|---|---:|---:|
| Recording rows | ${singles.length} | ${qualifiedSingles.length} |
| Distinct frequency values | ${allGroups.length} | ${qualifiedGroups.length} |
| Frequencies with multiple recordings | ${totals(allGroups).shared_frequency_groups} | ${totals(qualifiedGroups).shared_frequency_groups} |
| Recordings belonging to shared-frequency groups | ${totals(allGroups).recordings_in_shared_groups} | ${totals(qualifiedGroups).recordings_in_shared_groups} |

“Single-frequency” means the source label has one extracted numeric frequency, not that the carrier, eligibility or playback has been newly verified. Of 349 total rows, 330 are inventory-qualified and 19 are held. Four of the qualified rows have multiple numeric frequency mentions and are excluded from the single-frequency totals above. Inventory qualification is not public-release approval or proof that a URL currently plays.

| Frequency | All recording rows | Inventory-qualified rows | Significance |
|---|---:|---:|---|
| 4845 kHz | 17 | 17 | Largest exact-frequency group; regional stations and repeat recordings need explicit selection. |
| 4915 kHz | 10 | 10 | Several broadcasters and recordings from different dates. |
| 4800 kHz | 9 | 7 | Exact-frequency alternatives include entries still on hold. |
| 4890 kHz | 9 | 9 | PNG and other broadcasters, with multiple historical dates. |
| 4940 kHz | 9 | 9 | Multiple services/outlets and recordings. |
| 5000 kHz | 7 | 4 | WWV, WWVH, ZUO, IBF and VNG labels; some entries are held and the WWVH compilation requires segment review. |

These are recording counts, not counts of distinct stations. Name variants, repeated receptions, alternate files and compilation entries remain separate stable records.

## What breaks with a simple playlist expansion

- **Exact ties:** the current \`tune()\` reducer selects one nearest recording within 1000 Hz. Its comparison is strictly closer, not equally close, so the first array entry wins an exact tie. At 4845 kHz, one of seventeen entries would be selected and the other sixteen would remain inaccessible through ordinary tuning.
- **Guide clicks:** each guide button currently calls \`tune(r.frequencyHz)\`, not a recording-ID selection function. Clicking a second recording's guide button at the same frequency would still select the first tied entry.
- **Close carriers:** in the qualified single-frequency subset, 59 adjacent distinct-frequency pairs are less than 2 kHz apart. Examples include 4814.9/4815.0 and 4829.9/4830.0 kHz. The current plus/minus 1 kHz capture windows overlap; dense catalog tuning needs review to prevent excessive switching and to preserve deliberate between-station space.
- **Layout:** rendering one guide button per recording would turn a twenty-position guide into hundreds of buttons. Group by real frequency and paginate or collapse alternatives instead.
- **Playback state:** the current code cancels loading audio on selection change and uses a 250 ms tuning-settle timer. Keep those protections, and key alternative selection/resume positions/logs by stable recording ID.

## Recommended conflict behavior

- **Frequency first:** select the nearest eligible carrier group, then one recording from that group. Do not move recordings to invented nearby frequencies to make room.
- **Neutral alternatives:** show “4845.0 kHz · Recording 1 of 17” with previous/next or “Another recording.” Dates may be shown where documented; station names remain concealed until the listener chooses Reveal.
- **Session order:** use a session-shuffled order for each group, or a deterministic order in tester mode. Remember the selected recording when the listener tunes away and back; tiny knob movements must not reshuffle or restart the choice.
- **One stream:** stop the previous clip before starting an alternative. Do not mix independent historical recordings to manufacture co-channel interference: they may have been recorded years apart and do not establish simultaneous transmission.
- **Reachability:** the guide and tester control must select a stable recording ID, not just call the frequency tuner. Every eligible alternative must be reachable without editing the catalog order.
- **Nearby carriers:** retain the documented frequency and 0.1 kHz precision. Test neighbor-aware capture windows and a small hysteresis/dead zone rather than using artificial frequency relocation. Exact thresholds are implementation parameters, not approved facts.
- **Optional later filters:** historical date/era filters can reduce alternatives, but must preserve partial/unknown dates and must not be confused with today's Eastern date used for seasonal noise. They are not necessary to prove the full-catalog concept.

## All 349 records versus normal autoplay

Importing all 349 metadata rows into a private test catalog is different from enabling every row as an ordinary receiver station. Preserve the 19 existing inventory holds in a clearly marked review/test area, not normal autoplay. Frequency-label ambiguities need explicit interpretation or reviewed segment placements:

| Inventory ID | Original station label | Original frequency label |
|---|---|---|
`;
for(const r of multi)report+=`| ${r.id} | ${esc(r.station)} | ${esc(r.frequency)} |\n`;
report+=`
Do not automatically choose the lowest number from these labels or duplicate the full audio at every mentioned frequency. ID 123 changes frequency, ID 22 is a composite Rumbos/Torbes item, ID 174 contains multiple stated frequencies, and ID 299 preserves conflicting frequency evidence. The existing data contract requires curation before placements are approved.

Also preserve the existing WWVH ID 167 compilation/segment-review requirement and the separate, disabled ELWA ID 349 provisional placement. A single numeric value does not clear these cases. The 326 qualified single-frequency rows are a starting candidate pool, not a claim that all 326 are ready for public playback.

IDs 23 and 24 share one exact audio URL for the three-station sign-on compilation. That is one media asset referenced by two inventory entries, not evidence that the inventory should be merged or that each entry starts at the correct station segment. A media checker can deduplicate requests for that URL while retaining separate recording/segment identities.

## Catalog size and source-hosted latency

An estimated flat metadata payload using the pilot's existing field shape is ${audit.flat_metadata_estimate_bytes_all.toLocaleString('en-US')} bytes for all 349 rows, or approximately ${(audit.flat_metadata_estimate_bytes_all/1024).toFixed(0)} KiB uncompressed. The 326 qualified single-frequency candidate rows would be about ${(audit.flat_metadata_estimate_bytes_qualified_single/1024).toFixed(0)} KiB. These are serialization estimates, not built/shipped catalogs, and include private-preview reveal/provenance fields; a public manifest must obey the separate blind/reveal data contract.

The current player creates a selected audio element on demand with \`preload="metadata"\`, then calls \`play()\`. It does not create 349 players or start 349 audio downloads, so increasing metadata count does not by itself multiply the bandwidth needed for one active stream.

Browsers treat preload as a hint, and playback can begin before an entire file has downloaded. The actual buffering behavior is browser-dependent; metadata loading is not a guarantee of instant playback. ([MDN audio preload documentation](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/audio))

| Audio URL hostname | Inventory rows |
|---|---:|
`;
for(const [host,n] of Object.entries(hosts))report+=`| ${host} | ${n} |\n`;
report+=`
These are original URL hostnames from the inventory, not a measurement of final redirected serving hosts. All 349 rows contain an audio URL, but presence of a URL does not establish current availability. The files are labelled by extension as 347 MP3 and two M4A URLs.

Your reported near-immediate pilot playback is encouraging, but cannot be extrapolated to every file or mobile browser. Startup can be delayed by host connection/setup, redirects, source response time, bandwidth, media layout/codec work, and initial buffering; repeated playback may benefit from browser caching, but that benefit is not guaranteed. HTTP byte-range support can allow efficient seeks without downloading the whole audio file, while unsupported ranges can make seeking dependent on already downloaded data. ([MDN buffering and seeking](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Audio_and_video_delivery/buffering_seeking_time_ranges))

The October 10 pilot QA established finite duration metadata for all twenty selected URLs and exercised actual playback for several clips. It did not measure startup distributions for all 349, conduct complete seek tests, test every supported browser, or prove future source-host availability. No new playback-latency or concurrent-user benchmark was run for this assessment.

The defensible expectation is that catalog growth alone should not make each clip much slower if playback remains on demand. Some source files and hosts may nevertheless be slower or unavailable, and we do not control their response time. Hosting the audio ourselves is not automatically faster and would introduce storage, operational and rights requirements.

## Preserve speed while improving resilience

- **On-demand loading:** keep one playing stream; do not preload every source, create an audio element per guide item or launch hundreds of simultaneous metadata probes on page load.
- **Bounded connection preparation:** consider preconnecting only to verified source hosts, with attention to redirects and privacy. Evaluate it against measured cold-cache performance rather than assuming it helps.
- **Tuning stability:** retain the 250 ms settle behavior and cancel obsolete timers/requests. Guard all media callbacks with the selected ID or request generation so a slow old request cannot play after tuning has moved on.
- **Loading feedback:** show “Loading archive audio” and “Buffering,” then a bounded retry/next-recording option. The media \`waiting\` event specifically indicates playback stopped temporarily for lack of data. ([MDN waiting event](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/waiting_event))
- **Failure handling:** preserve the clip ID and log identity on failure; do not silently switch stations. Distinguish unavailable media, buffering and browser playback-policy rejection where possible. One bad source must not disable the receiver.
- **Noise transition:** consider keeping gentle between-station noise during loading and fading it on actual playback. The current implementation mutes noise as soon as a record is selected; changing that is a proposal to review, not an implemented fix.
- **Seek/resume:** test seek and return-to-clip behavior on each serving family. The browser's buffered and seekable ranges can differ, so duration metadata alone does not establish seamless seeking. ([MDN buffered versus seekable ranges](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Audio_and_video_delivery/buffering_seeking_time_ranges))

## Proof-of-concept acceptance tests

- **Catalog coverage:** reconcile all 349 stable IDs, keep 19 inventory holds visible as held, flag all four multi-frequency labels, and retain compilation/segment-review flags. Do not edit the workbook or silently promote release eligibility.
- **Conflict access:** demonstrate all seventeen 4845 kHz recordings and several 5000 kHz alternatives, with stable ID-based selection, no name spoilers, and no simultaneous audio.
- **Dense tuning:** test the 100 Hz-separated carriers, rapid sweeps, fine/coarse controls and tuning away while a slow clip loads. Verify no stale playback, oscillation or uncontrolled request churn.
- **Cold and warm startup:** measure frequency-settle-to-\`playing\` separately from play-request-to-\`playing\`, including the intentional 250 ms delay. Compare median and 95th-percentile results with the twenty-record baseline by host and device; choose a target from that baseline, not an invented guarantee.
- **Network failure:** exercise slow response, offline mode, missing files and browser-denied playback. Ensure a retry/skip path and accessible status messages without an automatic change to another station.
- **Media checker:** validate URLs and metadata at low, bounded concurrency with results saved per unique URL. Add actual playback and seek tests, including both M4A items and compilation assets. Do not interpret metadata success as complete playback or rights clearance.
- **Device matrix:** compare desktop Chromium, Firefox and Safari where available, plus iOS/Android touch behavior. A catalog-sized test on one machine is not a public multi-user capacity test.
- **Long session:** repeatedly tune, switch alternatives, reveal, log, reset and export. Check that abandoned audio elements, event handlers, object URLs and pending requests do not accumulate.
- **Release boundaries:** keep source-hosted audio unchanged, public publication separately authorized, and all QSL features on hold.

## Exact shared-frequency appendix

The following includes all 64 groups among the 345 one-numeric-frequency rows, including held rows. Each entry preserves its stable ID, main-sheet row, station label and original date; the original source page is provided for traceability, not as proof of playback permission or current availability.

`;
for(const g of allGroups.filter(g=>g.count>1)){
  report+=`### ${g.frequency_khz} kHz (${g.count} recordings)\n\n| Inventory ID | Main-sheet row | Station label | Recording date | Inventory status | Original reference |\n|---|---:|---|---|---|---|\n`;
  for(const r of g.records)report+=`| ${r.inventory_id} | ${r.sheet_row} | ${esc(r.station)} | ${esc(r.date)} | ${r.qualified_inventory?'Qualified':'Held'} | ${r.source_page?`[Recording reference](${r.source_page})`:'Not documented'} |\n`;
  report+='\n';
}
const destination=path.join(root,'research/receiver-scale');
fs.mkdirSync(destination,{recursive:true});
fs.writeFileSync(path.join(destination,'full-inventory-collision-audit.json'),JSON.stringify(audit,null,2)+'\n');
fs.writeFileSync(path.join(destination,'Full-Inventory-Receiver-Assessment.md'),report);
console.log(JSON.stringify({
  total:records.length,allSingle:totals(allGroups),qualifiedSingle:totals(qualifiedGroups),
  hosts,payloadBytes:audit.flat_metadata_estimate_bytes_all,reportBytes:Buffer.byteLength(report),
  runtimeChanged:false,benchmarkRun:false
},null,2));
