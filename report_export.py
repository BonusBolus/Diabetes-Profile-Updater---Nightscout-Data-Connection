"""Self-contained printable reports, using the app's existing browser graph renderer."""
from copy import deepcopy
from datetime import date, datetime
from html import escape
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from custom_graph import custom_bundle
from garmin_charts import activity_shapes, SLEEP_DAY_HEIGHT
from nightscout_charts import graph_figures, hourly_figure, date_label
from report_stats import report_range, observed_stats, day_window

from report_config import BLOCKS
from report_profiles import base_profiles, context as profile_context, graphical_profiles
from chart_cache import cached


def fmt(value,digits=1):
    return '—' if value is None else f'{value:,.{digits}f}'


def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+escape(str(v))+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'


def distribution_bar(row,prefix='own'):
    if row[prefix+'_within'] is None:return '<span>No glucose records</span>'
    return '<div class="distribution">'+''.join(f'<span style="width:{row[prefix+"_"+key]:.6f}%;background:{color}"></span>' for key,color in [('below','#e76b73'),('within','#47a85e'),('above','#dfad35')])+'</div>'


def overview(stats,unit,fields=None):
    fields=set(fields if fields is not None else ('coverage','glucose','treatments','events','app_range','comparison_range'))
    s=stats['total'];counts=s['changes']
    rows=[('Dates evaluated',str(s['days'])),('Glucose readings',str(s['readings'])),('Observed 5-minute bins',f'{s["bins"]} / {s["expected"]} expected'),
          ('Glucose coverage',fmt(s['coverage'])+'%'),('Site changes (recorded)',fmt(counts['Site Change'],0)),
          ('Sensor starts / changes (recorded)',fmt(counts['Sensor Start']+counts['Sensor Change'],0) if counts['Sensor Start'] is not None else '—'),('Insulin changes (recorded)',fmt(counts['Insulin Change'],0)),
          ('Mean glucose',fmt(s['mean'])+' '+unit),('Median glucose',fmt(s['median'])+' '+unit),('Lowest / highest bin',fmt(s['low'])+' / '+fmt(s['high'])+' '+unit),
          ('Standard deviation',fmt(s['sd'])+' '+unit),('Coefficient of variation',fmt(s['cv'])+'%'),
          ('Recorded bolus total',fmt(s['bolus'],3)+' U'),('Recorded carbs total',fmt(s['carbs'],0)+' g'),
          ('Average recorded bolus / day',fmt(s['bolus_daily'],3)+' U'),('Average recorded carbs / day',fmt(s['carbs_daily'])+' g')]
    ranges={'coverage':range(0,4),'events':range(4,7),'glucose':range(7,12),'treatments':range(12,16)}
    rows=[row for i,row in enumerate(rows) if any(i in ids and key in fields for key,ids in ranges.items())]
    html='<div class="overview-grid">'+table(['Measure','Value'],rows)+'<div>'
    scale=1 if unit=='mmol/L' else 18
    for prefix,title,lo in [('own','App range',4),('standard','3.9–10 comparison range',3.9)]:
        if ('app_range' if prefix=='own' else 'comparison_range') not in fields:continue
        html+='<h3>'+title+'</h3>'+distribution_bar(s,prefix)+table(['Glucose '+unit,'% observed bins'],[
            ('Below '+fmt(lo*scale),fmt(s[prefix+'_below'])),(fmt(lo*scale)+'–'+fmt(10*scale),fmt(s[prefix+'_within'])),('Above '+fmt(10*scale),fmt(s[prefix+'_above']))])
    html+='</div></div><p class="note">Statistics use one median value per observed 5-minute bin. Missing bins are excluded from glucose percentages; coverage is shown separately. Bin minima/maxima may differ from individual readings. App range includes both endpoints.</p>'
    html+=f'<p class="note">Treatment averages use {s["treatment_days"]} dates with a successful treatment load and elapsed time in the chosen window. Uploaded events may be incomplete. Sensor records can include restarts; they do not prove physical replacements. Total basal delivery and total insulin are not inferred from temporary-basal records.</p>'
    return html


