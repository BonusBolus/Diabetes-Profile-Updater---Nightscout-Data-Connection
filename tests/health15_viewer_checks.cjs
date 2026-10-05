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
 const ids=Object.fromEntries(['profile','profile-target-note','panels','hover-card','expand','viewer','previous-day','next-day','day-label','daily-summary','summary-title','summary-body','overlay-control','overlay-select','date-calendar','metric-select','show-targets','same-scale'].map(id=>[id,new Element(id)]));
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
 const context={window:{parent:{postMessage:m=>sent.push(m)}},crypto:{randomUUID:()=> 'test-save-event'},sessionStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},document,Number,String,Promise,Set,Math,JSON,requestAnimationFrame:f=>setImmediate(f),
  ResizeObserver:class{constructor(callback){observers.push(callback);}observe(){}},
  IntersectionObserver:class{constructor(callback){intersections.push(callback);}observe(){setImmediate(()=>intersections.forEach(f=>f([{isIntersecting:!hidden}])));}},
  Plotly:{purge:div=>{plots=plots.filter(p=>p!==div);},newPlot:(div,data,layout)=>render(div,data,layout,'new'),react:(div,data,layout)=>render(div,data,layout,'react'),
   relayout:async(div,patch)=>{
    if(active.has(div))races++;active.add(div);await tick();
    Object.assign(div.layout,patch);if(patch['xaxis.range'])div._fullLayout.xaxis.range=patch['xaxis.range'];
    active.delete(div);div.handlers.plotly_afterplot?.();
   }}};
 vm.createContext(context);vm.runInContext(source,context);
 async function settle(){for(let i=0;i<8;i++)await tick();await vm.runInContext('jobs',context);}
 await tick();assert.equal(plots.length,0,'Do not draw before fonts are ready');finishFonts();await settle();
 if(hidden){assert.equal(plots.length,0,'Do not draw hidden tabs even when iframe dimensions are nonzero');width=1000;observers.forEach(f=>f());await settle();assert.equal(plots.length,0);intersections.forEach(f=>f([{isIntersecting:true}]));await settle();}


 return {sent,context,ids,plots,settle,races:()=>races};
}
(async()=>{
 const a=await harness(sources[0]);
 const run=(h,code)=>vm.runInContext(code,h.context);
 await a.ids['previous-day'].handlers.click();await a.settle();
 assert.equal(a.ids['day-label'].textContent,'2026-09-25');
 const stress=a.plots.find(p=>p.layout.meta?.dataset==='g_stress');
 assert.equal(stress.data[0].type,'bar');assert.equal(stress.data[0].marker.color[0],'#42a5f5');
 const button=(option)=>run(a,'garminButtons').find(b=>b.option===option).button;
 await button('stressSmooth').handlers.click();await a.settle();
 assert(stress.data[0].y[1]>20 && stress.data[0].y[1]<60);
 assert.equal(stress.data[0].y.at(-1),90,'A gap resets smoothing');
 assert(stress.data.some(t=>t.meta?.kind==='stress_colored_line'));assert(stress.data.every(t=>t.type!=='bar'));
 await button('stressLine').handlers.click();await a.settle();
 await button('stressSmooth').handlers.click();await a.settle();
 assert.equal(stress.data[0].y[1],60);assert(stress.data.some(t=>t.meta?.kind==='stress_colored_line'));
 const steps=a.plots.find(p=>p.layout.meta?.dataset==='g_steps');
 assert(steps.data.every(t=>t.meta.variant==='cumulative'));
 const hr=a.plots.find(p=>p.layout.meta?.dataset==='g_hr');
 assert.equal(hr.layout.yaxis.range[0],35);
 const customFields=run(a,'customUIs.values().next().value.buttons');
 await customFields.find(b=>b.value==='garmin:g_stress').handlers.click();await a.settle();
 const customIds=run(a,'[...customState().selected]');
 run(a,'movePanel(panelOrder[0],1)');
 const order=run(a,'panelOrder.map(panelIdentity)');
 run(a,"configurationName.value='Running view'");await run(a,'saveConfiguration.handlers.click()');
 assert.equal(a.sent[0].request.name,'Running view');assert.equal(a.sent[0].type,'profile-studio:save');
 const config=run(a,'viewerSettings()');
 assert.equal(config.garmin.stressLine,true);
 // Rebuilding with an additional layer must retain the date, options, custom fields and order.
 const b=await harness(sources[1]);
 assert.equal(b.ids['day-label'].textContent,'2026-09-25');
 assert.deepEqual(run(b,'[...customState().selected]'),customIds);
 const bOrder=run(b,'panelOrder.map(panelIdentity)').filter(x=>order.includes(x));
 assert.deepEqual(bOrder,order);
 assert.equal(run(b,'garminOptions.stressLine'),true);
 assert(b.plots.find(p=>p.layout.meta?.dataset==='g_stress').data.some(t=>t.meta?.kind==='stress_colored_line'));
 await b.ids.expand.handlers.click();await b.settle();assert(b.context.document.fullscreenElement);
 await b.ids['next-day'].handlers.click();await b.settle();
 assert.equal(b.ids['day-label'].textContent,'2026-09-26');
 const speed=b.plots.find(p=>p.layout.meta?.dataset==='g_workout_speed');
 const pace=run(b,'garminButtons').find(b=>b.option==='pace').button;
 await pace.handlers.click();await b.settle();
 assert.equal(speed.data[0].y[0],6);assert.equal(speed.data[0].meta.unit,'min/km');
 assert.equal(speed.layout.yaxis.autorange,false);assert(speed.layout.yaxis.range[0]>speed.layout.yaxis.range[1]);
 assert(b.context.document.fullscreenElement);
 await b.ids['previous-day'].handlers.click();await b.settle();
 // An explicit sidebar date selection must override the retained local date.
 const c=await harness(sources[2]);
 assert.equal(c.ids['day-label'].textContent,'2026-09-26');
 assert.equal(a.races()+b.races()+c.races(),0);
 fs.writeFileSync(process.argv[5],JSON.stringify(renderedCustom));
 console.log('Health controls, date persistence and configuration state passed');
})().catch(e=>{console.error(e);process.exit(1);});
