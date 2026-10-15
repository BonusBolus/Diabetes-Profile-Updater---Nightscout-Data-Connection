"""Read known Garmin Sleep JSON and activity FIT fields. Source files stay untouched."""
from functools import lru_cache
import json
import math
from pathlib import Path
import re

import pandas as pd


def utc(value):
    if value is None:return pd.NaT
    if isinstance(value,(int,float)):
        return pd.to_datetime(value,unit='ms',utc=True,errors='coerce')
    return pd.to_datetime(value,utc=True,errors='coerce')


def number(value):
    return float(value) if isinstance(value,(int,float)) and math.isfinite(value) else None


ACTIVITY_COLORS={'walking':'#9ccc65','running':'#f16a43','mountain biking':'#a96c32',
                 'cycling':'#42a5f5','squash':'#ab6bd5','swimming':'#26a69a'}


def canonical_activity(label):
    text=str(label).casefold().replace('_',' ').replace('-',' ')
    if 'mountain' in text and any(v in text for v in ('bik','cycl')):return 'mountain biking'
    if text in ('biking','bike','cycling','road biking','road cycling'):return 'cycling'
    if text in ('walk','walking'):return 'walking'
    if text in ('run','running'):return 'running'
    if text=='squash':return 'squash'
    return label


def activity_label(sport, sub_sport=None, activity_type=None):
    def clean(value):
        return '' if value is None or pd.isna(value) else str(value).split('.')[-1].strip().replace('_',' ').lower()
    generic=('', 'generic', 'unknown', 'all', 'other', 'none')
    main,sub,kind=clean(sport),clean(sub_sport),clean(activity_type)
    if main in generic:main=kind if kind not in generic else 'Activity (type unavailable)'
    if sub not in generic and sub!=main:
        main=sub if main in ('fitness equipment','training') else sub+' '+main
    return canonical_activity(main)


def replace_interval(data,key,rows,start,end):
    if not rows:return
    incoming=pd.DataFrame(rows)
    old=data.get(key,pd.DataFrame())
    if not old.empty:
        if key=='g_activity':
            # Replace matching DB summaries, not other overlapping activities or FIT sessions.
            ids=old.get('activity_id',pd.Series('',index=old.index)).fillna('').astype(str)
            source=old.get('source',pd.Series('GarminDB',index=old.index)).fillna('GarminDB').str.startswith('GarminDB')
            remove=pd.Series(False,index=old.index)
            for row in rows:
                identity=str(row.get('activity_id',''))
                if identity:
                    remove |= ids.eq(identity)
                    remove |= source & ids.ne('') & ids.str.split('_').str[0].eq(identity.split('_')[0])
                remove |= source & ids.eq('') & old.time.eq(row['time'])
            old=old[~remove]
        elif 'end' in old:
            # Preserve the portions of DB intervals outside the better source window.
            left=old[old.time.lt(start)].copy();left['end']=left.end.clip(upper=start)
            right=old[old.end.gt(end)].copy();right['time']=right.time.clip(lower=end)
            old=pd.concat([left,right],ignore_index=True)
        else:old=old[old.time.lt(start)|old.time.ge(end)]
        incoming=pd.concat([old,incoming],ignore_index=True)
    unique=['time','end','label','activity_id'] if key=='g_activity' and 'activity_id' in incoming else ['time']
    data[key]=incoming.sort_values('time').drop_duplicates(unique,keep='last').reset_index(drop=True)


