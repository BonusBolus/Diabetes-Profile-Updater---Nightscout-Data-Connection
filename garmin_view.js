// Display-only transforms. Source samples stay immutable in the trace bank.
const garminOptions={stressSmooth:false,stressLine:false,pace:false,stressTau:5,aggregation:"Average",stepsHistogram:false,sleepFields:[],sleepOverlay:false,sleepDistribution:true,glucoseActivities:false,activityShading:true,activity:{}};
const defaultGarminOptions=JSON.parse(JSON.stringify(garminOptions));
function restoredGarminOptions(raw=garminOptions){
  raw=raw&&typeof raw==='object'?raw:garminOptions;
  return JSON.parse(JSON.stringify({...defaultGarminOptions,...raw,sleepFields:Array.isArray(raw?.sleepFields)?raw.sleepFields:[],activity:raw?.activity&&typeof raw.activity==='object'?raw.activity:{}}));
}
const garminButtons=[],stressSliders=[],sleepButtons=[],activitySliders=[],activityButtons=[],activityFloors=[];
const activitySignals=['g_workout_hr','g_workout_cadence','g_workout_speed','g_workout_altitude','g_workout_power'];
const activityFloorSignals=activitySignals.filter(key=>key!=='g_workout_altitude');
function activityOptions(key,options=garminOptions) {return {smooth:false,tauSeconds:300,lower:0,...options.activity[key]};}
function smoothingLabel(seconds){return Math.floor(seconds/60)+'m '+String(seconds%60).padStart(2,'0')+'s';}
// Give sub-minute intervals useful travel; keep controls and captions stable during drag.
const smoothingStops=[5,10,15,20,25,30,35,40,45,50,55,60,90,120,150,180,240,300,420,600,900,1200,1800];
function smoothingSeconds(slider){return smoothingStops[Number(slider.value)];}
function setSmoothingValue(slider,seconds){
  if(slider.editing)return;
  slider.value=String(smoothingStops.reduce((best,v,i)=>Math.abs(v-seconds)<Math.abs(smoothingStops[best]-seconds)?i:best,0));
}
function configureSmoothingSlider(slider,seconds){
  slider.type='range';slider.min='0';slider.max=String(smoothingStops.length-1);slider.step='1';slider.style.width='160px';
  setSmoothingValue(slider,seconds);
  slider.addEventListener('pointerdown',()=>{slider.editing=true;});
  slider.addEventListener('blur',()=>{slider.editing=false;});
}

