const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),C=require(path.join(root,'app/heritage-h60/catalog.js'));
const p=JSON.parse(fs.readFileSync(path.join(root,'app/heritage-h60/pilot.json')));
const f=JSON.parse(fs.readFileSync(path.join(root,'app/heritage-h60/full-inventory.json')));
const groups=C.buildGroups(f.recordings),pg=C.buildGroups(p.recordings);
assert.equal(p.recordings.length,20);assert.equal(pg.length,20);
assert.equal(f.recordings.length,349);assert.equal(new Set(f.recordings.map(r=>r.id)).size,349);
assert.equal(f.counts.tunable,323);assert.equal(f.counts.review,26);
assert.equal(f.counts.inventoryHolds,19);assert.equal(f.counts.frequencyReview,4);
assert.equal(f.counts.compilationReview,3);
assert.equal(groups.reduce((n,g)=>n+g.records.length,0),323);
for(const g of groups){
  assert.equal(C.findGroup(groups,g.hz)?.hz,g.hz,`Unreachable carrier ${g.hz}`);
  assert.deepEqual(g.records.map(r=>r.inventoryId),g.records.map(r=>r.inventoryId).sort((a,b)=>a-b));
  assert.ok(g.records.every(r=>r.testEligible&&!r.reviewReasons.length));
}
assert.equal(groups.find(g=>g.hz===4845000).records.length,17);
assert.equal(C.findGroup(groups,4814900)?.hz,4814900);
assert.equal(C.findGroup(groups,4815000,4814900)?.hz,4815000);
assert.equal(C.findGroup(groups,4814950),null,'Dense midpoint should retain a gap');
assert.equal(C.findGroup(groups,4829950),null);
assert.equal(C.findGroup(groups,4698000),null);
assert.equal(C.findGroup(groups,5085000),null);
for(let i=1;i<groups.length;i++)assert.ok(groups[i-1].hz+groups[i-1].retainRadius<groups[i].hz-groups[i].retainRadius);
for(const id of [23,24,167,349,123,22,174,299])assert.equal(f.recordings.find(r=>r.inventoryId===id).testEligible,false);
console.log(JSON.stringify({passed:true,total:349,tunable:323,review:26,groups:groups.length,baseline:20,exact4845Alternatives:17}));
