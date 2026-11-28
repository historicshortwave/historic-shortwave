// Reveal Station map (plan phase 6).
// Nothing here runs or downloads until the first reveal. The page keeps working if any of it fails.
// Data: geo/period-borders-1960-1992.json (CShapes 2.0, CC BY-NC-SA 4.0),
//       geo/reveal-regions.json (Natural Earth, public domain), geo/reveal-geography.json (one entry per recording).
// Drawing: vendor/d3-geo (ISC), loaded on demand. No tiles or third-party requests.
(function () {
  'use strict';
  const SIZE = 240, R = 108, NS = 'http://www.w3.org/2000/svg';
  let dataPromise = null, request = 0, frame = 0;

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src; s.async = false; s.onload = resolve; s.onerror = () => reject(new Error('Could not load ' + src));
      document.head.append(s);
    });
  }
  function loadJson(url) {
    return fetch(url).then(r => { if (!r.ok) throw new Error(url + ' ' + r.status); return r.json(); });
  }
  function load() {
    if (!dataPromise) {
      const libs = window.d3?.geoOrthographic ? Promise.resolve()
        : loadScript('./vendor/d3-array.min.js').then(() => loadScript('./vendor/d3-geo.min.js'));
      dataPromise = Promise.all([libs, loadJson('./geo/period-borders-1960-1992.json'), loadJson('./geo/reveal-regions.json'), loadJson('./geo/reveal-geography.json')])
        .then(([, borders, regions, sidecar]) => ({ borders: borders.features, byId: new Map(borders.features.map(f => [f.id, f])), regions: regions.regions, entries: sidecar.entries }))
        .catch(error => { dataPromise = null; throw error; });  // allow a retry on the next reveal
    }
    return dataPromise;
  }

  const feature = item => ({ type: 'Feature', properties: { id: item.id }, geometry: item.geometry });
  const dayOf = s => Date.parse(s + 'T00:00:00Z');
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  function niceDate(iso) { const [y, m, d] = iso.split('-').map(Number); return `${d} ${MONTHS[m - 1]} ${y}`; }

  function bordersLine(entry) {
    const [y, m] = entry.dateUsed.split('-').map(Number);
    if (entry.dateBasis === 'exact') return `Borders as of ${niceDate(entry.dateUsed)}`;
    if (entry.dateBasis === 'year') return `Borders as of mid-${y}; recording dated to the year only`;
    if (entry.dateBasis === 'month') return `Borders as of mid-${MONTHS[m - 1]} ${y}; recording dated to the month only`;
    return `Borders as of ${niceDate(entry.dateUsed)}; recording date: ${entry.dateLabel || entry.date}`;
  }
  function captionParts(entry) {
    const lines = [];
    let main = entry.eraLabel;
    if (entry.shownAs) main += ` · shown as ${entry.shownAs}`;
    if (entry.confidence === 'approximate' && !/approximate/i.test(main)) main += ' · approximate area';
    lines.push(['map-caption-main', main]);
    if (entry.transmitterSite) lines.push(['map-caption-line', `Transmitter: ${entry.transmitterSite}`]);
    if (entry.kind !== 'none' && entry.dateUsed) lines.push(['map-caption-line', bordersLine(entry)]);
    // The recordist now appears in the credit line under the station details (credits.json), not on the map card.
    return lines;
  }

  function el(tag, attrs = {}, parent) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.append(n);
    return n;
  }

  function draw(svg, data, entry, animate) {
    const d3 = window.d3, day = dayOf(entry.dateUsed);
    const highlight = entry.highlight.ids.map(id => entry.highlight.source === 'cshapes' ? data.byId.get(id) : data.regions[id]).filter(Boolean);
    if (!highlight.length) throw new Error('Highlight shape missing for ' + entry.inventoryId);
    const target = { type: 'FeatureCollection', features: highlight.map(feature) };
    const [lon, lat] = entry.center;
    const projection = d3.geoOrthographic().translate([SIZE / 2, SIZE / 2]).clipAngle(90).precision(0.3).rotate([-lon, -lat]);
    // Zoom so the highlight fills about half the card, but never smaller than the whole globe.
    projection.scale(R);
    const [[x0, y0], [x1, y1]] = d3.geoPath(projection).bounds(target);
    const extent = Math.max(x1 - x0, y1 - y0, 1);
    const scale = Math.max(R, Math.min(R * 7, R * (SIZE * 0.5) / extent));
    projection.scale(scale);
    const path = d3.geoPath(projection);
    const context = data.borders.filter(f => dayOf(f.start) <= day && day <= dayOf(f.end) && !entry.highlight.ids.includes(f.id));

    svg.replaceChildren();
    const defs = el('defs', {}, svg), clipId = 'map-clip-' + Math.random().toString(36).slice(2);
    el('rect', { id: clipId + '-r', x: 0, y: 0, width: SIZE, height: SIZE, rx: 6 }, el('clipPath', { id: clipId }, defs));
    const g = el('g', { 'clip-path': `url(#${clipId})` }, svg);
    const sphere = el('path', { class: 'map-ocean' }, g);
    const grat = el('path', { class: 'map-graticule' }, g);
    const land = el('path', { class: 'map-land' }, g);
    const hl = el('path', { class: 'map-highlight', 'data-testid': 'map-highlight' }, g);
    const ring = entry.marker ? el('circle', { class: 'map-ring', r: 11, 'data-testid': 'map-ring' }, g) : null;
    const graticule = d3.geoGraticule10();
    const contextCollection = { type: 'FeatureCollection', features: context.map(feature) };

    function render(rotation) {
      projection.rotate(rotation);
      sphere.setAttribute('d', path({ type: 'Sphere' }));
      grat.setAttribute('d', path(graticule) || '');
      land.setAttribute('d', path(contextCollection) || '');
      hl.setAttribute('d', path(target) || '');
      if (ring) {
        const p = projection(entry.center), visible = d3.geoDistance(entry.center, [-rotation[0], -rotation[1]]) < Math.PI / 2;
        ring.setAttribute('cx', p ? p[0] : -99); ring.setAttribute('cy', p ? p[1] : -99); ring.style.display = visible ? '' : 'none';
      }
    }
    cancelAnimationFrame(frame);
    const end = [-lon, -lat];
    if (!animate) { render(end); return context.length; }
    const start = [-lon + 70, -lat * 0.4], t0 = performance.now(), ms = 900;
    const step = now => {
      if (!svg.isConnected) return;
      const t = Math.min(1, (now - t0) / ms), e = 1 - Math.pow(1 - t, 3);
      render([start[0] + (end[0] - start[0]) * e, start[1] + (end[1] - start[1]) * e]);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    render(start); frame = requestAnimationFrame(step);
    return context.length;
  }

  function card(container, record) {
    const fig = document.createElement('figure');
    fig.className = 'reveal-map'; fig.dataset.testid = 'reveal-map'; fig.dataset.record = record.id; fig.setAttribute('aria-busy', 'true');
    const status = document.createElement('p'); status.className = 'map-status'; status.textContent = 'Loading map…';
    fig.append(status); container.append(fig);
    return fig;
  }

  async function show(record, container) {
    const token = ++request;
    const fig = card(container, record);
    const stale = () => token !== request || !fig.isConnected;
    let data;
    try { data = await load(); } catch (error) {
      if (stale()) return;
      fig.removeAttribute('aria-busy'); fig.dataset.state = 'error';
      fig.querySelector('.map-status').textContent = 'Map unavailable right now.';
      console.warn('[reveal map]', error);
      return;
    }
    if (stale()) return;
    const entry = data.entries[record.id];
    fig.replaceChildren(); fig.removeAttribute('aria-busy');
    if (!entry || entry.kind === 'none' || !entry.highlight) {
      fig.dataset.state = 'none';
      const p = document.createElement('p'); p.className = 'map-status';
      p.textContent = entry ? `${entry.eraLabel}. Transmitter country not established.` : 'Transmitter country not established.';
      fig.append(p);
      return;
    }
    const parts = captionParts(entry);
    const svg = el('svg', { viewBox: `0 0 ${SIZE} ${SIZE}`, width: SIZE, height: SIZE, role: 'img', class: 'map-svg',
      'aria-label': `Map highlighting ${parts[0][1]}` });
    fig.append(svg);
    const caption = document.createElement('figcaption');
    for (const [cls, text] of parts) { const s = document.createElement('span'); s.className = cls; s.textContent = text; caption.append(s); }
    const credit = document.createElement('span'); credit.className = 'map-credit';
    // Attribution required by CC BY-NC-SA 4.0: creator, source link, license link, and that the data was modified.
    const link = (text, href) => { const a = document.createElement('a'); a.href = href; a.textContent = text; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; };
    credit.append('Borders: ', link('CShapes 2.0', 'https://icr.ethz.ch/data/cshapes/'), ' (Schvitz et al.), simplified, ',
      Object.assign(link('CC BY-NC-SA 4.0', 'https://creativecommons.org/licenses/by-nc-sa/4.0/'), { className: 'nowrap' }));
    if (entry.highlight.source === 'natural-earth') credit.append(' · Area: Made with ', link('Natural Earth', 'https://www.naturalearthdata.com/'));
    const more = document.createElement('button'); more.type = 'button'; more.className = 'map-credits-button'; more.textContent = 'Map credits';
    more.dataset.testid = 'button-map-credits';
    more.addEventListener('click', () => {
      const dialog = document.getElementById('about-dialog'); if (!dialog) return;
      if (!dialog.open) dialog.showModal();
      document.getElementById('map-credits')?.scrollIntoView({ block: 'start' });
    });
    credit.append(' · ', more);
    caption.append(credit); fig.append(caption);
    try {
      const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      fig.dataset.context = draw(svg, data, entry, !reduce);
      fig.dataset.animated = reduce ? 'no' : 'yes';
      fig.dataset.state = 'drawn'; fig.dataset.highlight = entry.highlight.ids.join(' ');
    } catch (error) {
      svg.remove(); fig.dataset.state = 'error';
      const p = document.createElement('p'); p.className = 'map-status'; p.textContent = 'Map unavailable for this recording.'; fig.prepend(p);
      console.warn('[reveal map]', error);
    }
  }

  function clear() { request++; cancelAnimationFrame(frame); }

  window.RevealMap = { show, clear, _load: load };
})();