def read_sleep(path,data,start,end,zone):
    from garmin_data import STAGES
    raw=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(raw,dict):raise ValueError('Expected a sleep JSON object')
    dto=raw.get('dailySleepDTO') or {}
    a,b=utc(dto.get('sleepStartTimestampGMT')),utc(dto.get('sleepEndTimestampGMT'))
    if pd.isna(a) or pd.isna(b) or b<=a or b<=start or a>=end:return None
    stage_map={0:'deep_sleep',1:'light_sleep',2:'rem_sleep' if raw.get('remSleepData') else 'awake',3:'awake',-1:'unknown'}
    stages=[];movement=[]
    for field,target in [('sleepLevels',stages),('sleepMovement',movement)]:
        for item in raw.get(field) or []:
            x,y=utc(item.get('startGMT')),utc(item.get('endGMT'));value=number(item.get('activityLevel'))
            if pd.isna(x) or pd.isna(y) or y<=x or value is None or y<=start or x>=end:continue
            if field=='sleepLevels':
                stage=stage_map.get(value,'unknown');rank,label,_=STAGES[stage]
                target.append(dict(time=x,end=y,value=rank,label=label,stage=stage))
            else:target.append(dict(time=x,end=y,value=value,label='Sleep movement'))
    replace_interval(data,'g_sleep',stages,a,b)
    replace_interval(data,'g_sleep_movement',movement,a,b)
    for field,key,clock,value_col,label in [
        ('sleepRestlessMoments','g_sleep_restless','startGMT','value','Restless moment'),
        ('wellnessEpochRespirationDataDTOList','g_sleep_rr','startTimeGMT','respirationValue','Sleep respiration')]:
        rows=[]
        for item in raw.get(field) or []:
            at=utc(item.get(clock));value=number(item.get(value_col))
            if pd.isna(at) or value is None or not start<=at<end or not a<=at<b:continue
            if value<0 or (key=='g_sleep_rr' and value==0):continue
            rows.append(dict(time=at,value=value,label=label))
        replace_interval(data,key,rows,a,b)
    # A nightly category is not a time-resolved signal. Keep the original label.
    return dict(start=a.isoformat(),end=b.isoformat(),date=str(b.tz_convert(zone).date()),days=[str(d.date()) for d in pd.date_range(a.tz_convert(zone).date(),(b-pd.Timedelta(microseconds=1)).tz_convert(zone).date())],
        breathing=dto.get('breathingDisruptionSeverity'),awake_count=dto.get('awakeCount'),
        restless_count=raw.get('restlessMomentsCount'),
        restlessness=(dto.get('sleepScores') or {}).get('restlessness',{}).get('qualifierKey'))


@lru_cache(maxsize=2048)
def fit_created(path,mtime,size):
    import fitdecode
    with fitdecode.FitReader(path,check_crc=fitdecode.CrcCheck.RAISE) as reader:
        for message in reader:
            if isinstance(message,fitdecode.FitDataMessage) and message.name=='file_id':
                return message.get_value('time_created',fallback=None)
            if isinstance(message,fitdecode.FitDataMessage) and message.name=='record':return None
    return None


def coarse_location(latitude,longitude,semicircles=False):
    """One rounded regional label, never retain or upload a route/GPS coordinate."""
    a,b=number(latitude),number(longitude)
    if a is None or b is None:return None
    if semicircles:a*=180/(2**31);b*=180/(2**31)
    if not (-90<=a<=90 and -180<=b<=180) or (a==0 and b==0):return None
    a,b=round(a*4)/4,round(b*4)/4
    return f"Area {abs(a):.2f}°{'N' if a>=0 else 'S'}, {abs(b):.2f}°{'E' if b>=0 else 'W'} · coarse 0.25° cell"


