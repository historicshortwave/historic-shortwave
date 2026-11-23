'use strict';
const $ = id => document.getElementById(id);
// Band definitions, in BAND-switch order (low to high frequency). Only bands
// listed in ACTIVE_BANDS can be selected (design/three-band-receiver-plan.md).
const BANDS = {
  '90m': {id:'90m', label:'90 METERS', description:'90 METER ARCHIVE BAND', collection:'90 METER COLLECTION',
    minHz:3150000, maxHz:3500000, defaultHz:3300000, catalogs:{full:'./band-90m.json'}, defaultMode:'full', staticHint:null},
  '60m': {id:'60m', label:'60 METERS', description:'60 METER ARCHIVE BAND', collection:'60 METER COLLECTION',
    minHz:4700000, maxHz:5085000, defaultHz:4900000, catalogs:{full:'./band-60m.json'}, defaultMode:'full', staticHint:null},
  '49m': {id:'49m', label:'49 METERS', description:'49 METER ARCHIVE BAND', collection:'49 METER COLLECTION',
    minHz:5850000, maxHz:6350000, defaultHz:6100000, catalogs:{full:'./band-49m.json'}, defaultMode:'full', staticHint:null},
};
const ACTIVE_BANDS = ['90m','60m','49m'];
const BAND_ANGLES = {'90m':-50, '60m':0, '49m':50};
const bandShort = id => id.replace('m',' m');
const state = {loop:false, band:'60m', pendingBand:null, bandHz:new Map(), bandModes:new Map(), records:[], groups:[], group:null, mode:'full', catalogs:new Map(), choices:new Map(), catalogRequest:0, mediaRequest:0, mediaState:'idle', loadTimer:null, hz:4900000, tuningAngle:0, power:false, static:true, gain:.45, step:100, selected:null, revealed:new Set(), positions:new Map(), audio:null, timer:null, noise:null, ctx:null, noiseGain:null};
const currentBand = () => BANDS[state.band];
const bounds = () => [currentBand().minHz, currentBand().maxHz];
const bandForHz = hz => ACTIVE_BANDS.map(id => BANDS[id]).find(b => hz >= b.minHz && hz <= b.maxHz) || null;
const choiceKey = hz => `${state.band}:${state.mode}:${hz}`;
const frequency = hz => (hz/1000).toFixed(1);
const clock = seconds => Number.isFinite(seconds) ? `${Math.floor(seconds/60).toString().padStart(2,'0')}:${Math.floor(seconds%60).toString().padStart(2,'0')}` : '--:--';
const seasonalNoise = new SeasonalNoise(engine => {
  const condition = engine.condition;
  // Seasonal band conditions run in the background; nothing is shown on the receiver face.
  // State is kept on the receiver element for testing (season, Eastern date, level, status).
  const face=$('receiver');
  face.dataset.season=condition.season; face.dataset.seasonDate=condition.easternDate;
  face.dataset.seasonDb=String(condition.db); face.dataset.seasonStatus=engine.status;
  renderStaticStatus(engine);
});
function renderStaticStatus(engine) {
  let message;
  if (!state.power) message = state.static ? 'Receiver is in standby. Turn it on to hear static between recordings.' : 'Receiver is in standby and static is off.';
  else if (!state.static) message = 'Static is off. Enable this switch to hear seasonal noise between recordings.';
  else if (engine.status === 'error') message = engine.error;
  else if (engine.ctx && engine.ctx.state !== 'running') message = 'Static audio needs activation. Switch the receiver off/on to retry; check that this tab is not muted.';
  else if (engine.status !== 'ready') message = 'Loading seasonal static. Station playback does not wait for these assets.';
  else if (!state.gain) message = 'Audio gain is zero. Turn AUDIO GAIN clockwise to hear the receiver.';
  else if (!state.selected) message = 'Seasonal static is on between recordings. AUDIO GAIN controls its volume; buffering noise uses a gentler level.';
  else if (['loading','buffering'].includes(state.mediaState)) message = 'Gentle seasonal static is on while the selected recording loads or buffers.';
  else message = `Static is intentionally silent at a selected recording. Tune between recordings to hear it${currentBand().staticHint ? '; ' + currentBand().staticHint : ''}.`;
  $('static-description').textContent = message;
}
function noiseLevel() {
  seasonalNoise.update({ power: state.power, enabled: state.static, gain: state.gain,
    selected: Boolean(state.selected), mediaState: state.mediaState });
  renderStaticStatus(seasonalNoise);
}
async function initNoise() {
  // Context activation and static downloads must never delay station playback.
  const startup = seasonalNoise.start();
  state.ctx = seasonalNoise.ctx;
  state.noiseGain = seasonalNoise.master;
  noiseLevel();
  startup.then(noiseLevel).catch(noiseLevel);
}
function status(text) { $('receiver-status').textContent=text; }
function stopAudio() {
  state.mediaRequest++;
  clearTimeout(state.timer);
  clearTimeout(state.loadTimer);
  const audio=state.audio; state.audio=null; state.mediaState='idle';
  if(audio) {
    if(state.selected && Number.isFinite(audio.currentTime)) state.positions.set(state.selected.id,audio.ended?0:audio.currentTime);
    audio.pause(); audio.removeAttribute('src'); audio.load(); audio.remove();
  }
  noiseLevel();
}
function mediaStatus(kind,text) {
  state.mediaState=kind; status(text); noiseLevel();
}
function playbackFailure(audio,message) {
  if(state.audio!==audio)return;
  clearTimeout(state.loadTimer);
  mediaStatus('error','AUDIO ERROR');
  audio.pause();
  $('play-button').textContent='Retry recording';
  $('listening-description').textContent=message+' Retry this clip, or choose another recording at this frequency if available. The selected clip has not changed.';
}
function watchLoading(audio) {
  clearTimeout(state.loadTimer);
  state.loadTimer=setTimeout(()=>{
    if(state.audio===audio && ['loading','buffering'].includes(state.mediaState))
      playbackFailure(audio,'The source host did not start or resume playback within 15 seconds.');
  },15000);
}
// Recordings may play only over HTTPS from the approved archive hosts. This matches the media-src list in the
// Content Security Policy in index.html; a recording elsewhere is refused and shows Retry, never a substitute.
const APPROVED_AUDIO_HOSTS=['archive.org'];
function approvedAudioUrl(value) {
  let url; try {url=new URL(value);} catch(error) {return false;}
  if(url.protocol!=='https:'||url.username||url.password||url.port) return false;
  return APPROVED_AUDIO_HOSTS.includes(url.hostname)||url.hostname.endsWith('.archive.org');
}
function makeAudio() {
  if(!state.selected || state.audio) return;
  const recording=state.selected;
  const audio=document.createElement('audio'); audio.preload='metadata'; audio.volume=state.gain; audio.loop=state.loop;
  audio.setAttribute('aria-label',`Audio clip ${recording.inventoryId}`); audio.style.display='none'; document.body.append(audio);
  state.audio=audio;
  const current=()=> state.audio===audio && state.selected?.id===recording.id;
  audio.addEventListener('loadedmetadata',()=>{ if(!current()) return; const position=state.positions.get(recording.id)||0; if(position<audio.duration) audio.currentTime=position; $('seek-input').disabled=!Number.isFinite(audio.duration); $('duration').textContent=clock(audio.duration); });
  audio.addEventListener('timeupdate',()=>{if(!current()) return; if(state.mediaState==='buffering'&&!audio.paused&&audio.readyState>=3){clearTimeout(state.loadTimer);mediaStatus('playing','PLAYING');$('play-button').textContent='Pause recording';} $('elapsed').textContent=clock(audio.currentTime); if(Number.isFinite(audio.duration)) $('seek-input').value=audio.currentTime/audio.duration*100;});
  audio.addEventListener('playing',()=>{if(current()){
    if(!state.power||state.mediaState==='error'){audio.pause();return;}
    clearTimeout(state.loadTimer);mediaStatus('playing','PLAYING');$('play-button').textContent='Pause recording';
  }});
  audio.addEventListener('pause',()=>{if(current()&&!audio.error&&!['error','ended'].includes(state.mediaState)){
    clearTimeout(state.loadTimer);mediaStatus('paused',state.power?'PAUSED':'STANDBY');$('play-button').textContent='Play recording';
  }});
  audio.addEventListener('ended',()=>{if(current()){
    clearTimeout(state.loadTimer);state.positions.delete(recording.id);mediaStatus('ended','ENDED');
    $('play-button').textContent='Replay recording';$('listening-description').textContent='This recording has ended. Replay it, or choose another recording at this frequency if available. Nothing advances automatically.';
  }});
  for(const event of ['waiting','stalled'])audio.addEventListener(event,()=>{
    if(event==='stalled'&&audio.readyState>=3)return; // data is buffered; playback is not interrupted
    if(current()&&state.power&&!audio.paused&&!['error','ended'].includes(state.mediaState)){
      mediaStatus('buffering','BUFFERING');watchLoading(audio);
    }
  });
  audio.addEventListener('error',()=>{if(current())playbackFailure(audio,'The original archive host could not play this file.');});
  if(!approvedAudioUrl(recording.audioUrl)){audio.dataset.refused='true';return;}
  audio.src=recording.audioUrl;
}
async function play() {
  if(!state.selected) return;
  const selectedId=state.selected.id;
  const request=++state.mediaRequest;
  clearTimeout(state.timer);
  if(!state.power) {state.power=true; updatePower();}
  try {await initNoise();} catch(error) { /* Archive playback can still work without seasonal static. */ }
  if(!state.power||state.selected?.id!==selectedId||request!==state.mediaRequest)return;
  if(state.audio?.error||state.mediaState==='error') stopAudio();
  makeAudio(); const audio=state.audio;
  if(audio?.dataset.refused){playbackFailure(audio,'This recording is not hosted on an approved archive, so the receiver did not play it.');return;}
  if(!audio.paused&&!audio.ended&&audio.readyState>=3){mediaStatus('playing','PLAYING');$('play-button').textContent='Pause recording';return;}
  mediaStatus('loading','LOADING');watchLoading(audio);$('play-button').textContent='Pause recording';$('listening-description').textContent=listeningHint(state.selected);
  if(audio.ended) audio.currentTime=0;
  try {await audio.play();} catch(error) {if(state.audio===audio&&state.power&&!['paused','error','ended'].includes(state.mediaState))playbackFailure(audio,'Playback was blocked or the source file could not be opened.');}
}
function updatePower() {
  $('power-button').setAttribute('aria-checked',state.power);
  $('power-off').classList.toggle('active',!state.power); $('power-label').classList.toggle('active',state.power);
  $('signal-lamp').classList.toggle('lit',state.power && !!state.selected);
  noiseLevel(); draw();
}
function tune(hz) {
  const previousHz=state.hz;
  state.hz=Math.round(hz/100)*100;
  state.tuningAngle=(state.tuningAngle+(state.hz-previousHz)/(state.step===100?12000:120000)*360)%360;
  const [min,max]=bounds();
  document.querySelector('.dial-top span:last-child').textContent=`${(min/1000000).toFixed(3)}–${(max/1000000).toFixed(3)} Mc/s`;
  const group=state.hz>=min && state.hz<=max ? ReceiverCatalog.findGroup(state.groups,state.hz,state.group?.hz) : null;
  state.group=group;
  const choice=group?state.choices.get(choiceKey(group.hz)):null;
  const next=group?(group.records.find(r=>r.id===choice)||group.records[0]):null;
  if(next?.id!==state.selected?.id) {
    stopAudio(); state.selected=next;
    $('elapsed').textContent='00:00'; $('duration').textContent='--:--'; $('seek-input').value=0; $('seek-input').disabled=true;
    $('play-button').textContent='Play recording'; renderRecording();
    if(next && state.power) state.timer=setTimeout(()=>{if(state.power&&state.selected?.id===next.id)play();},250);
  }
  $('frequency-readout').textContent=frequency(state.hz);
  $('band-slider').value=state.hz/1000;
  $('tuning-knob').setAttribute('aria-valuenow',state.hz/1000);
  $('tuning-knob').setAttribute('aria-valuetext',frequency(state.hz)+' kilohertz');
  $('tuning-knob').style.transform=`rotate(${state.tuningAngle}deg)`;
  $('signal-lamp').classList.toggle('lit',state.power&&!!next);
  if(!state.power) status('STANDBY');
  else if(state.hz<min||state.hz>max) status('OUT OF RANGE');
  else if(!next) status('NO SIGNAL');
  else if(!state.audio) status('TUNED');
  for(const button of $('guide-grid').children) {button.classList.toggle('current',Number(button.dataset.hz)===group?.hz); button.disabled=Number(button.dataset.hz)<min||Number(button.dataset.hz)>max;}
  renderAlternatives();
  noiseLevel(); draw();
}
// Recordist credits (credits.json, keyed by record id) load on the first reveal, then re-render the panel.
let creditsData=null, creditsPromise=null, creditsFailed=false;
function loadCredits() {
  if(!creditsPromise) creditsPromise=fetch('./credits.json').then(r=>{if(!r.ok)throw Error(r.status);return r.json();})
    .then(d=>{creditsData=d.credits||{};renderRecording();})
    .catch(()=>{creditsPromise=null;creditsData=null;creditsFailed=true;renderRecording();});
  return creditsPromise;
}
function creditLine(r) {
  const p=document.createElement('p'); p.className='recording-credit'; p.dataset.testid='text-recording-credit';
  if(!creditsData&&creditsFailed){p.textContent='Recording credit unavailable right now.';creditsFailed=false;return p;}
  if(!creditsData){p.textContent='Loading recording credit…';p.classList.add('is-pending');loadCredits();return p;}
  const c=creditsData[r.id];
  if(!c){p.textContent='Recordist not named by the source';return p;}
  p.append(c.credit);
  if(c.via) p.append(' · ',c.via);
  if(c.license){let u=null;try{u=new URL(c.license.url);}catch{}
    if(!u||!['https:','http:'].includes(u.protocol)){p.append(' · ',c.license.label);return p;}
    const a=document.createElement('a');a.href=u.href;a.textContent=c.license.label;a.target='_blank';a.rel='noopener noreferrer';a.className='nowrap';p.append(' · ',a);}
  return p;
}
// Dial frequency in kHz from frequencyHz. The archive's own label is kept, quoted, only when it is written differently
// (for example "6.010MHz" or "3,290 khz"); plain kHz labels such as "4800" show exactly as before.
function frequencyDisplay(r) {
  const khz=String(r.frequencyHz/1000), label=String(r.frequencyLabel??'').trim();
  return (!label||label===khz||label.replace(/\s*khz$/i,'')===khz) ? `${khz} kHz` : `${khz} kHz (labeled “${label}”)`;
}
function listeningHint(r) {
  if(!r) return 'Turn the tuning knob or use the band guide to find an archive recording.';
  const base=state.revealed.has(r.id)?'The station is revealed below. Listen again, or tune on to find another recording.':'Listen for a voice identification and decide for yourself before revealing the station.';
  return base+(state.loop?' Loop is on: this recording repeats until you turn Loop off.':'');
}
function renderRecording() {
  const r=state.selected;
  $('recording-date').textContent=r?.date||'No recording tuned';
  $('recording-time').textContent=r?.time||'Not documented';
  $('clip-id').textContent=r?`AUDIO CLIP ${r.inventoryId}`:'AUDIO CLIP';
  $('scope-label').textContent=currentBand().collection;
  $('context-status').textContent=r?(state.revealed.has(r.id)?'Station revealed':'Station not revealed'):'Tune for a recording';
  $('listening-title').textContent=r?(state.revealed.has(r.id)?r.station:'An identification is waiting.'):'There is space between the signals.';
  $('listening-description').textContent=listeningHint(r);
  for(const id of ['play-button','restart-button','loop-button','reveal-button']) $(id).disabled=!r;
  const panel=$('reveal-panel');
  // Keep an existing map for the same recording so re-renders (tuning inside the capture window) do not redraw it.
  const keptMap=r?[...panel.querySelectorAll('.reveal-map')].find(m=>m.dataset.record===r.id):null;
  panel.replaceChildren(); panel.hidden=!r||!state.revealed.has(r.id);
  if(panel.hidden||!keptMap) window.RevealMap?.clear();
  if(!panel.hidden) {
    const title=document.createElement('h3'); title.textContent=r.station; panel.append(title);
    const details=document.createElement('p'); details.textContent=`${r.country} · ${frequencyDisplay(r)} · ${r.date} · GMT: ${r.time||'not documented'}`; panel.append(details);
    panel.append(creditLine(r));
    if(keptMap) panel.append(keptMap); else window.RevealMap?.show(r,panel);
    const notes=document.createElement('p'); notes.textContent=r.notes||'Original archive labels preserved.'; panel.append(notes);
    const references=[['Original archive page',r.sourceUrl],['Original audio file',r.audioUrl],...(r.additionalReferences||[]).map(ref=>[ref.label,ref.url])];
    for(const [index,[label,url]] of references.entries()) {
      if(!url)continue;
      let destination;try{destination=new URL(url);}catch{continue;}
      if(!['https:','http:'].includes(destination.protocol))continue;
      const a=document.createElement('a');a.textContent=label;a.href=destination.href;a.target='_blank';a.rel='noopener noreferrer';
      a.dataset.testid=`link-archive-reference-${r.inventoryId}-${index}`;panel.append(a,document.createTextNode('  '));
    }
  }
  if('mediaSession' in navigator) navigator.mediaSession.metadata=new MediaMetadata({title:r?`Audio clip ${r.inventoryId}`:'Historic Shortwave',artist:'Historical recording'});
}
function renderAlternatives() {
  const records=state.group?.records||[], select=$('recording-select');
  $('alternate-controls').hidden=records.length<2;
  select.replaceChildren();
  for(const r of records){const option=document.createElement('option');option.value=r.id;option.textContent=`Clip ${r.inventoryId} · ${r.date}`;select.append(option);}
  if(state.selected)select.value=state.selected.id;
  const index=records.findIndex(r=>r.id===state.selected?.id);
  $('alternative-count').textContent=`${index+1} / ${records.length}`;
  $('previous-recording').disabled=index<=0;
  $('next-recording').disabled=index<0||index>=records.length-1;
}
function chooseRecording(id) {
  const r=state.group?.records.find(r=>r.id===id);
  if(!r||r.id===state.selected?.id)return;
  state.choices.set(choiceKey(state.group.hz),r.id);
  tune(state.hz);
}
function renderBand() {
  // Every 60 m string below matches the text previously hardcoded in index.html.
  const band=currentBand(), [min,max]=bounds();
  document.querySelector('.dial-top span:first-child').textContent=band.label;
  document.querySelector('.receiver-description small').textContent=band.description;
  for(const selector of ['.dial-bottom','.band-edges']){const [low,high]=document.querySelectorAll(`${selector} span`);low.textContent=`${min/1000} kHz`;high.textContent=`${max/1000} kHz`;}
  const slider=$('band-slider');slider.min=min/1000;slider.max=max/1000;
  $('tuning-knob').setAttribute('aria-valuemin',min/1000);$('tuning-knob').setAttribute('aria-valuemax',max/1000);
  renderBandSwitch(band.id);
}
function bandText(band) { return `${band.id.replace('m','')} meter band, ${band.minHz/1000} to ${band.maxHz/1000} kilohertz`; }
function renderBandSwitch(bandId) {
  // Shows the requested band immediately; reverts if that band's catalog fails to load.
  const band=BANDS[bandId], knob=$('band-knob');
  knob.style.transform=`rotate(${BAND_ANGLES[bandId]}deg)`;
  knob.setAttribute('aria-valuenow',ACTIVE_BANDS.indexOf(bandId)+1);
  knob.setAttribute('aria-valuetext',bandText(band));
  $('band-output').textContent=band.id.replace('m',' M');
  $('band-select').value=bandId;
  for(const mark of document.querySelectorAll('.band-mark'))mark.classList.toggle('active',mark.dataset.band===bandId);
}
function installCatalog(bandId,mode,data) {
  const bandChange=bandId!==state.band;
  stopAudio();state.selected=null;state.group=null;state.mode=mode;
  if(bandChange){state.bandHz.set(state.band,state.hz);state.band=bandId;state.hz=state.bandHz.get(bandId)??BANDS[bandId].defaultHz;}
  state.bandModes.set(bandId,mode);renderBand();
  state.records=data.recordings.filter(r=>r.testEligible!==false);
  state.groups=ReceiverCatalog.buildGroups(state.records);
  $('catalog-status').textContent=statusText(mode,data);
  $('intro-description').textContent='Historical recordings at their original frequencies. Tune the band, listen for an identification, then reveal the station to confirm the station ID and its location.';
  $('footer-mode').textContent=`HISTORIC SHORTWAVE / ${currentBand().collection}`;
  $('guide-count').textContent=`${state.groups.length} recording positions`;
  $('guide-grid').replaceChildren();
  for(const g of state.groups){
    const b=document.createElement('button');b.dataset.hz=g.hz;
    const strong=document.createElement('strong');strong.textContent=frequency(g.hz)+' kHz';
    const small=document.createElement('span');small.textContent=g.records.length>1?`${g.records.length} recordings`:g.records[0].date;
    b.append(strong,small);b.onclick=()=>tune(g.hz);$('guide-grid').append(b);
  }
  /* Release build: no review-only entries. */
  const review=[];
  const reasons={inventory_hold:'Inventory hold',frequency_review:'Frequency needs review',compilation_segment_review:'Compilation segments need review',outside_era:'Outside 1960–1989',mirror_duplicate:'Second copy of a kept recording'};
  for(const r of review){
    const tr=document.createElement('tr');
    for(const text of [`Clip ${r.inventoryId}`,r.frequencyLabel,r.date,r.reviewReasons.map(reason=>reasons[reason]).join('; ')]){const td=document.createElement('td');td.textContent=text;tr.append(td);}
  }
  tune(state.hz);renderRecording();
}
async function switchCatalog(mode,bandId=state.band) {
  const request=++state.catalogRequest, band=BANDS[bandId];
  if(bandId===state.band&&state.pendingBand){state.pendingBand=null;renderBandSwitch(state.band);}
  if(!band.catalogs[mode])mode=band.defaultMode;
  $('catalog-status').textContent='Loading recordings…';
  try {
    const key=`${bandId}:${mode}`;
    let data=state.catalogs.get(key);
    if(!data){
      const response=await fetch(band.catalogs[mode]);
      if(!response.ok)throw Error('Catalog unavailable');
      data=await response.json();
      if(!Array.isArray(data.recordings)||!data.recordings.length)throw Error('Invalid catalog');
      state.catalogs.set(key,data);
    }
    if(request===state.catalogRequest){
      const changed=bandId!==state.band;
      state.pendingBand=null;installCatalog(bandId,mode,data);
      if(changed)$('band-announcement').textContent=bandText(band);
    }
  } catch(error) {
    if(request!==state.catalogRequest)return;
    state.pendingBand=null;renderBandSwitch(state.band);
    if(bandId!==state.band)$('band-announcement').textContent=`${bandText(band)} could not load. Staying on ${bandText(currentBand())}.`;
    $('catalog-status').textContent='Catalog could not load. Current catalog retained; select again to retry.';
    if(!state.records.length){status('NO CATALOG');$('listening-description').textContent='The recordings could not load. Reload this page to retry.';}
  }
}
function selectBand(bandId) {
  if(!ACTIVE_BANDS.includes(bandId))return Promise.resolve();
  if(bandId===(state.pendingBand??state.band))return Promise.resolve();
  if(bandId===state.band){
    // Turning back before another band finished loading: cancel that load.
    state.catalogRequest++;state.pendingBand=null;renderBandSwitch(bandId);
    $('catalog-status').textContent=state.catalogs.get(`${state.band}:${state.mode}`)?statusText(state.mode,state.catalogs.get(`${state.band}:${state.mode}`)):'';
    return Promise.resolve();
  }
  state.pendingBand=bandId;renderBandSwitch(bandId);
  return switchCatalog(state.bandModes.get(bandId)||BANDS[bandId].defaultMode,bandId);
}
const statusText=(mode,data)=>`${data.recordings.length} recordings on ${bandShort(currentBand().id)}`;
function canvas(id) {
  const node=$(id),rect=node.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
  node.width=rect.width*dpr;node.height=rect.height*dpr;const ctx=node.getContext('2d');ctx.scale(dpr,dpr);return [ctx,rect.width,rect.height];
}
function draw() {
  let [c,w,h]=canvas('band-canvas'); const [min,max]=bounds();
  c.clearRect(0,0,w,h); c.strokeStyle='#a9bf8b';c.fillStyle='#dbe9bd';c.font='12px "IBM Plex Mono",monospace'; c.textAlign='center';
  const x=hz=>18+(hz-min)/(max-min)*(w-36);
  const labelStep=w<240?100000:50000;
  for(let hz=Math.ceil(min/10000)*10000;hz<=max;hz+=10000){c.beginPath();c.moveTo(x(hz),h*.32);c.lineTo(x(hz),h*.32+(hz%labelStep===0?24:12));c.stroke();if(hz%labelStep===0)c.fillText((hz/1000000).toFixed(w<240?1:2),x(hz),h*.32+43);}
  const needle=Math.max(8,Math.min(w-8,x(state.hz)));c.strokeStyle='#fff3cd';c.lineWidth=2;c.beginPath();c.moveTo(needle,5);c.lineTo(needle,h-8);c.stroke();
  [c,w,h]=canvas('meter-canvas');c.clearRect(0,0,w,h);const cx=w/2,cy=h*.86,radius=Math.min(w*.43,h*.66);
  c.strokeStyle='#6e634f';c.lineWidth=1;c.beginPath();c.arc(cx,cy,radius,Math.PI*1.15,Math.PI*1.85);c.stroke();
  c.font='12px "IBM Plex Mono",monospace';c.textAlign='center';c.fillStyle='#4b4536';
  const labels=['1','3','5','7','9','+20'];
  labels.forEach((label,i)=>{const angle=Math.PI*(1.15+.7*i/5);const point=d=>[cx+Math.cos(angle)*d,cy+Math.sin(angle)*d];const a=point(radius),b=point(radius-7);c.beginPath();c.moveTo(...a);c.lineTo(...b);c.stroke();const t=point(radius+13);c.fillText(label,Math.max(9,Math.min(w-15,t[0])),t[1]+4);});
  const distance=state.selected?Math.abs(state.hz-state.selected.frequencyHz):1000;
  const signal=!!(state.power&&state.selected?.id);
  const level=signal ? .85*(1-distance/1600):.05;
  renderSignalIndicator(signal);
  const angle=Math.PI*(1.15+.7*level);c.strokeStyle='#a3542f';c.lineWidth=2;c.beginPath();c.moveTo(cx,cy);c.lineTo(cx+Math.cos(angle)*(radius-8),cy+Math.sin(angle)*(radius-8));c.stroke();
  c.fillStyle='#4b4536';c.beginPath();c.arc(cx,cy,4,0,Math.PI*2);c.fill();
}
// Red readout outline: lit under exactly the condition that lifts the S-meter
// (receiver on and a recording captured), at one strength anywhere in the capture window.
function renderSignalIndicator(signal) {
  $('digital-window').classList.toggle('has-signal',signal);
  $('signal-legend').hidden=!signal;
}
function setLoop(on) {
  state.loop=!!on;
  if(state.audio) state.audio.loop=state.loop;
  $('loop-button').setAttribute('aria-pressed',String(state.loop));
  $('loop-button').querySelector('.loop-state').textContent=state.loop?'ON':'OFF';
  $('loop-button').classList.toggle('active',state.loop);
  if(state.selected){
    const d=$('listening-description'), note=' Loop is on: this recording repeats until you turn Loop off.';
    if(state.loop&&!d.textContent.includes(note)) d.textContent+=note;
    if(!state.loop) d.textContent=d.textContent.replace(note,'');
  }
}
function setGain(value) {
  state.gain=Math.max(0,Math.min(1,value));
  const percent=Math.round(state.gain*100);
  $('gain-input').value=percent;$('gain-output').textContent=percent+'%';
  $('gain-knob').style.transform=`rotate(${state.gain*270-135}deg)`;
  $('gain-knob').setAttribute('aria-valuenow',percent);
  $('gain-knob').setAttribute('aria-valuetext',percent+' percent');
  if(state.audio)state.audio.volume=state.gain;
  noiseLevel();
}
function rotary(node,getValue,setValue,limits,travel) {
  let drag=null;
  const angle=e=>{
    const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
    return Math.hypot(dx,dy)<12?null:Math.atan2(dy,dx);
  };
  node.style.touchAction='none';
  node.onpointerdown=e=>{
    if(!e.isPrimary||e.button!==0)return;
    const box=node.getBoundingClientRect();
    drag={id:e.pointerId,x:box.x+box.width/2,y:box.y+box.height/2,value:getValue(),angle:null};
    drag.angle=angle(e);node.setPointerCapture(e.pointerId);node.focus();
    node.classList.add('grabbing');e.preventDefault();
  };
  node.onpointermove=e=>{
    if(!drag||e.pointerId!==drag.id)return;
    const next=angle(e);if(next===null){drag.angle=null;return;}
    if(drag.angle!==null){
      const delta=Math.atan2(Math.sin(next-drag.angle),Math.cos(next-drag.angle));
      const [min,max]=limits();
      drag.value=Math.max(min,Math.min(max,drag.value+delta/(2*Math.PI)*travel()));
      setValue(drag.value);
    }
    drag.angle=next;
  };
  const finish=()=>{drag=null;node.classList.remove('grabbing');};
  node.onpointerup=node.onpointercancel=node.onlostpointercapture=finish;
}
function bind() {
  $('recording-select').onchange=e=>chooseRecording(e.target.value);
  for(const [id,offset]of [['previous-recording',-1],['next-recording',1]])$(id).onclick=()=>{
    const records=state.group?.records||[],index=records.findIndex(r=>r.id===state.selected?.id);
    if(records[index+offset])chooseRecording(records[index+offset].id);
  };
  $('power-button').setAttribute('aria-label','Receiver power');
  for(const word of document.querySelectorAll('.power-word'))word.onclick=()=>{if((word.dataset.power==='on')!==state.power)$('power-button').click();};
  $('power-button').onclick=async()=>{state.power=!state.power;updatePower();if(state.power){try{await initNoise();}catch(error){}if(!state.power)return;if(state.selected)await play();else status('NO SIGNAL');}else{clearTimeout(state.timer);clearTimeout(state.loadTimer);state.audio?.pause();state.mediaState='paused';noiseLevel();status('STANDBY');}};
  $('play-button').onclick=()=>{if(state.audio&&!state.audio.paused&&state.mediaState!=='error')state.audio.pause();else play();};
  // Loop recording: off by default. When on, the current recording starts again from the beginning when it ends
  // (the browser's own loop, so no "ended" event and no gap handling). It never moves to another recording and
  // never retries a recording that failed. The setting stays until turned off or a new blind session starts.
  $('loop-button').onclick=()=>setLoop(!state.loop);
  $('restart-button').onclick=()=>{if(!state.selected)return;if(state.audio)state.audio.currentTime=0;state.positions.delete(state.selected.id);play();};
  $('seek-input').oninput=e=>{if(state.audio&&Number.isFinite(state.audio.duration))state.audio.currentTime=Number(e.target.value)/100*state.audio.duration;};
  $('gain-input').oninput=e=>setGain(Number(e.target.value)/100);
  $('static-button').onclick=()=>{state.static=!state.static;$('static-button').setAttribute('aria-checked',state.static);$('static-output').textContent=state.static?'On':'Off';noiseLevel();if(state.static&&state.power&&seasonalNoise.status==='error')initNoise().catch(()=>{});};
  rotary($('gain-knob'),()=>state.gain,setGain,()=>[0,1],()=>360/270);
  // BAND knob: 50 degrees per detent; a drag snaps to the nearest detent as it passes halfway.
  const bandIndex=()=>ACTIVE_BANDS.indexOf(state.pendingBand??state.band);
  rotary($('band-knob'),bandIndex,value=>selectBand(ACTIVE_BANDS[Math.round(value)]),()=>[0,ACTIVE_BANDS.length-1],()=>360/50);
  $('band-knob').onkeydown=e=>{
    const moves={ArrowUp:1,ArrowRight:1,PageUp:1,ArrowDown:-1,ArrowLeft:-1,PageDown:-1};
    let next=null;
    if(e.key in moves)next=bandIndex()+moves[e.key];
    if(e.key==='Home')next=0;if(e.key==='End')next=ACTIVE_BANDS.length-1;
    if(next===null)return;
    e.preventDefault();if(ACTIVE_BANDS[next])selectBand(ACTIVE_BANDS[next]);
  };
  for(const mark of document.querySelectorAll('.band-mark'))mark.onclick=()=>{selectBand(mark.dataset.band);$('band-knob').focus();};
  $('band-select').onchange=e=>selectBand(e.target.value);
  $('gain-knob').onkeydown=e=>{
    const values={ArrowUp:.01,ArrowRight:.01,ArrowDown:-.01,ArrowLeft:-.01,PageUp:.1,PageDown:-.1};
    if(e.key in values){e.preventDefault();setGain(state.gain+values[e.key]);}
    if(e.key==='Home'||e.key==='End'){e.preventDefault();setGain(e.key==='Home'?0:1);}
  };
  setGain(state.gain);
  function step(step){state.step=step;for(const [id,value]of [['step-fine',100],['step-coarse',5000]]){$(id).classList.toggle('active',value===step);$(id).setAttribute('aria-pressed',value===step);}}
  $('step-fine').onclick=()=>step(100);$('step-coarse').onclick=()=>step(5000);
  const increment=amount=>{const [min,max]=bounds();tune(Math.max(min,Math.min(max,state.hz+amount)));};
  $('tune-minus').onclick=()=>increment(-state.step);$('tune-plus').onclick=()=>increment(state.step);
  $('band-slider').oninput=e=>tune(Number(e.target.value)*1000);
  const knob=$('tuning-knob');knob.style.touchAction='none';
  knob.onkeydown=e=>{const values={ArrowUp:100,ArrowRight:100,ArrowDown:-100,ArrowLeft:-100,PageUp:5000,PageDown:-5000};if(e.key in values){e.preventDefault();increment(values[e.key]);}if(e.key==='Home'||e.key==='End'){e.preventDefault();tune(bounds()[e.key==='Home'?0:1]);}};
  rotary(knob,()=>state.hz,tune,bounds,()=>state.step===100?12000:120000);
  knob.onwheel=e=>{if(document.activeElement===knob){e.preventDefault();increment(e.deltaY<0?100:-100);}};
  $('reveal-button').onclick=()=>{if(state.selected){state.revealed.add(state.selected.id);renderRecording();}};
  $('about-button').onclick=()=>$('about-dialog').showModal();
  $('about-project-button').onclick=()=>$('about-project-dialog').showModal();
  document.querySelectorAll('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());
  $('new-session').onclick=()=>$('reset-dialog').showModal();
  $('confirm-reset').onclick=()=>{stopAudio();setLoop(false);state.power=false;state.revealed.clear();state.positions.clear();state.choices.clear();state.selected=null;state.bandHz.clear();updatePower();tune(currentBand().defaultHz);renderRecording();renderAlternatives();$('reset-dialog').close();};
  $('go-receiver').onclick=()=>$('receiver').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  $('theme-button').onclick=()=>{const dark=document.documentElement.dataset.theme!=='dark';document.documentElement.dataset.theme=dark?'dark':'light';$('theme-button').textContent=dark?'Day desk':'Night desk';};
  window.addEventListener('resize',draw);
}
bind();
switchCatalog(currentBand().defaultMode);
