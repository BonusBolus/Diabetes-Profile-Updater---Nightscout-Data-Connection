"""An offline Plotly viewer: profile pinned above scrollable recorded panels."""
from functools import lru_cache
from datetime import timedelta
import json
import hashlib

from plotly.offline import get_plotlyjs
import streamlit as st

from appearance import palette
from chart_cache import cached
from nightscout import daily_summary
from nightscout_charts import graph_figures, OVERLAY_CHOICES, hourly_figure, add_profile_guides


@lru_cache(maxsize=1)
def plotly_script():
    return get_plotlyjs()


def navigation_bundle(profile, view, unit, dark):
    loaded = view['loaded']
    days = [loaded['first']+timedelta(days=i) for i in range((loaded['last']-loaded['first']).days+1)]
    # One batch of dated traces lets the browser filter locally without an app
    # rerun, which would destroy fullscreen. No tokens or server URLs are sent.
    daily = graph_figures(profile, **dict(view, days=days, mode='One day',summary_layout=view['mode']=='Median + band'), unit=unit, dark=dark)
    overlays = {}
    for option in OVERLAY_CHOICES:
        options = dict(view, layers=[], overlay=option,profile_only=True)
        # Initial variants preserve median/multiple-day mode; daily variants
        # support local date navigation without requests or leaving fullscreen.
        initial_top = graph_figures(profile, **options, unit=unit, dark=dark)[0]
        daily_top = daily[0] if option == view.get('overlay', 'None') else graph_figures(
            profile, **dict(options, days=days, mode='One day'), unit=unit, dark=dark)[0]
        overlays[option] = dict(selected=json.loads(initial_top.to_json()), daily=json.loads(daily_top.to_json()))
    bolus_variants = {}
    if view['mode'] == 'Median + band':
        for label, selected in [('selected',view['days']),('daily',days)]:
            fig = hourly_figure(loaded,'bolus',selected,dark,exclude_smb=True)
            add_profile_guides(fig,(profile.layout.meta or {}).get('profile_changes',[]),dark)
            bolus_variants[label] = json.loads(fig.to_json())
    return dict(bolus_without_smb=bolus_variants, days=[day.isoformat() for day in days], selected=[day.isoformat() for day in view['days']],
                mode=view['mode'], same_scale=view.get('same_scale',False), unit=unit,
                glucose_overlay=view.get('overlay')=='Glucose', overlay=view.get('overlay','None'), overlays=overlays,
                figures=[json.loads(fig.to_json()) for fig in daily],
                summaries=cached(loaded,'daily_stats',(tuple(days),unit),lambda: daily_summary(loaded,days,unit)))


def prepared_graphs(profile, view, unit, dark):
    # The loaded snapshot is immutable until manual refresh. Profile edits only
    # rebuild the viewer; recorded traces and statistics remain reusable.
    key=(profile.to_json(),tuple(view['days']),view['mode'],tuple(view['layers']),
         view.get('overlay','None'),view.get('show_targets',True),view.get('same_scale',False),unit,dark)
    def build():
        figures=graph_figures(profile,**view,unit=unit,dark=dark)
        navigation=navigation_bundle(profile,view,unit,dark)
        navigation['render_key']=hashlib.sha256(repr(key).encode()).hexdigest()
        return figures,navigation
    return cached(view['loaded'],'prepared',key,build,limit=3)


