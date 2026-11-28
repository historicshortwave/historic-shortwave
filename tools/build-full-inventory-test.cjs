// Private test payload only. Never changes the workbook or twenty-record baseline.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
const source=JSON.parse(fs.readFileSync(path.join(root,'data/pilot/inventory-snapshot.json')));
const supplementalReferences=JSON.parse(fs.readFileSync(path.join(root,'data/pilot/supplemental-recording-references.json')));
const digest=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,source.workbook_file))).digest('hex');
if(digest!==source.workbook_sha256)throw Error('Stale inventory snapshot');
const compilationIds=new Set([23,24,167]);
const recordings=source.records.map(r=>{
  const reasons=[];
  if(!r.classification.qualified_inventory)reasons.push('inventory_hold');
  if(r.normalization.numeric_frequency_mentions_hz.length!==1)reasons.push('frequency_review');
  if(compilationIds.has(r.inventory_id))reasons.push('compilation_segment_review');
  return {
    id:r.recording_id,inventoryId:r.inventory_id,
    // Snap to the 0.1 kHz dial step, as tools/build-band-catalog.py does; the label keeps the recordist's figure (added 2026-11-27).
    frequencyHz:r.normalization.numeric_frequency_mentions_hz.length===1?Math.round(r.normalization.numeric_frequency_mentions_hz[0]/100)*100:null,
    frequencyLabel:r.source.frequency_label,station:r.source.station_label,date:r.source.recording_date_label,
    time:r.source.time_label,certainty:r.source.date_certainty,audioUrl:r.source.audio_url,
    sourceUrl:r.source.archive_page,collection:r.source.collection,notes:r.source.notes,
    ...(supplementalReferences[r.inventory_id]?{additionalReferences:supplementalReferences[r.inventory_id]}:{}),
    country:r.classification.naswa_entity,scope:r.classification.qualified_core_band?'core':'exception',
    evidence:r.classification.evidence_label,publicationReview:'pending',
    testEligible:reasons.length===0,reviewReasons:reasons
  };
}).sort((a,b)=>a.inventoryId-b.inventoryId);
if(recordings.length!==410||new Set(recordings.map(r=>r.id)).size!==410)throw Error('Invalid inventory coverage');
const active=recordings.filter(r=>r.testEligible),review=recordings.filter(r=>!r.testEligible);
const counts={
  total:recordings.length,tunable:active.length,review:review.length,
  inventoryHolds:recordings.filter(r=>r.reviewReasons.includes('inventory_hold')).length,
  frequencyReview:recordings.filter(r=>r.reviewReasons.includes('frequency_review')).length,
  compilationReview:recordings.filter(r=>r.reviewReasons.includes('compilation_segment_review')).length,
  frequencies:new Set(active.map(r=>r.frequencyHz)).size
};
const payload={
  schemaVersion:'1.1',name:'Heritage H-60: Full Inventory Test',
  status:'private_source_hosted_resilience_test_not_public_release',
  workbookSha256:digest,order:'fixed_ascending_inventory_id',
  dialMinHz:4700000,dialMaxHz:5085000,counts,recordings
};
fs.writeFileSync(path.join(root,'app/heritage-h60/full-inventory.json'),JSON.stringify(payload,null,2)+'\n');
console.log(JSON.stringify(counts,null,2));
