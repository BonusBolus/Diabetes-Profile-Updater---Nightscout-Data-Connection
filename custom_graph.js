// Every custom panel owns state; all panels reuse the same trace bank and renderer.
const customFields=navigation?.custom?.fields || [],customStates=new Map(),customUIs=new Map();
let customSequence=0;
function customState(id) {return customStates.get(id || customStates.keys().next().value);}
function customIndex(id) {return specs.findIndex(s=>s.layout.meta?.custom_id===id);}
function newCustomState(raw={}) {
  let id=raw.id;
  if(typeof id!=='string' || !/^custom-[0-9]+$/.test(id) || customStates.has(id))id='custom-'+(++customSequence);
  customSequence=Math.max(customSequence,Number(id.slice(7)));
  const state={id,selected:new Set((raw.selected || navigation?.custom?.selected || []).filter(k=>customFields.some(f=>f.id===k))),
    sameScale:raw.sameScale===true,activityShading:raw.activityShading!==false,
    garmin:JSON.parse(JSON.stringify(raw.garmin || garminOptions)),fieldOptions:{},axisRanges:{}};
  state.garmin={...garminOptions,...state.garmin,activity:{},stressSmooth:false}; // Custom filters are owned by each selected field.
  for(const [key,v] of Object.entries(raw.fieldOptions || {}))if(customFields.some(f=>f.id===key))
    state.fieldOptions[key]={axis:v.axis==='own'?'own':'unit',smooth:v.smooth===true,tauSeconds:Number.isFinite(v.tauSeconds)?Math.min(1800,Math.max(5,v.tauSeconds)):300};
  for(const [key,range] of Object.entries(raw.axisRanges || {}))if(Array.isArray(range) && range.length===2 && range.every(v=>v===null || Number.isFinite(v)) && (range.includes(null) || range[0]<range[1]))state.axisRanges[key]=range.slice();
  customStates.set(id,state);return state;
}
function serializeCustom(state) {return {id:state.id,selected:[...state.selected],sameScale:state.sameScale,
  activityShading:state.activityShading,garmin:state.garmin,fieldOptions:state.fieldOptions,axisRanges:state.axisRanges};}
