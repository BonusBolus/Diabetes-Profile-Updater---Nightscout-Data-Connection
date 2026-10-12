"""Descriptive event-aligned glucose analyses. Uploaded events are not device ground truth."""
from bisect import bisect_left
from datetime import timedelta
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from chart_cache import cached

INSIGHT_LABELS={'sensor':'Sensor-age glucose','sensor_variability':'Sensor-age variability',
                'site_age':'Site-age glucose','activity_during':'Activity glucose',
                'activity_after':'Post-activity glucose',
                'meal':'Meal-response glucose','sleep':'Sleep–glucose'}
INSIGHT_LAYERS={label:'insight_'+key for key,label in INSIGHT_LABELS.items()}
MAX_GAP_MINUTES=10


def meal_events(loaded):
    """Recorded carb timestamps, not inferred meals or insulin attribution."""
    frame=loaded['data'].get('carbs',pd.DataFrame()).copy()
    if frame.empty:return []
    frame['time']=pd.to_datetime(frame.time,utc=True)
    frame=frame.dropna(subset=['time','value']);frame=frame[frame.value.gt(0)]
    events=[]
    for at,part in frame.groupby('time',sort=True):
        grams=float(part.value.sum());events.append(dict(time=at,label=f'Carbs {grams:g} g',carbs=grams))
    return events


def interval_hours(intervals):
    """Union duration: duplicate/overlapping stage uploads count only once."""
    finish=None;seconds=0
    for a,b in sorted(intervals):
        if b<=a:continue
        left=max(a,finish) if finish is not None else a
        if b>left:seconds+=(b-left).total_seconds()
        finish=max(finish,b) if finish is not None else b
    return seconds/3600


def sleep_events(loaded):
    """Prefer explicit Garmin session boundaries; stage-only sessions stay labelled."""
    frame=loaded['data'].get('g_sleep',pd.DataFrame()).copy()
    if not frame.empty:
        frame['time']=pd.to_datetime(frame.time,utc=True);frame['end']=pd.to_datetime(frame.end,utc=True)
        frame=frame.dropna(subset=['time','end']).sort_values('time');frame=frame[frame.end.gt(frame.time)]
    sessions=loaded.get('garmin_sleep_sessions') or [dict(time=n['start'],end=n['end']) for n in loaded.get('garmin_sleep_notes',[])]
    source='Recorded Garmin session'
    if not sessions:
        # Stage-only DBs have no separate session boundaries. Group contiguous
        # recorded intervals, retaining gaps instead of declaring them asleep.
        sessions=[];source='Stage intervals grouped across gaps ≤30 min'
        for r in frame.itertuples():
            if sessions and r.time<=sessions[-1]['end']+pd.Timedelta(minutes=30):sessions[-1]['end']=max(sessions[-1]['end'],r.end)
            else:sessions.append(dict(time=r.time,end=r.end))
    unique=sorted({(pd.Timestamp(s['time']),pd.Timestamp(s['end'])) for s in sessions})
    hrv=loaded['data'].get('g_sleep_hrv',pd.DataFrame()).copy()
    if not hrv.empty:
        hrv['time']=pd.to_datetime(hrv.time,utc=True);hrv=hrv.dropna(subset=['time','value']);hrv=hrv[hrv.value.gt(0)]
    result=[]
    for a,b in unique:
        if pd.isna(a) or pd.isna(b) or b<=a:continue
        stages=frame[frame.time.lt(b)&frame.end.gt(a)] if not frame.empty else frame
        intervals=[(max(a,r.time),min(b,r.end),r.stage) for r in stages.itertuples()]
        asleep=[(x,y) for x,y,stage in intervals if stage in ('deep_sleep','light_sleep','rem_sleep')]
        known=[(x,y) for x,y,stage in intervals if stage!='unknown']
        values=hrv[hrv.time.ge(a)&hrv.time.lt(b)] if not hrv.empty else hrv
        # Equal five-minute contributions; not Garmin's nightly average.
        median_hrv=float(values.groupby(values.time.dt.floor('5min')).value.median().median()) if not values.empty else None
        result.append(dict(time=a,end=b,label='Sleep',sleep=dict(asleep_hours=interval_hours(asleep) if known else None,
            stage_coverage=100*interval_hours(known)/((b-a).total_seconds()/3600),hrv=median_hrv,
            hrv_source='Median of recorded five-minute HRV bins',source=source,wake=b.isoformat())))
    return result


