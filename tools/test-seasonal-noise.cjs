'use strict';
const assert = require('node:assert/strict');
const { conditions, levelsDb, rates, beds, mix, outputGain } = require('../app/heritage-h60/seasonal-noise.js');
const manifest = require('../app/heritage-h60/audio/seasonal/manifest.json');
let checks = 0;
function equal(actual, expected) { assert.deepEqual(actual, expected); checks++; }
for (const [date, season, easternDate] of [
  ['2026-03-01T04:59:59Z', 'winter', '2026-02-28'],
  ['2026-03-01T05:00:00Z', 'spring', '2026-03-01'],
  ['2026-06-01T03:59:59Z', 'spring', '2026-05-31'],
  ['2026-06-01T04:00:00Z', 'summer', '2026-06-01'],
  ['2026-09-01T03:59:59Z', 'summer', '2026-08-31'],
  ['2026-09-01T04:00:00Z', 'autumn', '2026-09-01'],
  ['2026-12-01T04:59:59Z', 'autumn', '2026-11-30'],
  ['2026-12-01T05:00:00Z', 'winter', '2026-12-01'],
  ['2027-01-01T04:59:59Z', 'winter', '2026-12-31'],
  ['2027-01-01T05:00:00Z', 'winter', '2027-01-01'],
  ['2026-03-08T06:59:59Z', 'spring', '2026-03-08'],
  ['2026-03-08T07:00:00Z', 'spring', '2026-03-08'],
  ['2026-11-01T05:59:59Z', 'autumn', '2026-11-01'],
  ['2026-11-01T06:00:00Z', 'autumn', '2026-11-01']
]) {
  const result = conditions(new Date(date));
  equal(result.season, season);
  equal(result.easternDate, easternDate);
}
// The season comes only from the date; a web-address setting is never read.
for (const [iso, season] of [['2026-01-15T17:00:00Z', 'winter'], ['2026-04-15T16:00:00Z', 'spring'],
                             ['2026-07-15T16:00:00Z', 'summer'], ['2026-10-12T01:58:00Z', 'autumn']]) {
  const result = conditions(new Date(iso), '?season=winter');
  equal(result.season, season);
  equal(result.actual, season);
  equal('override' in result, false);
  equal(result.db, levelsDb[season]);
  equal(result.rate, rates[season]);
  equal(result.bed, beds[season]);
}
equal(conditions(new Date('2026-10-12T01:58:00Z')).easternDate, '2026-10-11');
equal(levelsDb, { winter: 0, spring: 1, summer: 2, autumn: 1 });
equal(manifest.levelsDb, levelsDb);
equal(manifest.crashesPerMinute, rates);
equal(manifest.seasonBeds, beds);
for (const entry of Object.values(manifest.beds)) {
  equal(entry.durationSeconds, 75);
  assert(entry.peak < 1); checks++;
  assert(entry.seamStep < entry.ordinaryStepP999); checks++;
  assert(Math.abs(entry.rms * entry.normalizationGain - .12) < 1e-8); checks++;
}
equal(manifest.crashes.length, 6);
for (const crash of manifest.crashes) { equal(crash.durationSeconds, .9); assert(crash.peak < 1); checks++; }
assert(manifest.beds.winter.deBuzz.harmonicSuppressionDb < -15); checks++;
const desired = {power:true,enabled:true,gain:.45,selected:false,mediaState:'idle'};
equal(mix, { between:.24, loading:.08 });
for (const season of ['winter','spring','summer','autumn']) {
  const gain = outputGain(desired, season, true);
  assert(gain * .12 > .012); checks++;
  assert(Math.abs(20*Math.log10(gain/outputGain(desired,'winter',true))-levelsDb[season])<1e-10); checks++;
  equal(outputGain({...desired,power:false},season,true),0);
  equal(outputGain({...desired,enabled:false},season,true),0);
  equal(outputGain({...desired,gain:0},season,true),0);
  equal(outputGain(desired,season,false),0);
  for(const mediaState of ['playing','paused','ended','error']) {
    equal(outputGain({...desired,selected:true,mediaState},season,true),0);
  }
  for(const mediaState of ['loading','buffering']) {
    assert(Math.abs(outputGain({...desired,selected:true,mediaState},season,true)-gain/3)<1e-12); checks++;
  }
}
console.log(`${checks} seasonal date, levels and asset assertions passed.`);
