// One renderer for the individual-night Insight in the app and report.
// Values remain on a common glucose scale; rows are never normalized/averaged.
function sleepOverviewHours(options){
  const n=Number(options.overviewAfterHours ?? 4);return Number.isFinite(n)?Math.max(0,Math.min(12,n)):4;
}
function sleepOverviewWindow(row,hours){
  const finish=Math.min(Date.parse(row.end_stamp),Date.parse(row.wake_stamp)+hours*3600000);
  const d=new Date(finish),parts=new Intl.DateTimeFormat('en-CA',{timeZone:row.zone || 'UTC',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(d);
  const p=Object.fromEntries(parts.map(p=>[p.type,p.value]));
  return (Date.UTC(+p.year,+p.month-1,+p.day)-Date.parse(row.date+'T00:00:00Z'))/3600000+(+p.hour)+(+p.minute)/60;
}
function sleepOverviewNote(hours){
  return 'Rows = nights by wake date, aligned by local clock; loaded previous evening included. Shading: recorded stages; grey = unknown, pale grey = post-wake. Up to '+hours+' h after waking, ending at next sleep/data end. Shared glucose scale; >10-min gaps unfilled; no averaging.';
}
function renderSleepOverview(view,rows,options,range=null){
  const unit=navigation.unit || 'mmol/L',factor=unit==='mg/dL'?18:1,hours=sleepOverviewHours(options),low=4*factor,high=10*factor;
  const green=view.layout.meta.glucose_color || '#32cd32',red='#f44336';
  const end=r=>sleepOverviewWindow(r,hours);
  const visible=rows.map(r=>({...r,shownEnd:end(r),indices:r.x.map((_,i)=>i).filter(i=>r.x[i]===null || r.after[i]<=hours)}));
  const values=(view.layout.meta.sleep_overview_rows || rows).flatMap(r=>r.glucose.filter((v,i)=>Number.isFinite(v)&&r.after[i]<=hours));
  const peak=values.length?values.reduce((a,b)=>Math.max(a,b),-Infinity):20*factor,minimum=values.length?values.reduce((a,b)=>Math.min(a,b),Infinity):0,pad=Math.max(.3*factor,(peak-minimum)*.08);
  const yRange=options.fitY&&values.length?[Math.max(0,minimum-pad),peak+pad]:[0,peak>20*factor?Math.ceil(peak*1.05/factor)*factor:20*factor];
  const extent=range || (rows.length?[Math.floor(Math.min(...rows.map(r=>r.start))),Math.ceil(Math.max(...visible.map(r=>r.shownEnd)))]:[0,12]);
  const layout=view.layout;
  for(const key of Object.keys(layout))if(/^[xy]axis\d*$/.test(key))delete layout[key];
  view.data=[];layout.shapes=[];layout.annotations=[];
  const allRows=layout.meta.sleep_overview_rows || rows;
  const signals=[...new Set(options.sleepFields || [])].filter(k=>allRows.some(r=>r.signals?.[k]?.y.some(Number.isFinite)));
  const underneath=!options.sleepOverlay,rowHeight=88+(underneath?signals.length*48:0),total=Math.max(1,rows.length)*rowHeight;
  const signalRanges=Object.fromEntries(signals.map(k=>{const vs=allRows.flatMap(r=>(r.signals?.[k]?.y || []).filter((v,i)=>Number.isFinite(v)&&r.signals[k].after[i]<=hours)),lo=vs.reduce((a,b)=>Math.min(a,b),Infinity),hi=vs.reduce((a,b)=>Math.max(a,b),-Infinity),pad=Math.max((hi-lo)*.1,Math.abs(hi)*.02,.5);return [k,vs.length?[lo-pad,hi+pad]:[0,1]];}));
  layout.height=110+total;
  layout.margin={l:130,r:signals.length&&!underneath?90:30,t:40,b:60};layout.barmode='overlay';
  layout.xaxis={type:'linear',range:extent,autorange:false,domain:[0,1],anchor:'free',position:0,title:{text:'Local time'},showgrid:true,zeroline:false,
    tickvals:[],ticktext:[]};
  const step=extent[1]-extent[0]>24?4:2;
  for(let x=Math.ceil(extent[0]/step)*step;x<=extent[1];x+=step){layout.xaxis.tickvals.push(x);layout.xaxis.ticktext.push(String(((x%24)+24)%24).padStart(2,'0')+':00'+(x<0?' −1d':x>=24?' +1d':''));}
  layout.showlegend=true;layout.legend={orientation:'h',yref:'container',y:0,yanchor:'bottom',font:{size:10},itemsizing:'constant'};
  const seen=new Set(),n=Math.max(1,rows.length);
  for(const [i,row] of visible.entries()){
    const top=1-i*rowHeight/total;
    const axis=i?'y'+(i+1):'y',axisKey=i?'yaxis'+(i+1):'yaxis',domain=[top-80/total,top-8/total];
    layout[axisKey]={domain,range:yRange,autorange:false,anchor:'x',tickvals:[4*factor,10*factor,20*factor].filter(v=>v>=yRange[0]&&v<=yRange[1]),
      tickfont:{size:9},showgrid:false,zeroline:false,title:{text:i===0?unit:'',font:{size:10},standoff:2}};
    layout.annotations.push({xref:'paper',yref:'paper',x:0,y:(domain[0]+domain[1])/2,xanchor:'right',xshift:-42,
      text:row.date.slice(5)+'<br>'+row.start_label+'–'+row.wake_label,showarrow:false,font:{size:10},align:'right'});
    const shade=(x0,x1,color,name)=>{if(x1>x0)layout.shapes.push({type:'rect',xref:'x',yref:axis,x0,x1,y0:yRange[0],y1:yRange[1],line:{width:0},fillcolor:color,layer:'below',name});};
    shade(row.start,row.wake,'rgba(144,164,174,.13)','Recorded sleep session');
    shade(row.wake,row.shownEnd,'rgba(144,164,174,.045)','After waking');
    for(const stage of ['deep_sleep','light_sleep','rem_sleep','awake','unknown']){
      const intervals=row.stages.filter(s=>s.stage===stage&&s.end>s.start);if(!intervals.length)continue;
      const first=intervals[0];
      view.data.push({type:'bar',x:intervals.map(s=>(s.start+s.end)/2),y:intervals.map(()=>yRange[1]-yRange[0]),base:yRange[0],width:intervals.map(s=>s.end-s.start),yaxis:axis,
        name:first.label,legendgroup:'sleep-overview-'+stage,showlegend:!seen.has(stage),marker:{color:first.color,line:{width:0}},opacity:.22,
        customdata:intervals.map(s=>[row.date,s.label,s.detail]),meta:{kind:'sleep_overview_stage',label:first.label,date:row.date}});seen.add(stage);
    }
    for(const boundary of [low,high])layout.shapes.push({type:'line',xref:'x',yref:axis,x0:row.start,x1:row.shownEnd,y0:boundary,y1:boundary,
      line:{color:'rgba(50,150,50,.25)',width:.6,dash:'dot'},layer:'below',name:'Glucose range'});
    const xs=row.indices.map(j=>row.x[j]),ys=row.indices.map(j=>row.glucose[j]);
    const trace={type:'scatter',x:xs,y:ys,yaxis:axis,mode:'lines',line:{color:green,width:2},connectgaps:false,
      name:'Glucose',legendgroup:'sleep-overview-glucose',showlegend:i===0,customdata:row.indices.map(j=>row.clocks[j]),
      meta:{kind:'sleep_overview_glucose',label:'Glucose',unit,date:row.date}};
    view.data.push(trace);
    const excursions=insightExcursions(trace,low,high);excursions.yaxis=axis;view.data.push(excursions);
    for(const [j,key] of signals.entries()){
      const signal=row.signals?.[key];if(!signal)continue;
      const number=rows.length+1+i*signals.length+j,ref='y'+number,axisKey='yaxis'+number;
      const signalDomain=underneath?[top-(88+(j+1)*48-7)/total,top-(88+j*48+5)/total]:domain;
      layout[axisKey]={domain:signalDomain,range:signalRanges[key],autorange:false,anchor:'x',showgrid:false,zeroline:false,tickfont:{size:8,color:signal.color},title:{text:underneath?signal.unit:signal.label+' ('+signal.unit+')',font:{size:9,color:signal.color},standoff:2},...(underneath?{}:{overlaying:axis,side:'right',anchor:'free',position:1,autoshift:true})};
      if(underneath)layout.annotations.push({xref:'paper',yref:'paper',x:0,y:(signalDomain[0]+signalDomain[1])/2,xanchor:'right',xshift:-45,text:signal.label,showarrow:false,font:{size:9,color:signal.color}});
      const xs=[],ys=[],clocks=[];
      signal.x.forEach((x,k)=>{
        if(x===null || signal.after[k]<=hours){xs.push(x);ys.push(signal.y[k]);clocks.push(signal.clocks[k]);}
        else if(signal.interval&&k>0&&signal.x[k-1]!==null&&signal.after[k-1]<=hours){xs.push(row.shownEnd);ys.push(signal.y[k]);clocks.push('Until '+hours+' h after waking');}
      });
      view.data.push({type:'scatter',mode:'lines+markers',x:xs,y:ys,yaxis:ref,line:{color:signal.color,width:1.5},marker:{color:signal.color,size:3},connectgaps:false,
        name:signal.label,legendgroup:'sleep-overview-'+key,showlegend:!seen.has(key),customdata:clocks,hovertemplate:'%{customdata}<br>%{y} '+signal.unit+'<extra>'+signal.label+'</extra>',
        meta:{kind:'sleep_overview_signal',dataset:key,label:signal.label,unit:signal.unit,date:row.date}});seen.add(key);
    }
    if(!ys.some(Number.isFinite))layout.annotations.push({xref:'x',yref:axis,x:(row.start+row.shownEnd)/2,y:(yRange[0]+yRange[1])/2,text:'No glucose readings',showarrow:false,font:{size:10,color:'#888'}});
  }
  layout.meta={...layout.meta,sleep_overview:true,sleep_overview_visible:rows,insight_relationship:false,empty:!rows.length,
    insight_note:sleepOverviewNote(hours),insight_summary:[],sleep_overview_options:{...options},sleep_overview_range:extent,sleep_overview_row_height:rowHeight};
  if(!rows.length){layout.yaxis={range:yRange};layout.annotations.push({xref:'paper',yref:'paper',x:.5,y:.5,text:'No recorded sleep sessions ending on the selected dates',showarrow:false});}
}
function transformSleepOverview(view,index){
  const options=panelStateAt(index).insight,rows=(view.layout.meta.sleep_overview_rows || []).slice().sort((a,b)=>a.id.localeCompare(b.id));
  const count=7,page=Math.max(0,Math.min(Math.ceil(rows.length/count)-1,Math.floor(Number(options.overviewPage)||0)));
  renderSleepOverview(view,rows.slice(page*count,(page+1)*count),options);
  view.layout.meta.insight_note+=' Showing nights '+(rows.length?page*count+1:0)+'–'+Math.min(rows.length,(page+1)*count)+' of '+rows.length+'.';
}
function reportSleepOverviewViews(graph,options){
  const rows=(graph.layout.meta.sleep_overview_rows || []).slice().sort((a,b)=>a.id.localeCompare(b.id)),settings=graph.layout.meta.sleep_overview_options;
  // Respect fixed graphs/page; divide long lists into readable continuation panels.
  const count=Math.max(1,Math.floor(((options.height || 400)-95)/(graph.layout.meta.sleep_overview_row_height || 88))),views=[];
  const range=rows.length?[Math.floor(Math.min(...rows.map(r=>r.start))),Math.ceil(Math.max(...rows.map(r=>sleepOverviewWindow(r,sleepOverviewHours(settings)))))]:[0,12];
  for(let at=0;at<rows.length;at+=count){
    const view=JSON.parse(JSON.stringify({data:[],layout:graph.layout})),part=rows.slice(at,at+count);
    renderSleepOverview(view,part,settings,range);
    view.layout.title={...view.layout.title,text:'Sleep + glucose — Nights · '+part[0].date+' – '+part.at(-1).date};views.push(view);
  }
  return views;
}