def statistics_pages(stats,unit,layout='landscape'):
    result=[]
    # Distribution bars give these rows more height than plain text tables.
    # Leave room for wrapped headers and the explanatory note on A4 pages.
    page_size=15 if layout=='portrait' else 12
    for offset in range(0,len(stats['daily']),page_size):
        rows=stats['daily'][offset:offset+page_size]
        body='<table><thead><tr>'+''.join('<th>'+h+'</th>' for h in ['Date','Distribution','Below 4','4–10','Above 10','Readings','Coverage','Mean','SD','25%','Median','75%','Bolus U','Carbs g'])+'</tr></thead><tbody>'
        for r in rows:
            values=[r['date'],distribution_bar(r),fmt(r['own_below'])+'%',fmt(r['own_within'])+'%',fmt(r['own_above'])+'%',str(r['readings']),fmt(r['coverage'])+'%',fmt(r['mean']),fmt(r['sd']),fmt(r['q25']),fmt(r['median']),fmt(r['q75']),fmt(r['bolus'],3),fmt(r['carbs'],0)]
            body+='<tr>'+''.join('<td>'+ (v if i==1 else escape(v))+'</td>' for i,v in enumerate(values))+'</tr>'
        body+='</tbody></table><p class="note">Glucose statistics: '+escape(unit)+'. Range thresholds are 4–10 mmol/L (72–180 mg/dL). Percentages use observed five-minute bins; missing periods are not zeros. Treatment totals include uploaded SMB and user/unknown boluses, regardless of graph visibility filters.</p>'
        result.append(dict(title='Daily statistics',html=body))
    return result


def profile_pages(loaded,days,window):
    pages=[]
    for group in base_profiles(loaded,days,window):
        p=group['profile'];unit=str(p.get('units','unknown units'))
        periods=group['periods'];zone=ZoneInfo(loaded['zone'])
        rows=[]
        for field,label,units in [('carbratio','I:C','g/U'),('sens','ISF',unit+'/U'),('basal','Basal','U/h'),('target_low','Target low',unit),('target_high','Target high',unit)]:
            values=p.get(field,[])
            if not isinstance(values,list) or not values:rows.append((label,'—','Not available',units));continue
            for item in values:
                if not isinstance(item,dict):continue
                at=item.get('time')
                if at is None and isinstance(item.get('timeAsSeconds'),(int,float)):
                    seconds=int(item['timeAsSeconds']);at=f'{seconds//3600:02d}:{seconds%3600//60:02d}'
                rows.append((label,str(at or '?'),str(item.get('value','?')),units))
        for offset in range(0,len(rows),19):
            body='<p><strong>'+escape(group['label'])+'</strong> · Recorded profile timezone: '+escape(', '.join(group['timezones']))+' · DIA: '+escape(str(p.get('dia','not recorded')))+' h</p>'
            body+='<p class="note">'+escape(profile_context(group,loaded))+'</p>'
            body+=table(['Setting','Time','Value','Unit'],rows[offset:offset+19])
            body+='<p class="note">Base schedule from an uploaded unmodified profile switch or a recorded 100% unshifted state. Percentage states are grouped under this base name. If no base schedule was uploaded, values are marked unavailable; adjusted schedules are not substituted.</p>'
            # Keep long activity histories readable on separate pages.
            pages.append(dict(title='Base profiles · '+group['label'],html=body))
    if not pages:pages=[dict(title='Used profiles',html='<p>No effective-profile history was returned for this period. Reload Nightscout after updating; requested profile switches or the current editor profile are not assumed to be historical active profiles.</p>')]
    return pages


