// Independent graph instances share immutable data banks, never each other's settings.
const panelStates=new Map(),panelUIs=[];let panelSequence=0;let dormantPanelStates=[];
function sourceIdentity(s){if(!s.layout.meta?.dataset && !s.layout.meta?.kind)return 'profile:settings';return (s.layout.meta?.kind || '')+':'+(s.layout.meta?.dataset || s.layout.title.text.split(' · ')[0]);}
function ensurePanelState(spec,raw={}){
  const base=raw.base || sourceIdentity(spec),custom=spec.layout.meta?.custom_id;
  const id=raw.id || spec.layout.meta?.panel_id || (custom?'custom:'+custom:base);
  spec.layout.meta={...spec.layout.meta,panel_id:id};
  if(!panelStates.has(id))panelStates.set(id,{id,base,title:raw.title || (custom?'Custom '+custom.replace('custom-',''):spec.layout.title.text.split(' · ')[0]),deleted:raw.deleted===true,mode:raw.mode || 'Median + band',
    garmin:JSON.parse(JSON.stringify(raw.garmin || garminOptions)),hourly:raw.hourly || hourlyModes[spec.layout.meta?.dataset] || 'Average',showDailyGrid:raw.showDailyGrid===true,showTargets:raw.showTargets!==false,excludeSMB:raw.excludeSMB===true || (!('excludeSMB' in raw) && excludeSMB),
    axisRanges:JSON.parse(JSON.stringify(raw.axisRanges || {})),insight:{duration:spec.layout.meta?.insight==='sleep'?24:6,normalization:'absolute',metric:spec.layout.meta?.insight==='sensor_variability'?'rate':'glucose',aggregation:'Median',fitY:false,showIOB:false,showCOB:false,minCarbs:0,filterStartCOB:false,maxStartCOB:0,siteWindow:'full',sleepView:'overnight',relationX:'asleep_hours',relationY:'mean',...raw.insight},duplicate:raw.duplicate===true,profileCopy:raw.profileCopy===true,overlay:raw.overlay || currentOverlay,metric:raw.metric || currentMetric,sameScale:raw.sameScale===true});
  return panelStates.get(id);
}
function panelStateAt(index){return ensurePanelState(specs[index]);}
function graphOptions(id){return panelStates.get(id)?.garmin || garminOptions;}
function panelHasMedian(spec){
  const meta=spec.layout.meta || {};
  if(meta.kind==='hourly' || ['target','g_activity'].includes(meta.dataset))return false;
  if(meta.kind==='custom')return [...customState(meta.custom_id).selected].some(id=>!id.startsWith('profile:') && id!=='ns:target');
  if(!meta.dataset && !meta.kind){
    const state=panelStates.get(meta.panel_id),overlay=state?.profileCopy?state.overlay:currentOverlay;
    return overlay!=='None' && overlay!=='Temporary Targets';
  }
  return true;
}
function effectivePanelMode(index){return selectedDays.length<2 || dateCycled?'One day':!panelHasMedian(specs[index])?'Multiple days':panelStateAt(index).mode;}
function panelModeControls(parent,panel,spec){
  const state=ensurePanelState(spec),id=state.id;
  const mode=document.createElement('select');mode.setAttribute('aria-label','Graph display mode');
  for(const [value,label] of [['Multiple days','Multiple days'],['Median + band','Summary']]){const o=document.createElement('option');o.value=value;o.textContent=label;mode.appendChild(o);}
  mode.title='Multiple days shows individual dated curves; Summary combines them. The statistic control and legend specify Average or Median.';
  mode.addEventListener('change',()=>changePanelState(panel.graphIndex,s=>{s.mode=mode.value;}));parent.appendChild(mode);
  const duplicate=document.createElement('button');duplicate.textContent='Duplicate';duplicate.type='button';duplicate.addEventListener('click',()=>duplicateGraph(panel.graphIndex));parent.appendChild(duplicate);
  const remove=document.createElement('button');remove.textContent='Delete graph';remove.setAttribute('aria-label','Delete graph');remove.type='button';remove.addEventListener('click',()=>deleteGraph(panel.graphIndex));parent.appendChild(remove);
  panelUIs.push({panel,id,mode,duplicate,remove});
}
function panelControls(){
  for(const ui of panelUIs){if(!ui.panel.isConnected)continue;const state=panelStates.get(ui.id);if(!state)continue;
    if(ui.hourlyGridControl){ui.el.disabled=!ready || syncing;ui.el.setAttribute('aria-pressed',String(state.showDailyGrid));ui.el.textContent='Daily grid: '+(state.showDailyGrid?'on':'off');continue;}
    if(ui.profileControl){ui.el.value=state[ui.field];ui.el.disabled=!ready || syncing;if(ui.field==='sameScale'){ui.el.setAttribute('aria-pressed',String(state.sameScale));ui.el.textContent='Same axis scale: '+(state.sameScale?'on':'off');}continue;}
    if(ui.insightOnly){ui.el.value=state.insight[ui.field];ui.el.disabled=!ready || syncing;
      (ui.wrap || ui.el).hidden=ui.visible?!ui.visible(state.insight):false;
      if(ui.text)ui.text.textContent=ui.prefix+ui.el.value+' h';
      if(ui.onSync)ui.onSync();
      if(ui.toggle){ui.el.setAttribute('aria-pressed',String(state.insight[ui.field]===true));ui.el.textContent=ui.toggle(state.insight);}
      continue;}
    const spec=specs[ui.panel.graphIndex],fixed=!panelHasMedian(spec);
    ui.mode.hidden=selectedDays.length<2 || fixed || (spec.layout.meta?.insight==='sleep' && state.insight.sleepView==='relationship');ui.mode.value=state.mode;ui.mode.disabled=!ready || syncing;
    if(ui.top){if(ui.duplicate)ui.duplicate.disabled=!ready || syncing;if(ui.remove)ui.remove.disabled=!ready || syncing;continue;}
    ui.duplicate.disabled=!ready || syncing;ui.remove.disabled=!ready || syncing;
  }
}
function hourlyGridControls(parent,panel,spec){
  const state=ensurePanelState(spec),el=document.createElement('button');el.type='button';el.setAttribute('aria-label','Show daily grid');
  el.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{s.showDailyGrid=!s.showDailyGrid;}));parent.appendChild(el);
  panelUIs.push({hourlyGridControl:true,panel,id:state.id,el});
}
function applyHourlyGrid(view,index){
  if(view.layout.meta?.kind!=='hourly')return;
  const show=panelStateAt(index).showDailyGrid===true,heat=view.data.find(t=>t.meta?.kind==='hourly_heatmap');
  heat.visible=show;heat.showscale=show;view.layout.meta.daily_grid=show;
  if(!show){
    // Keep the immutable matrix for aggregation and local day navigation.
    // Its former space belongs to the bars when it is not displayed.
    view.layout.yaxis.visible=false;view.layout.xaxis.visible=false;
    view.layout.yaxis2.domain=[0,1];view.layout.xaxis2.showticklabels=true;
    view.layout.height=280;view.layout.margin.l=64;view.layout.margin.r=28;
  }
}
async function changePanelState(index,mutate){
  if(!ready)return;
  return enqueue(async()=>{syncing=true;clearHover();const state=panelStateAt(index),before=JSON.parse(JSON.stringify(state));
    try{mutate(state);controls();await redrawLocal((_,i)=>i===index);}catch(e){panelStates.set(state.id,before);card.textContent='Could not update graph: '+e.message;}finally{syncing=false;controls();}
  });
}
function appendGraphCopy(baseIndex,raw=null){
  const source=specs[baseIndex],state=raw || JSON.parse(JSON.stringify(panelStateAt(baseIndex)));
  if(!raw){state.id='duplicate-'+(++panelSequence)+'-'+crypto.randomUUID();state.duplicate=true;}
  if(baseIndex===0 && !raw){state.profileCopy=true;state.overlay=currentOverlay;state.metric=currentMetric;state.sameScale=sameScale;state.showTargets=showTargets;}
  const copy=JSON.parse(JSON.stringify(source));copy.layout.meta.panel_id=state.id;
  if(copy.layout.meta.kind==='custom'){
    const custom=newCustomState(JSON.parse(JSON.stringify(raw?.custom || serializeCustom(customState(copy.layout.meta.custom_id)))));
    copy.layout.meta.custom_id=custom.id;state.custom=serializeCustom(custom);
  }
  const index=specs.length;specs.push(copy);navigation.figures.push(JSON.parse(JSON.stringify(navigation.figures[baseIndex] || source)));
  ensurePanelState(copy,state);createPanel(index);return index;
}
async function duplicateGraph(index){
  if(!ready || syncing)return;
  return enqueue(async()=>{syncing=true;clearHover();controls();let copy;
    try{copy=appendGraphCopy(index);const v=decorate(localSource(copy),copy);v.layout=sizedLayout(v,copy);
      if(!v.layout.meta?.non_time)v.layout.xaxis.range=graphs[index].layout.xaxis.range.slice();
      await Plotly.newPlot(graphs[copy],v.data,v.layout,{responsive:false,displaylogo:false,toImageButtonOptions:{format:'png',scale:2}});await reflowProfileLabels(graphs[copy]);bindGraph(graphs[copy],copy);
      // Put the comparison beside the original in the scrolling order.
      panelOrder.splice(panelOrder.indexOf(copy),1);panelOrder.splice(panelOrder.indexOf(index)+1,0,copy);panelOrder.forEach(i=>panels.appendChild(panelCards[i]));
    }catch(e){if(copy!==undefined)removeCustomPanelAt(copy);card.textContent='Could not duplicate graph: '+e.message;}finally{syncing=false;controls();}
  });
}
async function removeGraphCopy(index){
  if(!ready || syncing || !panelStateAt(index).duplicate)return;
  return deleteGraph(index);
}
async function deleteGraph(index){
  if(!ready || syncing)return;
  return enqueue(async()=>{syncing=true;clearHover();try{
    if(panelStateAt(index).duplicate)removeCustomPanelAt(index);
    else panelStateAt(index).deleted=true;
  }finally{syncing=false;controls();lastSize='';scheduleLayout();}});
}
function hiddenGraphCatalog(){
  return [...panelStates.values(),...dormantPanelStates].filter(s=>s.deleted && !s.duplicate)
    .map(s=>({id:s.id,base:s.base,label:s.title || s.base}));
}
let sentHiddenGraphs=null;
function notifyHiddenGraphs(){
  if(!ready || syncing || navigation?.report_render)return;
  const hidden=hiddenGraphCatalog(),encoded=JSON.stringify(hidden);
  if(encoded===(sentHiddenGraphs ?? JSON.stringify(navigation?.hidden_graphs || [])))return;
  sentHiddenGraphs=encoded;
  window.parent.postMessage({type:'profile-studio:graph-visibility',request:{kind:'graph-visibility',id:crypto.randomUUID(),hidden}},'*');
}
function applyGraphRestore(){
  const request=navigation?.restore_graph;
  if(!request || request.revision===appliedRestoreRevision)return;
  const state=panelStates.get(request.id) || dormantPanelStates.find(s=>s.id===request.id);
  if(state)state.deleted=false;
  appliedRestoreRevision=request.revision;
}
function restoreGraphPanels(saved){
  if(!Array.isArray(saved))return;dormantPanelStates=[];
  const legacy='insight:insight_site_after',merged='insight:insight_site_age';
  // Two former base panels become one. Prefer an existing Site-age selection;
  // retain intentional copies and migrate post-change-only views with their window.
  const hasSiteAge=saved.some(s=>!s.duplicate && s.base===merged);
  saved=saved.filter(s=>s.duplicate || s.base!==legacy || !hasSiteAge).map(s=>s.base!==legacy?s:
    {...s,base:merged,id:s.id===legacy?merged:s.id,insight:{...s.insight,siteWindow:'limited'}});
  // Restore existing graphs first. A copy never stores duplicated raw observations.
  for(const raw of saved.filter(s=>!s.duplicate)){
    let index=specs.findIndex(s=>s.layout.meta?.panel_id===raw.id);if(index<0)index=specs.findIndex(s=>sourceIdentity(s)===raw.base);
    if(index<0){dormantPanelStates.push(raw);continue;}panelStates.delete(specs[index].layout.meta.panel_id);ensurePanelState(specs[index],raw);
  }
  for(const raw of saved.filter(s=>s.duplicate)){
    if(panelStates.has(raw.id))continue;const index=raw.profileCopy?0:specs.findIndex(s=>sourceIdentity(s)===raw.base);
    if(index>=0)appendGraphCopy(index,raw);else dormantPanelStates.push(raw);
  }
}
function applyPanelRanges(view,index){
  if(view.layout.meta?.kind==='custom')return;
  for(const [name,range] of Object.entries(panelStateAt(index).axisRanges))if(/^yaxis\d*$/.test(name) && view.layout[name] && Array.isArray(range) && range.length===2 && range.every(Number.isFinite))Object.assign(view.layout[name],{range:range.slice(),autorange:false});
}
function rememberPanelAxes(div,event){
  const index=graphs.indexOf(div);if(index<1 || div.layout.meta?.kind==='custom')return;
  const state=panelStateAt(index);let changed=false;
  for(const key of Object.keys(div.layout).filter(k=>/^yaxis\d*$/.test(k))){
    let r=event[key+'.range'];if(event[key+'.range[0]']!==undefined)r=[event[key+'.range[0]'],event[key+'.range[1]']];
    if(event[key+'.autorange']){delete state.axisRanges[key];changed=true;}else if(Array.isArray(r)&&r.every(Number.isFinite)){state.axisRanges[key]=r.slice();changed=true;}
  }if(changed)controls();
}

