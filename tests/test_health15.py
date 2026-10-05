"""Cross-source availability and portable configuration regressions."""
from datetime import date
import json
import sqlite3
import shutil
import subprocess
from pathlib import Path
import unittest
import pandas as pd
import plotly.graph_objects as go
import test_garmin as fixtures
from garmin_data import merge_sources, load_garmin
from garmin_charts import garmin_traces, activity_shapes
from nightscout_stats import hourly_events
from nightscout_charts import graph_figures, dataset_traces
from date_controls import loaded_days
from view_config import parse_configuration
from graph_view import prepared_graphs, viewer_html


class Health15Tests(unittest.TestCase):
    setUp=fixtures.GarminTests.setUp
    load=fixtures.GarminTests.load

    def test_union_dates_does_not_create_zero_treatment_days(self):
        garmin=self.load()
        ns=merge_sources(None,garmin)
        ns.update(first=self.first,last=self.first,availability={'treatments':True})
        combined=merge_sources(ns,garmin)
        self.assertEqual(loaded_days(combined),[self.first,self.last])
        stats=hourly_events(combined,'bolus',[self.first,self.last])
        self.assertEqual(stats['values'][0],[0.]*24)
        self.assertEqual(stats['values'][1],[None]*24)
        self.assertEqual(stats['contributing'],[1]*24)

    def test_sleep_respiration_and_power_only_when_recorded(self):
        with sqlite3.connect(self.folder/'garmin_monitoring.db') as c:
            c.executescript("CREATE TABLE monitoring_rr(timestamp DATETIME,rr FLOAT); INSERT INTO monitoring_rr VALUES ('2026-09-26 02:05:00',14),('2026-09-26 01:30:00',15),('2026-09-26 13:00:00',18);")
        result=self.load()
        self.assertEqual(result['data']['g_sleep_rr'].value.tolist(),[14])
        self.assertNotIn('g_workout_power',result['data'])
        with sqlite3.connect(self.folder/'garmin_activities.db') as c:
            c.executescript('ALTER TABLE activity_records ADD COLUMN power FLOAT; UPDATE activity_records SET power=250;')
        self.assertEqual(self.load()['data']['g_workout_power'].value.tolist(),[250])

    def test_cumulative_steps_gaps_and_median(self):
        loaded=merge_sources(None,self.load())
        for mode in ('One day','Median + band'):
            traces=garmin_traces('g_steps_cumulative',loaded,[self.last],mode)
            line=next(t for t in traces if t.meta.get('variant')=='cumulative')
            self.assertEqual(sorted(set(v for v in line.y if pd.notna(v))),[20.,55.])
            self.assertIsNot(line.visible,False)

    def test_activity_shading_and_compact_workout_panels(self):
        loaded=merge_sources(None,self.load());shapes=activity_shapes(loaded,[self.last],'One day')
        self.assertEqual((shapes[0]['x0'],shapes[0]['x1']),(600,640))
        self.assertIn('running',shapes[0]['name'].casefold())
        self.assertFalse(activity_shapes(loaded,[self.last],'Median + band'))
        profile=go.Figure();profile.update_layout(title='Health data')
        figs=graph_figures(profile,loaded,[self.last],'One day',['Garmin · Workout'],'mmol/L',True)
        self.assertEqual(len(figs),6) # hidden controller + 5 workout measurements
        power=next(f for f in figs if f.layout.meta.get('dataset')=='g_workout_power')
        self.assertIn('No recorded',power.layout.annotations[0].text)

    def test_smb_alternates_without_altering_dose_or_time(self):
        loaded=merge_sources(None,self.load())
        loaded['data']['bolus']=pd.DataFrame([dict(time=pd.Timestamp(f'2026-09-26 08:0{i}:00Z'),value=v,label='SMB') for i,v in enumerate([.05,.2,.5])])
        trace=dataset_traces('bolus',loaded,[self.last],'One day','mmol/L',True)[0]
        self.assertEqual(list(trace.marker.angle),[0,-180,0])
        self.assertEqual(list(trace.y),[0,0,0])
        self.assertEqual([v[1] for v in trace.customdata],[.05,.2,.5])
        self.assertAlmostEqual((trace.marker.size[2]/trace.marker.size[0])**2,10)

    def test_configuration_validation(self):
        source=dict(format='profile-studio-view',version=1,layers=['Garmin · Heart rate','Custom graph'],mode='One day',viewer={'custom':['garmin:g_hr'],'order':['g_hr'],'garmin':{'pace':True}},token='not-exported')
        parsed=parse_configuration(json.dumps(source))
        self.assertNotIn('token',parsed)
        self.assertEqual(parsed['viewer'],source['viewer'])
        with self.assertRaises(ValueError):parse_configuration('{"version": 99}')
        with self.assertRaises(ValueError):parse_configuration('x'*200_001)

    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_browser_controls_and_date_persistence(self):
        with sqlite3.connect(self.folder/'garmin.db') as c:
            c.executescript("INSERT INTO stress VALUES ('2026-09-25 10:00:00',20),('2026-09-25 10:01:00',60),('2026-09-25 10:10:00',90);")
        loaded=merge_sources(None,load_garmin(str(self.folder),self.first,self.last,'Europe/Amsterdam','Europe/Amsterdam','Metric'))
        profile=go.Figure();profile.update_layout(title='Health data',yaxis_title='')
        layers=['Garmin · Heart rate','Garmin · Stress','Garmin · Steps','Garmin · Cumulative steps','Garmin · Sleep','Garmin · Workout','Custom graph']
        paths=[]
        for i in range(3):
            view=dict(loaded=loaded,days=[self.last],mode='One day',layers=layers+(['Garmin · HRV'] if i else []),data_only=True)
            figures,nav=prepared_graphs(profile,view,'mmol/L',True)
            nav=dict(nav,state_scope='health15-regression',date_revision=1 if i==2 else 0)
            html=viewer_html(figures,True,nav)
            path=self.folder/f'viewer{i}.js';path.write_text(html.split('<script>')[-1].split('</script>')[0]);paths.append(str(path))
        target=self.folder/'rendered.json'
        result=subprocess.run(['node',str(Path(__file__).with_name('health15_viewer_checks.cjs')),*paths,str(target)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        for figure in json.loads(target.read_text()):go.Figure(figure)


if __name__=='__main__':unittest.main()
