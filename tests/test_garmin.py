from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import shutil
from unittest.mock import patch
import tempfile
import unittest

import pandas as pd
import plotly.graph_objects as go
from garmin_data import load_garmin, merge_sources
from garmin_charts import garmin_traces, sleep_probabilities
from graph_view import prepared_graphs, viewer_html
from streamlit.testing.v1 import AppTest


class GarminTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.first=date(2026,9,25);self.last=date(2026,9,26)
        with sqlite3.connect(self.folder/'garmin.db') as c:
            c.executescript('''
CREATE TABLE sleep (day DATETIME, start DATETIME, end DATETIME, total_sleep TIME, score INTEGER);
INSERT INTO sleep VALUES ('2026-09-26','2026-09-25 23:00:00','2026-09-26 07:00:00','08:00:00',82);
CREATE TABLE sleep_events (timestamp DATETIME, event TEXT, duration TIME);
INSERT INTO sleep_events VALUES ('2026-09-25 23:00:00','light_sleep','02:00:00');
INSERT INTO sleep_events VALUES ('2026-09-26 02:00:00','deep_sleep','01:00:00');
INSERT INTO sleep_events VALUES ('2026-09-26 03:00:00','rem_sleep','00:30:00');
CREATE TABLE stress(timestamp DATETIME, stress INTEGER);
INSERT INTO stress VALUES ('2026-09-26 10:00:00',25),('2026-09-26 10:05:00',-1);
CREATE TABLE daily_summary(day DATETIME,steps INTEGER,bb_max INTEGER);
INSERT INTO daily_summary VALUES ('2026-09-26',9000,80);
CREATE TABLE hrv(day DATETIME,last_night_avg FLOAT);
INSERT INTO hrv VALUES ('2026-09-26',48);
''')
        with sqlite3.connect(self.folder/'garmin_monitoring.db') as c:
            c.executescript('''
CREATE TABLE monitoring_hr(timestamp DATETIME,heart_rate INTEGER);
INSERT INTO monitoring_hr VALUES ('2026-09-26 10:00:00',70),('2026-09-26 10:01:00',72),('2026-09-26 11:00:00',0),('2026-09-26 12:00:00',75);
CREATE TABLE monitoring(timestamp DATETIME,activity_type TEXT,steps INTEGER);
INSERT INTO monitoring VALUES ('2026-09-26 10:00:00','walking',100),('2026-09-26 10:05:00','walking',120),('2026-09-26 10:10:00','walking',155),('2026-09-26 10:15:00','walking',2),('2026-09-26 12:00:00','walking',300);
CREATE TABLE monitoring_hrv_value(timestamp DATETIME,hrv FLOAT);
INSERT INTO monitoring_hrv_value VALUES ('2026-09-26 02:00:00',55);
''')
        with sqlite3.connect(self.folder/'garmin_activities.db') as c:
            c.executescript('''
CREATE TABLE activities(start_time DATETIME,stop_time DATETIME,sport TEXT,avg_hr FLOAT,calories INTEGER,start_lat FLOAT);
INSERT INTO activities VALUES ('2026-09-26 10:00:00','2026-09-26 10:40:00','running',145,NULL,52.1);
CREATE TABLE activity_records(timestamp DATETIME,hr INTEGER,speed FLOAT);
INSERT INTO activity_records VALUES ('2026-09-26 10:05:00',150,10);
''')

    def load(self):return load_garmin(str(self.folder),self.first,self.last,'Europe/Amsterdam','Europe/Amsterdam')

    def test_readonly_fields_units_and_counter_differences(self):
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.folder.glob('*.db')}
        loaded=self.load()
        self.assertEqual(loaded['data']['g_hr'].iloc[0].time.hour,8)
        self.assertEqual(loaded['data']['g_steps'].value.sum(),55)
        self.assertEqual(loaded['data']['g_stress'].value.tolist(),[25])
        self.assertEqual(len(loaded['data']['g_hr']),3)
        self.assertTrue(any(r['field']=='sleep · total sleep' and r['value']==8 for r in loaded['daily']))
        self.assertNotIn('start_lat',loaded['activities'][0])
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.folder.glob('*.db')})

    def test_sleep_cross_midnight_gaps_and_partial_session(self):
        loaded=merge_sources(None,self.load())
        traces=garmin_traces('g_sleep',loaded,[self.last],'One day')
        light=next(t for t in traces if t.name=='Light sleep')
        self.assertEqual(list(light.x),[0,60,None])
        self.assertFalse(any('unavailable' in t.name for t in traces))
        stats,counts=sleep_probabilities(loaded['data']['g_sleep'],[self.last],loaded['zone'])
        self.assertTrue(stats.loc[90].isna().all())
        self.assertEqual(stats.loc[125,'deep_sleep'],100)
        self.assertEqual(counts[125],1)
        # Fetch only the second day: retain the interval beginning the previous night.
        second=load_garmin(str(self.folder),self.last,self.last,'Europe/Amsterdam','Europe/Amsterdam')
        self.assertEqual(len(second['data']['g_sleep']),3)

    def test_session_fallback_and_missing_schema(self):
        with sqlite3.connect(self.folder/'garmin.db') as c:c.execute('DROP TABLE sleep_events')
        loaded=self.load()
        self.assertEqual(loaded['data']['g_sleep'].stage.tolist(),['unknown'])
        self.assertEqual(len(garmin_traces('g_sleep',merge_sources(None,loaded),[self.last],'Median + band')),0)

    def test_viewer_garmin_only_and_custom_all_modes(self):
        loaded=merge_sources(None,self.load());profile=go.Figure(go.Scatter(x=[0,1440],y=[1,1],meta={'kind':'profile','unit':'U/h','label':'Basal'}))
        profile.update_layout(title='Basal',yaxis_title='U/h')
        for mode in ['One day','Multiple days','Median + band']:
            view=dict(loaded=loaded,days=[self.last],mode=mode,layers=['Garmin · Heart rate','Garmin · Sleep','Garmin · Activities','Custom graph'])
            figs,nav=prepared_graphs(profile,view,'mmol/L',True)
            json.dumps(nav,allow_nan=False)
            self.assertEqual(len(figs),9)
            self.assertIn('Garmin · Sleep',nav['overlays'])
            self.assertTrue(any(f['id']=='garmin:g_sleep' for f in nav['custom']['fields']))
            self.assertTrue(nav['garmin_daily'])
            html=viewer_html(figs,True,nav)
            self.assertIn('garminAxes(view)',html)
            self.assertNotIn(str(self.folder),html)

    def test_streamlit_local_load_without_nightscout(self):
        code="""from nightscout_ui import sidebar_controls
view=sidebar_controls('Europe/Amsterdam')
"""
        at=AppTest.from_string(code,default_timeout=30).run()
        at.text_input(key='garmin_folder').set_value(str(self.folder))
        at.date_input(key='ns_from').set_value(self.first)
        at.date_input(key='ns_until').set_value(self.last)
        next(b for b in at.button if b.label=='Load / refresh Garmin data').click().run()
        self.assertFalse(at.exception,[e.value for e in at.exception])
        self.assertIn('Sleep',at.button_group(key='ns_layers_garmin').options)
        at.button_group(key='ns_layers_garmin').set_value(['Garmin · Sleep']).run()
        self.assertFalse(at.exception)

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_expanded_sleep_and_custom_navigation(self):
        loaded=merge_sources(None,self.load());profile=go.Figure(go.Scatter(x=[0,1440],y=[1,1]))
        profile.update_layout(title='Basal',yaxis_title='U/h')
        view=dict(loaded=loaded,days=[self.first],mode='Median + band',layers=['Garmin · Heart rate','Garmin · Sleep','Garmin · Activities','Custom graph'])
        figures,nav=prepared_graphs(profile,view,'mmol/L',True)
        html=viewer_html(figures,True,nav)
        script=self.folder/'viewer.js';script.write_text(html.split('<script>')[-1].split('</script>')[0])
        target=self.folder/'rendered.json'
        result=subprocess.run(['node',str(Path(__file__).with_name('garmin_viewer_checks.cjs')),str(script),str(target)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        for figure in json.loads(target.read_text()):go.Figure(figure)

    def test_data_only_workspace_without_profiles(self):
        with patch.dict('os.environ',{'PROFILE_STUDIO_DATA':str(self.folder)}):
            at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
            at.radio(key='page').set_value('Data').run()
            self.assertFalse(at.exception,[e.value for e in at.exception])
            self.assertFalse(any(x.key=='reference_category' for x in at.selectbox))
            at.text_input(key='garmin_folder').set_value(str(self.folder))
            at.date_input(key='ns_from').set_value(self.first)
            at.date_input(key='ns_until').set_value(self.last)
            next(b for b in at.button if b.label=='Load / refresh Garmin data').click().run()
            self.assertFalse(at.exception,[e.value for e in at.exception])
            self.assertTrue(any(t.value=='Health data' for t in at.title))
            self.assertFalse(at.tabs)

    def test_data_only_expanded_navigation(self):
        if not shutil.which('node'):self.skipTest('Node required')
        loaded=merge_sources(None,self.load());profile=go.Figure();profile.update_layout(title='Health data',yaxis_title='')
        view=dict(loaded=loaded,days=[self.first],mode='One day',layers=['Garmin · Heart rate','Garmin · Sleep','Garmin · Activities','Custom graph'],data_only=True)
        figures,nav=prepared_graphs(profile,view,'mmol/L',True)
        self.assertEqual(set(nav['overlays']),{'None'})
        self.assertFalse(nav['profiles'])
        html=viewer_html(figures,True,nav)
        script=self.folder/'data-viewer.js';script.write_text(html.split('<script>')[-1].split('</script>')[0])
        result=subprocess.run(['node',str(Path(__file__).with_name('data_viewer_checks.cjs')),str(script)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)

    def test_ambiguous_dst_is_not_silently_shifted(self):
        with sqlite3.connect(self.folder/'garmin_monitoring.db') as c:
            c.execute("INSERT INTO monitoring_hr VALUES ('2026-10-25 02:15:00',90)")
        result=load_garmin(str(self.folder),date(2026,10,25),date(2026,10,25),'Europe/Amsterdam','Europe/Amsterdam')
        self.assertNotIn('g_hr',result['data'])
        self.assertTrue(any('ambiguous' in w for w in result['warnings']))

if __name__=='__main__':unittest.main()
