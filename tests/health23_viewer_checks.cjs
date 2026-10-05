const fs=require('fs'),vm=require('vm'),assert=require('assert');
const {harness,storage,renderedCustom}=require('./health17_viewer_checks.cjs');
const sources=process.argv.slice(2,5).map(p=>fs.readFileSync(p,'utf8'));
const run=(h,code)=>vm.runInContext(code,h.context);
(async()=>{
 for(const source of sources){
  storage.clear();const h=await harness(source),div=run(h,'graphs[1]');
  const select=h.ids['overlay-select'];assert.equal(select.value,'None');assert(select.children.length>10);
  select.value='Garmin · Heart rate';await select.handlers.change();await h.settle();
  assert.equal(run(h,'currentOverlay'),'Garmin · Heart rate');assert.equal(select.value,'Garmin · Heart rate');
  await h.ids.expand.handlers.click();await h.settle();
  select.value='IOB + Boluses';await select.handlers.change();await h.settle();
  assert.equal(run(h,'currentOverlay'),'IOB + Boluses');assert(h.context.document.fullscreenElement);
  await h.ids.expand.handlers.click();await h.settle();
  const marker=run(h,'highlights[1]'),card=h.ids['hover-card'],floating=run(h,'floatingCard');
  // Actual SVG glyph bounds include standoff/angle. Select by original point index,
  // even when missing values mean rendered glyph order is different.
  div.getBoundingClientRect=()=>({left:100,top:200,width:900,height:300});
  let rect={left:300,right:324,top:330,bottom:354,width:24,height:24};
  const glyph={__data__:{i:4},getBoundingClientRect:()=>rect};
  div.querySelectorAll=()=>[{classList:{contains:name=>name==='traceevent'},querySelectorAll:()=>[{__data__:{i:0},getBoundingClientRect:()=>({})},glyph]}];
  card.getBoundingClientRect=()=>({top:0,bottom:40,left:500,right:990,width:490,height:40});
  h.context.window.innerWidth=1000;h.context.window.innerHeight=1040;
  const host={innerHeight:800,innerWidth:1200};host.parent=host;
  h.context.window.parent=host;h.context.window.frameElement={parentElement:null,getBoundingClientRect:()=>({left:100,top:-300})};
  const sample=(kind,label,y,size=24,extra={})=>({points:[{x:600,y,pointNumber:4,curveNumber:0,
    data:{type:'scatter',meta:{kind,label,unit:kind==='carbs'?'g':'U',...extra}},
    fullData:{uid:'event',marker:{size,standoff:14,angle:180,symbol:'triangle-up',line:{width:0}}},
    xaxis:div._fullLayout.xaxis,yaxis:div._fullLayout.yaxis,customdata:extra.baseline_smb?['recorded',.3]:null}]});
  div.handlers.plotly_hover(sample('bolus','SMB',0,24,{baseline_smb:true}));await h.settle();
  assert.equal(marker.style.left,'212px');assert.equal(marker.style.top,'142px');assert.equal(marker.style.width,'28px');assert.equal(marker.style.borderRadius,'3px');
  assert.equal(card.children.length,0);assert(floating.children.some(n=>n.textContent==='0.3 U'));
  assert.equal(floating.hidden,false);assert.equal(floating.parentElement,div);assert.equal(floating.style.top,'100px');
  // Scrolling the outer page changes clipping, not data selection or plotted traces.
  h.context.window.frameElement.getBoundingClientRect=()=>({left:100,top:-450});run(h,'scheduleHoverReadout()');await h.settle();
  assert.equal(floating.style.top,'100px');assert.equal(card.children.length,0);
  for(const [kind,label,value] of [['bolus','User bolus',3.5],['carbs','Carbs',42]]){
    rect={left:400,right:434,top:250,bottom:270,width:34,height:20};
    div.handlers.plotly_hover(sample(kind,label,value));await h.settle();
    assert.equal(marker.style.left,'317px');assert.equal(marker.style.top,'60px');
    assert.equal(card.children.length,0);assert.equal(floating.children[0].textContent,label);
    assert.equal(floating.children[1].textContent,value+(kind==='carbs'?' g':' U'));
  }
  // Same point: no DOM replacement/animation restart. Hover does not redraw Plotly.
  const valueNode=floating.children[1],renderCount=renderedCustom.length;
  div.handlers.plotly_hover(sample('carbs','Carbs',42));await h.settle();assert.equal(floating.children[1],valueNode);assert.equal(renderedCustom.length,renderCount);
  h.context.document.fullscreenElement=true;run(h,'positionHoverReadout()');assert(!floating.hidden,'In-graph readout remains visible in fullscreen');
  h.context.document.fullscreenElement=false;
  h.ids.panels.handlers.scroll();assert(floating.hidden);assert.equal(marker.style.display,'none');
  assert.equal(card.textContent,'');assert.equal(h.races(),0);
 }
 fs.writeFileSync(process.argv[5],JSON.stringify(renderedCustom));console.log('Health-23 rendered selection, floating readout and dropdown checks passed');
})().catch(e=>{console.error(e);process.exit(1)});
