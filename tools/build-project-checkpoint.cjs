'use strict';
// Read-only source packaging: never edits app code, workbook or original datasets.
// Usage (October 20, 2026 and later):
//   node tools/build-project-checkpoint.cjs WORKBOOK_EXPORT.json YYYY-MM-DD
// WORKBOOK_EXPORT.json comes from tools/export-workbook-cells.py (all three workbooks). The October 11, 2026
// checkpoint was built by the earlier single-workbook version of this script (see git history).
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const cp = require('node:child_process');
const root = path.resolve(__dirname, '..');
const checkpointDate = process.argv[3];
if (!/^\d{4}-\d{2}-\d{2}$/.test(checkpointDate || '')) throw Error('Pass the checkpoint date (YYYY-MM-DD) as the second argument');
const checkpointId = 'HR64-' + checkpointDate;
const out = path.join(root, 'handoff/hr64-checkpoint-' + checkpointDate);
fs.mkdirSync(out, { recursive: true });
const staging = '/tmp/hr64-checkpoint-package-' + checkpointDate;
const workbookExports = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')).workbooks;
const MASTER = '60m_SWBC_recordings_1960-1989.xlsx';
const workbookExport = workbookExports.find(book => book.file === MASTER);
if (!workbookExport) throw Error('Workbook export lacks the 60 m master');
// The twenty-record baseline is frozen and was built from the October 10, 2026 master (before the clip 10 date note).
const BASELINE_WORKBOOK_SHA256 = 'fcd6357e375bfaa7202a8950705ba4bcb72547c947e7c7861c703a059b75e837';
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const esc = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;').replaceAll('|', '&#124;').replace(/\r?\n/g, '<br>');
function table(headers, rows) {
  return '| ' + headers.map(esc).join(' | ') + ' |\n| ' + headers.map(() => '---').join(' | ')
    + ' |\n' + rows.map(row => '| ' + row.map(esc).join(' | ') + ' |').join('\n') + '\n';
}
function walk(directory, prefix = '') {
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((a,b) => a.name.localeCompare(b.name))) {
    if (entry.name.startsWith('.') || entry.name === 'node_modules' || (!prefix && entry.name === 'handoff')) continue;
    const relative = prefix ? prefix + '/' + entry.name : entry.name;
    if (entry.isDirectory()) files.push(...walk(path.join(directory,entry.name), relative));
    else if (entry.isFile()) files.push(relative);
  }
  return files.sort();
}
const sourceFiles = walk(root);
const files = sourceFiles.map(relative => {
  const bytes = fs.readFileSync(path.join(root, relative));
  if (bytes.subarray(0, 42).toString().startsWith('version https://git-lfs.github.com/spec/v1')) throw Error('Unhydrated LFS file: '+relative);
  return { path: relative, bytes: bytes.length, sha256: sha(bytes) };
});
const appFiles = files.filter(file => file.path.startsWith('app/heritage-h60/'));
const appDigest = sha(Buffer.from(appFiles.map(file => file.path + '\0' + file.sha256).join('\n')));
const revision = cp.execFileSync('git', ['rev-parse','HEAD'], { cwd: root, encoding: 'utf8' }).trim();
for (const book of workbookExports) if (sha(fs.readFileSync(path.join(root, book.file))) !== book.sha256) throw Error('Workbook export is stale: ' + book.file);
const workbookDigest = workbookExport.sha256;
const inventory = JSON.parse(fs.readFileSync(path.join(root,'data/pilot/inventory-snapshot.json')));
const full = JSON.parse(fs.readFileSync(path.join(root,'app/heritage-h60/full-inventory.json')));
const pilot = JSON.parse(fs.readFileSync(path.join(root,'app/heritage-h60/pilot.json')));
if ([inventory.workbook_sha256,full.workbookSha256].some(digest=>digest!==workbookDigest)) throw Error('Workbook/catalog digest mismatch');
if (pilot.workbookSha256 !== BASELINE_WORKBOOK_SHA256) throw Error('Frozen baseline digest changed');
if (inventory.records.length!==349 || full.recordings.length!==349 || pilot.recordings.length!==20) throw Error('Catalog count mismatch');
const bands = ['90m','49m'].map(band => {
  const catalog = JSON.parse(fs.readFileSync(path.join(root,'app/heritage-h60/band-'+band+'.json')));
  const book = workbookExports.find(item => item.file === 'data/bands/'+catalog.sourceWorkbook);
  if (!book || book.sha256 !== catalog.workbookSha256) throw Error('Band workbook digest mismatch: '+band);
  return catalog;
});
const geography = JSON.parse(fs.readFileSync(path.join(root,'app/heritage-h60/geo/reveal-geography.json')));
const sourceExtensions = new Set(['.js','.cjs','.py','.html','.css','.svg']);
const codeFiles = files.filter(file => sourceExtensions.has(path.extname(file.path)));
let sourceMarkdown = '# HR-64: Complete Source-Code Snapshot\n\n'
  + 'Optional verbose reference. Do not attach this entire file as initial context. The ZIP project files are byte-exact originals; this Markdown embeds every source file for chat inspection. '
  + 'Current receiver code is under app/heritage-h60; other code includes historical layout/branding and research/packaging helpers.\n\n'
  + table(['File','Bytes','SHA-256'], codeFiles.map(file => [file.path,file.bytes,file.sha256]));