function customAxisKey(state,field) {return state.fieldOptions[field.id]?.axis==='own'?'field:'+field.id:'unit:'+field.unit;}
function customDisplayField(field,state,daySelected=dateCycled) {
  return {...field,unit:field.dataset==='g_workout_speed' && ['km/h','mph'].includes(field.unit)
    ?(state.garmin.pace?'min/km':'km/h'):field.dataset==='g_sleep' && !daySelected && navigation.mode==='Median + band'
    ?(state.garmin.sleepDistribution?state.garmin.aggregation+' sleep (min/hour)':'Stage composition (%)'):(daySelected?field.daily_unit:field.selected_unit) || field.unit};
}
function customExtent(values) {
  let low=Infinity,high=-Infinity;
  for(const value of values)if(Number.isFinite(value)){low=Math.min(low,value);high=Math.max(high,value);}
  return low===Infinity?[0,1]:[low,high];
}
function canSmooth(field) {return !['profile','target','basal','basal_percent','carbs','bolus','g_steps','g_steps_cumulative','g_sleep','g_sleep_restless','g_sleep_movement'].includes(field.dataset);}
function setupCustomControls(bar,id) {
  const areas=controlAreas(bar),ui={buttons:[],id};customUIs.set(id,ui);
  const details=document.createElement('details'),summary=document.createElement('summary');
  summary.textContent='Choose custom data';details.appendChild(summary);areas.content.appendChild(details);
  for(const group of ['Nightscout','Garmin','Profiles']) {
    if(!customFields.some(f=>f.group===group))continue;
    const choices=document.createElement('div');choices.className='custom-options';
    const label=document.createElement('strong');label.textContent=group;choices.appendChild(label);
    customFields.filter(f=>f.group===group).forEach(field=>{
      const button=document.createElement('button');button.type='button';button.value=field.id;button.setAttribute('aria-label',field.label);
      button.style.borderLeft='3px solid '+(field.metric_color || field.color);
      if(field.group==='Profiles') {
        const setting=document.createElement('span');setting.textContent=field.metric_label+' · ';setting.style.color=field.metric_color;setting.style.fontWeight='600';button.appendChild(setting);
        const source=document.createElement('span');source.textContent=field.profile_name;source.style.color=field.source_color;button.appendChild(source);
        const role=document.createElement('small');role.textContent=field.source_role==='ref1'?' · Ref 1':field.source_role==='ref2'?' · Ref 2':' · Current';role.style.color=field.source_color;button.appendChild(role);
      } else {button.textContent=field.label;button.style.color=field.color;}
      button.addEventListener('click',()=>changeCustom(field.id,id));ui.buttons.push(button);choices.appendChild(button);
    });details.appendChild(choices);
  }
  const button=(parent,text,fn)=>{const b=document.createElement('button');b.type='button';b.textContent=text;b.addEventListener('click',fn);parent.appendChild(b);return b;};
  ui.scale=button(areas.settings,'Same axis scale',()=>changeCustom(null,id));
  ui.auto=button(areas.settings,'Autoscale axes',()=>changeCustomSetting(id,s=>{s.axisRanges={};}));
  ui.pace=button(areas.settings,'Pace',()=>changeCustomSetting(id,s=>{s.garmin.pace=!s.garmin.pace;s.axisRanges={};}));
  ui.fields=document.createElement('div');ui.fields.className='custom-field-settings';areas.settings.appendChild(ui.fields);

  ui.status=document.createElement('span');ui.status.className='custom-help';bar.appendChild(ui.status);
}
function customControls() {
  for(const [id,ui] of customUIs) {
    const state=customState(id),fields=customFields.filter(f=>state.selected.has(f.id)).map(f=>customDisplayField(f,state)),units=new Set(fields.map(f=>customAxisKey(state,f)));
    ui.buttons.forEach(b=>{b.disabled=!ready || syncing;b.setAttribute('aria-pressed',String(state.selected.has(b.value)));});
    for(const b of [ui.scale,ui.auto,ui.pace])b.disabled=!ready || syncing;
    ui.scale.hidden=fields.length===0 || fields.length>2 || fields.some(f=>['g_sleep','g_activity'].includes(f.dataset));
    ui.scale.disabled=!ready || syncing || units.size<2;
    ui.scale.textContent=units.size===1?'Same axis scale: shared unit':'Same axis scale: '+(state.sameScale?'on':'off');
    ui.scale.setAttribute('aria-pressed',String(state.sameScale));
    ui.pace.hidden=!fields.some(f=>f.dataset==='g_workout_speed');ui.pace.textContent='Speed: '+(state.garmin.pace?'min/km':'km/h');
    ui.status.textContent=fields.length+' datasets · independent axes and filters · shared time navigation';
    const signature=JSON.stringify([[...state.selected],fields.map(f=>state.fieldOptions[f.id]?.axis || 'unit'),state.garmin.pace,dateCycled]);
    if(ui.signature!==signature && !(ui.fields.inputs || []).some(n=>n.editing)){ui.signature=signature;customFieldControls(state,fields,ui.fields);}
    for(const refresh of ui.fields.refresh || [])refresh();
    for(const node of ui.fields.inputs || [])node.disabled=!ready || (node.type!=='range' && syncing);
  }
}
function customFieldControls(state,fields,parent) {
  parent.replaceChildren();parent.inputs=[];parent.refresh=[];
  for(const field of fields) {
    const row=document.createElement('div');row.className='custom-setting-row';parent.appendChild(row);
    const title=document.createElement('strong');title.textContent=field.label;title.style.color=field.color;row.appendChild(title);
    const own=state.fieldOptions[field.id] || {axis:'unit',smooth:false,tauSeconds:300};
    const save=(key,value)=>changeCustomSetting(state.id,s=>{s.fieldOptions[field.id]={...own,...s.fieldOptions[field.id],[key]:value};s.sameScale=false;});
    const axis=document.createElement('select');axis.setAttribute('aria-label',field.label+' axis assignment');
    for(const [value,label] of [['unit','Axis: shared unit'],['own','Axis: separate']]){const option=document.createElement('option');option.value=value;option.textContent=label;axis.appendChild(option);}
    axis.value=own.axis;axis.addEventListener('change',()=>save('axis',axis.value));row.appendChild(axis);parent.inputs.push(axis);
    const key=customAxisKey(state,field),limits=state.axisRanges[key] || [null,null];
    for(const [i,label] of [[0,'Min'],[1,'Max']]){
      const input=document.createElement('input');input.type='number';input.step='any';input.placeholder=label+': auto';input.value=limits[i] ?? '';input.style.width='90px';input.setAttribute('aria-label',field.label+' '+label);
      input.addEventListener('change',()=>changeCustomSetting(state.id,s=>{
        const range=(s.axisRanges[key] || [null,null]).slice();range[i]=input.value===''?null:Number(input.value);
        if(range.some(v=>v!==null&&!Number.isFinite(v)) || (!range.includes(null)&&range[0]>=range[1]))throw Error('Minimum must be below maximum.');
        s.axisRanges[key]=range;s.sameScale=false;
      }));row.appendChild(input);parent.inputs.push(input);
      parent.refresh.push(()=>{if(document.activeElement!==input)input.value=customState(state.id).axisRanges[key]?.[i] ?? '';});
    }
    if(canSmooth(field)){
      const toggle=document.createElement('button');toggle.type='button';toggle.textContent='Low-pass';toggle.setAttribute('aria-pressed',String(own.smooth));toggle.addEventListener('click',()=>save('smooth',!(customState(state.id).fieldOptions[field.id]?.smooth)));row.appendChild(toggle);parent.inputs.push(toggle);
      const slider=document.createElement('input');configureSmoothingSlider(slider,own.tauSeconds);slider.setAttribute('aria-label',field.label+' smoothing seconds');
      const label=document.createElement('span');label.className='smoothing-value';label.textContent=smoothingLabel(own.tauSeconds);
      slider.addEventListener('input',()=>{slider.editing=true;label.textContent=smoothingLabel(smoothingSeconds(slider));});slider.addEventListener('change',()=>{const seconds=smoothingSeconds(slider);slider.editing=false;return save('tauSeconds',seconds);});row.appendChild(slider);row.appendChild(label);parent.inputs.push(slider);
      parent.refresh.push(()=>{const current=customState(state.id).fieldOptions[field.id] || own;setSmoothingValue(slider,current.tauSeconds);if(!slider.editing)label.textContent=smoothingLabel(current.tauSeconds);toggle.setAttribute('aria-pressed',String(current.smooth));});
    }
  }
}
async function redrawCustom(id) {
  const index=customIndex(id),range=graphs[0]._fullLayout.xaxis.range.slice(),source=localSource(index);
  const view=decorate(dateCycled?dailyView(source,index,selectedDays[0],range):source,index);
  view.layout=sizedLayout(view,index);view.layout.xaxis.range=range;view.layout.xaxis.autorange=false;workoutAxes(view,range);applyCustomRanges(view);
  await Plotly.react(graphs[index],view.data,view.layout);
}
async function changeCustomSetting(id,mutate) {
  if(!ready)return;
  return enqueue(async()=>{
    const state=customState(id),previous=JSON.parse(JSON.stringify(serializeCustom(state)));syncing=true;clearHover();
    try{mutate(state);controls();await redrawCustom(id);}
    catch(error){customStates.delete(id);newCustomState(previous);card.textContent=error.message || 'Could not update custom graph.';}
    finally{syncing=false;controls();}
  });
}
async function changeCustom(field,id=customStates.keys().next().value) {
  return changeCustomSetting(id,state=>{
    if(field===null){state.sameScale=!state.sameScale;state.axisRanges={};}
    else {if(state.selected.has(field))state.selected.delete(field);else state.selected.add(field);state.sameScale=false;}
  });
}
function applyCustomRanges(view) {
  if(view.layout.meta?.kind!=='custom')return;
  const state=customState(view.layout.meta.custom_id);
  for(const [axis,key] of Object.entries(view.layout.meta.custom_axes || {})){
    const bounds=state.axisRanges[key];if(!bounds || bounds.every(v=>v===null))continue;
    const ref='y'+axis.slice(5),values=view.data.filter(t=>(t.yaxis || 'y')===ref).flatMap(t=>t.y || []).filter(Number.isFinite);
    const current=view.layout[axis].range || customExtent(values);
    let low=bounds[0] ?? Math.min(...current),high=bounds[1] ?? Math.max(...current);
    const pad=Math.max(.01,Math.abs(high-low)*.06);if(high<=low){if(bounds[1]===null)high=low+pad;else if(bounds[0]===null)low=high-pad;else continue;}
    const reverse=state.garmin.pace && view.data.some(t=>(t.yaxis || 'y')===ref && t.meta?.dataset==='g_workout_speed');
    Object.assign(view.layout[axis],{range:reverse?[high,low]:[low,high],autorange:false});
  }
}
function composeCustom(view) {
  const state=customState(view.layout.meta.custom_id),options=state.garmin;
  const daySelected=view.layout.meta.custom_day;
  const fields=Array.from(state.selected,id=>customFields.find(f=>f.id===id)).filter(Boolean).map(f=>customDisplayField(f,state,daySelected)),units=[...new Set(fields.map(f=>customAxisKey(state,f)))];
  const {layout}=view,day=layout.meta.custom_day;
  view.data=[];layout.annotations=[];
  // Rebuild axes from scratch so removed fields cannot leave axes or fill artifacts.
  Object.keys(layout).filter(k=>/^yaxis\d*$/.test(k)).forEach(k=>delete layout[k]);
  layout.shapes=(layout.shapes || []).filter(s=>s.name==='Profile change');
  layout.xaxis.domain=[0,1];
  customAxisLayout(layout,units.length);
  layout.title.text='Custom graph '+state.id.replace('custom-','')+' · '+(day || specs[customIndex(state.id)].layout.title.text.split(' · ').slice(1).join(' · '));
  layout.barmode='overlay';
  units.forEach((unit,index)=>{
    const onAxis=fields.filter(f=>customAxisKey(state,f)===unit),color=onAxis[0].color;
    const axis=coloredAxis(unit.startsWith('field:')?onAxis[0].label+' ('+onAxis[0].unit+')':onAxis[0].unit,color,index);
    if(onAxis[0].unit!=='U/h' && onAxis.every(f=>f.dataset==='profile' || f.dataset==='variable_sens'))axis.rangemode='normal';
    layout['yaxis'+(index?index+1:'')]=axis;
  });
  for(const field of fields) {
    const index=units.indexOf(customAxisKey(state,field)),axis='y'+(index?index+1:'');
    const traces=JSON.parse(JSON.stringify(day?field.daily:field.selected));
    for(const trace of traces.filter(t=>!day || !t.meta?.date || t.meta.date===day)) {
      trace.yaxis=axis;trace.xaxis='x';
      const filter=state.fieldOptions[field.id];
      if(filter?.smooth && canSmooth(field) && trace.meta?.kind!=='garmin_band' && trace.meta?.kind!=='band' && trace.type!=='bar'){
        trace.y=lowPass(trace.x,trace.y,filter.tauSeconds/60);
        trace.meta={...trace.meta,label:(trace.meta?.label || trace.name)+' · '+smoothingLabel(filter.tauSeconds)+' low-pass'};
      }
      // Every field has its own legend group, including target low/high and negative IOB.
      trace.legendgroup=field.id+':'+(trace.legendgroup || trace.name);
      view.data.push(trace);
    }
    if(field.dataset==='target' && !fields.some(f=>f.dataset==='glucose'))Object.assign(layout['yaxis'+(index?index+1:'')],{range:[0,navigation.unit==='mmol/L'?20:360],autorange:false});
    if(field.dataset==='glucose') {
      const scale=navigation.unit==='mmol/L'?1:18;
      const glucose=view.data.filter(t=>t.meta?.kind==='glucose' || t.meta?.dataset==='glucose').flatMap(t=>t.y || []).filter(Number.isFinite);
      const peak=Math.max(0,customExtent(glucose)[1]),maximum=peak>20*scale?Math.ceil(peak*1.05/scale)*scale:20*scale;
      Object.assign(layout['yaxis'+(index?index+1:'')],{range:[0,maximum],autorange:false});
      layout.shapes.push({type:'rect',xref:'x',yref:axis,x0:0,x1:1440,y0:4*scale,y1:10*scale,line:{width:0},fillcolor:'rgba(50,205,50,.12)',layer:'below'});
    }
  }
  if(!units.length)layout.yaxis={visible:false};
  transformGarmin(view,-1);
  if(state.sameScale && fields.length<=2 && units.length===2) {
    const values=[0,...view.data.flatMap(t=>t.y || []).filter(Number.isFinite),...units.flatMap((u,i)=>layout['yaxis'+(i?i+1:'')].range || [])];
    const [low,high]=customExtent(values),span=Math.max(1,high-low);
    const range=[low<0?low-.05*span:0,high+.2*span];
    for(const name of ['yaxis','yaxis2'])Object.assign(layout[name],{range,autorange:false});
  }
  layout.meta.custom_axes=Object.fromEntries(units.map((key,i)=>['yaxis'+(i?i+1:''),key]));
  smbAxes(view);
  garminAxes(view);
  if(!view.data.some(t=>(t.y || []).some(Number.isFinite)))layout.annotations=[{text:fields.length?'No data for the selected fields and dates':'Choose fields above to build a custom graph',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false}];
}

