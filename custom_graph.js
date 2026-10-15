// Every custom panel owns state; all panels reuse the same trace bank and renderer.
const customFields=navigation?.custom?.fields || [],customStates=new Map(),customUIs=new Map();
let customSequence=0;
function customState(id) {return customStates.get(id || customStates.keys().next().value);}
function customIndex(id) {return specs.findIndex(s=>s.layout.meta?.custom_id===id);}
function newCustomState(raw={}) {
  const fieldId=id=>id.startsWith('profile:')?'profile:'+id.split(':')[1]+':nightscout':id;
  let id=raw.id;
  if(typeof id!=='string' || !/^custom-[0-9]+$/.test(id) || customStates.has(id))id='custom-'+(++customSequence);
  customSequence=Math.max(customSequence,Number(id.slice(7)));
  const state={id,selected:new Set((raw.selected || navigation?.custom?.selected || []).map(fieldId).filter(k=>customFields.some(f=>f.id===k))),
    sameScale:raw.sameScale===true,activityShading:raw.activityShading!==false,
    garmin:restoredGarminOptions(raw.garmin),fieldOptions:{},axisRanges:{}};
  state.garmin={...garminOptions,...state.garmin,activity:{},stressSmooth:false}; // Custom filters are owned by each selected field.
  for(const [key,v] of Object.entries(raw.fieldOptions || {}))if(customFields.some(f=>f.id===fieldId(key)))
    state.fieldOptions[fieldId(key)]={aggregation:v.aggregation==='Median'?'Median':'Average',style:v.style==='Bars'?'Bars':'Line',excludeSMB:v.excludeSMB===true,showAmounts:v.showAmounts!==false,axis:v.axis==='own'?'own':'unit',visualOffset:Number.isFinite(v.visualOffset)?Math.max(-90,Math.min(90,v.visualOffset)):0,smooth:v.smooth===true,tauSeconds:Number.isFinite(v.tauSeconds)?Math.min(1800,Math.max(5,v.tauSeconds)):300};
  for(const [key,range] of Object.entries(raw.axisRanges || {}))if(Array.isArray(range) && range.length===2 && range.every(v=>v===null || Number.isFinite(v)) && (range.includes(null) || range[0]<range[1]))state.axisRanges[key]=range.slice();
  customStates.set(id,state);return state;
}
function originalCustomStates(){return [...customStates.values()].filter(s=>{const index=customIndex(s.id);return index>=0 && !panelStateAt(index).duplicate;});}
function serializeCustom(state) {return {id:state.id,selected:[...state.selected],sameScale:state.sameScale,
  activityShading:state.activityShading,garmin:state.garmin,fieldOptions:state.fieldOptions,axisRanges:state.axisRanges};}
