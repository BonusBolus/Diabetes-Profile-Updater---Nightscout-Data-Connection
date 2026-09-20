"""Recorded Nightscout charts, without changing the editable profile."""
from datetime import datetime, time, timedelta
from html import escape
import math
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from appearance import palette
from chart_cache import cached
from nightscout_stats import continuous_summary, hourly_events
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


def padded_range(values, pad=.18):
    """A y-range with headroom above the data instead of a tight autorange."""
    finite = [float(v) for v in values if v is not None and pd.notna(v)]
    if not finite:
        return None
    low, high = min(0., min(finite)), max(finite)
    span = max(high - low, 1e-9)
    return [low - .4*pad*span if low < 0 else 0, high + pad*span]


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
    cache_key=(key,tuple(days),mode,unit,dark)
    return cached(loaded,'traces',cache_key,lambda: _dataset_traces(key,loaded,days,mode,unit,dark),limit=48)


def _dataset_traces(key, loaded, days, mode, unit, dark):
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
    if mode == 'Median + band' and key in ('carbs','bolus'):
        return []  # Event amounts belong in the hourly summaries, not a pile of markers.
    if mode == 'Median + band' and key in ('glucose','iob','cob','basal','basal_percent'):
        stats=cached(loaded,'summaries',(key,tuple(days),unit),lambda: continuous_summary(loaded,key,days,unit))
        if stats.empty:return []
        label={'glucose':'Glucose','iob':'IOB','cob':'COB','basal':'Temp basal','basal_percent':'Temp basal %'}[key]
        sample_unit={'glucose':unit,'iob':'U','cob':'g','basal':'U/h','basal_percent':'% field'}[key]
        return [
            go.Scatter(x=stats.minute.tolist(), y=stats.low.tolist(), mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'),
            go.Scatter(x=stats.minute.tolist(), y=stats.high.tolist(), mode='lines', line=dict(width=0), fill='tonexty',
                       fillcolor=rgba(color,.18), name=label+' 25–75%', hoverinfo='skip'),
            go.Scatter(x=stats.minute.tolist(), y=stats['median'].tolist(), mode='lines', name='Median '+label.lower() if key=='glucose' else 'Median '+label,
                       line=dict(color=color,width=2.5,shape='hv' if key in ('basal','basal_percent','cob') else 'linear',dash='solid'),
                       fill='tozeroy' if key!='glucose' else None,fillcolor=rgba(color,.12),
                       customdata=stats['days'].tolist(), meta=dict(label='Median '+label,unit=sample_unit,kind='median',dataset=key), connectgaps=False,
                       hovertemplate='%{y:.3g} '+sample_unit+'<br>%{customdata:.0f} contributing days<extra>Median</extra>')]
    traces = []
    sample_unit = {'glucose':unit,'basal':'U/h','basal_percent':'% field','bolus':'U','iob':'U','carbs':'g','cob':'g','target':unit}[key]
    point_days = {}
    if key not in ("target","basal","basal_percent"):
        points = local_points(frame,zone,days)
        point_days = dict(tuple(points.groupby("day",sort=False))) if not points.empty else {}
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
            points = point_days.get(day, pd.DataFrame(columns=["label"]))
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
    maximum=max(20*scale, math.ceil(peak*1.15/scale)*scale if peak>20*scale else 20*scale)
    axis='yaxis2' if secondary else 'yaxis'
    fig.update_layout(**{axis:dict(range=[0,maximum],autorange=False)})
    if fixed_band:
        fig.add_shape(type='rect',xref='x',yref='y2' if secondary else 'y',x0=0,x1=1440,
                      y0=4*scale,y1=10*scale,line_width=0,fillcolor='rgba(50,205,50,.12)',layer='below')
        fig.add_trace(go.Scatter(x=[None],y=[None],mode='lines',name=f'Range {4*scale:g}–{10*scale:g}',
                                 line=dict(color='rgba(50,205,50,.5)',width=8),hoverinfo='skip',
                                 yaxis='y2' if secondary else 'y'))


def graph_figures(profile_figure, loaded, days, mode, layers, unit, dark, overlay='None', show_targets=True, same_scale=False, summary_layout=False, profile_only=False, exclude_smb=False):
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
        limits=[low-.08*span if low<0 else 0,high+.15*span]
        top.update_yaxes(range=limits,autorange=False)
        top.update_yaxes(matches='y',secondary_y=True)
    top.update_layout(uirevision=profile_figure.layout.uirevision)
    if profile_only:
        compact_legend(top)
        return [top]
    selected={LAYERS[label] for label in layers}
    groups=[(['glucose'],'Glucose',unit),(['basal'],'Temp basal','U/h'),
            (['iob','bolus'],'IOB & boluses','U'),(['cob','carbs'],'COB & carbs','g'),
            (['target'],'Temp targets',unit)]
    summary_layout = summary_layout or mode == 'Median + band'
    if summary_layout:
        groups=[(['glucose'],'Glucose',unit),(['basal'],'Temp basal','U/h'),
                (['iob'],'Median IOB' if mode=='Median + band' else 'IOB','U'),
                (['cob'],'Median COB' if mode=='Median + band' else 'COB','g'),(['target'],'Temp targets',unit)]
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
        elif 'glucose' not in active:
            rng=padded_range([y for trace in fig.data for y in trace.y])
            if rng:
                fig.update_yaxes(range=rng,autorange=False)
        figures.append(fig)
    if summary_layout:
        figures.extend(hourly_figure(loaded,key,days,dark,exclude_smb=exclude_smb and key=='bolus') for key in ("bolus","carbs"))
    for figure in figures:
        compact_legend(figure)
    return figures


def hourly_figure(loaded, key, days, dark, exclude_smb=False):
    stats=cached(loaded,'hourly',(key,tuple(days),exclude_smb),lambda: hourly_events(loaded,key,days,exclude_smb))
    label,unit=('Boluses','U') if key=='bolus' else ('Carbs','g')
    if exclude_smb:
        label='Boluses (excl. SMB)'
    color=COLORS[key];theme=palette(dark)
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.68,.32],vertical_spacing=.14)
    details=[[[day,f'{hour:02}:00–{hour+1:02}:00',value,stats['counts'][i][hour],stats['status'][i][hour],stats['complete'][i][hour]]
              for hour,value in enumerate(row)] for i,(day,row) in enumerate(zip(stats['days'],stats['values']))]
    fig.add_trace(go.Heatmap(x=[30+60*h for h in range(24)],y=stats['days'],z=stats['values'],customdata=details,
        colorscale=[[0,theme['surface']],[1,color]],zmin=0,xgap=1,ygap=1,hoverongaps=False,
        colorbar=dict(title=dict(text=unit),len=.6,y=.7,thickness=10),
        name=label+' hourly',meta=dict(kind='hourly_heatmap',label=label,unit=unit,dataset=key),
        hovertemplate='%{customdata[0]} · %{customdata[1]}<br>%{z:.3g} '+unit+' · %{customdata[3]} events<extra></extra>'),row=1,col=1)
    fig.add_trace(go.Bar(x=[30+60*h for h in range(24)],y=stats['median'],width=55,marker_color=color,
        customdata=stats['contributing'],name='Median hourly '+label.lower(),showlegend=False,
        meta=dict(kind='hourly_histogram',label='Median hourly '+label.lower(),unit=unit,dataset=key),
        hovertemplate='%{y:.3g} '+unit+'<br>%{customdata} complete days<extra></extra>'),row=2,col=1)
    height=min(540,max(290,205+len(days)*14))
    style_figure(fig,f'{label} hourly · {date_label(days)}','Date',loaded['zone'],dark,height=height)
    fig.update_layout(showlegend=False,margin=dict(l=90,r=64,t=40,b=36))
    fig.update_xaxes(range=[0,1440],tickvals=list(range(0,1441,240)),ticktext=[f'{x//60:02}:00' for x in range(0,1441,240)])
    fig.update_xaxes(matches='x',row=2,col=1)
    fig.update_yaxes(type='category',autorange='reversed',title_text='Date',tickfont_size=11,row=1,col=1)
    fig.update_yaxes(title_text='Median '+unit,rangemode='tozero',row=2,col=1)
    rng=padded_range(stats['median'])
    if rng:
        fig.update_yaxes(range=rng,autorange=False,row=2,col=1)
    fig.layout.meta=dict(zone=loaded['zone'],kind='hourly',dataset=key)
    if all(v is None for row in stats['values'] for v in row):
        fig.add_annotation(text='No available treatment data',xref='paper',yref='paper',x=.5,y=.7,showarrow=False)
    return fig
