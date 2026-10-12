// Report requests capture browser-owned settings; generation uses loaded data only.
function setupReportControls(){
  if(!navigation || navigation.report_render)return;
  const toolbar=expand.parentElement || document.getElementById('toolbar-left');if(!toolbar)return;
  const details=document.createElement('details');details.className='report-controls';
  const summary=document.createElement('summary');summary.textContent='Export report';details.appendChild(summary);
  const form=document.createElement('div');form.className='report-options';details.appendChild(form);
  const input=(label,type,value)=>{const wrap=document.createElement('label');wrap.textContent=label;const el=document.createElement('input');el.type=type;el.value=value;wrap.appendChild(el);form.appendChild(wrap);return el;};
  const title=input('Title','text','Profile Studio report');title.maxLength=120;
  const first=input('From date','date',selectedDays[0] || navigation.source_first),last=input('Through date','date',selectedDays[selectedDays.length-1] || navigation.source_last);
  for(const el of [first,last]){el.min=navigation.source_first;el.max=navigation.source_last;}
  const begin=input('Daily start (HH:MM)','text','00:00'),end=input('Daily end (HH:MM)','text','24:00');
  const select=(label,options)=>{const wrap=document.createElement('label');wrap.textContent=label;const el=document.createElement('select');for(const [value,text] of options){const o=document.createElement('option');o.value=value;o.textContent=text;el.appendChild(o);}wrap.appendChild(el);form.appendChild(wrap);return el;};
  const layout=select('Page layout',[['landscape','Landscape'],['portrait','Portrait · vertical stack']]);
  const count=select('Graphs per page',[1,2,3,4,5,6].map(n=>[String(n),String(n)]));count.value='2';
  const sections=[];
  for(const [key,text] of [['overview','Overview'],['profiles','Base profiles'],['median','Median graphs'],['statistics','Daily statistics'],['daily','Daily graphs'],['overlay','All days overlaid'],['distribution','Glucose distribution']]){
    const el=input(text,'checkbox','');el.checked=true;sections.push({key,el});
  }
  const note=document.createElement('p');note.textContent='Selected graph layers, order and filters are retained. Graphs stack vertically in either page orientation. Multi-panel sleep graphs use extra slots to keep their axes readable. Open the downloaded preview, then Print / Save as PDF.';form.appendChild(note);
  const status=document.createElement('p');status.setAttribute('role','status');form.appendChild(status);
  const snapshot=()=>({title:title.value,first:first.value,last:last.value,from_time:begin.value,until_time:end.value,layout:layout.value,graphs_per_page:Number(count.value),sections:sections.filter(s=>s.el.checked && !s.el.disabled).map(s=>s.key)});
  const button=document.createElement('button');button.type='button';button.textContent='Prepare report';form.appendChild(button);
  const validate=()=>{
    const dates=first.value && last.value && first.value<=last.value && first.value>=navigation.source_first && last.value<=navigation.source_last;
    const multiple=dates && first.value<last.value;
    const minutes=v=>/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(v)?Number(v.slice(0,2))*60+Number(v.slice(3)):v==='24:00'?1440:NaN;
    const times=minutes(begin.value)<minutes(end.value);
    const tooLong=dates && (Date.parse(last.value)-Date.parse(first.value))/86400000>365;
    for(const {key,el} of sections){
      const available=(!['median','overlay'].includes(key)||multiple) && (!['profiles'].includes(key)||navigation.report_capabilities?.profiles!==false) && (!['overview','statistics','distribution'].includes(key)||navigation.has_nightscout!==false) && (!['daily','median','overlay'].includes(key)||navigation.layers?.length || !dataOnly);
      el.disabled=!available;if(!available)el.checked=false;
      el.parentElement.title=available?'':(['median','overlay'].includes(key)?'Select at least two days.':'Required data is not loaded.');
    }
    button.disabled=!dates || !times || tooLong || !snapshot().sections.length;
    status.textContent=!dates?'Choose dates within the loaded range.':tooLong?'Choose up to 366 days.':!times?'Use an increasing daily time window (HH:MM).':!multiple?'Single day: median and multi-day sections are unavailable.':(Date.parse(last.value)-Date.parse(first.value))/86400000>=90?'Long-range daily reports can contain hundreds of pages; charts are prepared sequentially.':'';
  };
  for(const el of [first,last,begin,end,...sections.map(s=>s.el)])el.addEventListener('change',validate);
  const preset=select('Saved PDF settings',[['','Choose preset'],...(navigation.report_presets || []).map((p,i)=>[String(i),p.name])]);
  const presetName=input('Preset name','text','');presetName.maxLength=80;
  preset.addEventListener('change',()=>{
    const p=navigation.report_presets?.[Number(preset.value)];if(preset.value==='' || !p)return;
    const v=p.settings;title.value=v.title;layout.value=v.layout;count.value=String(v.graphs_per_page);begin.value=v.from_time;end.value=v.until_time;
    first.value=v.first || first.value;last.value=v.last || last.value;presetName.value=p.name;
    for(const s of sections)s.el.checked=v.sections.includes(s.key);validate();
  });
  const save=document.createElement('button');save.type='button';save.textContent='Save PDF settings';form.appendChild(save);
  save.addEventListener('click',()=>{
    if(!presetName.value.trim()){status.textContent='Enter a preset name.';return;}
    window.parent.postMessage({type:'profile-studio:report',request:{id:crypto.randomUUID(),kind:'report-preset',name:presetName.value.trim(),settings:snapshot()}},'*');status.textContent='Saving PDF settings…';
  });
  button.addEventListener('click',()=>{
    validate();if(!ready || syncing || button.disabled)return;
    const request={...snapshot(),id:crypto.randomUUID(),kind:'report',config:viewerSettings(),layers:navigation.layers};
    window.parent.postMessage({type:'profile-studio:report',request},'*');details.open=false;card.textContent='Preparing report. The download will appear below the graphs.';
  });
  validate();
  toolbar.appendChild(details);
}
function reportSleepViews(graph,options){
  const dates=[...new Set((graph.data || []).filter(t=>t.meta?.kind==='garmin_sleep').map(t=>t.meta.date))].sort();
  if(graph.layout.meta?.dataset!=='g_sleep' || dates.length<2)return [{data:graph.data,layout:graph.layout}];
  const settings=displayOptions(graph.layout),rows=settings.sleepOverlay?0:(settings.sleepFields || []).length;
  const available=Math.max(navigation?.sleep_day_height || 28,(options.height || 400)*(options.capacity || 1)-150-rows*100);
  const perPage=Math.max(1,Math.floor(available/(navigation?.sleep_day_height || 28)));
  if(dates.length<=perPage)return [{data:graph.data,layout:graph.layout}];
  const views=[];
  for(let at=0;at<dates.length;at+=perPage){
    const chosen=dates.slice(at,at+perPage),set=new Set(chosen),view=JSON.parse(JSON.stringify({data:graph.data,layout:graph.layout}));
    view.data=view.data.filter(t=>(!t.meta?.date || set.has(t.meta.date)) && !['profile_event','automation_note'].includes(t.meta?.kind));
    const before=selectedDays;
    try{selectedDays=chosen;composeSleep(view);garminAxes(view);
      for(const shape of view.layout.shapes || [])if(shape.name==='Profile change'){shape.y0=0;shape.y1=1;}
      applyActivityShading(view);applyChangeEvents(view);applyProfileEvents(view);applyAutomationNotes(view);
    }finally{selectedDays=before;}
    const belongs=item=>{const date=item.name?.split(' | ')[1];return !/^\d{4}-\d{2}-\d{2}$/.test(date || '') || set.has(date);};
    view.layout.shapes=(view.layout.shapes || []).filter(belongs);view.layout.annotations=(view.layout.annotations || []).filter(belongs);
    view.layout.title={...view.layout.title,text:'Sleep · '+chosen[0]+' – '+chosen.at(-1)};views.push(view);
  }
  return views;
}
function reportInsightNoteSize(text,width){
  if(!text)return 0;
  const el=document.createElement('div');el.textContent=text;
  el.style.cssText='position:absolute;visibility:hidden;font:8px/1.2 Arial,sans-serif;padding:2px 0 0;margin:0;white-space:normal;box-sizing:border-box;width:'+width+'px';
  document.body.appendChild(el);const height=Math.ceil(el.getBoundingClientRect().height);el.remove();
  return height*25.4/96;
}
async function exportReportFigures(){
  const options=navigation.report_render;if(!options)return;
  try {
    await setTimeRange(options.range);
    const result=[];
    for(const index of [...(dataOnly?[]:[0]),...panelOrder]){
      if(panelStateAt(index).deleted)continue;
      const g=graphs[index];
      for(const view of reportSleepViews(g,options)){
      const layout=JSON.parse(JSON.stringify(view.layout));
      const meaningful=(view.data || []).some(t=>t.visible!==false && t.visible!=='legendonly' && !t.meta?.legend_proxy && !['profile_event','automation_note'].includes(t.meta?.kind) && t.hoverinfo!=='skip' &&
        (t.type==='heatmap'?(t.z || []).flat().some(Number.isFinite):(t.y || []).some(Number.isFinite)));
      if(!meaningful || layout.meta?.empty)continue;
      const note=layout.meta?.kind==='insight'?layout.meta.insight_note || '':'';
      const dense=Boolean(note) && (options.capacity || 1)>=5;
      const noteMM=reportInsightNoteSize(note,options.note_width || 263*96/25.4);
      const notePixels=noteMM*(options.width || 1320)/(options.note_width || 263*96/25.4)*96/25.4;
      const rows=new Set(Object.entries(layout).filter(([k,v])=>/^yaxis[0-9]*$/.test(k) && v.domain && !v.overlaying).map(([,v])=>JSON.stringify(v.domain))).size;
      const levels=layout.meta?.profile_label_levels || 0;
      const eventHeight=levels?64+Math.max(0,levels-1)*18+45+Math.max(0,levels-1)*16+100*Math.max(1,(layout.meta.percentage_max || 100)/100):0;
      const sleepTimeline=layout.meta?.dataset==='g_sleep' && view.data.some(t=>t.meta?.kind==='garmin_sleep');
      const required=Math.max(eventHeight,sleepTimeline?layout.height:rows>1?rows*100+100:0);
      const slots=Math.min(options.capacity || 1,Math.max(1,Math.ceil(required/(options.height || 400))));
      layout.height=Math.round((options.height || 400)*slots-notePixels);layout.width=options.width || 1320;
      layout.margin={...layout.margin,t:options.compact?25:35,b:Math.max(layout.margin?.b || 0,options.compact?40:55)};
      layout.title={...layout.title,font:{size:options.compact?12:16}};
      layout.legend={...layout.legend,font:{size:options.compact?9:11},y:-.22,itemsizing:'constant'};
      if(dense){
        // Dense pages need less chrome as well as smaller charts; resize the
        // actual Plotly plot so neither data nor the method note is cropped.
        layout.margin={...layout.margin,t:20,b:48,autoexpand:false};
        layout.title.font.size=11;
        layout.legend={...layout.legend,...(!levels?{yref:'container',y:0,yanchor:'bottom'}:{}),font:{size:8}};
      }
      profileEventLayout(layout);
      layout.paper_bgcolor='#ffffff';layout.plot_bgcolor='#ffffff';layout.font={...layout.font,color:'#24354b',size:options.compact?11:15};
      if(options.compact && layout.meta?.dataset==='g_sleep'){
        const hourly=view.data.find(t=>t.meta?.sleep_variant==='hourly');
        if(hourly)layout.yaxis.title={...layout.yaxis.title,text:hourly.meta.aggregation+' h/h'};
      }
      for(const key of Object.keys(layout).filter(k=>/^[xy]axis[0-9]*$/.test(k))){
        const axis=layout[key];axis.tickfont={...axis.tickfont,size:dense?8:options.compact?10:13};axis.gridcolor='#dce4eb';axis.linecolor='#b5c0cb';
        if(axis.title){axis.title.font={...axis.title.font,size:dense?9:options.compact?11:13};}
        if(dense){
          axis.automargin=false;if(key.startsWith('y'))axis.nticks=3;
          if(axis.title)axis.title.standoff=0;
          // The note already names the alignment/relationship. Put the units
          // on dense insight X ticks so a long title cannot collide with them.
          if(key==='xaxis' && layout.meta?.kind==='insight'){
            axis.title={text:''};axis.ticksuffix=' '+(layout.meta.insight_relationship?view.data.find(t=>t.meta?.kind==='insight_relationship')?.meta.x_unit || '':'h');
          }
        }
      }
      const holder=document.createElement('div');holder.style.width=layout.width+'px';document.getElementById('viewer').appendChild(holder);
      try {
        await Plotly.newPlot(holder,view.data,layout,{staticPlot:true});await reflowProfileLabels(holder);
        const url=await Plotly.toImage(holder,{format:'svg',width:layout.width,height:layout.height});
        let title=layout.title?.text || 'Graph';
        if(layout.meta?.kind==='custom'){
          const fields=[...customState(layout.meta.custom_id).selected].map(id=>customFields.find(f=>f.id===id)?.label).filter(Boolean);
          title='Custom '+layout.meta.custom_id.replace('custom-','')+' — '+fields.slice(0,4).join(', ')+(fields.length>4?' + '+(fields.length-4)+' more':'');
        }
        result.push({title,height:layout.height,slots,url,note,note_mm:noteMM});
      }finally{Plotly.purge(holder);holder.remove();}
      }
    }
    window.parent.postMessage({type:'profile-studio:report-rendered',id:options.id,figures:result},'*');
  }catch(error){window.parent.postMessage({type:'profile-studio:report-rendered',id:options.id,error:String(error)},'*');}
}
