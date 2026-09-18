// DOM/Plotly lifecycle regression checks. Run by test_viewer.py when Node exists.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[2],'utf8');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function harness(hidden=false) {
 let width=hidden==='zero'?0:1000, finishFonts;
 const fonts=new Promise(resolve=>finishFonts=resolve);
 class Element {
  constructor(id=''){this.id=id;this.style={};this.children=[];this.handlers={};this.textContent='';this.value='';this.disabled=false;}
  get clientWidth(){return width;} get clientHeight(){return 720;}
  getBoundingClientRect(){return {width,height:720};}
  appendChild(x){this.children.push(x);return x;} replaceChildren(){this.children=[];this.textContent='';}
  on(k,f){this.handlers[k]=f;}addEventListener(k,f){this.handlers[k]=f;}
 }
 const ids=Object.fromEntries(['profile','panels','hover-card','expand','viewer','previous-day','next-day','day-label','daily-summary','summary-title','summary-body','overlay-control','overlay-select'].map(id=>[id,new Element(id)]));
 const events={},observers=[],intersections=[];let plots=[],active=new Set(),races=0,reacts=0;
 const document={getElementById:id=>ids[id],createElement:()=>new Element(),addEventListener:(k,f)=>events[k]=f,fonts:{ready:fonts},
  documentElement:{requestFullscreen:async()=>{document.fullscreenElement=true;events.fullscreenchange();}},
  exitFullscreen:async()=>{document.fullscreenElement=false;events.fullscreenchange();}};
 async function render(div,data,layout,kind) {
  if(active.has(div))races++;
  active.add(div);await tick();
  div.data=data;div.layout=layout;
  div._fullLayout={xaxis:{range:layout.xaxis.range.slice(),_offset:62,_length:876,l2p:x=>x/1440*876},yaxis:{_offset:36,_length:120,l2p:y=>120-y*6}};
  if(kind==='new')plots.push(div);else reacts++;
  active.delete(div);div.handlers.plotly_afterplot?.();
 }
 const context={document,Number,String,Promise,Set,Math,JSON,requestAnimationFrame:f=>setImmediate(f),
  ResizeObserver:class{constructor(callback){observers.push(callback);}observe(){}},
  IntersectionObserver:class{constructor(callback){intersections.push(callback);}observe(){setImmediate(()=>intersections.forEach(f=>f([{isIntersecting:!hidden}])));}},
  Plotly:{newPlot:(div,data,layout)=>render(div,data,layout,'new'),react:(div,data,layout)=>render(div,data,layout,'react'),
   relayout:async(div,patch)=>{
    if(active.has(div))races++;active.add(div);await tick();
    Object.assign(div.layout,patch);if(patch['xaxis.range'])div._fullLayout.xaxis.range=patch['xaxis.range'];
    active.delete(div);div.handlers.plotly_afterplot?.();
   }}};
 vm.createContext(context);vm.runInContext(source,context);
 async function settle(){for(let i=0;i<8;i++)await tick();await vm.runInContext('jobs',context);}
 await tick();assert.equal(plots.length,0,'Do not draw before fonts are ready');finishFonts();await settle();
 if(hidden){assert.equal(plots.length,0,'Do not draw hidden tabs even when iframe dimensions are nonzero');width=1000;observers.forEach(f=>f());await settle();assert.equal(plots.length,0);intersections.forEach(f=>f([{isIntersecting:true}]));await settle();}
 assert.equal(plots.length,8);assert(plots.every(p=>p.layout.width===1000));
 assert.equal(ids['overlay-select'].children.length,6);
 assert.equal(ids['overlay-select'].value,'None');
 await ids.expand.handlers.click();await settle();assert(document.fullscreenElement);
 plots[0]._fullLayout.xaxis.range=[360,720];
 async function overlay(value) {ids['overlay-select'].value=value;await ids['overlay-select'].handlers.change();await settle();assert(document.fullscreenElement);assert.deepEqual(plots[0]._fullLayout.xaxis.range,[360,720]);}
 const lower=plots.slice(1).map(p=>JSON.stringify(p.data));
 await overlay('Glucose');assert(plots[0].data.some(t=>t.meta?.kind==='median'),'Initial median mode is preserved');
 assert.equal(plots[0].layout.yaxis2.range[1],20);
 await overlay('IOB + boluses');assert(plots[0].data.some(t=>t.meta?.kind==='median' && t.meta.dataset==='iob'));assert(!plots[0].data.some(t=>t.meta?.kind==='bolus'));
 assert.deepEqual(plots.slice(1).map(p=>JSON.stringify(p.data)),lower,'Changing overlay leaves other panels unchanged');
 await ids['next-day'].handlers.click();await settle();
 assert.equal(ids['day-label'].textContent,'2026-09-16'); // wraps after last selected day
 assert(ids['summary-title'].textContent.includes('In range 100%'));
 const hourly=plots.find(p=>p.layout.meta?.dataset==='carbs' && p.layout.meta?.kind==='hourly');
 assert(hourly);assert.equal(hourly.data[0].y[0],'2026-09-16');assert.equal(hourly.data[0].z[0][5],30);assert.equal(hourly.data[1].y[5],30);
 await overlay('COB + carbs');assert(plots[0].data.some(t=>t.meta?.kind==='cob'));assert(plots[0].data.some(t=>t.meta?.kind==='carbs'));
 assert(plots[0].data.filter(t=>t.meta?.date).every(t=>t.meta.date==='2026-09-16'));
 await ids['next-day'].handlers.click();await settle();assert.equal(ids['day-label'].textContent,'2026-09-17');
 await overlay('Glucose');assert(plots[0].data.some(t=>t.meta?.kind==='glucose'));assert(!plots[0].data.some(t=>t.meta?.kind==='median'));
 assert(plots[0].data.find(t=>t.meta?.kind==='glucose').showlegend,'Rebuild legend after filtering to a later day');
 await overlay('None');assert(!plots[0].layout.yaxis2);assert(plots[0].data.every(t=>!t.meta?.date));
 assert.equal(plots[0].layout.yaxis.rangemode,'normal');
 assert(plots.every(p=>p.layout.title.text.includes('2026-09-17')));
 await ids['previous-day'].handlers.click();await settle();assert.equal(ids['day-label'].textContent,'2026-09-16');
 // Hide/show and concurrent resize/change requests must not overlap Plotly calls.
 width=0;observers.forEach(f=>f());await settle();
 width=780;ids['overlay-select'].value='IOB + boluses';const change=ids['overlay-select'].handlers.change();observers.forEach(f=>f());
 await change;await settle();assert.equal(races,0);assert(plots.every(p=>p.layout.width===780));
 const boxes=[{left:10,right:30,top:10,bottom:20},{left:15,right:35,top:10,bottom:20},{left:80,right:100,top:10,bottom:20}];
 const labels=boxes.map(box=>({style:{},getBoundingClientRect:()=>({...box,width:20,height:10})}));context.labelDiv={querySelectorAll:()=>labels};
 vm.runInContext('tidyLabels(labelDiv)',context);assert.equal(labels[1].style.visibility,'hidden');
 boxes[1].left=40;boxes[1].right=60;vm.runInContext('tidyLabels(labelDiv)',context);assert.equal(labels[1].style.visibility,'visible');
 assert(document.fullscreenElement);assert(reacts>5);
}
(async()=>{await harness(false);await harness('zero');await harness('intersection');console.log('Overlay changes, median/day navigation, concise legends, hidden tabs, font readiness, serialized resize and label reset passed.');})().catch(error=>{console.error(error);process.exitCode=1;});