def insight_available(loaded,key):
    if loaded['data'].get('glucose',pd.DataFrame()).empty:return False
    key=key.removeprefix('insight_')
    if key=='meal':return not loaded['data'].get('carbs',pd.DataFrame()).empty
    if key=='sleep':return bool(loaded.get('garmin_sleep_sessions') or loaded.get('garmin_sleep_notes')) or not loaded['data'].get('g_sleep',pd.DataFrame()).empty
    if key.startswith('sensor'):return bool(change_events(loaded,'sensor'))
    if key.startswith('site'):return bool(change_events(loaded,'site'))
    return not loaded['data'].get('g_activity',pd.DataFrame()).empty


def meal_context(loaded,event):
    at=event['time'];iob=loaded['data'].get('iob',pd.DataFrame())
    samples=iob[iob.time.le(at)&iob.time.ge(at-pd.Timedelta(minutes=MAX_GAP_MINUTES))].sort_values('time') if not iob.empty else iob
    cob=loaded['data'].get('cob',pd.DataFrame())
    prior=cob[cob.time.le(at)&cob.time.ge(at-pd.Timedelta(minutes=MAX_GAP_MINUTES))].sort_values('time') if not cob.empty else cob
    bolus=loaded['data'].get('bolus',pd.DataFrame())
    known=loaded.get('availability',{}).get('treatments') or not bolus.empty
    near=bolus[bolus.time.ge(at-pd.Timedelta(minutes=30))&bolus.time.lt(at+pd.Timedelta(minutes=60))] if not bolus.empty else bolus
    totals={name:float(near[near.label.eq(label)].value.sum()) if not near.empty else 0.
            for name,label in [('user','User bolus'),('smb','SMB'),('unknown','Bolus · unknown type')]}
    return dict(carbs=event['carbs'],cob=float(prior.value.iloc[-1]) if not prior.empty else None,iob=float(samples.value.iloc[-1]) if not samples.empty else None,
                bolus={k:v if known else None for k,v in totals.items()})


def change_events(loaded,kind):
    frame=loaded['data'].get('changes',pd.DataFrame()).copy()
    labels={'sensor':['Sensor Start','Sensor Change'],'site':['Site Change']}[kind]
    records=frame.to_dict('records') if not frame.empty else []
    records.extend(loaded.get('alignment_events',[]))
    records=[r for r in records if r.get('label') in labels]
    if not records:return []
    frame=pd.DataFrame(records);frame['time']=pd.to_datetime(frame.time,utc=True)
    frame=frame.sort_values('time').drop_duplicates(['time','label'])
    # Simultaneous start/change records describe one alignment origin.
    return frame.drop_duplicates('time',keep='last').to_dict('records')


def baseline_at(points,at,times=None):
    """Exact reading or interpolation bracketed within a ten-minute observed interval."""
    if times is None:times=points.time.tolist()
    i=bisect_left(times,at)
    if i<len(times) and times[i]==at:return float(points.value.iloc[i]),'Recorded at event time'
    if i==0 or i==len(times):return None,'No bracketed baseline'
    left,right=times[i-1],times[i];gap=(right-left).total_seconds()/60
    if gap<=0 or gap>MAX_GAP_MINUTES:return None,'Baseline lies in a glucose gap'
    ratio=(at-left).total_seconds()/(right-left).total_seconds()
    return float(points.value.iloc[i-1]+ratio*(points.value.iloc[i]-points.value.iloc[i-1])),'Interpolated between adjacent readings (≤10 min)'


def glucose_points(loaded,unit):
    points=loaded['data'].get('glucose',pd.DataFrame()).copy()
    if points.empty:return points,[]
    points['time']=pd.to_datetime(points.time,utc=True)
    points=points.dropna(subset=['time','value']).sort_values('time').groupby('time',as_index=False).value.median()
    if unit=='mmol/L':points['value']/=18
    points['_day']=points.time.dt.tz_convert(loaded['zone']).dt.date
    return points,points.time.tolist()


