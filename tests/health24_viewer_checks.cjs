const fs=require('fs'),vm=require('vm'),assert=require('assert');
const {harness,storage,renderedCustom}=require('./health17_viewer_checks.cjs');
const sources=process.argv.slice(2,5).map(p=>fs.readFileSync(p,'utf8'));
const run=(h,code)=>vm.runInContext(code,h.context);
(async()=>{
 for(let mode=0;mode<sources.length;mode++){
  storage.clear();const h=await harness(sources[mode]);
  const message=h.sent.find(m=>m.type==='profile-studio:report-rendered');assert(message,'Renderer must acknowledge the report');
  assert(!message.error,message.error);assert(message.figures.length>=4,'Nonempty configured graphs are retained; empty activity metrics are omitted');assert(message.figures.every(f=>f.url.startsWith('data:image/svg+xml')));
  assert.equal(storage.size,0,'Export must not change live viewer settings');
  assert.equal(run(h,'changeScope'),'all');assert.equal(run(h,'currentOverlay'),'Glucose');
  assert.equal(run(h,"activityOptions('g_workout_hr').tauSeconds"),15);
  assert.equal(run(h,"activityOptions('g_workout_hr').lower"),100);
  for(const g of run(h,'graphs.filter(g=>!g.layout.meta?.non_time)'))assert.deepEqual(g._fullLayout.xaxis.range,[540,780]);
  if(mode>0){
    for(const g of run(h,'graphs.filter(g=>!g.layout.meta?.non_time && g.layout.meta?.kind!=="hourly")'))assert(g.layout.shapes.some(s=>s.name?.includes('Site Change')));
    const annotations=run(h,'graphs[0].layout.annotations.filter(a=>a.name?.startsWith("Change | "))');
    assert(new Set(annotations.map(a=>a.y)).size>1,'Simultaneous site and sensor labels use separate rows');
  }
  if(mode===2){
    const hourly=run(h,"graphs.find(g=>g.layout.meta?.kind==='hourly' && g.layout.meta.dataset==='bolus')");
    assert(hourly.layout.title.text.includes('no SMB'));assert.equal(hourly.layout.yaxis2.title.text,'Median U');
    const steps=run(h,"graphs.find(g=>g.layout.meta?.dataset==='g_steps')");assert(steps.data.every(t=>t.meta.variant==='cumulative'));
  }
  const before=run(h,'JSON.stringify(graphs.map(g=>g.data))');
  run(h,"changeSelect.value='off'");await run(h,'changeSelect.handlers.change()');await h.settle();
  assert(run(h,'graphs.every(g=>!g.layout.shapes.some(s=>s.name?.startsWith("Change | ")))'));
  assert(run(h,'graphs.every(g=>!g.layout.annotations.some(s=>s.name?.startsWith("Change | ")))'));
  assert.equal(run(h,'JSON.stringify(graphs.map(g=>g.data))'),before,'Annotation toggle does not change glucose/median data');
  assert.equal(h.races(),0);
 }
 fs.writeFileSync(process.argv[5],JSON.stringify(renderedCustom));console.log('Report renderer and change markers passed');
})().catch(e=>{console.error(e);process.exit(1)});
