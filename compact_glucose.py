"""Compact daily overview; scheduled basal is historical, never the editor draft."""
from datetime import datetime
import math
import pandas as pd
import plotly.graph_objects as go
from nightscout import utc_bounds


def basal_records(loaded,days):
    """Integrate known effective schedules with absolute temp-basal overrides.

    This reconstructs configured delivery, not pump-confirmed delivered insulin.
    Percent-only temp records are deliberately left unknown.
    """
    frames=[]
    for key in ('basal','basal_percent'):
        frame=loaded['data'].get(key,pd.DataFrame())
        frames.append([] if frame.empty else frame.to_dict('records'))
    profiles=loaded.get('recorded_profiles',[]);result=[]
    compiled={}
    for record in profiles:
        profile=record.get('profile') or {};schedule=[]
        for row in profile.get('basal',[]):
            try:
                h,m,*sec=str(row.get('time','00:00')).split(':')
                at_seconds=float(row.get('timeAsSeconds',int(h)*3600+int(m)*60+(float(sec[0]) if sec else 0)))
                schedule.append((at_seconds,float(row['value'])))
            except (ValueError,TypeError,KeyError):continue
        compiled[id(profile)]=sorted(schedule,reverse=True)
    for day in days:
        start,finish=map(pd.Timestamp,utc_bounds(day,day,loaded['zone']));end=min(finish,pd.Timestamp(loaded['loaded_at']))
        if end<=start:continue
        ps=[(pd.Timestamp(r['start']),pd.Timestamp(r['end']),r.get('profile') or {}) for r in profiles if pd.Timestamp(r['start'])<end and pd.Timestamp(r['end'])>start]
        # Minute grid plus every actual switch/override boundary preserves short events.
        edges={start,end,*pd.date_range(start,end,freq='1min')}
        for a,b,_ in ps:
            edges.update((max(start,a),min(end,b)))
        selected=[[r for r in rows if r['time']<end and r['end']>start] for rows in frames]
        for rows in selected:
            for r in rows:edges.update((max(start,r['time']),min(end,r['end'])))
        edges=sorted(edges);x=[];rates=[];scheduled=[];total=0.;known=0.
        for a,b in zip(edges,edges[1:]):
            profile=next((p for lo,hi,p in reversed(ps) if lo<=a<hi),{})
            at=a.tz_convert(profile.get('timezone') or loaded['zone']);seconds=at.hour*3600+at.minute*60+at.second
            base=next((v for t,v in compiled.get(id(profile),[]) if t<=seconds),None)
            rate=base if loaded.get('availability',{}).get('treatments',True) else None
            for row in selected[0]:
                if row['time']<=a<row['end']:rate=float(row['value'])
            if any(r['time']<=a<r['end'] for r in selected[1]):rate=None
            local=a.tz_convert(loaded['zone']);stop=b.tz_convert(loaded['zone']);lo=local.hour*60+local.minute+local.second/60;hi=1440 if b==finish else stop.hour*60+stop.minute+stop.second/60
            duration=(b-a).total_seconds()/3600
            if rate is not None and math.isfinite(rate):total+=rate*duration;known+=duration
            # Preserve elapsed insulin accounting at a backward DST clock jump.
            # Break the visual line instead of drawing backwards across the hour.
            if hi<=lo:
                x.append(None);rates.append(None);scheduled.append(None);continue
            if x and x[-1]==lo and rates[-1]==rate and scheduled[-1]==base:
                x[-1]=hi
            else:
                if x and x[-1]!=lo:x.append(None);rates.append(None);scheduled.append(None)
                x.extend([lo,hi]);rates.extend([rate,rate]);scheduled.extend([base,base])
        result.append(dict(date=str(day),x=x,rate=rates,scheduled=scheduled,basal=total,known_hours=known,elapsed_hours=(end-start).total_seconds()/3600))
    return result


def compact_figure(loaded,days,unit,dark):
    from nightscout_charts import dataset_traces,style_figure,glucose_axis,date_label
    fig=go.Figure()
    for key in ('glucose','iob','bolus','cob','carbs','target'):
        for trace in dataset_traces(key,loaded,days,'One day',unit,dark):fig.add_trace(trace)
    style_figure(fig,'Glucose Compact · '+date_label(days),unit,loaded['zone'],dark,height=460)
    glucose_axis(fig,loaded,days,unit)
    fig.update_layout(meta=dict(dataset='glucose',kind='compact',zone=loaded['zone']))
    return fig
