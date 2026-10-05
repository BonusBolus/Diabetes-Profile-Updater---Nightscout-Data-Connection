"""Display-only effective profile events, clipped to the loaded observation window."""
import pandas as pd
from nightscout_charts import interval_points
from date_controls import loaded_days


def profile_events(loaded):
    result=[];zone=loaded['zone']
    for row in loaded.get('recorded_profiles',[]):
        start=pd.Timestamp(row['start']);end=min(pd.Timestamp(row['end']),pd.Timestamp(loaded['loaded_at']))
        if end<=start:continue
        at=pd.Timestamp(row.get('active_at',row['start'])).tz_convert(zone)
        item=dict(name=row['name'],percentage=row.get('percentage'),date=str(at.date()),minute=at.hour*60+at.minute+at.second/60,intervals=[])
        frame=pd.DataFrame([dict(time=start,end=end,value=1)])
        for day in loaded_days(loaded):
            xs,_,_=interval_points(frame,zone,day);segment=[]
            for x in xs+[None]:
                if x is not None:segment.append(x)
                elif segment:
                    if segment[-1]>segment[0]:item['intervals'].append(dict(date=str(day),start=segment[0],end=segment[-1]))
                    segment=[]
        result.append(item)
    return result