@lru_cache(maxsize=64)
def read_fit(path,mtime,size):
    import fitdecode
    rows=[];sessions=[];segment=0
    with fitdecode.FitReader(path,check_crc=fitdecode.CrcCheck.RAISE) as reader:
        for message in reader:
            if not isinstance(message,fitdecode.FitDataMessage):continue
            def value(name):
                fields=[f for f in message.fields if f.name==name and f.value is not None]
                # Decoders may synthesize an enhanced field from legacy speed/altitude.
                # Prefer the explicitly recorded enhanced value when both exist.
                fields.sort(key=lambda f:f.is_expanded)
                return fields[0].value if fields else None
            if message.name=='event' and value('event')=='timer':segment+=1
            if message.name=='record':
                at=value('timestamp')
                if at is None:continue
                # No location export: these GPS samples exist only during activities.
                row=dict(time=pd.to_datetime(at,utc=True),segment=Path(path).stem+':'+str(segment))
                for key,fields in {
                    'hr':['heart_rate'],'rr':['respiration_rate'],'cadence':['cadence'],
                    'speed':['enhanced_speed','speed'],'altitude':['enhanced_altitude','altitude'],
                    'power':['power'],'temperature':['temperature']}.items():
                    n=next((number(value(f)) for f in fields if number(value(f)) is not None),None)
                    if n is not None:row[key]=n*3.6 if key=='speed' else n
                rows.append(row)
            elif message.name=='session':
                a,b=value('start_time'),value('timestamp')
                elapsed=number(value('total_elapsed_time'))
                if a is not None:
                    a=pd.to_datetime(a,utc=True)
                    # Some Garmin multi-sport sessions repeat the parent's start in timestamp.
                    # Elapsed time includes pauses; timer time would shorten the shaded interval.
                    b=pd.to_datetime(b,utc=True)
                    if (pd.isna(b) or b<=a) and elapsed is not None and elapsed>0:
                        b=a+pd.Timedelta(seconds=elapsed)
                    if pd.notna(b) and b>a:
                        sessions.append(dict(time=a,end=b,value=1.,source='FIT session',
                                             label=activity_label(value('sport'),value('sub_sport'))))
    numbers=re.findall(r'(?<!\d)\d{5,}(?!\d)',Path(path).stem)
    identity=numbers[0] if len(numbers)==1 else Path(path).stem
    for index,session in enumerate(sessions,1):
        session['activity_id']=identity if len(sessions)==1 else identity+'_'+str(index)
    return rows,sessions


def supplement_exports(root,data,activities,daily,inventory,warnings,start,end,zone,include_sleep=True,include_activity=True,progress=None):
    notes=[]
    for day in (pd.date_range(start.tz_convert(zone).date(),end.tz_convert(zone).date()) if include_sleep else []):
        if progress:progress('Sleep exports · '+str(day.date()))
        path=root/'Sleep'/f'sleep_{day.date()}.json'
        if not path.is_file():continue
        try:
            note=read_sleep(path,data,start,end,zone)
            if note:notes.append(note)
        except (ValueError,TypeError,KeyError,OSError) as exc:warnings.append(f'Sleep export {path.name} could not be read: {exc}')
    folder=root/'FitFiles'/'Activities'
    if include_activity and folder.is_dir():
        import fitdecode
        ids={str(a['activity_id']).split('_')[0] for a in activities if a.get('activity_id') is not None}
        count=0
        for path in sorted(folder.rglob('*')):
            if not path.is_file() or path.suffix.lower()!='.fit':continue
            if progress:progress('Activity FIT · '+path.name)
            file_ids=set(re.findall(r'(?<!\d)\d{5,}(?!\d)',path.stem))
            try:
                stat=path.stat();signature=(str(path),stat.st_mtime_ns,stat.st_size)
                if not ids.intersection(file_ids):
                    hint=fit_created(*signature)
                    if hint is not None and not start-pd.Timedelta(days=1)<=pd.to_datetime(hint,utc=True)<end+pd.Timedelta(days=1):continue
                rows,sessions=read_fit(*signature)
                selected=[r for r in rows if start<=r['time']<end]
                sessions=[s for s in sessions if s['end']>start and s['time']<end and s['end']>s['time']]
                if not selected and not sessions:continue
                count+=1
                for session in sessions:
                    replace_interval(data,'g_activity',[session],session['time'],session['end'])
                if not selected:continue
                a=min(r['time'] for r in selected);b=max(r['time'] for r in selected)+pd.Timedelta(microseconds=1)
                for field in ('hr','rr','cadence','speed','altitude','power','temperature'):
                    valid=[dict(time=r['time'],value=r[field],label='Activity '+field+' · FIT',segment=r['segment'])
                           for r in selected if field in r and (r[field]>=0 or field in ('altitude','temperature')) and (field not in ('hr','rr') or r[field]>0)]
                    replace_interval(data,'g_workout_'+field,valid,a,b)
            except (fitdecode.FitError,ValueError,TypeError,OSError) as exc:warnings.append(f'Activity FIT {path.name} could not be read: {exc}')
        inventory.append(dict(field='Activity FIT files',records=count,source='FitFiles/Activities'))
    if (root/'Sleep').is_dir():inventory.append(dict(field='Sleep JSON nights',records=len(notes),source='Sleep'))
    return notes