def context_points(loaded, field):
    frame=loaded['data'].get(field,pd.DataFrame()).copy()
    if frame.empty:return frame
    frame['time']=pd.to_datetime(frame.time,utc=True,errors='coerce')
    frame['value']=pd.to_numeric(frame.value,errors='coerce')
    frame=frame.dropna(subset=['time','value']).sort_values('time').drop_duplicates('time',keep='last')
    if field=='cob':frame=frame[frame.value.ge(0)]
    frame['_day']=frame.time.dt.tz_convert(loaded['zone']).dt.date
    return frame


def aligned_context(frame,origin,stop,selected):
    # Independent timestamps, no nearest-glucose matching or forward fill.
    xs=[];values=[];previous=None
    if not frame.empty:
        part=frame.iloc[frame.time.searchsorted(origin):frame.time.searchsorted(stop)]
        for row in part[part['_day'].isin(selected)].itertuples():
            if previous is not None and (row.time-previous).total_seconds()>MAX_GAP_MINUTES*60:
                xs.append(None);values.append(None)
            xs.append((row.time-origin).total_seconds()/60);values.append(float(row.value));previous=row.time
    return dict(x=xs,value=values)


def aligned_series(loaded,days,key,unit):
    # Legacy post-change callers use the same replacement-bounded site periods.
    if key=='site_after':key='site_age'
    points,times=cached(loaded,'insight_glucose',unit,lambda:glucose_points(loaded,unit))
    if points.empty:return []
    selected=set(days);zone=loaded['zone'];end=min(pd.Timestamp(loaded['loaded_at']),pd.Timestamp(loaded['last']+timedelta(days=1)).tz_localize(zone).tz_convert('UTC'))
    if key=='meal':events=cached(loaded,'insight_events','meal',lambda:meal_events(loaded))
    elif key.startswith('sleep'):events=cached(loaded,'insight_events','sleep',lambda:sleep_events(loaded))
    elif key.startswith('activity'):
        activities=loaded['data'].get('g_activity',pd.DataFrame())
        events=[] if activities.empty else activities.to_dict('records')
    else:events=change_events(loaded,'sensor' if key=='sensor' else 'site')
    context={field:cached(loaded,'insight_context',field,lambda field=field:context_points(loaded,field)) for field in ('iob','cob')}
    result=[]
    for i,event in enumerate(events):
        start=pd.Timestamp(event['time']);finish=pd.Timestamp(event.get('end',end))
        if key.startswith('sleep'):
            if finish.tz_convert(zone).date() not in selected:continue
            origin=finish if key=='sleep_after' else start
            next_start=pd.Timestamp(events[i+1]['time']) if i+1<len(events) else end
            stop=min(end,next_start,origin+pd.Timedelta(hours=24)) if key=='sleep_after' else min(end,finish)
        elif key=='meal':
            if start.tz_convert(zone).date() not in selected:continue
            origin=start;next_start=pd.Timestamp(events[i+1]['time']) if i+1<len(events) else end
            stop=min(end,next_start,start+pd.Timedelta(hours=72))
        elif key.startswith('activity'):
            if start.tz_convert(zone).date() not in selected:continue
            origin=finish if key=='activity_after' else start
            stop=min(end,origin+pd.Timedelta(hours=72)) if key=='activity_after' else min(end,finish)
        else:
            origin=start;next_start=pd.Timestamp(events[i+1]['time']) if i+1<len(events) else end
            stop=min(end,next_start) if key in ('sensor','site_age') else min(end,start+pd.Timedelta(hours=72))
            if stop<=origin:continue
        if stop<=origin:continue
        part=points.iloc[points.time.searchsorted(origin):points.time.searchsorted(stop)]
        part=part[part['_day'].isin(selected)].copy()
        if part.empty:continue
        value,note=baseline_at(points,origin,times)
        minutes=(part.time-origin).dt.total_seconds()/60
        dt=part.time.diff().dt.total_seconds()/60
        slope=part.value.diff()/dt;slope=slope.where(dt.gt(0)&dt.le(MAX_GAP_MINUTES))
        jump=(slope-slope.shift()).abs()
        # A curve break is explicit; no line is drawn across outages.
        xs=[];ys=[];rates=[];jumps=[];previous=None
        for at,x,y,rate,j in zip(part.time,minutes,part.value,slope.abs(),jump):
            if previous is not None and (at-previous).total_seconds()>MAX_GAP_MINUTES*60:
                xs.append(None);ys.append(None);rates.append(None);jumps.append(None)
            xs.append(float(x));ys.append(float(y));rates.append(None if pd.isna(rate) else float(rate));jumps.append(None if pd.isna(j) else float(j));previous=at
        bins=part.assign(bin=part.time.dt.floor('5min')).groupby('bin').value.median()
        mean=float(bins.mean());high=10 if unit=='mmol/L' else 180;low=4 if unit=='mmol/L' else 72
        hours=dt.to_numpy()[1:]/60  # Timedelta seconds are independent of pandas' timestamp storage unit.
        above=np.maximum(0,part.value.to_numpy()-high)
        observed=(hours>0)&(hours<=MAX_GAP_MINUTES/60)
        exposure=float(np.sum((hours*(above[:-1]+above[1:])/2)[observed]))
        label=str(event.get('label','Event'))+' · '+origin.tz_convert(zone).strftime('%Y-%m-%d %H:%M')
        result.append(dict(id=origin.isoformat()+':'+str(i),label=label,x=xs,glucose=ys,rate=rates,jump=jumps,baseline=value,baseline_note=note,
                           start=origin.isoformat(),end=stop.isoformat(),duration=(stop-origin).total_seconds()/60,
                           context={field:aligned_context(frame,origin,stop,selected) for field,frame in context.items()},
                           **({'meal':meal_context(loaded,event)} if key=='meal' else {'sleep':event['sleep']} if key.startswith('sleep') else {}),
                           statistics=dict(cv=float(bins.std(ddof=0)/mean*100) if mean else None,
                                           tir=float(bins.between(low,high).mean()*100),above_exposure=float(exposure),observed_bins=len(bins))))
    return result


