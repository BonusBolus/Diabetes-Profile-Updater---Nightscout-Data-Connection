"""Read-only GarminDB adapter. No Garmin login, downloads or source writes."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# Explicit schema mappings: unknown columns are never guessed into health curves.
# key: label, unit, color, source database, table, value column
METRICS = {
 'g_hr': ('Heart rate','bpm','#f06292','garmin_monitoring','monitoring_hr','heart_rate'),
 'g_stress': ('Stress','score','#ffb74d','garmin','stress','stress'),
 'g_rr': ('Respiration','breaths/min','#4dd0e1','garmin_monitoring','monitoring_rr','rr'),
 'g_spo2': ('SpO₂','%','#80cbc4','garmin_monitoring','monitoring_pulse_ox','pulse_ox'),
 'g_hrv': ('HRV','ms','#ba68c8','garmin_monitoring','monitoring_hrv_value','hrv'),
 'g_steps': ('Steps','steps','#aed581','garmin_monitoring','monitoring','steps'),
 'g_sleep': ('Sleep','Sleep stage','#9575cd','garmin','sleep_events','event'),
 'g_activity': ('Activities','Activity','#4fc3f7','garmin_activities','activities','sport'),
}
for key,label,unit,color,column in [
 ('hr','Activity heart rate','bpm','#ec407a','hr'),
 ('rr','Activity respiration','breaths/min','#26c6da','rr'),
 ('cadence','Activity cadence','cycles/min','#d4e157','cadence'),
 ('speed','Activity speed','speed (DB units)','#42a5f5','speed'),
 ('altitude','Activity altitude','altitude (DB units)','#a1887f','altitude'),
 ('power','Activity power','W','#ab47bc','power'),
 ('temperature','Activity temperature','temperature (DB units)','#ff7043','temperature')]:
 METRICS['g_workout_'+key]=(label,unit,color,'garmin_activities','activity_records',column)
METRICS['g_sleep_rr']=('Sleep respiration','breaths/min','#4dd0e1','derived','','')
METRICS['g_sleep_movement']=('Sleep movement','movement level','#ffb74d','derived','','')
METRICS['g_sleep_restless']=('Restless moments','recorded value','#ef5350','derived','','')
METRICS['g_sleep_respiration']=('Respiration during sleep','breaths/min','#4dd0e1','derived','','')
METRICS['g_sleep_rhr']=('Resting heart rate · daily reference','bpm','#f06292','derived','','')
METRICS['g_sleep_spo2']=('Sleep Pulse Ox','%','#80cbc4','derived','','')
METRICS['g_sleep_hrv']=('Overnight HRV','ms','#ba68c8','derived','','')
METRICS['g_waking_rr']=('Respiration outside sleep','breaths/min','#4dd0e1','derived','','')
SLEEP_OVERLAYS={'Movement':'g_sleep_movement','Restless moments':'g_sleep_restless',
 'Respiration':'g_sleep_respiration','Resting heart rate':'g_sleep_rhr','Pulse Ox':'g_sleep_spo2',
 'Sleep respiration':'g_sleep_rr','Overnight HRV':'g_sleep_hrv'}
METRICS['g_steps_cumulative']=('Cumulative steps','steps','#aed581','derived','','')
GARMIN_LAYERS = {'Garmin · '+v[0]: k for k,v in METRICS.items()}
STAGES = {'deep_sleep':(0,'Deep sleep','#673ab7'),'light_sleep':(1,'Light sleep','#9575cd'),
          'rem_sleep':(2,'REM','#ce93d8'),'awake':(3,'Awake','#ffb74d'),
          'unknown':(4,'Sleep session · stages unavailable','#90a4ae')}
SLEEP_AXIS=dict(tickvals=[0],ticktext=['Sleep'],range=[-.5,.5],autorange=False)
DAILY_TABLES=('daily_summary','sleep','resting_hr','weight','hrv')
DAILY_UNITS={'weight':'DB units','resting_heart_rate':'bpm','rhr':'bpm','hr_min':'bpm','hr_max':'bpm',
 'avg_spo2':'%','spo2_avg':'%','spo2_min':'%','avg_rr':'breaths/min','rr_waking_avg':'breaths/min',
 'rr_max':'breaths/min','rr_min':'breaths/min','weekly_avg':'ms','last_night_avg':'ms',
 'last_night_5min_high':'ms','baseline_low':'ms','baseline_upper':'ms'}


def frame():
    return pd.DataFrame(columns=['time','value','label'])


def read_table(conn, table, clock, first, last, overlap=None):
    columns={r[1]:r[2] for r in conn.execute(f'PRAGMA table_info("{table}")')}
    if clock not in columns:return pd.DataFrame(),columns
    # ISO text dates are GarminDB's SQLAlchemy SQLite representation. Read all
    # intervals whose end overlaps the window; point queries use indexed bounds.
    has_end=overlap and overlap in columns
    lower=f'("{overlap}" >= ? OR "{clock}" >= ?)' if has_end else f'"{clock}" >= ?'
    params=[str(first),str(first),str(last)] if has_end else [str(first),str(last)]
    return pd.read_sql_query(f'SELECT * FROM "{table}" WHERE {lower} AND "{clock}" < ? ORDER BY "{clock}"',conn,
                             params=params),columns


def localize(series, zone, warnings):
    ts=pd.to_datetime(series,errors='coerce',format='mixed')
    if ts.dt.tz is None:
        ts=ts.dt.tz_localize(zone,ambiguous='NaT',nonexistent='NaT')
    bad=int(ts.isna().sum())
    if bad:warnings.append(f'{bad} invalid or ambiguous timestamps omitted; check the Garmin database timezone.')
    return ts.dt.tz_convert('UTC')


def metric_unit(key, loaded):
    system=loaded.get('garmin_units','Unknown')
    extra={'g_workout_speed':('km/h','mph'),'g_workout_altitude':('m','ft'),'g_workout_temperature':('°C','°F')}
    return extra[key][system=='Statute'] if key in extra and system in ('Metric','Statute') else METRICS[key][1]


def load_garmin(folder, first, last, source_zone, display_zone, measurement_units='Metric'):
    ZoneInfo(source_zone);ZoneInfo(display_zone)
    if last<first or (last-first).days>30:raise ValueError('Load between 1 and 31 days at a time.')
    root=Path(folder).expanduser()
    if not root.is_dir():raise ValueError('Choose the folder containing the GarminDB .db files on this PC.')
    health_root=root.parent if root.name.casefold()=='dbs' else root
    db_root=root/'DBs' if (root/'DBs').is_dir() else root
    paths={p.stem:p for p in db_root.glob('*.db') if p.stem in ('garmin','garmin_monitoring','garmin_activities')}
    if not paths:raise ValueError('No garmin.db, garmin_monitoring.db or garmin_activities.db found in this folder.')
    warnings=[];data={};daily=[];inventory=[];activities=[];sleep_sessions=[]
    # A day of padding covers timezone offsets and steps' previous sample.
    begin=first-timedelta(days=1);stop=last+timedelta(days=2)
    start_utc=pd.Timestamp(first).tz_localize(display_zone).tz_convert('UTC')
    end_utc=pd.Timestamp(last+timedelta(days=1)).tz_localize(display_zone).tz_convert('UTC')
    for db,path in paths.items():
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)) as conn:
            conn.execute('PRAGMA query_only=ON');conn.execute('BEGIN')
            tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            cache={}
            def read(table,clock='timestamp',overlap=None):
                if table not in tables:return pd.DataFrame(),{}
                ck=(table,clock,overlap)
                if ck not in cache:cache[ck]=read_table(conn,table,clock,begin,stop,overlap)
                return cache[ck]
            for key,(label,unit,color,source,table,column) in METRICS.items():
                if source!=db:continue
                clock='start_time' if key=='g_activity' else 'timestamp'
                raw,cols=read(table,clock,'stop_time' if key=='g_activity' else None)
                if raw.empty or (column not in cols and key!='g_activity'):continue
                raw=raw.copy();raw['time']=localize(raw[clock],source_zone,warnings)
                raw=raw.dropna(subset=['time'])
                if key=='g_sleep':
                    if 'duration' not in raw:continue
                    raw['end']=raw.time+pd.to_timedelta(raw.duration.astype(str),errors='coerce')
                    raw['label']=raw.event.map(lambda s:STAGES.get(s,STAGES['unknown'])[1])
                    raw['stage']=raw.event.where(raw.event.isin(STAGES),'unknown')
                    raw['value']=raw.stage.map(lambda s:STAGES[s][0])
                    result=raw[['time','end','value','label','stage']]
                elif key=='g_activity':
                    from garmin_exports import activity_label
                    raw['end']=localize(raw.stop_time,source_zone,warnings) if 'stop_time' in raw else pd.Series(pd.NaT,index=raw.index,dtype='datetime64[ns, UTC]')
                    if 'elapsed_time' in raw:
                        duration=pd.to_timedelta(raw.elapsed_time.astype(str),errors='coerce')
                        raw['end']=raw.end.where(raw.end.gt(raw.time),raw.time+duration)
                    raw['value']=1.;raw['label']=[activity_label(r.get('sport'),r.get('sub_sport'),r.get('type')) for r in raw.to_dict('records')]
                    if 'activity_id' not in raw:raw['activity_id']=''
                    raw['source']='GarminDB'
                    incomplete=~raw.end.gt(raw.time)
                    if incomplete.any() and raw.activity_id.ne('').any():
                        records,record_cols=read('activity_records')
                        if not records.empty and 'activity_id' in record_cols:
                            ends=records.groupby('activity_id').timestamp.max()
                            observed=localize(raw.activity_id.map(ends),source_zone,[])
                            recovered=incomplete & observed.gt(raw.time)
                            raw.loc[recovered,'end']=observed[recovered]
                            raw.loc[recovered,'source']='GarminDB · end at last recorded activity sample'
                    result=raw[['time','end','value','label','activity_id','source']]
                    # All available activity summary fields, with original schema names.
                    safe=raw.drop(columns=[c for c in raw if 'lat' in c or 'long' in c or c in ('time','end')])
                    activities.extend({k:None if pd.isna(v) else v for k,v in row.items()} for row in safe.to_dict('records') if str(first)<=str(row.get('start_time',''))[:10]<=str(last))
                elif key=='g_steps':
                    if 'activity_type' not in raw:continue
                    raw['value']=pd.to_numeric(raw[column],errors='coerce')
                    raw=raw.sort_values('time').drop_duplicates(['time','activity_type'],keep='last')
                    raw['date']=raw.time.dt.tz_convert(source_zone).dt.date
                    groups=raw.groupby(['activity_type','date'],dropna=False)
                    delta=groups.value.diff();gap=groups.time.diff().dt.total_seconds()
                    # Cumulative counters: skip first observations, resets and long
                    # unknown intervals. Never assign a day's total to one hour.
                    raw['value']=delta.where(delta.ge(0)&gap.gt(0)&gap.le(1200))
                    raw['label']='Steps since previous sample'
                    result=raw[['time','value','label']].dropna(subset=['value'])
                    result=result.groupby('time',as_index=False).agg(value=('value','sum'),label=('label','first'))
                else:
                    raw['value']=pd.to_numeric(raw[column],errors='coerce')
                    valid=raw.value.notna() & np.isfinite(raw.value)
                    if key=='g_stress':valid &= raw.value.between(0,100)
                    elif key=='g_spo2':valid &= raw.value.gt(0)&raw.value.le(100)
                    elif key not in ('g_workout_temperature','g_workout_altitude'):valid &= raw.value.ge(0) if key in ('g_workout_speed','g_workout_cadence','g_workout_power') else raw.value.gt(0)
                    raw['label']=label
                    result=raw.loc[valid,['time','value','label']].groupby('time',as_index=False).agg(value=('value','median'),label=('label','first'))
                    if key.startswith('g_workout_') and 'activity_id' in raw:
                        result=result.merge(raw[['time','activity_id']].drop_duplicates('time'),on='time',how='left').rename(columns={'activity_id':'segment'})
                result=result.dropna(subset=['time','value'])
                if 'end' in result:
                    result=result[result.end.gt(result.time)&result.end.gt(start_utc)&result.time.lt(end_utc)]
                else:result=result[result.time.ge(start_utc)&result.time.lt(end_utc)]
                if not result.empty:
                    data[key]=result.reset_index(drop=True)
                    inventory.append(dict(field=label,records=len(result),source=table))
            if db=='garmin':
                for table in DAILY_TABLES:
                    raw,cols=read(table,'day')
                    if raw.empty:continue
                    for row in raw.to_dict('records'):
                        day=str(row['day'])[:10]
                        if not str(first)<=day<=str(last):continue
                        for column,sqltype in cols.items():
                            if column in ('day','start','end'):continue
                            value=row.get(column)
                            if value is None or pd.isna(value):continue
                            unit=DAILY_UNITS.get(column,'')
                            if column=='weight' and measurement_units in ('Metric','Statute'):unit='kg' if measurement_units=='Metric' else 'lb'
                            if 'TIME' in sqltype.upper():
                                try:value=pd.to_timedelta(str(value)).total_seconds()/3600;unit='h'
                                except (ValueError,TypeError):continue
                            elif isinstance(value,(float,int)) and not np.isfinite(value):continue
                            daily.append(dict(date=day,field=table+' · '+column.replace('_',' '),value=value,unit=unit))
                sessions,cols=read('sleep','start','end')
                if not sessions.empty and 'end' in cols:
                    existing=data.get('g_sleep',pd.DataFrame(columns=['time','end']))
                    unknown=[]
                    for row in sessions.to_dict('records'):
                        times=localize(pd.Series([row['start'],row['end']]),source_zone,warnings)
                        a,b=times.iloc[0],times.iloc[1]
                        if pd.isna(a) or pd.isna(b) or b<=a or b<=start_utc or a>=end_utc:continue
                        sleep_sessions.append(dict(time=a,end=b,date=str(row['day'])[:10]))
                        # Only a whole session without any stage data gets a generic
                        # band; gaps in a partly staged night must stay blank.
                        if not existing.empty and ((existing.time<b)&(existing.end>a)).any():continue
                        unknown.append(dict(time=a,end=b,value=4,label=STAGES['unknown'][1],stage='unknown'))
                    if unknown:
                        data['g_sleep']=pd.concat([existing,pd.DataFrame(unknown)],ignore_index=True)
                        data['g_sleep']['time']=pd.to_datetime(data['g_sleep']['time'],utc=True)
                        data['g_sleep']['end']=pd.to_datetime(data['g_sleep']['end'],utc=True)
    if 'g_sleep' in data and 'g_rr' in data:
        rr=data['g_rr'];inside=pd.Series(False,index=rr.index)
        for row in data['g_sleep'].itertuples():inside |= rr.time.ge(row.time)&rr.time.lt(row.end)
        if inside.any():data['g_sleep_rr']=rr[inside].copy()
    from garmin_exports import supplement_exports
    sleep_notes=supplement_exports(health_root,data,activities,daily,inventory,warnings,start_utc,end_utc,display_zone)
    activity_count=len(data.get('g_activity',[]))
    inventory.append(dict(field='Recorded activity intervals',records=activity_count,source='GarminDB / FIT sessions'))
    if not activity_count and any(k.startswith('g_workout_') for k in data):
        warnings.append('Activity samples loaded, but no usable activity intervals were found. Check the activity FIT files and GarminDB activity summaries; the activity zoom control remains disabled.')
    for note in sleep_notes:
        a,b=pd.Timestamp(note['start']),pd.Timestamp(note['end'])
        sleep_sessions=[s for s in sleep_sessions if not (s['time']<b and s['end']>a)]
        sleep_sessions.append(dict(time=a,end=b,date=note['date']))
    add_sleep_fields(data,daily,sleep_sessions,display_zone)
    if not data and not daily: warnings.append('No supported populated health fields found for these dates.')
    return dict(sleep_notes=sleep_notes,data=data,daily=daily,activities=activities,inventory=inventory,warnings=list(dict.fromkeys(warnings)),
                first=first,last=last,zone=display_zone,source_zone=source_zone,measurement_units=measurement_units,loaded_at=datetime.now(timezone.utc))


def add_sleep_fields(data,daily,sessions,zone):
    """Use recorded sleep intervals; a daily RHR reference is never a measured curve."""
    intervals=sessions or [dict(time=r.time,end=r.end,date=str(r.end.tz_convert(zone).date()))
                          for r in data.get('g_sleep',pd.DataFrame()).itertuples()]
    for source,target in [('g_rr','g_sleep_respiration'),('g_spo2','g_sleep_spo2'),('g_hrv','g_sleep_hrv')]:
        points=data.get(source,frame());inside=pd.Series(False,index=points.index)
        for s in intervals:inside |= points.time.ge(s['time'])&points.time.lt(s['end'])
        if inside.any():data[target]=points[inside].copy()
        if source=='g_rr' and not points.empty:data['g_waking_rr']=points[~inside].copy()
    rhr={r['date']:r['value'] for r in daily if r['field']=='resting_hr · resting heart rate'}
    rows=[dict(time=s['time'],end=s['end'],value=float(rhr[s['date']]),label='Resting heart rate · daily reference')
          for s in intervals if isinstance(rhr.get(s['date']),(float,int)) and rhr[s['date']]>0]
    if rows:data['g_sleep_rhr']=pd.DataFrame(rows).drop_duplicates(['time','end'])


def merge_sources(ns, garmin):
    """New immutable view snapshot; never add Garmin data to saved profiles."""
    base=dict(ns) if ns else dict(first=garmin['first'],last=garmin['last'],zone=garmin['zone'],
                  loaded_at=garmin['loaded_at'],warnings=[],availability={'treatments':False})
    if ns:
        base['nightscout_first']=ns['first'];base['nightscout_last']=ns['last']
    if garmin:
        base['first']=min(base['first'],garmin['first']);base['last']=max(base['last'],garmin['last'])
    base['has_nightscout']=ns is not None
    base['data']=dict(ns['data']) if ns else {k:frame() for k in ('glucose','basal','basal_percent','iob','cob','bolus','carbs','target','variable_sens')}
    base['_chart_cache']={};base['garmin_daily']=[];base['garmin_activities']=[];base['day_sources']={}
    if ns:
        for day in pd.date_range(ns['first'],ns['last']):base['day_sources'][day.date()]=['Nightscout loaded']
    if garmin and garmin['zone']==base['zone']:
        base['garmin_loaded_at']=garmin['loaded_at'];base['garmin_sleep_notes']=garmin.get('sleep_notes',[]);base['garmin_units']=garmin.get('measurement_units','Metric');base['data'].update(garmin['data']);base['garmin_daily']=garmin['daily'];base['garmin_activities']=garmin['activities']
        for key,df in garmin['data'].items():
            dates=set(df.time.dt.tz_convert(base['zone']).dt.date)
            if 'end' in df:
                for row in df.itertuples():
                    a=row.time.tz_convert(base['zone']).date()
                    b=(row.end-pd.Timedelta(microseconds=1)).tz_convert(base['zone']).date()
                    dates.update(day.date() for day in pd.date_range(a,b))
            for day in dates:
                names=base['day_sources'].setdefault(day,[])
                if 'Garmin records' not in names:names.append('Garmin records')
        for row in garmin['daily']:
            day=datetime.fromisoformat(row['date']).date();names=base['day_sources'].setdefault(day,[])
            if 'Garmin records' not in names:names.append('Garmin records')
    return base
