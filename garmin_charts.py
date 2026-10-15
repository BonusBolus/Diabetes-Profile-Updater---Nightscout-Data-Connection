"""Garmin timelines with dated traces for the offline/expanded viewer."""
from html import escape
from collections import Counter
from chart_cache import cached
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from garmin_data import METRICS, STAGES, SLEEP_AXIS, metric_unit

# Pixels per recorded date in a multi-day sleep timeline. Shared with the viewer.
SLEEP_DAY_HEIGHT=28

def _rgba(color,opacity):
    return f'rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},{opacity})'


def quartile_bands(low,high,color,label,meta,step=False,visible=True):
    """Closed polygons per contiguous observed region; never bridge missing bins."""
    valid=low.notna()&high.notna();regions=valid.ne(valid.shift()).cumsum();bands=[]
    for _,part in low[valid].groupby(regions[valid]):
        xs=part.index.tolist();lo=part.tolist();hi=high.loc[xs].tolist()
        if step:
            # Explicit stair vertices keep both polygon edges aligned to five-minute bins.
            edges=xs+[min(1440,xs[-1]+5)]
            xs=[v for a,b in zip(edges,edges[1:]) for v in (a,b)]
            lo=[v for y in lo for v in (y,y)];hi=[v for y in hi for v in (y,y)]
        elif len(xs)==1:xs=[xs[0],xs[0]+5];lo=lo*2;hi=hi*2
        bands.append(go.Scatter(x=xs+xs[::-1],y=hi+lo[::-1],mode='lines',line=dict(width=0),fill='toself',
            fillcolor=_rgba(color,.18),name=label+' 25–75%',hoverinfo='skip',showlegend=False,visible=visible,meta=meta))
    return bands


def segments(frame, day, zone):
    begin=pd.Timestamp(day).tz_localize(zone).tz_convert('UTC')
    end=(pd.Timestamp(day)+pd.Timedelta(days=1)).tz_localize(zone).tz_convert('UTC')
    for row in frame.itertuples():
        a=max(row.time,begin);b=min(row.end,end)
        if a>=b:continue
        local=a.tz_convert(zone);finish=b.tz_convert(zone)
        x=local.hour*60+local.minute+local.second/60
        y=1440 if b==end else finish.hour*60+finish.minute+finish.second/60
        # Do not draw a backwards segment through the repeated DST hour.
        if y<=x:continue
        yield row,x,y,a,b


