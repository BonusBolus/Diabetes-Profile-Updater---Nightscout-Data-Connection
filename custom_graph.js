// Custom graphs reuse dated traces; selections never leave fullscreen or fetch data.
const customFields=navigation?.custom?.fields || [];
let customSelected=new Set(navigation?.custom?.selected || []),customSameScale=false;
const customButtons=[];
let customScaleButton=null,customStatus=null;
function setupCustomControls(bar) {
  const details=document.createElement('details'),summary=document.createElement('summary');
  summary.textContent='Choose custom data';details.appendChild(summary);bar.appendChild(details);
  for(const group of ['Nightscout','Profiles']) {
    const options=document.createElement('div');options.className='custom-options';
    const label=document.createElement('strong');label.textContent=group;options.appendChild(label);
    customFields.filter(f=>f.group===group).forEach(field=>{
      const button=document.createElement('button');button.type='button';button.value=field.id;button.setAttribute('aria-label',field.label);
      button.style.borderLeft='3px solid '+(field.metric_color || field.color);
      if(field.group==='Profiles') {
        const setting=document.createElement('span');setting.textContent=field.metric_label+' · ';setting.style.color=field.metric_color;setting.style.fontWeight='600';button.appendChild(setting);
        const source=document.createElement('span');source.textContent=field.profile_name;source.style.color=field.source_color;button.appendChild(source);
        const role=document.createElement('small');role.textContent=field.source_role==='ref1'?' · Ref 1':field.source_role==='ref2'?' · Ref 2':' · Current';role.style.color=field.source_color;button.appendChild(role);
      } else {button.textContent=field.label;button.style.color=field.color;}
      button.addEventListener('click',()=>changeCustom(field.id));customButtons.push(button);options.appendChild(button);
    });details.appendChild(options);
  }
  customScaleButton=document.createElement('button');customScaleButton.type='button';
  customScaleButton.title='Match numeric limits, without converting units. With one unit the scale is already shared.';
  customScaleButton.addEventListener('click',()=>changeCustom(null));bar.appendChild(customScaleButton);
  customStatus=document.createElement('span');customStatus.className='custom-help';bar.appendChild(customStatus);
}
function customControls() {
  customButtons.forEach(button=>{button.disabled=!ready || syncing;button.setAttribute('aria-pressed',String(customSelected.has(button.value)));});
  if(!customScaleButton)return;
  const fields=Array.from(customSelected,id=>customFields.find(f=>f.id===id)).filter(Boolean),units=new Set(fields.map(f=>f.unit));
  customScaleButton.hidden=fields.length===0 || fields.length>2;
  customScaleButton.disabled=!ready || syncing || units.size<2;
  customScaleButton.textContent=units.size===1?'Same axis scale: shared unit':'Same axis scale: '+(customSameScale?'on':'off');
  customScaleButton.setAttribute('aria-pressed',String(customSameScale && fields.length<=2));
  customStatus.textContent=fields.length+' selected · '+units.size+' unit scales; each axis follows its first selected dataset’s color. Profiles are current draft/reference schedules, not historical active settings. Median view: continuous medians; event bars are hourly averages. Selecting a day shows that day’s events.';
}
async function changeCustom(id) {
  if(!ready || syncing)return;
  return enqueue(async()=>{
    const previous=new Set(customSelected),previousScale=customSameScale;
    syncing=true;controls();clearHover();
    try {
      if(id===null)customSameScale=!customSameScale;
      else {if(customSelected.has(id))customSelected.delete(id);else customSelected.add(id);customSameScale=false;}
      const index=specs.findIndex(s=>s.layout.meta?.kind==='custom'),range=graphs[0]._fullLayout.xaxis.range.slice();
      const source=localSource(index),view=decorate(dateCycled?dailyView(source,index,selectedDays[0],range):source,index);
      view.layout=sizedLayout(view,index);view.layout.xaxis.range=range;view.layout.xaxis.autorange=false;
      await Plotly.react(graphs[index],view.data,view.layout);
    } catch(error){customSelected=previous;customSameScale=previousScale;card.textContent='Could not update the custom graph.';}
    finally{syncing=false;controls();}
  });
}
function composeCustom(view) {
  const fields=Array.from(customSelected,id=>customFields.find(f=>f.id===id)).filter(Boolean),units=[...new Set(fields.map(f=>f.unit))];
  const {layout}=view,day=layout.meta.custom_day;
  view.data=[];layout.annotations=[];
  // Rebuild axes from scratch so removed fields cannot leave axes or fill artifacts.
  Object.keys(layout).filter(k=>/^yaxis\d*$/.test(k)).forEach(k=>delete layout[k]);
  layout.shapes=(layout.shapes || []).filter(s=>s.name==='Profile change');
  layout.xaxis.domain=[0,1];
  customAxisLayout(layout,units.length);
  layout.title.text='Custom graph · '+(day || specs.find(s=>s.layout.meta?.kind==='custom').layout.title.text.split(' · ').slice(1).join(' · '));
  layout.barmode='overlay';
  units.forEach((unit,index)=>{
    const onAxis=fields.filter(f=>f.unit===unit),color=onAxis[0].color;
    const axis={title:{text:unit,font:{color,size:12},standoff:3},color,tickfont:{color,size:12},tickformat:'.3~g',
      showline:true,linecolor:color,linewidth:1,ticks:'outside',ticklen:3,tickcolor:color,automargin:true,
      showgrid:index===0,rangemode:'tozero',autorange:true};
    Object.assign(axis,customAxisPosition(index));
    if(unit!=='U/h' && onAxis.every(f=>f.dataset==='profile' || f.dataset==='variable_sens'))axis.rangemode='normal';
    layout['yaxis'+(index?index+1:'')]=axis;
  });
  for(const field of fields) {
    const index=units.indexOf(field.unit),axis='y'+(index?index+1:'');
    const traces=JSON.parse(JSON.stringify(day?field.daily:field.selected));
    for(const trace of traces.filter(t=>!day || !t.meta?.date || t.meta.date===day)) {
      trace.yaxis=axis;trace.xaxis='x';
      // Every field has its own legend group, including target low/high and negative IOB.
      trace.legendgroup=field.id+':'+(trace.legendgroup || trace.name);
      view.data.push(trace);
    }
    if(field.dataset==='target' && !fields.some(f=>f.dataset==='glucose'))Object.assign(layout['yaxis'+(index?index+1:'')],{range:[0,navigation.unit==='mmol/L'?20:360],autorange:false});
    if(field.dataset==='glucose') {
      const scale=navigation.unit==='mmol/L'?1:18;
      const glucose=view.data.filter(t=>t.meta?.kind==='glucose' || t.meta?.dataset==='glucose').flatMap(t=>t.y || []).filter(Number.isFinite);
      const peak=Math.max(0,...glucose),maximum=peak>20*scale?Math.ceil(peak*1.05/scale)*scale:20*scale;
      Object.assign(layout['yaxis'+(index?index+1:'')],{range:[0,maximum],autorange:false});
      layout.shapes.push({type:'rect',xref:'x',yref:axis,x0:0,x1:1440,y0:4*scale,y1:10*scale,line:{width:0},fillcolor:'rgba(50,205,50,.12)',layer:'below'});
    }
  }
  if(!units.length)layout.yaxis={visible:false};
  if(customSameScale && fields.length<=2 && units.length===2) {
    const values=[0,...view.data.flatMap(t=>t.y || []).filter(Number.isFinite),...units.flatMap((u,i)=>layout['yaxis'+(i?i+1:'')].range || [])];
    const low=Math.min(...values),high=Math.max(...values),span=Math.max(1,high-low);
    const range=[low<0?low-.05*span:0,high+.2*span];
    for(const name of ['yaxis','yaxis2'])Object.assign(layout[name],{range,autorange:false});
  }
  if(!view.data.some(t=>(t.y || []).some(Number.isFinite)))layout.annotations=[{text:fields.length?'No data for the selected fields and dates':'Choose fields above to build a custom graph',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false}];
}

// Fixed pixel lanes keep axes compact on wide screens and stable on resize.
function customAxisPosition(index) {
  const left=index%2===0,lane=Math.floor(index/2);
  return {anchor:'free',side:left?'left':'right',position:left?0:1,
          shift:(left?-1:1)*lane*54,...(index?{overlaying:'y'}:{})};
}
function customAxisLayout(layout,count) {
  const left=Math.ceil(count/2),right=Math.floor(count/2);
  layout.margin={...layout.margin,l:54+Math.max(0,left-1)*54,r:54+Math.max(0,right-1)*54};
}