function changeActivityOption(key,option,value,id=null) {
  return changeGarminOption('activity',()=>({...graphOptions(id).activity,[key]:{...activityOptions(key,graphOptions(id)),[option]:value}}),key,id);
}
function smoothingControl(bar,key,id=null) {
  const label=document.createElement('label'),slider=document.createElement('input'),value=document.createElement('span');
  const stress=key==='g_stress';
  if(stress){slider.type='range';slider.min='1';slider.max='30';slider.step='1';slider.value='5';slider.style.width='160px';}
  else configureSmoothingSlider(slider,300);
  value.className='smoothing-value';
  slider.setAttribute('aria-label',(key==='g_stress'?'Stress':key.replace('g_workout_','Activity '))+' smoothing time constant in '+(stress?'minutes':'seconds'));
  slider.title=stress?'1–30 minutes; higher values smooth more.':'5 seconds–30 minutes; higher values smooth more. Gaps reset the filter.';
  slider.addEventListener('input',()=>{slider.editing=true;value.textContent='Smoothing: '+smoothingLabel(stress?Number(slider.value)*60:smoothingSeconds(slider));});
  slider.addEventListener('change',()=>{const seconds=stress?Number(slider.value)*60:smoothingSeconds(slider);slider.editing=false;return stress?changeGarminOption('stressTau',seconds/60,null,id):changeActivityOption(key,'tauSeconds',seconds,id);});
  label.appendChild(value);label.appendChild(slider);bar.appendChild(label);
  (key==='g_stress'?stressSliders:activitySliders).push({slider,value,key,id});
}
function activityGraphControls(bar,spec,axisControls) {
  const id=spec.layout.meta.panel_id;
  const key=spec.layout.meta.dataset;
  const button=document.createElement('button');button.type='button';button.textContent='Low-pass';
  button.addEventListener('click',()=>changeActivityOption(key,'smooth',!activityOptions(key,graphOptions(id)).smooth,id));
  bar.appendChild(button);activityButtons.push({button,key,id});smoothingControl(bar,key,id);
  if(!activityFloorSignals.includes(key))return;
  const label=document.createElement('label'),slider=document.createElement('input'),value=document.createElement('span');
  const unit=key==='g_workout_speed'?'km/h':spec.data.find(t=>t.meta?.dataset===key)?.meta.unit || '';
  let peak=0;
  for(const figure of [spec,...(navigation?.figures || [])])for(const t of figure.data || [])if(t.meta?.dataset===key)
    for(const v of t.y || [])if(Number.isFinite(v))peak=Math.max(peak,v*(key==='g_workout_speed' && t.meta.unit==='mph'?1.609344:1));
  const step=key==='g_workout_speed'?.1:1;
  slider.type='range';slider.min='0';slider.max=String(Math.max(step,Math.ceil(peak/step)*step));slider.step=String(step);slider.value='0';slider.style.width='100px';
  slider.setAttribute('aria-label',key.replace('g_workout_','Activity ')+' lower axis limit');
  slider.title='0 = Auto. Clip the displayed range below this limit; upper scaling remains automatic. Source samples stay unchanged.'+(key==='g_workout_speed'?' Always in km/h; in pace view this clips slow values.':'');
  const caption=v=>'Lower: '+(v>0?v+' '+unit:'Auto');
  slider.addEventListener('input',()=>{value.textContent=caption(Number(slider.value));});
  slider.addEventListener('change',()=>changeActivityOption(key,'lower',Number(slider.value),id));
  label.className='axis-floor';slider.className='axis-slider';slider.style.width='22px';slider.style.height='130px';
  label.appendChild(value);label.appendChild(slider);axisControls.appendChild(label);activityFloors.push({key,slider,value,caption,peak,id});
}
const sleepFields={'g_sleep_movement':'Movement','g_sleep_restless':'Restless moments','g_sleep_respiration':'Respiration','g_sleep_rhr':'Resting heart rate','g_sleep_spo2':'Pulse Ox','g_sleep_rr':'Sleep respiration','g_sleep_hrv':'Overnight HRV'};
function garminControls(bar,spec) {
  const areas=controlAreas(bar),settings=areas.settings;
  const key=spec.layout.meta?.dataset,id=spec.layout.meta?.panel_id;
  const options=key==='g_stress'?[['stressSmooth','Low-pass'],['stressLine','Line']]:
    key==='g_workout_speed'?[['pace','Pace · min/km']]:[];
  if(key==='g_steps')options.push(['stepsHistogram','Histogram']);
  if(['g_steps','g_stress','g_sleep'].includes(key))options.push(['aggregation','Bars: Average']);
  if(key==='g_stress')smoothingControl(settings,key,id);
  if(activitySignals.includes(key))activityGraphControls(settings,spec,areas.axis);
  if(key==='g_sleep') {
    options.push(['sleepOverlay','Sleep: Underneath']);
    options.push(['sleepDistribution','Hourly sleep distribution']);
    const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Sleep overlays';details.appendChild(summary);
    const choices=document.createElement('div');choices.className='custom-options';details.appendChild(choices);areas.content.appendChild(details);
    for(const [field,label] of Object.entries(sleepFields)) {
      const button=document.createElement('button');button.type='button';button.textContent=label;
      const available=(spec.layout.meta.sleep_fields || []).includes(field);
      button.title=!available?'No recorded data for this signal':field==='g_sleep_rhr'?'Daily resting heart rate reference over the recorded night; not a time-resolved measurement.':field==='g_sleep_respiration'?'Monitoring respiration recorded inside sleep sessions.':field==='g_sleep_rr'?'Sleep-export respiration where present; monitoring respiration otherwise. These can match Respiration.':'Show '+label.toLowerCase()+' alongside sleep stages.';
      button.addEventListener('click',()=>changeGarminOption('sleepFields',graphOptions(id).sleepFields.includes(field)?graphOptions(id).sleepFields.filter(k=>k!==field):[...graphOptions(id).sleepFields,field],null,id));
      choices.appendChild(button);sleepButtons.push({button,field,available,id});
    }
  }
  for(const [option,label] of options) {
    const button=document.createElement('button');button.type='button';button.textContent=label;
    button.title=option==='stressSmooth'?'Display filter: time-aware exponential smoothing; choose the time constant with the slider. Resets at gaps longer than 5 minutes.':
      option==='stressLine'?'Switch stress bars to a colored line; smoothing always uses a line.':
      option==='sleepDistribution'?'Hourly minutes asleep across dates with recorded stages, or conditional stage percentages among observations at each time. Missing dates are excluded.':
      option==='sleepOverlay'?'Switch sleep signals between aligned rows and color-identified overlaid axes.':
      option==='stepsHistogram'?'Switch cumulative steps to hourly step increments.':
      option==='aggregation'?'Switch aggregate bars between the average and median of the observed daily values.':
      'Switch km/h and min/km. zero speed has no finite pace.';
    button.addEventListener('click',()=>changeGarminOption(option,option==='aggregation'?(graphOptions(id).aggregation==='Average'?'Median':'Average'):!graphOptions(id)[option],null,id));
    garminButtons.push({button,option,key,id});settings.appendChild(button);
  }
}
function stressColor(v) {return v<=25?'#42a5f5':v<=50?'#ffb74d':v<=75?'#ff8a3d':'#ef5350';}
function lowPass(xs,ys,tau=garminOptions.stressTau) {
  let previous=null,average=null;
  return ys.map((v,i)=>{
    const x=xs[i];if(!Number.isFinite(v)||!Number.isFinite(x)){previous=null;average=null;return null;}
    const dt=previous===null?null:x-previous;
    average=dt===null||dt<=0||dt>5?v:average+(1-Math.exp(-dt/tau))*(v-average);
    previous=x;return average;
  });
}
function customLayerOptions(layout,dataset){
  const options=displayOptions(layout);if(layout.meta?.kind!=='custom')return options;
  const state=customState(layout.meta.custom_id),field=customFields.find(f=>state.selected.has(f.id)&&f.dataset===dataset),own=state.fieldOptions[field?.id] || {};
  return {...options,aggregation:own.aggregation || 'Average',stressLine:own.style!=='Bars' || own.smooth===true};
}
function transformGarmin(view,index) {
  const panel=view.layout.meta?.dataset,options=customLayerOptions(view.layout,'g_sleep');
  const stressBars=()=>{const o=customLayerOptions(view.layout,'g_stress');return (panel==='g_stress' || view.layout.meta?.kind==='custom') && !o.stressSmooth && !o.stressLine;};
  view.data=view.data.filter(t=>!t.meta?.sleep_variant || (t.meta.sleep_variant===(options.sleepDistribution?'hourly':'stages') && (!t.meta.aggregation || t.meta.aggregation===options.aggregation)));
  if(view.layout.meta?.display_mode==='Median + band' && !dateCycled){
    const sleepAxis=panel==='g_sleep'?view.layout.yaxis:index===0 && currentOverlay==='Garmin · Sleep'?view.layout.yaxis2:null;
    if(sleepAxis){sleepAxis.range=[0,options.sleepDistribution?1:100];sleepAxis.autorange=false;
      sleepAxis.title={...sleepAxis.title,text:options.sleepDistribution?options.aggregation+' sleep (hours)' :'Stage composition (%)'};}
    for(const ref of new Set(view.data.filter(t=>t.meta?.sleep_variant).map(t=>t.yaxis || 'y'))){
      const axis=view.layout['yaxis'+ref.slice(1)];
      const exclusive=view.data.filter(t=>(t.yaxis || 'y')===ref && !t.meta?.legend_proxy).every(t=>t.meta?.dataset==='g_sleep');
      if(axis && exclusive){axis.range=[0,options.sleepDistribution?1:100];axis.autorange=false;
        axis.title={...axis.title,text:options.sleepDistribution?options.aggregation+' sleep (hours)' :'Stage composition (%)'};}
    }
  }
  if(panel==='g_steps'){
    view.data=view.data.filter(t=>options.stepsHistogram?t.meta?.dataset==='g_steps':t.meta?.dataset==='g_steps_cumulative');
    view.layout.title.text=view.layout.title.text.replace(/^.*? · /,(options.stepsHistogram?'Hourly steps':'Cumulative steps')+' · ');
  }
  view.data=view.data.filter(t=>{
    if(t.meta?.dataset!=='g_steps')return true;
    if(t.meta.aggregation && t.meta.aggregation!==customLayerOptions(view.layout,'g_steps').aggregation)return false;
    t.visible=true;return true;
  });
  view.data=view.data.filter(t=>!(t.meta?.kind==='garmin_band' && (t.meta.dataset==='g_sleep_restless' || (t.meta.dataset==='g_stress' && stressBars()))));
  for(const t of view.data) {
    const activity=activityOptions(t.meta?.dataset,options);
    if(activitySignals.includes(t.meta?.dataset) && activity.smooth && t.meta.kind!=='garmin_band'){
      if(t.meta.summary)for(const q of ['p10','p90'])t.meta.summary[q]=lowPass(t.x,t.meta.summary[q],activity.tauSeconds/60);
      t.y=lowPass(t.x,t.y,activity.tauSeconds/60);t.meta.label+=' · '+smoothingLabel(activity.tauSeconds)+' low-pass';
    }
    if(t.meta?.dataset==='g_workout_speed' && ['km/h','mph'].includes(t.meta.unit)) {
      const factor=t.meta.unit==='mph'?1.609344:1;
      if(t.meta.summary){const convert=values=>values.map(v=>!Number.isFinite(v)?null:options.pace?(v>0?60/(v*factor):null):v*factor);const lo=convert(t.meta.summary.p10),hi=convert(t.meta.summary.p90);t.meta.summary.p10=options.pace?hi:lo;t.meta.summary.p90=options.pace?lo:hi;}
      t.y=t.y.map(v=>!Number.isFinite(v)?null:options.pace?(v>0?60/(v*factor):null):v*factor);
      t.meta.unit=options.pace?'min/km':'km/h';if(t.meta.kind!=='garmin_band'){t.meta.label=options.pace?'Activity pace':'Activity speed';t.name=t.meta.label;}
      const axis=view.layout['yaxis'+(t.yaxis || 'y').slice(1)];
      if(axis){axis.title={...axis.title,text:t.meta.unit};axis.autorange=options.pace?'reversed':true;axis.rangemode='normal';delete axis.range;}
    }
    const key=t.meta?.dataset;
    if((key==='g_sleep_restless' || key==='g_stress' && stressBars()) && t.meta?.kind==='median' && t.meta.average) {
      const aggregation=customLayerOptions(view.layout,key).aggregation;
      t.y=t.meta[aggregation==='Average'?'average':'median'];
      t.meta.label=aggregation+' '+(key==='g_stress'?'stress':'restless moments');t.name=t.meta.label;
    }
    if(key==='g_sleep_restless' && t.meta.kind!=='garmin_band')makeGarminBar(t,'#ef5350',t.meta.kind==='median'?5:1);
    if(key!=='g_stress' || t.meta.kind==='garmin_band')continue;
    if(options.stressSmooth){if(t.meta.summary)for(const q of ['p10','p90'])t.meta.summary[q]=lowPass(t.x,t.meta.summary[q],options.stressTau);t.y=lowPass(t.x,t.y,options.stressTau);if(t.meta.label)t.meta.label+=' · '+options.stressTau+'-min low-pass';}
    t.marker={...t.marker,color:t.y.map(v=>Number.isFinite(v)?stressColor(v):'#888'),size:4};
    if(stressBars() && t.meta?.kind!=='garmin_band')makeGarminBar(t,t.marker.color,t.meta.kind==='median'?5:(view.layout.meta?.display_mode==='Multiple days' && selectedDays.length>7)?5:1);

  }
  if(panel==='g_workout_speed' && options.pace && ['Metric','Statute'].includes(navigation?.garmin_units))view.layout.title.text=view.layout.title.text.replace('Activity speed','Activity pace');
  // Plotly has one color per line. Split contiguous segments at stress-category changes.
  const extra=[];
  for(const t of view.data.filter(t=>t.meta?.dataset==='g_stress' && t.meta.kind!=='garmin_band' && t.type!=='bar')){
    const groups=new Map();
    for(let i=1;i<t.y.length;i++){
      if(![t.x[i-1],t.x[i],t.y[i-1],t.y[i]].every(Number.isFinite))continue;
      const color=stressColor((t.y[i-1]+t.y[i])/2),g=groups.get(color)||{x:[],y:[]};
      g.x.push(t.x[i-1],t.x[i],null);g.y.push(t.y[i-1],t.y[i],null);groups.set(color,g);
    }
    t.mode='markers';t.marker={...t.marker,size:3};
    for(const [color,g] of groups)extra.push({type:'scatter',x:g.x,y:g.y,xaxis:t.xaxis,yaxis:t.yaxis,
      mode:'lines',line:{color,width:2},name:t.name,showlegend:false,hoverinfo:'skip',
      meta:{kind:'stress_colored_line',date:t.meta.date}});
  }
  view.data.push(...extra);
}
function makeGarminBar(t,color,bin) {
  t.type='bar';t.marker={color,line:{width:.5,color}};t.width=bin*1.3;
  delete t.mode;delete t.line;delete t.fill;delete t.fillcolor;delete t.connectgaps;
}
async function changeGarminOption(option,value,dataset=null,id=null) {
  if(!ready)return;
  return enqueue(async()=>{
    syncing=true;clearHover();const options=graphOptions(id),previous=options[option];
    try{
      options[option]=typeof value==='function'?value():value;
      if(id)garminOptions[option]=option==='activity'?{...garminOptions.activity,...JSON.parse(JSON.stringify(options[option]))}:JSON.parse(JSON.stringify(options[option]));
      else if(option!=='activityShading')for(const state of panelStates.values())state.garmin[option]=JSON.parse(JSON.stringify(options[option]));
      controls();
      const key=dataset || (option.startsWith('stress')?'g_stress':option==='stepsHistogram'?'g_steps':null);
      await redrawLocal(id?(spec)=>spec.layout.meta?.panel_id===id:key?(spec,i)=>spec.layout.meta?.kind!=='custom' && (i===0 || spec.data.some(t=>t.meta?.dataset===key)):null);
    }
    catch(error){options[option]=previous;card.textContent='Could not change Garmin display.';}
    finally{syncing=false;controls();}
  });
}
function sleepDimensions(dateCount,detailCount,overlay=false) {
  const dayHeight=navigation?.sleep_day_height || 28;
  const stage=Math.max(100,dateCount*dayHeight),row=65,chrome=90;
  return {stage,row,chrome,height:Math.max(210,stage+(overlay?0:detailCount*row)+chrome)};
}
function composeSleep(view) {
  if(view.layout.meta?.dataset!=='g_sleep')return;
  delete view.layout.meta.automation_axis;delete view.layout.meta.automation_scale;
  const options=displayOptions(view.layout);
  const enabled=options.sleepFields.filter(k=>(view.layout.meta.sleep_fields || []).includes(k) &&
    view.data.some(t=>t.meta?.dataset===k && t.y?.some(Number.isFinite)));
  view.data=view.data.filter(t=>!t.meta?.sleep_overlay || enabled.includes(t.meta.dataset));
  const dates=[...new Set(view.data.filter(t=>t.meta?.kind==='garmin_sleep').map(t=>t.meta.date))];
  const dayHeight=navigation?.sleep_day_height || 28;
  const size=sleepDimensions(dates.length,enabled.length,options.sleepOverlay);
  const stageHeight=size.stage,total=stageHeight+enabled.length*size.row;
  view.layout.height=size.height;
  view.layout.margin={...view.layout.margin,t:30,b:48};
  view.layout.yaxis.title={text:dates.length?'Stage':options.sleepDistribution?'h/h':'%',font:{size:11},standoff:3};
  view.layout.annotations=(view.layout.annotations || []).filter(a=>!a.name?.startsWith('Sleep metric | '));
  for(const name of Object.keys(view.layout))if(/^yaxis[0-9]+$/.test(name))delete view.layout[name];
  view.layout.meta.sleep_details=enabled.length>0;
  if(options.sleepOverlay && enabled.length) {
    view.layout.yaxis.domain=[0,1];view.layout.xaxis.anchor='y';
    const units=[...new Set(enabled.map(key=>view.data.find(t=>t.meta?.dataset===key)?.meta.unit || ''))];
    customAxisLayout(view.layout,units.length+1);
    Object.assign(view.layout.yaxis,customAxisPosition(0));
    units.forEach((unit,i)=>{
      const keys=enabled.filter(key=>(view.data.find(t=>t.meta?.dataset===key)?.meta.unit || '')===unit);
      const first=view.data.find(t=>t.meta?.dataset===keys[0] && t.meta.kind!=='garmin_band');
      const color=first?.line?.color || first?.marker?.color || '#90a4ae';
      const axis=coloredAxis(keys.map(key=>sleepFields[key]).join(' / ')+' ('+unit+')',color,i+1);
      Object.assign(axis,{showgrid:false,rangemode:keys.includes('g_sleep_restless')?'tozero':'normal'});
      view.layout['yaxis'+(i+2)]=axis;
      for(const t of view.data.filter(t=>keys.includes(t.meta?.dataset))){t.yaxis='y'+(i+2);t.visible=true;}
    });
    // Keep stages legible while optional signals occupy the same plot area.
    for(const t of view.data.filter(t=>t.meta?.dataset==='g_sleep'))t.opacity=.55;
  } else {
    view.layout.yaxis.domain=[enabled.length*size.row/total,1];
    view.layout.xaxis.anchor=enabled.length?'y'+(enabled.length+1):'y';
    enabled.forEach((key,i)=>{
      const axis='y'+(i+2),upper=(enabled.length-i)*size.row/total;
      const unit=view.data.find(t=>t.meta?.dataset===key)?.meta.unit || '';
      view.layout['yaxis'+(i+2)]={domain:[Math.max(0,upper-(size.row-5)/total),upper-18/total],title:{text:unit,font:{size:10},standoff:3},
        tickfont:{size:10},nticks:3,showgrid:true,automargin:true,rangemode:key==='g_sleep_restless'?'tozero':'normal',autorange:true};
      view.layout.annotations.push({name:'Sleep metric | '+key,text:sleepFields[key],xref:'x domain',yref:'paper',x:0,y:upper-4/total,
        xanchor:'left',yanchor:'top',showarrow:false,font:{size:10}});
      for(const t of view.data.filter(t=>t.meta?.dataset===key)){t.yaxis=axis;t.visible=true;}
    });
  }
  for(const t of view.data.filter(t=>t.meta?.kind==='garmin_sleep'))t.line.width=dates.length<=1?72:dayHeight*.78;
}
function garminControlState() {
  for(const {button,option,key,id} of garminButtons){
    button.setAttribute('aria-pressed',String(option==='aggregation'?graphOptions(id).aggregation==='Average':graphOptions(id)[option]));
    button.disabled=!ready || syncing || (option==='aggregation' && dateCycled) || (key==='g_workout_speed' && !['Metric','Statute'].includes(navigation?.garmin_units));
    
    if(option==='sleepOverlay')button.textContent='Sleep: '+(graphOptions(id).sleepOverlay?'Overlay':'Underneath');
    if(option==='sleepDistribution'){button.hidden=false;button.disabled ||= dateCycled || panelStates.get(id)?.mode!=='Median + band' || selectedDays.length<2;}
    if(option==='sleepDistribution')button.textContent=graphOptions(id).sleepDistribution?'Sleep: hourly distribution':'Sleep: stage composition';
    if(option==='aggregation'){
      button.textContent=(key==='g_sleep'?'Sleep bars':key==='g_stress'?'Stress bars':'Step bars')+': '+graphOptions(id).aggregation;
      button.hidden=selectedDays.length<2 || dateCycled || panelStates.get(id)?.mode!=='Median + band';
      if(key==='g_stress' && (graphOptions(id).stressSmooth || graphOptions(id).stressLine))button.hidden=true;
      if(key==='g_sleep' && !graphOptions(id).sleepDistribution && !graphOptions(id).sleepFields.includes('g_sleep_restless'))button.hidden=true;
      if(key==='g_sleep' && !graphOptions(id).sleepDistribution)button.textContent='Restless bars: '+graphOptions(id).aggregation;
      if(key==='g_steps' && !graphOptions(id).stepsHistogram)button.hidden=true;
      if(key==='g_sleep'){button.hidden=false;button.disabled ||= selectedDays.length<2 || dateCycled || panelStates.get(id)?.mode!=='Median + band';}
    }
  }
  for(const {slider,value,id} of stressSliders){if(!slider.editing){slider.value=String(graphOptions(id).stressTau);value.textContent='Smoothing: '+smoothingLabel(graphOptions(id).stressTau*60);}slider.disabled=!ready || !graphOptions(id).stressSmooth;}
  for(const {button,key,id} of activityButtons){button.disabled=!ready || syncing;button.setAttribute('aria-pressed',String(activityOptions(key,graphOptions(id)).smooth));}
  for(const {slider,value,key,id} of activitySliders){const opts=activityOptions(key,graphOptions(id));setSmoothingValue(slider,opts.tauSeconds);slider.disabled=!ready || !opts.smooth;if(!slider.editing)value.textContent='Smoothing: '+smoothingLabel(opts.tauSeconds);}
  for(const {slider,value,key,caption,peak,id} of activityFloors){const opts=activityOptions(key,graphOptions(id));slider.max=String(Math.max(Number(slider.max),peak,opts.lower));slider.value=String(opts.lower);slider.disabled=!ready || syncing;value.textContent=caption(opts.lower);}
  for(const {button,field,available,id} of sleepButtons){button.disabled=!ready || syncing || !available;button.setAttribute('aria-pressed',String(graphOptions(id).sleepFields.includes(field)));}
}

