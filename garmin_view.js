// Display-only transforms. Source samples stay immutable in the trace bank.
const garminOptions={stressSmooth:false,stressLine:false,pace:false,stressTau:5,aggregation:"Average",stepsHistogram:false,sleepFields:[],sleepOverlay:false,sleepDistribution:true,glucoseActivities:false,activityShading:true,activity:{}};
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

function changeActivityOption(key,option,value) {
  return changeGarminOption('activity',()=>({...garminOptions.activity,[key]:{...activityOptions(key),[option]:value}}),key);
}
function smoothingControl(bar,key) {
  const label=document.createElement('label'),slider=document.createElement('input'),value=document.createElement('span');
  const stress=key==='g_stress';
  if(stress){slider.type='range';slider.min='1';slider.max='30';slider.step='1';slider.value='5';slider.style.width='160px';}
  else configureSmoothingSlider(slider,300);
  value.className='smoothing-value';
  slider.setAttribute('aria-label',(key==='g_stress'?'Stress':key.replace('g_workout_','Activity '))+' smoothing time constant in '+(stress?'minutes':'seconds'));
  slider.title=stress?'1–30 minutes; higher values smooth more.':'5 seconds–30 minutes; higher values smooth more. Gaps reset the filter.';
  slider.addEventListener('input',()=>{slider.editing=true;value.textContent='Smoothing: '+smoothingLabel(stress?Number(slider.value)*60:smoothingSeconds(slider));});
  slider.addEventListener('change',()=>{const seconds=stress?Number(slider.value)*60:smoothingSeconds(slider);slider.editing=false;return stress?changeGarminOption('stressTau',seconds/60):changeActivityOption(key,'tauSeconds',seconds);});
  label.appendChild(value);label.appendChild(slider);bar.appendChild(label);
  (key==='g_stress'?stressSliders:activitySliders).push({slider,value,key});
}
function activityGraphControls(bar,spec,axisControls) {
  const key=spec.layout.meta.dataset;
  const button=document.createElement('button');button.type='button';button.textContent='Low-pass';
  button.addEventListener('click',()=>changeActivityOption(key,'smooth',!activityOptions(key).smooth));
  bar.appendChild(button);activityButtons.push({button,key});smoothingControl(bar,key);
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
  slider.addEventListener('change',()=>changeActivityOption(key,'lower',Number(slider.value)));
  label.className='axis-floor';slider.className='axis-slider';slider.style.width='22px';slider.style.height='130px';
  label.appendChild(value);label.appendChild(slider);axisControls.appendChild(label);activityFloors.push({key,slider,value,caption,peak});
}
const sleepFields={'g_sleep_movement':'Movement','g_sleep_restless':'Restless moments','g_sleep_respiration':'Respiration','g_sleep_rhr':'Resting heart rate','g_sleep_spo2':'Pulse Ox','g_sleep_rr':'Sleep respiration','g_sleep_hrv':'Overnight HRV'};
function garminControls(bar,spec) {
  const areas=controlAreas(bar),settings=areas.settings;
  const key=spec.layout.meta?.dataset;
  const options=key==='g_stress'?[['stressSmooth','Low-pass'],['stressLine','Line']]:
    key==='g_workout_speed'?[['pace','Pace · min/km']]:[];
  if(key==='g_steps')options.push(['stepsHistogram','Histogram']);
  if(['g_steps','g_stress','g_sleep'].includes(key) && navigation?.mode!=='One day')options.push(['aggregation','Bars: Average']);
  if(key==='g_stress')smoothingControl(settings,key);
  if(activitySignals.includes(key))activityGraphControls(settings,spec,areas.axis);
  if(key==='g_sleep') {
    options.push(['sleepOverlay','Sleep: Underneath']);
    if(navigation?.mode==='Median + band')options.push(['sleepDistribution','Hourly sleep distribution']);
    const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Sleep overlays';details.appendChild(summary);
    const choices=document.createElement('div');choices.className='custom-options';details.appendChild(choices);areas.content.appendChild(details);
    for(const [field,label] of Object.entries(sleepFields)) {
      const button=document.createElement('button');button.type='button';button.textContent=label;
      const available=(spec.layout.meta.sleep_fields || []).includes(field);
      button.title=!available?'No recorded data for this signal':field==='g_sleep_rhr'?'Daily resting heart rate reference over the recorded night; not a time-resolved measurement.':field==='g_sleep_respiration'?'Monitoring respiration recorded inside sleep sessions.':field==='g_sleep_rr'?'Sleep-export respiration where present; monitoring respiration otherwise. These can match Respiration.':'Show '+label.toLowerCase()+' alongside sleep stages.';
      button.addEventListener('click',()=>changeGarminOption('sleepFields',garminOptions.sleepFields.includes(field)?garminOptions.sleepFields.filter(k=>k!==field):[...garminOptions.sleepFields,field]));
      choices.appendChild(button);sleepButtons.push({button,field,available});
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
    button.addEventListener('click',()=>changeGarminOption(option,option==='aggregation'?(garminOptions.aggregation==='Average'?'Median':'Average'):!garminOptions[option]));
    garminButtons.push({button,option,key});settings.appendChild(button);
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
function transformGarmin(view,index) {
  const panel=view.layout.meta?.dataset,options=displayOptions(view.layout);
  view.data=view.data.filter(t=>!t.meta?.sleep_variant || (t.meta.sleep_variant===(options.sleepDistribution?'hourly':'stages') && (!t.meta.aggregation || t.meta.aggregation===options.aggregation)));
  if(navigation?.mode==='Median + band' && !dateCycled){
    const sleepAxis=panel==='g_sleep'?view.layout.yaxis:index===0 && currentOverlay==='Garmin · Sleep'?view.layout.yaxis2:null;
    if(sleepAxis){sleepAxis.range=[0,options.sleepDistribution?60:100];sleepAxis.autorange=false;
      sleepAxis.title={...sleepAxis.title,text:options.sleepDistribution?options.aggregation+' sleep (min/hour)':'Stage composition (%)'};}
    for(const ref of new Set(view.data.filter(t=>t.meta?.sleep_variant).map(t=>t.yaxis || 'y'))){
      const axis=view.layout['yaxis'+ref.slice(1)];
      const exclusive=view.data.filter(t=>(t.yaxis || 'y')===ref && !t.meta?.legend_proxy).every(t=>t.meta?.dataset==='g_sleep');
      if(axis && exclusive){axis.range=[0,options.sleepDistribution?60:100];axis.autorange=false;
        axis.title={...axis.title,text:options.sleepDistribution?options.aggregation+' sleep (min/hour)':'Stage composition (%)'};}
    }
  }
  if(panel==='g_steps'){
    view.data=view.data.filter(t=>options.stepsHistogram?t.meta?.dataset==='g_steps':t.meta?.dataset==='g_steps_cumulative');
    view.layout.title.text=view.layout.title.text.replace(/^.*? · /,(options.stepsHistogram?'Hourly steps':'Cumulative steps')+' · ');
  }
  view.data=view.data.filter(t=>{
    if(t.meta?.dataset!=='g_steps')return true;
    if(t.meta.aggregation && t.meta.aggregation!==options.aggregation)return false;
    t.visible=true;return true;
  });
  view.data=view.data.filter(t=>!(t.meta?.kind==='garmin_band' && (t.meta.dataset==='g_sleep_restless' || (t.meta.dataset==='g_stress' && panel==='g_stress' && !options.stressSmooth && !options.stressLine))));
  for(const t of view.data) {
    const activity=activityOptions(t.meta?.dataset,options);
    if(activitySignals.includes(t.meta?.dataset) && activity.smooth && t.meta.kind!=='garmin_band'){
      t.y=lowPass(t.x,t.y,activity.tauSeconds/60);t.meta.label+=' · '+smoothingLabel(activity.tauSeconds)+' low-pass';
    }
    if(t.meta?.dataset==='g_workout_speed' && ['km/h','mph'].includes(t.meta.unit)) {
      const factor=t.meta.unit==='mph'?1.609344:1;
      t.y=t.y.map(v=>!Number.isFinite(v)?null:options.pace?(v>0?60/(v*factor):null):v*factor);
      t.meta.unit=options.pace?'min/km':'km/h';if(t.meta.kind!=='garmin_band'){t.meta.label=options.pace?'Activity pace':'Activity speed';t.name=t.meta.label;}
      const axis=view.layout['yaxis'+(t.yaxis || 'y').slice(1)];
      if(axis){axis.title={...axis.title,text:t.meta.unit};axis.autorange=options.pace?'reversed':true;axis.rangemode='normal';delete axis.range;}
    }
    const key=t.meta?.dataset;
    if((key==='g_sleep_restless' || key==='g_stress' && panel==='g_stress' && !options.stressSmooth && !options.stressLine) && t.meta?.kind==='median' && t.meta.average) {
      t.y=t.meta[options.aggregation==='Average'?'average':'median'];
      t.meta.label=options.aggregation+' '+(key==='g_stress'?'stress':'restless moments');t.name=t.meta.label;
    }
    if(key==='g_sleep_restless' && t.meta.kind!=='garmin_band')makeGarminBar(t,'#ef5350',t.meta.kind==='median'?5:1);
    if(key!=='g_stress' || t.meta.kind==='garmin_band')continue;
    if(options.stressSmooth){t.y=lowPass(t.x,t.y,options.stressTau);if(t.meta.label)t.meta.label+=' · '+options.stressTau+'-min low-pass';}
    t.marker={...t.marker,color:t.y.map(v=>Number.isFinite(v)?stressColor(v):'#888'),size:4};
    if(panel==='g_stress' && t.meta?.kind!=='garmin_band' && !options.stressSmooth && !options.stressLine)makeGarminBar(t,t.marker.color,t.meta.kind==='median'?5:(navigation?.mode==='Multiple days' && selectedDays.length>7)?5:1);

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
async function changeGarminOption(option,value,dataset=null) {
  if(!ready)return;
  return enqueue(async()=>{
    syncing=true;clearHover();const previous=garminOptions[option];
    try{
      garminOptions[option]=typeof value==='function'?value():value;controls();
      const key=dataset || (option.startsWith('stress')?'g_stress':option==='stepsHistogram'?'g_steps':null);
      await redrawLocal(key?(spec,i)=>spec.layout.meta?.kind!=='custom' && (i===0 || spec.data.some(t=>t.meta?.dataset===key)):null);
    }
    catch(error){garminOptions[option]=previous;card.textContent='Could not change Garmin display.';}
    finally{syncing=false;controls();}
  });
}
function composeSleep(view) {
  if(view.layout.meta?.dataset!=='g_sleep')return;
  const enabled=garminOptions.sleepFields.filter(k=>(view.layout.meta.sleep_fields || []).includes(k));
  view.data=view.data.filter(t=>!t.meta?.sleep_overlay || enabled.includes(t.meta.dataset));
  const dates=[...new Set(view.data.filter(t=>t.meta?.kind==='garmin_sleep').map(t=>t.meta.date))];
  const stageHeight=Math.max(150,dates.length*86),total=stageHeight+enabled.length*100;
  for(const name of Object.keys(view.layout))if(/^yaxis[0-9]+$/.test(name))delete view.layout[name];
  view.layout.meta.sleep_details=enabled.length>0;
  if(garminOptions.sleepOverlay && enabled.length) {
    view.layout.height=Math.max(350,stageHeight+150);view.layout.yaxis.domain=[0,1];view.layout.xaxis.anchor='y';
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
    view.layout.yaxis.domain=[enabled.length*100/total,1];view.layout.height=total+150;
    view.layout.xaxis.anchor=enabled.length?'y'+(enabled.length+1):'y';
    enabled.forEach((key,i)=>{
      const axis='y'+(i+2),upper=(enabled.length-i)*100/total;
      const unit=view.data.find(t=>t.meta?.dataset===key)?.meta.unit || '';
      view.layout['yaxis'+(i+2)]={domain:[Math.max(0,upper-85/total),upper-10/total],title:{text:sleepFields[key]+' ('+unit+')',font:{size:11}},
        tickfont:{size:11},showgrid:true,automargin:true,rangemode:key==='g_sleep_restless'?'tozero':'normal',autorange:true};
      for(const t of view.data.filter(t=>t.meta?.dataset===key)){t.yaxis=axis;t.visible=true;}
    });
  }
  for(const t of view.data.filter(t=>t.meta?.kind==='garmin_sleep'))t.line.width=dates.length<=1?120:86;
}
function garminControlState() {
  for(const {button,option,key} of garminButtons){
    button.setAttribute('aria-pressed',String(option==='aggregation'?garminOptions.aggregation==='Average':garminOptions[option]));
    button.disabled=!ready || syncing || (option==='aggregation' && dateCycled) || (key==='g_workout_speed' && !['Metric','Statute'].includes(navigation?.garmin_units));
    if(option==='activityShading')button.textContent='Activity shading: '+(garminOptions.activityShading?'on':'off');
    if(option==='sleepOverlay')button.textContent='Sleep: '+(garminOptions.sleepOverlay?'Overlay':'Underneath');
    if(option==='sleepDistribution')button.textContent=garminOptions.sleepDistribution?'Sleep: hourly distribution':'Sleep: stage composition';
    if(option==='aggregation'){
      button.textContent=dateCycled?'Bars: selected day':'Bars: '+garminOptions.aggregation;
      if(key==='g_steps')button.hidden=!garminOptions.stepsHistogram;
    }
  }
  for(const {slider,value} of stressSliders){if(!slider.editing){slider.value=String(garminOptions.stressTau);value.textContent='Smoothing: '+smoothingLabel(garminOptions.stressTau*60);}slider.disabled=!ready || !garminOptions.stressSmooth;}
  for(const {button,key} of activityButtons){button.disabled=!ready || syncing;button.setAttribute('aria-pressed',String(activityOptions(key).smooth));}
  for(const {slider,value,key} of activitySliders){const opts=activityOptions(key);setSmoothingValue(slider,opts.tauSeconds);slider.disabled=!ready || !opts.smooth;if(!slider.editing)value.textContent='Smoothing: '+smoothingLabel(opts.tauSeconds);}
  for(const {slider,value,key,caption,peak} of activityFloors){const opts=activityOptions(key);slider.max=String(Math.max(Number(slider.max),peak,opts.lower));slider.value=String(opts.lower);slider.disabled=!ready || syncing;value.textContent=caption(opts.lower);}
  for(const {button,field,available} of sleepButtons){button.disabled=!ready || syncing || !available;button.setAttribute('aria-pressed',String(garminOptions.sleepFields.includes(field)));}
}

// One rescaling policy for workout panels, profile overlays and custom graphs.
function workoutAxisUpdates(data,layout,range) {
  const result={},options=displayOptions(layout);
  if(layout.meta?.kind==='custom' && customState(layout.meta.custom_id).sameScale)return result;
  if(layout.yaxis2 && sameScale && !layout.meta?.dataset && layout.meta?.kind!=='custom')return result;
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
    for(const [key,value] of Object.entries(result)){const [axis,field]=key.split('.');view.layout[axis][field]=value;}
    applyCustomRanges(view);
    const state=customState(layout.meta.custom_id);
    for(const [axis,key] of Object.entries(layout.meta.custom_axes || {}))if(state.axisRanges[key]?.some(v=>v!==null)){
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
  activityShadingControl(group);
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
  try{await Promise.all(graphs.filter(g=>!g.layout.meta?.non_time).map(g=>Plotly.relayout(g,{
    'xaxis.range':range,'xaxis.autorange':false,...workoutAxisUpdates(g.data,g.layout,range)})));}
  finally{syncing=false;controls();}
}

function activityShadingControl(bar) {
  if(!bar)return null;
  const button=document.createElement('button');button.type='button';
  button.title='Show recorded activity intervals on every time graph. In aggregate views labels include the recorded date; shading is context, not an average activity.';
  button.addEventListener('click',()=>changeGarminOption('activityShading',!garminOptions.activityShading));
  bar.appendChild(button);garminButtons.push({button,option:'activityShading',key:'global'});return button;
}
function applyActivityShading(view) {
  view.layout.shapes=(view.layout.shapes || []).filter(s=>!s.name?.startsWith('Activity | '));
  if(!garminOptions.activityShading || view.layout.meta?.non_time || view.layout.meta?.kind==='hourly')return;
  const aggregate=!dateCycled && navigation?.mode==='Median + band';
  const dated=aggregate || selectedDays.length>1;
  for(const band of navigation?.activity_bands || []){
    const day=band.name.split(' | ')[1];if(!selectedDays.includes(day))continue;
    view.layout.shapes.push({...band,label:{...band.label,text:(dated?day+' · ':'')+(band.label?.text || band.name.split(' | ')[2])}});
  }
}

function displayOptions(layout) {
  return layout.meta?.kind==='custom'?customState(layout.meta.custom_id).garmin:garminOptions;
}
// Open, distinct control boxes: settings left, datasets/annotations right.
function controlAreas(bar) {
  if(bar.graphAreas)return bar.graphAreas;
  bar.className+=' graph-control-row';
  const content=document.createElement('div');content.className='graph-content';
  const label=document.createElement('span');label.className='control-label';label.textContent='Overlays';content.appendChild(label);
  const settings=document.createElement('div');settings.className='graph-settings';
  const title=document.createElement('span');title.className='control-label';title.textContent='Graph settings';settings.appendChild(title);
  const body=document.createElement('div');body.className='settings-body';settings.appendChild(body);
  const axis=document.createElement('div');axis.className='axis-controls';
  bar.appendChild(settings);bar.appendChild(content);
  return bar.graphAreas={content,settings:body,axis};
}


function settingsGroup(bar,title) {
  const group=document.createElement('div');group.className='settings-group';
  const label=document.createElement('span');label.className='settings-group-title';label.textContent=title;group.appendChild(label);bar.appendChild(group);return group;
}
let changeScope='glucose',changeSelect;
let eventOptions={site:true,sensor:true,profiles:false,percentage:false};
const eventButtons=[];
function setupChangeControls() {
  const top=document.getElementById('top-graph-controls');
  const bar=top?controlAreas(top).settings:controlAreas(document.getElementById('toolbar-left') || document.getElementById('viewer')).settings;
  const group=settingsGroup(bar,'Events');
  const label=document.createElement('label');label.textContent='Site / sensor changes';
  changeSelect=document.createElement('select');changeSelect.setAttribute('aria-label','Site and sensor change markers');
  for(const [value,text] of [['glucose','Glucose'],['all','All time graphs'],['off','Off']]){
    const option=document.createElement('option');option.value=value;option.textContent=text;changeSelect.appendChild(option);
  }
  changeSelect.addEventListener('change',()=>changeEventOption('scope',changeSelect.value));
  label.appendChild(changeSelect);group.appendChild(label);
  for(const [key,text] of [['site','Site'],['sensor','Sensor'],['profiles','Profile switches'],['percentage','Profile % shading']]){
    const button=document.createElement('button');button.type='button';button.textContent=text;
    button.title=key==='percentage'?'Recorded effective percentage: blue below 100%, orange above 100%; stronger tint further from 100%. No shading at 100%.':'Recorded events only';
    if(['profiles','percentage'].includes(key) && !navigation?.profile_events?.length){button.disabled=true;button.title='No effective profile records loaded. Refresh Nightscout to check availability.';}
    button.setAttribute('aria-pressed',String(eventOptions[key]));
    button.addEventListener('click',()=>changeEventOption(key,!eventOptions[key]));
    group.appendChild(button);eventButtons.push({key,button});
  }
}
function applyChangeEvents(view,index) {
  view.layout.shapes=(view.layout.shapes || []).filter(s=>!s.name?.startsWith('Change | '));
  view.layout.annotations=(view.layout.annotations || []).filter(s=>!s.name?.startsWith('Change | '));
  if(changeScope==='off' || view.layout.meta?.non_time || view.layout.meta?.kind==='hourly')return;
  const glucose=view.layout.meta?.dataset==='glucose' || (index===0 && currentOverlay==='Glucose') || view.data.some(t=>t.meta?.kind==='glucose' || t.meta?.dataset==='glucose');
  if(changeScope!=='all' && !glucose)return;
  for(const event of navigation?.change_events || []){
    if(!selectedDays.includes(event.date))continue;
    const site=event.label==='Site Change',color=site?'#557dce':'#b45bb5';
    if(!eventOptions[site?'site':'sensor'])continue;
    const clock=String(Math.floor(event.minute/60)).padStart(2,'0')+':'+String(Math.floor(event.minute%60)).padStart(2,'0');
    const text=(selectedDays.length>1?event.date+' · ':'')+(site?'Site':'Sensor')+' '+clock;
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
    const previous=key==='scope'?changeScope:eventOptions[key];syncing=true;clearHover();
    try{if(key==='scope')changeScope=value;else eventOptions[key]=value;controls();await redrawLocal();}
    catch(error){if(key==='scope')changeScope=previous;else eventOptions[key]=previous;card.textContent='Could not update event display.';}
    finally{syncing=false;controls();}
  });
}
function profileLineStyle(name){
  // Stable by base name, including unseen profiles; percentages share its line style.
  const dashes=['solid','dash','dot','dashdot','longdash','longdashdot'];
  const names=[...new Set((navigation?.profile_events || []).map(e=>e.name))].sort();
  return {color:'#7774a8',width:1.25,dash:dashes[names.indexOf(name)%dashes.length]};
}
function applyProfileEvents(view) {
  view.layout.shapes=(view.layout.shapes || []).filter(s=>!s.name?.startsWith('Effective | ') && !s.name?.startsWith('Profile · '));
  view.layout.annotations=(view.layout.annotations || []).filter(s=>!s.name?.startsWith('Effective | '));
  if(view.layout.meta?.non_time || view.layout.meta?.kind==='hourly')return;
  const seen=new Set(),labels=[];
  const events=(navigation?.profile_events || []).filter(e=>selectedDays.includes(e.date)).sort((a,b)=>a.minute-b.minute);
  for(const event of navigation?.profile_events || []){
    const p=event.percentage,text=event.name+(Number.isFinite(p)?' · '+p+'%':'');
    const name='Effective | '+event.date+' | '+event.minute+' | '+text;
    if(eventOptions.percentage && Number.isFinite(p) && p!==100 && !(navigation?.mode==='Median + band' && !dateCycled)){
      const rgb=p<100?'65,130,205':'225,125,45',alpha=.04+.10*Math.min(1,Math.abs(p-100)/100);
      for(const part of event.intervals || [])if(selectedDays.includes(part.date))view.layout.shapes.push({type:'rect',name:name+' | '+part.date,xref:'x',yref:'paper',x0:part.start,x1:part.end,y0:0,y1:1,line:{width:0},fillcolor:'rgba('+rgb+','+alpha+')',layer:'below'});
    }
  }
  // Actual switches have no meaningful time on a median; use the percentage distribution instead.
  if(!eventOptions.profiles || navigation?.mode==='Median + band' && !dateCycled)return;
  for(const event of events){
    const p=event.percentage,text=event.name+(Number.isFinite(p)?' · '+p+'%':'');
    const name='Effective | '+event.date+' | '+event.minute+' | '+text,line=profileLineStyle(event.name);
    view.layout.shapes.push({type:'line',name,xref:'x',yref:'paper',x0:event.minute,x1:event.minute,y0:0,y1:1,
      line,showlegend:!seen.has(event.name),legendgroup:'profile-switch-'+event.name,legendrank:90,
      label:{text:''},...(!seen.has(event.name)?{name:'Effective | '+event.name}: {})});
    // Legend names are short base names; internal identity is retained separately.
    view.layout.shapes.at(-1).legendgroup='Profile · '+event.name;
    if(!seen.has(event.name))view.layout.shapes.at(-1).name='Profile · '+event.name;
    seen.add(event.name);
    if(!Number.isFinite(p))continue;
    // Reserve one short annotation per 25 clock minutes; close switches retain their lines.
    if(labels.some(x=>Math.abs(x-event.minute)<25))continue;
    labels.push(event.minute);
    view.layout.annotations.push({name,xref:'x',yref:'paper',x:event.minute,y:1.015,
      text:p+'%',hovertext:event.date+' · '+text,showarrow:false,xanchor:'center',yanchor:'bottom',font:{size:10,color:line.color}});
  }
  if(seen.size)view.layout.showlegend=true;
}
