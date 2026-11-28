#!/usr/bin/env node
// Checks the Reveal Station map data built by tools/build-reveal-geography.py (plan phase 5).
const fs = require('fs'), path = require('path'), assert = require('assert');
const root = path.resolve(__dirname, '..'), app = path.join(root, 'app/heritage-h60'), geo = path.join(app, 'geo');
const load = f => JSON.parse(fs.readFileSync(path.join(geo, f), 'utf8'));
const borders = load('period-borders-1960-1992.json'), regions = load('reveal-regions.json').regions, sidecar = load('reveal-geography.json');
const byId = Object.fromEntries(borders.features.map(f => [f.id, f]));
const day = s => new Date(s + 'T00:00:00Z').getTime();

// Files: sizes, licenses, attribution.
const size = f => fs.statSync(path.join(geo, f)).size;
assert(size('period-borders-1960-1992.json') < 1_000_000, 'period borders under 1 MB');
assert(size('reveal-regions.json') < 200_000, 'fallback regions under 200 KB');
assert(size('reveal-geography.json') < 400_000, 'sidecar under 400 KB');
assert.equal(borders.license, 'CC BY-NC-SA 4.0');
assert(/CShapes 2\.0/.test(borders.attribution));
assert(/CC BY-NC-SA 4\.0/.test(fs.readFileSync(path.join(geo, 'LICENSES.md'), 'utf8')));
assert(/Natural Earth/.test(fs.readFileSync(path.join(geo, 'LICENSES.md'), 'utf8')));

// Period borders: valid date windows overlapping 1960-1992, no overlapping windows for one country.
const perGw = {};
for (const f of borders.features) {
  assert(day(f.start) <= day(f.end), `${f.id} start before end`);
  assert(day(f.start) <= day('1992-12-31') && day(f.end) >= day('1960-01-01'), `${f.id} overlaps the era`);
  assert(['Polygon', 'MultiPolygon'].includes(f.geometry.type) && f.geometry.coordinates.length, `${f.id} has geometry`);
  assert(f.center.length === 2 && Math.abs(f.center[1]) <= 90, `${f.id} center`);
  (perGw[f.gw] ||= []).push(f);
}
for (const [gw, list] of Object.entries(perGw)) {
  list.sort((a, b) => day(a.start) - day(b.start));
  for (let i = 1; i < list.length; i++) assert(day(list[i].start) > day(list[i - 1].end), `gw ${gw} windows do not overlap`);
}

// Every tunable recording on all three bands has exactly one entry; each highlight resolves.
const catalogs = [['60m', 'full-inventory.json'], ['90m', 'band-90m.json'], ['49m', 'band-49m.json']];
const kinds = new Set(['country', 'region', 'republic', 'territory', 'union', 'none']);
let tunable = 0;
for (const [band, file] of catalogs) {
  for (const r of JSON.parse(fs.readFileSync(path.join(app, file), 'utf8')).recordings) {
    const e = sidecar.entries[r.id];
    if (!r.testEligible) { assert(!e, `${r.id} held-back recording has no map entry`); continue; }
    tunable++;
    assert(e, `${band} ${r.inventoryId} has a map entry`);
    assert.equal(e.band, band); assert.equal(e.inventoryId, r.inventoryId); assert.equal(e.countryLabel, String(r.country).trim());
    assert(kinds.has(e.kind), `${r.id} kind`);
    assert(e.eraLabel && e.eraLabel.length > 2, `${r.id} caption`);
    if (e.kind === 'none') { assert.equal(e.highlight, null, `${r.id} no highlight`); continue; }
    const d = day(e.dateUsed);
    for (const id of e.highlight.ids) {
      if (e.highlight.source === 'cshapes') {
        const f = byId[id]; assert(f, `${r.id} -> ${id} exists`);
        assert(day(f.start) <= d && d <= day(f.end), `${r.id} polygon ${id} valid on ${e.dateUsed}`);
      } else assert(regions[id], `${r.id} -> region ${id} exists`);
    }
    if (e.context) { const c = byId[e.context]; assert(c && day(c.start) <= d && d <= day(c.end), `${r.id} context valid on date`); }
    if (e.kind === 'republic' || e.kind === 'union') assert.equal(byId[e.context].gw, 365, `${r.id} inside the USSR`);
    assert(Array.isArray(e.review));
  }
}
// 709 before the 2026-11-27 era extension to 1992.
assert.equal(tunable, 833, 'all 833 tunable recordings');
assert.equal(Object.keys(sidecar.entries).length, 833);

// Spot checks of period decisions.
const find = (band, inv) => Object.values(sidecar.entries).find(e => e.band === band && e.inventoryId === inv);
assert.equal(find('49m', '49M-0058').eraLabel, 'Uzbek SSR');
assert.equal(find('49m', '49M-0072').kind, 'union');
assert.equal(find('60m', 63).eraLabel, 'Karelian ASSR (Russian SFSR)');
assert.equal(find('90m', '90M-0136').eraLabel, 'Zimbabwe Rhodesia');
assert.equal(find('49m', '49M-0108').eraLabel, 'West Germany (Federal Republic of Germany)');
// Era extension to 1992 (2026-11-27): reunified Germany, renamed Congo, late-Soviet republics.
assert.equal(find('49m', '49M-0275').eraLabel, 'Germany'); assert.equal(find('49m', '49M-0275').basis, 'country as labeled in source');
assert.equal(find('60m', 386).eraLabel, 'Republic of the Congo');
assert.equal(find('60m', 392).eraLabel, 'Saint Petersburg (Russian SFSR, USSR)');
assert.equal(find('49m', '49M-0292').eraLabel, 'Estonian SSR'); assert.equal(find('49m', '49M-0290').eraLabel, 'Kazakh SSR');
assert.equal(find('49m', '49M-0291').kind, 'none');
assert.equal(find('60m', 10).dateUsed, '1978-07-01');
assert(find('49m', '49M-0328').marker, 'Vatican City gets a marker');
assert(!find('60m', 10).marker, 'Angola has no marker');
// Owner decisions (October 20, 2026).
const cab = find('60m', 10);
assert.equal(cab.dateLabel, '1970s, timing unknown'); assert.equal(cab.recordist, 'Dan Robinson');
assert.equal(cab.eraLabel, 'Angola'); assert(cab.highlight.ids[0].startsWith('cs:540:1975-11-11'), 'independent Angola');
for (const inv of ['49M-0108', '49M-0158', '49M-0220', '49M-0338']) assert(find('49m', inv).decision && !find('49m', inv).review.length, `${inv} decided`);
assert.equal(sidecar.needsReview, 0); assert.equal(sidecar.decided, 12);
assert.equal(find('49m', '49M-0042').eraLabel, 'Antigua (Antigua and Barbuda)'); assert(find('49m', '49M-0042').marker);
for (const inv of ['49M-0248', '49M-0250']) assert(/^Bonaire/.test(find('49m', inv).eraLabel) && find('49m', inv).marker);
assert.equal(find('49m', '49M-0293').eraLabel, 'Honduras');
assert.equal(find('49m', '49M-0024').transmitterSite, 'Sackville, New Brunswick, Canada');
assert.equal(find('49m', '49M-0072').kind, 'union'); assert.equal(find('49m', '49M-0072').confidence, 'low');

console.log(JSON.stringify({ passed: true, entries: tunable, counts: sidecar.counts, needsReview: sidecar.needsReview,
  periodPolygons: borders.features.length, regions: Object.keys(regions).length }));