def histogram(stats,unit):
    values=np.array(stats['values']);width=.25 if unit=='mmol/L' else 5
    upper=max(20 if unit=='mmol/L' else 360,float(values.max()) if len(values) else 0)
    edges=np.arange(0,upper+2*width,width)
    centers=(edges[:-1]+edges[1:])/2;scale=1 if unit=='mmol/L' else 18
    fig=go.Figure()
    for label,color,mask in [('Below range','#e76b73',values<4*scale),('Within range','#47a85e',(values>=4*scale)&(values<=10*scale)),('Above range','#dfad35',values>10*scale)]:
        counts,_=np.histogram(values[mask],bins=edges)
        fig.add_bar(name=label,x=centers.tolist(),y=(100*counts/len(values)).tolist() if len(values) else [0]*len(counts),width=width,marker_color=color)
    fig.update_layout(title='Distribution of observed glucose',xaxis_title=unit,yaxis_title='% observed five-minute bins',template='plotly_white',barmode='stack',showlegend=True,meta=dict(empty=not len(values)),height=550,legend=dict(orientation='h',y=-.2))
    if not len(values):fig.add_annotation(text='No glucose records in the selected range',xref='paper',yref='paper',x=.5,y=.5,showarrow=False)
    return json.loads(fig.to_json())


def graph_bundle(loaded,nav,config,days,window,mode,job_id,block=None):
    from graph_view import figure_identity
    from nightscout_charts import LAYERS, GROUP_KEYS, normalize_layers
    state=deepcopy(config);state['defaultMode']=mode
    selected=[]
    for panel in state.get('panels',[]):
        kind=panel.get('graphType','daily')
        wanted=(kind=='daily' if block=='daily' else kind=='insight' if block=='insights' else kind in ('summary','overlay') if block=='summary' else
                kind=='daily' if mode=='One day' else kind=='overlay' if mode=='Multiple days' else kind in ('summary','insight'))
        if state.get('workspaceVersion'):panel['deleted']=panel.get('deleted',False) or not wanted
        elif block:panel['graphType']={'daily':'daily','summary':'summary','insights':'insight'}[block]
        if not panel.get('deleted'):selected.append(panel)
    if state.get('workspaceVersion') and not selected:return None
    bases={p.get('base','') for p in selected}
    datasets={b.split(':',1)[-1] for b in bases}
    if 'compact:glucose' in bases:datasets.add('compact')
    if any(b.startswith('custom:') for b in bases):datasets.add('custom')
    if ':iob' in bases:datasets.add('bolus')
    if ':cob' in bases:datasets.add('carbs')
    layers=[label for label in normalize_layers(nav['layers']) if not state.get('workspaceVersion') or any(k in datasets for k in GROUP_KEYS.get(LAYERS[label],[LAYERS[label]]))]
    profile=go.Figure(nav.get('report_profile',{}));profiles=nav.get('profiles',{})
    if config.get('metric') in profiles:profile=go.Figure(profiles[config['metric']])
    overlay=config.get('overlay','None') if not nav.get('data_only') else 'None'
    modes={mode}
    if block=='summary':modes={p.get('mode','Median + band') for p in selected} or {mode}
    mode='Median + band' if 'Median + band' in modes else next(iter(modes))
    banks={};raw=None
    for variant in sorted(modes):
        figs=graph_figures(profile,loaded,days,variant,layers,nav['unit'],False,overlay=overlay,data_only=nav.get('data_only',False),only_datasets=datasets if state.get('workspaceVersion') else None)
        values=[json.loads(f.to_json()) for f in figs]
        banks[variant]={figure_identity(f):r for f,r in zip(figs,values)}
        if variant==mode:raw=values
    custom=None
    if 'Custom graph' in layers:
        ids={key for p in selected for key in (p.get('custom') or {}).get('selected',[])}
        if not state.get('workspaceVersion'):ids=None
        custom_profiles={k:go.Figure(v) for k,v in nav.get('report_profiles',{}).items()}
        custom=custom_bundle(loaded,days,days,mode,nav['unit'],False,custom_profiles,field_ids=ids)
        for variant in modes:
            bank=custom if variant==mode else custom_bundle(loaded,days,days,variant,nav['unit'],False,custom_profiles,field_ids=ids)
            by_id={f['id']:f for f in bank['fields']}
            for field in custom['fields']:field.setdefault('modes',{})[variant]=by_id[field['id']]['selected']
    chosen={str(d) for d in days}
    events=[dict(event,intervals=[p for p in event.get('intervals',[]) if p['date'] in chosen]) for event in nav.get('profile_events',[]) if event['date'] in chosen or any(p['date'] in chosen for p in event.get('intervals',[]))]
    navigation=dict(workspace_graphs=bool(state.get('workspaceVersion')),mode_banks=banks,sleep_day_height=SLEEP_DAY_HEIGHT,state_scope='report-'+job_id,config_revision=1,saved_config=state,report_render=dict(id=job_id,range=window),
                    day_color_dates=nav.get('day_color_dates',nav.get('days',[str(d) for d in days])),data_only=nav.get('data_only',False),selected=[str(d) for d in days],days=[str(d) for d in days],mode=mode,unit=nav['unit'],
                    layers=layers,metric=config.get('metric'),profiles=profiles,overlay=overlay,overlays={overlay:dict(selected=raw[0],daily=raw[0])},figures=raw,
                    show_targets=config.get('showTargets',True),same_scale=config.get('sameScale',False),custom=custom,
                    custom_ids=config.get('customVisible',nav.get('custom_ids')),custom_catalog=[p['id'] for p in config.get('customPanels',[])],
                    automation_notes=[e for e in nav.get('automation_notes',[]) if e['date'] in chosen],activity_bands=activity_shapes(loaded,days,'One day'),
                    change_events=[e for e in nav.get('change_events',[]) if e['date'] in chosen],profile_events=events,garmin_units=nav.get('garmin_units'),
                    garmin_sleep_notes=[n for n in nav.get('garmin_sleep_notes',[]) if n['date'] in chosen],summaries=[],garmin_daily=[],garmin_activities=[])
    from compact_glucose import basal_records
    from nightscout import daily_summary
    if 'Glucose Compact' in layers:
        navigation['compact_basal']=cached(loaded,'compact_basal',tuple(days),lambda:basal_records(loaded,days))
        navigation['summaries']=cached(loaded,'daily_stats',(tuple(days),nav['unit']),lambda:daily_summary(loaded,days,nav['unit']))
    if len(set(days))>1 and 'IOB + Boluses' in layers:
        f=json.loads(hourly_figure(loaded,'bolus',days,False,exclude_smb=True).to_json());navigation['bolus_without_smb']=dict(selected=f,daily=f)
    return dict(specs=raw,navigation=navigation)


