(function(root){
  'use strict';
  function buildGroups(records){
    const map=new Map();
    for(const r of records){
      if(r.testEligible===false||!Number.isFinite(r.frequencyHz))continue;
      if(!map.has(r.frequencyHz))map.set(r.frequencyHz,[]);
      map.get(r.frequencyHz).push(r);
    }
    const groups=[...map].sort((a,b)=>a[0]-b[0]).map(([hz,entries])=>({
      hz,records:entries.sort((a,b)=>(a.sortKey??a.inventoryId)-(b.sortKey??b.inventoryId)),radius:1000,retainRadius:1000
    }));
    groups.forEach((g,i)=>{
      const gap=Math.min(i?g.hz-groups[i-1].hz:Infinity,i+1<groups.length?groups[i+1].hz-g.hz:Infinity);
      g.radius=Math.min(1000,gap*.4);
      g.retainRadius=Math.min(g.radius+Math.min(50,g.radius*.15),gap/2-1);
    });
    return groups;
  }
  function findGroup(groups,hz,currentHz=null){
    let lo=0,hi=groups.length;
    while(lo<hi){const mid=(lo+hi)>>1;if(groups[mid].hz<hz)lo=mid+1;else hi=mid;}
    const candidates=[groups[lo-1],groups[lo]].filter(Boolean);
    const nearest=candidates.sort((a,b)=>Math.abs(a.hz-hz)-Math.abs(b.hz-hz)||a.hz-b.hz)[0];
    if(nearest&&Math.abs(nearest.hz-hz)<=nearest.radius)return nearest;
    const previous=candidates.find(g=>g.hz===currentHz);
    return previous&&Math.abs(previous.hz-hz)<=previous.retainRadius?previous:null;
  }
  const api={buildGroups,findGroup};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.ReceiverCatalog=api;
})(typeof window==='undefined'?globalThis:window);