// One rescaling policy for workout panels, profile overlays and custom graphs.
function workoutAxisUpdates(data,layout,range) {
  const result={},options=displayOptions(layout);
  if(layout.meta?.kind==='custom' && customState(layout.meta.custom_id).sameScale)return result;
  if(layout.yaxis2 && (layout.meta?.profile_copy?layout.meta.profile_same_scale:sameScale) && !layout.meta?.dataset && layout.meta?.kind!=='custom')return result;
  const axes=[...new Set(data.filter(t=>t.meta?.dataset?.startsWith('g_workout_') && t.visible!==false && t.visible!=='legendonly').map(t=>t.yaxis || 'y'))];
  for(const name of axes) {
    const key='yaxis'+name.slice(1),values=[];
    for(const t of data.filter(t=>(t.yaxis || 'y')===name && t.visible!==false && t.visible!=='legendonly')){
      (t.y || []).forEach((v,i)=>{if(Number.isFinite(v) && Number.isFinite(t.x?.[i]) && (!range || t.x[i]>=range[0] && t.x[i]<=range[1]))values.push(v);});
    }
    if(!values.length)continue;
    const datasets=[...new Set(data.filter(t=>(t.yaxis || 'y')===name && t.visible!==false).map(t=>t.meta?.dataset))];
    const dataset=datasets.length===1?datasets[0]:null;
    const lower=activityFloorSignals.includes(dataset)?activityOptions(dataset,options).lower:0;
    const reverse=options.pace && data.some(t=>(t.yaxis || 'y')===name && t.meta?.dataset==='g_workout_speed');
    const limit=lower>0?(reverse?60/lower:lower):null;
    const included=limit===null?values:values.filter(v=>reverse?v<=limit:v>=limit);
    let low=Infinity,high=-Infinity;for(const v of included){low=Math.min(low,v);high=Math.max(high,v);}
    if(!included.length){low=limit;high=limit;}
    const pad=high>low?.06*(high-low):Math.max(.5,Math.abs(high)*.03);
    result[key+'.range']=reverse?[limit ?? high+pad,Math.min(low-pad,(limit ?? high)-.01)]:[limit ?? low-pad,Math.max(high+pad,(limit ?? low)+.01)];
    result[key+'.autorange']=false;result[key+'.rangemode']='normal';
  }
  if(layout.meta?.kind==='custom') {
    const view={data,layout:JSON.parse(JSON.stringify(layout))};
    if(range)view.layout.xaxis.range=range.slice();
    for(const [key,value] of Object.entries(result)){const [axis,field]=key.split('.');view.layout[axis][field]=value;}
    applyCustomRanges(view);
    const state=customState(layout.meta.custom_id);
    for(const [axis,key] of Object.entries(layout.meta.custom_axes || {}))if(state.axisRanges[key]?.some(v=>v!==null) || customFields.some(f=>state.selected.has(f.id) && customAxisKey(state,customDisplayField(f,state))===key && state.fieldOptions[f.id]?.visualOffset)){
      result[axis+'.range']=view.layout[axis].range;result[axis+'.autorange']=false;
    }
  }
  return result;
}
function workoutAxes(view,range=view.layout.xaxis.range) {
  for(const [key,value] of Object.entries(workoutAxisUpdates(view.data,view.layout,range))){const [axis,field]=key.split('.');view.layout[axis][field]=value;}
  applyCustomRanges(view);
}
let activitySelect,fitActivityButton,fullDayButton;
function setupActivityControls() {
  const parent=document.getElementById('expand').parentElement || document.getElementById('toolbar-left');
  const top=document.getElementById('top-graph-controls');
  const bar=top?controlAreas(top).settings:parent?controlAreas(parent).settings:null;
  if(!bar || !['Metric','Statute'].includes(navigation?.garmin_units) && !(navigation?.activity_bands || []).length)return;
  const group=settingsGroup(bar,'Activity');

  activitySelect=document.createElement('select');activitySelect.setAttribute('aria-label','Recorded activity');group.appendChild(activitySelect);
  fitActivityButton=document.createElement('button');fitActivityButton.textContent='Fit time axis to activity';fitActivityButton.type='button';group.appendChild(fitActivityButton);
  fullDayButton=document.createElement('button');fullDayButton.textContent='Full day';fullDayButton.type='button';group.appendChild(fullDayButton);
  fitActivityButton.addEventListener('click',async()=>{
    if(!ready || syncing)return;
    const band=(navigation.activity_bands || []).find(s=>s.name+'|'+s.x0===activitySelect.value);if(!band)return;
    // Fit the time-of-day window; never replace aggregate traces with a single day.
    await enqueue(()=>setTimeRange([Math.max(0,band.x0-5),Math.min(1440,band.x1+5)]));
  });
  fullDayButton.addEventListener('click',()=>{if(ready && !syncing)return enqueue(()=>setTimeRange([0,1440]));});
}
function activityControlState() {
  if(!activitySelect)return;
  const previous=activitySelect.value;activitySelect.replaceChildren();
  const clock=m=>String(Math.floor(m/60)).padStart(2,'0')+':'+String(Math.floor(m%60)).padStart(2,'0');
  const bands=(navigation.activity_bands || []).filter(s=>selectedDays.includes(s.name.split(' | ')[1]));
  for(const s of bands){
    const option=document.createElement('option');option.value=s.name+'|'+s.x0;
    option.textContent=s.name.split(' | ').slice(1,3).join(' · ')+' · '+clock(s.x0)+'–'+clock(s.x1);activitySelect.appendChild(option);
  }
  if(!bands.length){const option=document.createElement('option');option.value='';option.textContent='No recorded activities for selected dates';activitySelect.appendChild(option);}
  activitySelect.value=Array.from(activitySelect.children).some(o=>o.value===previous)?previous:(activitySelect.children[0]?.value || '');
  activitySelect.disabled=!ready || syncing || !bands.length;
  fitActivityButton.title=bands.length?'Zoom all time graphs to the selected recorded activity':'Reload Garmin with activity summaries or activity FIT files containing start/end times.';
  fitActivityButton.disabled=activitySelect.disabled;fullDayButton.disabled=!ready || syncing;
}
async function setTimeRange(range) {
  syncing=true;controls();clearHover();
  try{await Promise.all(graphs.filter(g=>g._fullLayout && !g.layout.meta?.non_time).map(g=>{
    const local=panelTimeRange(graphs.indexOf(g),range),updates={};
    for(const key of Object.keys(g.layout).filter(k=>/^xaxis\d*$/.test(k)&&g._fullLayout[k])){
      updates[key+'.range']=local;updates[key+'.autorange']=false;
      if(g.layout.meta?.kind!=='insight')for(const [option,value] of Object.entries(timeAxisTicks(local,g._fullLayout[key]._length)))updates[key+'.'+option]=value;
    }
    for(const [key,value] of Object.entries(workoutAxisUpdates(g.data,g.layout,local)))if(g._fullLayout[key.split('.')[0]])updates[key]=value;
    return (Object.keys(updates).length?Plotly.relayout(g,updates):Promise.resolve()).then(()=>reflowProfileLabels(g));
  }));}
  finally{syncing=false;controls();}
}

