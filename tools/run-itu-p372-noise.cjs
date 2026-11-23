// Runs the DJ5IL CCIR 322-3 / ITU-R P.372 model locally. Download http://www.cq-cq.eu/atnoisco.js and rnoise.js into the working directory first; they are not copied into this repo.
const fs=require('fs'),vm=require('vm');
const ctx={console,Math,Number,Array,document:{getElementById:()=>({}),daten:{}}};vm.createContext(ctx);
vm.runInContext(fs.readFileSync('atnoisco.js','utf8'),ctx);
vm.runInContext(fs.readFileSync('rnoise.js','utf8').replace(/main\(\);?\s*$/,''),ctx);
const out=[];
for(const [name,m] of [['Winter (Jan)',1],['Spring (Apr)',4],['Summer (Jul)',7],['Autumn (Oct)',10]]){
 for(const lt of [22,2]){
  vm.runInContext(`month=${m};lat=39.95;lon=-75.17;f=4.9;rxbw=6000;lt=${lt};mncat=2;calc="n";noise();__r={fama:typeof fama!=="undefined"?fama:null,dua:typeof dua!=="undefined"?dua:null,dla:typeof dla!=="undefined"?dla:null,famm,famg,famt,dut,dlt}`,ctx);
  out.push({season:name,lt,...Object.fromEntries(Object.entries(ctx.__r).map(([k,v])=>[k,v==null?null:+v.toFixed(1)]))});
 }}
console.table(out);
