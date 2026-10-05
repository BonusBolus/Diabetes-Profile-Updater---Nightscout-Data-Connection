"""Shared Garmin controls, observed-data aggregates, gaps and layer migration."""
from datetime import date
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import unittest
from unittest.mock import patch

import pandas as pd
import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest
import test_garmin as fixtures
from garmin_data import load_garmin, merge_sources, SLEEP_OVERLAYS
from garmin_charts import garmin_traces, activity_shapes
from nightscout_charts import graph_figures, LAYERS, normalize_layers
from graph_view import prepared_graphs, viewer_html
from view_config import save_configuration, saved_configurations


class Health17Tests(unittest.TestCase):
    setUp=fixtures.GarminTests.setUp
    load=fixtures.GarminTests.load

    def enriched(self):
        with sqlite3.connect(self.folder/'garmin.db') as c:
            c.executescript("CREATE TABLE resting_hr(day DATETIME,resting_heart_rate FLOAT); INSERT INTO resting_hr VALUES ('2026-09-26',48); INSERT INTO stress VALUES ('2026-09-26 10:01:00',90),('2026-09-26 10:02:00',45);")
        with sqlite3.connect(self.folder/'garmin_monitoring.db') as c:
            c.executescript("CREATE TABLE monitoring_pulse_ox(timestamp DATETIME,pulse_ox FLOAT); INSERT INTO monitoring_pulse_ox VALUES ('2026-09-26 02:05:00',97),('2026-09-26 13:00:00',98); CREATE TABLE monitoring_rr(timestamp DATETIME,rr FLOAT); INSERT INTO monitoring_rr VALUES ('2026-09-26 02:05:00',14),('2026-09-26 13:00:00',18);")
        with sqlite3.connect(self.folder/'garmin_activities.db') as c:
            c.executescript("INSERT INTO activity_records VALUES ('2026-09-26 10:06:00',155,11),('2026-09-26 10:07:00',160,12),('2026-09-26 11:00:00',190,18);")
        result=merge_sources(None,self.load())
        result['data']['g_sleep_movement']=pd.DataFrame([dict(time=pd.Timestamp('2026-09-26T00:00Z'),end=pd.Timestamp('2026-09-26T00:10Z'),value=1.5,label='Movement')])
        result['data']['g_sleep_restless']=pd.DataFrame([dict(time=pd.Timestamp('2026-09-26T00:00Z'),value=1,label='Restless moment'),dict(time=pd.Timestamp('2026-09-26T00:05Z'),value=2,label='Restless moment')])
        return result

    def test_hrv_band_has_separate_valid_polygons(self):
        loaded=merge_sources(None,self.load());loaded['zone']='UTC'
        loaded['data']['g_hrv']=pd.DataFrame([dict(time=pd.Timestamp('2026-09-26T'+clock+'Z'),value=v,label='HRV') for clock,v in [('00:00',50),('00:05',55),('22:00',65),('22:05',70)]])
        traces=garmin_traces('g_hrv',loaded,[self.last],'Median + band')
        bands=[t for t in traces if t.meta['kind']=='garmin_band']
        self.assertEqual(len(bands),2)
        for band in bands:
            self.assertEqual(band.fill,'toself')
            self.assertLessEqual(max(band.x)-min(band.x),5)
        curve=next(t for t in traces if t.meta['kind']=='median')
        self.assertTrue(pd.isna(curve.y[120]))

    def test_aggregate_steps_uses_each_days_cumulative_curve(self):
        loaded=merge_sources(None,self.load());loaded['zone']='UTC'
        days=[date(2026,9,d) for d in (24,25,26)]
        loaded['data']['g_steps']=pd.DataFrame([dict(time=pd.Timestamp(t,tz='UTC'),value=v,label='Steps') for t,v in [
            ('2026-09-24 00:00',10),('2026-09-24 01:00',10),('2026-09-25 01:00',40),('2026-09-26 01:00',100)]])
        for mode in ('Median + band',):
            traces=garmin_traces('g_steps_cumulative',loaded,days,mode)
            median=next(t for t in traces if t.meta['kind']=='median')
            self.assertEqual(median.y[list(median.x).index(60)],40)
            self.assertEqual(median.customdata[0],1)
            bars=garmin_traces('g_steps',loaded,days,mode)
            self.assertTrue(all(t.type=='bar' for t in bars))
            self.assertEqual(next(t for t in bars if t.visible).meta['aggregation'],'Average')

    def test_sleep_fields_and_default_layer_order(self):
        loaded=self.enriched()
        self.assertEqual(loaded['data']['g_sleep_spo2'].value.tolist(),[97])
        self.assertEqual(loaded['data']['g_waking_rr'].value.tolist(),[18])
        self.assertEqual(loaded['data']['g_sleep_rhr'].value.tolist(),[48])
        self.assertIn('daily reference',loaded['data']['g_sleep_rhr'].label.iloc[0])
        profile=go.Figure();profile.update_layout(title='Health data')
        figures=graph_figures(profile,loaded,[self.last],'One day',list(LAYERS),'mmol/L',True)
        keys=[f.layout.meta.get('dataset') for f in figures[1:]]
        self.assertEqual([k for k in keys if k not in ('profile_percentage','site_changes','sensor_changes')][:10],['glucose','cob','iob','basal','target','variable_sens','g_steps','g_hr','g_workout_hr','g_workout_speed'])
        self.assertNotIn('g_activity',keys)
        sleep=next(f for f in figures if f.layout.meta.get('dataset')=='g_sleep')
        self.assertEqual(set(sleep.layout.meta['sleep_fields']),set(SLEEP_OVERLAYS.values()))
        self.assertTrue(all(t.visible is False for t in sleep.data if t.meta.get('sleep_overlay')))
        for fig in figures:
            if (fig.layout.meta or {}).get('dataset','').startswith('g_'):
                bands=[s for s in fig.layout.shapes if (s.name or '').startswith('Activity | ')]
                self.assertEqual((bands[0].x0,bands[0].x1),(600,640))
                self.assertEqual(bands[0].label.text,'Running')
        hr=next(f for f in figures if f.layout.meta.get('dataset')=='g_workout_hr')
        self.assertGreater(hr.layout.yaxis.range[0],140)
        self.assertEqual(activity_shapes(loaded,[self.last],'Median + band'),[])

    def test_saved_legacy_layers_and_smoothing_migrate(self):
        config=dict(format='profile-studio-view',version=1,layers=['Nightscout targets','Garmin · HRV','Garmin · SpO₂','Garmin · Activities'],mode='One day',viewer={'garmin':{'stressSmooth':True,'stressTau':17}})
        save_configuration('Legacy night',config,self.folder/'views')
        with patch('view_config.CONFIG_FOLDER',self.folder/'views'):
            app=AppTest.from_string("from view_config import configuration_controls\nconfiguration_controls()",default_timeout=20).run()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['ns_layers'],['Temporary Targets','Garmin · Sleep','Garmin · Activity'])
            opts=app.session_state['health_view_config']['garmin']
            self.assertEqual(opts['stressTau'],17)
            self.assertEqual(opts['sleepFields'],['g_sleep_hrv','g_sleep_spo2'])

    def test_external_javascript_is_decoded_as_utf8(self):
        original=Path.read_text
        def windows_read(path,*args,**kwargs):
            # Reproduce default CP1252 on Windows; code must explicitly opt into UTF-8.
            if path.suffix=='.js' and not kwargs.get('encoding'):
                return path.read_bytes().decode('cp1252',errors='replace')
            return original(path,*args,**kwargs)
        with patch.object(Path,'read_text',windows_read):
            fig=go.Figure();fig.update_layout(title='Test')
            html=viewer_html([fig],True)
        self.assertIn('Low-pass',html)
        self.assertNotIn('Â',html)
        self.assertNotIn('â€',html)

    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_live_controls_all_modes_and_configuration_restore(self):
        loaded=self.enriched();profile=go.Figure();profile.update_layout(title='Health data')
        loaded['data']['g_steps']=pd.concat([loaded['data']['g_steps'],pd.DataFrame([
            dict(time=pd.Timestamp('2026-09-25T08:05Z'),value=100,label='Steps')])],ignore_index=True)
        paths=[]
        for mode in ('One day','Multiple days','Median + band'):
            view=dict(loaded=loaded,days=[self.last] if mode=='One day' else [self.first,self.last],mode=mode,layers=[label for label in LAYERS if label.startswith('Garmin')]+['Custom graph'],data_only=True)
            figs,nav=prepared_graphs(profile,view,'mmol/L',True)
            html=viewer_html(figs,True,nav)
            path=self.folder/('viewer'+str(len(paths))+'.js');path.write_text(html.split('<script>')[-1].split('</script>')[0],encoding='utf-8');paths.append(str(path))
        result=subprocess.run(['node',str(Path(__file__).with_name('health17_viewer_checks.cjs')),*paths,str(self.folder/'rendered.json')],capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        for fig in json.loads((self.folder/'rendered.json').read_text()):go.Figure(fig)

if __name__=='__main__':unittest.main()
