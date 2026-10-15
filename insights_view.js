function insightControls(parent,panel,spec,content=parent){
  if(spec.layout.meta?.kind!=='insight')return;
  const state=ensurePanelState(spec),key=spec.layout.meta.insight;
  if(key==='meal'){
    const label=document.createElement('label'),input=document.createElement('input');
    input.type='number';input.min='0';input.step='1';input.value=insightCarbCutoff(state.insight);input.style.width='4.5em';
    input.setAttribute('aria-label','Carb cutoff (g)');input.title='Include recorded carb entries strictly above this amount. Zero includes all positive entries.';
    input.addEventListener('change',()=>{const cutoff=insightCarbCutoff({minCarbs:input.value});input.value=cutoff;changePanelState(panel.graphIndex,s=>{s.insight.minCarbs=cutoff;});});
    label.append('Carbs > ',input,' g');parent.appendChild(label);
    panelUIs.push({insightOnly:true,panel,id:state.id,el:input,field:'minCarbs'});
    const button=document.createElement('button');button.type='button';button.setAttribute('aria-label','Starting COB filter');
    button.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{s.insight.filterStartCOB=!s.insight.filterStartCOB;}));parent.appendChild(button);
    panelUIs.push({insightOnly:true,panel,id:state.id,el:button,field:'filterStartCOB',toggle:o=>'Start COB filter: '+(o.filterStartCOB?'on':'off')});
    const wrap=document.createElement('label'),slider=document.createElement('input'),value=document.createElement('span');
    slider.type='range';slider.min='0';slider.step='1';slider.max=String(Math.max(100,Math.ceil(Math.max(0,...(spec.layout.meta.series || []).map(s=>Number.isFinite(s.meal?.cob)?s.meal.cob:0))/10)*10));
    slider.value=insightCOBCutoff(state.insight);slider.setAttribute('aria-label','Maximum starting COB (g)');
    slider.title='Last recorded COB at or before the carb entry, no older than 10 minutes. Missing COB is excluded while this filter is on.';
    const update=()=>{value.textContent='Starting COB ≤ '+slider.value+' g';};update();
    slider.addEventListener('input',update);slider.addEventListener('change',()=>changePanelState(panel.graphIndex,s=>{s.insight.maxStartCOB=Number(slider.value);}));
    wrap.append(value,slider);parent.appendChild(wrap);
    panelUIs.push({insightOnly:true,panel,id:state.id,el:slider,field:'maxStartCOB',wrap,visible:o=>o.filterStartCOB===true,onSync:update});
  }
  const relation=o=>key==='sleep' && o.sleepView==='relationship';
  const overview=o=>key==='sleep' && o.sleepView==='overview';
  if(['meal','sleep','activity_during','activity_after','site_age','sensor'].includes(key))for(const [field,label] of [['showIOB','IOB'],['showCOB','COB']]){
    const el=document.createElement('button');el.type='button';el.setAttribute('aria-label',label+' overlay');
    el.title='Uploaded estimates aligned to the same event windows; gaps stay missing. Hover shows contributing periods.';
    el.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{s.insight[field]=!s.insight[field];s.axisRanges={};}));content.appendChild(el);
    panelUIs.push({insightOnly:true,panel,id:state.id,el,field,visible:o=>!relation(o)&&!overview(o),toggle:o=>label+': '+(o[field]?'on':'off')});
  }
  const select=(name,items,field,visible=null)=>{const el=document.createElement('select');el.setAttribute('aria-label',name);
    for(const [v,label] of items){const o=document.createElement('option');o.value=v;o.textContent=label;el.appendChild(o);}el.value=state.insight[field];
    el.addEventListener('change',()=>changePanelState(panel.graphIndex,s=>{s.insight[field]=el.value;if(field!=='aggregation')s.axisRanges={};}));parent.appendChild(el);
    panelUIs.push({insightOnly:true,panel,id:state.id,el,field,visible});return el;};
  if(key==='sleep'){
    select('Sleep insight view',[['overnight','During sleep'],['overview','Nights · sleep + glucose'],['after','After waking'],['relationship','Sleep → next-day glucose']],'sleepView');
    select('Sleep relationship X',[['asleep_hours','Recorded asleep (h)'],['hrv','Overnight HRV (ms)']],'relationX',relation);
    select('Sleep relationship Y',[['mean','Next-day mean glucose'],['tir','Next-day time in range'],['below','Next-day time below range']],'relationY',relation);
    const wrap=document.createElement('label'),slider=document.createElement('input'),text=document.createElement('span');
    slider.type='range';slider.min='0';slider.max='12';slider.step='.5';slider.value=sleepOverviewHours(state.insight);slider.setAttribute('aria-label','Overview hours after waking');
    const update=()=>{text.textContent='After waking: '+slider.value+' h';};update();slider.addEventListener('input',update);
    slider.addEventListener('change',()=>changePanelState(panel.graphIndex,s=>{s.insight.overviewAfterHours=Number(slider.value);}));
    wrap.append(text,slider);parent.appendChild(wrap);panelUIs.push({insightOnly:true,panel,id:state.id,el:slider,field:'overviewAfterHours',wrap,visible:overview,onSync:update});
    const signalLayout=document.createElement('button');signalLayout.type='button';signalLayout.setAttribute('aria-label','Night sleep signal layout');
    signalLayout.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{s.insight.sleepOverlay=!s.insight.sleepOverlay;s.axisRanges={};}));parent.appendChild(signalLayout);
    panelUIs.push({insightOnly:true,panel,id:state.id,el:signalLayout,field:'sleepOverlay',visible:overview,toggle:o=>'Sleep signals: '+(o.sleepOverlay?'Overlay':'Underneath')});
    const choices=document.createElement('details'),heading=document.createElement('summary');heading.textContent='Sleep overlays';choices.appendChild(heading);content.appendChild(choices);
    panelUIs.push({insightOnly:true,panel,id:state.id,el:choices,field:'sleepFields',visible:overview});
    for(const [field,label] of Object.entries(sleepFields)){
      const el=document.createElement('button');el.type='button';el.textContent=label;el.setAttribute('aria-label','Night sleep overlay '+label);choices.appendChild(el);
      const available=(spec.layout.meta.sleep_overview_rows || []).some(r=>r.signals?.[field]?.y.some(Number.isFinite));
      el.title=available?'Show recorded '+label.toLowerCase():'No recorded '+label.toLowerCase()+' in the loaded nights';
      el.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{const fields=s.insight.sleepFields || [];s.insight.sleepFields=fields.includes(field)?fields.filter(k=>k!==field):[...fields,field];s.axisRanges={};}));
      panelUIs.push({insightOnly:true,panel,id:state.id,el,field:'sleepFields',visible:overview,onSync:()=>{el.disabled=!ready||syncing||!available;el.setAttribute('aria-pressed',String((panelStateAt(panel.graphIndex).insight.sleepFields || []).includes(field)));}});
    }
    for(const [step,label] of [[-1,'Older nights'],[1,'Newer nights']]){
      const el=document.createElement('button');el.type='button';el.textContent=label;
      const last=Math.max(0,Math.ceil((spec.layout.meta.sleep_overview_rows || []).length/7)-1);
      el.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{s.insight.overviewPage=Math.max(0,Math.min(last,(s.insight.overviewPage || 0)+step));}));parent.appendChild(el);
      panelUIs.push({insightOnly:true,panel,id:state.id,el,field:'overviewPage',visible:overview,onSync:()=>{const p=Math.min(last,panelStateAt(panel.graphIndex).insight.overviewPage || 0);el.disabled=!ready||syncing||(step<0?p<=0:p>=last);}});
    }
  }
  if(key==='site_age')select('Site window',[['full','Until next replacement'],['limited','First hours']],'siteWindow');
  const statistic=select('Glucose and overlays statistic',[['Median','Median · glucose + overlays'],['Average','Average · glucose + overlays']],'aggregation',o=>!relation(o)&&!overview(o));
  statistic.title='One statistic for glucose and all enabled IOB/COB overlays. Bands always show the 25th–75th percentiles.';
  if(key==='sensor_variability')select('Sensor-age variability metric',[['rate','Variability · |ΔBG/Δt|'],['jump','Jumpiness · |Δ slope|']],'metric');
  else if(key!=='sensor')select('Event glucose display',[['absolute','Absolute glucose'],['delta','Δ glucose from t=0']],'normalization',o=>!relation(o)&&!overview(o));
  if(key!=='sensor_variability'){
    const el=document.createElement('button');el.type='button';el.setAttribute('aria-label','Insight glucose Y-axis');
    el.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{s.insight.fitY=!s.insight.fitY;s.axisRanges={};}));parent.appendChild(el);
    panelUIs.push({insightOnly:true,panel,id:state.id,el,field:'fitY',visible:o=>overview(o)|| (relation(o)?o.relationY==='mean':o.normalization!=='delta'),
      toggle:o=>'Y axis: '+(o.fitY?'fitted':navigation.unit==='mg/dL'?'0–360':'0–20')});
  }
  if(['activity_after','site_age','meal','sleep'].includes(key)){
    const prefix=key==='site_age'?'First: ':key==='meal'?'After carbs: ':key==='sleep'?'After waking: ':'After event: ';
    const label=document.createElement('label'),slider=document.createElement('input'),text=document.createElement('span');slider.type='range';slider.min='.5';slider.max=key==='sleep'?'24':key==='meal'?'12':'72';slider.step='.5';slider.value=state.insight.duration;slider.setAttribute('aria-label','Post-event hours');
    text.textContent=prefix+slider.value+' h';slider.addEventListener('input',()=>{text.textContent=prefix+slider.value+' h';});slider.addEventListener('change',()=>changePanelState(panel.graphIndex,s=>{s.insight.duration=Number(slider.value);}));label.append(text,slider);parent.appendChild(label);
    if(key==='site_age')slider.setAttribute('aria-label','Site window hours');
    panelUIs.push({insightOnly:true,panel,id:state.id,el:slider,wrap:label,text,prefix,field:'duration',visible:o=>key==='site_age'?o.siteWindow==='limited':key!=='sleep' || !['overnight','overview'].includes(o.sleepView)});
  }
}
function insightMedian(values,p=.5){const vs=values.filter(Number.isFinite).sort((a,b)=>a-b);if(!vs.length)return null;const pos=(vs.length-1)*p,lo=Math.floor(pos);return vs[lo]+(vs[Math.ceil(pos)]-vs[lo])*(pos-lo);}
function insightAggregate(values,aggregation){const vs=values.filter(Number.isFinite);return !vs.length?null:aggregation==='Average'?vs.reduce((a,b)=>a+b,0)/vs.length:insightMedian(vs);}
function insightCarbCutoff(options){const value=Number(options.minCarbs ?? 0);return Number.isFinite(value)?Math.max(0,value):0;}
function insightCOBCutoff(options){const n=Number(options.maxStartCOB ?? 0);return Number.isFinite(n)?Math.max(0,n):0;}
function selectedInsightSeries(meta,options,after=false){
  const series=(after?meta.after_series:meta.series) || [];
  // Filter inclusion only. Source periods still end at the next carb record,
  // even when that next record is below the cutoff.
  return meta.insight==='meal'?series.filter(s=>Number.isFinite(s.meal?.carbs)&&s.meal.carbs>insightCarbCutoff(options) && (!options.filterStartCOB || Number.isFinite(s.meal.cob) && s.meal.cob<=insightCOBCutoff(options))):series;
}
// Immutable aligned observations are shared by copies/mode banks. Cache only the
// calculation, not panel settings or Plotly objects; axis/visual edits reuse it.
const insightCalculations=new Map();
function calculateInsight(series,metric,delta,limit,bin,aggregation){
  const bins=new Map(),traces=[];let noBaseline=0,alignedBaselines=0,maximum=0;
  for(const s of series){
    if(delta && !Number.isFinite(s.baseline)){noBaseline++;continue;}
    const xs=[],ys=[],per=new Map();let first=null;
    for(let i=0;i<s.x.length;i++){
      const x=s.x[i],y=s[metric]?.[i];if(!Number.isFinite(x)){xs.push(null);ys.push(null);continue;}if(x>=limit)continue;
      const value=Number.isFinite(y)?y-(delta?s.baseline:0):null;xs.push(x/60);ys.push(value);
      if(Number.isFinite(value)){if(first===null)first=x;maximum=Math.max(maximum,x/60);const slot=Math.floor(x/bin)*bin,values=per.get(slot)||[];values.push(value);per.set(slot,values);}
    }
    if(delta && first!==null && first<=10){alignedBaselines++;if(first>0){xs.unshift(0);ys.unshift(0);}}
    for(const [slot,values] of per){const valuesAt=bins.get(slot)||[];valuesAt.push(insightAggregate(values,aggregation));bins.set(slot,valuesAt);}
    if(ys.some(Number.isFinite))traces.push({type:'scatter',x:xs,y:ys,mode:'lines',line:{width:1.1},connectgaps:false,opacity:.25,name:s.label,
      meta:{kind:'insight_event',label:s.label,event_id:s.id,date:s.date || s.label.match(/\d{4}-\d{2}-\d{2}/)?.[0]},showlegend:false});
  }
  const last=Math.max(0,...bins.keys()),xs=[],aggregate=[],lower=[],upper=[],counts=[];
  for(let slot=0;slot<=last;slot+=bin){const vals=bins.get(slot)||[];xs.push((slot+bin/2)/60);aggregate.push(insightAggregate(vals,aggregation));lower.push(vals.length>=2?insightMedian(vals,.25):null);upper.push(vals.length>=2?insightMedian(vals,.75):null);counts.push(vals.length);}
  const band=[];
  for(const [ql,qh,label] of [[.10,.90,'10–90%'],[.25,.75,'25–75%']]){
    const loValues=xs.map((_,i)=>{const vals=bins.get(i*bin)||[];return vals.length>=2?insightMedian(vals,ql):null;});
    const hiValues=xs.map((_,i)=>{const vals=bins.get(i*bin)||[];return vals.length>=2?insightMedian(vals,qh):null;});let start=null,first=true;
    for(let i=0;i<=xs.length;i++){
      if(i<xs.length && Number.isFinite(loValues[i])&&Number.isFinite(hiValues[i])){if(start===null)start=i;continue;}
      if(start!==null){let xx=xs.slice(start,i),lo=loValues.slice(start,i),hi=hiValues.slice(start,i);if(xx.length===1){xx=[xx[0]-bin/120,xx[0]+bin/120];lo=[lo[0],lo[0]];hi=[hi[0],hi[0]];}
        band.push({type:'scatter',x:xx.concat(xx.slice().reverse()),y:lo.concat(hi.slice().reverse()),mode:'lines',line:{width:0},fill:'toself',fillcolor:'rgba(70,150,190,.22)',name:label,legendgroup:'insight-'+label,showlegend:first,hoverinfo:'skip',meta:{kind:'insight_band',percentile:label,legend_entry:first}});first=false;start=null;}
    }
  }
  if(delta && alignedBaselines){xs.unshift(0);aggregate.unshift(0);counts.unshift(alignedBaselines);}
  return {traces,band,xs,aggregate,counts,maximum,noBaseline};
}
// Absolute Insight curves use the glucose scale and thresholds. Their faint
// event curves retain the event-aligned analysis identity. Apply
// this after copying calculated arrays so panel styles never enter the cache.
function insightExcursions(trace,low,high){
  const x=[],y=[];
  const append=(ax,ay,bx,by)=>{
    if(x.length && (x[x.length-1]!==ax || y[y.length-1]!==ay)){x.push(null);y.push(null);}
    if(!x.length || x[x.length-1]!==ax || y[y.length-1]!==ay){x.push(ax);y.push(ay);}
    x.push(bx);y.push(by);
  };
  for(let i=1;i<trace.x.length;i++){
    const ax=trace.x[i-1],bx=trace.x[i],ay=trace.y[i-1],by=trace.y[i];
    if(![ax,bx,ay,by].every(Number.isFinite))continue;
    // Clip each segment at the thresholds, preserving both sides when a
    // segment crosses the complete target range. Never bridge missing bins.
    for(const [bound,below] of [[low,true],[high,false]]){
      const outside=v=>below?v<bound:v>bound,a=outside(ay),b=outside(by);
      if(!a && !b)continue;
      const cross=a===b?null:(bound-ay)/(by-ay),from=a?0:cross,to=b?1:cross;
      append(ax+(bx-ax)*from,ay+(by-ay)*from,ax+(bx-ax)*to,ay+(by-ay)*to);
    }
  }
  return {type:'scatter',x,y,mode:'lines',connectgaps:false,line:{color:'#f44336',width:trace.line.width},
    showlegend:false,hoverinfo:'skip',meta:{kind:'insight_excursion'}};
}
function styleInsightGlucose(view,unit,fitY=false){
  const scale=unit==='mmol/L'?1:18,low=4*scale,high=10*scale;
  const green=view.layout.meta.glucose_color || '#32cd32',red='#f44336';let peak=0,minimum=Infinity;
  const color=y=>Number.isFinite(y)&&(y<low || y>high)?red:green;
  let excursion=null;
  for(const t of view.data){
    for(const y of t.y || [])if(Number.isFinite(y)){peak=Math.max(peak,y);minimum=Math.min(minimum,y);}
    if(t.meta?.kind==='insight_band')t.fillcolor='rgba(50,205,50,.18)';
    if(!['insight_event','insight_median','insight_relationship'].includes(t.meta?.kind))continue;
    const reference=t.meta.kind==='insight_median';
    const relationship=t.meta.kind==='insight_relationship';
    t.mode=relationship?'markers':'lines+markers';t.line={...t.line,color:reference?green:'#45a4c8'};
    t.marker={color:t.y.map(color),size:t.y.map(y=>relationship?7:reference?4:Number.isFinite(y)&&(y<low || y>high)?4:2),line:{width:0}};
    if(reference)excursion=insightExcursions(t,low,high);
  }
  if(excursion?.x.length)view.data.push(excursion);
  const maximum=peak>20*scale?Math.ceil(peak*1.05/scale)*scale:20*scale;
  const padding=Math.max(.3*scale,(peak-minimum)*.08);
  view.layout.yaxis={...view.layout.yaxis,autorange:false,range:fitY && Number.isFinite(minimum)?[Math.max(0,minimum-padding),peak+padding]:[0,maximum]};
  view.layout.shapes.push({type:'rect',name:'Insight glucose range',xref:'x domain',yref:'y',x0:0,x1:1,y0:low,y1:high,
    line:{width:0},fillcolor:'rgba(50,205,50,.12)',layer:'below'});
  view.data.push({type:'scatter',x:[null],y:[null],mode:'lines',name:'Range '+low+'–'+high,
    line:{color:'rgba(50,205,50,.5)',width:8},hoverinfo:'skip',meta:{kind:'insight_range',legend_entry:true}},
    {type:'scatter',x:[null],y:[null],mode:'markers',name:'<'+low+' / >'+high,
    marker:{color:red,size:5},hoverinfo:'skip',meta:{kind:'insight_range',legend_entry:true}});
}
function insightPeriodSummary(s,limit,unit){
  const duration=Math.min(s.duration,limit),scale=unit==='mmol/L'?1:18,rows=[],bins=new Map();
  for(let i=0;i<s.x.length;i++){
    const x=s.x[i],y=s.glucose[i];if(!Number.isFinite(x)||!Number.isFinite(y)||x>=duration)continue;
    rows.push({x,y});const slot=Math.floor(x/5),values=bins.get(slot)||[];values.push(y);bins.set(slot,values);
  }
  const values=[...bins.values()].map(v=>insightMedian(v)),n=values.length;
  let peak=null;for(const row of rows)if(!peak || row.y>peak.y)peak=row;
  let returned=null;
  if(peak && peak.y>10*scale){
    let previous=peak.x;
    for(const row of rows.filter(r=>r.x>=peak.x)){
      if(row.x-previous>10)break;
      if(row.y>=4*scale && row.y<=10*scale){returned=row.x/60;break;}previous=row.x;
    }
  }
  return {observed_bins:n,coverage:duration>0?100*n/Math.ceil(duration/5):null,duration:duration/60,
    mean:insightAggregate(values,'Average'),tir:n?100*values.filter(v=>v>=4*scale&&v<=10*scale).length/n:null,
    below:n?100*values.filter(v=>v<4*scale).length/n:null,peak:peak?.y??null,peak_time:peak?peak.x/60:null,
    rise:peak&&Number.isFinite(s.baseline)?peak.y-s.baseline:null,returned};
}
function insightSummaries(meta,options,unit){
  if(meta.insight==='meal')return selectedInsightSeries(meta,options).map(s=>({label:s.label,baseline:s.baseline,meal:s.meal,...insightPeriodSummary(s,options.duration*60,unit)}));
  const periods=new Map();
  for(const [name,series] of [['overnight',meta.series || []],['next',meta.after_series || []]])for(const s of series){
    const id=s.sleep.wake,row=periods.get(id)||{label:'Sleep ending '+id,sleep:s.sleep};
    row[name]=insightPeriodSummary(s,name==='next'?options.duration*60:Infinity,unit);periods.set(id,row);
  }
  return [...periods.values()];
}
function transformSleepRelationship(view,index){
  const state=panelStateAt(index),options=state.insight,unit=navigation.unit || 'mmol/L';
  const rows=insightSummaries(view.layout.meta,options,unit),xkey=options.relationX || 'asleep_hours',ykey=options.relationY || 'mean';
  const paired=rows.filter(r=>Number.isFinite(r.sleep[xkey]) && Number.isFinite(r.next?.[ykey]));
  const xlabel=xkey==='hrv'?'Median recorded overnight HRV':'Recorded asleep',xunit=xkey==='hrv'?'ms':'h';
  const ylabel=ykey==='tir'?'Next-day time in range':ykey==='below'?'Next-day time below range':'Next-day mean glucose',yunit=ykey==='mean'?unit:'%';
  view.data=[{type:'scatter',x:paired.map(r=>r.sleep[xkey]),y:paired.map(r=>r.next[ykey]),mode:'markers',marker:{color:'#9575cd',size:7},name:'Sleep periods',showlegend:false,
    customdata:paired.map(r=>[r.label,r.next.coverage,r.sleep.stage_coverage,r.next.observed_bins]),
    meta:{kind:'insight_relationship',label:ylabel,unit:yunit,x_label:xlabel,x_unit:xunit,dataset:view.layout.meta.dataset}}];
  view.layout.shapes=(view.layout.shapes || []).filter(s=>s.name!=='Insight glucose range');
  view.layout.annotations=[];view.layout.showlegend=ykey==='mean';view.layout.legend={...view.layout.legend,y:-.23,maxheight:.16};
  view.layout.height=Math.max(350,view.layout.height || 0);view.layout.margin={...view.layout.margin,t:44,b:80};
  const period=view.layout.meta.insight_title.split(' · ').slice(1).join(' · ');
  view.layout.title={...view.layout.title,text:'Sleep · '+(xkey==='hrv'?'Overnight HRV':'Recorded asleep')+' → '+ylabel+' · '+period};
  view.layout.xaxis={...view.layout.xaxis,type:'linear',autorange:true,rangemode:'normal',title:{text:(xkey==='hrv'?'Overnight HRV':xlabel)+' ('+xunit+')'}};
  delete view.layout.xaxis.range;delete view.layout.xaxis.tickvals;delete view.layout.xaxis.ticktext;
  view.layout.yaxis={...view.layout.yaxis,autorange:false,range:[0,100],title:{text:yunit}};
  if(ykey==='mean')styleInsightGlucose(view,unit,options.fitY===true);
  view.layout.meta={...view.layout.meta,insight_relationship:true,insight_pairs:paired.length,insight_summary:rows,empty:!paired.length,insight_excluded_baselines:0};
  if(!paired.length)view.layout.annotations.push({xref:'paper',yref:'paper',x:.5,y:.5,text:'No paired sleep and next-day glucose records for these metrics',showarrow:false});
  applyPanelRanges(view,index);
  view.layout.meta.insight_bands=state.bands;view.layout.meta.insight_note=insightMethodNote(view,options);
}
function insightSummaryTable(div,details){
  const meta=div.layout.meta,rows=meta.insight_summary || [];if(!['meal','sleep'].includes(meta.insight))return;
  if(meta.sleep_overview){
    const note=document.createElement('p');note.textContent='Recorded Garmin session boundaries are preferred; otherwise stage intervals separated by at most 30 minutes are grouped. The end of the recorded session defines waking here, not proof of actual wakefulness. Each glucose reading retains its original value. Hover shows the full local timestamp and UTC offset; repeated daylight-saving clock hours are not joined backwards. Use Newer/Older nights to browse seven rows at a time. The report includes every selected night in continuation panels.';details.appendChild(note);return;
  }
  const note=document.createElement('p');note.textContent=meta.insight==='meal'?
    'Carbs > '+(meta.insight_carb_cutoff ?? 0)+' g · '+rows.length+' recorded periods. Each carb timestamp is an event (not necessarily a meal); simultaneous entries are summed. Each response ends at the earliest of the selected window, next carb entry (including excluded entries), or loaded-data end. Peak is observed glucose; return to range is the first observed 4–10 mmol/L reading after an above-range peak, without crossing a >10 min gap. Starting IOB/COB are the last readings ≤10 min before entry; starting COB affects inclusion only when its filter is enabled. Nearby boluses are recorded within −30/+60 min, not attributed to that meal. — means unavailable or no observed return.':
    'Sleep periods use recorded Garmin session boundaries when available; stage-only records are grouped across gaps ≤30 min. Recorded asleep counts Deep/Light/REM only; missing/unknown stages do not count as sleep. HRV is the median of recorded five-minute overnight bins, not Garmin’s nightly average. Next-day means after waking, up to the selected window, next sleep or loaded-data end (maximum 24 h). Wake dates must be selected; glucose is restricted to selected dates. Coverage shows incomplete windows. These are associations, not causal effects or significance tests.';
  if(meta.insight==='meal' && Number.isFinite(meta.insight_cob_cutoff))note.textContent+=' Starting COB filter: ≤'+meta.insight_cob_cutoff+' g. '+meta.insight_missing_cob+' carb entries have missing/stale starting COB and are excluded. This filter changes inclusion only; every later carb entry still ends the preceding window.';
  details.appendChild(note);
  const wrap=document.createElement('div');wrap.style.overflowX='auto';const table=document.createElement('table');table.style.cssText='border-collapse:collapse;white-space:nowrap;font-size:12px';wrap.appendChild(table);details.appendChild(wrap);
  const headers=meta.insight==='meal'?['Recorded carbs','g','Start IOB U','Start COB g','Start BG','Peak BG','Rise','Peak h','Back in range h','Glucose %','User bolus U','SMB U','Unknown U']:
    ['Sleep ending (UTC)','Asleep h','Stages %','HRV ms','Night mean BG','Night TIR %','Night coverage %','Next mean BG','Next TIR %','Next below %','Next coverage %'];
  const add=(values,head=false)=>{const row=document.createElement('tr');for(const value of values){const cell=document.createElement(head?'th':'td');cell.textContent=value;cell.style.cssText='padding:4px 8px;text-align:left;border-bottom:1px solid #80808040';row.appendChild(cell);}table.appendChild(row);};
  add(headers,true);const n=v=>Number.isFinite(v)?number(v,1):'—';
  for(const r of rows)add(meta.insight==='meal'?[r.label,n(r.meal.carbs),n(r.meal.iob),n(r.meal.cob),n(r.baseline),n(r.peak),n(r.rise),n(r.peak_time),n(r.returned),n(r.coverage),n(r.meal.bolus.user),n(r.meal.bolus.smb),n(r.meal.bolus.unknown)]:
    [r.sleep.wake,n(r.sleep.asleep_hours),n(r.sleep.stage_coverage),n(r.sleep.hrv),n(r.overnight?.mean),n(r.overnight?.tir),n(r.overnight?.coverage),n(r.next?.mean),n(r.next?.tir),n(r.next?.below),n(r.next?.coverage)]);
  if(meta.insight_relationship){const count=document.createElement('p');count.textContent=meta.insight_pairs+' paired recorded sleep periods';details.appendChild(count);}
}
function transformInsight(view,index){
  const state=panelStateAt(index),options=state.insight,key=view.layout.meta.insight;
  if(key==='sleep' && options.sleepView==='overview'){transformSleepOverview(view,index);return;}
  if(key==='sleep' && options.sleepView==='relationship'){transformSleepRelationship(view,index);return;}
  const after=key==='sleep' && options.sleepView==='after',series=selectedInsightSeries(view.layout.meta,options,after),cutoff=key==='meal'?insightCarbCutoff(options):0;
  const metric=key==='sensor_variability'?options.metric:key==='sensor'?'glucose':'glucose',delta=!key.startsWith('sensor') && options.normalization==='delta';
  const aggregation=options.aggregation==='Average'?'Average':'Median',unit=navigation.unit || 'mmol/L',suffix=metric==='glucose'?unit:unit+'/min';
  const limit=['activity_after','meal'].includes(key) || after || (key==='site_age' && options.siteWindow==='limited')?options.duration*60:Infinity,bin=key.startsWith('sensor')?60:5;
  const cacheKey=JSON.stringify([state.base,after,metric,delta,limit,aggregation,cutoff,options.filterStartCOB===true,insightCOBCutoff(options)]);
  if(!insightCalculations.has(cacheKey)){
    insightCalculations.set(cacheKey,calculateInsight(series,metric,delta,limit,bin,aggregation));
    if(insightCalculations.size>24)insightCalculations.delete(insightCalculations.keys().next().value);
  }
  const result=JSON.parse(JSON.stringify(insightCalculations.get(cacheKey)));
  const label=aggregation+' '+(delta?'Δ glucose':metric==='rate'?'glucose variability':metric==='jump'?'glucose jumpiness':'glucose');
  const reference={type:'scatter',x:result.xs,y:result.aggregate,mode:'lines',name:aggregation,line:{color:'#45a4c8',width:2.5},connectgaps:false,customdata:result.counts,
    meta:{kind:'insight_median',label,unit:suffix,aggregation}};
  view.data=(state.mode==='Median + band'?result.band:result.traces).concat([reference]);
  if(metric==='glucose'){
    reference.line.color=view.layout.meta.glucose_color || '#32cd32';
    for(const band of result.band)band.fillcolor='rgba(50,205,50,.18)';
  }
  view.layout.showlegend=true;view.layout.legend={...view.layout.legend,y:-.23,maxheight:.16};
  view.layout.height=Math.max(350,view.layout.height || 0);view.layout.margin={...view.layout.margin,t:44,b:80};
  // The graph title identifies the signal; concise units avoid long rotated
  // titles colliding with neighboring graphs in compact reports.
  view.layout.yaxis={...view.layout.yaxis,autorange:true,rangemode:'normal',title:{text:delta?'Δ '+unit:suffix}};
  delete view.layout.yaxis.range;
  view.layout.shapes=(view.layout.shapes || []).filter(s=>s.name!=='Insight glucose range');
  if(metric==='glucose' && !delta)styleInsightGlucose(view,unit,options.fitY===true);
  for(const t of view.data){t.meta={...t.meta,dataset:view.layout.meta.dataset,unit:suffix};}
  const maximum=Math.max(result.maximum,...result.xs.filter((_,i)=>Number.isFinite(result.aggregate[i]))),margin=Math.max(bin/600,maximum*.02);
  view.layout.xaxis={...view.layout.xaxis,type:'linear',autorange:false,range:[0,maximum>0?maximum+margin:1]};delete view.layout.xaxis.tickvals;delete view.layout.xaxis.ticktext;
  if(key==='sleep'){view.layout.xaxis.title={text:'Time since '+(after?'waking':'sleep start')+' (hours)'};view.layout.title={...view.layout.title,text:view.layout.meta.insight_title};}
  if(key==='site_age')view.layout.title={...view.layout.title,text:options.siteWindow==='limited'?view.layout.meta.insight_title.replace(' · ',' · First '+options.duration+' h · '):view.layout.meta.insight_title};
  if(key==='meal'){
    view.layout.meta.insight_carb_cutoff=cutoff;
    view.layout.meta.insight_cob_cutoff=options.filterStartCOB?insightCOBCutoff(options):null;
    view.layout.meta.insight_missing_cob=(view.layout.meta.series || []).filter(s=>s.meal?.carbs>cutoff&&!Number.isFinite(s.meal?.cob)).length;
    view.layout.title={...view.layout.title,text:cutoff>0?view.layout.meta.insight_title.replace(' · ',' · Carbs > '+cutoff+' g · '):view.layout.meta.insight_title};
  }
  if(key==='meal' && options.filterStartCOB)view.layout.title.text+=' · Start COB ≤ '+insightCOBCutoff(options)+' g';
  view.layout.annotations=[];view.layout.meta.empty=!view.data.some(t=>t.meta?.kind!=='insight_band' && t.y?.some(Number.isFinite));
  if(view.layout.meta.empty)view.layout.annotations.push({xref:'paper',yref:'paper',x:.5,y:.5,text:(key==='meal'?'No usable carb entries above '+cutoff+' g':'No usable recorded periods')+(delta?' with a bracketed t=0 baseline':''),showarrow:false});
  view.layout.meta.insight_excluded_baselines=result.noBaseline;view.layout.meta.insight_aggregation=aggregation;
  view.layout.meta.insight_relationship=false;
  const contributors=result.counts.filter(n=>n>0);
  view.layout.meta.insight_periods=result.traces.length;
  view.layout.meta.insight_count_range=contributors.length?[Math.min(...contributors),Math.max(...contributors)]:[];
  view.layout.meta.insight_summary=['meal','sleep'].includes(key)?insightSummaries(view.layout.meta,options,unit):[];
  addInsightContext(view,state,series,limit,bin,delta);
  applyPanelRanges(view,index);
  view.layout.meta.insight_bands=state.bands;view.layout.meta.insight_note=insightMethodNote(view,options);
}

