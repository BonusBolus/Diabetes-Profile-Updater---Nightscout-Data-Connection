"""Hourly recorded profile states and explicit change events; no inferred events."""
from datetime import datetime,time,timedelta
import numpy as np
import pandas as pd
from nightscout import UTC
from nightscout_stats import hourly_events

EVENT_LAYERS={'Profile percentage':'profile_percentage','Site changes':'site_changes','Sensor changes':'sensor_changes'}
EVENT_LABELS={'profile_percentage':('Profile percentage','%','#7774a8'),
              'site_changes':('Site changes','events','#557dce'),'sensor_changes':('Sensor changes','events','#b45bb5')}


def hourly_state_events(loaded,key,days):
    if key!='profile_percentage':
        frame=loaded['data'].get('changes',pd.DataFrame()).copy()
        labels=['Site Change'] if key=='site_changes' else ['Sensor Start','Sensor Change']
        if not frame.empty:
            frame=frame[frame.label.isin(labels)].copy();frame['value']=1.
        snapshot=dict(loaded,data={key:frame})
        return hourly_events(snapshot,key,days)
    # Each known effective state contributes its duration, not its upload count.
    zone=loaded['zone'];totals={};coverage={};cutoff=pd.Timestamp(loaded['loaded_at'])
    for row in loaded.get('recorded_profiles',[]):
        p=row.get('percentage')
        if not isinstance(p,(int,float)) or not np.isfinite(p):continue
        cursor=pd.Timestamp(row['start']);end=min(pd.Timestamp(row['end']),cutoff)
        while cursor<end:
            stop=min(cursor.floor('h')+pd.Timedelta(hours=1),end)
            local=cursor.tz_convert(zone);slot=(local.date(),local.hour)
            seconds=(stop-cursor).total_seconds()
            totals[slot]=totals.get(slot,0)+seconds*p;coverage[slot]=coverage.get(slot,0)+seconds
            cursor=stop
    values=[];flags=[];counts=[];status=[]
    for day in sorted(set(days)):
        begin=pd.Timestamp(datetime.combine(day,time.min)).tz_localize(zone).tz_convert('UTC')
        end=pd.Timestamp(datetime.combine(day+timedelta(days=1),time.min)).tz_localize(zone).tz_convert('UTC')
        minutes=pd.date_range(begin,end,freq='1min',inclusive='left');hours=minutes.tz_convert(zone).hour
        row=[];full=[];n=[];s=[]
        for hour in range(24):
            instants=minutes[hours==hour];known=coverage.get((day,hour),0)
            valid=bool(len(instants) and known>0)
            complete=bool(valid and instants[-1]+pd.Timedelta(minutes=1)<=cutoff and abs(known-len(instants)*60)<.01)
            row.append(totals[(day,hour)]/known if valid else None);full.append(complete);n.append(None)
            s.append(('Complete hour' if complete else 'Partial known state')+f' · {known/60:g} known min' if valid else 'Unknown effective state')
        values.append(row);flags.append(full);counts.append(n);status.append(s)
    observed=[[row[h] for row,f in zip(values,flags) if f[h]] for h in range(24)]
    return dict(days=[str(d) for d in sorted(set(days))],values=values,complete=flags,counts=counts,status=status,
                average=[float(np.mean(v)) if v else None for v in observed],median=[float(np.median(v)) if v else None for v in observed],contributing=[len(v) for v in observed])
