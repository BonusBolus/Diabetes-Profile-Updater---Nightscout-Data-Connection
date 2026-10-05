// DOM/Plotly lifecycle regression checks. Run by test_viewer.py when Node exists.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[2],'utf8');
const renderedCustom=[];
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function harness(hidden=false) {
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
  if(layout.meta?.kind==='custom')renderedCustom.push(JSON.parse(JSON.stringify({data,layout})));
  div._fullLayout={xaxis:{range:layout.xaxis.range.slice(),_offset:62,_length:876,l2p:x=>x/1440*876},yaxis:{_offset:36,_length:120,l2p:y=>120-y*6}};
  if(kind==='new')plots.push(div);else reacts++;
  active.delete(div);div.handlers.plotly_afterplot?.();
 }
 const context={document,Number,String,Promise,Set,Math,JSON,requestAnimationFrame:f=>setImmediate(f),
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

 assert.equal(plots.length,9);
 assert.equal(ids.profile.style.display,'none');
 assert(ids['overlay-control'].hidden);assert(ids['same-scale'].hidden);assert(ids['metric-select'].hidden);
 await ids.expand.handlers.click();await settle();assert(document.fullscreenElement);
 await ids['next-day'].handlers.click();await settle();
 assert.equal(ids['day-label'].textContent,'2026-09-26');
 assert.deepEqual(plots.find(p=>p.layout.meta?.dataset==='g_sleep').layout.yaxis.range,[-.5,.5]);
 assert(plots.find(p=>p.layout.meta?.dataset==='g_sleep').data.some(t=>t.name==='Deep sleep'));
 assert.equal(races,0);
}
(async()=>{await harness();console.log('Data-only expanded navigation passed');})().catch(e=>{console.error(e);process.exit(1);});
