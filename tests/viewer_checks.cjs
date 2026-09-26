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
  appendChild(x){this.children=this.children.filter(v=>v!==x);this.children.push(x);return x;} replaceChildren(){this.children=[];this.textContent='';}
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
 assert.equal(plots.length,10);assert(plots.every(p=>p.layout.width===1000));
 assert.equal(ids['overlay-select'].children.length,7);
 assert.equal(ids['overlay-select'].children[0]['aria-pressed'],'true');
 assert(ids['profile-target-note'].hidden);
 await ids.expand.handlers.click();await settle();assert(document.fullscreenElement);
 plots[0]._fullLayout.xaxis.range=[360,720];
 async function overlay(value) {await ids['overlay-select'].children.find(b=>b.value===value).handlers.click();await settle();assert(document.fullscreenElement);assert.deepEqual(plots[0]._fullLayout.xaxis.range,[360,720]);}
 const custom=plots.find(p=>p.layout.meta?.kind==='custom');
 const fieldButtons=vm.runInContext('customButtons',context);
 const customScale=vm.runInContext('customScaleButton',context);
 const pick=async id=>{await fieldButtons.find(b=>b.value===id).handlers.click();await settle();assert(document.fullscreenElement);};
 const icChoice=fieldButtons.find(b=>b.value==='profile:ic:0');
 assert.equal(icChoice.children[0].style.color,'#ff9800');
 assert.equal(icChoice.children[1].style.color,'#ff9bc9');
 assert.equal(icChoice.children[1].textContent,'LenStandardV17');
 assert.equal(icChoice.children[2].textContent,' · Ref 2');
 assert.equal(custom.layout.yaxis.color,'#32cd32');
 assert.equal(custom.layout.yaxis.title.text,'mmol/L');assert.deepEqual(custom.layout.yaxis.range,[0,20]);
 await pick('ns:iob');await customScale.handlers.click();await settle();
 assert.deepEqual(custom.layout.yaxis.range,custom.layout.yaxis2.range);
 await pick('ns:cob');assert(customScale.hidden);assert(custom.layout.yaxis3);
 assert.equal(custom.layout.yaxis3.title.text,'g');
 await pick('ns:iob');await pick('ns:cob');await pick('profile:ic:0');
 assert(!customScale.hidden);assert.equal(custom.layout.yaxis2.title.text,'g/U');assert.equal(custom.layout.yaxis2.color,'#ff9800');
 assert(custom.data.some(t=>t.meta?.kind==='profile' && t.name.includes('I:C')));
 await pick('profile:ic:0');await pick('ns:carbs');
 const customCarbs=custom.data.find(t=>t.type==='bar');assert.equal(customCarbs.y[5],10);assert.equal(customCarbs.customdata[5],3);
 assert.equal(custom.layout.yaxis2.title.text,'g');
 // Source changes do not leak into the pinned graph or its independent same-scale control.
 assert(!plots[0].layout.yaxis2);assert.equal(ids['same-scale']['aria-pressed'],'false');
 const bolus=plots.find(p=>p.layout.meta?.dataset==='bolus' && p.layout.meta?.kind==='hourly');
 const smbButton=vm.runInContext('bolusButtons[0]',context);
 const hourlyToggle=vm.runInContext('hourlyButtons.find(b=>b.value==="bolus")',context);
 const originalHeat=JSON.stringify(bolus.data[0]);
 const originalBars=JSON.stringify(bolus.data[1].y);
 assert.equal(bolus.layout.yaxis2.title.text,'Average U');
 await hourlyToggle.handlers.click();await settle();
 const medianBars=JSON.stringify(bolus.data[1].y);
 assert.equal(bolus.layout.yaxis2.title.text,'Median U');assert.equal(JSON.stringify(bolus.data[0]),originalHeat);
 assert.notEqual(JSON.stringify(bolus.data[1].y),originalBars,'Mean differs from median for an asymmetric sample');
 function assertMean(panel) {
   const grid=panel.data[0],bars=panel.data[1];
   for(let h=0;h<24;h++) {
     const values=grid.z.map((row,i)=>grid.customdata[i][h][5]?row[h]:null).filter(Number.isFinite);
     assert.equal(bars.y[h],values.length?values.reduce((a,b)=>a+b,0)/values.length:null);
   }
 }
 await hourlyToggle.handlers.click();await settle();assert.equal(JSON.stringify(bolus.data[1].y),originalBars);
 assertMean(bolus);
 await smbButton.handlers.click();await settle();assertMean(bolus);assert.equal(bolus.layout.yaxis2.title.text,'Average U');
 await smbButton.handlers.click();await settle();assertMean(bolus);
 await hourlyToggle.handlers.click();await settle();assert.equal(JSON.stringify(bolus.data[1].y),medianBars);
 const carbPanel=plots.find(p=>p.layout.meta?.kind==='hourly' && p.layout.meta.dataset==='carbs');
 const carbToggle=vm.runInContext('hourlyButtons.find(b=>b.value==="carbs")',context);
 const carbGrid=JSON.stringify(carbPanel.data[0]);
 assertMean(carbPanel);await carbToggle.handlers.click();await settle();assert.equal(carbPanel.layout.yaxis2.title.text,'Median g');
 await carbToggle.handlers.click();await settle();assertMean(carbPanel);assert.equal(JSON.stringify(carbPanel.data[0]),carbGrid);
 assert.equal(carbPanel.layout.yaxis2.title.text,'Average g');assert.equal(bolus.layout.yaxis2.title.text,'Median U');
 const allBolus=JSON.stringify(bolus.data);
 await smbButton.handlers.click();await settle();assert.equal(smbButton['aria-pressed'],'true');
 assert(bolus.layout.title.text.includes('no SMB'));assert.notEqual(JSON.stringify(bolus.data),allBolus);
 const heat=bolus.data[0],bars=bolus.data[1];
 for(let h=0;h<24;h++) {
   const values=heat.z.map((row,i)=>heat.customdata[i][h][5]?row[h]:null).filter(v=>v!==null).sort((a,b)=>a-b);
   const mid=Math.floor(values.length/2),median=values.length?(values.length%2?values[mid]:(values[mid-1]+values[mid])/2):null;
   assert.equal(bars.y[h],median);
 }
 await smbButton.handlers.click();await settle();assert.equal(JSON.stringify(bolus.data),allBolus);
 assert(plots.every(p=>p.layout.height>=285));
 assert(plots.every(p=>p.layout.shapes.some(s=>s.name==='Profile change' && s.x0===600)));
 const variablePanel=plots.find(p=>p.layout.meta?.dataset==='variable_sens');
 assert.equal(variablePanel.layout.yaxis.title.text,'mmol/L/U');
 const beforeOrder=vm.runInContext('panelOrder.slice()',context);
 await vm.runInContext('moveButtons.find(b=>b.index===2 && b.direction===-1).button.handlers.click()',context);await settle();
 const changedOrder=vm.runInContext('panelOrder.slice()',context);
 assert.equal(changedOrder[0],2);assert.equal(changedOrder[1],1);
 assert.equal(ids.panels.children.length,plots.length-1);
 await overlay('Variable sensitivity');assert.equal(plots[0].layout.yaxis2.title.text,'mmol/L/U');
 const scale=ids['same-scale'];await scale.handlers.click();await settle();
 assert.deepEqual(plots[0].layout.yaxis.range,plots[0].layout.yaxis2.range);
 await overlay('IOB + boluses');assert.deepEqual(plots[0].layout.yaxis.range,plots[0].layout.yaxis2.range);
 await scale.handlers.click();await settle();assert(plots[0].layout.yaxis.autorange);
 await overlay('Variable sensitivity');assert.equal(plots[0].layout.yaxis2.title.text,'mmol/L/U');
 assert.deepEqual(vm.runInContext('panelOrder.slice()',context),changedOrder);
 await overlay('Nightscout targets');assert.deepEqual(plots[0].layout.yaxis2.range,[0,20]);
 const lower=plots.slice(1).map(p=>JSON.stringify(p.data));
 await overlay('Glucose');assert(plots[0].data.some(t=>t.meta?.kind==='median'),'Initial median mode is preserved');
 assert.equal(plots[0].layout.yaxis2.range[1],20);
 assert(!ids['profile-target-note'].hidden);assert(ids['profile-target-note'].textContent.includes('historical profile'));
 assert(plots[0].data.some(t=>t.meta?.kind==='target_fill' && t.fill==='toself'));
 await ids['show-targets'].handlers.click();await settle();assert(ids['profile-target-note'].hidden);assert(!plots[0].data.some(t=>t.meta?.kind==='target'));
 await overlay('None');await overlay('Glucose');assert(!plots[0].data.some(t=>t.meta?.kind==='target'));
 await ids['show-targets'].handlers.click();await settle();assert(!ids['profile-target-note'].hidden);
 await overlay('IOB + boluses');assert(plots[0].data.some(t=>t.meta?.kind==='median' && t.meta.dataset==='iob'));assert(!plots[0].data.some(t=>t.meta?.kind==='bolus'));
 assert.deepEqual(plots.slice(1).map(p=>JSON.stringify(p.data)),lower,'Changing overlay leaves other panels unchanged');
 await smbButton.handlers.click();await settle();
 await ids['next-day'].handlers.click();await settle();
 assert(bolus.layout.title.text.includes('no SMB'));assert.equal(bolus.data[0].y.length,1);
 assert(hourlyToggle.disabled);assert.equal(hourlyToggle.textContent,'Bars: selected day');
 assert(custom.layout.title.text.includes('2026-09-16'));
 assert(custom.data.some(t=>t.meta?.kind==='carbs' && t.y.includes(30)));
 assert(!custom.data.some(t=>t.type==='bar'));
 assert(custom.data.filter(t=>t.meta?.date).every(t=>t.meta.date==='2026-09-16'));
 assert.equal(ids['day-label'].textContent,'2026-09-16'); // wraps after last selected day
 assert(ids['summary-title'].textContent.includes('In range 100%'));
 const hourly=plots.find(p=>p.layout.meta?.dataset==='carbs' && p.layout.meta?.kind==='hourly');
 assert(hourly);assert.equal(hourly.data[0].y[0],'2026-09-16');assert.equal(hourly.data[0].z[0][5],30);assert.equal(hourly.data[1].y[5],30);
 await overlay('COB + carbs');assert(plots[0].layout.yaxis2.autorangeoptions.include>=36);assert(plots[0].data.find(t=>t.meta?.kind==='carbs').cliponaxis===false);assert(plots[0].data.some(t=>t.meta?.kind==='cob'));assert(plots[0].data.some(t=>t.meta?.kind==='carbs'));
 assert(plots[0].data.filter(t=>t.meta?.date).every(t=>t.meta.date==='2026-09-16'));
 await ids['next-day'].handlers.click();await settle();assert.equal(ids['day-label'].textContent,'2026-09-17');
 assert.deepEqual(vm.runInContext('panelOrder.slice()',context),changedOrder);
 assert(!plots[0].layout.yaxis2.autorangeoptions,'Clear padding from the previous day when no labeled events remain');
 await overlay('Glucose');assert(plots[0].data.some(t=>t.meta?.kind==='glucose'));assert(!plots[0].data.some(t=>t.meta?.kind==='median'));
 assert(plots[0].data.find(t=>t.meta?.kind==='glucose').showlegend,'Rebuild legend after filtering to a later day');
 await overlay('Nightscout targets');assert.deepEqual(plots[0].layout.yaxis2.range,[0,20]);
 await overlay('None');assert(ids['profile-target-note'].hidden);assert(!plots[0].layout.yaxis2);assert(plots[0].data.every(t=>!t.meta?.date));
 assert.equal(plots[0].layout.yaxis.rangemode,'normal');
 assert(plots.every(p=>p.layout.title.text.includes('2026-09-17')));
 await ids['previous-day'].handlers.click();await settle();assert.equal(ids['day-label'].textContent,'2026-09-16');
 await ids['day-label'].handlers.click();
 const calendarButtons=ids['date-calendar'].children.flatMap(c=>c.children).filter(c=>c.title);
 assert(calendarButtons.some(b=>b.disabled));
 const chosen=calendarButtons.find(b=>b.title.startsWith('2026-09-17'));
 await chosen.handlers.click();await settle();assert.equal(ids['day-label'].textContent,'2026-09-17');
 assert(bolus.layout.title.text.includes('no SMB'));assert(document.fullscreenElement);
 // Local day navigation must preserve the target panel's fixed range, including empty days.
 const targetSpec={data:[],layout:{title:{text:'Temp targets · 2026-09-16'},xaxis:{range:[0,1440]},yaxis:{range:[0,20]},height:285}};
 context.targetSpec=targetSpec;
 assert.deepEqual(vm.runInContext("dailyView(targetSpec,1,'2026-09-17',[0,1440]).layout.yaxis.range",context),[0,20]);
 // Profile tabs and local overlay controls keep fullscreen, zoom, date and SMB state.
 assert.equal(ids['metric-select'].children.length,4);
 const changeMetricButton=ids['metric-select'].children.find(b=>b.value==='isf');
 await changeMetricButton.handlers.click();await settle();
 assert(plots[0].layout.title.text.startsWith('ISF ·'));
 assert.equal(plots[0].layout.yaxis.title.text,'mmol/L/U');
 assert.deepEqual(plots[0]._fullLayout.xaxis.range,[360,720]);
 assert.equal(ids['day-label'].textContent,'2026-09-17');
 assert(plots.every(p=>p.layout.shapes.some(s=>s.name==='Profile change' && s.x0===800)));
 assert(plots.every(p=>!p.layout.shapes.some(s=>s.name==='Profile change' && s.x0===600)));
 await overlay('Glucose');assert(plots[0].layout.title.text.startsWith('ISF ·'));
 await overlay('Variable sensitivity');
 await ids['previous-day'].handlers.click();await settle();
 assert.equal(plots[0].layout.yaxis2.title.text,'mmol/L/U');
 assert(plots[0].data.some(t=>t.meta?.kind==='variable_sens' && t.y.includes(5)));
 assert(plots[0].layout.title.text.startsWith('ISF ·'));
 assert(bolus.layout.title.text.includes('no SMB'));assert(document.fullscreenElement);
 await pick('ns:carbs');await pick('ns:glucose');
 assert.equal(custom.data.length,0);assert(custom.layout.annotations[0].text.includes('Choose fields'));
 assert(!custom.layout.yaxis2);assert.equal(custom.layout.xaxis.domain[1],1);
 await pick('profile:target:0');
 assert(custom.data.some(t=>t.meta?.kind==='profile'));assert.equal(custom.layout.annotations.length,0);
 await pick('ns:variable_sens');assert.equal(custom.layout.yaxis2.title.text,'mmol/L/U');
 await customScale.handlers.click();await settle();assert.deepEqual(custom.layout.yaxis.range,custom.layout.yaxis2.range);
 await ids['next-day'].handlers.click();await settle();
 assert(custom.data.some(t=>t.meta?.kind==='profile'));assert(!custom.data.some(t=>t.meta?.kind==='variable_sens'));
 assert.deepEqual(custom.layout.yaxis.range,custom.layout.yaxis2.range);
 // All fields remain selectable together; free axes stay within the plot's paper domain.
 for(const button of fieldButtons)if(button['aria-pressed']!=='true')await pick(button.value);
 const axes=Object.entries(custom.layout).filter(([key])=>/^yaxis\d*$/.test(key));
 assert(axes.length>=7);assert(customScale.hidden);
 const positions=axes.slice(1).map(([,axis])=>axis.position);
 assert(positions.every(p=>p>=0 && p<=1));assert.equal(new Set(axes.map(([,a])=>a.side+':'+a.shift)).size,axes.length);
 assert(axes.some(([,a])=>a.side==='left' && a.shift<0));assert(axes.some(([,a])=>a.side==='right' && a.shift>0));
 assert.equal(custom.layout.xaxis.domain[1],1);
 assert(custom.layout.margin.l+custom.layout.margin.r<=54*axes.length);
 assert(custom.layout.xaxis.domain[1]>=.35);
 const allCustomFields=custom.data.filter(t=>t.meta?.kind==='profile');assert(allCustomFields.length>=4);
 // Hide/show and concurrent resize/change requests must not overlap Plotly calls.
 width=0;observers.forEach(f=>f());await settle();
 width=780;const change=ids['overlay-select'].children.find(b=>b.value==='IOB + boluses').handlers.click();observers.forEach(f=>f());
 await change;await settle();assert.equal(races,0);assert(plots.every(p=>p.layout.width===780));
 const boxes=[{left:10,right:30,top:10,bottom:20},{left:15,right:35,top:10,bottom:20},{left:80,right:100,top:10,bottom:20}];
 const labels=boxes.map(box=>({style:{},getBoundingClientRect:()=>({...box,width:20,height:10})}));context.labelDiv={querySelectorAll:()=>labels};
 vm.runInContext('tidyLabels(labelDiv)',context);assert.equal(labels[1].style.visibility,'hidden');
 boxes[1].left=40;boxes[1].right=60;vm.runInContext('tidyLabels(labelDiv)',context);assert.equal(labels[1].style.visibility,'visible');
 assert(document.fullscreenElement);assert(reacts>5);
}
(async()=>{await harness(false);await harness('zero');await harness('intersection');if(process.argv[3])fs.writeFileSync(process.argv[3],JSON.stringify(renderedCustom));console.log('Overlay changes, median/day navigation, concise legends, hidden tabs, font readiness, serialized resize and label reset passed.');})().catch(error=>{console.error(error);process.exitCode=1;});