function customAxisKey(state,field) {return state.fieldOptions[field.id]?.axis==='own' || state.fieldOptions[field.id]?.visualOffset || (!state.garmin.sleepOverlay && field.dataset in sleepFields && [...state.selected].some(id=>customFields.find(f=>f.id===id)?.dataset==='g_sleep'))?'field:'+field.id:'unit:'+field.unit;}
function customDisplayField(field,state,daySelected=dateCycled) {
  return {...field,unit:field.dataset==='g_workout_speed' && ['km/h','mph'].includes(field.unit)
    ?(state.garmin.pace?'min/km':'km/h'):field.dataset==='g_sleep' && selectedDays.length>1 && !daySelected && (panelStates.get(specs[customIndex(state.id)]?.layout.meta?.panel_id)?.mode || navigation.mode)==='Median + band'
    ?(state.garmin.sleepDistribution?(state.fieldOptions[field.id]?.aggregation || 'Average')+' sleep (h/hour)':'Stage composition (%)'):(daySelected?field.daily_unit:field.selected_unit) || field.unit};
}
function customExtent(values) {
  let low=Infinity,high=-Infinity;
  for(const value of values)if(Number.isFinite(value)){low=Math.min(low,value);high=Math.max(high,value);}
  return low===Infinity?[0,1]:[low,high];
}
function canSmooth(field) {return !['profile','profile_percentage','site_changes','sensor_changes','target','basal','basal_percent','carbs','bolus','g_steps','g_steps_cumulative','g_sleep','g_sleep_restless','g_sleep_movement'].includes(field.dataset);}
function setupCustomControls(bar,id) {
  bar.classList.add('custom-graph-controls');
  const areas=controlAreas(bar),ui={buttons:[],id};customUIs.set(id,ui);
  const details=document.createElement('details'),summary=document.createElement('summary');
  summary.textContent='Data Layers';details.className='custom-data-layers';ui.layersSummary=summary;details.appendChild(summary);areas.settings.appendChild(details);
  const search=document.createElement('input');search.type='search';search.placeholder='Find a data layer';search.setAttribute('aria-label','Find custom data layer');details.appendChild(search);
  search.addEventListener('input',()=>{for(const b of ui.buttons)b.hidden=!b.getAttribute('aria-label').toLowerCase().includes(search.value.toLowerCase());});
  for(const group of ['Nightscout','Summary','Garmin','Profiles']) {
    if(!customFields.some(f=>f.group===group))continue;
    const choices=document.createElement('div');choices.className='custom-options';
    const label=document.createElement('strong');label.textContent=group;choices.appendChild(label);
    customFields.filter(f=>f.group===group).forEach(field=>{
      const button=document.createElement('button');button.type='button';button.value=field.id;button.setAttribute('aria-label',field.label);
      button.style.borderLeft='3px solid '+(field.metric_color || field.color);
      button.title=field.daily?.length?field.label+' · '+field.unit:'No records loaded for this layer';
      if(field.group==='Profiles') {
        const setting=document.createElement('span');setting.textContent=field.metric_label+' · ';setting.style.color=field.metric_color;setting.style.fontWeight='600';button.appendChild(setting);
        const source=document.createElement('span');source.textContent=field.profile_name;source.style.color=field.source_color;button.appendChild(source);
        const role=document.createElement('small');role.textContent=field.source_role==='nightscout'?' · recorded':field.source_role==='ref1'?' · Ref 1':field.source_role==='ref2'?' · Ref 2':' · Current';role.style.color=field.source_color;button.appendChild(role);
      } else {button.textContent=field.label;button.style.color=field.color;}
      button.addEventListener('click',()=>changeCustom(field.id,id));ui.buttons.push(button);choices.appendChild(button);
    });details.appendChild(choices);
  }
  const button=(parent,text,fn)=>{const b=document.createElement('button');b.type='button';b.textContent=text;b.addEventListener('click',fn);parent.appendChild(b);return b;};
  ui.scale=button(areas.settings,'Same axis scale',()=>changeCustom(null,id));
  ui.auto=button(areas.settings,'Autoscale axes',()=>changeCustomSetting(id,s=>{s.axisRanges={};}));
  ui.sleep=document.createElement('div');ui.sleep.className='custom-sleep-controls';areas.settings.appendChild(ui.sleep);
  ui.sleepLayout=button(ui.sleep,'Sleep: Underneath',()=>changeCustomSetting(id,s=>{s.garmin.sleepOverlay=!s.garmin.sleepOverlay;}));ui.sleepLayout.setAttribute('aria-label','Custom sleep signal layout');
  const sleepDetails=document.createElement('details'),sleepSummary=document.createElement('summary');sleepSummary.textContent='Sleep overlays';sleepDetails.appendChild(sleepSummary);ui.sleep.appendChild(sleepDetails);
  const sleepChoices=document.createElement('div');sleepChoices.className='custom-options';sleepDetails.appendChild(sleepChoices);ui.sleepChoices=[];
  for(const [key,label] of Object.entries(sleepFields)){
    const field=customFields.find(f=>f.dataset===key),b=button(sleepChoices,label,()=>changeCustomSetting(id,s=>{if(s.selected.has(field.id))s.selected.delete(field.id);else s.selected.add(field.id);s.garmin.sleepFields=[...s.selected].map(id=>customFields.find(f=>f.id===id)?.dataset).filter(k=>k in sleepFields);}));
    b.setAttribute('aria-label','Sleep overlay '+label);b.title=field?.daily?.length?'Show '+label+' with sleep.':'No recorded data for this signal';ui.sleepChoices.push({button:b,field});
  }
  ui.fields=document.createElement('div');ui.fields.className='custom-field-settings';areas.settings.appendChild(ui.fields);

  ui.status=document.createElement('span');ui.status.className='custom-help';areas.settings.appendChild(ui.status);
}
function customControls() {
  for(const [id,ui] of customUIs) {
    const state=customState(id),fields=customFields.filter(f=>state.selected.has(f.id)).map(f=>customDisplayField(f,state,effectivePanelMode(customIndex(id))==='One day')),units=new Set(fields.map(f=>customAxisKey(state,f)));
    ui.sleep.hidden=!fields.some(f=>f.dataset==='g_sleep');ui.sleepLayout.textContent='Sleep: '+(state.garmin.sleepOverlay?'Overlay':'Underneath');ui.sleepLayout.disabled=!ready||syncing;
    for(const {button,field} of ui.sleepChoices){button.disabled=!ready||syncing||!field?.daily?.length;button.setAttribute('aria-pressed',String(Boolean(field&&state.selected.has(field.id))));}
    ui.buttons.forEach(b=>{b.disabled=!ready || syncing;b.setAttribute('aria-pressed',String(state.selected.has(b.value)));});
    for(const b of [ui.scale,ui.auto])b.disabled=!ready || syncing;
    ui.scale.hidden=fields.length===0 || fields.length>2 || fields.some(f=>['g_sleep','g_activity'].includes(f.dataset));
    ui.scale.disabled=!ready || syncing || units.size<2;
    ui.scale.textContent=units.size===1?'Same axis scale: shared unit':'Same axis scale: '+(state.sameScale?'on':'off');
    ui.scale.setAttribute('aria-pressed',String(state.sameScale));
    ui.layersSummary.textContent='Data Layers · '+fields.length+' selected';
    ui.status.textContent=fields.length+' data layers';
    const signature=JSON.stringify([[...state.selected],fields.map(f=>[state.fieldOptions[f.id]?.axis || 'unit',f.unit]),state.garmin.pace,effectivePanelMode(customIndex(id)),dateCycled]);
    if(ui.signature!==signature && !(ui.fields.inputs || []).some(n=>n.editing)){ui.signature=signature;customFieldControls(state,fields,ui.fields);}
    for(const refresh of ui.fields.refresh || [])refresh();
    for(const node of ui.fields.inputs || [])node.disabled=!ready || (node.type!=='range' && syncing);
  }
}
function customFieldControls(state,fields,parent) {
  parent.replaceChildren();parent.inputs=[];parent.refresh=[];
  for(const field of fields) {
    const row=document.createElement('div');row.className='custom-setting-row';parent.appendChild(row);
    const heading=document.createElement('span');heading.className='custom-layer-heading';row.appendChild(heading);
    const title=document.createElement('strong');title.textContent=field.label;title.style.color=field.color;heading.appendChild(title);
    const remove=document.createElement('button');remove.type='button';remove.className='custom-layer-remove';remove.textContent='×';remove.title='Remove '+field.label;remove.setAttribute('aria-label','Remove '+field.label);
    remove.addEventListener('click',()=>changeCustomSetting(state.id,s=>{s.selected.delete(field.id);}));heading.appendChild(remove);parent.inputs.push(remove);
    const own=state.fieldOptions[field.id] || {axis:'unit',smooth:false,tauSeconds:300};
    const save=(key,value)=>changeCustomSetting(state.id,s=>{s.fieldOptions[field.id]={...own,...s.fieldOptions[field.id],[key]:value};s.sameScale=false;});
    const choice=(label,items,get,set)=>{
      const select=document.createElement('select');select.setAttribute('aria-label',field.label+' '+label);select.title=field.label+' · '+label;
      for(const [value,text] of items){const o=document.createElement('option');o.value=value;o.textContent=text;select.appendChild(o);}
      select.addEventListener('change',()=>set(select.value));row.appendChild(select);parent.inputs.push(select);parent.refresh.push(()=>select.value=String(get()));return select;
    };
    const current=()=>customState(state.id).fieldOptions[field.id] || {};
    if(field.dataset==='g_workout_speed')choice('units',[['speed','km/h'],['pace','min/km']],()=>customState(state.id).garmin.pace?'pace':'speed',value=>changeCustomSetting(state.id,s=>{s.garmin.pace=value==='pace';s.axisRanges={};}));
    if(field.dataset==='g_stress')choice('style',[['Line','Stress line'],['Bars','Stress bars']],()=>current().style || 'Line',value=>save('style',value));
    if(field.dataset==='g_sleep' && effectivePanelMode(customIndex(state.id))==='Median + band')choice('distribution',[['hourly','Hourly sleep'],['stages','Stage composition']],()=>customState(state.id).garmin.sleepDistribution?'hourly':'stages',value=>changeCustomSetting(state.id,s=>{s.garmin.sleepDistribution=value==='hourly';}));
    if(['bolus','carbs','profile_percentage','site_changes','sensor_changes','g_steps','g_sleep','g_sleep_restless','g_stress'].includes(field.dataset) && effectivePanelMode(customIndex(state.id))==='Median + band')choice('bar statistic',[['Average','Bars: Average'],['Median','Bars: Median']],()=>current().aggregation || 'Average',value=>save('aggregation',value));
    if(field.dataset==='bolus')choice('SMB',[['all','Include SMB'],['exclude','Exclude SMB']],()=>current().excludeSMB?'exclude':'all',value=>save('excludeSMB',value==='exclude'));
    if(['carbs','bolus'].includes(field.dataset) && effectivePanelMode(customIndex(state.id))!=='Median + band')choice('amount labels',[['show','Amount labels'],['hide','Amounts on hover']],()=>current().showAmounts===false?'hide':'show',value=>save('showAmounts',value==='show'));
    const axis=document.createElement('select');axis.setAttribute('aria-label',field.label+' axis assignment');
    for(const [value,label] of [['unit','Axis: shared unit'],['own','Axis: separate']]){const option=document.createElement('option');option.value=value;option.textContent=label;axis.appendChild(option);}
    axis.value=own.axis;axis.addEventListener('change',()=>save('axis',axis.value));row.appendChild(axis);parent.inputs.push(axis);
    const offsetLabel=document.createElement('label');offsetLabel.textContent='Vertical offset (%)';offsetLabel.title='Positive values move this layer up on a separate axis. Recorded values and hover readings stay unchanged.';
    const offset=document.createElement('input');offset.type='number';offset.min='-90';offset.max='90';offset.step='5';offset.style.width='65px';offset.setAttribute('aria-label',field.label+' vertical offset (%)');offset.value=own.visualOffset || 0;
    offset.addEventListener('change',()=>{const value=Number(offset.value);if(Number.isFinite(value))save('visualOffset',Math.max(-90,Math.min(90,value)));});offsetLabel.appendChild(offset);row.appendChild(offsetLabel);parent.inputs.push(offset);parent.refresh.push(()=>{if(document.activeElement!==offset)offset.value=current().visualOffset || 0;});
    const key=customAxisKey(state,field),limits=state.axisRanges[key] || [null,null];
    for(const [i,label] of [[0,'Min'],[1,'Max']]){
      const input=document.createElement('input');input.type='number';input.step='any';input.placeholder=label+': auto';input.value=limits[i] ?? '';input.style.width='78px';input.setAttribute('aria-label',field.label+' '+label);
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
  const index=customIndex(id),range=panelTimeRange(index,graphs[0]._fullLayout.xaxis.range),source=localSource(index);
  const view=decorate(panelSourceView(source,index,range),index);
  view.layout=sizedLayout(view,index);view.layout.xaxis.range=range;view.layout.xaxis.autorange=false;applyClockTicks(view.layout,range);workoutAxes(view,range);applyCustomRanges(view);
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
    const field=customFields.find(f=>state.selected.has(f.id) && customAxisKey(state,customDisplayField(f,state))===key),offset=state.fieldOptions[field?.id]?.visualOffset || 0;
    const bounds=state.axisRanges[key] || [null,null];if(!offset && bounds.every(v=>v===null))continue;
    const ref='y'+axis.slice(5),range=view.layout.xaxis?.range;
    const values=view.data.filter(t=>(t.yaxis || 'y')===ref && !t.meta?.legend_proxy).flatMap(t=>(t.y || []).filter((v,i)=>Number.isFinite(v) && (!offset || !range || !Number.isFinite(t.x?.[i]) || t.x[i]>=range[0] && t.x[i]<=range[1])));
    if(offset && !values.length)continue;
    const extent=customExtent(values),padding=Math.max(.01,(extent[1]-extent[0])*.06,Math.abs(extent[0])*.01);
    const current=offset?[extent[0]-padding,extent[1]+padding]:view.layout[axis].range || extent;
    let low=bounds[0] ?? Math.min(...current),high=bounds[1] ?? Math.max(...current);
    const pad=Math.max(.01,Math.abs(high-low)*.06);if(high<=low){if(bounds[1]===null)high=low+pad;else if(bounds[0]===null)low=high-pad;else continue;}
    const reverse=(state.garmin.pace && view.data.some(t=>(t.yaxis || 'y')===ref && t.meta?.dataset==='g_workout_speed')) || (view.layout[axis].range?.[0]>view.layout[axis].range?.[1] && view.data.some(t=>(t.yaxis || 'y')===ref && t.meta?.dataset==='g_sleep'));
    // Add blank space on the opposite side; shifting a fixed span clips peaks.
    const extra=(high-low)*Math.abs(offset)/(100-Math.abs(offset));
    if(offset>0){if(reverse)high+=extra;else low-=extra;}
    else if(offset<0){if(reverse)low-=extra;else high+=extra;}
    Object.assign(view.layout[axis],{range:reverse?[high,low]:[low,high],autorange:false});
  }
}
function composeCustom(view) {
  const state=customState(view.layout.meta.custom_id),options=state.garmin;
  const daySelected=view.layout.meta.custom_day;
  let fields=Array.from(state.selected,id=>customFields.find(f=>f.id===id)).filter(Boolean).map(f=>customDisplayField(f,state,daySelected));
  const underneath=!state.garmin.sleepOverlay && fields.some(f=>f.dataset==='g_sleep');
  if(underneath)fields=fields.filter(f=>!(f.dataset in sleepFields)).concat(fields.filter(f=>f.dataset in sleepFields));
  const units=[...new Set(fields.map(f=>customAxisKey(state,f)))];
  const {layout}=view,day=layout.meta.custom_day;
  view.data=[];layout.annotations=[];
  // Rebuild axes from scratch so removed fields cannot leave axes or fill artifacts.
  Object.keys(layout).filter(k=>/^yaxis\d*$/.test(k)).forEach(k=>delete layout[k]);
  layout.shapes=(layout.shapes || []).filter(s=>s.name==='Profile change');
  layout.xaxis.domain=[0,1];
  customAxisLayout(layout,units.length);
  layout.title.text='Custom graph '+state.id.replace('custom-','')+' · '+(day || specs[customIndex(state.id)].layout.title.text.split(' · ').slice(1).join(' · '));
  layout.barmode=fields.some(f=>f.group==='Summary') && !day?'group':'overlay';
  units.forEach((unit,index)=>{
    const onAxis=fields.filter(f=>customAxisKey(state,f)===unit),color=onAxis[0].color;
    const axis=coloredAxis(unit.startsWith('field:')?onAxis[0].label+' ('+onAxis[0].unit+')':onAxis[0].unit,color,index);
    if(onAxis[0].unit!=='U/h' && onAxis.every(f=>f.dataset==='profile' || f.dataset==='variable_sens'))axis.rangemode='normal';
    layout['yaxis'+(index?index+1:'')]=axis;
  });
  for(const field of fields) {
    const index=units.indexOf(customAxisKey(state,field)),axis='y'+(index?index+1:'');
    const traces=JSON.parse(JSON.stringify(day?field.daily:(field.modes?.[view.layout.meta.display_mode] || field.selected)));
    for(const trace of traces.filter(t=>!day || !t.meta?.date || t.meta.date===day)) {
      trace.yaxis=axis;trace.xaxis='x';
      if(field.dataset in sleepFields){trace.visible=true;delete trace.meta.sleep_overlay;if(trace.type==='scatter' && !['garmin_band','band'].includes(trace.meta?.kind)){trace.mode='lines+markers';trace.marker={...trace.marker,size:3};}}
      if(trace.type==='bar')trace.offsetgroup=field.id;
      const filter=state.fieldOptions[field.id];
      if(field.dataset==='bolus' && filter?.excludeSMB && (trace.meta?.baseline_smb || (trace.meta?.label || trace.name)?.trim().toLowerCase()==='smb'))continue;
      if(['bolus','carbs'].includes(field.dataset) && filter?.showAmounts===false){trace.mode=(trace.mode || 'markers').replace('+text','').replace('text+','');delete trace.text;}
      if(trace.meta?.hourly_values){
        const bank=filter?.excludeSMB && trace.meta.hourly_without_smb || trace.meta.hourly_values,stat=filter?.aggregation || 'Average';
        trace.y=bank[stat==='Median'?'median':'average'].slice();trace.name=stat+' hourly '+field.label.toLowerCase();trace.meta.label=trace.name;
      }
      if(filter?.smooth && canSmooth(field) && trace.meta?.kind!=='garmin_band' && trace.meta?.kind!=='band' && trace.type!=='bar'){
        trace.y=lowPass(trace.x,trace.y,filter.tauSeconds/60);
        if(trace.meta?.summary)for(const key of ['average','median','p10','p90'])if(trace.meta.summary[key])trace.meta.summary[key]=lowPass(trace.x,trace.meta.summary[key],filter.tauSeconds/60);
        trace.meta.custom_smoothed=true;
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
  customSleepLayout(view,state,fields);
  if(!view.data.some(t=>(t.y || []).some(Number.isFinite)))layout.annotations=[{text:fields.length?'No data for the selected fields and dates':'Choose fields above to build a custom graph',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false}];
}
function customSleepLayout(view,state,fields){
  if(state.garmin.sleepOverlay || !fields.some(f=>f.dataset==='g_sleep'))return;
  const signals=fields.filter(f=>f.dataset in sleepFields);if(!signals.length)return;
  const layout=view.layout,total=260+signals.length*85,base=signals.length*85/total;
  const signalAxes=new Set(signals.map(f=>Object.keys(layout.meta.custom_axes).find(axis=>layout.meta.custom_axes[axis]===customAxisKey(state,f))));
  for(const [axis,key] of Object.entries(layout.meta.custom_axes))if(!signalAxes.has(axis))layout[axis].domain=[base,1];
  signals.forEach((field,i)=>{
    const axis=Object.keys(layout.meta.custom_axes).find(axis=>layout.meta.custom_axes[axis]===customAxisKey(state,field));
    const upper=(signals.length-i)*85/total,lower=(signals.length-i-1)*85/total;
    Object.assign(layout[axis],{domain:[lower,upper-22/total],overlaying:undefined,anchor:'x',side:'left',position:undefined,shift:0,showgrid:true,title:{text:field.unit,font:{size:10}},nticks:3});
    layout.annotations.push({name:'Custom sleep metric | '+field.dataset,text:field.label,xref:'x domain',yref:'paper',x:0,y:upper,xanchor:'left',yanchor:'top',showarrow:false,font:{size:10,color:field.color}});
    if(i===signals.length-1)layout.xaxis.anchor='y'+axis.slice(5);
  });
  customAxisLayout(layout,Object.keys(layout.meta.custom_axes).length-signals.length);layout.height=Math.max(layout.height || 390,total+90);
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
  spec.layout.meta.custom_id=state.id;daily.layout.meta.custom_id=state.id;spec.layout.meta.panel_id='custom:'+state.id;daily.layout.meta.panel_id='custom:'+state.id;
  specs.push(spec);navigation.figures.push(daily);createPanel(index);return index;
}
function removeCustomPanelAt(index) {
  const id=specs[index].layout.meta.custom_id,panel=panelCards[index];
  if(ready)Plotly.purge(graphs[index]);
  panel.remove();panelStates.delete(specs[index].layout.meta?.panel_id);customStates.delete(id);customUIs.delete(id);
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
      const view=decorate(panelSourceView(source,index,range),index);view.layout=sizedLayout(view,index);view.layout.xaxis.range=range;
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
  if(workspaceGraphs){
    dormantCustomPanels=customTemplate?[]:saved;
    for(const raw of saved)if(customStates.has(raw.id)){
      customStates.delete(raw.id);newCustomState(raw);const ui=customUIs.get(raw.id);if(ui)ui.signature=null;
    }
    return;
  }
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
  const group=settingsGroup(areas.settings,'Profile');group.id='profile-settings-group';group.appendChild(metricSelect);group.appendChild(scaleButton);
  if(!dataOnly){const mode=document.createElement('select');mode.setAttribute('aria-label','Profile overlay display mode');for(const [value,label] of [['Multiple days','Multiple days'],['Median + band','Median']]){const o=document.createElement('option');o.value=value;o.textContent=label;mode.appendChild(o);}mode.addEventListener('change',()=>changePanelState(0,s=>{s.mode=mode.value;}));group.appendChild(mode);const panel={graphIndex:0,isConnected:true},duplicate=document.createElement('button');duplicate.type='button';duplicate.textContent='Duplicate';duplicate.addEventListener('click',()=>duplicateGraph(0));group.appendChild(duplicate);
    const remove=document.createElement('button');remove.type='button';remove.textContent='Delete graph';remove.setAttribute('aria-label','Delete graph');remove.addEventListener('click',()=>deleteGraph(0));group.appendChild(remove);
    workspacePanelControls(areas,panel,specs[0]);
    panelUIs.push({top:true,mode,duplicate,remove,id:ensurePanelState(specs[0]).id,panel});}
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