function addInsightContext(view,state,series,limit,bin,delta){
  const enabled=[['iob','showIOB','IOB','U','#2196f3'],['cob','showCOB','COB','g','#ff9800']].filter(f=>state.insight[f[1]]===true);
  const primary=delta?series.filter(s=>Number.isFinite(s.baseline)):series;
  const aggregation=state.insight.aggregation==='Average'?'Average':'Median';
  // Each signal retains its own timestamps and one contribution per event/bin.
  // Never delta-normalize insulin/carbs or use their units for glucose scaling.
  view.layout.xaxis.domain=enabled.length?[0,enabled.length===2?.80:.90]:[0,1];
  for(const [i,[field,,label,unit,color]] of enabled.entries()){
    const source=primary.map(s=>({...s,x:s.context?.[field]?.x || [],value:s.context?.[field]?.value || []}));
    const result=calculateInsight(source,'value',false,limit,bin,aggregation),axis='y'+(i+2);
    for(const band of result.band)view.data.push({...band,yaxis:axis,name:label+' '+band.meta.percentile,legendgroup:field+'-'+band.meta.percentile,
      fillcolor:field==='iob'?'rgba(33,150,243,.10)':'rgba(255,152,0,.10)',
      meta:{...band.meta,kind:'insight_context_band',dataset:field,label:label+' '+band.meta.percentile,unit}});
    view.data.push({type:'scatter',x:result.xs,y:result.aggregate,yaxis:axis,mode:'lines',connectgaps:false,
      name:aggregation+' '+label,line:{color,width:1.8},opacity:.65,customdata:result.counts,
      meta:{kind:'insight_context',label:aggregation+' '+label,unit,dataset:field,aggregation}});
    view.layout['yaxis'+(i+2)]={overlaying:'y',anchor:'free',side:'right',position:enabled.length===2?.82+i*.12:1,
      autorange:true,rangemode:'normal',showgrid:false,zeroline:false,tickfont:{color},title:{text:label+' ('+unit+')',font:{color}},color};
  }
  view.layout.meta.insight_context=enabled.map(f=>f[0]);
}