function profileCopyControls(areas,panel,spec){
  const state=ensurePanelState(spec);if(!state.profileCopy)return;
  for(const [field,choices,parent,label] of [['metric',Object.entries(navigation?.profiles || {}).map(([k,f])=>[k,f.layout.title.text.split(' · ')[0]]),areas.settings,'Profile setting'],['overlay',Object.keys(navigation?.overlays || {}).map(k=>[k,k]),areas.content,'Profile copy overlay']]){
    if(!choices.length)continue;const el=document.createElement('select');el.setAttribute('aria-label',label);
    for(const [value,text] of choices){const o=document.createElement('option');o.value=value;o.textContent=text;el.appendChild(o);}el.value=state[field];
    el.addEventListener('change',()=>changePanelState(panel.graphIndex,s=>{s[field]=el.value;s.axisRanges={};}));parent.appendChild(el);panelUIs.push({profileControl:true,panel,id:state.id,el,field});
  }
  const target=document.createElement('button');target.type='button';target.panel=panel;target.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{s.showTargets=!s.showTargets;}));areas.content.appendChild(target);targetButtons.push(target);
  const button=document.createElement('button');button.type='button';button.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{s.sameScale=!s.sameScale;s.axisRanges={};}));areas.settings.appendChild(button);panelUIs.push({profileControl:true,panel,id:state.id,el:button,field:'sameScale'});
}