function activityShadingControl(bar) {
  return eventScopeControl(bar,'activity','Shading');
}
function applyActivityShading(view) {
  view.layout.shapes=(view.layout.shapes || []).filter(s=>!s.name?.startsWith('Activity | '));
  if(!eventAllowed(view,'activity'))return;
  const aggregate=!dateCycled && view.layout.meta?.display_mode==='Median + band';
  const dated=aggregate || selectedDays.length>1;
  for(const band of navigation?.activity_bands || []){
    const day=band.name.split(' | ')[1];if(!selectedDays.includes(day))continue;
    view.layout.shapes.push({...band,label:{...band.label,text:(dated?day+' · ':'')+(band.label?.text || band.name.split(' | ')[2])}});
  }
  if(dated){
    // Identical intervals from different dates must not stack unreadable labels.
    // Keep every recorded region/color; only combine their coincident labels.
    const groups=new Map();
    for(const band of view.layout.shapes.filter(s=>s.name?.startsWith('Activity | '))){
      const key=band.x0+'|'+band.x1,group=groups.get(key) || [];group.push(band);groups.set(key,group);
    }
    for(const group of groups.values())if(group.length>1){
      const dates=new Set(group.map(s=>s.name.split(' | ')[1])),types=[...new Set(group.map(s=>s.label.text.replace(/^\d{4}-\d{2}-\d{2} · /,'')))];
      group[0].label.text=types.join(' / ')+' · '+dates.size+(dates.size===1?' date':' dates');
      for(const band of group.slice(1))band.label.text='';
    }
  }
}