def sleep_probabilities(frame,days,zone):
    rows=[]
    for day in days:
        for row,x,y,a,b in segments(frame,day,zone):
            if row.stage=='unknown':continue
            slot=int(x//5)*5
            while slot<y:
                minutes=max(0,min(y,slot+5)-max(x,slot))
                if minutes:rows.append((str(day),slot,row.stage,minutes))
                slot+=5
    if not rows:return pd.DataFrame(),{}
    raw=pd.DataFrame(rows,columns=['day','minute','stage','duration'])
    per=raw.groupby(['day','minute','stage']).duration.sum().unstack('stage',fill_value=0)
    # Treat each night's observed portion equally; missing nights are excluded.
    per=per.div(per.sum(axis=1),axis=0)*100
    return per.groupby('minute').mean().reindex(range(0,1440,5)),per.groupby('minute').size().to_dict()


def hourly_sleep_distribution(frame,days,zone):
    """Hourly stage durations across dates with known stage intervals.

    Dates without any stage data are excluded, rather than declared awake.
    Within included dates, hours with no recorded sleep contribute zero.
    """
    rows=[];recorded=set()
    for day in days:
        for row,x,y,a,b in segments(frame,day,zone):
            if row.stage=='unknown':continue
            recorded.add(str(day))
            slot=int(x//60)*60
            while slot<y:
                minutes=max(0,min(y,slot+60)-max(x,slot))
                if minutes:rows.append((str(day),slot//60,row.stage,minutes))
                slot+=60
    if not recorded:return pd.DataFrame(),0
    raw=pd.DataFrame(rows,columns=['day','hour','stage','minutes'])
    per=raw.groupby(['day','hour','stage']).minutes.sum().unstack('stage',fill_value=0)
    # Defensive cap for duplicate/overlapping exports, preserving stage proportions.
    per=per.mul((60/per.sum(axis=1)).clip(upper=1),axis=0)
    result=(per.groupby('hour').sum()/len(recorded)).reindex(range(24),fill_value=0)
    asleep=per.drop(columns=['awake'],errors='ignore').sum(axis=1)
    asleep=asleep.reindex(pd.MultiIndex.from_product([sorted(recorded),range(24)],names=['day','hour']),fill_value=0)
    result.attrs['median']=asleep.groupby('hour').median().tolist()
    result.attrs['distribution']={name:(asleep.groupby('hour').quantile(q)/60).tolist() if len(recorded)>=2 else [None]*24 for name,q in [('p10',.1),('p90',.9),('p25',.25),('p75',.75)]}
    # A stack of independent stage medians can exceed an hour, or become all
    # zero despite everyone sleeping. Split the median total by the observed
    # asleep-stage mix instead, and identify that composition in the hover.
    mix=result.drop(columns=['awake'],errors='ignore')
    mix=mix.div(mix.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
    median=mix.mul(result.attrs['median'],axis=0)
    if 'awake' in per:
        awake=per.awake.reindex(asleep.index,fill_value=0)
        median['awake']=awake.groupby('hour').median().reindex(range(24),fill_value=0)
    result.attrs['median_stages']=median.to_dict('list')
    return result,len(recorded)


def garmin_traces(key,loaded,days,mode):
    frame=loaded['data'].get('g_steps' if key=='g_steps_cumulative' else key,pd.DataFrame())
    if frame.empty:return []
    label,unit,color,*_=METRICS[key];unit=metric_unit(key,loaded);zone=loaded['zone'];traces=[]
    if key=='g_sleep' and mode=='Median + band':
        stats,counts=cached(loaded,'sleep_summary',('stages',tuple(days),zone),lambda:sleep_probabilities(frame,days,zone))
        if stats.empty:return []
        base=pd.Series(0.,index=stats.index)
        for stage in ('deep_sleep','light_sleep','rem_sleep','awake'):
            if stage not in stats:continue
            _,name,c=STAGES[stage]
            traces.append(go.Bar(x=[x+2.5 for x in stats.index],y=stats[stage].tolist(),base=base.tolist(),width=5,
                name=name,offsetgroup='sleep-stage',marker_color=c,customdata=[counts.get(x,0) for x in stats.index],
                meta=dict(kind='median',dataset=key,label=name+' · observed dates',unit='%',sleep_variant='stages',legend_entry=True),
                hovertemplate='%{y:.1f}% · %{customdata} recorded dates<extra>'+name+'</extra>'))
            base=base+stats[stage].fillna(0)
        hourly,denominator=cached(loaded,'sleep_summary',('hourly',tuple(days),zone),lambda:hourly_sleep_distribution(frame,days,zone))
        # One real hourly stack, with explicit common positions and bases.
        # Do not repeat each hour's statistic as twelve adjacent five-minute bars.
        minutes=list(range(0,1440,60));base=[0.]*len(minutes)
        for stage in ('deep_sleep','light_sleep','rem_sleep','awake'):
            if stage not in hourly:continue
            _,name,c=STAGES[stage];values=[float(hourly.loc[x//60,stage])/60 for x in minutes]
            traces.append(go.Bar(x=[x+30 for x in minutes],y=values,base=base,width=54,offsetgroup='sleep-stage',
                name=name,marker_color=c,customdata=[denominator]*len(minutes),
                meta=dict(kind='sleep_distribution',dataset=key,label=name+' · hourly average',unit='h/hour',sleep_variant='hourly',aggregation='Average',legend_entry=True),
                hovertemplate='%{y:.3g} h per clock hour · %{customdata} recorded dates<extra>'+name+'</extra>'))
            base=[a+b for a,b in zip(base,values)]
        base=[0.]*len(minutes)
        for stage in ('deep_sleep','light_sleep','rem_sleep','awake'):
            if stage not in hourly.attrs['median_stages']:continue
            _,name,c=STAGES[stage];values=[v/60 for v in hourly.attrs['median_stages'][stage]]
            detail='Median awake duration' if stage=='awake' else 'Median asleep duration × recorded stage share'
            traces.append(go.Bar(x=[x+30 for x in minutes],y=values,base=base,width=54,offsetgroup='sleep-stage',
                name=name,marker_color=c,customdata=[denominator]*len(minutes),
                meta=dict(kind='sleep_distribution',dataset=key,label=name+' · median hourly sleep',unit='h/hour',sleep_variant='hourly',aggregation='Median',legend_entry=True),
                hovertemplate='%{y:.3g} h per clock hour · %{customdata} recorded dates<br>'+detail+'<extra>'+name+'</extra>'))
            base=[a+b for a,b in zip(base,values)]
        for aggregation in ('Average','Median'):
            first=next((t for t in traces if t.meta.get('aggregation')==aggregation),None)
            if first is not None:first.meta=dict(first.meta,distribution=hourly.attrs['distribution'])
        return traces
    if key in ('g_sleep','g_activity'):
        # Activities are categorical intervals, never averaged as numeric amounts.
        for day in days:
            grouped={}
            for row,x,y,a,b in segments(frame,day,zone):
                name=row.label;c=STAGES.get(getattr(row,'stage','unknown'),STAGES['unknown'])[2] if key=='g_sleep' else activity_color(row.label)
                values=grouped.setdefault((name,row.value,c),[[],[],[]])
                duration=(b-a).total_seconds()/60
                hover=f'{a.tz_convert(zone):%Y-%m-%d %H:%M %z} – {b.tz_convert(zone):%H:%M %z} · {duration:g} min'
                values[0].extend([x,y,None]);values[1].extend([0 if key=='g_sleep' else row.value,0 if key=='g_sleep' else row.value,None]);values[2].extend([hover,hover,''])
            for (name,value,c),(xs,ys,details) in grouped.items():
                traces.append(go.Scatter(x=xs,y=ys,name=name,customdata=details,mode='lines',
                    line=dict(color=c,width=64 if key=='g_sleep' else 18),connectgaps=False,
                    meta=dict(kind='garmin_sleep' if key=='g_sleep' else 'garmin_interval',dataset=key,label=name,unit='',date=str(day)),
                    hovertemplate='%{customdata}<extra>'+escape(name)+'</extra>'))
        return traces
    if 'end' in frame and mode=='Median + band':
        samples=[]
        for day in days:
            for row,x,y,a,b in segments(frame,day,zone):
                slot=int(x//5)*5
                while slot<y:
                    weight=max(0,min(y,slot+5)-max(x,slot))
                    if weight:samples.append(dict(time=pd.Timestamp(day).tz_localize(zone).tz_convert('UTC')+pd.Timedelta(minutes=slot),value=row.value,weight=weight))
                    slot+=5
        if not samples:return []
        sample=pd.DataFrame(samples);sample['weighted']=sample.value*sample.weight
        grouped=sample.groupby('time')[['weighted','weight']].sum()
        frame=(grouped.weighted/grouped.weight).rename('value').reset_index()
    points=frame.copy();local=points.time.dt.tz_convert(zone)
    points['day']=local.dt.date;points['minute']=local.dt.hour*60+local.dt.minute+local.dt.second/60+local.dt.microsecond/60_000_000
    points=points[points.day.isin(days)]
    if points.empty:return []
    if key in ('g_steps','g_steps_cumulative'):
        points['slot']=points.minute//60*60
        per=points.groupby(['day','slot']).value.sum()
        if key=='g_steps':
            if mode in ('Median + band','Multiple days'):
                hourly=per.groupby('slot').agg(['mean','median','count']).reindex(range(0,1440,60))
                return [go.Bar(x=[x+30 for x in hourly.index],y=hourly[column].tolist(),width=50,
                    name=name+' hourly steps',marker_color=color,customdata=hourly['count'].fillna(0).tolist(),
                    visible=name=='Average',meta=dict(kind='garmin_aggregate',dataset=key,unit=unit,aggregation=name,label=name+' hourly steps',distribution={name:per.groupby('slot').quantile(q).reindex(hourly.index).where(hourly['count'].ge(2)).tolist() for name,q in [('p10',.1),('p90',.9),('p25',.25),('p75',.75)]}),
                    hovertemplate='%{y:g} steps · %{customdata} days<extra></extra>') for name,column in [('Average','mean'),('Median','median')]]
            return [go.Bar(x=[x[1]+30 for x in group.index],y=group.tolist(),width=50,name=label,
                    marker_color=color,opacity=.65,meta=dict(kind='garmin',dataset=key,label='Observed hourly steps',unit=unit,date=str(day)))
                    for day,group in per.groupby(level=0)]
        if mode=='Median + band':
            cumulative=points.sort_values('time').copy()
            cumulative['total']=cumulative.groupby('day').value.cumsum()
            cumulative['slot']=cumulative.minute//5*5
            daily=cumulative.groupby(['day','slot']).total.last().unstack('slot').reindex(columns=range(0,1440,5)).ffill(axis=1)
            now=pd.Timestamp(loaded.get('garmin_loaded_at',loaded['loaded_at'])).tz_convert(zone)
            for day in daily.index:
                if day>=now.date():
                    stop=now.hour*60+now.minute if day==now.date() else -1
                    daily.loc[day,daily.columns>stop]=float('nan')
            totals=daily.median().reindex(range(0,1440,5));counts=daily.count()
            low=daily.quantile(.25).where(counts.ge(2));high=daily.quantile(.75).where(counts.ge(2))
            bands=quartile_bands(low,high,color,'Cumulative steps',
                dict(kind='garmin_band',dataset=key,unit=unit,label='Cumulative steps 25–75%',variant='cumulative'),step=True)
            for i,band in enumerate(bands):
                band.name='25–75%';band.legendgroup='cumulative-iqr';band.showlegend=i==0
                band.meta=dict(band.meta,legend_entry=i==0);band.fillcolor=_rgba(color,.28)
            line=go.Scatter(x=totals.index.tolist(),y=totals.tolist(),mode='lines',name='Median',
                line=dict(color=color,width=2.5,shape='hv'),connectgaps=False,customdata=counts.tolist(),
                meta=dict(kind='median',dataset=key,unit=unit,label='Median cumulative steps',variant='cumulative',summary=dict(p10=daily.quantile(.10).where(counts.ge(2)).tolist(),p90=daily.quantile(.90).where(counts.ge(2)).tolist(),count=counts.tolist())),
                hovertemplate='%{y:g} steps · %{customdata} days<extra>Median</extra>')
            return bands+[line]
        # A separate observed-increment line; never assume missing increments are zero.
        for day_index,(day,part) in enumerate(points.groupby('day')):
            part=part.sort_values('time');xs=[];ys=[];total=0.;previous=None
            for row in part.itertuples():
                total+=row.value;xs.append(float(row.minute));ys.append(float(total));previous=row.minute
            if xs:
                now=pd.Timestamp(loaded.get('garmin_loaded_at',loaded['loaded_at'])).tz_convert(zone)
                stop=1440 if day<now.date() else now.hour*60+now.minute if day==now.date() else xs[-1]
                if stop>xs[-1]:xs.append(float(stop));ys.append(total)
            traces.append(go.Scatter(x=xs,y=ys,name=f'Cumulative · {day}' if mode=='Multiple days' else 'Cumulative observed steps',mode='lines',visible=True,
                          line=dict(color=color,width=2,shape='hv',dash=['solid','dash','dot','dashdot'][day_index%4] if mode=='Multiple days' else 'solid'),connectgaps=False,
                          meta=dict(kind='garmin',dataset=key,label='Cumulative observed steps · held between observations',unit=unit,date=str(day),variant='cumulative')))
        return traces
    if mode=='Median + band':
        points['slot']=points.minute//5*5
        per=points.groupby(['day','slot']).value.sum(min_count=1) if key=='g_sleep_restless' else points.groupby(['day','slot']).value.median()
        group=per.groupby('slot');stats=group.agg(['median','count']).reindex(range(0,1440,5))
        low=group.quantile(.25).reindex(stats.index);high=group.quantile(.75).reindex(stats.index)
        bands=quartile_bands(low,high,color,label,dict(kind='garmin_band',dataset=key,unit=unit))
        meta=dict(kind='median',dataset=key,label='Median '+label,unit=unit,summary=dict(p10=group.quantile(.10).reindex(stats.index).tolist(),p90=group.quantile(.90).reindex(stats.index).tolist(),count=stats['count'].tolist()))
        if key in ('g_stress','g_sleep_restless'):
            meta.update(average=group.mean().reindex(stats.index).tolist(),median=stats['median'].tolist())
        line=go.Scatter(x=stats.index.tolist(),y=stats['median'].tolist(),mode='lines+markers' if key.startswith('g_sleep_') else 'lines',marker=dict(size=3),name='Median '+label,
            line=dict(color=color,width=2),customdata=stats['count'].fillna(0).tolist(),connectgaps=False,
            meta=meta,hovertemplate='%{y:.3g} '+unit+' · %{customdata} days<extra></extra>')
        return bands+[line]
    if key in ('g_sleep_movement','g_sleep_rhr'):
        for day in days:
            xs=[];ys=[]
            for row,x,y,_,_ in segments(frame,day,zone):xs.extend([x,y,None]);ys.extend([row.value,row.value,None])
            if xs:traces.append(go.Scatter(x=xs,y=ys,mode='lines',name=label,line=dict(color=color,width=2),
                meta=dict(kind='garmin',dataset=key,label=label,unit=unit,date=str(day))))
        return traces
    if key.startswith('g_workout_'):
        for day,group in points.groupby('day'):
            group=group.sort_values('time')
            # Retain native samples. For very long days keep min/max per temporal bucket.
            if len(group)>12000:
                buckets=group.groupby(pd.Series(range(len(group)),index=group.index)//math.ceil(len(group)/6000))
                keep=set(buckets.value.idxmin())|set(buckets.value.idxmax())|{group.index[0],group.index[-1]}
                group=group.loc[sorted(keep)].sort_values('time')
            xs=[];ys=[];previous=None;last_segment=None
            for row in group.itertuples():
                segment=getattr(row,'segment',None)
                if previous is not None and ((row.time-previous).total_seconds()>30 or segment!=last_segment):
                    xs.append(None);ys.append(None)
                xs.append(float(row.minute));ys.append(float(row.value));previous=row.time;last_segment=segment
            traces.append(go.Scatter(x=xs,y=ys,mode='lines',name=label,line=dict(color=color,width=1.8),
                connectgaps=False,meta=dict(kind='garmin',dataset=key,label=label,unit=unit,date=str(day)),
                hovertemplate='%{y:.3g} '+unit+'<extra>'+label+'</extra>'))
        return traces
    # Bound the viewer payload: one sample/bin, with explicit gaps between bins.
    width=5 if len(days)>7 else 1
    for day,group in points.groupby('day'):
        binned=group.assign(slot=group.minute//width*width).groupby('slot').value
        group=binned.sum(min_count=1) if key=='g_sleep_restless' else binned.median()
        xs=[];ys=[];previous=None
        for minute,value in group.items():
            if previous is not None and minute-previous>max(width*2,5):xs.append(None);ys.append(None)
            xs.append(int(minute));ys.append(float(value));previous=minute
        traces.append(go.Scatter(x=xs,y=ys,mode='markers' if key=='g_sleep_restless' else 'lines+markers',marker=dict(size=5 if key=='g_sleep_restless' else 3),line=dict(color=color,width=1.8),
                      name=label,connectgaps=False,meta=dict(kind='garmin',dataset=key,label=label,unit=unit,date=str(day)),
                      hovertemplate='%{y:.3g} '+unit+'<extra>'+label+'</extra>'))
    return traces


def apply_garmin_axis(fig,key,mode,secondary=False):
    axis='yaxis2' if secondary else 'yaxis'
    if key=='g_sleep':
        fig.update_layout(**{axis:dict(SLEEP_AXIS) if mode!='Median + band' else dict(title='Observed nights (%)',range=[0,100],autorange=False)})
    elif key.startswith('g_workout_'):
        values=[float(v) for t in fig.data if (t.yaxis or 'y')==('y2' if secondary else 'y') for v in t.y if v is not None and pd.notna(v)]
        limits=padded_range(values)
        fig.update_layout(**{axis:dict(rangemode='normal',**(dict(range=limits,autorange=False) if limits else dict(autorange=True)))})
    elif key=='g_hr':
        values=[v for t in fig.data for v in t.y if v is not None and pd.notna(v)]
        fig.update_layout(**{axis:dict(range=[min(35,min(values)) if values else 35,max(100,max(values)*1.08) if values else 100],autorange=False)})
    elif key=='g_stress':fig.update_layout(**{axis:dict(range=[0,100],autorange=False)})
    elif key=='g_activity':fig.update_layout(**{axis:dict(tickvals=[1],ticktext=['Exercise'],range=[0,2],autorange=False)})


def activity_color(label):
    from garmin_exports import ACTIVITY_COLORS, canonical_activity
    name=canonical_activity(label).casefold()
    return ACTIVITY_COLORS.get(name,next((c for sport,c in ACTIVITY_COLORS.items() if sport in name.split()),'#90a4ae'))


def activity_shapes(loaded,days,mode):
    # No actual episode shading on an across-day median; that would imply an average activity.
    if mode=='Median + band':return []
    out=[]
    for day in days:
        intervals=sorted(segments(loaded['data'].get('g_activity',pd.DataFrame()),day,loaded['zone']),key=lambda s:s[3])
        totals=Counter(s[0].label for s in intervals);counts=Counter()
        for row,x,y,_,_ in intervals:
            counts[row.label]+=1
            label=row.label.replace('_',' ').title()+(f' {counts[row.label]}' if totals[row.label]>1 else '')
            identity=str(getattr(row,'activity_id','')) or row.time.isoformat()
            out.append(dict(type='rect',name='Activity | '+str(day)+' | '+label+' | '+identity,
                xref='x',yref='paper',x0=x,x1=y,y0=0,y1=1,line=dict(width=.7,color=_rgba(activity_color(row.label),.25)),
                fillcolor=_rgba(activity_color(row.label),.055),layer='below',
                label=dict(text=escape(label),textposition='top left',font=dict(size=11,color=activity_color(row.label)))))
    return out


def padded_range(values):
    if not values:return None
    low,high=min(values),max(values)
    margin=.06*(high-low) if high>low else max(abs(high)*.03,.5)
    return [low-margin,high+margin]
