"""Report-only descriptive statistics from observed Nightscout records."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import math
import numpy as np
import pandas as pd
from nightscout import UTC, utc_bounds


def time_minute(value):
    try:
        h,m=map(int,str(value).split(':'))
        if (h==24 and m==0) or (0<=h<24 and 0<=m<60):return h*60+m
    except (TypeError,ValueError):pass
    raise ValueError('Use HH:MM for times (00:00 through 24:00).')


def report_range(request, loaded):
    first=date.fromisoformat(request['first']);last=date.fromisoformat(request['last'])
    if not loaded['first']<=first<=last<=loaded['last']:raise ValueError('Select dates within the loaded range; load more dates first if needed.')
    if (last-first).days>30:raise ValueError('Export up to 31 days at a time.')
    window=[time_minute(request.get('from_time','00:00')),time_minute(request.get('until_time','24:00'))]
    if window[0]>=window[1]:raise ValueError('The daily start time must be earlier than the end time. Split overnight windows into separate exports.')
    return [t.date() for t in pd.date_range(first,last)],window


def day_window(day,window,zone):
    tz=ZoneInfo(zone)
    start=datetime.combine(day,time.min,tz)+timedelta(minutes=window[0])
    end=datetime.combine(day,time.min,tz)+timedelta(minutes=window[1])
    return start.astimezone(UTC),end.astimezone(UTC)


def observed_stats(loaded,days,window,unit):
    factor=18 if unit=='mmol/L' else 1
    frame=loaded['data']['glucose'];all_bins=[];daily=[];change_counts={label:0 for label in ('Site Change','Sensor Start','Sensor Change','Insulin Change')}
    bolus_total=carbs_total=0.;known_days=0
    for day in days:
        start,end=day_window(day,window,loaded['zone']);end=max(start,min(end,loaded['loaded_at']))
        in_source=loaded.get('nightscout_first',loaded['first'])<=day<=loaded.get('nightscout_last',loaded['last']) and loaded.get('has_nightscout',True)
        selected=frame[(frame.time>=start)&(frame.time<end)].copy()
        if not selected.empty:
            midnight,_=utc_bounds(day,day,loaded['zone'])
            selected['bin']=(pd.to_datetime(selected.time,utc=True)-midnight).dt.total_seconds()//300
            values=selected.groupby('bin').value.median().to_numpy(dtype=float)/factor
        else:values=np.array([])
        all_bins.extend(values.tolist())
        midnight,_=utc_bounds(day,day,loaded['zone'])
        expected=max(0,math.ceil((end-midnight).total_seconds()/300)-math.floor((start-midnight).total_seconds()/300)) if in_source and end>start else 0
        row=describe(values,unit);row.update(date=str(day),readings=len(selected),expected=expected,coverage=100*len(values)/expected if expected else None)
        known=in_source and loaded.get('availability',{}).get('treatments',False) and end>start
        for key in ('bolus','carbs'):
            records=loaded['data'][key];records=records[(records.time>=start)&(records.time<end)]
            row[key]=float(records.value.sum()) if known else None
        if known:
            known_days+=1;bolus_total+=row['bolus'];carbs_total+=row['carbs']
        changes=loaded['data'].get('changes',pd.DataFrame())
        if not changes.empty:
            for label,count in changes[(changes.time>=start)&(changes.time<end)].label.value_counts().items():
                if label in change_counts:change_counts[label]+=int(count)
        daily.append(row)
    total=describe(np.array(all_bins),unit);expected=sum(row['expected'] for row in daily)
    total.update(readings=sum(row['readings'] for row in daily),days=len(days),expected=expected,
                 coverage=100*len(all_bins)/expected if expected else None,changes=change_counts if known_days else {k:None for k in change_counts},
                 bolus=bolus_total if known_days else None,carbs=carbs_total if known_days else None,
                 bolus_daily=bolus_total/known_days if known_days else None,carbs_daily=carbs_total/known_days if known_days else None,
                 treatment_days=known_days)
    return dict(total=total,daily=daily,values=all_bins)


def describe(values,unit):
    scale=1 if unit=='mmol/L' else 18
    n=len(values);mean=float(np.mean(values)) if n else None;sd=float(np.std(values)) if n>=2 else None
    result=dict(bins=n,mean=mean,sd=sd,cv=100*sd/mean if sd is not None and mean else None,
                low=float(np.min(values)) if n else None,high=float(np.max(values)) if n else None,
                q25=float(np.quantile(values,.25)) if n else None,median=float(np.median(values)) if n else None,q75=float(np.quantile(values,.75)) if n else None)
    for prefix,lo,hi in [('own',4*scale,10*scale),('standard',3.9*scale,10*scale)]:
        for name,mask in [('below',values<lo),('within',(values>=lo)&(values<=hi)),('above',values>hi)]:result[prefix+'_'+name]=100*float(np.mean(mask)) if n else None
    return result
