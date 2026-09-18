"""Recorded Nightscout charts, without changing the editable profile."""
from datetime import datetime, time, timedelta
from html import escape
import math
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from appearance import palette
from nightscout import UTC, glucose_summary, local_points

LAYERS = {"Glucose": "glucose", "Temporary basal": "basal", "Boluses": "bolus",
          "Carbs": "carbs", "IOB": "iob", "COB": "cob", "Nightscout targets": "target"}
OVERLAY_CHOICES = ["None", "Glucose", "Temporary basal", "IOB + boluses", "COB + carbs", "Nightscout targets"]
OVERLAYS = {**{label: [key] for label, key in LAYERS.items()},
            "IOB + boluses": ["iob", "bolus"], "COB + carbs": ["cob", "carbs"]}
COLORS = {"glucose": "#32cd32", "basal": "#00cfe8", "basal_percent": "#00cfe8",
          "iob": "#2196f3", "bolus": "#42baf5", "carbs": "#ff9800", "cob": "#ff9800", "target": "#64d86a"}
TARGET_COLORS = {"Eating Soon":"#ff9800", "Activity":"#59cddd", "Hypo":"#f44336", "Custom":"#64d86a"}


def target_reason(reason):
    return {"eating soon":"Eating Soon", "activity":"Activity", "hypo":"Hypo", "hypoglycemia":"Hypo"}.get(str(reason).strip().lower(), "Custom")


def event_sizes(values, key):
    # Fixed scales across days; sqrt makes visible area roughly proportional to
    # amount, with readable minimums and capped large events. Units stay separate.
    factor = 11 if key == 'bolus' else 3
    return [max(6,min(30,factor*math.sqrt(max(0,y)))) if y is not None else 6 for y in values]


DASHES = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]


def date_label(days):
    days = sorted(set(days))
    if not days:
        return "No dates selected"
    if len(days) == 1:
        return days[0].isoformat()
    suffix = " · selected days" if (days[-1]-days[0]).days + 1 != len(days) else ""
    return f"{days[0].isoformat()} – {days[-1].isoformat()}{suffix}"


def rgba(color, alpha):
    return f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},{alpha})"


def interval_points(frame, zone, day):
    """Clip intervals to a local day; do not bridge gaps or DST clock jumps."""
    tz = ZoneInfo(zone)
    start = datetime.combine(day, time.min, tz).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, tz).astimezone(UTC)
    xs, ys, labels = [], [], []
    for item in frame.to_dict("records"):
        a, b = max(start, item["time"]), min(end, item["end"])
        if a >= b:
            continue
        times = [a, b]
        if a.astimezone(tz).utcoffset() != b.astimezone(tz).utcoffset():
            times = list(pd.date_range(a, b, freq="1min"))
            if times[-1] != b:
                times.append(b)
        previous = None
        for at in times:
            local = at.astimezone(tz)
            minute = 1440 if at == end else local.hour*60 + local.minute + local.second/60
            if previous and (minute < previous[0] or
                             abs((minute-previous[0]) - (at-previous[1]).total_seconds()/60) > .01):
                xs.append(None); ys.append(None); labels.append("")
            xs.append(minute); ys.append(item["value"]); labels.append(local.strftime("%Y-%m-%d %H:%M %z") + (" · " + item["source"] if "source" in item else ""))
            previous = minute, at
        xs.append(None); ys.append(None); labels.append("")
    return xs, ys, labels


