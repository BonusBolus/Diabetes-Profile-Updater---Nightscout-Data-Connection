// Blocks own report order; graph instances remain editable with the existing controls.
const REPORT_BLOCKS={overview:'Overview',profiles:'Base profiles',profile_graphs:'Graphical profile overview',statistics:'Daily statistics',distribution:'Glucose distribution',daily:'Daily graphs',summary:'Summary graphs',insights:'Insight graphs'};
let reportEditorBlock='daily',reportControlsRefresh=null;
function reportPresetViewer(settings){
  const viewer=JSON.parse(JSON.stringify(settings.viewer || {}));
  const panels=new Map((viewer.panels || []).map(p=>[p.id,p]));
  for(const block of settings.blocks || [])for(const panel of block.viewer?.panels || [])panels.set(panel.id,JSON.parse(JSON.stringify(panel)));
  viewer.panels=[...panels.values()];return viewer;
}
function reportBlockOf(state){return state.graphType==='insight'?'insights':state.graphType==='daily'?'daily':'summary';}
function reportEditingAllows(item){return !navigation?.export_workspace || (item.group==='Custom'?reportEditorBlock!=='insights':reportEditorBlock===(item.group==='Daily'?'daily':item.group==='Insights'?'insights':'summary'));}
function setupReportControls(){
  if(!navigation || navigation.report_render || (workspaceGraphs && !navigation.export_workspace))return;
  const root=document.createElement('section');root.className='report-workspace';root.setAttribute('aria-label','PDF report');
  const heading=document.createElement('div');heading.className='report-heading';
  const titleLabel=document.createElement('strong');titleLabel.textContent='PDF report';
  const loadedLabel=document.createElement('span');loadedLabel.textContent='Loaded data: '+navigation.source_first+' – '+navigation.source_last;
  heading.append(titleLabel,loadedLabel);root.appendChild(heading);
  const actions=document.createElement('div');actions.className='report-actions';root.appendChild(actions);
  const details=document.createElement('details');details.className='report-controls export-workspace';
  const summary=document.createElement('summary');summary.textContent='Report settings';details.appendChild(summary);
  const form=document.createElement('div');form.className='report-options';details.appendChild(form);
  let group=actions,loadingPreset=false,pending=null,baseline=null,feedback='',loadError='',lastResultId=null;
  let blocks=['overview','profiles','daily','summary','insights','statistics','distribution'].map(key=>({key,graphs_per_page:2}));
  const input=(label,type,value)=>{const wrap=document.createElement('label'),text=document.createElement('span');text.textContent=label;const el=document.createElement('input');el.type=type;el.value=value;el.setAttribute('aria-label',label);wrap.append(text,el);group.appendChild(wrap);return el;};
  const select=(label,options)=>{const wrap=document.createElement('label'),text=document.createElement('span');text.textContent=label;const el=document.createElement('select');el.setAttribute('aria-label',label);for(const [value,label] of options)el.add(new Option(label,value));wrap.append(text,el);group.appendChild(wrap);return el;};
  const action=(parent,text,fn)=>{const b=document.createElement('button');b.type='button';b.textContent=text;b.addEventListener('click',fn);parent.appendChild(b);return b;};
  const section=text=>{group=document.createElement('fieldset');group.className='report-section';const legend=document.createElement('legend');legend.textContent=text;group.appendChild(legend);form.appendChild(group);};
  const presets=navigation.report_presets || [];
  const preset=select('Saved PDF settings',[['','New preset'],...presets.map((p,i)=>[String(i),p.name])]);
  const presetName=input('Preset name','text','');presetName.maxLength=80;presetName.placeholder='Name this preset';
  const save=action(actions,'Save PDF settings',()=>send('report-preset'));
  const remove=action(actions,'Delete PDF preset',()=>send('report-delete'));
  remove.title='Remove this saved preset. Deleted settings remain recoverable in report_configurations/.trash.';
  const make=action(actions,'Make PDF',()=>send('report'));make.className='report-primary';
  const edit=action(actions,'Edit PDF settings',()=>{details.open=!details.open;});edit.setAttribute('aria-expanded','false');
  const status=document.createElement('p');status.className='report-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');root.appendChild(status);
  const useLoaded=action(root,'Use loaded dates',()=>{dateMode.value='loaded';applyDates();feedback='';drawOrder();validate();});useLoaded.className='report-repair';useLoaded.hidden=true;
  if(navigation.report_preset_errors?.length){const warning=document.createElement('p');warning.className='report-warning';warning.textContent='Some saved presets could not be loaded: '+navigation.report_preset_errors.join('; ');root.appendChild(warning);}
  root.appendChild(details);
  section('Dates & layout');
  const title=input('Report title','text','Profile Studio report');title.maxLength=120;
  const dateMode=select('Report dates',[['loaded','Use loaded dates'],['fixed','Use specific dates']]);
  const first=input('From date','date',navigation.source_first),last=input('Through date','date',navigation.source_last);
  for(const el of [first,last]){el.min=navigation.source_first;el.max=navigation.source_last;}
  const begin=input('Daily start (HH:MM)','text','00:00'),end=input('Daily end (HH:MM)','text','24:00');
  const layout=select('Page layout',[['landscape','Landscape'],['portrait','Portrait']]);
  const count=select('Default graphs per page',[1,2,3,4,5,6].map(n=>[String(n),String(n)]));count.value='2';
  const applyDates=()=>{const loaded=dateMode.value==='loaded';if(loaded){first.value=navigation.source_first;last.value=navigation.source_last;}first.disabled=last.disabled=loaded;};applyDates();
  section('Report blocks');group.classList.add('report-builder');
  const available=document.createElement('div'),ordered=document.createElement('div');group.append(available,ordered);
  const validBlock=key=>(key!=='summary' || first.value<last.value) && (!['profiles','profile_graphs'].includes(key) || navigation.report_capabilities?.profiles!==false) && (!['overview','statistics','distribution'].includes(key) || navigation.has_nightscout!==false);
  const drawOrder=()=>{
    available.replaceChildren();ordered.replaceChildren();
    for(const [node,text] of [[available,'Add a block'],[ordered,'PDF order']]){const h=document.createElement('strong');h.textContent=text;node.appendChild(h);}
    for(const [key,label] of Object.entries(REPORT_BLOCKS)){
      const b=action(available,'+ '+label,()=>{blocks.push({key,graphs_per_page:Number(count.value)});drawOrder();validate();});b.disabled=blocks.some(s=>s.key===key)||!validBlock(key);
    }
    blocks.forEach((block,i)=>{
      const row=document.createElement('div');row.className='report-block-row';row.dataset.block=block.key;ordered.appendChild(row);
      const label=document.createElement('span');label.textContent=(i+1)+'. '+REPORT_BLOCKS[block.key]+(!validBlock(block.key)?' (unavailable for these dates/data)':'');row.appendChild(label);row.classList.toggle('unavailable',!validBlock(block.key));
      if(['daily','summary','insights'].includes(block.key)){const b=action(row,'Configure',()=>{details.open=true;reportEditorBlock=block.key;controls();lastSize='';resizeVisible();});b.setAttribute('aria-label','Configure '+REPORT_BLOCKS[block.key]);b.className='block-configure';b.dataset.block=block.key;}
      if(['daily','summary','insights','profile_graphs'].includes(block.key)){const n=document.createElement('select');n.setAttribute('aria-label',REPORT_BLOCKS[block.key]+' graphs per page');for(let k=1;k<=6;k++)n.add(new Option(k+' / page',k));n.value=block.graphs_per_page;n.addEventListener('change',()=>{block.graphs_per_page=Number(n.value);validate();});row.appendChild(n);}
      for(const [direction,label] of [[-1,'↑'],[1,'↓']]){const b=action(row,label,()=>{[blocks[i],blocks[i+direction]]=[blocks[i+direction],blocks[i]];drawOrder();validate();});b.disabled=i+direction<0||i+direction>=blocks.length;b.setAttribute('aria-label','Move '+REPORT_BLOCKS[block.key]+(direction<0?' up':' down'));}
      const remove=action(row,'×',()=>{blocks.splice(i,1);drawOrder();validate();});remove.setAttribute('aria-label','Remove '+REPORT_BLOCKS[block.key]);
    });
  };
  section('Overview measures');group.classList.add('report-measures');
  const overviewFields=[];
  for(const [key,label] of [['coverage','Coverage'],['glucose','Glucose statistics'],['treatments','Carbs / insulin'],['events','Event totals'],['app_range','Range 4–10'],['comparison_range','Range 3.9–10']]){const el=input(label,'checkbox','');el.checked=true;overviewFields.push({key,el});}
  const snapshot=()=>{const viewer=viewerSettings();return {title:title.value,date_mode:dateMode.value,first:first.value,last:last.value,from_time:begin.value,until_time:end.value,layout:layout.value,graphs_per_page:Number(count.value),sections:[],
    blocks:blocks.map(b=>({...b,...(['daily','summary','insights'].includes(b.key)?{viewer:{...viewer,panels:viewer.panels.filter(p=>reportBlockOf(p)===b.key)}}:{})})),viewer,overview_fields:overviewFields.filter(s=>s.el.checked).map(s=>s.key)};};
  const fingerprint=()=>JSON.stringify({name:presetName.value.trim(),settings:snapshot()});
  const problem=()=>{
    if(loadError)return loadError;
    if(!first.value || !last.value || first.value>last.value)return 'Choose a valid start and end date.';
    if(first.value<navigation.source_first || last.value>navigation.source_last)return 'Saved dates '+first.value+' – '+last.value+' are outside the loaded range. Use loaded dates and save, or load the requested dates first.';
    if((Date.parse(last.value)-Date.parse(first.value))/86400000>365)return 'Choose up to 366 days using specific dates.';
    const minutes=v=>/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(v)?Number(v.slice(0,2))*60+Number(v.slice(3)):v==='24:00'?1440:NaN;
    if(!(minutes(begin.value)<minutes(end.value)))return 'Use an increasing daily time window, from 00:00 through 24:00.';
    if(!blocks.some(b=>validBlock(b.key)))return 'Add at least one report block available for these dates and data.';
    return '';
  };
  const validate=()=>{
    const error=problem(),busy=!ready||syncing||loadingPreset||Boolean(pending),dirty=baseline!==null&&fingerprint()!==baseline;
    preset.disabled=Boolean(pending)||loadingPreset;save.disabled=busy||Boolean(error)||!presetName.value.trim();make.disabled=busy||Boolean(error)||preset.value===''||dirty||baseline===null;
    remove.disabled=busy||preset.value==='';
    edit.disabled=Boolean(pending);form.inert=Boolean(pending);presetName.disabled=Boolean(pending);
    useLoaded.hidden=dateMode.value!=='fixed' || Boolean(first.value && last.value && first.value>=navigation.source_first && first.value<=last.value && last.value<=navigation.source_last);useLoaded.disabled=Boolean(pending);
    status.dataset.state=error?'error':pending?'busy':dirty?'changed':'ready';
    status.textContent=loadingPreset?'Loading preset…':pending?(pending.kind==='report'?'Preparing PDF…':pending.kind==='report-delete'?'Deleting PDF preset…':'Saving PDF settings…'):error||(dirty?'Unsaved changes. Save PDF settings before making the PDF.':feedback)||(preset.value===''?'Choose a saved preset, or name and save these settings.':'Ready · '+first.value+' – '+last.value+' · '+(dateMode.value==='loaded'?'uses loaded dates':'specific dates')+' · '+layout.options[layout.selectedIndex].text+' · '+count.value+' graphs per page');
  };
  const send=async kind=>{
    await jobs;validate();if((kind==='report'?make:kind==='report-delete'?remove:save).disabled)return;
    const request={id:crypto.randomUUID(),kind,...(['report','report-delete'].includes(kind)?{preset_name:presets[Number(preset.value)].name}:{name:presetName.value.trim(),settings:snapshot()})};
    pending=request;root.dataset.requestId=request.id;feedback='';validate();window.parent.postMessage({type:'profile-studio:report',request},'*');
  };
  const loadPreset=async()=>{
    loadingPreset=true;loadError='';feedback='';baseline=null;validate();
    try{
      const saved=preset.value===''?null:presets[Number(preset.value)];
      if(!saved){presetName.value='';details.open=true;return;}
      const v=saved.settings;title.value=v.title || 'Profile Studio report';layout.value=v.layout || 'landscape';count.value=String(v.graphs_per_page || 2);begin.value=v.from_time || '00:00';end.value=v.until_time || '24:00';
      dateMode.value=v.date_mode || (v.first&&v.last?'fixed':'loaded');first.value=v.first || navigation.source_first;last.value=v.last || navigation.source_last;applyDates();presetName.value=saved.name;
      blocks=JSON.parse(JSON.stringify(v.blocks || []));for(const s of overviewFields)s.el.checked=!v.overview_fields || v.overview_fields.includes(s.key);
      if(v.viewer || v.blocks?.some(b=>b.viewer))await loadWorkspacePreset(reportPresetViewer(v));
      reportEditorBlock=blocks.find(b=>['daily','summary','insights'].includes(b.key))?.key || 'daily';drawOrder();baseline=fingerprint();
      if(problem())details.open=true;
    }catch(error){loadError='Could not load this preset: '+error.message;details.open=true;}
    finally{loadingPreset=false;drawOrder();controls();validate();}
  };
  preset.addEventListener('change',loadPreset);
  form.addEventListener('input',()=>{feedback='';validate();});form.addEventListener('change',()=>{feedback='';applyDates();drawOrder();validate();});presetName.addEventListener('input',()=>{feedback='';validate();});
  const editor=document.createElement('div');editor.className='report-block-editor';const tabs=document.createElement('div');editor.appendChild(tabs);
  for(const key of ['daily','summary','insights']){const b=action(tabs,REPORT_BLOCKS[key],()=>{reportEditorBlock=key;controls();lastSize='';resizeVisible();});b.dataset.block=key;}
  const add=action(editor,'+ Add graph to block',openGraphPicker),hint=document.createElement('span');editor.appendChild(hint);
  reportControlsRefresh=()=>{for(const b of [...tabs.querySelectorAll('button'),...ordered.querySelectorAll('.block-configure')])b.setAttribute('aria-pressed',String(b.dataset.block===reportEditorBlock));hint.textContent=REPORT_BLOCKS[reportEditorBlock]+' · '+panelOrder.filter(i=>!panelStateAt(i).deleted&&reportBlockOf(panelStateAt(i))===reportEditorBlock).length+' graphs';add.disabled=!ready||syncing||Boolean(pending);validate();};
  details.addEventListener('toggle',()=>{edit.textContent=details.open?'Hide PDF settings':'Edit PDF settings';edit.setAttribute('aria-expanded',String(details.open));});
  window.addEventListener('message',event=>{
    if(event.source!==window.parent || event.data?.type!=='profile-studio:report-result')return;
    const result=event.data.result;if(!result || result.id===lastResultId || (pending && result.id!==pending.id))return;lastResultId=result.id;
    pending=null;root.dataset.completedRequestId=result.id;feedback=result.message || '';validate();
  });
  const chosen=presets.findIndex(p=>p.name===navigation.report_selected_preset);preset.value=chosen>=0?String(chosen):presets.length?'0':'';
  details.open=!presets.length;drawOrder();
  const viewer=document.getElementById('viewer');viewer.insertBefore(root,document.getElementById('toolbar'));document.getElementById('panels').before(editor);
  if(navigation.export_workspace)viewer.classList.add('pdf-workspace');
  validate();if(preset.value!=='')setTimeout(()=>loadPreset(),0);
}

