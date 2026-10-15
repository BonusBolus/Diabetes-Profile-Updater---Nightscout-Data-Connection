"""Distinct historical base schedules shared by table and graphical PDF blocks."""
from collections import Counter
from html import escape
import math
import pandas as pd
import plotly.graph_objects as go
from appearance import LIGHT_COLORS
from report_stats import day_window
from nightscout_charts import style_figure, date_label

FIELDS=('carbratio','sens','basal','target_low','target_high')


def schedule(profile,field):
    values={}
    entries=profile.get(field,[])
    if not isinstance(entries,list):return []
    for item in entries:
        if not isinstance(item,dict):continue
        try:
            seconds=float(item['timeAsSeconds']) if item.get('timeAsSeconds') is not None else sum(float(v)*m for v,m in zip(item['time'].split(':'),(3600,60,1)))
            value=float(item['value'])
            if not math.isfinite(value) or not 0<=seconds<86400:continue
            values[seconds]=value
        except (KeyError,TypeError,ValueError):continue
    result=[]
    for at,value in sorted(values.items()):
        if not result or result[-1][1]!=value:result.append((at,value))
    return result


def schedule_identity(profile):
    # Ignore metadata, numeric spelling and redundant identical schedule entries.
    units=str(profile.get('units','unknown')).lower()
    factor=1/18 if units in ('mg/dl','mgdl') else 1
    canonical=tuple((field,tuple((at,round(v*(factor if field in ('sens','target_low','target_high') else 1),9)) for at,v in schedule(profile,field))) for field in FIELDS)
    dia=profile.get('dia')
    try:dia=round(float(dia),9);dia=dia if math.isfinite(dia) else ''
    except (TypeError,ValueError):dia=str(dia or '')
    return (canonical,dia,units if units not in ('mmol/l','mmol','mg/dl','mgdl') else 'glucose')


def base_profiles(loaded,days,window):
    groups={};windows=[day_window(day,window,loaded['zone']) for day in days]
    for row in loaded.get('recorded_profiles',[]):
        start=pd.Timestamp(row['start']);end=min(pd.Timestamp(row['end']),loaded['loaded_at'])
        periods=[(max(start,a),min(end,b)) for a,b in windows if max(start,a)<min(end,b)]
        if not periods:continue
        raw=row.get('base_profile')
        if raw is None and row.get('percentage')==100 and row.get('timeshift') in (None,0):raw=row.get('profile')
        raw=raw or {};name=row['name'];key=(name,schedule_identity(raw) if raw else None)
        group=groups.setdefault(key,dict(name=name,profile=raw,periods=[],timezones=set()))
        group['periods'].extend(periods);group['timezones'].add(str(raw.get('timezone','unknown')))
    for key in list(groups):
        if key[1] is not None:continue
        known=[k for k in groups if k[0]==key[0] and k[1] is not None]
        if len(known)==1:groups[known[0]]['periods'].extend(groups.pop(key)['periods'])
    counts=Counter(g['name'] for g in groups.values());seen=Counter();result=[]
    for group in sorted(groups.values(),key=lambda g:(g['name'],min(a for a,b in g['periods']))):
        name=group['name'];seen[name]+=1
        group['label']=name+(f' · schedule variant {seen[name]} of {counts[name]}' if counts[name]>1 else '')
        group['variant']=counts[name]>1
        group['timezones']=sorted(group['timezones'])
        result.append(group)
    return result


def context(group,loaded):
    dates=sorted({str(pd.Timestamp(a).tz_convert(loaded['zone']).date()) for a,b in group['periods']})
    return ('Observed in report: '+dates[0]+(' – '+dates[-1] if dates[-1]!=dates[0] else '')+
            ' · Report/data timezone: '+loaded['zone']+' · Recorded profile timezone: '+', '.join(group['timezones'])+
            (' · Same base name has different recorded schedules; variants are shown separately.' if group['variant'] else '')+
            (' · Multiple recorded timezones share this schedule; clock times are shown as stored.' if len(group['timezones'])>1 else ''))


def graphical_profiles(loaded,days,window,unit):
    jobs=[]
    for group in base_profiles(loaded,days,window):
        p=group['profile'];source_unit=str(p.get('units','')).lower()
        factor=18 if source_unit in ('mmol/l','mmol') and unit=='mg/dL' else 1/18 if source_unit in ('mg/dl','mgdl') and unit=='mmol/L' else 1
        glucose_unit=unit if source_unit in ('mmol/l','mmol','mg/dl','mgdl') else 'recorded units (unspecified)'
        for metric,label,fields,axis_unit in [('ic','I:C',['carbratio'],'g/U'),('isf','ISF',['sens'],glucose_unit+'/U'),('basal','Basal',['basal'],'U/h'),('target','Target',['target_low','target_high'],glucose_unit)]:
            fig=go.Figure()
            for field in fields:
                points=schedule(p,field)
                if not points:continue
                xs=[at/60 for at,v in points]+[1440];ys=[v*(factor if metric in ('isf','target') else 1) for at,v in points];ys.append(ys[-1])
                fig.add_scatter(x=xs,y=ys,mode='lines',name=group['label']+(' · '+field.removeprefix('target_') if metric=='target' else ''),line=dict(color=LIGHT_COLORS[metric],shape='hv',width=2.5),meta=dict(kind='profile',label=group['label'],unit=axis_unit),hovertemplate='%{y:.4g} '+axis_unit+'<extra>%{fullData.name}</extra>')
            if not fig.data:continue
            style_figure(fig,label+' · '+group['label']+' · '+date_label(days),axis_unit,loaded['zone'],False)
            fig.update_yaxes(rangemode='tozero' if metric=='basal' else 'normal')
            fig.update_layout(meta=dict(kind='historical_profile',non_time=True),showlegend=False)
            jobs.append(dict(figure=fig.to_dict(),title=label+' · '+group['label'],note=context(group,loaded)))
    return jobs
