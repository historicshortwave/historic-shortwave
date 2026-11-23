// Read-only checks for the staged 90 m and 49 m catalogs (plan phase 1).
// Run from the project root: node tools/test-band-catalogs.cjs
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const root = path.resolve(__dirname, '..');
const C = require(path.join(root, 'app/heritage-h60/catalog.js'));
const load = f => JSON.parse(fs.readFileSync(path.join(root, f)));

const expected = {
  '90m': {total: 141, tunable: 125, compilation: 10, mirror: 6, era: 0, min: 3150000, max: 3500000},
  '49m': {total: 350, tunable: 261, compilation: 5, mirror: 8, era: 76, min: 5850000, max: 6350000},
};
const summary = {};
for (const [band, e] of Object.entries(expected)) {
  const cat = load(`data/bands/band-${band}.json`), recs = cat.recordings;
  assert.equal(fs.readFileSync(path.join(root, `app/heritage-h60/band-${band}.json`), 'utf8'), fs.readFileSync(path.join(root, `data/bands/band-${band}.json`), 'utf8'), 'receiver copy matches the built catalog');
  assert.equal(cat.band, band);
  assert.equal(cat.dialMinHz, e.min); assert.equal(cat.dialMaxHz, e.max);
  assert.ok(cat.defaultHz > e.min && cat.defaultHz < e.max);
  assert.equal(recs.length, e.total); assert.equal(cat.counts.total, e.total);
  assert.equal(new Set(recs.map(r => r.id)).size, e.total, 'unique ids');
  assert.equal(new Set(recs.map(r => r.inventoryId)).size, e.total, 'unique candidate ids');
  assert.deepEqual(recs.map(r => r.sortKey), [...recs.map(r => r.sortKey)].sort((a, b) => a - b), 'fixed order');
  const tun = recs.filter(r => r.testEligible);
  assert.equal(tun.length, e.tunable); assert.equal(cat.counts.tunable, e.tunable);
  const by = cat.counts.byReason;
  assert.equal(by.compilation_segment_review || 0, e.compilation);
  assert.equal(by.mirror_duplicate || 0, e.mirror);
  assert.equal(by.outside_era || 0, e.era);
  for (const r of recs) {
    assert.equal(r.testEligible, r.reviewReasons.length === 0, `${r.inventoryId} eligibility matches reasons`);
    assert.ok(/^https:\/\//.test(r.audioUrl), `${r.inventoryId} https audio`);
  }
  for (const r of tun) {
    assert.ok(Number.isInteger(r.frequencyHz) && r.frequencyHz % 100 === 0, `${r.inventoryId} on the 0.1 kHz step`);
    assert.ok(r.frequencyHz >= e.min && r.frequencyHz <= e.max, `${r.inventoryId} inside dial`);
    assert.ok(!/^Compilation/.test(r.recordingType || ''), `${r.inventoryId} compilation held`);
    const ys = (String(r.date).match(/(?<!\d)(19\d\d|20\d\d)(?!\d)/g) || []).map(Number);
    assert.ok(ys.length && Math.min(...ys) >= 1960 && Math.max(...ys) <= 1989, `${r.inventoryId} in era`);
  }
  assert.equal(new Set(tun.map(r => r.audioUrl)).size, tun.length, 'no audio file tunable twice');
  // Carrier grouping and reachability with the receiver's existing catalog code.
  const groups = C.buildGroups(tun);
  assert.equal(groups.reduce((n, g) => n + g.records.length, 0), tun.length);
  assert.equal(groups.length, cat.counts.frequencies);
  for (const g of groups) assert.equal(C.findGroup(groups, g.hz)?.hz, g.hz, `unreachable ${g.hz}`);
  for (const g of groups) assert.deepEqual(g.records.map(r => r.sortKey), g.records.map(r => r.sortKey).sort((x, y) => x - y), `alternatives at ${g.hz} in candidate order`);
  for (let i = 1; i < groups.length; i++)
    assert.ok(groups[i - 1].hz + groups[i - 1].retainRadius < groups[i].hz - groups[i].retainRadius, 'groups do not overlap');
  assert.equal(C.findGroup(groups, e.min), null, 'dial start is clear');
  assert.equal(C.findGroup(groups, e.max), null, 'dial end is clear');
  const busiest = groups.reduce((a, g) => g.records.length > a.records.length ? g : a);
  summary[band] = {total: e.total, tunable: tun.length, frequencies: groups.length,
    busiestKHz: busiest.hz / 1000, busiestCount: busiest.records.length};
}
// The 60 m catalog is untouched by this phase.
const f60 = load('app/heritage-h60/full-inventory.json');
assert.equal(f60.recordings.length, 349); assert.equal(f60.counts.tunable, 323);
assert.equal(f60.dialMinHz, 4700000); assert.equal(f60.dialMaxHz, 5085000);
console.log(JSON.stringify({passed: true, ...summary, '60m': {total: 349, tunable: 323}}));