function displayOptions(layout) {
  return layout.meta?.kind==='custom'?customState(layout.meta.custom_id).garmin:graphOptions(layout.meta?.panel_id);
}
// Open, distinct control boxes: settings left, datasets/annotations right.
function controlAreas(bar) {
  if(bar.graphAreas)return bar.graphAreas;
  bar.className+=' graph-control-row';
  const content=document.createElement('div');content.className='graph-content';
  const label=document.createElement('span');label.className='control-label';label.textContent='Overlays';content.appendChild(label);
  const settings=document.createElement('div');settings.className='graph-settings';
  const title=document.createElement('span');title.className='control-label';title.textContent='Settings';settings.appendChild(title);
  const body=document.createElement('div');body.className='settings-body';settings.appendChild(body);
  const axis=document.createElement('div');axis.className='axis-controls';
  const actions=document.createElement('div');actions.className='graph-actions';const caption=document.createElement('span');caption.className='control-label';caption.textContent='Graph actions';actions.appendChild(caption);
  bar.appendChild(actions);bar.appendChild(settings);bar.appendChild(content);
  return bar.graphAreas={content,settings:body,axis,actions};
}


function settingsGroup(bar,title) {
  const group=document.createElement('div');group.className='settings-group';
  const label=document.createElement('span');label.className='settings-group-title';label.textContent=title;group.appendChild(label);bar.appendChild(group);return group;
}
// One independent scope per event type, shared by daily/aggregate/report rendering.
const eventScopes={site:'glucose',sensor:'glucose',profiles:'off',percentage:'off',automation:'off',activity:'all'};
const eventSelects=[];
function eventAllowed(view,key){
  const own=panelStates.get(view.layout.meta?.panel_id)?.events?.[key];
  const scope=own==='show'?'all':own==='hide'?'off':eventScopes[key];
  if(scope==='off' || view.layout.meta?.non_time)return false;
  const glucose=view.layout.meta?.dataset==='glucose' || (view.data || []).some(t=>t.meta?.kind==='glucose' || t.meta?.dataset==='glucose');
  return scope==='all' || glucose;
}
function restoreEventScopes(s){
  for(const key of Object.keys(eventScopes)){
    const legacy=key==='activity'?(s.garmin?.activityShading===false?'off':'all'):key==='automation'?(s.automationScope || 'off'):
      ['profiles','percentage'].includes(key)?(s.eventOptions?.[key]?'all':'off'):
      s.eventOptions?.[key]===false?'off':(s.changeScope || 'glucose');
    const value=s.eventScopes?.[key] ?? legacy;
    if(['glucose','all','off'].includes(value))eventScopes[key]=value;
  }
}
function eventScopeControl(parent,key,text){
  const label=document.createElement('label');label.textContent=text;
  const select=document.createElement('select');select.setAttribute('aria-label',text+' display');
  for(const [value,caption] of [['off','Off'],['glucose','Glucose only'],['all','All time graphs']]){
    const option=document.createElement('option');option.value=value;option.textContent=caption;select.appendChild(option);
  }
  label.title=key==='automation'?'Only loaded CarePortal notes starting with Automation: are shown. Median views show actual dated events by time of day, not an average execution.':
    'Recorded events by time of day. Elapsed-time insights and other non-time plots are excluded.';
  select.addEventListener('change',()=>changeEventOption(key,select.value));label.appendChild(select);parent.appendChild(label);
  eventSelects.push({key,select});return select;
}
function setupChangeControls() {
  const top=document.getElementById('top-graph-controls');
  const bar=top?controlAreas(top).settings:controlAreas(document.getElementById('toolbar-left') || document.getElementById('viewer')).settings;
  const details=document.createElement('details');details.className='graph-events';const heading=document.createElement('summary');heading.textContent='Global event defaults';details.appendChild(heading);bar.appendChild(details);
  const group=settingsGroup(details,'Events');
  for(const [key,text] of [['activity','Activity shading'],['site','Site changes'],['sensor','Sensor changes'],['profiles','Profile switches'],['percentage','Profile % shading'],['automation','Automation notes']])eventScopeControl(group,key,text);
}
function eventControlState(){
  for(const {key,select} of eventSelects){
    select.value=eventScopes[key];select.disabled=!ready || syncing || (['profiles','percentage'].includes(key) && !navigation?.profile_events?.length);
    if(['profiles','percentage'].includes(key) && !navigation?.profile_events?.length)select.title='No effective profile records loaded. Refresh Nightscout to check availability.';
  }
}
function changeEventText(event,dated=selectedDays.length>1){
  const clock=String(Math.floor(event.minute/60)).padStart(2,'0')+':'+String(Math.floor(event.minute%60)).padStart(2,'0');
  return (dated?event.date+' · ':'')+(event.label==='Site Change'?'Site':'Sensor')+' '+clock;
}
function applyChangeEvents(view,index) {
  view.layout.shapes=(view.layout.shapes || []).filter(s=>!s.name?.startsWith('Change | '));
  view.layout.annotations=(view.layout.annotations || []).filter(s=>!s.name?.startsWith('Change | '));
  if(view.layout.meta?.non_time)return;
  for(const event of navigation?.change_events || []){
    if(!selectedDays.includes(event.date))continue;
    const site=event.label==='Site Change',color=site?'#557dce':'#b45bb5';
    if(!eventAllowed(view,site?'site':'sensor'))continue;
    const text=changeEventText(event);
    const name='Change | '+event.date+' | '+event.label+' | '+event.minute;
    view.layout.shapes.push({type:'line',name,
      xref:'x',yref:'paper',x0:event.minute,x1:event.minute,y0:0,y1:1,line:{color,width:1.5,dash:'dot'}});
    view.layout.annotations.push({name,text,xref:'x',yref:'paper',x:event.minute,y:site?0.94:0.06,
      showarrow:false,xanchor:'left',yanchor:site?'top':'bottom',xshift:4,
      bgcolor:view.layout.plot_bgcolor || view.layout.paper_bgcolor || 'rgba(255,255,255,.85)',font:{size:10,color}});
  }
}

