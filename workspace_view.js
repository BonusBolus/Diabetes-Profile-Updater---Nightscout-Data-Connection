// Workspace orchestration reuses the existing immutable source/mode banks.
const workspaceUI=[];
let graphPicker=null;
function panelDateContext(index,fn){
  if(!workspaceGraphs)return fn();
  const previous=[selectedDays,dateCycled],s=panelStateAt(index);
  try{dateCycled=s.graphType==='daily';if(dateCycled)selectedDays=[dailyDate];return fn();}
  finally{[selectedDays,dateCycled]=previous;}
}
function panelTimeRange(index,fallback){
  const state=panelStateAt(index);
  if(!state.fitActivities || effectivePanelMode(index)!=='One day' || specs[index].layout.meta?.non_time)return fallback.slice();
  const day=workspaceGraphs?dailyDate:selectedDays[0];
  const bands=(navigation?.activity_bands || []).filter(b=>b.name.split(' | ')[1]===day && Number.isFinite(b.x0) && Number.isFinite(b.x1) && b.x1>b.x0);
  return bands.length?[Math.max(0,Math.min(...bands.map(b=>b.x0))),Math.min(1440,Math.max(...bands.map(b=>b.x1)))]:fallback.slice();
}
function timeAxisTicks(range,width=700){
  const span=range[1]-range[0],capacity=Math.max(2,Math.min(8,Math.floor(width/85)));
  const step=[1/60,.25,.5,1,2,5,10,15,20,30,60,120,180,240,360,720].find(n=>span/n<=capacity) || 720;
  const tickvals=[];for(let t=Math.ceil((range[0]-1e-8)/step)*step;t<=range[1]+1e-8;t+=step)tickvals.push(Math.round(t*1e6)/1e6);
  const clock=value=>{const seconds=Math.round(value*60),h=Math.floor(seconds/3600),m=Math.floor(seconds%3600/60),s=seconds%60;return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+(step<1?':'+String(s).padStart(2,'0'):'');};
  return {tickmode:'array',tickvals,ticktext:tickvals.map(clock),tickangle:0};
}
function applyClockTicks(layout,range,width=null){
  if(layout.meta?.non_time || layout.meta?.kind==='insight')return;
  const pixels=width || (layout.width || 900)-(layout.margin?.l || 60)-(layout.margin?.r || 60);
  for(const key of Object.keys(layout).filter(k=>/^xaxis\d*$/.test(k)))if(layout[key].type!=='category')Object.assign(layout[key],timeAxisTicks(range,pixels));
}
function overlayDateColor(day){
  const days=[...new Set(navigation?.day_color_dates || navigation?.days || selectedDays)].sort(),index=Math.max(0,days.indexOf(day));
  const palette=['#2878b5','#e58223','#46a65b','#b757a5','#d74c4c','#31a6a0','#94714b','#796ac2','#b3a221','#269dbf','#d36a91','#677b3c'];
  return palette[index] || 'hsl('+((index*137.508)%360).toFixed(3)+',65%,48%)';
}
function applyOverlayDayColors(view,index){
  if(effectivePanelMode(index)!=='Multiple days' || (view.layout.meta?.non_time && (view.layout.meta.kind!=='insight' || view.layout.meta.sleep_overview || view.layout.meta.insight_relationship)))return;
  view.data=view.data.filter(t=>t.meta?.kind!=='day_legend');
  const days=new Set(),fields=[...new Set(view.data.filter(t=>t.meta?.date && !['automation_note','profile_event'].includes(t.meta.kind)).map(t=>t.meta?.dataset || t.meta?.label || t.name))].sort();
  for(const trace of view.data){
    const day=trace.meta?.date;if(!day || ['automation_note','profile_event'].includes(trace.meta.kind))continue;
    const color=overlayDateColor(day),field=trace.meta?.dataset || trace.meta?.label || trace.name;
    if(!trace.type || trace.type==='scatter' || trace.type==='scattergl')trace.line={...trace.line,color,dash:['solid','dash','dot','dashdot','longdash'][Math.max(0,fields.indexOf(field))%5]};
    if(trace.marker)trace.marker={...trace.marker,color};if(trace.textfont)trace.textfont={...trace.textfont,color};
    if(trace.fill && trace.fill!=='none'){const alpha=trace.meta?.profile_source==='nightscout'?.055:.13;trace.fillcolor=color.startsWith('#')?rgbaColor(color,alpha):color.replace('hsl(','hsla(').replace(')',','+alpha+')');}
    trace.showlegend=false;trace.meta={...trace.meta,legend_entry:false,day_color:color};
    if(trace.hoverinfo!=='skip' && (trace.y || []).some(Number.isFinite))days.add(day);
    if(trace.meta.day_name!==day){trace.name=day+' · '+(trace.meta.label || trace.name);trace.meta.day_name=day;}
  }
  for(const day of [...days].sort())view.data.push({type:'scatter',x:[null],y:[null],mode:'lines',line:{color:overlayDateColor(day),width:3},name:day,legendgroup:'day:'+day,showlegend:true,hoverinfo:'skip',meta:{kind:'day_legend',legend_proxy:true,date:day}});
  if(days.size)view.layout.showlegend=true;
}
function panelSourceView(source,index,range){
  range=panelTimeRange(index,range);
  return (workspaceGraphs?panelStateAt(index).graphType==='daily':dateCycled)?dailyView(source,index,workspaceGraphs?dailyDate:selectedDays[0],range):source;
}
function graphBaseName(spec){
  const m=spec.layout.meta || {};
  return m.dataset==='cob'?'COB + Carbs':m.dataset==='iob'?'IOB + Boluses':m.kind==='compact'?'Glucose Compact':m.kind==='custom'?'Custom graph':spec.layout.title.text.split(' · ')[0];
}
function nameWorkspaceGraph(view,index){
  if(!workspaceGraphs)return;
  const s=panelStateAt(index),type=s.graphType;
  const label=type==='daily'?'Daily':effectivePanelMode(index)==='Multiple days'?'Multiple-day overlay':type==='insight'?'Insight':view.layout.meta?.kind==='hourly'?'Hourly distribution':view.layout.meta?.dataset==='g_sleep'?(s.garmin.sleepDistribution?'Hourly distribution':'Stage composition'):(s.statistic || 'Median');
  const period=type==='daily'?dailyDate:(selectedDays.length===1?selectedDays[0]:selectedDays[0]+' – '+selectedDays.at(-1));
  view.layout.title.text=(view.layout.meta?.dataset==='g_steps'?(s.garmin.stepsHistogram?'Steps histogram':'Cumulative steps'):graphBaseName(specs[index]))+' — '+label+' · '+period;
  if(view.layout.meta?.sleep_overview)view.layout.title.text='Sleep + glucose — Nights · '+period;
}
function workspacePanelControls(areas,panel,spec){
  const id=ensurePanelState(spec).id;
  const details=document.createElement('details');details.className='graph-events';const summary=document.createElement('summary');summary.textContent='Events';details.appendChild(summary);
  const body=document.createElement('div');body.className='event-options';details.appendChild(body);areas.content.appendChild(details);
  const selects=[];
  for(const [key,text] of [['activity','Activity'],['site','Site changes'],['sensor','Sensor changes'],['profiles','Profile switches'],['percentage','Profile %'],['automation','Automation notes']]){
    const label=document.createElement('label');label.textContent=text;const el=document.createElement('select');el.setAttribute('aria-label',text+' for this graph');
    for(const [value,name] of [['inherit','Use global'],['show','Show'],['hide','Hide']]){const o=document.createElement('option');o.value=value;o.textContent=name;el.appendChild(o);}
    el.addEventListener('change',()=>changePanelState(panel.graphIndex,s=>{s.events[key]=el.value;}));label.appendChild(el);body.appendChild(label);selects.push({key,el});
  }
  const wrap=document.createElement('label');wrap.textContent='Bands ';const bands=document.createElement('select');bands.setAttribute('aria-label','Summary percentile bands');
  for(const value of ['25–75%','10–90%','Both','None']){const o=document.createElement('option');o.value=value;o.textContent=value;bands.appendChild(o);}
  bands.addEventListener('change',()=>changePanelState(panel.graphIndex,s=>{s.bands=bands.value;}));wrap.appendChild(bands);areas.settings.appendChild(wrap);
  const statWrap=document.createElement('label');statWrap.textContent='Curve ';const statistic=document.createElement('select');statistic.setAttribute('aria-label','Summary curve statistic');
  for(const name of ['Median','Average']){const option=document.createElement('option');option.value=name;option.textContent=name;statistic.appendChild(option);}
  statistic.addEventListener('change',()=>changePanelState(panel.graphIndex,s=>{s.statistic=statistic.value;}));statWrap.appendChild(statistic);areas.settings.appendChild(statWrap);
  const modeWrap=document.createElement('label');modeWrap.textContent='Display ';const mode=document.createElement('select');mode.setAttribute('aria-label','Summary display');modeWrap.appendChild(mode);areas.settings.prepend(modeWrap);
  for(const value of [...(spec.layout.meta?.kind==='custom'?['One day']:[]),'Median','Average','Multiple-day overlay']){const o=document.createElement('option');o.value=value;o.textContent=value;mode.appendChild(o);}
  mode.addEventListener('change',()=>changePanelState(panel.graphIndex,s=>{if(spec.layout.meta?.kind==='custom')s.graphType=mode.value==='One day'?'daily':'summary';s.mode=mode.value==='Multiple-day overlay'?'Multiple days':'Median + band';if(!['Multiple-day overlay','One day'].includes(mode.value))s.statistic=mode.value;}));
  const viewWrap=document.createElement('label');viewWrap.textContent='Content ';const content=document.createElement('select');content.setAttribute('aria-label','Summary content');viewWrap.appendChild(content);areas.settings.appendChild(viewWrap);
  for(const value of ['Timeline + hourly bars','Timeline','Hourly bars']){const o=document.createElement('option');o.value=value;o.textContent=value;content.appendChild(o);}
  content.addEventListener('change',()=>changePanelState(panel.graphIndex,s=>{s.summaryView=content.value;s.axisRanges={};}));
  const fit=document.createElement('button');fit.type='button';fit.setAttribute('aria-label','Fit this graph to activities');
  fit.title='Daily view only. Use the first recorded activity start through the last activity end on this day. Other graphs keep their time window; no activity uses the normal window. Saved with graph and PDF configurations.';
  fit.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{s.fitActivities=!s.fitActivities;}));areas.settings.appendChild(fit);
  let amounts=null;
  if(spec.layout.meta?.kind==='compact'){
    amounts=document.createElement('button');amounts.type='button';amounts.setAttribute('aria-label','Carb and bolus amount labels');
    amounts.title='Permanent amount labels in this compact graph. Markers and hover details always remain available.';
    amounts.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{s.showAmounts=!s.showAmounts;}));areas.settings.appendChild(amounts);
  }
  workspaceUI.push({id,panel,summary,selects,bands,wrap,statistic,statWrap,mode,modeWrap,content,viewWrap,amounts,fit});
}
function workspaceControls(){
  for(const ui of workspaceUI){if(!ui.panel.isConnected)continue;const state=panelStateAt(ui.panel.graphIndex);if(!state)continue;let count=0;
    ui.fit.hidden=state.graphType!=='daily' || specs[ui.panel.graphIndex].layout.meta?.non_time;ui.fit.disabled=!ready || syncing;ui.fit.textContent='Fit to activities: '+(state.fitActivities?'on':'off');ui.fit.setAttribute('aria-pressed',String(state.fitActivities));
    if(ui.amounts){ui.amounts.disabled=!ready || syncing;ui.amounts.textContent='Amount labels: '+(state.showAmounts?'on':'off');ui.amounts.setAttribute('aria-pressed',String(state.showAmounts));}
    for(const {key,el} of ui.selects){el.value=state.events[key] || 'inherit';el.disabled=!ready || syncing || specs[ui.panel.graphIndex].layout.meta?.non_time===true;if(el.value==='show' || (el.value==='inherit' && eventAllowed({...specs[ui.panel.graphIndex],layout:{...specs[ui.panel.graphIndex].layout,meta:{...specs[ui.panel.graphIndex].layout.meta,panel_id:state.id}}},key)))count++;}
    const spec=specs[ui.panel.graphIndex],isSummary=state.graphType==='summary' || state.graphType==='overlay';
    ui.modeWrap.hidden=(!isSummary && spec.layout.meta?.kind!=='custom') || spec.layout.meta?.kind==='hourly';ui.modeWrap.hidden ||= Boolean(summaryEventKey(spec) && state.summaryView==='Hourly bars');ui.mode.disabled=!ready || syncing;
    const continuous=spec.layout.meta?.kind==='custom' || ['glucose','iob','cob','basal','basal_percent','variable_sens'].includes(spec.layout.meta?.dataset);
    for(const option of ui.mode.options)option.hidden=(option.value==='Average' && !continuous) || (!['Multiple-day overlay','One day'].includes(option.value) && !panelHasMedian(spec));
    ui.mode.value=spec.layout.meta?.kind==='custom' && state.graphType==='daily'?'One day':effectivePanelMode(ui.panel.graphIndex)==='Multiple days'?'Multiple-day overlay':state.statistic || 'Median';
    ui.viewWrap.hidden=!isSummary || !summaryEventKey(spec);ui.content.value=state.summaryView || 'Timeline + hourly bars';ui.content.disabled=!ready || syncing;
    ui.summary.textContent='Events · '+count+' active';ui.bands.value=state.bands;ui.statistic.value=state.statistic || 'Median';ui.statistic.disabled=!ready || syncing;ui.bands.disabled=!ready || syncing;
    ui.statWrap.hidden=workspaceGraphs || effectivePanelMode(ui.panel.graphIndex)!=='Median + band' || !['glucose','iob','cob','basal','basal_percent','variable_sens'].includes(specs[ui.panel.graphIndex].layout.meta?.dataset) || specs[ui.panel.graphIndex].layout.meta?.kind==='compact';
    ui.wrap.hidden=(workspaceGraphs?state.graphType==='daily' || effectivePanelMode(ui.panel.graphIndex)==='Multiple days':effectivePanelMode(ui.panel.graphIndex)!=='Median + band');
    ui.wrap.hidden ||= spec.layout.meta?.insight==='sleep' && ['overview','relationship'].includes(state.insight.sleepView);
  }
}
function compactDistribution(view,index){
  const m=view.layout.meta || {},state=panelStateAt(index);
  const bars=view.data.filter(t=>t.type==='bar' && t.visible!==false);
  if((m.kind==='hourly' && !state.showDailyGrid) || (bars.length && m.dataset==='g_sleep' && effectivePanelMode(index)==='Median + band' && !state.garmin.sleepFields?.length) || (m.dataset==='g_steps' && state.garmin.stepsHistogram)){
    view.layout.height=m.dataset==='g_sleep'?210:190;view.layout.meta.compact_distribution=true;
    view.layout.margin={...view.layout.margin,t:32,b:45};
  }
}
function applySummaryBands(view,index){
  const choice=panelStateAt(index).bands || '25–75%';
  // All quantile polygons are constructed from per-day/per-period observations.
  const extra=[];
  const heat=view.data.find(t=>t.meta?.kind==='hourly_heatmap');
  if(heat && !view.layout.meta?.single_day){
    const bars=view.data.find(t=>t.meta?.kind==='hourly_histogram');
    if(bars){const per=bars.x.map((_,i)=>heat.z.map((r,d)=>heat.customdata[d]?.[i]?.[5]?r[i]:null).filter(Number.isFinite));
      bars.meta.distribution={p10:per.map(v=>v.length>=2?insightMedian(v,.1):null),p90:per.map(v=>v.length>=2?insightMedian(v,.9):null),p25:per.map(v=>v.length>=2?insightMedian(v,.25):null),p75:per.map(v=>v.length>=2?insightMedian(v,.75):null)};
    }
  }
  for(const t of view.data){const d=t.meta?.distribution;if(!d || t.visible===false)continue;
    for(const [low,high,label,alpha] of [[d.p10,d.p90,'10–90%',.07],[d.p25,d.p75,'25–75%',.18]]){
      if(!low || !high)continue;let start=null;
      for(let i=0;i<=t.x.length;i++){
        if(i<t.x.length && Number.isFinite(low[i]) && Number.isFinite(high[i])){if(start===null)start=i;continue;}
        if(start!==null){let x=[],lo=[],hi=[];for(let k=start;k<i;k++){x.push(t.x[k]-27,t.x[k]+27);lo.push(low[k],low[k]);hi.push(high[k],high[k]);}
          extra.push({type:'scatter',x:x.concat(x.slice().reverse()),y:lo.concat(hi.slice().reverse()),yaxis:t.yaxis,xaxis:t.xaxis,mode:'lines',fill:'toself',fillcolor:rgbaColor(t.marker?.color || '#778895',alpha),line:{width:0},name:label,legendgroup:label,hoverinfo:'skip',meta:{kind:'percentile_band',percentile:label,legend_entry:true}});start=null;}
      }
    }
    view.layout.showlegend=true;
  }
  for(const t of view.data){const q=t.meta?.summary;
    if(q && t.meta?.kind==='median'){
      const statistic=panelStateAt(index).statistic || 'Median';
      if(q.average && q.median){t.y=q[statistic==='Average'?'average':'median'].slice();t.name=t.name.replace(/^Median|^Average/,statistic);t.meta.label=t.meta.label.replace(/^Median|^Average/,statistic);}
      const color=t.line?.color || '#68ae66';
      for(const [low,high,label,alpha] of [[q.p10,q.p90,'10–90%',.07]]){
        if(!low || !high)continue;let start=null;
        for(let i=0;i<=t.x.length;i++){
          if(i<t.x.length && Number.isFinite(low[i]) && Number.isFinite(high[i]) && (q.count?.[i] ?? 2)>=2){if(start===null)start=i;continue;}
          if(start!==null){let x=t.x.slice(start,i),lo=low.slice(start,i),hi=high.slice(start,i);if(x.length===1){x=[x[0],x[0]+5];lo=[lo[0],lo[0]];hi=[hi[0],hi[0]];}
            extra.push({type:'scatter',x:x.concat(x.slice().reverse()),y:lo.concat(hi.slice().reverse()),xaxis:t.xaxis,yaxis:t.yaxis,fill:'toself',fillcolor:rgbaColor(color,alpha),line:{width:0},mode:'lines',hoverinfo:'skip',name:(t.meta.dataset || '')+' '+label,legendgroup:(t.meta.dataset || '')+'-outer',meta:{kind:'percentile_band',dataset:t.meta.dataset,percentile:label,legend_entry:true},visible:t.visible});start=null;}
        }
      }
    }
  }
  // Split after choosing the statistic: Average can cross zero where Median does not.
  const curves=[];
  for(const t of view.data){
    if(t.meta?.kind==='median' && t.meta?.dataset==='iob' && (t.y || []).some(v=>Number.isFinite(v)&&v<0)){
      const positive={...t,y:t.y.map(v=>Number.isFinite(v)&&v>=0?v:null)};
      const negative={...t,y:t.y.map(v=>Number.isFinite(v)&&v<=0?v:null),name:(panelStateAt(index).statistic || 'Median')+' negative IOB',legendgroup:'Negative IOB',line:{...t.line,color:'#9874c8'},meta:{...t.meta,label:'Negative IOB',summary:undefined}};
      curves.push(positive,negative);
    }else curves.push(t);
  }
  view.data=extra.concat(curves);
  for(const t of view.data){const band=t.meta?.percentile || (/10–90%/.test(t.name)?'10–90%':(/25–75%/.test(t.name) || ['spread','garmin_band','insight_band','insight_context_band'].includes(t.meta?.kind))?'25–75%':null);
    if(band && t.visible!==false){t.visible=choice==='Both' || choice===band;if(band==='10–90%' && t.fillcolor)t.fillcolor=t.fillcolor.replace(/,[\d.]+\)$/ ,',0.07)');}
  }
}
function rgbaColor(color,alpha){if(/^#[\da-f]{6}$/i.test(color))return 'rgba('+[1,3,5].map(i=>parseInt(color.slice(i,i+2),16)).join(',')+','+alpha+')';return color.replace(/,[\d.]+\)$/,','+alpha+')');}
function summaryEventKey(spec){return spec.layout.meta?.kind!=='hourly'?({cob:'carbs',iob:'bolus'}[spec.layout.meta?.dataset] || null):null;}
function graphCatalog(){
  const items=[];
  specs.forEach((spec,index)=>{
    const state=panelStateAt(index),meta=spec.layout.meta || {};if(state.duplicate)return;
    if(index===0){if(!dataOnly)items.push({index,type:'daily',group:'Daily',label:'Profile settings'});return;}
    const name=graphBaseName(spec),isInsight=meta.kind==='insight',hourly=meta.kind==='hourly',compact=meta.kind==='compact';
    if(isInsight)items.push({index,type:'insight',group:'Insights',label:name});
    else if(hourly){
      if(!['carbs','bolus'].includes(meta.dataset) || !specs.some(s=>summaryEventKey(s)===meta.dataset))items.push({index,type:'summary',group:'Summary',label:name});
    }else if(meta.kind==='custom'){
      if(!items.some(item=>item.group==='Custom'))items.push({index,type:navigation?.export_workspace && reportEditorBlock==='summary'?'summary':'daily',group:'Custom',label:navigation?.export_workspace && reportEditorBlock==='summary'?'Custom summary graph':'Custom graph'});
    }
    else{
      items.push({index,type:'daily',group:'Daily',label:name});
      if(!compact)items.push({index,type:'summary',group:'Summary',label:name});
    }
  });return items;
}
function graphColor(item){
  const spec=specs[item.index],m=spec?.layout.meta || {},key=m.dataset;
  return ({glucose:'#32ad42',cob:'#dd8a18',carbs:'#dd8a18',iob:'#2994cb',bolus:'#2994cb',basal:'#00aabd',target:'#50aa68',variable_sens:'#bb9c18',g_sleep:'#9575cd',g_steps:'#5aa970',g_hr:'#e56b70',g_stress:'#e49339'}[key]) ||
    (m.kind==='insight'?'#4a9c70':m.kind==='custom'?'#7286b3':spec?.data?.find(t=>typeof t.line?.color==='string')?.line.color || '#7286a0');
}
function summarySource(index){
  const state=panelStateAt(index),key=summaryEventKey(specs[index]);
  if(!key || state.graphType==='daily' || state.summaryView!=='Hourly bars')return null;
  return (key==='bolus' && state.excludeSMB?navigation.bolus_without_smb?.selected:null) || navigation.mode_banks?.['Median + band']?.['hourly:'+key] || navigation.figures.find(f=>f.layout.meta?.kind==='hourly' && f.layout.meta.dataset===key);
}
function composeSummaryGroup(view,index){
  const state=panelStateAt(index),key=summaryEventKey(specs[index]);
  if(!workspaceGraphs || state.graphType==='daily' || !key || state.summaryView!=='Timeline + hourly bars' || view.layout.meta?.kind==='hourly')return view;
  const source=(key==='bolus'&&state.excludeSMB?navigation.bolus_without_smb?.selected:null) || navigation.mode_banks?.['Median + band']?.['hourly:'+key] || navigation.figures.find(f=>f.layout.meta?.kind==='hourly'&&f.layout.meta.dataset===key);
  if(!source)return view;
  const hourly=decorateCore(source,index),grid=state.showDailyGrid;
  const timelineLow=grid?.64:.38;
  view.layout.yaxis.domain=[timelineLow,1];view.layout.xaxis.anchor='y';view.layout.xaxis.showticklabels=false;
  view.layout.yaxis2={...hourly.layout.yaxis2,domain:grid?[.38,.52]:[0,.24],anchor:'x2',overlaying:undefined};
  view.layout.xaxis2={...hourly.layout.xaxis2,domain:view.layout.xaxis.domain || [0,1],anchor:'y2',matches:'x',showticklabels:true};
  if(grid){view.layout.yaxis3={...hourly.layout.yaxis,domain:[0,.25],anchor:'x3',visible:true};view.layout.xaxis3={...hourly.layout.xaxis,domain:[0,1],anchor:'y3',matches:'x',visible:true};}
  for(const t of hourly.data){if(t.meta?.kind==='automation_note' || t.meta?.kind==='profile_event')continue;
    if(t.meta?.kind==='hourly_heatmap'){if(!grid)continue;view.data.push({...t,yaxis:'y3',xaxis:'x3'});}
    else view.data.push({...t,yaxis:'y2',xaxis:'x2'});
  }
  view.layout.height=grid?620:430;view.layout.showlegend=true;view.layout.meta.combined_summary=true;
  view.layout.annotations=[...(view.layout.annotations || []),{text:(state.hourly || 'Average')+' hourly '+(key==='carbs'?'carbs':'boluses'),xref:'paper',yref:'paper',x:0,y:grid?.55:.27,showarrow:false,xanchor:'left',font:{size:11}}];
  return view;
}
async function addWorkspaceGraph(item){
  if(!ready || syncing)return;
  return enqueue(async()=>{syncing=true;clearHover();controls();let index;
    try{const base=panelStateAt(item.index);const raw={...JSON.parse(JSON.stringify(base)),id:'graph-'+crypto.randomUUID(),duplicate:true,deleted:false,graphType:navigation.export_workspace && item.group==='Custom' && reportEditorBlock==='summary'?'summary':item.type,mode:item.type==='overlay'?'Multiple days':'Median + band',axisRanges:{},summaryView:summaryEventKey(specs[item.index])?'Timeline + hourly bars':undefined};
      if(!panelHasMedian(specs[item.index]) && item.type==='summary')raw.mode='Multiple days';
      if(item.sleepDistribution!==undefined)raw.garmin.sleepDistribution=item.sleepDistribution;
      if(item.index===0)raw.profileCopy=true;
      index=appendGraphCopy(item.index,raw);const v=decorate(panelSourceView(localSource(index),index,[0,1440]),index);
      await Plotly.newPlot(graphs[index],v.data,sizedLayout(v,index),{responsive:false,displaylogo:false});bindGraph(graphs[index],index);await reflowProfileLabels(graphs[index]);
      if(graphPicker?.open)graphPicker.close();panelCards[index].scrollIntoView({block:'nearest',behavior:'smooth'});
    }catch(e){if(index!==undefined)removeCustomPanelAt(index);card.textContent='Could not add graph: '+e.message;}
    finally{syncing=false;controls();}
  });
}
function openGraphPicker(){
  if(!graphPicker || graphPicker.open)return;
  graphPicker.draw();graphPicker.showModal();workspaceSize();graphPicker.querySelector('input').focus();
}
function setupWorkspace(){
  if(!workspaceGraphs || navigation?.report_render)return;
  graphPicker=document.createElement('dialog');graphPicker.className='graph-picker';graphPicker.setAttribute('aria-label','Add graph');
  const header=document.createElement('div');header.className='picker-heading';const title=document.createElement('strong');title.textContent='Add graph';header.appendChild(title);
  const close=document.createElement('button');close.textContent='×';close.setAttribute('aria-label','Close graph picker');close.addEventListener('click',()=>graphPicker.close());header.appendChild(close);graphPicker.appendChild(header);
  const search=document.createElement('input');search.placeholder='Find a graph';search.setAttribute('aria-label','Find a graph');graphPicker.appendChild(search);
  const list=document.createElement('div');graphPicker.appendChild(list);
  graphPicker.draw=()=>{list.replaceChildren();for(const group of ['Daily','Summary','Insights','Custom']){
    const section=document.createElement('section'),h=document.createElement('h4');h.textContent=group;section.appendChild(h);const tiles=document.createElement('div');tiles.className='tiles';section.appendChild(tiles);
    for(const item of graphCatalog().filter(i=>reportEditingAllows(i) && i.group===group && i.label.toLowerCase().includes(search.value.toLowerCase()))){
      const b=document.createElement('button');b.type='button';b.textContent=item.label;b.dataset.group=group;b.style.setProperty('--graph-color',graphColor(item));b.disabled=item.type!=='daily' && selectedDays.length<2;b.title=b.disabled?'Select at least two loaded dates.':group+' graph';b.addEventListener('click',()=>addWorkspaceGraph(item));tiles.appendChild(b);
    }
    const unavailable=dormantPanelStates.filter(s=>!s.deleted);if(unavailable.length && group==='Insights'){const note=document.createElement('p');note.textContent=unavailable.length+' saved graph(s) need additional loaded data.';section.appendChild(note);}
    if(tiles.children.length)list.appendChild(section);
  }if(!list.children.length){const p=document.createElement('p');p.textContent='No matching graphs. Load the required data or change your search.';list.appendChild(p);}};
  graphPicker.addEventListener('close',workspaceSize);search.addEventListener('input',graphPicker.draw);graphPicker.addEventListener('click',e=>{if(e.target===graphPicker){const r=graphPicker.getBoundingClientRect();if(e.clientX<r.left || e.clientX>r.right || e.clientY<r.top || e.clientY>r.bottom)graphPicker.close();}});
  document.getElementById('viewer').appendChild(graphPicker);
  const button=document.createElement('button');button.type='button';button.textContent='+ Add graph';button.id='add-graph';button.addEventListener('click',openGraphPicker);expand.parentElement.prepend(button);
  const empty=document.createElement('p');empty.id='empty-workspace';empty.textContent='No graphs yet. Add a graph to start.';panels.before(empty);
  if(navigation.export_workspace){document.getElementById('daily-summary').hidden=true;configurationName.hidden=true;saveConfiguration.hidden=true;}
}
let pickerRevision=0,lastFrameHeight=null;
function workspaceSize(){
  if(!workspaceGraphs || navigation?.report_render)return;
  const empty=panelOrder.every(i=>panelStateAt(i).deleted) && (dataOnly || panelStateAt(0).deleted);
  const message=document.getElementById('empty-workspace');if(message)message.hidden=!empty;
  panels.hidden=empty;document.getElementById('viewer').classList.toggle('empty-workspace',empty);
  const add=document.getElementById('add-graph');if(add)add.hidden=window.parent!==window && !document.fullscreenElement;
  const height=graphPicker?.open?Math.max(650,lastFrameHeight || 0):empty?(navigation.export_workspace?440:170):1040;
  if(height!==lastFrameHeight){lastFrameHeight=height;window.parent.postMessage({type:'profile-studio:height',height},'*');}
}
window.addEventListener('message',event=>{
  if(event.source!==window.parent || event.data?.type!=='profile-studio:open-picker')return;
  const revision=event.data.revision;if(revision && revision!==pickerRevision){pickerRevision=revision;openGraphPicker();}
});
function composeCompact(view,index){
  const scale=navigation.unit==='mmol/L'?1:18,day=workspaceGraphs?dailyDate:selectedDays[0];
  const state=panelStateAt(index),data=view.data.filter(t=>!t.meta?.date || t.meta.date===day),out=[];
  view.layout.meta={...view.layout.meta,compact_amount_labels:state.showAmounts!==false};
  const values=key=>data.filter(t=>t.meta?.kind===key).flatMap(t=>t.meta?.baseline_smb?(t.customdata || []).map(r=>r[1]):t.y || []).filter(Number.isFinite);
  const iobMax=Math.max(1,...values('iob'),...data.filter(t=>t.meta?.kind==='bolus' && !t.meta.baseline_smb).flatMap(t=>t.y || []).filter(Number.isFinite))*1.12;
  const carbMax=Math.max(10,...values('carbs'),...values('cob'))*1.12;
  const glucose=data.filter(t=>t.meta?.kind==='glucose'),gx=glucose.flatMap(t=>(t.x || []).map((x,i)=>[x,t.y[i]])).filter(([x,y])=>Number.isFinite(x)&&Number.isFinite(y));
  const glucoseAt=x=>{let best=null,delta=Infinity;for(const p of gx){const d=Math.abs(p[0]-x);if(d<delta){best=p[1];delta=d;}}return delta<=5?best:null;};
  for(const t of data){const kind=t.meta?.kind;if(t.meta?.legend_proxy)continue;
    if(['target','target_fill','target_boundary'].includes(kind) && !state.showTargets)continue;
    if(kind==='glucose')t.zorder=30;
    if(kind?.startsWith('target'))t.zorder=5;
    if(['iob','bolus','cob','carbs'].includes(kind)){
      if(['bolus','carbs'].includes(kind)){t.meta.legend_entry=true;t.showlegend=true;}
      if(t.meta.baseline_smb){
        const doses=t.customdata.map(r=>r[1]),anchors=t.x.map(glucoseAt),offset=.85*scale;
        const connectors={type:'scatter',x:[],y:[],mode:'lines',line:{color:'rgba(80,140,175,.55)',width:1},hoverinfo:'skip',showlegend:false,zorder:34,meta:{kind:'compact_smb_connector'}};
        anchors.forEach((y,i)=>{if(y!==null){connectors.x.push(t.x[i],t.x[i],null);connectors.y.push(y,y+offset,null);}});
        out.push(connectors);t.y=anchors.map(y=>y===null?null:y+offset);
        t.meta={...t.meta,baseline_smb:false,compact_smb:true};t.fill='none';t.yaxis='y';t.cliponaxis=true;t.zorder=35;t.opacity=.85;
        t.marker={...t.marker,symbol:'triangle-down',size:doses.map(v=>Math.max(5,Math.min(12,16*Math.sqrt(v)))),angle:0,standoff:0};
      }else{
        t.yaxis=['iob','bolus'].includes(kind)?'y2':'y3';t.opacity=.8;t.zorder=['iob','cob'].includes(kind)?1:12;
        t.line={...t.line,dash:'solid',width:1.6};
        if(['iob','cob'].includes(kind)){
          t.fill='tozeroy';t.fillcolor=kind==='iob'?(t.meta?.label?.toLowerCase().includes('negative')?'rgba(156,112,197,.19)':'rgba(48,150,220,.16)'):'rgba(255,152,0,.16)';
        }else{
          t.mode='markers+text';t.marker={...t.marker,size:(t.y || []).map(v=>Math.max(5,Math.min(18,(kind==='carbs'?1.65:4.7)*Math.sqrt(Math.max(0,v || 0)))))};
          t.textposition=kind==='carbs'?'bottom center':'top center';t.textfont={...t.textfont,size:10};
        }
      }
    }
    out.push(t);
  }
  const basal=(navigation.compact_basal || []).find(r=>r.date===day);
  if(basal)for(const [key,name,color,dash] of [['scheduled','Scheduled basal','#778895','dot'],['rate','Basal (reconstructed)','#279acc','solid']])out.push({type:'scatter',x:basal.x,y:basal[key],yaxis:'y4',mode:'lines',line:{color,width:1.5,dash,shape:'hv'},fill:key==='rate'?'tozeroy':'none',fillcolor:'rgba(39,154,204,.13)',name,meta:{kind:'compact_basal',unit:'U/h',label:name},hovertemplate:'%{y:.3g} U/h<extra>'+name+'</extra>',connectgaps:false});
  view.data=out;
  const peak=Math.max(20*scale,...values('glucose').map(v=>v+1.2*scale)),iobMin=Math.min(0,...values('iob'))*1.12;
  Object.assign(view.layout.yaxis,{domain:[.32,1],range:[0,peak>20*scale?Math.ceil(peak/scale)*scale:20*scale],autorange:false,layer:'below traces'});
  // Shared plot domain: real U/g axes are overlaid instead of opaque inset subplots.
  // Axis limits place insulin in the bottom 28% and carbs in the upper 30%.
  view.layout.yaxis2={overlaying:'y',range:[iobMin,iobMin+(iobMax-iobMin)/.28],autorange:false,visible:false,showgrid:false,zeroline:false,anchor:'x'};
  view.layout.yaxis3={overlaying:'y',range:[carbMax/.30,0],autorange:false,visible:false,showgrid:false,zeroline:false,side:'right',anchor:'x'};
  view.layout.yaxis4={domain:[.12,.27],title:{text:'U/h',font:{size:11,color:'#279acc'}},rangemode:'tozero',showgrid:true,gridcolor:'rgba(128,128,128,.12)',tickfont:{size:10},nticks:3,anchor:'x'};
  view.layout.xaxis.anchor='y4';view.layout.height=515;view.layout.margin={l:58,r:24,t:38,b:66};
  view.layout.legend={orientation:'h',y:-.20,font:{size:10},itemsizing:'constant'};
  view.layout.shapes=(view.layout.shapes || []).filter(s=>!s.name?.startsWith('Activity | '));
  view.layout.annotations=[];
  const annotate=(name,text,x,color,size=10)=>view.layout.annotations.push({name,text,xref:'paper',yref:'paper',x,y:0,xanchor:'center',yanchor:'middle',showarrow:false,font:{size,color}});
  annotate('compact-cob','COB / carbs · g ↓',.01,'#bf7100');
  annotate('compact-iob','IOB / bolus · U',.01,'#279acc');
  const stats=(navigation.summaries || []).find(r=>r.date===day);
  if(stats){
    let left=0;const pieces=[];
    for(const [key,value,color] of [['Below',stats.below,'#ef5350'],['TIR',stats.tir,'#60b970'],['Above',stats.above,'#ff9800']])if(Number.isFinite(value)){
      view.layout.shapes.push({name:'compact-tir',type:'rect',xref:'paper',yref:'paper',x0:left,x1:left+value/100,y0:0,y1:0,fillcolor:color,line:{width:0}});left+=value/100;pieces.push(key+' '+number(value)+'%');
    }
    // One centered label stays readable even when an out-of-range segment is tiny.
    annotate('compact-tir-label',pieces.length?'<b>'+pieces.join(' · ')+'</b>':'No glucose readings',.5,'#172b3a',11);
    const complete=basal && basal.known_hours>=basal.elapsed_hours-.001 && basal.elapsed_hours>0,bolus=stats.bolus;
    const total=complete && Number.isFinite(bolus)?basal.basal+bolus:null;
    const fraction=total>0?basal.basal/total:0;
    view.layout.shapes.push({name:'compact-insulin',type:'rect',xref:'paper',yref:'paper',x0:0,x1:1,y0:0,y1:0,fillcolor:'rgba(41,154,204,.16)',line:{width:0}});
    if(total>0)view.layout.shapes.push({name:'compact-insulin',type:'rect',xref:'paper',yref:'paper',x0:0,x1:fraction,y0:0,y1:0,fillcolor:'#62b6df',line:{width:0}});
    const basalLabel='Basal '+(complete?number(basal.basal,2)+' U':'incomplete')+(total>0?' · '+number(100*fraction,0)+'%':'');
    const bolusLabel='Bolus '+number(bolus,2)+' U'+(total>0?' · '+number(100*(1-fraction),0)+'%':'');
    annotate('compact-insulin-label','<b>'+basalLabel+'  |  '+bolusLabel+'</b>',.5,'#14354c',11);
    annotate('compact-total','<b>'+(stats.partial?'Total so far':'TDD')+' '+(total===null?'—':number(total,2)+' U')+'</b> · estimated · CGM '+number(stats.coverage,0)+'% · daily totals',0,'#718096',10);
  }
  closeFilledRegions(view);compactLegend(view.data);
}
// Pixel-sized footer rows and label lanes are recalculated at screen/PDF width.
function compactLayout(layout,plotWidth=null){
  if(!layout.yaxis4)return; // Source templates have not been composed yet.
  const range=layout.xaxis.range || [0,1440],span=Math.max(1,range[1]-range[0]);
  const width=Math.max(100,plotWidth || (layout.width || 1000)-(layout.margin.l || 58)-(layout.margin.r || 24));
  const labels=(layout.annotations || []).filter(a=>/^(Effective|Change) \| /.test(a.name || ''));
  const lanes=[];
  for(const label of labels.sort((a,b)=>a.x-b.x)){
    label.visible=label.x>=range[0] && label.x<=range[1];if(!label.visible)continue;
    const size=Math.min(width,Math.max(36,label.text.length*6)+14),center=(label.x-range[0])*width/span;
    const left=Math.max(0,Math.min(width-size,center-size/2));
    let lane=lanes.findIndex(end=>left>=end+6);if(lane<0){lane=lanes.length;lanes.push(0);}lanes[lane]=left+size;
    label.xanchor='left';label.xshift=left-center+4;label.yshift=0;label.yanchor='middle';
    label._compactLane=lane;
  }
  const laneCount=navigation?.report_render?Math.max(lanes.length,layout.meta.report_label_levels || 0):lanes.length;
  const required=(navigation?.report_render?470:515)+laneCount*17;
  layout.meta={...layout.meta,profile_label_levels:lanes.length,compact_required_height:required};
  if(!navigation?.report_render)layout.height=required;
  const height=Math.max(260,(layout.height || required)-(layout.margin.t || 38)-(layout.margin.b || 66));
  const low=(69+laneCount*17)/height,basalTop=low+60/height,high=layout.meta.compact_automation?(layout.meta.compact_automation_top || .90):1;
  layout.yaxis4.domain=[low,basalTop];layout.yaxis.domain=[basalTop+20/height,high];
  const old=layout.meta.compact_event_bounds || [0,1],map=y=>low+(y-old[0])/(old[1]-old[0])*(high-low);
  for(const shape of layout.shapes || []){
    if(shape.name==='compact-tir'){shape.y0=25/height;shape.y1=44/height;continue;}
    if(shape.name==='compact-insulin'){shape.y0=0;shape.y1=19/height;continue;}
    if(shape.yref==='paper' && (shape.name==='Profile change' || /^(Activity|Change|Effective) \| |^Profile · /.test(shape.name || ''))){
      if(!layout.meta.compact_event_bounds && shape.type==='rect' && shape.name?.startsWith('Effective | '))shape.y1/=Math.max(1,(layout.meta.percentage_max || 100)/100);
      shape.y0=Math.max(low,Math.min(high,map(shape.y0)));shape.y1=Math.max(low,Math.min(high,map(shape.y1)));
    }
  }
  for(const a of layout.annotations || []){
    if(/^(Effective|Change) \| /.test(a.name || '')){a.y=(56+(laneCount-1-(a._compactLane || 0))*17)/height;delete a._compactLane;}
    else if(a.name==='compact-tir-label')a.y=34.5/height;
    else if(a.name==='compact-insulin-label')a.y=9.5/height;
    else if(a.name==='compact-total'){a.y=-13/height;a.xanchor='left';}
    else if(a.name==='compact-cob'){a.y=high-10/height;a.xanchor='left';}
    else if(a.name==='compact-iob'){a.y=layout.yaxis.domain[0]+10/height;a.xanchor='left';}
  }
  layout.meta.compact_event_bounds=[low,high];
  layout.legend=navigation?.report_render?{...layout.legend,yref:'container',y:0,yanchor:'bottom'}:{...layout.legend,y:-32/height,yanchor:'top'};
}
// Shared marker-label placement: nearby first, then vertical downward leaders.
function placeGraphText(px,py,w,{width,bottom,top,boxes,points=[],direction=1,step=16,textHeight=14}){
  const tryLabel=(cx,cy,direct)=>{
    if(cx-w/2<0 || cx+w/2>width || cy<bottom || cy>top)return null;
    const box=[cx-w/2,cy-textHeight/2,cx+w/2,cy+textHeight/2];
    if(boxes.some(b=>box[0]<b[2]+3 && box[2]>b[0]-3 && box[1]<b[3]+3 && box[3]>b[1]-3))return null;
    if(points.some(([gx,gy,r])=>gx>box[0]-r&&gx<box[2]+r&&gy>box[1]-r&&gy<box[3]+r))return null;
    return {cx,cy,box,direct};
  };
  for(const offset of [step,step+6]){const p=tryLabel(Math.max(w/2,Math.min(width-w/2,px)),py+direction*offset,true);if(p)return p;}
  for(const dx of [0,12,24])for(let distance=20;py-distance>=bottom;distance+=step){const p=tryLabel(px+dx,py-distance,false);if(p)return p;}
  return null;
}
function compactAmountLabels(view,plotWidth=null){
  const {layout,data}=view,range=layout.xaxis.range || [0,1440],span=Math.max(1,range[1]-range[0]);
  const width=Math.max(100,plotWidth || (layout.width || 1000)-(layout.margin.l || 58)-(layout.margin.r || 24));
  const height=(layout.height || 515)-(layout.margin.t || 38)-(layout.margin.b || 66);
  const domain=layout.yaxis.domain,plotHeight=(domain[1]-domain[0])*height,boxes=[],points=[];
  layout.annotations=(layout.annotations || []).filter(a=>!a.name?.startsWith('compact-dose'));
  const treatments=data.filter(t=>['bolus','carbs'].includes(t.meta?.kind) && !t.meta?.compact_smb && t.text);
  for(const t of treatments)t.mode='markers';
  if(layout.meta?.compact_amount_labels===false)return;
  const pixelY=(t,y)=>{const axis=layout['yaxis'+(t.yaxis || 'y').slice(1)].range;return domain[0]*height+(y-axis[0])/(axis[1]-axis[0])*plotHeight;};
  // Reserve the glucose trace and treatment markers, as well as previously placed text.
  for(const t of data)if(t.meta?.kind==='glucose' || t.meta?.compact_smb || treatments.includes(t)){
    for(let i=0;i<(t.x || []).length;i++)if(Number.isFinite(t.x[i]) && Number.isFinite(t.y[i]))
      points.push([(t.x[i]-range[0])*width/span,pixelY(t,t.y[i]),treatments.includes(t)?6:3]);
  }
  // The free annotation area is usable too, but never cover event text, time ticks or TIR.
  for(const a of layout.annotations)if(/^(Effective|Change) \| /.test(a.name || '') && a.visible!==false){
    const left=(a.x-range[0])*width/span+(a.xshift || 0),cy=a.y*height;
    boxes.push([left,cy-7,left+a.text.length*6+10,cy+7]);
  }
  const basalBottom=layout.yaxis4.domain[0]*height;
  boxes.push([0,basalBottom-20,width,basalBottom-1]);
  const bottom=53,top=domain[1]*height-8;
  for(const t of treatments){
    for(let i=0;i<t.x.length;i++){
      const x=t.x[i],y=t.y[i],text=t.text[i];if(!text || !Number.isFinite(x) || !Number.isFinite(y) || x<range[0] || x>range[1])continue;
      const px=(x-range[0])*width/span,py=pixelY(t,y),w=text.length*5.8+6;
      // Carb labels sit below their downward-growing markers; bolus labels sit above.
      // Both use the same downward-only placement when the nearby text would overlap.
      const direction=t.meta.kind==='carbs'?-1:1;
      const selected=placeGraphText(px,py,w,{width,bottom,top,boxes,points,direction});
      // Extremely dense clusters retain every marker and exact amount on hover.
      if(!selected)continue;boxes.push(selected.box);
      const a={name:'compact-dose-'+t.meta.kind+'-'+x+'-'+i,text,xref:'x',x,
        bgcolor:layout.plot_bgcolor,borderpad:1,font:{size:10,color:t.textfont?.color || t.marker?.color || '#177cb8'}};
      if(selected.direct)Object.assign(a,{yref:'paper',y:selected.cy/height,xshift:selected.cx-px,showarrow:false,yanchor:'middle',xanchor:'center'});
      else Object.assign(a,{yref:t.yaxis,y,ax:selected.cx-px,ay:py-selected.cy,showarrow:true,
        arrowhead:0,arrowwidth:.6,arrowcolor:'rgba(100,125,145,.4)',standoff:4});
      layout.annotations.push(a);
    }
  }
}
// Marker colors and line segments share the same 4/10 mmol/L boundaries.
function colorGlucoseLines(view){
  const lines=[];
  for(const t of view.data){
    if(t.meta?.kind!=='glucose' || !String(t.mode).includes('lines'))continue;
    const thresholds=navigation.unit==='mmol/L'?[4,10]:[72,180];
    const normal=t.line?.color || '#218c24',color=y=>y<thresholds[0]?'#f44336':y>thresholds[1]?'#ff9800':normal,buckets=new Map();
    for(let i=1;i<(t.x || []).length;i++){
      const x0=t.x[i-1],x1=t.x[i],y0=t.y[i-1],y1=t.y[i];if(![x0,x1,y0,y1].every(Number.isFinite))continue;
      const cuts=[0,...thresholds.filter(v=>v>Math.min(y0,y1)&&v<Math.max(y0,y1)).map(v=>(v-y0)/(y1-y0)),1].sort((a,b)=>a-b);
      for(let j=1;j<cuts.length;j++){
        const a=cuts[j-1],b=cuts[j],c=color(y0+(y1-y0)*(a+b)/2);if(!buckets.has(c))buckets.set(c,{x:[],y:[]});const part=buckets.get(c);
        part.x.push(x0+(x1-x0)*a,x0+(x1-x0)*b,null);part.y.push(y0+(y1-y0)*a,y0+(y1-y0)*b,null);
      }
    }
    t.mode='markers';t.marker={...t.marker,color:t.y.map(y=>Number.isFinite(y)?color(y):normal)};
    for(const [c,part] of buckets)lines.push({...part,type:'scatter',mode:'lines',name:t.name,legendgroup:t.legendgroup,showlegend:false,hoverinfo:'skip',connectgaps:false,xaxis:t.xaxis,yaxis:t.yaxis,
      line:{...t.line,color:c},zorder:t.zorder || 0,meta:{kind:'glucose_line',dataset:'glucose',date:t.meta.date,legend_entry:false}});
  }
  view.data.unshift(...lines);
}

async function loadWorkspacePreset(settings){
  return enqueue(async()=>{syncing=true;clearHover();try{
    // Remove graph copies only; the source catalog remains available.
    for(let i=specs.length-1;i>0;i--)if(panelStateAt(i).duplicate)removeCustomPanelAt(i);
    for(let i=1;i<specs.length;i++)panelStateAt(i).deleted=true;
    restoreGlobalViewerSettings(settings);restoreCustomPanels(settings.customPanels || []);restoreGraphPanels(settings.panels || []);
    if(Array.isArray(settings.order)){const rank=i=>{const n=settings.order.indexOf(panelIdentity(i));return n<0?10000:n;};panelOrder.sort((a,b)=>rank(a)-rank(b));panelOrder.forEach(i=>panels.appendChild(panelCards[i]));}
    await Promise.all(graphs.map((g,i)=>{if(workspaceGraphs && i>0 && panelStateAt(i).deleted){if(g._fullLayout)Plotly.purge(g);g.layout=JSON.parse(JSON.stringify(specs[i].layout));g.data=[];return Promise.resolve();}const v=decorate(panelSourceView(localSource(i),i,[0,1440]),i);return Plotly.newPlot(g,v.data,sizedLayout(v,i),{responsive:false,displaylogo:false});}));graphs.forEach(bindGraph);
  }finally{syncing=false;controls();}});
}

// Delayed busy UI; determinate values count finished graph operations, never time.
let workStarted=0,workTimer=null,workBox=null,workBar=null,workText=null;
function startGraphWork(){
  if(navigation?.report_render)return;
  workStarted=performance.now();clearTimeout(workTimer);
  if(!workBox){workBox=document.createElement('div');workBox.id='work-progress';workBox.hidden=true;workBox.setAttribute('role','status');workBar=document.createElement('progress');workText=document.createElement('span');workBox.append(workBar,workText);document.getElementById('toolbar').after(workBox);}
  workBar.removeAttribute('value');workText.textContent='Updating graphs…';workTimer=setTimeout(()=>{workBox.hidden=false;},250);
}
async function graphWorkStep(label,done,total){
  if(workBox && performance.now()-workStarted>250){workBox.hidden=false;workText.textContent=label+' · '+done+' / '+total;workBar.max=total;workBar.value=done;}
  await new Promise(resolve=>setTimeout(resolve,0));
}
function finishGraphWork(){clearTimeout(workTimer);if(workBox)workBox.hidden=true;}
