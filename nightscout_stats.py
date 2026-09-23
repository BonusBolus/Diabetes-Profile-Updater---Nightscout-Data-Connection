"""Descriptive recorded-data summaries. Missing records never become basal/IOB zeros."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from nightscout import UTC, glucose_summary, local_points


def continuous_summary(loaded, key, days, unit):
    frame=loaded['data'].get(key,pd.DataFrame())
    if key not in ('basal','basal_percent'):
        return glucose_summary(frame,loaded['zone'],days,unit if key=='glucose' else 'mg/dL')
    # First aggregate each day's known rate duration within wall-clock bins.
    # Short intervals count for their actual duration, not their record count.
    totals={};selected=set(days);tz=ZoneInfo(loaded['zone'])
    for row in frame.itertuples():
        cursor=pd.Timestamp(row.time);end=pd.Timestamp(row.end)
        while cursor<end:
            stop=min(cursor.floor('5min')+pd.Timedelta(minutes=5),end)
            local=cursor.tz_convert(tz);day=local.date()
            if day in selected:
                slot=(day,(local.hour*60+local.minute)//5*5)
                seconds=(stop-cursor).total_seconds()
                weighted,duration=totals.get(slot,(0.,0.))
                totals[slot]=(weighted+row.value*seconds,duration+seconds)
            cursor=stop
    if not totals:
        return pd.DataFrame(columns=['minute','median','low','high','days'])
    values=pd.DataFrame([dict(day=day,minute=minute,value=weighted/duration) for (day,minute),(weighted,duration) in totals.items()])
    groups=values.groupby('minute')['value']
    return pd.DataFrame(dict(median=groups.median(),low=groups.quantile(.25),high=groups.quantile(.75),days=groups.count())).reindex(range(0,1440,5)).rename_axis('minute').reset_index()


def hourly_events(loaded,key,days,exclude_smb=False):
    """Recorded totals per local day/hour; histogram uses complete hours only.

    DST repeated hours are combined; nonexistent hours remain blank. Partial
    hours appear in the heatmap but do not bias the across-day median downward.
    """
    days=sorted(set(days));zone=loaded['zone'];tz=ZoneInfo(zone)
    points=local_points(loaded['data'].get(key,pd.DataFrame()),zone,days)
    if exclude_smb and key == 'bolus' and 'label' in points:
        # Only explicit SMB classification; retain unknown and user boluses.
        points=points[points['label'].fillna('').str.strip().str.casefold() != 'smb']
    if not points.empty:
        points=points[points['time']<loaded['loaded_at']].copy()
        points['hour']=(points['minute']//60).astype(int)
        sums=points.groupby(['day','hour'])['value'].sum().to_dict()
        counts=points.groupby(['day','hour']).size().to_dict()
    else:sums={};counts={}
    available=loaded.get('availability',{}).get('treatments',True)
    values=[];complete=[];event_counts=[];status=[]
    for day in days:
        begin=datetime.combine(day,time.min,tz).astimezone(UTC)
        end=datetime.combine(day+timedelta(days=1),time.min,tz).astimezone(UTC)
        minutes=pd.date_range(begin,end,freq='1min',inclusive='left')
        hours=minutes.tz_convert(tz).hour
        row=[];flags=[];events=[];labels=[]
        for hour in range(24):
            instants=minutes[hours==hour]
            elapsed=bool(len(instants) and instants[0]<loaded['loaded_at'])
            full=bool(elapsed and instants[-1]+pd.Timedelta(minutes=1)<=loaded['loaded_at'])
            usable=available and elapsed
            row.append(float(sums.get((day,hour),0.)) if usable else None)
            events.append(int(counts.get((day,hour),0)) if usable else None)
            flags.append(bool(usable and full))
            labels.append('Unavailable' if not usable else 'Complete hour' if full else 'Partial hour')
        values.append(row);complete.append(flags);event_counts.append(events);status.append(labels)
    medians=[];contributing=[]
    for hour in range(24):
        observed=[row[hour] for row,flags in zip(values,complete) if flags[hour]]
        medians.append(float(np.median(observed)) if observed else None)
        contributing.append(len(observed))
    return dict(days=[str(day) for day in days],values=values,complete=complete,counts=event_counts,status=status,median=medians,contributing=contributing)
