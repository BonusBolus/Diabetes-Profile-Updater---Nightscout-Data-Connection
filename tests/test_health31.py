"""Recorded meals/sleep windows and independently fitted glucose Insight axes."""
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import unittest
import pandas as pd
from insights import aligned_series, insight_available, insight_figures, sleep_events


def fixture():
    start=pd.Timestamp('2026-09-25T00:00Z');days=[(start+pd.Timedelta(days=d)).date() for d in range(4)]
    data={k:pd.DataFrame(columns=['time','value','label']) for k in ('glucose','carbs','iob','bolus','changes','g_sleep_hrv')}
    data['glucose']=pd.DataFrame([dict(time=start+pd.Timedelta(minutes=m),value=(5+m//1440)*18,label='Glucose') for m in range(0,4*1440,5)])
    at=start+pd.Timedelta(days=1,hours=12)
    for minute,value in [(0,90),(5,180),(10,234),(15,180),(20,126)]:
        data['glucose'].loc[data['glucose'].time.eq(at+pd.Timedelta(minutes=minute)),'value']=value
    data['carbs']=pd.DataFrame([dict(time=at,value=30,label='Meal Bolus'),dict(time=at+pd.Timedelta(hours=2),value=10,label='Carb Correction'),dict(time=at+pd.Timedelta(days=1),value=50,label='Meal Bolus')])
    data['iob']=pd.DataFrame([dict(time=at+pd.Timedelta(minutes=m),value=v,label='IOB') for m,v in [(-15,4),(-5,1.2),(1,8)]])
    data['bolus']=pd.DataFrame([dict(time=at+pd.Timedelta(minutes=m),value=v,label=l) for m,v,l in [(-15,2,'User bolus'),(10,.1,'SMB'),(20,.2,'Bolus · unknown type'),(60,7,'User bolus')]])
    stages=[];hrv=[];sessions=[]
    for d in range(3):
        a=start+pd.Timedelta(days=d,hours=22);b=a+pd.Timedelta(hours=8+d)
        sessions.append(dict(time=a,end=b,date=str(b.date())))
        for x,y,stage in [(0,2,'deep_sleep'),(2,6+d,'light_sleep'),(6+d,7+d,'rem_sleep'),(7+d,8+d,'awake')]:
            stages.append(dict(time=a+pd.Timedelta(hours=x),end=a+pd.Timedelta(hours=y),stage=stage,value=1,label=stage))
        hrv.extend([dict(time=a+pd.Timedelta(hours=1),value=40+d*10,label='HRV'),dict(time=a+pd.Timedelta(hours=2),value=60+d*10,label='HRV')])
    data['g_sleep']=pd.DataFrame(stages);data['g_sleep_hrv']=pd.DataFrame(hrv)
    return dict(data=data,zone='UTC',first=days[0],last=days[-1],loaded_at=start+pd.Timedelta(days=4),availability=dict(treatments=True),recorded_profiles=[],garmin_sleep_sessions=sessions,_chart_cache={}),days


class Health31Tests(unittest.TestCase):
    def test_clock_profile_guides_do_not_enter_insight_axes(self):
        import plotly.graph_objects as go
        from nightscout_charts import graph_figures
        loaded,days=fixture()
        profile=go.Figure(go.Scatter(x=[0,600,1440],y=[10,11,11]))
        profile.update_layout(title='I:C',yaxis_title='g/U',meta=dict(profile_changes=[600]))
        figures=graph_figures(profile,loaded,days,'Median + band',
            ['Glucose','Meal-response glucose','Sleep–glucose'],'mmol/L',False)
        insights=[f for f in figures if (f.layout.meta or {}).get('kind')=='insight']
        self.assertEqual(len(insights),2)
        for figure in insights:
            self.assertTrue(figure.layout.meta['non_time'])
            self.assertFalse(figure.layout.meta.get('profile_changes'))
            self.assertFalse(any(s.name=='Profile change' for s in figure.layout.shapes))
        clock_figures=[f for f in figures if not (f.layout.meta or {}).get('non_time')]
        self.assertTrue(all(any(s.name=='Profile change' and s.x0==600 for s in f.layout.shapes) for f in clock_figures))

    def test_meal_windows_context_and_source_dependencies(self):
        loaded,days=fixture();before=loaded['data']['glucose'].copy(deep=True)
        self.assertTrue(insight_available(loaded,'insight_meal'))
        periods=aligned_series(loaded,days,'meal','mmol/L')
        self.assertEqual(len(periods),3);self.assertEqual(periods[0]['duration'],120)
        self.assertLess(max(x for x in periods[0]['x'] if x is not None),120)
        self.assertEqual(periods[0]['baseline'],5);self.assertEqual(max(periods[0]['glucose']),13)
        self.assertEqual(periods[0]['meal'],dict(carbs=30,iob=1.2,cob=None,bolus=dict(user=2,smb=.1,unknown=.2)))
        self.assertIsNone(periods[2]['meal']['iob'])
        pd.testing.assert_frame_equal(before,loaded['data']['glucose'])
        loaded['data']['carbs']=pd.DataFrame();self.assertFalse(insight_available(loaded,'meal'))
        loaded['data']['glucose']=pd.DataFrame();self.assertFalse(insight_available(loaded,'sleep'))

    def test_explicit_sleep_stages_hrv_after_waking_and_no_double_counting(self):
        loaded,days=fixture();loaded['data']['g_sleep']=pd.concat([loaded['data']['g_sleep'],loaded['data']['g_sleep'].iloc[:1]],ignore_index=True)
        events=sleep_events(loaded);self.assertEqual(len(events),3)
        self.assertEqual([e['sleep']['asleep_hours'] for e in events],[7,8,9])
        self.assertEqual([e['sleep']['stage_coverage'] for e in events],[100]*3)
        self.assertEqual([e['sleep']['hrv'] for e in events],[50,60,70])
        self.assertTrue(all(e['sleep']['source']=='Recorded Garmin session' for e in events))
        after=aligned_series(loaded,days,'sleep_after','mmol/L')
        self.assertEqual([s['duration'] for s in after],[16*60,15*60,16*60])
        self.assertTrue(all(max(x for x in s['x'] if x is not None)<s['duration'] for s in after))
        overnight=aligned_series(loaded,days[1:],'sleep','mmol/L')
        self.assertEqual(overnight[0]['x'][0],120,'Unselected dates do not silently enter glucose summaries')
        self.assertTrue(insight_available(loaded,'sleep'))

    def test_meal_cutoff_shared_transform_summaries_cache_and_window_boundaries(self):
        loaded,days=fixture()
        meta=insight_figures(loaded,days,'mmol/L',False,{'insight_meal'})[0].layout.meta
        source=(Path(__file__).parents[1]/'insights_view.js').read_text()
        setup="""const assert=require('assert');const navigation={unit:'mmol/L'};
let state={base:'meal-cutoff',mode:'Median + band',insight:{duration:6,aggregation:'Median',normalization:'absolute'}};
function panelStateAt(){return state;}function applyPanelRanges(){}
const meta="""+json.dumps(meta)+";\n"+"""
function view(){return {data:[],layout:{meta:JSON.parse(JSON.stringify(meta)),yaxis:{},xaxis:{},margin:{}}};}
function render(){const v=view();transformInsight(v,0);return v;}
"""
        checks="""
const original=JSON.stringify(meta);
let v=render();assert.equal(v.layout.meta.insight_summary.length,3);
assert.equal(v.data.find(t=>t.meta.kind==='insight_median').customdata[0],3);
state.insight.minCarbs=20;v=render();
assert.deepEqual(v.layout.meta.insight_summary.map(r=>r.meal.carbs),[30,50]);
assert.equal(v.layout.meta.insight_summary[0].duration,2,'Excluded 10 g record still ends the first response');
assert.equal(v.data.find(t=>t.meta.kind==='insight_median').customdata[0],2);
assert(v.layout.title.text.includes('Carbs > 20 g'));
state.mode='Several days overlaid';v=render();assert.equal(v.data.filter(t=>t.meta.kind==='insight_event').length,2);
state.insight.minCarbs=30;v=render();assert.deepEqual(v.layout.meta.insight_summary.map(r=>r.meal.carbs),[50],'Cutoff is strictly above, not inclusive');
state.insight.minCarbs=50;v=render();assert(v.layout.meta.empty);assert.equal(v.layout.meta.insight_summary.length,0);assert(v.layout.annotations[0].text.includes('above 50 g'));
state.insight.minCarbs=0;v=render();assert.equal(v.layout.meta.insight_summary.length,3,'Restoring cutoff must invalidate the cached result');
assert.equal(JSON.stringify(meta),original,'Filtering must not mutate source periods');
assert.equal(insightCarbCutoff({minCarbs:-20}),0);assert.equal(insightCarbCutoff({minCarbs:'invalid'}),0);
"""
        result=subprocess.run(['node','-e',setup+source+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_stage_only_sessions_keep_unknown_asleep_missing(self):
        loaded,days=fixture();loaded.pop('garmin_sleep_sessions')
        stages=loaded['data']['g_sleep'];loaded['data']['g_sleep']=stages.assign(stage='unknown')
        events=sleep_events(loaded);self.assertEqual(len(events),3)
        self.assertIsNone(events[0]['sleep']['asleep_hours']);self.assertEqual(events[0]['sleep']['stage_coverage'],0)
        self.assertIn('Stage intervals',events[0]['sleep']['source'])

    def test_shared_browser_summaries_relationship_and_fitted_axes(self):
        loaded,days=fixture();figures=insight_figures(loaded,days,'mmol/L',False,{'insight_meal','insight_sleep'})
        metas={f.layout.meta['insight']:f.layout.meta for f in figures}
        source=(Path(__file__).parents[1]/'insights_view.js').read_text()
        setup="""const assert=require('assert');const navigation={unit:'mmol/L'};
let state={base:'meal',mode:'Median + band',insight:{duration:6,aggregation:'Median',normalization:'absolute',fitY:false}};
function panelStateAt(){return state;}function applyPanelRanges(){}
function view(meta){return {data:[],layout:{meta:JSON.parse(JSON.stringify(meta)),yaxis:{},xaxis:{},margin:{}}};}
const metas="""+json.dumps(metas)+";\n"
        checks="""
let v=view(metas.meal);transformInsight(v,0);assert.deepEqual(v.layout.yaxis.range,[0,20]);
const summary=v.layout.meta.insight_summary[0];assert.equal(summary.peak,13);assert.equal(summary.rise,8);assert.equal(summary.peak_time,10/60);assert.equal(summary.returned,15/60);assert.equal(summary.coverage,100);
state.insight.fitY=true;v=view(metas.meal);transformInsight(v,0);assert(v.layout.yaxis.range[0]>0);assert(v.layout.yaxis.range[1]<20);assert(v.layout.shapes.some(s=>s.y0===4&&s.y1===10));
state.insight.duration=.5;v=view(metas.meal);transformInsight(v,0);assert.equal(v.layout.meta.insight_summary[0].duration,.5);
const gap={x:[0,5,null,30],glucose:[5,12,null,7],baseline:5,duration:60};assert.equal(insightPeriodSummary(gap,60,'mmol/L').returned,null);
state={base:'sleep',mode:'Median + band',insight:{duration:24,aggregation:'Median',normalization:'absolute',fitY:true,sleepView:'relationship',relationX:'asleep_hours',relationY:'mean'}};
v=view(metas.sleep);transformInsight(v,0);let t=v.data.find(t=>t.meta.kind==='insight_relationship');assert.deepEqual(t.x,[7,8,9]);assert.equal(t.y.length,3);assert.equal(t.y[2],8);assert.equal(t.mode,'markers');assert.equal(v.layout.meta.insight_pairs,3);assert(v.layout.yaxis.range[0]>0);assert.equal(v.layout.yaxis.title.text,'mmol/L');assert(v.layout.title.text.includes('Next-day mean glucose'));
state.insight.relationX='hrv';state.insight.relationY='tir';v=view(metas.sleep);transformInsight(v,0);t=v.data[0];assert.deepEqual(t.x,[50,60,70]);assert.deepEqual(v.layout.yaxis.range,[0,100]);assert.equal(v.layout.shapes.length,0);
state.insight.sleepView='after';v=view(metas.sleep);transformInsight(v,0);assert(v.layout.xaxis.title.text.includes('waking'));assert(v.layout.meta.insight_summary[0].next.coverage===100);assert(v.data.some(t=>t.meta.kind==='insight_median'));
state.insight.sleepView='overnight';v=view(metas.sleep);transformInsight(v,0);assert(v.layout.xaxis.title.text.includes('sleep start'));assert.equal(v.layout.meta.insight_relationship,false);
"""
        result=subprocess.run(['node','-e',setup+source+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
