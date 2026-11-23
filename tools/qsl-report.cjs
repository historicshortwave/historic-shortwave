// Generate a research register from fetched evidence; never edits inventory/app data.
const fs = require('fs');
const path = require('path');
const base = path.resolve(__dirname, '../research/qsl');
const rows = JSON.parse(fs.readFileSync(path.join(base, 'reviewed-matches.json')));
const galleries = JSON.parse(fs.readFileSync(path.join(base, 'gallery-links.json')));
const clean = s => (s || '').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
  .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, '').replace(/<[^>]*>/g, ' ')
  .replace(/&nbsp;|&#160;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"')
  .replace(/&#8220;|&#8221;/g, '"').replace(/\s+/g, ' ').trim();
const pages = new Map();
for (const f of fs.readdirSync(base).filter(f => /\.json$/.test(f))) {
  try {
    for (const p of JSON.parse(fs.readFileSync(path.join(base, f))).pages || []) {
      if (p.url && !p.error && (p.raw_html || p.content)) pages.set(p.url, {
        url: p.url, title: p.title || '', text: clean(p.raw_html || p.content),
        image_count: [...(p.raw_html || '').matchAll(/<img\b/gi)].length,
        evidence_file: f
      });
    }
  } catch {}
}
const full = s => s.startsWith('http') ? s : 'http://www.swlqslmuseum.com/' + s;
const corrections = {
  18: ['https://medxr.blogspot.com/p/qsl-archives-5.html', 'Radio Bolívar verification is captioned 4770 kHz, 18 August 1971; gallery also contains letters.'],
  52: ['https://radiotapes.com/qsl_africa', 'Africa No. 1 is explicitly listed. Earlier guessed museum detail URL failed and is not used.'],
  131: ['https://shortwavearchive.com/archive?year=2022', '2022 archive listing includes VLT4 ABC Port Moresby, 3 May 1971, with a QSL credited to Radio Heritage Foundation. Individual article fetch returned 403; use the fetched annual listing.'],
  212: ['https://radiotapes.com/qsl_clandestine/', 'A Voz da Resistencia do Galo Negro is explicitly listed.'],
  238: ['https://radiotapes.com/qsl_africa', 'Radio Madagascar is explicitly listed; exact historic branding/design needs visual review. Earlier guessed museum detail URL failed and is not used.'],
  242: ['https://radiotapes.com/qsl_clandestine/', 'Radio Truth is explicitly listed; do not substitute Guatemala Radio Verdad.'],
  262: ['https://radiotapes.com/qsl_clandestine/', 'La Voz de la UNO is explicitly listed.']
};
const reports = {
  5: ['https://www.schoechi.de/as-pru01.html', 'Huanta 2000: 4746.6/4746.5 kHz verification letter/postcard reports; 1992 reception and later replies.'],
  62: ['https://www.schoechi.de/as-b04.html', 'Difusora Londrina: 4815 kHz; 1980 letter/postcard report and later aerial-view QSL-card reports.'],
  63: ['https://www.schoechi.de/as-b04.html', 'Difusora Londrina: 4815 kHz; 1980 letter/postcard report and later aerial-view QSL-card reports.'],
  73: ['http://www.pateplumaradio.com/south/venez/venenote.html', 'Radio Tachira, San Cristobal, 4830 kHz is described as a good letter verifier; no card scan established.'],
  74: ['http://www.pateplumaradio.com/south/venez/venenote.html', 'Radio Tachira, San Cristobal, 4830 kHz is described as a good letter verifier; no card scan established.'],
  76: ['https://www.schoechi.de/as-pru01.html', 'Difusora Huanta: 4888 kHz email verification reported in 2004; not a located card scan.'],
  84: ['https://www.radioheritage.com/playdx/Play-DX/www.playdx.com/news/news017.html', 'Radio Interoceanica: 4840 kHz full-data email verification reported, 70-day reply; no card scan established.'],
  104: ['https://www.schoechi.de/as-pru02.html', 'Pampas: 4855 kHz certificate/postcard reported in 1983.'],
  112: ['https://www.schoechi.de/as-bol.html', '16 de Marzo: 4865 kHz, two prepared cards and personal letter reported in 1999.'],
  135: ['https://swling.com/blog/tag/ecuador/', 'Don Moore reports obtaining Centinela del Sur QSLs in March 1985. Displayed business card is not itself a QSL.'],
  136: ['https://swling.com/blog/tag/ecuador/', 'Don Moore reports obtaining Centinela del Sur QSLs in March 1985. Displayed business card is not itself a QSL.'],
  140: ['https://www.schoechi.de/as-pru01.html', 'Chanchamayo: 4895 kHz prepared card and station card reported in 2000; source explicitly says station card is not really a QSL card.'],
  171: ['https://www.schoechi.de/as-pru01.html', 'Ondas del Titicaca: 4922 kHz letter/prepared-card replies in 1999, including an old 1983 reception.'],
  208: ['https://www.schoechi.de/as-pru02.html', 'San Miguel: 4965/4966 kHz prepared-card replies reported in 1999–2000; do not confuse the 5500 kHz San Miguel de Pallaques entries.'],
  237: ['https://www.schoechi.de/as-clm02.html', 'Surcolombiana, Neiva: 5010 kHz verification letter; 5 April 1980 reception, 19 May 1980 reply.'],
  287: ['https://www.schoechi.de/as-pru02.html', 'Radio Mundo: 5082.5 kHz prepared-card verification for a November 1993 reception, reported in 2000.']
};
// Potential false matches are held, not silently corrected in the master.
const holds = {
  1: ['https://www.schoechi.de/as-pru01.html', 'Radio Imperio verification reports found for Chiclayo 4389 kHz; master recording is 4705.1 kHz. Same outlet/era not established.'],
  132: ['https://www.schoechi.de/au-png.html', 'NBC Port Moresby/Karai cards reported at 4890 kHz, but generic NBC label requires exact outlet attribution.'],
  137: ['https://www.schoechi.de/au-png.html', 'NBC Port Moresby/Karai cards reported at 4890 kHz, but generic NBC label requires exact outlet attribution.'],
  272: ['http://www.swlqslmuseum.com/culture.htm', 'Gallery caption is Radio Cultura do Pará, whereas master says Cultural do Para. Likely candidate, but the name equivalence is not yet proven.']
};
const allLinks = Object.values(galleries).flatMap(g => g.links);
for (const x of rows) {
  if (corrections[x.i]) {
    x.status = 'Located'; [x.match_url, x.match_note] = corrections[x.i];
  }
  if (reports[x.i]) {
    x.status = 'Reported only'; [x.match_url, x.match_note] = reports[x.i];
  }
  if (holds[x.i]) {
    x.status = 'Related'; [x.match_url, x.match_note] = holds[x.i];
  }
  x.evidence_url = '';
  x.caption = '';
  x.source_years = [];
  if (x.status === 'Located') {
    const p = pages.get(x.match_url);
    const link = allLinks.find(l => l.url === x.match_url);
    if (p) {
      x.status = 'Gallery located';
      x.evidence_url = x.match_url;
      if (x.match_url.includes('swlqslmuseum')) {
        const h = p.text.split(/Contributed|Courtesy|QSL From The/i)[0];
        x.caption = h.replace(/^.*?The SWL QSL (?:Card )?Museum\s*/i, '').slice(0, 360);
        if (x.caption.includes('\uFFFD')) x.caption = '';
        x.source_years = [...new Set((h.match(/\b(?:19|20)\d{2}\b/g) || []))];
      }
    } else if (link && pages.has(link.index_url)) {
      x.status = 'Indexed only';
      x.evidence_url = link.index_url;
      x.caption = link.title;
      x.match_note = 'Fetched museum index lists this verification page; detail page could not be verified.';
    } else {
      x.status = 'Not located';
      x.match_note = 'Provisional candidate could not be substantiated by fetched evidence.';
    }
  } else if (x.status === 'Unresolved') x.status = 'Not located';
  if (!x.evidence_url && x.match_url && pages.has(x.match_url)) x.evidence_url = x.match_url;
  if (!x.evidence_url && x.index_url && pages.has(x.index_url)) x.evidence_url = x.index_url;
  if (!x.evidence_url && [12,198].includes(x.i)) x.evidence_url = 'https://radiotapes.com/qsl_clandestine/';
  if (!x.evidence_url && x.i===44) x.evidence_url = 'https://radiotapes.com/qsl_north_central_america';
  x.rights = 'Not cleared';
  x.period_match = 'n.a.; source-labelled years are not proof of the design used on the recording date';
  x.fallback = x.status === 'Identity hold' ? 'Hold award until identity resolved'
    : ['Gallery located','Indexed only'].includes(x.status) ? 'Generic commemorative card until artwork approval'
    : 'Generic commemorative card; identity review where flagged';
}
const counts = rows.reduce((a,x) => (a[x.status]=(a[x.status]||0)+1,a),{});
const coverage = rows.reduce((a,x) => (a[x.status]=(a[x.status]||0)+x.records.length,a),{});
const md = s => String(s ?? 'n.a.').replace(/\|/g, '\\|').replace(/\n/g, ' ');
const cite = (url,label='Verification gallery') => url ? `[${label}](${url})` : 'n.a.';
const stationRef = x => `QSL-${String(x.i+1).padStart(3,'0')}`;
const pilot = JSON.parse(fs.readFileSync(path.resolve(base,'../../app/heritage-h60/pilot.json'))).recordings;
let out = `# Master Station QSL Availability Register\n\nResearch date: 11 October 2026. Scope: the main “60m SWBC recordings 1960-89” worksheet only, containing 349 recording rows and 288 exact station labels. These labels include aliases, spelling variants and mixed/uncertain identifications; they are not a count of distinct broadcasters. This is an availability-and-clearance research register, not a release-ready artwork library.\n\nThe master workbook and receiver code were not changed. Every master label is retained below, with stable recording IDs, original frequency/date fields and a source-backed availability status. The final appendix retains all 349 recording mappings.\n\n## Results\n\n| Evidence category | Exact labels | Recording rows |\n|---|---:|---:|\n`;
for (const status of ['Gallery located','Indexed only','Reported only','Related','Identity hold','Not located']) out += `| ${status} | ${counts[status]||0} | ${coverage[status]||0} |\n`;
out += `\n- **Gallery located:** a fetched verification page/gallery contains an explicit station listing or QSL caption. This can be a card, letter, or prepared card; it does not mean that every image has been visually inspected or that reproduction is licensed.\n- **Indexed only:** the fetched QSL index explicitly links the station, but the detail page could not be verified. Treat this as a lead rather than a reviewed image.\n- **Reported only:** a fetched collector report establishes that a verification was received; no usable scan was located in the checked sources.\n- **Related:** a service, locality, frequency, spelling, or historical-branding issue prevents a confident one-to-one assignment.\n- **Identity hold:** the master has an unidentified, composite or conflicting attribution. Resolve identity before an award is assigned.\n- **Not located:** n.a. in the checked sources, not proof that no QSL survives. Country indexes, regional galleries and targeted station searches were checked; remaining gaps need collector/archive follow-up.\n\n**No historical artwork is cleared for inclusion in listener downloads by this research.** RadioTapes explicitly prohibits copying and reposting without permission, Glenn Hauser also requires permission, and the Kock archive says normal copyright applies. Public visibility and ownership of a physical card are not a license to redistribute the broadcaster's artwork. ([RadioTapes](https://radiotapes.com/qsl_south_america), [Glenn Hauser QSL collection](http://www.worldofradio.com/QSL.html), [Kock DX archive](https://www.filatelia.fi/dx/index.html))\n\n## What is promising\n\n- **Regional coverage:** the museum explicitly indexes separate RRI regional stations and numerous Peruvian, Bolivian, Brazilian, Colombian and Ecuadorian broadcasters. Use the station-specific source, not a generic national-service QSL. ([Indonesia museum index](http://www.swlqslmuseum.com/indomain.htm), [Peru museum index](http://www.swlqslmuseum.com/perumain.htm), [Bolivia museum index](http://www.swlqslmuseum.com/boliviamain.htm), [Brazil museum index](http://www.swlqslmuseum.com/brazilmain.htm), [Colombia museum index](http://www.swlqslmuseum.com/columbiamain.htm), [Ecuador museum index](http://www.swlqslmuseum.com/equadormain.htm))\n- **Period-labelled examples:** ELWA lists 1968, 1969 and 1970 examples, Baku lists 1968 and 1975, Lara lists 1971 and 1977, Tawantinsuyu lists 1972, and 4VEH lists 1970, 1972, 1976 and 1978. These are strong candidates for later artwork inspection, not confirmation that the same design was used on each recording date. ([ELWA](http://www.swlqslmuseum.com/elwa.htm), [Baku](http://www.swlqslmuseum.com/baku.htm), [Lara](http://www.swlqslmuseum.com/lara.htm), [Tawantinsuyu](http://www.swlqslmuseum.com/rtawa.html), [4VEH](http://www.swlqslmuseum.com/haiti.htm))\n- **Unusual services:** RadioTapes has the clandestine services A Voz da Resistencia do Galo Negro, Radio Truth and La Voz de la UNO, and its regional galleries list WWV and WWVH verifications. ([Clandestine gallery](https://radiotapes.com/qsl_clandestine/), [WWV gallery](https://radiotapes.com/qsl_north_central_america), [WWVH gallery](https://radiotapes.com/qsl_oceana))\n- **Later-only examples:** Tarma's page labels its QSL 1992, La Voz de los Caras 1995, Onda Azul 1990 and San Martín 1990. These establish surviving verifications but should not be presented as proven 1960s–1980s artwork. ([Tarma](http://www.swlqslmuseum.com/peru23.htm), [La Voz de los Caras](http://www.swlqslmuseum.com/equador3.htm), [Onda Azul](http://www.swlqslmuseum.com/peru6.htm), [San Martín](http://www.swlqslmuseum.com/sanmartinperu.htm))\n- **Reported, not scanned:** Pampas has a reported 1983 certificate/postcard, Surcolombiana a reported 1980 letter, and Difusora Londrina reported 1980 and later verifications. These support focused collector requests, but not a download button pointing to a scan. ([Pampas reports](https://www.schoechi.de/as-pru02.html), [Surcolombiana reports](https://www.schoechi.de/as-clm02.html), [Londrina reports](https://www.schoechi.de/as-b04.html))\n\n## Receiver implementation recommendation\n\nKeep the QSL feature on the TBD list; do not implement or distribute artwork yet. The existing session-only log and explicit-click Markdown download decisions remain unchanged.\n\n- **Immediate fallback:** use the user's approved blank artwork with a large station-name stamp and Courier or Times 12-point details. Label the output “Commemorative archive-listening QSL · Not station-issued.” Do not use a historical collector's signature, name, address, report date, or reception claim as the new listener's data.\n- **Date model:** preserve the original broadcast date from the selected recording, including unknown or partial dates, and separately add the listener's logging date in US Eastern time. The date on a source QSL is evidence about that historical verification, not the date of our recording.\n- **Artwork approval:** for each chosen image, verify station/callsign/locality, front/back, actual card versus letter, source-labelled date versus design period, image resolution, rights holder and permitted transformations. Store written permission and privacy review before generating PNG downloads.\n- **Secure delivery:** generate a local raster PNG from approved assets and text-drawn fields only after the listener clicks. No automatic downloads, external collector-file redirects, active HTML/SVG payloads or external tracking images. Keep optional log exports as literal Markdown text generated in-browser.\n- **Matching:** attach approved artwork to curated station identity plus recording ID, not frequency alone. Aliases need review, and composite recordings need segment attribution.\n- **Permission outreach:** prepare a small, station-specific permission request to RadioTapes or the relevant museum contributor/rights holder. Ask expressly about hosting, cropping/redacting, overlaying commemorative fields, and letting users download derivative PNGs. No outreach has been sent.\n\n## Pilot coverage\n\nThe twenty-recording pilot is shown for prioritization, without changing its catalog. Frequency and broadcast-date fields below are copied from the project data; availability comes from the cited research.\n\n| Pilot recording ID | Station | kHz | Broadcast date | Availability | Evidence |\n|---|---|---:|---|---|---|\n`;
for (const p of pilot) {
  const x=rows.find(x=>x.records.some(r=>r.id===p.inventoryId));
  out+=`| ${md(p.id)} | ${md(p.station)} | ${md(p.frequencyLabel)} | ${md(p.date)} | ${x?.status||'n.a.'} | ${cite(x?.evidence_url,x?.status==='Reported only'?'QSL report':'Checked gallery')} |\n`;
}
out += `\n## Complete station-label register\n\nSource-labelled years are transcribed from the fetched gallery's station-heading block when available. They are not assumed to be issue years, artwork-design years, or the original-broadcast date. “n.a.” means no sufficiently specific heading year was extracted. Follow the source to select an actual card; a gallery may also include envelopes, pennants, photographs, stickers or letters. All rows have reuse status **Not cleared**, actual image resolution/front-back inspection **n.a.**, and a required privacy review before release.\n\n`;
const countries=[...new Set(rows.map(x=>x.country||'Other / uncertain'))];
for(const c of countries){
  out+=`### ${c}\n\n| Register ID / master label | Recording IDs | Availability | Source-labelled years | Evidence and identity notes |\n|---|---|---|---|---|\n`;
  for(const x of rows.filter(x=>(x.country||'Other / uncertain')===c)){
    let evidence=cite(x.evidence_url,x.status==='Reported only'?'QSL reception reports':x.status==='Not located'?'Checked country index':'Fetched verification evidence');
    let caption=x.caption ? ` Source caption: ${x.caption}.` : '';
    let note=x.match_note|| (x.status==='Not located'?'n.a.; no station-specific verification scan established in checked sources.':'');
    if(x.status==='Gallery located'&&/Reviewed station-name/.test(note))note='Station-name/abbreviation match; exact design and recording-era equivalence still need review.';
    out+=`| ${stationRef(x)}: ${md(x.station)} | ${x.records.map(r=>r.id).join(', ')} | ${x.status} | ${x.source_years.join(', ')||'n.a.'} | ${evidence}. ${md(note.replace(/\.$/,'')+'.')}${md(caption)} |\n`;
  }
  out+='\n';
}
out+=`## Recording-level mapping\n\nAll 349 main-sheet rows are retained. This appendix is an identity crosswalk, not a correction of inventory data; dates and frequencies are copied as-is. The URLs are the master recording references, not QSL-artwork download URLs. An original recording's missing or uncertain date must remain missing or uncertain in a listener's commemorative card.\n\n| Sheet row | Inventory ID | Register ID | Exact master station label | kHz | Original date field | Recording reference |\n|---|---:|---|---|---:|---|---|\n`;
for(const {x,r} of rows.flatMap(x=>x.records.map(r=>({x,r}))).sort((a,b)=>a.r.sheet_row-b.r.sheet_row)){
  out+=`| ${r.sheet_row} | ${r.id} | ${stationRef(x)} | ${md(x.station)} | ${md(r.frequency)} | ${md(r.date||'n.a.')} | ${cite(r.source,'Master recording reference')} |\n`;
}
out+=`\n## Audit boundaries and follow-up\n\nThis register covers every exact label in the main master worksheet, not the separate “Freq not confirmed” or “Verify by listening” sheets. It is a bounded public-web availability search, not a claim to have searched every private DX collection. Source pages were fetched and station listings/captions reviewed; image pixels were not comprehensively inspected. Source-labelled dates can establish that a historical verification survives but cannot alone establish artwork identity, frequency written on a card, authenticity, or redistribution rights.\n\nThe remaining priorities are collector follow-up for “Reported only” rows, exact identity/locality resolution for “Related” and “Identity hold” rows, and written reproduction permission for a small pilot artwork set. If a usable, cleared scan cannot be obtained, use the original generic commemorative card rather than copying a similar station's QSL.\n\nFetch limitations: the guessed museum pages for Africa No. 1 and Madagascar failed, so verified RadioTapes listings are used instead. The individual VLT4 article returned HTTP 403; the fetched 2022 archive listing explicitly contains the QSL credit, so that listing is cited without claiming direct-article access. Other failed detail fetches remain indexed-only where the country index supports the link. No failed page is treated as factual evidence.\n\nWorkbook integrity: SHA-256 before and after research is \`fcd6357e375bfaa7202a8950705ba4bcb72547c947e7c7861c703a059b75e837\`. No edits were made to the master workbook, pilot catalog, live receiver or visual prototype.\n`;
out = out.replace("use the user's approved blank artwork", "use the planned user-provided blank artwork once supplied and approved, or an original generic design");
const target=path.join(base,'Master-Station-QSL-Availability-Register.md');
fs.writeFileSync(target,out);
fs.writeFileSync(path.join(base,'station-qsl-register.json'),JSON.stringify({
  researched_on:'2026-10-11',scope:'Main master sheet only',recording_count:349,label_count:288,
  counts,recording_coverage:coverage,artwork_cleared:0,
  disclaimer:'Gallery availability is not a license or proof of period-specific artwork. No image-pixel audit.',
  rows:rows.map(({candidates,...r})=>r)
},null,2));
fs.writeFileSync(path.join(base,'fetched-source-evidence.json'),JSON.stringify([...pages.values()],null,2));
if(rows.length!==288||rows.reduce((n,x)=>n+x.records.length,0)!==349)throw new Error('Coverage mismatch');
console.log(JSON.stringify({counts,coverage,report:target,bytes:out.length},null,2));
