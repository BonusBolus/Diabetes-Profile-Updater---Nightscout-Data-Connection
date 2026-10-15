"""Data banks for the browser's custom graph; no additional Nightscout requests."""
import json
from plotly.utils import PlotlyJSONEncoder
from html import escape
import plotly.graph_objects as go
from chart_cache import cached
from appearance import COLORS as METRIC_COLORS, LIGHT_COLORS
from nightscout_charts import dataset_traces, dataset_color
from nightscout_stats import hourly_events
from garmin_data import METRICS, metric_unit


def trace_data(traces):
    # Serialize traces directly; avoid constructing a temporary Figure/template.
    return json.loads(json.dumps([t.to_plotly_json() for t in traces],cls=PlotlyJSONEncoder))


def custom_bundle(loaded, days, all_days, mode, unit, dark, profiles, field_ids=None):
    fields=[]
    metric_colors=METRIC_COLORS if dark else LIGHT_COLORS
    for key,label,axis_unit in [
        ('glucose','Glucose',unit), ('basal','Temporary basal','U/h'),
        ('basal_percent','Temporary basal %','% field'),
        ('iob','IOB','U'), ('bolus','Boluses','U'), ('cob','COB','g'),
        ('carbs','Carbs','g'), ('target','Temporary targets',unit),
        ('variable_sens','VSENS',unit+'/U')]:
        if field_ids is not None and 'ns:'+key not in field_ids:continue
        daily=dataset_traces(key,loaded,all_days,'One day',unit,dark)
        if mode=='Median + band' and key in ('bolus','carbs'):
            stats=cached(loaded,'hourly',(key,tuple(days),False),lambda:hourly_events(loaded,key,days))
            without=cached(loaded,'hourly',(key,tuple(days),True),lambda:hourly_events(loaded,key,days,True)) if key=='bolus' else None
            selected=[go.Bar(x=[30+60*h for h in range(24)],y=stats['average'],width=50,
                name='Average hourly '+label.lower(),marker_color=dataset_color(key,dark),opacity=.65,
                customdata=stats['contributing'],
                meta=dict(kind='hourly_histogram',dataset=key,label='Average hourly '+label.lower(),unit=axis_unit,
                    hourly_values={s:stats[s] for s in ('average','median')},hourly_without_smb={s:without[s] for s in ('average','median')} if without else None))]
        else:
            selected=dataset_traces(key,loaded,days,mode,unit,dark)
        color=dataset_color(key,dark)
        fields.append(dict(color=color,id='ns:'+key,label=label,unit=axis_unit,dataset=key,group='Nightscout',
                           selected=trace_data(selected),
                           daily=trace_data(daily)))
    from event_stats import EVENT_LABELS, hourly_state_events
    for key,(label,axis_unit,color) in EVENT_LABELS.items():
        field_id='summary:'+key
        if field_ids is not None and field_id not in field_ids:continue
        stats=cached(loaded,'hourly',(key,tuple(days),False),lambda:hourly_state_events(loaded,key,days))
        all_stats=cached(loaded,'hourly',(key,tuple(all_days),False),lambda:hourly_state_events(loaded,key,all_days))
        def daily_bars(bank):
            return [go.Bar(x=[30+60*h for h in range(24)],y=values,width=45,name=label,marker_color=color,opacity=.7,
                meta=dict(kind='hourly_histogram',dataset=key,date=day,label=label,unit=axis_unit,legend_entry=True),
                hovertemplate=day+' · %{x:.0f} min<br>%{y:.4g} '+axis_unit+'<extra>'+label+'</extra>') for day,values in zip(bank['days'],bank['values'])]
        if mode=='Median + band' and len(days)>1:
            selected=[go.Bar(x=[30+60*h for h in range(24)],y=stats['average'],width=45,name='Average hourly '+label.lower(),marker_color=color,opacity=.7,
                meta=dict(kind='hourly_histogram',dataset=key,label=label,unit=axis_unit,legend_entry=True,hourly_values={s:stats[s] for s in ('average','median')}),
                customdata=stats['contributing'],hovertemplate='%{y:.4g} '+axis_unit+'<br>%{customdata} contributing days<extra>'+label+'</extra>')]
        else:selected=daily_bars(stats)
        fields.append(dict(id=field_id,label=label,unit=axis_unit,color=color,group='Summary',dataset=key,selected=trace_data(selected),daily=trace_data(daily_bars(all_stats))))
    for key,(label,axis_unit,color,*_) in METRICS.items():
        if field_ids is not None and 'garmin:'+key not in field_ids:continue
        if key=='g_activity':continue  # Activity intervals remain an event overlay, not a numeric axis.
        axis_unit=metric_unit(key,loaded)
        selected=dataset_traces(key,loaded,days,mode,unit,dark)
        daily=dataset_traces(key,loaded,all_days,'One day',unit,dark)
        fields.append(dict(id='garmin:'+key,label=label,unit=axis_unit,color=color,group='Garmin',dataset=key,
                           selected_unit='Average sleep (h/hour)' if key=='g_sleep' and mode=='Median + band' else axis_unit,
                           daily_unit=axis_unit,selected=trace_data(selected),
                           daily=trace_data(daily)))
    from recorded_profile_values import METRICS as PROFILE_METRICS, profile_traces
    for metric,(label,_,axis_unit) in PROFILE_METRICS.items():
        field_id='profile:'+metric+':nightscout'
        if field_ids is not None and field_id not in field_ids and not any(k.startswith('profile:'+metric+':') for k in field_ids):continue
        color=metric_colors[metric];axis_unit=axis_unit or unit+('/U' if metric=='isf' else '')
        fields.append(dict(id=field_id,label='Nightscout '+label,unit=axis_unit,color=color,metric_color=color,metric_label=label,
            profile_name='Nightscout profile',source_role='nightscout',source_color=color,group='Profiles',dataset='profile',
            selected=trace_data(profile_traces(loaded,metric,days,mode,unit,color)),daily=trace_data(profile_traces(loaded,metric,all_days,'One day',unit,color))))
    return dict(fields=fields,selected=['ns:glucose'] if not loaded['data']['glucose'].empty else [next((f['id'] for f in fields if f['group']=='Garmin'),'ns:glucose')])
