const fs=require('fs'),vm=require('vm'),assert=require('assert');
const {harness,storage,renderedCustom}=require('./health17_viewer_checks.cjs');
const sources=process.argv.slice(2,5).map(p=>fs.readFileSync(p,'utf8'));
const run=(h,code)=>vm.runInContext(code,h.context);
(async()=>{
 for(let mode=0;mode<sources.length;mode++) {
  storage.clear();const h=await harness(sources[mode]);
  const graph=id=>run(h,`graphs[customIndex('${id}')]`);
  const ids=()=>run(h,'[...customStates.keys()]');
  const first=ids()[0];assert(first);
  assert.deepEqual(run(h,'customExtent(Array.from({length:200000},(_,i)=>i))'),[0,199999]);
  assert.equal(run(h,"customDisplayField({dataset:'g_sleep',unit:'Sleep stage',selected_unit:'Sleep probability (%)',daily_unit:'Sleep stage'},customState(),false).unit"),mode===0?'Sleep probability (%)':'Average sleep (h/hour)');
  assert.equal(run(h,"customDisplayField({dataset:'g_sleep',unit:'Sleep stage',selected_unit:'Sleep probability (%)',daily_unit:'Sleep stage'},customState(),true).unit"),'Sleep stage');
  const ui=run(h,`customUIs.get('${first}')`);
  assert.equal(ui.shading,undefined,'Activity shading is shared by all panels');
  assert.equal(ui.scale.parentElement.className,'settings-body');
  assert.equal(run(h,'activitySliders[0].slider.min'),'0');assert.equal(run(h,'activitySliders[0].slider.step'),'1');
  const slider=run(h,'activitySliders').find(s=>s.key==='g_workout_hr').slider;
  slider.value='0';await slider.handlers.change();await h.settle();
  assert.equal(run(h,"activityOptions('g_workout_hr').tauSeconds"),5);
  assert.equal(run(h,'smoothingLabel(5)'),'0m 05s');assert.equal(run(h,'smoothingLabel(45)'),'0m 45s');assert.equal(run(h,'smoothingLabel(120)'),'2m 00s');
  await run(h,`changeCustomSetting('${first}',s=>{s.selected=new Set(['garmin:g_workout_hr','ns:glucose']);s.fieldOptions['garmin:g_workout_hr']={axis:'own',smooth:true,tauSeconds:5};s.activityShading=false;})`);await h.settle();
  await run(h,'addCustomGraph()');await h.settle();
  const second=ids()[1];assert(second);
  await run(h,`changeCustomSetting('${second}',s=>{s.selected=new Set(['garmin:g_workout_hr','ns:glucose']);s.activityShading=true;s.axisRanges['unit:bpm']=[110,180];})`);await h.settle();
  assert.equal(graph(second).layout.yaxis.range[0],110);
  assert.equal(run(h,`customState('${first}').axisRanges['unit:bpm']`),undefined);
  assert(graph(second).layout.shapes.some(s=>s.name?.startsWith('Activity | ')));
  assert(graph(first).layout.shapes.some(s=>s.name?.startsWith('Activity | ')));
  if(mode===0){
    const filtered=graph(first).data.find(t=>t.meta.dataset==='g_workout_hr'),raw=graph(second).data.find(t=>t.meta.dataset==='g_workout_hr');
    assert(filtered.y[1]>40 && filtered.y[1]<150);assert.equal(raw.y[1],150,'Another graph keeps its own raw data');
    assert.deepEqual(run(h,`specs[customIndex('${first}')].data`),[],'Source bank stays immutable');
  }
  await run(h,'addCustomGraph()');await h.settle();const third=ids()[2];assert(third);
  await run(h,`changeCustomSetting('${third}',s=>{s.selected=new Set(['garmin:g_workout_speed']);s.garmin.pace=true;})`);await h.settle();
  assert(graph(third).data.some(t=>t.meta.unit==='min/km'));
  assert.equal(run(h,`customState('${second}').garmin.pace`),false);
  graph(second).handlers.plotly_relayout({'yaxis.range':[120,175]});await h.settle();
  assert.deepEqual(run(h,`customState('${second}').axisRanges['unit:bpm']`),[120,175]);
  await h.ids.expand.handlers.click();await h.settle();
  await run(h,`removeCustomGraph('${first}')`);await h.settle();assert.equal(ids().length,2);
  assert.equal(run(h,'graphs.length'),run(h,'specs.length'));assert.equal(run(h,'guides.length'),run(h,'graphs.length'));
  await run(h,`movePanel(customIndex('${third}'),-1)`);await h.settle();
  await h.ids['previous-day'].handlers.click();await h.settle();
  await h.ids['next-day'].handlers.click();await h.settle();
  assert(h.context.document.fullscreenElement);assert.equal(h.races(),0);
  await run(h,'setTimeRange([599,610])');await h.settle();
  for(const g of run(h,'graphs'))assert.deepEqual(g._fullLayout.xaxis.range,[599,610]);
  assert.deepEqual(graph(second).layout.yaxis.range,[120,175],'Own Y range survives shared time navigation');
  const saved=run(h,'viewerSettings()');assert.equal(saved.customPanels.length,2);
  const restored=await harness(sources[mode]);
  assert.deepEqual(run(restored,'[...customStates.keys()]'),ids());
  assert.deepEqual(run(restored,`customState('${second}').axisRanges['unit:bpm']`),[120,175]);
  assert(run(restored,`customState('${third}').garmin.pace`));
  assert.equal(run(restored,"activityOptions('g_workout_hr').tauSeconds"),5);
  if(mode===2){
    const bars=run(h,'graphs').find(g=>g.layout.meta?.dataset==='g_steps');
    const cumulative=run(h,'specs').find(g=>g.layout.meta?.dataset==='g_steps');
    assert(cumulative.data.some(t=>t.name==='Median' && t.showlegend!==false));
    assert(cumulative.data.some(t=>t.name==='25–75%' && t.showlegend));
    const before=JSON.stringify(cumulative.data);
    // After selecting a single day the aggregate toggle is disabled; the median source is still independent.
    run(h,"garminOptions.aggregation='Median'");await run(h,'redrawLocal()');await h.settle();
    assert.equal(JSON.stringify(cumulative.data),before);
    assert(bars.data.every(t=>t.meta.variant==='cumulative'));
  }
  for(const id of ids()) {await run(h,`removeCustomGraph('${id}')`);await h.settle();}
  assert.equal(ids().length,0);
  await run(h,'addCustomGraph()');await h.settle();assert.equal(ids().length,1,'Can add again after removing the final custom panel');
  assert.equal(h.races(),0);
 }
 // Old single-panel files migrate without losing selected fields or minute-based filters.
 const payload=JSON.parse(sources[0].match(/const payload = (.*);/)[1]);
 payload.navigation.saved_config={custom:['garmin:g_workout_hr'],customSameScale:false,garmin:{activity:{g_workout_hr:{smooth:true,tau:0.5,lower:0}}}};
 payload.navigation.config_revision=100;
 const migrated=await harness(sources[0].replace(/const payload = .*;/,'const payload = '+JSON.stringify(payload)+';'));
 assert.deepEqual(run(migrated,'[...customState().selected]'),['garmin:g_workout_hr']);
 assert.equal(run(migrated,"customState().fieldOptions['garmin:g_workout_hr'].tauSeconds"),30);
 fs.writeFileSync(process.argv[5],JSON.stringify(renderedCustom));console.log('Health-20 independent custom panels passed');
})().catch(e=>{console.error(e);process.exit(1);});