async function changeEventOption(key,value){
  if(!ready || syncing)return;
  return enqueue(async()=>{
    const previous=eventScopes[key];syncing=true;clearHover();
    try{eventScopes[key]=value;controls();await redrawLocal();}
    catch(error){eventScopes[key]=previous;card.textContent='Could not update event display.';}
    finally{syncing=false;controls();}
  });
}
function profileLineStyle(name){
  // Stable by base name, including unseen profiles; percentages share its line style.
  const dashes=['dash','longdash','dashdot','longdashdot'];
  const names=[...new Set((navigation?.profile_events || []).map(e=>e.name))].sort();
  return {color:'#a173cb',width:1.35,dash:dashes[names.indexOf(name)%dashes.length]};
}
function profileEventText(event){return event.name+(Number.isFinite(event.percentage)?' · '+event.percentage+'%':'');}
function applyProfileEvents(view) {
  view.layout.shapes=(view.layout.shapes || []).filter(s=>!s.name?.startsWith('Effective | ') && !s.name?.startsWith('Profile · '));
  view.layout.annotations=(view.layout.annotations || []).filter(s=>!s.name?.startsWith('Effective | '));
  if(view.layout.meta?.non_time)return;
  const seen=new Set(),labelsByEvent=new Map();
  view.data=(view.data || []).filter(t=>t.meta?.kind!=='profile_event');
  const aux=1+Math.max(1,...Object.keys(view.layout).filter(k=>/^yaxis\d*$/.test(k)).map(k=>Number(k.slice(5)) || 1));
  const eventAxis='y'+aux;
  const events=(navigation?.profile_events || []).filter(e=>selectedDays.includes(e.date)).sort((a,b)=>a.minute-b.minute);
  view.layout.meta={...view.layout.meta,profile_label_levels:0,percentage_max:100};
  for(const event of navigation?.profile_events || []){
    const p=event.percentage,text=profileEventText(event);
    const name='Effective | '+event.date+' | '+event.minute+' | '+text;
    if(eventAllowed(view,'percentage') && Number.isFinite(p) && p!==100){
      for(const part of event.intervals || [])if(selectedDays.includes(part.date)){
        view.layout.meta.percentage_max=Math.max(view.layout.meta.percentage_max,p);
        view.layout.shapes.push({type:'rect',name:name+' | '+part.date,xref:'x',yref:'paper',x0:part.start,x1:part.end,y0:0,y1:Math.max(0,p/100),line:{width:0},fillcolor:'rgba(153,102,204,.14)',layer:'below'});
      }
    }
  }
  // Aggregate views retain actual dated events as context, never average switches.
  if(!eventAllowed(view,'profiles')){profileEventLayout(view.layout);return;}
  for(const event of events){
    const p=event.percentage,text=profileEventText(event);
    const name='Effective | '+event.date+' | '+event.minute+' | '+text,line=profileLineStyle(event.name);
    view.layout.shapes.push({type:'line',name,xref:'x',yref:'paper',x0:event.minute,x1:event.minute,y0:0,y1:1,
      line,showlegend:!seen.has(event.name),legendgroup:'profile-switch-'+event.name,legendrank:90,
      label:{text:''},...(!seen.has(event.name)?{name:'Effective | '+event.name}: {})});
    // Legend names are short base names; internal identity is retained separately.
    view.layout.shapes.at(-1).legendgroup='Profile · '+event.name;
    if(!seen.has(event.name))view.layout.shapes.at(-1).name='Profile · '+event.name;
    seen.add(event.name);
    view.layout['yaxis'+aux]={overlaying:'y',range:[0,1],autorange:false,visible:false,fixedrange:true,showgrid:false};
    view.data.push({type:'scatter',x:Array(51).fill(event.minute),y:Array.from({length:51},(_,i)=>i/50),yaxis:eventAxis,mode:'lines',line:{color:'rgba(161,115,203,.01)',width:10},showlegend:false,
      meta:{kind:'profile_event',label:event.name,percentage:p,date:event.date,legend_entry:false},hovertemplate:event.name+'<extra></extra>'});
    const key=event.minute+'|'+text,existing=labelsByEvent.get(key);
    if(existing)existing.hovertext+='; '+event.date;
    else{
      const label={name,xref:'x',yref:'paper',x:event.minute,y:-.001,text,hovertext:event.date+' · '+text,
        showarrow:false,yanchor:'top',font:{size:navigation?.report_render?.compact?9:10,color:line.color}};
      view.layout.annotations.push(label);labelsByEvent.set(key,label);
    }
  }
  if(seen.size)view.layout.showlegend=true;
  profileEventLayout(view.layout);
}