// Fixed pixel lanes keep axes compact on wide screens and stable on resize.
function customAxisPosition(index) {
  const left=index%2===0,lane=Math.floor(index/2);
  return {anchor:'free',side:left?'left':'right',position:left?0:1,
          shift:(left?-1:1)*lane*54,...(index?{overlaying:'y'}:{})};
}
function customAxisLayout(layout,count) {
  const left=Math.ceil(count/2),right=Math.floor(count/2);
  layout.margin={...layout.margin,l:54+Math.max(0,left-1)*54,r:54+Math.max(0,right-1)*54};
}

function coloredAxis(title,color,index) {
  return {title:{text:title,font:{color,size:12},standoff:3},color,tickfont:{color,size:12},tickformat:'.3~g',
    showline:true,linecolor:color,linewidth:1,ticks:'outside',ticklen:3,tickcolor:color,automargin:true,
    showgrid:index===0,rangemode:'tozero',autorange:true,...customAxisPosition(index)};
}

let dormantCustomPanels=[];
function appendCustomPanel(raw={}) {
  const state=newCustomState(raw),index=specs.length;
  const spec=JSON.parse(JSON.stringify(customTemplate)),daily=JSON.parse(JSON.stringify(customDailyTemplate));
  spec.layout.meta.custom_id=state.id;daily.layout.meta.custom_id=state.id;
  specs.push(spec);navigation.figures.push(daily);createPanel(index);return index;
}
function removeCustomPanelAt(index) {
  const id=specs[index].layout.meta.custom_id,panel=panelCards[index];
  if(ready)Plotly.purge(graphs[index]);
  panel.remove();customStates.delete(id);customUIs.delete(id);
  specs.splice(index,1);navigation.figures.splice(index,1);graphs.splice(index,1);targetNotes.splice(index,1);
  if(ready){guides.splice(index,1);highlights.splice(index,1);}
  for(let i=moveButtons.length-1;i>=0;i--)if(moveButtons[i].panel===panel)moveButtons.splice(i,1);
  const entries=Object.entries(panelCards);for(const key of Object.keys(panelCards))delete panelCards[key];
  for(const [oldKey,item] of entries){const old=Number(oldKey);if(old===index)continue;const key=old>index?old-1:old;item.graphIndex=key;panelCards[key]=item;}
  const order=panelOrder.filter(i=>i!==index).map(i=>i>index?i-1:i);panelOrder.splice(0,panelOrder.length,...order);
}
async function addCustomGraph() {
  if(!ready || syncing || !customTemplate)return;
  return enqueue(async()=>{
    syncing=true;controls();clearHover();let index;
    try{
      index=appendCustomPanel();const range=graphs[0]._fullLayout.xaxis.range.slice(),source=localSource(index);
      const view=decorate(dateCycled?dailyView(source,index,selectedDays[0],range):source,index);view.layout=sizedLayout(view,index);view.layout.xaxis.range=range;
      await Plotly.newPlot(graphs[index],view.data,view.layout,{responsive:false,displaylogo:false,scrollZoom:false,toImageButtonOptions:{format:'png',scale:2}});
      bindGraph(graphs[index],index);
    } catch(error){if(index!==undefined)removeCustomPanelAt(index);card.textContent='Could not add graph: '+error.message;}
    finally{syncing=false;controls();}
  });
}
async function removeCustomGraph(id) {
  if(!ready || syncing)return;
  return enqueue(async()=>{syncing=true;controls();clearHover();try{const index=customIndex(id);if(index>0)removeCustomPanelAt(index);}finally{syncing=false;controls();}});
}
function restoreCustomPanels(saved) {
  const catalog=navigation?.custom_catalog;
  const kept=Array.isArray(catalog)?saved.filter(s=>catalog.includes(s.id)):saved;
  const ids=navigation?.custom_ids;
  const visible=Array.isArray(ids)?ids:kept.map(s=>s.id);
  dormantCustomPanels=kept.filter(s=>!visible.includes(s.id));
  if(!customTemplate){dormantCustomPanels=kept;return;}
  for(let i=specs.length-1;i>0;i--)if(specs[i].layout.meta?.kind==='custom')removeCustomPanelAt(i);
  for(const id of visible)appendCustomPanel(kept.find(s=>s.id===id) || {id});
}