def insight_figures(loaded,days,unit,dark,selected=None):
    from nightscout_charts import style_figure,date_label,dataset_color
    figures=[]
    if selected is not None:selected={'insight_site_age' if key=='insight_site_after' else key for key in selected}
    if len(set(days))<2:return figures
    for key,label in INSIGHT_LABELS.items():
        if selected is not None and 'insight_'+key not in selected:continue
        source_key='sensor' if key=='sensor_variability' else key
        series=cached(loaded,'insights',(source_key,tuple(days),unit),lambda:aligned_series(loaded,days,source_key,unit))
        after=cached(loaded,'insights',('sleep_after',tuple(days),unit),lambda:aligned_series(loaded,days,'sleep_after',unit)) if key=='sleep' else None
        fig=go.Figure()
        for s in series:
            fig.add_scatter(x=s['x'],y=s['glucose'],name=s['label'],mode='lines',connectgaps=False,line=dict(width=1.3),opacity=.45,
                meta=dict(kind='insight_event',dataset='insight_'+key,label=s['label'],unit=unit,event_id=s['id']))
        style_figure(fig,label+' · '+date_label(days),'Glucose ('+unit+')',loaded['zone'],dark,height=350)
        fig.update_layout(meta=dict(kind='insight',dataset='insight_'+key,insight=key,non_time=True,series=series,insight_title=fig.layout.title.text,**({'after_series':after} if after is not None else {}),glucose_color=dataset_color('glucose',dark)),
                          xaxis=dict(title='Time since '+('sensor start' if key.startswith('sensor') else 'site change' if key.startswith('site') else 'carb entry' if key=='meal' else 'sleep start' if key=='sleep' else 'activity end' if key=='activity_after' else 'activity start')+' (hours)',autorange=True))
        # Source x is minutes; the shared browser Insights transform converts to hours.
        if not series:fig.add_annotation(text='No usable recorded event periods with glucose in the selected dates',xref='paper',yref='paper',x=.5,y=.5,showarrow=False)
        figures.append(fig)
    return figures