def dataset_traces(key, loaded, days, mode, unit, dark):
    data, zone = loaded['data'], loaded['zone']
    frame = data.get(key, pd.DataFrame())
    color = COLORS[key]
    if not dark:
        color = {"glucose":"#218c24", "basal":"#0089a4", "basal_percent":"#0089a4",
                 "iob":"#177cb8", "bolus":"#177cb8", "carbs":"#bf7100", "cob":"#bf7100", "target":"#24843b"}[key]
    if key == 'target' and not frame.empty:
        frame = frame[frame['source'] == 'Temporary target']
    if frame.empty:
        return []
    if key == 'glucose' and mode == 'Median + band':
        stats = glucose_summary(frame, zone, days, unit)
        if stats.empty:
            return []
        return [
            go.Scatter(x=stats.minute, y=stats.low, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'),
            go.Scatter(x=stats.minute, y=stats.high, mode='lines', line=dict(width=0), fill='tonexty',
                       fillcolor=rgba(color,.18), name='Glucose 25–75% band', hoverinfo='skip'),
            go.Scatter(x=stats.minute, y=stats['median'], mode='lines', name='Median glucose',
                       line=dict(color=color,width=2.5), customdata=stats['days'], meta=dict(label='Median glucose',unit=unit,kind='median'), connectgaps=False,
                       hovertemplate='%{y:.2f} '+unit+'<br>%{customdata:.0f} days in this 5-minute bin<extra>Median</extra>')]
    traces = []
    sample_unit = {'glucose':unit,'basal':'U/h','basal_percent':'% field','bolus':'U','iob':'U','carbs':'g','cob':'g','target':unit}[key]
    for index, day in enumerate(days):
        dash = DASHES[index % len(DASHES)]
        name = {'glucose':'Glucose','basal':'Temp basal','basal_percent':'Temp basal %',
                'bolus':'Bolus','iob':'IOB','carbs':'Carbs','cob':'COB','target':'Nightscout target'}[key]
        if key == 'target':
            # Split only the color groups, preserving explicit gaps between
            # intervals and separate low/high traces for each filled band.
            colored = frame.copy()
            colored['reason'] = colored.get('reason', pd.Series('',index=colored.index)).fillna('')
            colored['color_reason'] = colored['reason'].map(target_reason)
            for (source, reason), part in colored.groupby(['source','color_reason'],sort=False):
                target_color = TARGET_COLORS[reason]
                if not dark:
                    target_color = {'Eating Soon':'#bf7100','Activity':'#008b9c','Hypo':'#cc2727','Custom':'#24843b'}[reason]
                label = source + (' · '+reason if source == 'Temporary target' else '')
                for field in ('low','high'):
                    values = part.rename(columns={field:'value'}).drop(columns=['high' if field=='low' else 'low'])
                    xs,ys,labels = interval_points(values,zone,day)
                    if not xs:
                        continue
                    ys = [y/18 if unit=='mmol/L' and y is not None else y for y in ys]
                    # Reason is retained even for custom or uploader-specific text.
                    details=[]
                    for row in part.to_dict('records'):
                        one = pd.DataFrame([dict(row,value=row[field])])
                        rx,_,_ = interval_points(one,zone,day)
                        text = str(row.get('reason') or 'Unspecified') if source=='Temporary target' else ''
                        details.extend([text]*len(rx))
                    traces.append(go.Scatter(x=xs,y=ys,customdata=details,name='Temp target · '+reason,
                        meta=dict(label=source+' '+field,unit=unit,date=str(day),kind='target',legend_entry=field=='high'),
                        legendgroup=f'target-{reason}',showlegend=field=='high',mode='lines',
                        line=dict(color=target_color,shape='hv',width=2,dash='solid'),
                        fill='tonexty' if field=='high' else None,fillcolor=rgba(target_color,.16),connectgaps=False,
                        hovertemplate='%{y:.2f} '+unit+'<extra>'+escape(label)+'</extra>'))
            continue
        if key in ('basal','basal_percent'):
            xs,ys,labels = interval_points(frame,zone,day)
            groups = [(name,xs,ys,labels)]
        else:
            points = local_points(frame,zone,[day])
            groups = []
            subsets = [(label,part) for label,part in points.groupby('label',sort=False)] if key=='bolus' else [(name,points)]
            for group, part in subsets:
                xs,ys,labels = [],[],[]
                previous = None
                for item in part.to_dict('records'):
                    at, minute = item['time'], item['minute']
                    if previous and key in ('glucose','iob','cob') and (
                        (at-previous[0]).total_seconds()>900 or minute<previous[1] or
                        abs(minute-previous[1]-(at-previous[0]).total_seconds()/60)>.01):
                        xs.append(None); ys.append(None); labels.append('')
                    xs.append(minute)
                    ys.append(item['value']/18 if key=='glucose' and unit=='mmol/L' else item['value'])
                    labels.append(at.strftime('%Y-%m-%d %H:%M %z')+' · '+escape(item['label']))
                    previous=at,minute
                groups.append((group,xs,ys,labels))
        for group,xs,ys,labels in groups:
            if not xs:
                continue
            symbol = 'line-ew' if group=='User bolus' else 'triangle-up' if group=='SMB' else 'diamond-open' if key=='bolus' else 'diamond' if key=='carbs' else ['circle','square','diamond','cross'][index%4]
            marker_color = color
            if key=='glucose':
                scale=1 if unit=='mmol/L' else 18
                marker_color=['#f44336' if y is not None and y<4*scale else '#ff9800' if y is not None and y>10*scale else color for y in ys]
            sizes = event_sizes(ys,key) if key in ('carbs','bolus') else 5
            amount_labels = key=='carbs' or group=='User bolus'
            traces.append(go.Scatter(x=xs,y=ys,customdata=labels,name=group,
                meta=dict(label=group,unit=sample_unit,date=str(day),kind=key,legend_entry=True),
                text=[f'{y:g} {sample_unit}' if y is not None else '' for y in ys] if amount_labels else None,
                textposition='top center',textfont=dict(size=12,color=color),cliponaxis=True,
                legendgroup=group,mode='markers+text' if amount_labels else 'markers' if key in ('carbs','bolus') else 'lines+markers' if key=='glucose' else 'lines',
                line=dict(color=color,width=2,dash='solid' if key in ('iob','cob') else dash,shape='hv' if key.startswith('basal') or key=='cob' else 'linear'),
                marker=dict(color=marker_color,symbol=symbol,size=sizes,
                            line=dict(color=color,width=[v*.55 for v in sizes]) if group=='User bolus' else dict(width=0)),
                fill='tozeroy' if key in ('basal','basal_percent','cob','iob') else None,
                fillcolor=rgba(color,.24 if mode=='One day' else .10), connectgaps=False,
                hovertemplate='%{customdata}<br>%{y:.3f} '+sample_unit+'<extra>'+escape(group)+'</extra>'))
    return traces


def compact_legend(fig):
    """One concise legend item per series, while dates remain in hover metadata."""
    seen = set()
    for trace in fig.data:
        meta = trace.meta if isinstance(trace.meta, dict) else {}
        eligible = meta.get('legend_entry', trace.showlegend is not False)
        group = trace.legendgroup or trace.name
        trace.showlegend = eligible and group not in seen
        if eligible:
            seen.add(group)


def style_figure(fig, title, ylabel, zone, dark, height=205):
    theme=palette(dark)
    fig.update_layout(title=dict(text=title,font=dict(size=16),x=.01),height=height,
        template='plotly_dark' if dark else 'plotly_white',paper_bgcolor=theme['background'],
        plot_bgcolor=theme['surface'],font=dict(color=theme['text'],size=14),
        margin=dict(l=62,r=62,t=36,b=62),hovermode='closest',hoverdistance=25,
        legend=dict(orientation='h',y=-.32,yanchor='top',x=0,font=dict(size=12),maxheight=.15),
        xaxis=dict(range=[0,1440],tickvals=list(range(0,1441,240)),
                   ticktext=[f'{x//60:02}:00' for x in range(0,1441,240)],title=None),
        meta=dict(zone=zone))
    fig.update_xaxes(tickfont_size=13,title_font_size=14,gridcolor=theme['grid'],showspikes=True,spikemode='across',spikesnap='data',spikethickness=1)
    fig.update_yaxes(tickfont_size=13,title_font_size=14,title_standoff=8,automargin=True,gridcolor=theme['grid'],rangemode='tozero')
    fig.update_yaxes(title_text=ylabel,secondary_y=False) if fig._grid_ref else fig.update_yaxes(title_text=ylabel)


def glucose_axis(fig, loaded, days, unit, secondary=False, fixed_band=True):
    points=local_points(loaded['data']['glucose'],loaded['zone'],days)
    scale=1 if unit=='mmol/L' else 18
    peak=points['value'].max()/18*scale if not points.empty else 0
    maximum=max(20*scale, math.ceil(peak*1.05/scale)*scale if peak>20*scale else 20*scale)
    axis='yaxis2' if secondary else 'yaxis'
    fig.update_layout(**{axis:dict(range=[0,maximum],autorange=False)})
    if fixed_band:
        fig.add_shape(type='rect',xref='x',yref='y2' if secondary else 'y',x0=0,x1=1440,
                      y0=4*scale,y1=10*scale,line_width=0,fillcolor='rgba(50,205,50,.12)',layer='below')
        fig.add_trace(go.Scatter(x=[None],y=[None],mode='lines',name=f'Range {4*scale:g}–{10*scale:g}',
                                 line=dict(color='rgba(50,205,50,.5)',width=8),hoverinfo='skip',
                                 yaxis='y2' if secondary else 'y'))


def graph_figures(profile_figure, loaded, days, mode, layers, unit, dark, overlay='None', show_targets=True, same_scale=False):
    """Return a pinned profile figure followed by independent, time-aligned panels."""
    dates=date_label(days)
    title=profile_figure.layout.title.text or 'Profile'
    title = title.split(' · ')[0]+' · '+dates
    top=make_subplots(specs=[[{'secondary_y':True}]]) if overlay!='None' else go.Figure()
    for trace in profile_figure.data:
        if overlay != 'None':
            top.add_trace(trace, secondary_y=False)
        else:
            top.add_trace(trace)
    if overlay!='None':
        keys=OVERLAYS[overlay]
        key=keys[0]
        for overlay_key in keys:
            for trace in dataset_traces(overlay_key,loaded,days,mode,unit,dark):
                top.add_trace(trace,secondary_y=True)
        if key=='glucose' and show_targets:
            for trace in dataset_traces('target',loaded,days,mode,unit,dark):
                top.add_trace(trace,secondary_y=True)
        overlay_unit={'glucose':unit,'target':unit,'basal':'U/h','iob':'U','bolus':'U','carbs':'g','cob':'g'}[key]
        top.update_yaxes(title_text=overlay_unit,secondary_y=True,showgrid=False)
        if key=='glucose':
            glucose_axis(top,loaded,days,unit,secondary=True)
    style_figure(top,title,profile_figure.layout.yaxis.title.text,loaded['zone'],dark,height=245)
    top.layout.yaxis.rangemode = profile_figure.layout.yaxis.rangemode or 'normal'
    if overlay!='None':
        top.update_yaxes(showgrid=False,secondary_y=True)
    if overlay!='None' and same_scale:
        # Match numeric limits, without converting between different quantities.
        values=[float(y) for trace in top.data for y in trace.y if y is not None and pd.notna(y)]
        bounds=[0]+values
        for axis in (top.layout.yaxis,top.layout.yaxis2):
            if axis.range:
                bounds.extend(axis.range)
        low,high=min(bounds),max(bounds)
        span=max(high-low,1)
        limits=[low-.05*span if low<0 else 0,high+.08*span]
        top.update_yaxes(range=limits,autorange=False)
        top.update_yaxes(matches='y',secondary_y=True)
    top.update_layout(uirevision=profile_figure.layout.uirevision)
    selected={LAYERS[label] for label in layers}
    groups=[(['glucose'],'Glucose',unit),(['basal'],'Temp basal','U/h'),
            (['iob','bolus'],'IOB & boluses','U'),(['cob','carbs'],'COB & carbs','g'),
            (['target'],'Temp targets',unit)]
    figures=[top]
    if 'basal' in selected and not loaded['data']['basal_percent'].empty:
        groups.insert(2,(['basal_percent'],'Temp basal %','% field'))
        selected.add('basal_percent')
    for keys,label,ylabel in groups:
        active=[key for key in keys if key in selected]
        if not active:
            continue
        fig=go.Figure()
        for key in active:
            for trace in dataset_traces(key,loaded,days,mode,unit,dark):
                fig.add_trace(trace)
        has_records = any(any(pd.notna(y) for y in trace.y) for trace in fig.data)
        if 'glucose' in active:
            if show_targets:
                for trace in dataset_traces('target',loaded,days,mode,unit,dark):
                    fig.add_trace(trace)
            glucose_axis(fig,loaded,days,unit)
        style_figure(fig,f'{label} · {dates}',ylabel,loaded['zone'],dark)
        if not has_records:
            fig.add_annotation(text='No recorded data for the selected dates',xref='paper',yref='paper',x=.5,y=.5,showarrow=False)
        figures.append(fig)
    for figure in figures:
        compact_legend(figure)
    return figures