let topControlAreas;
function setupTopControlAreas() {
  const bar=expand.parentElement || document.getElementById('toolbar-left');if(!bar)return;
  const row=document.createElement('div');row.id='top-graph-controls';
  const profile=document.getElementById('profile');profile.parentElement?.insertBefore(row,profile);
  if(!profile.parentElement)bar.appendChild(row);
  const areas=controlAreas(row);topControlAreas=areas;
  for(const el of [overlayControl,targetButton].filter(Boolean))areas.content.appendChild(el);
  const group=settingsGroup(areas.settings,'Profile');group.appendChild(metricSelect);group.appendChild(scaleButton);
}
function rememberCustomAxes(div,event) {
  if(div.layout.meta?.kind!=='custom')return;
  const state=customState(div.layout.meta.custom_id);let changed=false;
  for(const [axis,key] of Object.entries(div.layout.meta.custom_axes || {})){
    let range=event[axis+'.range'];
    if(event[axis+'.range[0]']!==undefined)range=[event[axis+'.range[0]'],event[axis+'.range[1]']];
    if(event[axis+'.autorange']){delete state.axisRanges[key];changed=true;}
    else if(Array.isArray(range) && range.every(Number.isFinite)){state.axisRanges[key]=range.slice().sort((a,b)=>a-b);state.sameScale=false;changed=true;}
  }
  if(changed)controls();
}