def viewer_html(figures, dark, navigation=None):
    # Escape all '<' in JSON so uploaded labels cannot terminate a script tag.
    specs='['+','.join(fig.to_json() for fig in figures)+']'
    specs=specs.replace('<','\\u003c')
    navigation_json=json.dumps(navigation,allow_nan=False).replace('<','\\u003c')
    payload_json='{"specs":'+specs+',"navigation":'+navigation_json+'}'
    theme=palette(dark)
    return """<!doctype html><html><head><meta charset="utf-8"><style>
html,body {margin:0;height:100%;font-family:Arial,sans-serif;background:BACKGROUND;color:TEXT;}
#viewer {height:100vh;display:flex;flex-direction:column;}
#toolbar {min-height:38px;flex:0 0 auto;flex-wrap:wrap;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 10px;box-sizing:border-box;border-bottom:1px solid GRID;}
#toolbar-left {display:flex;flex-wrap:wrap;align-items:center;gap:6px;}
#overlay-control {font-size:12px;display:flex;align-items:center;gap:5px;}
#overlay-select {display:flex;flex-wrap:wrap;gap:4px;}
button[aria-pressed="true"] {outline:2px solid #22a6bb;}
.bolus-controls {padding:5px 12px;display:flex;align-items:center;gap:10px;font-size:12px;}
.bolus-controls button {background:transparent;color:inherit;border:1px solid #80808080;border-radius:5px;padding:5px 10px;cursor:pointer;}
#date-calendar {position:absolute;z-index:20;top:42px;left:10px;background:SURFACE;border:1px solid GRID;border-radius:6px;padding:12px;max-height:65vh;overflow:auto;}
.calendar-grid {display:grid;grid-template-columns:repeat(7,32px);gap:3px;}
.calendar-grid button {padding:5px 2px!important;}
.calendar-month {font-weight:bold;margin:8px 0;}
#date-calendar[hidden] {display:none;}
#toolbar button,#toolbar select {border:1px solid GRID;border-radius:5px;background:SURFACE;color:TEXT;padding:4px 9px;cursor:pointer;white-space:nowrap;}
#toolbar button:disabled {opacity:.35;cursor:default;}
#day-label {font-size:12px;}
#daily-summary {font-size:12px;padding:5px 10px;border-bottom:1px solid GRID;}
#daily-summary summary {cursor:pointer;}
#summary-body {max-height:135px;overflow:auto;}
#summary-body table {border-collapse:collapse;width:100%;font-size:12px;}
#summary-body th,#summary-body td {padding:4px 8px;text-align:right;white-space:nowrap;border-bottom:1px solid GRID;}
#summary-body th:first-child,#summary-body td:first-child {text-align:left;}
#summary-body p {margin:6px 0;opacity:.8;}
#hover-card {min-width:0;max-width:100%;overflow-wrap:anywhere;font-size:13px;line-height:1.25;text-align:right;display:flex;flex-wrap:wrap;justify-content:flex-end;gap:3px 12px;pointer-events:none;}
#hover-card strong {font-weight:600;} #hover-card .muted {opacity:.8;}
#profile {flex:0 0 310px;border-bottom:1px solid GRID;background:BACKGROUND;}
#panels {flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;}
.graph {width:100%;min-width:0;position:relative;}
.target-note {flex:0 0 auto;margin:0;padding:4px 12px 10px;font-size:12px;line-height:1.4;opacity:.8;}
.target-note[hidden] {display:none;}
.hoverlayer {visibility:hidden;}
.time-guide {position:absolute;width:0;border-left:1px dashed TEXT;opacity:.65;pointer-events:none;z-index:4;display:none;}
.point-highlight {position:absolute;width:14px;height:14px;border:2px solid TEXT;border-radius:50%;box-shadow:0 0 0 2px SURFACE;transform:translate(-50%,-50%);pointer-events:none;z-index:5;display:none;}
</style></head><body><div id="viewer"><div id="toolbar"><div id="toolbar-left"><button id="expand" type="button">⛶ Expand graphs</button>
<button id="previous-day" type="button" aria-label="Previous loaded day">← Previous</button>
<button id="day-label" type="button" aria-label="Choose loaded day" aria-expanded="false"></button><div id="date-calendar" hidden></div><button id="next-day" type="button" aria-label="Next loaded day">Next →</button>
<div id="overlay-control">Overlay <div id="overlay-select" role="group" aria-label="Nightscout overlay on profile"></div></div></div>
<div id="hover-card" role="status" aria-live="polite">Hover a point for details</div></div>
<details id="daily-summary"><summary id="summary-title">Daily summary</summary><div id="summary-body"></div></details>
<div id="profile" class="graph"></div><p id="profile-target-note" class="target-note" hidden></p><div id="panels" tabindex="0" aria-label="Recorded data graphs; scroll here. Profile remains pinned."></div></div>
<script>""".replace('BACKGROUND',theme['background']).replace('SURFACE',theme['surface']).replace('TEXT',theme['text']).replace('GRID',theme['grid']) + plotly_script()+"""</script><script>
const payload = __VIEWER_PAYLOAD__;
const specs = payload.specs;
const navigation = payload.navigation;
let selectedDays = navigation ? navigation.selected.slice() : [];
const previousDay=document.getElementById('previous-day'),nextDay=document.getElementById('next-day');
const dayLabel=document.getElementById('day-label'),dateCalendar=document.getElementById('date-calendar');
const overlayControl=document.getElementById('overlay-control'),overlaySelect=document.getElementById('overlay-select');
let currentOverlay=navigation ? navigation.overlay || 'None' : 'None', dateCycled=false, excludeSMB=false;
const overlayButtons=[],bolusButtons=[];
if(navigation && navigation.overlays) {
  Object.keys(navigation.overlays).forEach(value=>{const option=document.createElement('button');option.type='button';option.value=value;option.textContent=value==='Nightscout targets'?'Temp targets':value;option.addEventListener('click',()=>changeOverlay(value));overlaySelect.appendChild(option);overlayButtons.push(option);});
} else overlayControl.hidden=true;
const summary=document.getElementById('daily-summary'),summaryTitle=document.getElementById('summary-title'),summaryBody=document.getElementById('summary-body');
function number(value,digits=1) {return value===null || value===undefined ? '—' : Number(value.toFixed(digits)).toString();}
function updateSummary() {
  if(!navigation) {summary.hidden=true;previousDay.hidden=true;nextDay.hidden=true;return;}
  const days=navigation.summaries.filter(r=>selectedDays.includes(r.date));
  dayLabel.textContent=selectedDays.length===1 ? selectedDays[0] : selectedDays.length+' days';
  summaryTitle.textContent=days.length===1 ? 'Daily summary · In range '+number(days[0].tir)+'% · CGM coverage '+number(days[0].coverage)+'%' : 'Daily summary · '+days.length+' selected days';
  summaryBody.replaceChildren();
  const table=document.createElement('table');
  const labels=['Date','In 4–10 (%)','Below (%)','Above (%)','Mean','SD','CV (%)','Carbs (g)','Bolus (U)','CGM coverage (%)'];
  labels[1]=navigation.unit==='mmol/L'?'In 4–10 (%)':'In 72–180 (%)';
  const head=document.createElement('tr');labels.forEach(label=>{const cell=document.createElement('th');cell.textContent=label;head.appendChild(cell);});table.appendChild(head);
  days.forEach(r=>{const row=document.createElement('tr');
    [r.date+(r.partial?' · through '+r.through:''),r.tir,r.below,r.above,r.mean,r.sd,r.cv,r.carbs,r.bolus,r.coverage].forEach((value,i)=>{
      const cell=document.createElement('td');cell.textContent=i===0?value:number(value,i===8?2:1);row.appendChild(cell);
    });table.appendChild(row);
  });
  summaryBody.appendChild(table);
  const note=document.createElement('p');note.textContent='Glucose: '+navigation.unit+'. Five-minute bin medians; SD is population standard deviation; CV = SD / mean. Percentages use observed glucose only. Missing bins are excluded. Coverage uses elapsed time through the load timestamp, including DST. Treatment totals are recorded uploads; unavailable data is —.';
  summaryBody.appendChild(note);
}
updateSummary();
const graphs = [document.getElementById('profile')];
const targetNotes = [document.getElementById('profile-target-note')];
function updateTargetNote(div,index) {
  const note=targetNotes[index];
  note.hidden=!div.data.some(trace=>trace.meta?.kind==='target');
  note.textContent='Shading reaches the historical profile target range active at that time, from Nightscout—not the draft. Dotted sides mark interval boundaries. Missing target history: line only.';
}
const panels = document.getElementById('panels');
const card = document.getElementById('hover-card');
const expand = document.getElementById('expand');
for(let i=1;i<specs.length;i++) {
  if(specs[i].layout.meta?.kind==='hourly' && specs[i].layout.meta.dataset==='bolus' && navigation?.bolus_without_smb?.selected) {
    const bar=document.createElement('div');bar.className='bolus-controls';
    const button=document.createElement('button');button.type='button';button.textContent='Exclude SMB';button.addEventListener('click',()=>toggleSMB(i));bar.appendChild(button);bolusButtons.push(button);
    const note=document.createElement('span');note.textContent='Grid + histogram · unknown boluses remain included';bar.appendChild(note);panels.appendChild(bar);
  }
  const div=document.createElement('div');div.className='graph';panels.appendChild(div);graphs.push(div);
  const note=document.createElement('p');note.className='target-note';note.hidden=true;panels.appendChild(note);targetNotes.push(note);
}
let syncing=false;
const guides=[], highlights=[];
let ready=false;
previousDay.disabled=true;nextDay.disabled=true;
function clearHover() {
  guides.forEach(g=>g.style.display='none');highlights.forEach(g=>g.style.display='none');
  card.textContent='Hover a point for details';
}
function showHover(div,event) {
  const point=event.points && event.points[0];
  if(point && point.data?.meta?.kind==='hourly_heatmap') {
    const d=point.customdata;
    if(!d || d[2]===null)return;
    clearHover();card.textContent=point.data.meta.label+' · '+d[0]+' '+d[1]+' · '+number(d[2],3)+' '+point.data.meta.unit+' · '+d[3]+' events · '+d[4];
    return;
  }
  if(!point || !Number.isFinite(point.x) || !Number.isFinite(point.y))return;
  const trace=point.data, meta=trace.meta || {};
  const minute=Math.round(point.x), clock=String(Math.floor(minute/60)).padStart(2,'0')+':'+String(minute%60).padStart(2,'0');
  const value=Number(point.y.toFixed(3)).toString();
  const label=meta.label || trace.name || 'Value';
  card.replaceChildren();
  const parts=[label,value+(meta.unit?' '+meta.unit:''),(meta.date?meta.date+' · ':'')+clock];
  if(meta.kind==='target' && point.customdata)parts.push(String(point.customdata));
  if((meta.kind==='median' || meta.kind==='hourly_histogram') && point.customdata)parts.push(point.customdata+' contributing days');
  parts.forEach((text,i)=>{const el=document.createElement(i===1?'strong':'span');el.textContent=text;if(i>1)el.className='muted';card.appendChild(el);});
  // Plotly 6.9 supplies axis transforms with its hover event. Reusing them also
  // places highlights correctly on the secondary axis and after zoom/pan.
  graphs.forEach((g,i)=>{
    const axis=g._fullLayout.xaxis, y=g._fullLayout.yaxis;
    const px=axis._offset+axis.l2p(point.x);
    const inside=px>=axis._offset && px<=axis._offset+axis._length;
    Object.assign(guides[i].style,{display:inside?'block':'none',left:px+'px',top:y._offset+'px',height:y._length+'px'});
    highlights[i].style.display='none';
  });
  const marker=highlights[graphs.indexOf(div)];
  Object.assign(marker.style,{display:'block',left:(point.xaxis._offset+point.xaxis.l2p(point.x))+'px',top:(point.yaxis._offset+point.yaxis.l2p(point.y))+'px'});
}
// Keep amount labels readable without hiding their markers or hover values.
// Re-evaluate from scratch after zoom, resize and changing day/dataset.
function tidyLabels(div) {
  if(!div.querySelectorAll)return;
  const accepted=[];
  div.querySelectorAll('.scatterlayer .textpoint text').forEach(node=>{
    node.style.visibility='visible';
    const box=node.getBoundingClientRect();
    if(!box.width || !box.height)return;
    if(accepted.some(other=>box.left<other.right+4 && box.right>other.left-4 && box.top<other.bottom+2 && box.bottom>other.top-2))node.style.visibility='hidden';
    else accepted.push(box);
  });
}
// Plotly cannot measure hidden tabs correctly. Wait for width and fonts, then
// serialize initialization, redraws and resizes so stale layouts cannot race.
const viewer=document.getElementById('viewer');
let jobs=Promise.resolve(), starting=false, resizePending=false, lastSize='';
let intersects=typeof IntersectionObserver==='undefined';
function enqueue(task) {const next=jobs.then(task);jobs=next.catch(()=>{});return next;}
function visibleWidth() {return intersects ? Math.floor(viewer.getBoundingClientRect().width) : 0;}
function sizedLayout(spec, index) {
  const layout=JSON.parse(JSON.stringify(spec.layout));
  layout.width=Math.max(1, panels.clientWidth || visibleWidth());
  layout.autosize=false;
  return layout;
}
function controls() {
  previousDay.disabled=!ready || syncing || !navigation || navigation.days.length<2;
  nextDay.disabled=previousDay.disabled;dayLabel.disabled=!ready || syncing || !navigation;
  overlayButtons.forEach(button=>{button.disabled=!ready || syncing;button.setAttribute('aria-pressed',String(button.value===currentOverlay));});
  bolusButtons.forEach(button=>{button.disabled=!ready || syncing;button.setAttribute('aria-pressed',String(excludeSMB));button.textContent=excludeSMB?'Exclude SMB: on':'Exclude SMB: off';});
}
function compactLegend(data) {
  const seen=new Set();
  data.forEach(trace=>{
    const eligible=trace.meta?.legend_entry ?? (trace.showlegend!==false);
    const group=trace.legendgroup || trace.name;
    trace.showlegend=eligible && !seen.has(group);
    if(eligible)seen.add(group);
  });
}
function resizeVisible() {
  if(!ready || visibleWidth()<50)return;
  const width=Math.floor(panels.clientWidth || visibleWidth());
  const size=width+':'+viewer.clientHeight;
  if(size===lastSize)return;
  lastSize=size;
  clearHover();
  return Promise.all(graphs.map((div,i)=>Plotly.relayout(div,{width,height:specs[i].layout.height,autosize:false})))
    .then(()=>graphs.forEach(tidyLabels));
}
function scheduleLayout() {
  if(visibleWidth()<50) {lastSize='';return;}
  if(!ready) {startPlots();return;}
  if(resizePending)return;
  resizePending=true;
  requestAnimationFrame(()=>enqueue(async()=>{
    try {await resizeVisible();} finally {resizePending=false;}
  }).catch(()=>{card.textContent='Could not resize graphs. Reopen this tab.';}));
}
async function startPlots() {
  if(starting || ready || visibleWidth()<50)return;
  starting=true;
  try {
    if(document.fonts)await document.fonts.ready;
    await enqueue(async()=>{
      if(visibleWidth()<50)return;
      await Promise.all(graphs.map((div,i)=>Plotly.newPlot(div,specs[i].data,sizedLayout(specs[i],i),
        {responsive:false,displaylogo:false,scrollZoom:false,toImageButtonOptions:{format:'png',scale:2}})));
      graphs.forEach((div,index)=>{
        const guide=document.createElement('div');guide.className='time-guide';div.appendChild(guide);guides.push(guide);
        const marker=document.createElement('div');marker.className='point-highlight';div.appendChild(marker);highlights.push(marker);
        div.on('plotly_afterplot',()=>{tidyLabels(div);updateTargetNote(div,index);});tidyLabels(div);updateTargetNote(div,index);
        div.on('plotly_hover',event=>showHover(div,event));div.on('plotly_unhover',clearHover);
        div.on('plotly_relayout',event=>{
          if(syncing)return;
          let range=event['xaxis.range'];
          if(event['xaxis.range[0]']!==undefined)range=[event['xaxis.range[0]'],event['xaxis.range[1]']];
          if(event['xaxis.autorange'])range=[0,1440];
          if(!range)return;
          enqueue(async()=>{
            syncing=true;controls();clearHover();
            try {await Promise.all(graphs.filter(g=>g!==div).map(g=>Plotly.relayout(g,{'xaxis.range':range,'xaxis.autorange':false})));}
            finally {syncing=false;controls();}
          }).catch(()=>{card.textContent='Could not synchronize zoom.';});
        });
      });
      ready=true;controls();await resizeVisible();
    });
  } catch(error) {card.textContent='Could not draw graphs. Reopen this tab.';}
  finally {starting=false;}
}
function dailyView(spec,index,day,range) {
  const clone=JSON.parse(JSON.stringify(spec));
  const data=clone.data.filter(trace=>!trace.meta?.date || trace.meta.date===day);
  compactLegend(data);
  const layout=sizedLayout(clone,index);
  layout.title.text=layout.title.text.replace(/[0-9]{4}-[0-9]{2}-[0-9]{2}(?: – [0-9]{4}-[0-9]{2}-[0-9]{2}(?: · selected days)?)?/g,day);
  layout.xaxis.range=range;layout.xaxis.autorange=false;layout.annotations=[];
  if(layout.meta?.kind==='hourly') {
    const heat=data.find(t=>t.meta?.kind==='hourly_heatmap');
    const bars=data.find(t=>t.meta?.kind==='hourly_histogram');
    const row=heat.y.indexOf(day);
    heat.y=[day];heat.z=row>=0?[heat.z[row]]:[Array(24).fill(null)];
    heat.customdata=row>=0?[heat.customdata[row]]:[[]];
    bars.y=heat.z[0].map((value,h)=>heat.customdata[0][h]?.[5]?value:null);
    bars.customdata=bars.y.map(v=>v===null?0:1);
    bars.name='Hourly '+heat.meta.label.toLowerCase();bars.meta.label=bars.name;
    layout.yaxis.autorange='reversed';delete layout.yaxis.range;
    layout.yaxis2.autorange=true;delete layout.yaxis2.range;
    layout.yaxis2.title.text=heat.meta.unit;
    if(heat.z[0].every(v=>v===null))layout.annotations=[{text:'No available treatment data',xref:'paper',yref:'paper',x:.5,y:.7,showarrow:false}];
    return {data,layout};
  }

  const recorded=data.filter(t=>t.meta?.date===day);
  const relevant=layout.title.text.startsWith('Glucose ·')?recorded.filter(t=>t.meta.kind==='glucose'):recorded;
  if(index>0 && !relevant.some(t=>Array.isArray(t.y) && t.y.some(v=>v!==null)))layout.annotations=[{text:'No recorded data for this day',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false}];
  const isGlucose=index===0?currentOverlay==='Glucose':layout.title.text.startsWith('Glucose ·');
  const isTarget=index===0?currentOverlay==='Nightscout targets':layout.title.text.startsWith('Temp targets ·');
  const scale=navigation.unit==='mmol/L'?1:18;
  let peak=0;data.filter(t=>t.meta?.kind==='glucose').forEach(t=>t.y.forEach(y=>{if(y!==null)peak=Math.max(peak,y);}));
  const maximum=Math.max(20*scale,peak>20*scale?Math.ceil(peak*1.05/scale)*scale:20*scale);
  [layout.yaxis,layout.yaxis2].filter(Boolean).forEach(axis=>{delete axis.range;axis.autorange=true;delete axis.matches;delete axis.autorangeoptions;});
  if(isGlucose){const axis=index===0?layout.yaxis2:layout.yaxis;axis.range=[0,maximum];axis.autorange=false;}
  if(isTarget){const axis=index===0?layout.yaxis2:layout.yaxis;axis.range=[0,20*scale];axis.autorange=false;}
  if(index===0 && navigation.same_scale && layout.yaxis2){
    let low=0,high=isGlucose?maximum:isTarget?20*scale:0;
    data.forEach(t=>{if(Array.isArray(t.y))t.y.forEach(y=>{if(Number.isFinite(y)){low=Math.min(low,y);high=Math.max(high,y);}});});
    const padding=data.some(t=>t.mode?.includes('text')) ? .20 : .08;
    const span=Math.max(high-low,1),limits=[low<0?low-.05*span:0,high+padding*span];
    layout.yaxis.range=limits;layout.yaxis2.range=limits;layout.yaxis.autorange=false;layout.yaxis2.autorange=false;layout.yaxis2.matches='y';
  }
  // Recompute per displayed day; do not retain a larger day's label padding.
  const labelAxes=new Set(data.filter(t=>t.mode?.includes('text')).map(t=>t.yaxis || 'y'));
  labelAxes.forEach(name=>{
    const axis=layout['yaxis'+name.slice(1)];axis.layer='below traces';layout.xaxis.layer='below traces';
    if(axis.autorange===false)return;
    const values=data.filter(t=>(t.yaxis || 'y')===name).flatMap(t=>t.y || []).filter(Number.isFinite);
    if(values.length){const high=Math.max(...values),span=Math.max(high-Math.min(0,...values),1);axis.autorangeoptions={include:high+.20*span};}
  });
  layout.uirevision=day+':'+currentOverlay;
  return {data,layout};
}
function drawCalendar() {
  dateCalendar.replaceChildren();
  if(!navigation)return;
  const months=[...new Set(navigation.days.map(day=>day.slice(0,7)))];
  months.forEach(month=>{
    const [year,number]=month.split('-').map(Number);
    const title=document.createElement('div');title.className='calendar-month';title.textContent=new Date(year,number-1,1).toLocaleDateString(undefined,{month:'long',year:'numeric'});dateCalendar.appendChild(title);
    const grid=document.createElement('div');grid.className='calendar-grid';dateCalendar.appendChild(grid);
    ['M','T','W','T','F','S','S'].forEach(text=>{const label=document.createElement('span');label.textContent=text;grid.appendChild(label);});
    const offset=(new Date(year,number-1,1).getDay()+6)%7;
    for(let i=0;i<offset;i++)grid.appendChild(document.createElement('span'));
    for(let i=1;i<=new Date(year,number,0).getDate();i++) {
      const day=month+'-'+String(i).padStart(2,'0'),button=document.createElement('button');button.type='button';button.textContent=String(i);button.disabled=!navigation.days.includes(day);button.title=day+(button.disabled?' · not loaded':' · loaded');button.setAttribute('aria-pressed',String(selectedDays.includes(day)));
      button.addEventListener('click',()=>{dateCalendar.hidden=true;dayLabel.setAttribute('aria-expanded','false');cycleDay(0,day);});grid.appendChild(button);
    }
  });
}
dayLabel.addEventListener('click',()=>{drawCalendar();dateCalendar.hidden=!dateCalendar.hidden;dayLabel.setAttribute('aria-expanded',String(!dateCalendar.hidden));});
async function toggleSMB(index) {
  if(!ready || syncing)return;
  return enqueue(async()=>{
    const next=!excludeSMB,range=graphs[0]._fullLayout.xaxis.range.slice();
    syncing=true;controls();clearHover();
    try {
      const source=next?navigation.bolus_without_smb[dateCycled?'daily':'selected']:(dateCycled?navigation.figures[index]:specs[index]);
      const view=dateCycled?dailyView(source,index,selectedDays[0],range):JSON.parse(JSON.stringify(source));
      view.layout=sizedLayout(view,index);view.layout.xaxis.range=range;view.layout.xaxis.autorange=false;
      await Plotly.react(graphs[index],view.data,view.layout);excludeSMB=next;
    } catch(error) {card.textContent='Could not update SMB filter.';}
    finally {syncing=false;controls();}
  });
}
async function cycleDay(direction,requestedDay=null) {
  if(!navigation || !ready || syncing)return;
  return enqueue(async()=>{
    const current=direction>0?selectedDays[selectedDays.length-1]:selectedDays[0];
    const index=(navigation.days.indexOf(current)+direction+navigation.days.length)%navigation.days.length;
    const day=requestedDay || navigation.days[index], range=graphs[0]._fullLayout.xaxis.range.slice();
    syncing=true;controls();clearHover();
    try {
      const source=navigation.figures.slice();
      if(excludeSMB)source.forEach((spec,i)=>{if(spec.layout.meta?.kind==='hourly' && spec.layout.meta.dataset==='bolus')source[i]=navigation.bolus_without_smb.daily;});
      if(navigation.overlays)source[0]=navigation.overlays[currentOverlay].daily;
      const views=source.map((spec,i)=>dailyView(spec,i,day,range));
      await Promise.all(graphs.map((div,i)=>Plotly.react(div,views[i].data,views[i].layout)));
      selectedDays=[day];dateCycled=true;updateSummary();graphs.forEach(tidyLabels);
    } catch(error) {card.textContent='Could not change the displayed day. Reopen the graph view.';}
    finally {syncing=false;controls();}
  });
}
async function changeOverlay(requested) {
  if(!navigation?.overlays || !ready || syncing)return;
  return enqueue(async()=>{
    const previous=currentOverlay;
    syncing=true;controls();clearHover();
    try {
      currentOverlay=requested;
      const range=graphs[0]._fullLayout.xaxis.range.slice();
      let view;
      if(dateCycled)view=dailyView(navigation.overlays[currentOverlay].daily,0,selectedDays[0],range);
      else {
        view=JSON.parse(JSON.stringify(navigation.overlays[currentOverlay].selected));
        view.layout=sizedLayout(view,0);view.layout.xaxis.range=range;view.layout.xaxis.autorange=false;
        view.layout.uirevision='overlay:'+currentOverlay;
      }
      await Plotly.react(graphs[0],view.data,view.layout);tidyLabels(graphs[0]);
    } catch(error) {currentOverlay=previous;card.textContent='Could not change overlay. Reopen the graph view.';}
    finally {syncing=false;controls();}
  });
}
previousDay.addEventListener('click',()=>cycleDay(-1));
nextDay.addEventListener('click',()=>cycleDay(1));
expand.addEventListener('click',async()=>{
  try {
    if(document.fullscreenElement)await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  }catch(error){card.textContent='Browser blocked fullscreen. Use browser fullscreen (F11) for more room.';}
});
document.addEventListener('fullscreenchange',()=>{expand.textContent=document.fullscreenElement?'↙ Exit expanded view':'⛶ Expand graphs';scheduleLayout();});
const observer=new ResizeObserver(scheduleLayout);
observer.observe(viewer);observer.observe(panels);
if(typeof IntersectionObserver!=='undefined')new IntersectionObserver(entries=>{
  intersects=entries.some(entry=>entry.isIntersecting);
  if(!intersects)lastSize='';
  scheduleLayout();
}).observe(viewer);
controls();startPlots();
</script></body></html>""".replace('__VIEWER_PAYLOAD__',payload_json,1)


def render_graphs(figures, dark, navigation=None, cache=None):
    # A fixed profile plus a separately scrollable stack works on short screens
    # without a page-level overlay covering the editor or save controls.
    html = cached(cache,'html',(navigation['render_key'],dark),lambda: viewer_html(figures,dark,navigation),limit=3) if cache is not None and navigation and 'render_key' in navigation else viewer_html(figures,dark,navigation)
    st.iframe(html,height=860 if len(figures)>1 else 410,tab_index=0)
