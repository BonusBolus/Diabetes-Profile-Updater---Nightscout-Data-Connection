"""Data banks for the browser's custom graph; no additional Nightscout requests."""
import json
from html import escape
import plotly.graph_objects as go
from chart_cache import cached
from appearance import COLORS as METRIC_COLORS, LIGHT_COLORS, palette, reference_identity_colors
from nightscout_charts import dataset_traces, dataset_color
from nightscout_stats import hourly_events


def custom_bundle(loaded, days, all_days, mode, unit, dark, profiles):
    fields=[]
    metric_colors=METRIC_COLORS if dark else LIGHT_COLORS
    source_colors=reference_identity_colors(dark)
    for key,label,axis_unit in [
        ('glucose','Glucose',unit), ('basal','Temporary basal','U/h'),
        ('basal_percent','Temporary basal %','% field'),
        ('iob','IOB','U'), ('bolus','Boluses','U'), ('cob','COB','g'),
        ('carbs','Carbs','g'), ('target','Temporary targets',unit),
        ('variable_sens','VSENS',unit+'/U')]:
        daily=dataset_traces(key,loaded,all_days,'One day',unit,dark)
        if mode=='Median + band' and key in ('bolus','carbs'):
            stats=cached(loaded,'hourly',(key,tuple(days),False),lambda:hourly_events(loaded,key,days))
            selected=[go.Bar(x=[30+60*h for h in range(24)],y=stats['average'],width=50,
                name='Average hourly '+label.lower(),marker_color=dataset_color(key,dark),opacity=.65,
                customdata=stats['contributing'],
                meta=dict(kind='hourly_histogram',dataset=key,label='Average hourly '+label.lower(),unit=axis_unit))]
        else:
            selected=dataset_traces(key,loaded,days,mode,unit,dark)
        color=dataset_color(key,dark)
        fields.append(dict(color=color,id='ns:'+key,label=label,unit=axis_unit,dataset=key,group='Nightscout',
                           selected=json.loads(go.Figure(selected).to_json())['data'],
                           daily=json.loads(go.Figure(daily).to_json())['data']))
    for metric,fig in profiles.items():
        groups={}
        for trace in fig.data:
            if (trace.meta or {}).get('kind')=='profile':
                groups.setdefault(trace.legendgroup or trace.name,[]).append(trace)
        for index,traces in enumerate(groups.values()):
            label=fig.layout.title.text.split(' · ')[0]+' · '+traces[0].name
            field_id=f'profile:{metric}:{index}'
            role=traces[0].meta.get('source_role','current')
            source_color=source_colors.get(role,palette(dark)['text'])
            data=json.loads(go.Figure(traces).to_json())['data']
            for trace in data:
                trace['hovertemplate']='%{customdata}<br>%{y:.4g} '+trace['meta']['unit']+'<extra>%{fullData.name}</extra>'
                trace['name']='<span style="color:'+metric_colors[metric]+'">'+escape(fig.layout.title.text.split(' · ')[0])+'</span> · <span style="color:'+source_color+'">'+escape(traces[0].name)+'</span>'
                trace['legendgroup']=field_id
                trace['meta']['label']=label+(' · low' if trace['meta']['label'].endswith(' · low') else ' · high' if trace['meta']['label'].endswith(' · high') else '')
            fields.append(dict(id=field_id,label=label,unit=traces[0].meta['unit'],
                               color=traces[0].line.color or metric_colors[metric],metric_color=metric_colors[metric],
                               metric_label='Target range' if metric=='target' else fig.layout.title.text.split(' · ')[0],
                               profile_name=traces[0].name,source_role=role,source_color=source_color,
                               group='Profiles',dataset='profile',selected=data,daily=data))
    return dict(fields=fields,selected=['ns:glucose'])