function profileEventLayout(layout,plotWidth=null){
  if(layout.meta?.kind==='compact'){compactLayout(layout,plotWidth);return;}
  // Recompute at the final plot width, including resize, expanded view and PDF.
  // Compare full text boxes rather than just the distance between event times.
  const range=layout.xaxis?.range || [0,1440],span=range[1]-range[0];
  const width=Math.max(100,plotWidth || (layout.width || 1000)-(layout.margin?.l || 62)-(layout.margin?.r || 62));
  const dense=navigation?.report_render?.compact,rowHeight=dense?12:18;
  const labels=(layout.annotations || []).filter(a=>a.name?.startsWith('Effective | ') && a.y<0).sort((a,b)=>a.x-b.x);
  const lanes=[];
  for(const label of labels){
    label.visible=label.x>=range[0] && label.x<=range[1];if(!label.visible)continue;
    const size=Math.min(width,Math.max(label.text.length*(label.font?.size || 10)*.65,36)+14);
    const center=(label.x-range[0])*width/span;
    const left=Math.max(0,Math.min(width-size,center-size/2));
    let lane=lanes.findIndex(end=>left>=end+6);
    if(lane<0){lane=lanes.length;lanes.push(0);}
    lanes[lane]=left+size;
    label.xanchor='left';label.xshift=left-center+7;label.yshift=-(dense?18:28)-lane*rowHeight;
  }
  layout.meta={...layout.meta,profile_label_levels:lanes.length};
  const levels=layout.meta?.profile_label_levels || 0,overflow=Math.max(0,(layout.meta?.percentage_max || 100)/100-1);
  if(!levels && !overflow)return;
  const bottom=Math.max(layout.margin?.b || 0,levels?(dense?44:64)+Math.max(0,levels-1)*rowHeight:dense?32:62);
  const baseTop=dense?20:36;
  const room=Math.max(40,(layout.height || 350)-bottom-baseTop);
  // Above-100% shade belongs in dedicated headroom, never over the title.
  layout.margin={...layout.margin,b:bottom,t:baseTop+Math.ceil(room*overflow/(1+overflow))};
  profileEventLegendPosition(layout);
}
function profileEventLegendPosition(layout){
  if(!(layout.annotations || []).some(a=>a.name?.startsWith('Effective | ') && a.y<0))return;
  if(navigation?.report_render){layout.legend={...layout.legend,yref:'container',y:0,yanchor:'bottom'};return;}
  const height=Math.max(40,(layout.height || 350)-(layout.margin?.t || 36)-(layout.margin?.b || 65));
  const levels=layout.meta?.profile_label_levels || 1;
  const dense=navigation?.report_render?.compact;
  layout.legend={...layout.legend,y:-((dense?31:45)+Math.max(0,levels-1)*(dense?12:18))/height,yanchor:'top'};
}

async function reflowProfileLabels(div){
  if(div.layout.meta?.kind==='compact' && !div.layout.yaxis4)return;
  if(div.layout.meta?.kind!=='compact' && !(div.layout.annotations || []).some(a=>a.name?.startsWith('Effective | ') && a.y<0))return;
  const width=div._fullLayout?.xaxis?._length;
  if(!Number.isFinite(width))return;
  // Automargins and multiple axes can reduce the real plot width after layout.
  const layout=JSON.parse(JSON.stringify(div.layout));profileEventLayout(layout,width);
  if(layout.meta.kind==='compact')compactAmountLabels({data:div.data,layout},width);
  if(JSON.stringify(layout.annotations)===JSON.stringify(div.layout.annotations))return;
  const updates={annotations:layout.annotations,margin:layout.margin,legend:layout.legend,meta:layout.meta};
  if(layout.meta.kind==='compact'){
    Object.assign(updates,{height:layout.height,shapes:layout.shapes});
    // Plotly omits unused axes on days without data. Relayout of a missing
    // domain otherwise crashes inside Plotly while accessing _inputDomain.
    for(const key of ['yaxis','yaxis4'])if(div._fullLayout?.[key] && layout[key]?.domain)updates[key+'.domain']=layout[key].domain;
  }
  await Plotly.relayout(div,updates);
}

