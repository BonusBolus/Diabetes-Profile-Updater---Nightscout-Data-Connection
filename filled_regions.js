// Explicit closed regions avoid Plotly joining disconnected tozeroy/tonexty
// paths diagonally during SVG export. Run after all standard/custom transforms.
function closeFilledRegions(view) {
  const out=[];
  const runs=t=>{const list=[];let run=[];for(let i=0;i<(t.x || []).length;i++){
    if(Number.isFinite(t.x[i]) && Number.isFinite(t.y?.[i]))run.push(i);
    else if(run.length){list.push(run);run=[];}
  }if(run.length)list.push(run);return list;};
  for(let n=0;n<view.data.length;n++){
    const t=view.data[n];
    if(!['tozeroy','tonexty','toself'].includes(t.fill)){out.push(t);continue;}
    if(t.fill==='tonexty'){
      const lower=view.data[n-1];if(!lower)continue;
      const paired={x:t.x,y:t.y.map((v,i)=>Number.isFinite(lower.y?.[i])?v:null)};
      let first=true;
      for(const r of runs(paired)){
        const x=r.map(i=>t.x[i]),y=r.map(i=>t.y[i]);
        out.push({...t,x:x.concat(x.slice().reverse(),x[0]),y:y.concat(r.slice().reverse().map(i=>lower.y[i]),y[0]),fill:'toself',connectgaps:false,showlegend:first && t.showlegend!==false});first=false;
      }
    }else if(t.fill==='tozeroy'){
      for(const r of runs(t)){
        const x=r.map(i=>t.x[i]),y=r.map(i=>t.y[i]);
        out.push({...t,x:[x[0],...x,x[x.length-1],x[0]],y:[0,...y,0,0],mode:'lines',line:{...t.line,width:0},fill:'toself',showlegend:false,hoverinfo:'skip',hovertemplate:null,customdata:null,meta:{...t.meta,kind:'area_fill',legend_entry:false}});
      }
      out.push({...t,fill:'none'});
    }else{
      let first=true;
      for(const r of runs(t)){out.push({...t,x:r.map(i=>t.x[i]),y:r.map(i=>t.y[i]),showlegend:first && t.showlegend!==false});first=false;}
    }
  }
  view.data=out;
}
