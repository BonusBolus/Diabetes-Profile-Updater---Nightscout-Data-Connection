// Retain local graph navigation when Streamlit rebuilds an iframe after layer changes.
const storageKey='profile-studio-view:'+navigation?.state_scope;
const dateRequest=JSON.stringify([navigation?.selected,navigation?.mode,navigation?.date_revision]);
function panelIdentity(index) {
  const s=specs[index];if(s.layout.meta?.kind==='custom')return 'custom:'+s.layout.meta.custom_id;return (s.layout.meta?.kind || '')+':'+(s.layout.meta?.dataset || s.layout.title.text.split(' · ')[0]);
}
function viewerSettings() {
  return {overlay:currentOverlay,sameScale,metric:currentMetric,showTargets,excludeSMB,changeScope,eventOptions,
    customPanels:[...dormantCustomPanels,...[...customStates.values()].map(serializeCustom)],customVisible:[...customStates.keys()],hourlyModes,
    order:panelOrder.map(panelIdentity),garmin:garminOptions};
}
function persistViewer() {
  if(navigation?.report_render)return;
  try {sessionStorage.setItem(storageKey,JSON.stringify({dateRequest,selectedDays,dateCycled,
    configRevision:navigation?.config_revision,viewer:viewerSettings()}));} catch(_) { /* Browser storage may be disabled. */ }
}
function restoreViewer() {
  let state=null;
  try {if(!navigation?.report_render)state=JSON.parse(sessionStorage.getItem(storageKey));} catch(_) {}
  if(state?.dateRequest===dateRequest && state?.dateCycled && state.selectedDays?.length===1 && navigation?.days.includes(state.selectedDays[0])) {
    selectedDays=state.selectedDays;dateCycled=true;
  }
  const incoming=navigation?.saved_config && (!state || state.configRevision!==navigation.config_revision);
  const s=incoming?navigation.saved_config:state?.viewer;
  if(!s || typeof s!=='object'){if(Array.isArray(navigation?.custom_ids))restoreCustomPanels([]);return;}
  const overlayName={'Nightscout targets':'Temporary Targets','Temporary basal':'Temporary Basal','IOB + boluses':'IOB + Boluses','COB + carbs':'COB + Carbs','Variable sensitivity':'Variable Sensitivity'}[s.overlay] || s.overlay?.replace('Garmin · Workout ','Garmin · Activity ');
  if(navigation?.overlays?.[overlayName])currentOverlay=overlayName;
  sameScale=s.sameScale===true;
  if(['glucose','all','off'].includes(s.changeScope))changeScope=s.changeScope;
  for(const key of Object.keys(eventOptions))if(typeof s.eventOptions?.[key]==='boolean')eventOptions[key]=s.eventOptions[key];
  if(navigation?.profiles?.[s.metric])currentMetric=s.metric;
  showTargets=s.showTargets!==false;excludeSMB=s.excludeSMB===true;
  for(const key of Object.keys(hourlyModes))if(['Average','Median'].includes(s.hourlyModes?.[key]))hourlyModes[key]=s.hourlyModes[key];
  for(const key of Object.keys(garminOptions))if(typeof s.garmin?.[key]===typeof garminOptions[key])garminOptions[key]=s.garmin[key];
  garminOptions.stressTau=Number.isFinite(garminOptions.stressTau)?Math.min(30,Math.max(1,garminOptions.stressTau)):5;
  garminOptions.aggregation=['Average','Median'].includes(garminOptions.aggregation)?garminOptions.aggregation:'Average';
  garminOptions.sleepFields=Array.isArray(garminOptions.sleepFields)?garminOptions.sleepFields.filter(k=>k in sleepFields):[];
  const activity={};
  for(const key of activitySignals) {
    const raw=garminOptions.activity?.[key];if(!raw || typeof raw!=='object')continue;
    activity[key]={smooth:raw.smooth===true,tauSeconds:Math.min(1800,Math.max(5,Number.isFinite(raw.tauSeconds)?raw.tauSeconds:Number.isFinite(raw.tau)?raw.tau*60:300)),
      lower:Number.isFinite(raw.lower)?Math.max(0,raw.lower):0};
  }
  garminOptions.activity=activity;
  if(Array.isArray(s.customPanels))restoreCustomPanels(s.customPanels);
  else if(Array.isArray(s.custom)){
    const fieldOptions={};for(const [key,value] of Object.entries(activity))fieldOptions['garmin:'+key]={...value,axis:'unit'};
    if(garminOptions.stressSmooth)fieldOptions['garmin:g_stress']={axis:'unit',smooth:true,tauSeconds:garminOptions.stressTau*60};
    restoreCustomPanels([{id:'custom-1',selected:s.custom,sameScale:s.customSameScale,garmin:garminOptions,fieldOptions}]);
  }
  else if(Array.isArray(navigation?.custom_ids))restoreCustomPanels([]);
  if(Array.isArray(s.order)) {
    const aliases={':Glucose':':glucose',':Temp basal':':basal',':Temp basal %':':basal_percent',':IOB & boluses':':iob',':Median IOB':':iob',':IOB':':iob',':COB & carbs':':cob',':Median COB':':cob',':COB':':cob',':Temp targets':':target','custom:Custom graph':'custom:custom-1'};
    const order=s.order.map(id=>aliases[id] || id);
    const rank=i=>{const r=order.indexOf(panelIdentity(i));return r<0?10000:r;};
    panelOrder.sort((a,b)=>rank(a)-rank(b));panelOrder.forEach(i=>panels.appendChild(panelCards[i]));
  }
}
const configurationName=document.createElement('input');configurationName.type='text';configurationName.maxLength=80;
configurationName.placeholder='Configuration name';configurationName.setAttribute('aria-label','Configuration name');
const saveConfiguration=document.createElement('button');saveConfiguration.type='button';saveConfiguration.textContent='Save configuration';
saveConfiguration.title='Save to graph_configurations in the project. Reusing a name updates that saved view.';
saveConfiguration.addEventListener('click',()=>{
  const name=configurationName.value.trim();if(!name){card.textContent='Enter a configuration name first.';configurationName.focus();return;}
  persistViewer();
  const config={format:'profile-studio-view',version:1,layers:navigation?.layers || [],mode:navigation?.mode || 'One day',viewer:viewerSettings()};
  window.parent.postMessage({type:'profile-studio:save',request:{id:crypto.randomUUID(),name,config}},'*');
  card.textContent='Saving '+name+'…';
});
expand.parentElement?.appendChild(configurationName);expand.parentElement?.appendChild(saveConfiguration);