for (const file of codeFiles) {
  const text = fs.readFileSync(path.join(root,file.path),'utf8');
  const runs = [...text.matchAll(/`{3,}/g)].map(match=>match[0].length);
  const fence = '`'.repeat(Math.max(3, ...runs.map(length=>length+1)));
  const extension = path.extname(file.path);
  const language = ['.js','.cjs'].includes(extension) ? 'javascript' : extension==='.py' ? 'python' : extension==='.svg' ? 'xml' : extension.slice(1);
  sourceMarkdown += '\n## '+file.path+'\n\nSHA-256: `'+file.sha256+'`\n\n'+fence+language+'\n'+text+(text.endsWith('\n')?'':'\n')+fence+'\n';
}
fs.writeFileSync(path.join(out,'SOURCE_SNAPSHOT.md'),sourceMarkdown);
const byId = new Map(full.recordings.map(record=>[record.inventoryId,record]));
const baseline = new Set(pilot.recordings.map(record=>record.inventoryId));
const recordingsRows = [...inventory.records].sort((a,b)=>a.inventory_id-b.inventory_id).map(record => {
  const runtime=byId.get(record.inventory_id);
  return [record.inventory_id,record.source.station_label,record.source.frequency_label,
    record.source.recording_date_label,record.source.time_label,record.classification.naswa_entity,
    record.classification.qualified_core_band ? 'core' : 'exception/held',
    runtime.testEligible ? 'tunable' : runtime.reviewReasons.join(', '),
    baseline.has(record.inventory_id) ? 'baseline' : '',
    record.source.archive_page && /^https?:\/\//.test(record.source.archive_page) ? `[Archive page](${record.source.archive_page})` : record.source.archive_page || ''];
});
// Render data cells literally while retaining original source URLs as real links.
const rowText = recordingsRows.map(row => '| '+row.map((value,index)=>index===9 ? value : esc(value)).join(' | ')+' |').join('\n');
fs.writeFileSync(path.join(out,'RECORDINGS.md'),
  '# HR-64: Full Recording Inventory Snapshot\n\nOptional curator reference, not blind-listener content. Covers 60 m (all 349 records, below) and the staged 90 m and 49 m catalogs (later sections). '
  +'Original dates/frequencies are labels, not newly verified facts; eligibility is for private receiver testing only. Full fields and URLs remain in the original JSON/workbook.\n\n'
  +'| Clip | Original station label | kHz label | Recording date | UTC label | NASWA entity | Scope | Full test | Baseline | Evidence |\n'
  +'|---|---|---|---|---|---|---|---|---|---|\n'+rowText+'\n'
  + bands.map(catalog => '\n## '+catalog.bandLabel+' ('+catalog.recordings.length+' entries, '+catalog.counts.tunable+' tunable)\n\n'
    +'Source: `data/bands/'+catalog.sourceWorkbook+'`. Labels are as staged from the candidate workbook; held entries show their review reasons.\n\n'
    +'| Clip | Station as labeled | kHz label | Recording date | UTC label | Country as labeled | Scope | Receiver | Evidence |\n|---|---|---|---|---|---|---|---|---|\n'
    + catalog.recordings.map(record => '| '+[record.inventoryId,record.stationAsLabeled,record.frequencyLabel,record.date,record.time,record.countryAsLabeled,record.scope,
        record.testEligible ? 'tunable' : (record.reviewReasons||[]).join(', ')].map(esc).join(' | ')
        +' | '+(record.sourceUrl && /^https?:\/\//.test(record.sourceUrl) ? `[Source page](${record.sourceUrl})` : esc(record.sourceUrl||''))+' |').join('\n')+'\n').join(''));
let workbookMarkdown = '# HR-64: Complete Workbook Cell Data\n\n'
  + 'Read-only cached-value export of the 60 m master and the 90 m and 49 m candidate workbooks. '
  + 'Every worksheet and its formula text are preserved below. Blanks remain empty, and formula results are the existing workbook caches, not new calculations. '
  + 'Row numbers are worksheet addresses, not recording IDs. Original XLSX files preserve formatting, formulas and workbook structure exactly; these tables are for Markdown inspection.\n';
for (const book of workbookExports) {
workbookMarkdown += '\n# '+book.file+'\n\nSHA-256: `'+book.sha256+'`.\n';
for (const sheet of book.sheets) {
  const width=Math.max(...sheet.rows.map(row=>row.length));
  const columnName = index => {
    let result='';for(let n=index+1;n>0;n=Math.floor((n-1)/26))result=String.fromCharCode(65+(n-1)%26)+result;
    return result;
  };
  workbookMarkdown += '\n## '+sheet.name+'\n\nRange: `'+sheet.range+'`.\n\n'
    +table(['Excel row',...Array.from({length:width},(_,index)=>columnName(index))],
      sheet.rows.map((row,index)=>[index+1,...row]));
  const formulas=Object.entries(sheet.formulas);
  if(formulas.length)workbookMarkdown+='\n### Formula text\n\n'+table(['Cell','Original formula'],formulas);
}
}
fs.writeFileSync(path.join(out,'WORKBOOK_DATA.md'),workbookMarkdown);
const counts={};
for(const file of files){const group=file.path.includes('/')?file.path.split('/')[0]:'root';counts[group]=(counts[group]||0)+1;}
fs.writeFileSync(path.join(out,'FILE_INDEX.md'),
  '# HR-64: Complete Frozen File Index ('+checkpointDate+')\n\nThis optional reference lists every source file included under the ZIP `project/` directory. '
  +'It includes raw discovery/QSL evidence and historical documents without loading them into the starter context. '
  +'Hidden repository/platform folders, handoff outputs and dependencies are excluded. Binary assets are exact ZIP files, not lossy Markdown substitutes.\n\n'
  +table(['Folder','Files'],Object.entries(counts))+'\n'
  +table(['Source path','Bytes','SHA-256'],files.map(file=>[file.path,file.bytes,file.sha256])));
const manifest = {
  checkpoint:checkpointId,checkpointEasternDate:checkpointDate,generatedAtUtc:new Date().toISOString(),
  sourceRevision:revision,sourceWorkbookSha256:workbookDigest,applicationDigestAlgorithm:'SHA-256 of sorted path-NUL-fileSHA256 lines',
  applicationSha256:appDigest,appId:'3c374183-871e-4459-8cf4-bb75c75e4e96',
  previewUrl:'https://www.perplexity.ai/computer/a/heritage-hr-64-historical-shor-PDdBg4ceRFmM9Lt1x15Olg',
  baselineWorkbookSha256:BASELINE_WORKBOOK_SHA256,
  bandWorkbooks:Object.fromEntries(bands.map(catalog=>[catalog.band,{file:'data/bands/'+catalog.sourceWorkbook,sha256:catalog.workbookSha256}])),
  counts:{'60m':{inventory:349,baseline:20,tunable:323,review:26,carriers:143},
    ...Object.fromEntries(bands.map(catalog=>[catalog.band,{inventory:catalog.recordings.length,tunable:catalog.counts.tunable,held:catalog.counts.held,carriers:catalog.counts.frequencies}])),
    revealGeographyEntries:Object.keys(geography.entries).length},
  sourceFileCount:files.length,sourceCodeFileCount:codeFiles.length,files
};
fs.writeFileSync(path.join(out,'CHECKPOINT_MANIFEST.json'),JSON.stringify(manifest,null,2)+'\n');
fs.rmSync(staging,{recursive:true,force:true});
fs.mkdirSync(path.join(staging,'project'),{recursive:true});
fs.mkdirSync(path.join(staging,'context'),{recursive:true});
for(const file of files){
  const target=path.join(staging,'project',file.path);fs.mkdirSync(path.dirname(target),{recursive:true});
  fs.copyFileSync(path.join(root,file.path),target);
  if(sha(fs.readFileSync(target))!==file.sha256)throw Error('Copy checksum failed: '+file.path);
}
for(const name of fs.readdirSync(out)){
  if(['.md','.json'].includes(path.extname(name)))fs.copyFileSync(path.join(out,name),path.join(staging,'context',name));
}
fs.writeFileSync(path.join(staging,'README.md'),
  '# Heritage HR-64: Full Project Checkpoint ('+checkpointDate+')\n\nStart with `context/START_HERE.md` and `context/SPEC.md`. '
  +'The rest of context/ is optional supporting material. project/ contains the exact original code, data, workbook, noise assets and historical research. '
  +'Nothing here authorizes public publication, rights reproduction, QSL outreach or changes to the paused receiver. '
  +'Source-file SHA-256 hashes are in `context/CHECKPOINT_MANIFEST.json`. Serve `project/app/heritage-h60/` using HTTP to run the frozen build. '
  +'The project handoff/ folder (including earlier checkpoints) is not repeated under project/; earlier checkpoint ZIPs remain in the project repository. '
  +'No browser-session logs, repository/platform internals or hidden credential files are included.\n');
const checksumFiles=walk(staging).filter(relative=>relative!=='SHA256SUMS.txt');
fs.writeFileSync(path.join(staging,'SHA256SUMS.txt'),checksumFiles.map(relative =>
  sha(fs.readFileSync(path.join(staging,relative)))+'  '+relative).join('\n')+'\n');
const zipName = 'Heritage-HR64-Complete-Checkpoint-'+checkpointDate+'.zip';
fs.rmSync(path.join(out,zipName),{force:true});
cp.execFileSync('zip',['-q','-r','-X',path.join(out,zipName),'.'],{cwd:staging});
console.log(JSON.stringify({zip:path.join(out,zipName),zipBytes:fs.statSync(path.join(out,zipName)).size,sourceFiles:files.length,codeFiles:codeFiles.length,applicationSha256:appDigest,
  workbookSha256:workbookDigest,sourceBytes:files.reduce((sum,file)=>sum+file.bytes,0),staging,out},null,2));
