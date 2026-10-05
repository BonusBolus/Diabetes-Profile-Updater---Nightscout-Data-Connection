const fs=require('fs'),vm=require('vm'),assert=require('assert');
const {harness,storage,renderedCustom}=require('./health17_viewer_checks.cjs');
const sources=process.argv.slice(2,5).map(p=>fs.readFileSync(p,'utf8'));
const run=(h,code)=>vm.runInContext(code,h.context);
(async()=>{
 for(let mode=0;mode<sources.length;mode++){
  storage.clear();const h=await harness(sources[mode]);
  await run(h,"changeCustomSetting('custom-1',s=>{s.selected=new Set(['ns:glucose']);})");await h.settle();
  const global=run(h,"garminButtons.filter(b=>b.option==='activityShading')");assert.equal(global.length,1);
  assert.equal(global[0].button.parentElement,run(h,'fitActivityButton.parentElement'));
  assert.equal(global[0].button.parentElement.className,'settings-group');
  const timeGraphs=()=>run(h,'graphs.filter(g=>!g.layout.meta?.non_time && g.layout.meta?.kind!=="hourly")');
  for(const g of timeGraphs()){
   const bands=g.layout.shapes.filter(s=>s.name?.startsWith('Activity | '));assert(bands.length,'Every time graph has shared shading');
   assert.equal(bands[0].x0,600);assert.equal(bands[0].x1,640);
   assert(bands[0].label.text.endsWith('Running'));
   if(mode>0)assert(bands[0].label.text.startsWith('2026-09-26'));
  }
  assert(run(h,'graphs.filter(g=>g.layout.meta?.non_time).every(g=>!g.layout.shapes.some(s=>s.name?.startsWith("Activity | ")))'),'Date/hour heatmaps do not receive a misleading full-height time interval');
  const state=run(h,'JSON.stringify({days:selectedDays,cycled:dateCycled,mode:navigation.mode})');
  const data=run(h,'JSON.stringify(graphs.map(g=>g.data))');
  run(h,'activitySelect.value=activitySelect.children[0].value');
  await run(h,'fitActivityButton.handlers.click()');await h.settle();
  assert.equal(run(h,'JSON.stringify({days:selectedDays,cycled:dateCycled,mode:navigation.mode})'),state);
  assert.equal(run(h,'JSON.stringify(graphs.map(g=>g.data))'),data,'Fitting activity must not replace aggregate data with daily traces');
  for(const g of timeGraphs())assert.deepEqual(g._fullLayout.xaxis.range,[595,645]);
  await run(h,'fullDayButton.handlers.click()');await h.settle();
  assert.equal(run(h,'JSON.stringify(graphs.map(g=>g.data))'),data);
  for(const g of timeGraphs())assert.deepEqual(g._fullLayout.xaxis.range,[0,1440]);
  await global[0].button.handlers.click();await h.settle();
  for(const g of timeGraphs())assert(!g.layout.shapes.some(s=>s.name?.startsWith('Activity | ')));
  const restored=await harness(sources[mode]);assert.equal(run(restored,'garminOptions.activityShading'),false);
  await global[0].button.handlers.click();await h.settle();
  for(const g of timeGraphs())assert(g.layout.shapes.some(s=>s.name?.startsWith('Activity | ')));
  const floor=run(h,'activityFloors[0]');assert.equal(floor.slider.style.height,'90px');assert.equal(floor.slider.parentElement.style.top,'36px');
  run(h,"graphs.find(g=>g.layout.meta?.dataset===activityFloors[0].key)._fullLayout.yaxis={_offset:50,_length:200};positionAxisControls(graphs.find(g=>g.layout.meta?.dataset===activityFloors[0].key))");
  assert.equal(floor.slider.style.height,'170px');assert.equal(floor.slider.parentElement.style.top,'50px');
  assert.equal(h.plots[0].layout.height,250);
  assert.equal(h.races(),0);
 }
 fs.writeFileSync(process.argv[5],JSON.stringify(renderedCustom));console.log('Health-22 mode, shading, and axis alignment checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