def build_report(loaded,nav,request,progress=None):
    from graph_view import viewer_html,pack_payload
    from report_config import settings
    request=dict(request,**settings(request))
    days,window=report_range(request,loaded)
    blocks=[b for b in request['blocks'] if b['key']!='summary' or len(days)>1]
    if not blocks:raise ValueError('Choose at least one report block valid for these dates.')
    config=request.get('config',request.get('viewer'))
    if not isinstance(config,dict):raise ValueError('Graph configuration is missing. Export from the graph toolbar.')
    title=str(request.get('title') or 'Profile Studio report')[:120]
    total=2+sum(len(days) if b['key']=='daily' else 1 for b in blocks);done=0
    if progress:progress(done,total,'Preparing report blocks')
    stats=None
    if any(b['key'] in ('overview','statistics','distribution') for b in blocks):
        stats=cached(loaded,'report_stats',(tuple(days),tuple(window),nav['unit']),lambda:observed_stats(loaded,days,window,nav['unit']),limit=4)
    jobs=[];done=1
    labels=dict(overview='Overview',profiles='Base profiles',profile_graphs='Graphical profile overview',statistics='Daily statistics',distribution='Glucose distribution',daily='Daily graphs',summary='Summary graphs',insights='Insight graphs')
    for block in blocks:
        section=block['key'];start=len(jobs)
        if progress:progress(done,total,'Preparing '+labels[section])
        if section=='overview':jobs.append(dict(title='Overview',html=overview(stats,nav['unit'],request.get('overview_fields'))))
        elif section=='statistics':jobs.extend(statistics_pages(stats,nav['unit'],request['layout']))
        elif section=='profiles':jobs.extend(profile_pages(loaded,days,window))
        elif section=='profile_graphs':
            figures=graphical_profiles(loaded,days,window,nav['unit'])
            if figures:jobs.append(dict(title=labels[section],figures=figures))
        elif section=='distribution':jobs.append(dict(title='Distribution of glucose values',figure=histogram(stats,nav['unit']),note='Percent of observed five-minute glucose bins; gaps are excluded. Colors follow the app range (4–10 mmol/L).'))
        else:
            mode='One day' if section=='daily' else 'Median + band'
            for subset in ([[d] for d in days] if section=='daily' else [days]):
                if progress:progress(done,total,labels[section]+' · '+date_label(subset))
                if section=='daily':done+=1
                payload=graph_bundle(loaded,nav,block.get('viewer',config),subset,window,mode,str(len(jobs)),block=section)
                if payload:
                    heading={'daily':'Daily','summary':'Summary','insights':'Insights'}[section]+' · '+date_label(subset)
                    jobs.append(dict(title=heading,payload=payload,note=''))
        for job in jobs[start:]:
            job.update(block=section,graphs_per_page=block['graphs_per_page'])
            if section not in ('daily','summary','insights'):
                job['title']={'profile_graphs':'Profiles','statistics':'Statistics','distribution':'Glucose distribution'}.get(section,labels[section])+' · '+date_label(days)
        if section!='daily':done+=1
    if not jobs:raise ValueError('No report content is available. Add graphs to the selected report blocks, or choose a block with loaded data, then save the preset.')
    if progress:progress(done,total,'Bundling report')
    portrait=request['layout']=='portrait';count=request['graphs_per_page'];width=1000 if portrait else 1320
    slot_mm=(210 if portrait else 140)/count;height=round(width*slot_mm/(176 if portrait else 263))
    for job in jobs:
        if 'payload' in job:job['payload']=pack_payload(job['payload'])
    # Template is bundled once, reused in a sequential offscreen renderer. The
    # ordinary viewer remains untouched and all existing graph transforms run.
    template=viewer_html([go.Figure()],False,None)
    template=re.sub(r'const payload = .*?;\nconst specs =', 'const payload = __REPORT_PAYLOAD__;\nconst specs =',template,count=1)
    info=dict(title=title,filename=f'profile-studio-{days[0]}-{days[-1]}.html',period=f'{request.get("from_time","00:00")}–{request.get("until_time","24:00")} · {loaded["zone"]}',
              context_profiles=[e for e in nav.get('profile_events',[]) if e['date'] in {str(d) for d in days}],
              context_changes=[e for e in nav.get('change_events',[]) if e['date'] in {str(d) for d in days}],
              reserve_automation=any(e['date'] in {str(d) for d in days} and window[0]<=e['minute']<=window[1] for e in nav.get('automation_notes',[])),
              generated=datetime.now(ZoneInfo(loaded['zone'])).strftime('%Y-%m-%d %H:%M %Z'),jobs=jobs,template=template,
              settings=json.dumps(config,ensure_ascii=False,indent=2),layout=request['layout'],graphs_per_page=count,chart_height_mm=slot_mm,render_width=width,render_height=height)
    script=Path(__file__).with_name('report_document.js').read_text(encoding='utf-8')
    css=Path(__file__).with_name('report_document.css').read_text(encoding='utf-8')
    css+=f'@page{{size:A4 {request["layout"]};}}'
    if count>=5:css+='.page h1{font-size:16px}.page .subtitle{margin-bottom:6px;padding-bottom:5px}'
    if portrait:css+=':root{--page-width:190mm;--page-height:277mm;--body-height:230mm;--chart-height:210mm}.page h1{font-size:'+str(16 if count>=5 else 20)+'px}.page table{font-size:10px}.page th{font-size:9px}.page td,.page th{padding:5px 3px}'
    return '<!doctype html><html><head><meta charset="utf-8"><title>'+escape(title)+'</title><style>'+css+'</style></head><body><header class="screen"><strong>'+escape(title)+'</strong> <span id="progress">Preparing charts…</span><button id="print" disabled>Print / Save as PDF</button><p>Use the selected A4 orientation and disable browser headers/footers in the print dialog. Charts are generated locally; this document contains health data.</p></header><main id="pages"></main><iframe id="renderer" title="Report chart renderer"></iframe><script>const report='+json.dumps(info,ensure_ascii=False,allow_nan=False).replace('<','\\u003c')+';</script><script>'+script+'</script></body></html>'