function automationReportLabels(view,events,aux,height,top){
  const range=view.layout.xaxis.range || [0,1440],span=Math.max(1,range[1]-range[0]);
  const width=Math.max(100,(view.layout.width || 1000)-(view.layout.margin?.l || 62)-(view.layout.margin?.r || 62));
  const rail=(1-top)*height,boxes=[],groups=new Map();
  const family='Arial, "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif';
  const context=document.createElement('canvas').getContext('2d');context.font='8px '+family;
  for(const e of events)if(e.minute>=range[0]&&e.minute<=range[1])groups.set(e.minute+'|'+e.label,e);
  let crowded=false;
  for(const e of [...groups.values()].sort((a,b)=>a.minute-b.minute)){
    const px=(e.minute-range[0])*width/span,py=rail*.88;
    const text=String(e.label),w=Math.ceil(context.measureText(text).width)+8;
    const p=placeGraphText(px,py,w,{width,bottom:6,top:rail-6,boxes,direction:-1,step:12,textHeight:10});
    if(!p){crowded=true;continue;}boxes.push(p.box);
    const safe=text.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const a={name:'Automation label | '+e.minute+' | '+e.label,text:safe,xref:'x',x:e.minute,font:{size:8,color:'#327b77',family},borderpad:1,bgcolor:view.layout.plot_bgcolor};
    if(p.direct)Object.assign(a,{yref:'y'+aux,y:p.cy/rail,xshift:p.cx-px,showarrow:false,xanchor:'center',yanchor:'middle'});
    else Object.assign(a,{yref:'y'+aux,y:.88,ax:p.cx-px,ay:py-p.cy,showarrow:true,arrowhead:0,arrowwidth:.5,arrowcolor:'rgba(65,140,135,.4)',standoff:3});
    view.layout.annotations.push(a);
  }
  // When a fixed-height slot is too dense, print the complete notes in a tiny time key.
  view.layout.meta.automation_print_key=crowded?[...groups.values()].map(e=>String(Math.floor(e.minute/60)).padStart(2,'0')+':'+String(Math.floor(e.minute%60)).padStart(2,'0')+' · '+e.label).join('; '):'';
}
function automationReportRail(view,events){
  const range=view.layout.xaxis.range || [0,1440],span=Math.max(1,range[1]-range[0]);
  const width=Math.max(100,(view.layout.width || 1000)-(view.layout.margin?.l || 62)-(view.layout.margin?.r || 62));
  const context=document.createElement('canvas').getContext('2d');context.font='8px Arial, "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif';
  const unique=new Map(events.filter(e=>e.minute>=range[0]&&e.minute<=range[1]).map(e=>[e.minute+'|'+e.label,e]));
  const lanes=[];
  for(const e of [...unique.values()].sort((a,b)=>a.minute-b.minute)){
    const size=Math.min(width,context.measureText(String(e.label)).width+8),center=(e.minute-range[0])*width/span;
    const left=Math.max(0,Math.min(width-size,center-size/2));
    let lane=lanes.findIndex(end=>left>=end+6);if(lane<0){lane=lanes.length;lanes.push(0);}lanes[lane]=left+size;
  }
  return Math.max(24,lanes.length*16+8);
}
function applyAutomationNotes(view,index){
  const previous=view.data.filter(t=>t.meta?.kind==='automation_note'),compact=view.layout.meta?.kind==='compact';
  const reserved=view.layout.meta?.automation_axis;
  if(previous.length || reserved!==undefined&&view.layout['yaxis'+reserved]){
    const axes=new Set(previous.map(t=>'yaxis'+t.yaxis.slice(1)));
    if(reserved!==undefined)axes.add('yaxis'+reserved);
    for(const axis of axes)delete view.layout[axis];
    const scale=view.layout.meta?.automation_scale;
    if(!compact && scale){
      for(const [key,axis] of Object.entries(view.layout))if(/^yaxis\d*$/.test(key)&&!axis.overlaying)axis.domain=axis.domain.map(v=>v/scale);
      for(const shape of view.layout.shapes || [])if(shape.yref==='paper'){shape.y0/=scale;shape.y1/=scale;}
      for(const a of view.layout.annotations || [])if(a.yref==='paper'&&a.y>=0&&a.y<=scale)a.y/=scale;
    }
  }
  delete view.layout.meta.automation_axis;delete view.layout.meta.automation_scale;
  delete view.layout.meta.automation_print_key;
  view.layout.annotations=(view.layout.annotations || []).filter(a=>!a.name?.startsWith('Automation label | '));
  if(compact){delete view.layout.meta.compact_automation;delete view.layout.meta.compact_automation_top;}
  view.data=(view.data || []).filter(t=>t.meta?.kind!=='automation_note');
  if(!eventAllowed(view,'automation'))return;
  const events=(navigation?.automation_notes || []).filter(e=>selectedDays.includes(e.date));
  if(!events.length && !(navigation?.report_render?.reserve_automation))return;
  const aux=1+Math.max(1,...Object.keys(view.layout).filter(k=>/^yaxis\d*$/.test(k)).map(k=>Number(k.slice(5)) || 1));
  // Plotly hides out-of-range marker points even with cliponaxis:false.
  // Reserve a small real axis strip above the data instead of drawing outside it.
  const printable=Boolean(navigation?.report_render),height=Math.max(40,(view.layout.height || 350)-(view.layout.margin?.t || 36)-(view.layout.margin?.b || 62));
  const top=printable?1-Math.min(.45,(navigation.report_render.consolidate_automation?12:events.length?automationReportRail(view,events):24)/height):.90;
  if(compact){view.layout.meta.compact_automation=true;view.layout.meta.compact_automation_top=top;}
  else for(const key of Object.keys(view.layout).filter(k=>/^yaxis\d*$/.test(k))){const axis=view.layout[key];if(!axis.overlaying)axis.domain=(axis.domain || [0,1]).map(v=>v*top);}
  view.layout.meta={...view.layout.meta,automation_scale:top,automation_axis:aux};
  for(const shape of view.layout.shapes || [])if(!compact && shape.yref==='paper'){shape.y0*=top;shape.y1*=top;}
  for(const annotation of view.layout.annotations || [])if(!compact && annotation.yref==='paper' && annotation.y>=0 && annotation.y<=1)annotation.y*=top;
  view.layout['yaxis'+aux]={anchor:'x',domain:[printable?top+.01:.93,1],range:[0,1],autorange:false,visible:false,fixedrange:true,showgrid:false};
  const safe=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  for(const [i,e] of events.entries())view.data.push({type:'scatter',x:[e.minute],y:[printable ? .88 : .25+(i%2)*.5],yaxis:'y'+aux,mode:'markers',cliponaxis:false,
    marker:{symbol:'diamond',size:7,color:'#44a6a1',line:{width:.7,color:view.layout.plot_bgcolor}},name:'Automation notes',legendgroup:'automation-notes',showlegend:i===0,
    meta:{kind:'automation_note',label:e.label,date:e.date,legend_entry:i===0},hovertemplate:safe(e.label)+'<extra></extra>'});
  if(printable && events.length && !navigation.report_render.consolidate_automation)automationReportLabels(view,events,aux,height,top);
  view.layout.margin={...view.layout.margin,t:Math.max(view.layout.margin?.t || 0,printable?20:44)};
  if(events.length)view.layout.showlegend=true;
}
