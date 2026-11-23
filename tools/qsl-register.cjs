const fs=require('fs'),path=require('path');
const base=path.resolve(__dirname,'../research/qsl');
const stations=JSON.parse(fs.readFileSync(path.join(base,'master-stations.json')));
const countries={
 'PERU':'Peru','BRAZIL':'Brazil','BOLIVIA':'Bolivia','COLOMBIA':'Colombia','ECUADOR':'Ecuador','VENEZUELA':'Venezuela','GUATEMALA':'Guatemala','HONDURAS':'Honduras',
 'INDONESIA':'Indonesia','SULAWESI (INDONESIA)':'Indonesia','JAVA (INDONESIA)':'Indonesia','INDONESIA (MOLUCCA ISLANDS)':'Indonesia','INDONESIA (IRIAN JAYA)':'Indonesia',
 'ANGOLA':'Angola','BENIN':'Benin','CAMEROON':'Cameroun','CENTRAL AFRICAN REPUBLIC':'Central African Empire','CENTRAL AFRICAN REP':'Central African Empire','CHAD':'Chad','CONGO (BRAZZAVILLE)':'Congo','DJIBOUTI':'Djibouti','EQUATORIAL GUINEA':'Equatorial Guinea','GABON':'Gabon','GAMBIA':'Gambia','GHANA':'Ghana','GUINEA':'Guinea','GUINEA BISSAU':'Guinea-Bissau','IVORY COAST':'Ivory Coast','KENYA':'Kenya','LESOTHO':'Lesotho','LIBERIA':'Liberia','MADAGASCAR':'Madagascar','MALI':'Mali','MAURITANIA':'Mauritania','MOZAMBIQUE':'Mozambique','SOUTHWEST AFRICA':'Namibia','NIGER':'Niger','PORTUGUESE GUINEA':'Portuguese Guinea','SENEGAL':'Senegal','SOUTH AFRICA':'South Africa','SUDAN':'Sudan','SWAZILAND':'Swaziland-Eswatini','TANZANIA':'Tanzania','TOGO':'Togo','UPPER VOLTA':'Upper Volta','ZAMBIA':'Zambia','ZAIRE':'Zaire',
 'AFGHANISTAN':'Afghanistan','AZERBAIJAN SSR':'Russia-USSR','CHINA':'China','INDIA':'India','NEPAL':'Nepal','KARELO-FINNISH SSR':'Russia-USSR','KIRGHIZ SSR':'Russia-USSR','TADZHIK SSR':'Russia-USSR','GEORGIAN SSR':'Russia-USSR','SRI LANKA':'Sri Lanka','AUSTRALIA':'Australia','MARSHALL ISLANDS':'Marshall Islands','SOLOMON ISLANDS':'Solomon Islands','COSTA RICA':'Costa Rica','DOMINICAN REPUBLIC':'Dominican Republic','HAITI':'Haiti','SURINAM':'Suriname','TURKS & CAICOS':'Turks &amp; Caicos','ALBANIA':'Albania','ITALY':'Italy','PORTUGAL':'Portugal','IRAN':'Iran','SAUDI ARABIA':'Saudi Arabia','UNITED ARAB EMIRATES':'United Arab Emirates','SOUTH YEMEN':'South Yemen','YEMEN (SOUTH)':'North Yemen'
};
function clean(s){return s.replace(/<[^>]*>/g,' ').replace(/&nbsp;|&#160;/g,' ').replace(/&amp;/g,'&').replace(/&#8220;|&#8221;/g,'"').replace(/\s+/g,' ').trim()}
const galleries={};
for(const f of fs.readdirSync(base).filter(f=>f.startsWith('museum-')&&f.endsWith('.json'))){
 const p=JSON.parse(fs.readFileSync(path.join(base,f))).pages?.[0];if(!p||p.error)continue;
 const h=p.raw_html||p.content||'';
 const links=[...h.matchAll(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)].map(m=>({url:new URL(m[1],p.url).href,title:clean(m[2]),index_url:p.url})).filter(x=>x.title&&/^https?:/.test(x.url)&&!/\.(mp3|jpg|gif|png)$/i.test(x.url));
 const key=f.slice(7,-5);galleries[key]={url:p.url,text:clean(h),links};
}
function norm(s){return s.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().replace(/\([^)]*\)/g,' ').replace(/[^\p{L}\p{N}]+/gu,' ').split(' ').filter(t=>t&&!['radio','r','de','del','da','do','dos','du','la','el','los','las','the','of','emissora','emisora','emisoras','emissore','regional','nacional','national','rri','station','provincial','service','sign','on','off','one','id','part','side','in','english','a','b'].includes(t));}
function score(a,b){const x=new Set(norm(a)),y=new Set(norm(b));const n=[...x].filter(t=>y.has(t)).length;return x.size&&y.size?2*n/(x.size+y.size):0}
const prefixes=Object.keys(countries).sort((a,b)=>b.length-a.length);
const candidates=stations.map((s,i)=>{
 const prefix=prefixes.find(p=>s.station.startsWith(p+' '));
 const country=prefix?countries[prefix]:'',name=prefix?s.station.slice(prefix.length+1):s.station;
 const g=galleries[country];let best=(g?.links||[]).map(a=>({...a,score:score(name,a.title)})).sort((a,b)=>b.score-a.score).slice(0,2);
 return {i,station:s.station,country,name,records:s.records,index_url:g?.url||'',candidates:best};
});
fs.writeFileSync(path.join(base,'candidate-matches.json'),JSON.stringify(candidates,null,2));
fs.writeFileSync(path.join(base,'gallery-links.json'),JSON.stringify(galleries,null,2));
for(const x of candidates)console.log(`${x.i}\t${x.station}\t${x.candidates[0]?.score.toFixed(2)||'0'}\t${x.candidates[0]?.title||''}\t${x.candidates[0]?.url||''}`);
