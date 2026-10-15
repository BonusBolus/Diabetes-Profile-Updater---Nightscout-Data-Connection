"""Historical Nightscout profile values, using already-adjusted effective schedules."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from bisect import bisect_right
import pandas as pd
import plotly.graph_objects as go
from chart_cache import cached
from nightscout import UTC
from nightscout_charts import rgba
from nightscout_stats import continuous_summary
from report_profiles import schedule

METRICS={'ic':('I:C',['carbratio'],'g/U'),'isf':('ISF',['sens'],None),'basal':('Basal',['basal'],'U/h'),'target':('Target',['target_low','target_high'],None)}


def profile_step_points(frame, zone, day):
    """Clip effective schedules without breaking adjacent recorded steps.

    A schedule boundary produces the two values at one clock instant, giving
    Plotly a real vertical jump. True record gaps and repeated DST clock time
    remain disconnected instead of being visually invented.
    """
    tz=ZoneInfo(zone)
    start=datetime.combine(day,time.min,tz).astimezone(UTC)
    end=datetime.combine(day+timedelta(days=1),time.min,tz).astimezone(UTC)
    xs=[];ys=[];labels=[];previous_at=None;previous_minute=None;previous_offset=None
    for item in frame.sort_values(['time','end']).to_dict('records'):
        a,b=max(start,item['time']),min(end,item['end'])
        if a>=b:continue
        local_a=a.astimezone(tz)
        minute_a=1440 if a==end else local_a.hour*60+local_a.minute+local_a.second/60+local_a.microsecond/60_000_000
        connected=previous_at==a and previous_offset==local_a.utcoffset() and previous_minute is not None and minute_a>=previous_minute
        if xs and not connected:xs.append(None);ys.append(None);labels.append('')
        times=[a,b]
        if local_a.utcoffset()!=b.astimezone(tz).utcoffset():
            times=list(pd.date_range(a,b,freq='1min'))
            if times[-1]!=b:times.append(b)
        previous=None
        for at in times:
            local=at.astimezone(tz)
            minute=1440 if at==end else local.hour*60+local.minute+local.second/60+local.microsecond/60_000_000
            if previous and (minute<previous[0] or abs((minute-previous[0])-(at-previous[1]).total_seconds()/60)>.01):
                xs.append(None);ys.append(None);labels.append('')
            xs.append(minute);ys.append(item['value']);labels.append(local.strftime('%Y-%m-%d %H:%M %z')+' · '+item['source'])
            previous=minute,at
        previous_at=b;previous_minute=previous[0];previous_offset=b.astimezone(tz).utcoffset()
    return xs,ys,labels


def profile_intervals(loaded,field,unit):
    result=[]
    for record in loaded.get('recorded_profiles',[]):
        profile=record.get('profile') or {};values=schedule(profile,field)
        if not values or values[0][0]!=0:continue
        try:zone=ZoneInfo(profile['timezone'])
        except (KeyError,TypeError,ValueError,ZoneInfoNotFoundError):continue
        source_unit=str(profile.get('units','')).lower();factor=1
        if field in ('sens','target_low','target_high'):
            if source_unit not in ('mg/dl','mgdl','mmol/l','mmol'):continue
            factor=(18 if unit=='mg/dL' else 1) if source_unit in ('mmol/l','mmol') else (1 if unit=='mg/dL' else 1/18)
        start=pd.Timestamp(record['start']).to_pydatetime();end=min(pd.Timestamp(record['end']),pd.Timestamp(loaded['loaded_at'])).to_pydatetime()
        if end<=start:continue
        boundaries={start,end};day=start.astimezone(zone).date();last=end.astimezone(zone).date()
        while day<=last:
            for seconds,_ in values:
                naive=datetime.combine(day,time.min)+timedelta(seconds=seconds)
                for fold in (0,1):
                    at=naive.replace(tzinfo=zone,fold=fold).astimezone(UTC)
                    if start<at<end and at.astimezone(zone).replace(tzinfo=None)==naive:boundaries.add(at)
            day+=timedelta(days=1)
        # Offset changes can cross a schedule boundary without a valid wall-clock instant.
        cursor=start
        while cursor<end:
            stop=min(end,cursor+timedelta(hours=6))
            if cursor.astimezone(zone).utcoffset()!=stop.astimezone(zone).utcoffset():
                lo,hi=int(cursor.timestamp()),int(stop.timestamp());offset=cursor.astimezone(zone).utcoffset()
                while hi-lo>1:
                    mid=(lo+hi)//2
                    if datetime.fromtimestamp(mid,UTC).astimezone(zone).utcoffset()==offset:lo=mid
                    else:hi=mid
                boundaries.add(datetime.fromtimestamp(hi,UTC))
            cursor=stop
        edges=sorted(boundaries);times=[s for s,v in values]
        for a,b in zip(edges,edges[1:]):
            local=a.astimezone(zone);seconds=local.hour*3600+local.minute*60+local.second
            value=values[bisect_right(times,seconds)-1][1]*factor
            if value<0 or (field!='basal' and value==0):continue
            result.append(dict(time=pd.Timestamp(a),end=pd.Timestamp(b),value=value,source='Nightscout · '+record['name']))
    return pd.DataFrame(result,columns=['time','end','value','source']).sort_values('time')


def profile_traces(loaded,metric,days,mode,unit,color):
    label,fields,axis_unit=METRICS[metric];axis_unit=axis_unit or unit+('/U' if metric=='isf' else '')
    traces=[]
    for field in fields:
        frame=cached(loaded,'profile_values',(field,unit),lambda:profile_intervals(loaded,field,unit))
        suffix=' · low' if field=='target_low' else ' · high' if field=='target_high' else ''
        name='Nightscout '+label+suffix
        meta=dict(dataset='profile',profile_source='nightscout',metric=metric,label=name,unit=axis_unit,legend_entry=True)
        if mode=='Median + band' and len(days)>1:
            stats=cached(loaded,'profile_summary',(field,tuple(days),unit),lambda:continuous_summary(dict(loaded,data={'basal':frame}),'basal',days,unit))
            if stats.empty:continue
            traces.append(go.Scatter(x=stats.minute.tolist(),y=stats['median'].tolist(),name=name,mode='lines',line=dict(color=color,shape='hv',dash='dot' if field=='target_low' else 'solid'),fill='tozeroy',fillcolor=rgba(color,.055),connectgaps=False,
                meta=dict(meta,kind='median',summary={k:stats[v].tolist() for k,v in dict(average='average',median='median',p10='p10',p90='p90',p25='low',p75='high',count='days').items()}),hovertemplate='%{y:.4g} '+axis_unit+'<extra>'+name+'</extra>'))
        else:
            for day in days:
                xs,ys,details=profile_step_points(frame,loaded['zone'],day)
                if not any(v is not None for v in ys):continue
                traces.append(go.Scatter(x=xs,y=ys,customdata=details,name=name,legendgroup=name,mode='lines',line=dict(color=color,shape='hv',dash='dot' if field=='target_low' else 'solid'),fill='tozeroy',fillcolor=rgba(color,.055),connectgaps=False,
                    meta=dict(meta,kind='profile',date=str(day)),hovertemplate='%{customdata}<br>%{y:.4g} '+axis_unit+'<extra>'+name+'</extra>'))
    return traces
