"""Duration-weighted events, honest sleep distributions and compact marker contracts."""
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import subprocess,unittest
import pandas as pd
from event_stats import hourly_state_events
from garmin_charts import hourly_sleep_distribution,garmin_traces
from nightscout_charts import dataset_traces,hourly_figure
from test_nightscout import sample_data

class Health26Tests(unittest.TestCase):
    def test_percentage_weights_time_not_switch_count_and_excludes_unknown_hours(self):
        start=datetime(2026,9,16,tzinfo=timezone.utc)
        loaded=sample_data();loaded['zone']='UTC';loaded['loaded_at']=start+timedelta(days=2)
        def state(a,b,p):return dict(start=(start+timedelta(minutes=a)).isoformat(),end=(start+timedelta(minutes=b)).isoformat(),percentage=p)
        loaded['recorded_profiles']=[state(0,10,100),state(10,60,80),state(60,90,50),state(90,120,None),state(1440,1500,120)]
        stats=hourly_state_events(loaded,'profile_percentage',[start.date(),(start+timedelta(days=1)).date()])
        self.assertAlmostEqual(stats['values'][0][0],250/3)
        self.assertTrue(stats['complete'][0][0]);self.assertFalse(stats['complete'][0][1])
        self.assertEqual(stats['values'][0][1],50);self.assertIsNone(stats['average'][1])
        self.assertAlmostEqual(stats['average'][0],305/3)
        self.assertAlmostEqual(stats['median'][0],305/3)
        self.assertEqual(stats['contributing'][0],2)
        fig=hourly_figure(loaded,'profile_percentage',[start.date()],False)
        self.assertEqual(fig.layout.meta['dataset'],'profile_percentage')
        self.assertEqual(fig.data[0].meta['unit'],'%')

    def test_change_counts_require_explicit_types_and_available_treatments(self):
        loaded=sample_data();loaded['zone']='UTC'
        start=datetime(2026,9,16,tzinfo=timezone.utc);days=[start.date()]
        loaded['data']['changes']=pd.DataFrame([dict(time=start+timedelta(hours=10),value=1,label=label)
            for label in ['Site Change','Sensor Start','Sensor Change','Insulin Change']])
        for key,total in [('site_changes',1),('sensor_changes',2)]:
            stats=hourly_state_events(loaded,key,days);self.assertEqual(stats['values'][0][10],total)
            self.assertEqual(stats['values'][0][9],0)
            loaded['availability']={'treatments':False}
            self.assertIsNone(hourly_state_events(loaded,key,days)['values'][0][10])
            loaded['availability']={'treatments':True}

    def test_hourly_sleep_includes_zero_hours_within_recorded_dates(self):
        start=pd.Timestamp('2026-09-16T00:00Z');days=[date(2026,9,16),date(2026,9,17),date(2026,9,18)]
        frame=pd.DataFrame([dict(time=start+pd.Timedelta(hours=12),end=start+pd.Timedelta(hours=13),stage='light_sleep'),
                            dict(time=start+pd.Timedelta(hours=25),end=start+pd.Timedelta(hours=26),stage='deep_sleep')])
        stats,count=hourly_sleep_distribution(frame,days,'UTC')
        self.assertEqual(count,2)  # Entirely missing third date is not presumed awake.
        self.assertEqual(stats.loc[12,'light_sleep'],30)
        self.assertEqual(stats.loc[1,'deep_sleep'],30)
        self.assertEqual(stats.loc[0].sum(),0)
        self.assertEqual(stats.attrs['median'][12],30)
        traces=garmin_traces('g_sleep',dict(data={'g_sleep':frame},zone='UTC'),days,'Median + band')
        self.assertTrue(any(t.meta.get('sleep_variant')=='hourly' for t in traces))
        self.assertTrue(any(t.meta.get('sleep_variant')=='stages' for t in traces))

    def test_fixed_legends_do_not_inherit_dose_sizes(self):
        loaded=sample_data();loaded['_chart_cache']={};start=datetime(2026,9,16,tzinfo=timezone.utc)
        loaded['data']['bolus']=pd.DataFrame([dict(time=start+timedelta(minutes=i),value=value,label=label)
            for i,(value,label) in enumerate([(0.01,'SMB'),(10,'SMB'),(20,'User bolus')])])
        traces=dataset_traces('bolus',loaded,[start.date()],'One day','mmol/L',True)
        actual=[t for t in traces if not t.meta.get('legend_proxy')]
        proxies=[t for t in traces if t.meta.get('legend_proxy')]
        self.assertEqual({t.marker.size for t in proxies},{8})
        self.assertEqual({t.marker.symbol for t in proxies},{'triangle-up','square'})
        self.assertLessEqual(max(actual[0].marker.size),18)
        self.assertEqual(actual[0].customdata[1][1],10)
        self.assertFalse(actual[0].meta['legend_entry'])

    def test_profile_labels_and_event_button_feedback(self):
        code=(Path(__file__).parents[1]/'garmin_view.js').read_text()
        source=code[code.index('function eventAllowed'):code.index('function eventScopeControl')]+code[code.index('async function changeEventOption'):]
        context="""const assert=require('assert');
let ready=true,syncing=false,eventScopes={profiles:'off',percentage:'off'},dateCycled=false;
let card={},feedback=0,draws=0;function clearHover(){}function controls(){feedback++;}async function redrawLocal(){draws++;}
function enqueue(fn){return fn();}
const selectedDays=['2026-09-16'];const navigation={mode:'One day',profile_events:[
{name:'Standard',percentage:100,date:selectedDays[0],minute:0,intervals:[]},
{name:'Standard',percentage:80,date:selectedDays[0],minute:5,intervals:[]},
{name:'Drinking',percentage:90,date:selectedDays[0],minute:100,intervals:[]}]};
"""
        check="""(async()=>{await changeEventOption('profiles','all');assert.equal(eventScopes.profiles,'all');assert.equal(feedback,2);assert.equal(draws,1);assert(!syncing);
const view={layout:{shapes:[],annotations:[],meta:{}}};applyProfileEvents(view);applyProfileEvents(view);
assert.equal(view.layout.shapes.length,3);assert.equal(view.layout.annotations.length,6);
assert(view.layout.annotations.filter(a=>a.y>1).every(a=>/^\\d+%$/.test(a.text)));assert(view.layout.annotations.filter(a=>a.y<0).every(a=>['Standard','Drinking'].includes(a.text)));assert(view.data.every(t=>t.meta.kind==='profile_event'));
const legends=view.layout.shapes.filter(s=>s.showlegend);assert.equal(legends.length,2);
assert.notEqual(legends[0].line.dash,legends[1].line.dash);
})().catch(e=>{console.error(e);process.exit(1)});"""
        result=subprocess.run(['node','-e',context+source+check],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
