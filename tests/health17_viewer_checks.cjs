// DOM/Plotly lifecycle regression checks. Run by test_viewer.py when Node exists.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const sources=process.argv.slice(2,5).map(p=>fs.readFileSync(p,'utf8'));
const storage=new Map();
const source=sources[0];
const renderedCustom=[];
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function harness(source,hidden=false) {
 let width=hidden==='zero'?0:1000, finishFonts;
 const fonts=new Promise(resolve=>finishFonts=resolve);
 class Element {
  constructor(id=''){this.id=id;this.style={};this.children=[];this.handlers={};this.textContent='';this.value='';this.disabled=false;}
  get clientWidth(){return width;} get clientHeight(){return 720;}
  getBoundingClientRect(){return {width,height:720};}
  appendChild(x){if(x.parentElement)x.parentElement.children=x.parentElement.children.filter(v=>v!==x);this.children=this.children.filter(v=>v!==x);this.children.push(x);x.parentElement=this;return x;} replaceChildren(){this.children=[];this.textContent='';}
  remove(){if(this.parentElement)this.parentElement.children=this.parentElement.children.filter(c=>c!==this);}
  setAttribute(k,v){this[k]=v;}
  on(k,f){this.handlers[k]=f;}addEventListener(k,f){this.handlers[k]=f;}
 }
 const ids=Object.fromEntries(['profile','profile-target-note','panels','hover-card','expand','viewer','previous-day','next-day','day-label','daily-summary','summary-title','summary-body','overlay-control','overlay-select','date-calendar','metric-select','show-targets','same-scale','toolbar-left'].map(id=>[id,new Element(id)]));
 const events={},observers=[],intersections=[];let plots=[],active=new Set(),races=0,reacts=0;
 const document={getElementById:id=>ids[id],createElement:()=>new Element(),addEventListener:(k,f)=>events[k]=f,fonts:{ready:fonts},
  documentElement:{requestFullscreen:async()=>{document.fullscreenElement=true;events.fullscreenchange();}},
  exitFullscreen:async()=>{document.fullscreenElement=false;events.fullscreenchange();}};
 async function render(div,data,layout,kind) {
  if(active.has(div))races++;
  active.add(div);await tick();
  div.data=data;div.layout=layout;
  renderedCustom.push(JSON.parse(JSON.stringify({data,layout})));
  div._fullLayout={xaxis:{range:layout.xaxis.range.slice(),_offset:62,_length:876,l2p:x=>x/1440*876},yaxis:{_offset:36,_length:120,l2p:y=>120-y*6}};
  if(kind==='new')plots.push(div);else reacts++;
  active.delete(div);div.handlers.plotly_afterplot?.();
 }
 const sent=[];
 const context={window:{addEventListener(){},parent:{postMessage:m=>sent.push(m)}},crypto:{randomUUID:()=> 'test-save-event'},sessionStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},document,Number,String,Promise,Set,Math,JSON,requestAnimationFrame:f=>setImmediate(f),
  ResizeObserver:class{constructor(callback){observers.push(callback);}observe(){}},
  IntersectionObserver:class{constructor(callback){intersections.push(callback);}observe(){setImmediate(()=>intersections.forEach(f=>f([{isIntersecting:!hidden}])));}},
  Plotly:{toImage:async()=> 'data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22/%3E',purge:div=>{plots=plots.filter(p=>p!==div);},newPlot:(div,data,layout)=>render(div,data,layout,'new'),react:(div,data,layout)=>render(div,data,layout,'react'),
   relayout:async(div,patch)=>{
    if(active.has(div))races++;active.add(div);await tick();
    for(const [key,value] of Object.entries(patch)){const parts=key.split('.');if(parts.length===2){div.layout[parts[0]]||={};div.layout[parts[0]][parts[1]]=value;}else div.layout[key]=value;}if(patch['xaxis.range'])div._fullLayout.xaxis.range=patch['xaxis.range'];
    active.delete(div);div.handlers.plotly_afterplot?.();
   }}};
 vm.createContext(context);vm.runInContext(source,context);
 async function settle(){for(let i=0;i<8;i++)await tick();await vm.runInContext('jobs',context);}
 await tick();assert.equal(plots.length,0,'Do not draw before fonts are ready');finishFonts();await settle();
 if(hidden){assert.equal(plots.length,0,'Do not draw hidden tabs even when iframe dimensions are nonzero');width=1000;observers.forEach(f=>f());await settle();assert.equal(plots.length,0);intersections.forEach(f=>f([{isIntersecting:true}]));await settle();}


 return {sent,context,ids,plots,settle,races:()=>races};
}
module.exports={harness,storage,renderedCustom};
if(require.main===module)(async()=>{
 const run=(h,code)=>vm.runInContext(code,h.context);
 for(let i=0;i<sources.length;i++) {
  storage.clear();const h=await harness(sources[i]);
  const sleep=h.plots.find(p=>p.layout.meta?.dataset==='g_sleep'),stress=h.plots.find(p=>p.layout.meta?.dataset==='g_stress');
  assert(sleep.data.every(t=>!t.meta?.sleep_overlay),'Sleep extras start off');
  for(const field of ['g_sleep_movement','g_sleep_restless','g_sleep_hrv','g_sleep_rhr']) {
    await run(h,'sleepButtons').find(b=>b.field===field).button.handlers.click();await h.settle();
  }
  assert(sleep.data.some(t=>t.meta?.dataset==='g_sleep_restless' && t.type==='bar'));
  assert(sleep.data.some(t=>t.meta?.dataset==='g_sleep_hrv'));assert(sleep.layout.yaxis4);
  if(i===0)assert(!sleep.layout.yaxis5,'An empty resting-heart-rate signal does not reserve an overlay row');
  else assert(sleep.layout.yaxis5);
  const button=run(h,'garminButtons').find(b=>b.option==='stressSmooth').button;
  await button.handlers.click();await h.settle();assert(stress.data.every(t=>t.type!=='bar'));
  const slider=run(h,'stressSliders[0].slider');slider.value='20';await slider.handlers.change();await h.settle();
  assert.equal(run(h,'garminOptions.stressTau'),20);
  assert.equal(run(h,'viewerSettings().garmin.stressTau'),20);
  assert(run(h,'viewerSettings().garmin.stressSmooth'));
  const fast=run(h,'lowPass([0,1,2],[0,100,0],1)'),slow=run(h,'lowPass([0,1,2],[0,100,0],20)');assert(slow[1]<fast[1]);
  if(i>0){
    const step=h.plots.find(p=>p.layout.meta?.dataset==='g_steps');
    if(i===2)assert(step.data.some(t=>t.name==='25–75%' && t.fill==='toself' && t.showlegend));
    else assert(step.data.some(t=>t.name==='Median'),'Multi-day graphs default to Median');
    await run(h,"changeGarminOption('stepsHistogram',true)");await h.settle();
    assert(step.data.every(t=>t.meta.aggregation==='Average'));
    await run(h,'garminButtons').find(b=>b.option==='aggregation').button.handlers.click();await h.settle();
    assert(step.data.every(t=>t.meta.aggregation==='Median'));
    await run(h,"changeGarminOption('stepsHistogram',false)");await h.settle();
    assert(step.data.every(t=>t.meta.variant==='cumulative'));
  }
  await h.ids.expand.handlers.click();await h.settle();assert(h.context.document.fullscreenElement);
  await run(h,'fitActivityButton.handlers.click()');await h.settle();
  for(const p of h.plots)assert.deepEqual(p._fullLayout.xaxis.range,[595,645]);
  const workout=h.plots.find(p=>p.layout.meta?.dataset==='g_workout_hr');
  assert(workout.layout.yaxis.range[0]>140);assert(workout.layout.yaxis.range[1]<170,'Visible workout excludes later outlier');
  for(const p of h.plots.filter(p=>p.layout.meta?.dataset?.startsWith('g_')))assert(p.layout.shapes.some(s=>s.label?.text?.endsWith('Running')));
  await run(h,'fullDayButton.handlers.click()');await h.settle();
  assert.deepEqual(workout._fullLayout.xaxis.range,[0,1440]);assert(workout.layout.yaxis.range[1]>190);
  assert(h.context.document.fullscreenElement);assert.equal(h.races(),0);
  // Browser-session restore is the same state payload used by named configurations.
  const restored=await harness(sources[i]);
  assert.equal(run(restored,'garminOptions.stressTau'),20);
  assert(run(restored,'garminOptions.stressSmooth'));
  assert(run(restored,"garminOptions.sleepFields.includes('g_sleep_hrv')"));
  run(h,'navigation.activity_bands=[];setupActivityControls();activityControlState()');
  assert(run(h,'fitActivityButton.disabled'),'Missing intervals disable, rather than hide, the zoom control');
  assert(run(h,'activitySelect.children[0].textContent').includes('No recorded activities'));
  run(h,"navigation.activity_bands=[{name:'Activity | 2026-09-26 | Cycling | cycle',x0:700,x1:760},{name:'Activity | 2026-09-26 | Running 2 | run2',x0:800,x1:820}];activityControlState()");
  assert(!run(h,'fitActivityButton.disabled'));
  assert(!run(h,'activitySelect.children[0].textContent').includes('cycle'),'Internal IDs stay out of labels');
  run(h,'activitySelect.value=activitySelect.children[1].value');
  await run(h,'fitActivityButton.handlers.click()');await h.settle();
  for(const p of h.plots)assert.deepEqual(p._fullLayout.xaxis.range,[795,825]);
 }
 fs.writeFileSync(process.argv[5],JSON.stringify(renderedCustom));console.log('Health-17 controls passed');
})().catch(e=>{console.error(e);process.exit(1);});