function reportSleepViews(graph,options){
  if(graph.layout.meta?.sleep_overview)return reportSleepOverviewViews(graph,options);
  const dates=[...new Set((graph.data || []).filter(t=>t.meta?.kind==='garmin_sleep').map(t=>t.meta.date))].sort();
  if(graph.layout.meta?.dataset!=='g_sleep' || dates.length<2)return [{data:graph.data,layout:graph.layout}];
  const settings=displayOptions(graph.layout),rows=settings.sleepOverlay?0:(settings.sleepFields || []).length;
  const size=sleepDimensions(0,rows,settings.sleepOverlay);
  const available=Math.max(navigation?.sleep_day_height || 28,(options.height || 400)*(options.capacity || 1)-size.chrome-rows*size.row);
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
const reportProfileSizing=new Map();
function reportProfileLevels(view,index,options,width){
  const compact=view.layout.meta?.kind==='compact',profiles=eventAllowed(view,'profiles'),site=compact&&eventAllowed(view,'site'),sensor=compact&&eventAllowed(view,'sensor');
  if(!profiles&&!site&&!sensor)return 0;
  if(panelStateAt(index).graphType!=='daily' || !options.context_profiles)return view.layout.meta?.profile_label_levels || 0;
  const key=JSON.stringify([view.layout.meta?.kind,width,options.range,profiles,site,sensor]);
  if(reportProfileSizing.has(key))return reportProfileSizing.get(key);
  const days=new Map();
  if(profiles)for(const e of options.context_profiles){const labels=days.get(e.date)||[];labels.push({name:'Effective | '+e.minute,text:profileEventText(e),x:e.minute,y:-.001,font:{size:9}});days.set(e.date,labels);}
  if(compact)for(const e of options.context_changes || []){
    if(!(e.label==='Site Change'?site:sensor))continue;
    const labels=days.get(e.date)||[];labels.push({name:'Change | '+e.minute,text:changeEventText(e,false),x:e.minute,y:-.001,font:{size:9}});days.set(e.date,labels);
  }
  let maximum=0;
  for(const labels of days.values()){
    const layout=JSON.parse(JSON.stringify(view.layout));layout.annotations=labels;layout.shapes=[];layout.xaxis.range=options.range;
    profileEventLayout(layout,width);maximum=Math.max(maximum,layout.meta?.profile_label_levels || 0);
  }
  reportProfileSizing.set(key,maximum);return maximum;
}
async function exportReportFigures(){
  const options=navigation.report_render;if(!options)return;
  try {
    await setTimeRange(options.range);
    const result=[];
    const active=[...(dataOnly?[]:[0]),...panelOrder].filter(i=>!panelStateAt(i).deleted);
    // Give time axes the same physical plot bounds, including compact and ordinary panels.
    const axisMargins={l:Math.max(72,...active.map(i=>graphs[i].layout.margin?.l || 0)),r:Math.max(72,...active.map(i=>graphs[i].layout.margin?.r || 0))};
    for(const index of [...(dataOnly?[]:[0]),...panelOrder]){
      if(panelStateAt(index).deleted)continue;
      const g=graphs[index],graphRange=panelTimeRange(index,options.range);
      for(const view of reportSleepViews(g,options)){
      const layout=JSON.parse(JSON.stringify(view.layout));
      const meaningful=(view.data || []).some(t=>t.visible!==false && t.visible!=='legendonly' && !t.meta?.legend_proxy && !['profile_event','automation_note'].includes(t.meta?.kind) && t.hoverinfo!=='skip' &&
        (t.type==='heatmap'?(t.z || []).flat().some(Number.isFinite):(t.y || []).some(Number.isFinite)));
      if(!meaningful || layout.meta?.empty)continue;
      let note=layout.meta?.kind==='insight'?layout.meta.insight_note || '':'';
      const dense=Boolean(note) && (options.capacity || 1)>=5;
      let noteMM=reportInsightNoteSize(note,options.note_width || 263*96/25.4);
      const notePixels=options.local_note_pixels || noteMM*(options.width || 1320)/(options.note_width || 263*96/25.4)*96/25.4;
      const usedAxes=new Set(view.data.filter(t=>t.visible!==false && !t.meta?.legend_proxy && !['automation_note','profile_event'].includes(t.meta?.kind)).map(t=>'yaxis'+(t.yaxis || 'y').slice(1)));
      const rows=new Set(Object.entries(layout).filter(([k,v])=>usedAxes.has(k) && v.visible!==false && v.domain && !v.overlaying).map(([,v])=>JSON.stringify(v.domain))).size;
      const plotWidth=(options.width || 1320)-axisMargins.l-axisMargins.r;
      const levels=reportProfileLevels(view,index,{...options,range:graphRange},plotWidth);
      if(layout.meta?.kind==='compact')layout.meta.report_label_levels=levels;
      const reserveNotes=eventAllowed(view,'automation')&&options.reserve_automation;
      const percent=eventAllowed(view,'percentage')?Math.max(100,...(options.context_profiles || []).map(e=>e.percentage || 100)):100;
      const labelMargin=levels?(options.compact?56:64)+Math.max(0,levels-1)*(options.compact?12:18):(options.compact?40:55);
      const eventHeight=levels||percent>100?labelMargin+(options.compact?20:35)+50*percent/100+(reserveNotes?24:0):0;
      const sleepOptions=displayOptions(layout);
      const sleepDates=new Set(view.data.filter(t=>t.meta?.kind==='garmin_sleep').map(t=>t.meta.date)).size;
      const sleepHeight=sleepDimensions(sleepDates,(sleepOptions.sleepFields || []).length,sleepOptions.sleepOverlay).height;
      const compactBars=layout.meta?.compact_distribution&&rows<=1&&!(layout.meta?.dataset==='g_sleep'&&sleepOptions.sleepFields?.length);
      const required=compactBars?0:Math.max(eventHeight,layout.meta?.kind==='compact'?470+levels*17:
        layout.meta?.sleep_overview?95+rows*(layout.meta.sleep_overview_row_height || 88):layout.meta?.dataset==='g_sleep'?sleepHeight:rows>1?rows*100+100:0);
      // Compact receives twice the standard allocation. Pagination still counts graphs.
      const slots=layout.meta?.kind==='compact'?2:layout.meta?.dataset==='g_sleep'?(rows>1?.75:.5):1,heightFactor=1;
      const slotHeight=(options.height || 400)*slots;
      layout.height=Math.round(Math.max(slotHeight,required)-notePixels);layout.width=options.width || 1320;
      if(layout.meta?.dataset==='g_sleep' && sleepDates<=1)layout.height=Math.max(levels?100:70,Math.round(slotHeight-notePixels));
      layout.margin={...layout.margin,...axisMargins,t:options.compact?20:35,b:Math.max(labelMargin,layout.meta?.kind==='compact'?66:0),autoexpand:false};
      layout.title={...layout.title,font:{size:options.compact?12:16}};
      layout.legend={...layout.legend,font:{size:options.capacity>=5?8:options.compact?9:11},yref:'container',y:0,yanchor:'bottom',itemsizing:'constant'};
      if(dense){
        // Dense pages need less chrome as well as smaller charts; resize the
        // actual Plotly plot so neither data nor the method note is cropped.
        layout.margin={...layout.margin,t:20,b:Math.max(48,labelMargin),autoexpand:false};
        layout.title.font.size=11;
        layout.legend={...layout.legend,...(!levels?{yref:'container',y:0,yanchor:'bottom'}:{}),font:{size:8}};
      }
      if(layout.meta?.sleep_overview){layout.margin.b=65;layout.xaxis.title={text:''};}
      if(eventAllowed(view,'percentage'))layout.meta.percentage_max=percent;
      profileEventLayout(layout,plotWidth);
      if(!layout.meta?.non_time){layout.xaxis.range=graphRange;layout.xaxis.autorange=false;}
      const printable={data:JSON.parse(JSON.stringify(view.data)),layout};
      for(const shape of layout.shapes || [])if(shape.legendgroup?.startsWith('Profile · '))shape.showlegend=false;
      panelDateContext(index,()=>applyAutomationNotes(printable,index));
      if(layout.meta?.automation_print_key && !options.consolidate_automation){
        note=[note,'Notes: '+layout.meta.automation_print_key].filter(Boolean).join(' ');
        noteMM=reportInsightNoteSize(note,options.note_width || 263*96/25.4);
        layout.height=Math.max(40,Math.max(slotHeight,required)-noteMM*(options.width || 1320)/(options.note_width || 263*96/25.4)*96/25.4);
        profileEventLayout(layout,plotWidth);panelDateContext(index,()=>applyAutomationNotes(printable,index));
      }
      if(layout.meta?.kind==='compact'){compactLayout(layout,plotWidth);compactAmountLabels(printable,plotWidth);}
      if(layout.meta?.dataset==='g_sleep' && sleepDates<=1){
        layout.legend={...layout.legend,font:{size:8}};
        for(const [key,axis] of Object.entries(layout).filter(([k])=>/^yaxis[0-9]+$/.test(k))){
          const unit=axis.title?.text;axis.title={text:''};axis.nticks=2;
          const trace=printable.data.find(t=>t.yaxis==='y'+key.slice(5) && t.meta?.dataset);
          const label=(layout.annotations || []).find(a=>a.name==='Sleep metric | '+trace?.meta?.dataset);
          if(label && unit)label.text+=' ('+unit+')';
        }
        if(layout.height<140)for(const shape of layout.shapes || [])if(shape.name?.startsWith('Activity | ') && shape.label)shape.label.text='';
        const domain=layout.yaxis.domain || [0,1],stagePixels=(domain[1]-domain[0])*Math.max(12,layout.height-layout.margin.t-layout.margin.b);
        for(const trace of printable.data.filter(t=>t.meta?.kind==='garmin_sleep'))trace.line.width=Math.max(8,Math.min(36,stagePixels*.7));
      }
      layout.paper_bgcolor='#ffffff';layout.plot_bgcolor='#ffffff';layout.font={...layout.font,color:'#24354b',size:options.compact?11:15,family:'Arial, "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif'};
      if(options.compact && layout.meta?.dataset==='g_sleep'){
        const hourly=view.data.find(t=>t.meta?.sleep_variant==='hourly');
        if(hourly)layout.yaxis.title={...layout.yaxis.title,text:hourly.meta.aggregation+' h/h'};
      }
      for(const key of Object.keys(layout).filter(k=>/^[xy]axis[0-9]*$/.test(k))){
        const axis=layout[key];axis.automargin=false;axis.tickfont={...axis.tickfont,size:options.capacity>=5?8:options.compact?10:13};axis.gridcolor='#dce4eb';axis.linecolor='#b5c0cb';
        if(options.capacity>=5 && key.startsWith('y'))axis.nticks=3;
        if(axis.title){axis.title.font={...axis.title.font,size:options.capacity>=5?9:options.compact?11:13};axis.title.standoff=options.compact?2:8;}
        if(dense){
          axis.automargin=false;if(key.startsWith('y'))axis.nticks=3;
          if(axis.title)axis.title.standoff=0;
          // The note already names the alignment/relationship. Put the units
          // on dense insight X ticks so a long title cannot collide with them.
          if(key==='xaxis' && layout.meta?.kind==='insight' && !layout.meta?.sleep_overview){
            axis.title={text:''};axis.ticksuffix=' '+(layout.meta.insight_relationship?view.data.find(t=>t.meta?.kind==='insight_relationship')?.meta.x_unit || '':'h');
          }
        }
      }
      const holder=document.createElement('div');holder.style.width=layout.width+'px';document.getElementById('viewer').appendChild(holder);
      applyClockTicks(layout,graphRange,plotWidth);applyOverlayDayColors(printable,index);
      try {
        await Plotly.newPlot(holder,printable.data,layout,{staticPlot:true});await reflowProfileLabels(holder);tidyLabels(holder);
        const outputHeight=Math.max(40,slotHeight-(note?noteMM*(options.width || 1320)/(options.note_width || 263*96/25.4)*96/25.4:notePixels));
        const image=await Plotly.toImage(holder,{format:'svg',width:layout.width,height:layout.height});
        const svg=new DOMParser().parseFromString(decodeURIComponent(image.slice(image.indexOf(',')+1)),'image/svg+xml').documentElement;
        svg.setAttribute('viewBox','0 0 '+layout.width+' '+layout.height);
        svg.setAttribute('height',String(outputHeight));svg.setAttribute('preserveAspectRatio','none');
        const url='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(new XMLSerializer().serializeToString(svg));
        let title=layout.title?.text || 'Graph';
        if(layout.meta?.kind==='custom'){
          const fields=[...customState(layout.meta.custom_id).selected].map(id=>customFields.find(f=>f.id===id)?.label).filter(Boolean);
          title='Custom '+layout.meta.custom_id.replace('custom-','')+' — '+fields.slice(0,4).join(', ')+(fields.length>4?' + '+(fields.length-4)+' more':'');
        }
        const automation_notes=options.consolidate_automation?printable.data.filter(t=>t.meta?.kind==='automation_note' && t.x?.[0]>=graphRange[0] && t.x[0]<=graphRange[1]).map(t=>({date:t.meta.date,minute:t.x[0],label:t.meta.label})):[];
        result.push({title,height:outputHeight,slots:slots*heightFactor,url,note,note_mm:noteMM,automation_notes});
      }finally{Plotly.purge(holder);holder.remove();}
      }
    }
    window.parent.postMessage({type:'profile-studio:report-rendered',id:options.id,figures:result},'*');
  }catch(error){window.parent.postMessage({type:'profile-studio:report-rendered',id:options.id,error:String(error)},'*');}
}