// One settings-aware explanation is shared by the app and static report renderer.
// Keep technical detail in the expandable methods table, not the compact footer.
function insightMethodNote(view,options){
  const meta=view.layout.meta,key=meta.insight,parts=[];
  if(meta.insight_relationship){
    const x=options.relationX==='hrv'?'Recorded HRV (ms; 5-min median)':'Recorded asleep (h; Deep/Light/REM)',
      y=options.relationY==='tir'?'next-day time in range':options.relationY==='below'?'next-day time below range':'next-day mean glucose';
    parts.push(x+' vs '+y+'; '+meta.insight_pairs+' paired sleeps.');
    parts.push('After waking: earliest of '+options.duration+' h, next sleep or data end.');
    parts.push('Observed 5-min glucose bins; missing stages/readings excluded. Association, not causation.');
  }else{
    if(key==='meal'){
      parts.push('Carbs >'+insightCarbCutoff(options)+' g; '+(options.filterStartCOB?'start COB ≤'+insightCOBCutoff(options)+' g (last ≤10 min; missing excluded)':'start COB unfiltered')+'.');
      parts.push('Ends at earliest of next carbs (even excluded), '+options.duration+' h or data end.');
    }else if(key==='activity_during')parts.push('Activity start → recorded end/data end; meals remain included.');
    else if(key==='activity_after')parts.push('From activity end, up to '+options.duration+' h/data end; later meals/activities remain included.');
    else if(key==='sleep')parts.push(options.sleepView==='after'?'From waking: earliest of '+options.duration+' h, next sleep or data end; meals/activities remain included.':'Recorded sleep start → wake/data end; recorded sessions preferred, otherwise stages grouped across ≤30-min gaps.');
    else if(key==='site_age')parts.push('From site change: until next replacement/data end'+(options.siteWindow==='limited'?', limited to '+options.duration+' h':'')+'; other profile/treatment changes remain included.');
    else parts.push('From sensor change until next replacement/data end; restarts may count as changes.');
    const signal=key==='sensor_variability'?(options.metric==='jump'?'|change in glucose slope|':'|glucose slope|'):options.normalization==='delta' && !key.startsWith('sensor')?'Δ glucose from t=0':'absolute glucose';
    parts.push((meta.insight_aggregation || 'Median')+' '+signal+'; '+(key.startsWith('sensor')?'60':'5')+'-min bins.');
    const counts=meta.insight_count_range || [];
    parts.push((meta.insight_periods || 0)+' periods'+(counts.length?'; '+(counts[0]===counts[1]?counts[0]:counts[0]+'–'+counts[1])+' contributors/bin':'')+'.');
    if(view.data.some(t=>t.meta?.kind==='insight_band'))parts.push((meta.insight_bands==='Both'?'25–75% / 10–90%':meta.insight_bands || '25–75%')+': between-period variation, not a confidence interval.');
    if(signal.startsWith('Δ'))parts.push('Baseline exact/bracketed ≤10 min; '+(meta.insight_excluded_baselines || 0)+' missing excluded.');
    if(meta.insight_context?.length)parts.push(meta.insight_context.map(k=>k.toUpperCase()).join('/')+' '+(meta.insight_aggregation==='Average'?'averages':'medians')+': upload coverage may differ.');
    if(key==='sensor_variability')parts.push('Signal variability, not sensor accuracy.');
    parts.push('Selected dates only; >10-min gaps unfilled.');
  }
  const crop=navigation?.report_render?.range;
  if(crop && (crop[0]!==0 || crop[1]!==1440))parts.push('Clock-hour crop does not apply to elapsed-time insights.');
  return parts.join(' ');
}
