const fs=require('fs'),vm=require('vm'),assert=require('assert');
const {harness,storage,renderedCustom}=require('./health17_viewer_checks.cjs');
const sources=process.argv.slice(2,5).map(p=>fs.readFileSync(p,'utf8'));
const run=(h,code)=>vm.runInContext(code,h.context);
(async()=>{
 for(let i=0;i<sources.length;i++) {
  storage.clear();const h=await harness(sources[i]);
  const plot=key=>h.plots.find(p=>p.layout.meta?.dataset===key);
  const hr=plot('g_workout_hr'),sleep=plot('g_sleep'),glucose=plot('glucose');
  assert.equal(run(h,'activityButtons.length'),5);assert.equal(run(h,'activityFloors.length'),4);
  assert.equal(run(h,'garminOptions.sleepOverlay'),false);
  assert(glucose.layout.shapes.some(s=>s.name?.startsWith('Activity | ')));
  await run(h,"garminButtons.find(b=>b.option==='activityShading').button.handlers.click()");await h.settle();
  assert(!glucose.layout.shapes.some(s=>s.name?.startsWith('Activity | ')));
  await run(h,"garminButtons.find(b=>b.option==='activityShading').button.handlers.click()");await h.settle();
  assert.deepEqual(glucose.layout.shapes.filter(s=>s.name?.startsWith('Activity | ')),hr.layout.shapes.filter(s=>s.name?.startsWith('Activity | ')));
  for(const field of run(h,'Object.keys(sleepFields)')){
    const b=run(h,'sleepButtons').find(b=>b.field===field);assert(b.available);await b.button.handlers.click();await h.settle();
  }
  const previousHeight=sleep.layout.height;
  await run(h,"garminButtons.find(b=>b.option==='sleepOverlay').button.handlers.click()");await h.settle();
  assert(sleep.layout.height<previousHeight);assert.deepEqual(sleep.layout.yaxis.domain,[0,1]);
  assert.equal(sleep.layout.yaxis2.overlaying,'y');assert.equal(sleep.layout.yaxis2.color,'#ffb74d');
  assert.equal(sleep.layout.yaxis3.color,'#ef5350');
  const rr=sleep.data.find(t=>t.meta.dataset==='g_sleep_respiration'),srr=sleep.data.find(t=>t.meta.dataset==='g_sleep_rr');
  assert.equal(rr.yaxis,srr.yaxis,'Same-unit respiration signals share one clearly labeled axis');
  assert(sleep.layout['yaxis'+rr.yaxis.slice(1)].title.text.includes('Respiration / Sleep respiration'));
  assert(sleep.layout.margin.l>=150);assert(sleep.data.filter(t=>t.meta.dataset==='g_sleep').every(t=>t.opacity===.55));
  await run(h,"garminButtons.find(b=>b.option==='sleepOverlay').button.handlers.click()");await h.settle();
  assert.equal(sleep.layout.height,previousHeight);assert(!sleep.layout.yaxis2.overlaying);assert(sleep.layout.yaxis.domain[0]>0);
  await run(h,"garminButtons.find(b=>b.option==='sleepOverlay').button.handlers.click()");await h.settle();
  for(const key of run(h,'activitySignals')){
    await run(h,`activityButtons.find(b=>b.key==='${key}').button.handlers.click()`);await h.settle();
    const slider=run(h,'activitySliders').find(s=>s.key===key).slider;slider.value='19';await slider.handlers.change();await h.settle();
    assert.equal(run(h,`activityOptions('${key}').tauSeconds`),600);
  }
  const gap=run(h,'lowPass([0,.1,null,8,8.1],[100,200,null,40,60],5)');assert.equal(gap[3],40);assert.equal(gap[2],null);
  if(i===0){
    assert(hr.data[0].y[1]<150,'Filter follows native samples instead of relabeling raw data');
    await run(h,"activityButtons.find(b=>b.key==='g_workout_hr').button.handlers.click()");await h.settle();
    const floor=run(h,'activityFloors').find(s=>s.key==='g_workout_hr').slider;floor.value='140';await floor.handlers.change();await h.settle();
    assert.equal(hr.layout.yaxis.range[0],140);assert(hr.layout.yaxis.range[1]>180);assert.equal(hr.data[0].y[0],40,'Clipping does not alter samples');
    await run(h,'setTimeRange([600,601])');await h.settle();assert(hr.layout.yaxis.range[1]<170,'Upper bound still follows visible data');
    await run(h,'setTimeRange([0,1440])');await h.settle();
    await run(h,"activityButtons.find(b=>b.key==='g_workout_speed').button.handlers.click()");await h.settle();
    const speedFloor=run(h,'activityFloors').find(s=>s.key==='g_workout_speed').slider;speedFloor.value='10';await speedFloor.handlers.change();await h.settle();
    await run(h,"garminButtons.find(b=>b.option==='pace').button.handlers.click()");await h.settle();
    assert.equal(plot('g_workout_speed').layout.yaxis.range[0],6);assert(plot('g_workout_speed').layout.yaxis.range[1]<6);
    assert(run(h,'activityFloors').find(s=>s.key==='g_workout_speed').value.textContent.includes('km/h'));
  }
  await h.ids.expand.handlers.click();await h.settle();assert(h.context.document.fullscreenElement);
  await run(h,'fitActivityButton.handlers.click()');await h.settle();
  assert(glucose.layout.shapes.some(s=>s.label?.text?.endsWith('Running')));
  assert(h.context.document.fullscreenElement);assert.equal(h.races(),0);
  const restored=await harness(sources[i]);
  assert(run(restored,'garminOptions.activityShading'));assert(run(restored,'garminOptions.sleepOverlay'));
  assert.equal(run(restored,"activityOptions('g_workout_power').tauSeconds"),600);
  assert(run(restored,"activityOptions('g_workout_power').smooth"));
  assert.equal(run(restored,'garminOptions.sleepFields.length'),7);
  if(i===0){assert.equal(run(restored,"activityOptions('g_workout_hr').lower"),140);assert.equal(run(restored,"activityOptions('g_workout_speed').lower"),10);}
 }
 fs.writeFileSync(process.argv[5],JSON.stringify(renderedCustom));console.log('Health-19 viewer controls passed');
})().catch(e=>{console.error(e);process.exit(1);});
