"""Activity controls, shared overlays and one-shot source refresh."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch
import pandas as pd
import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest
import test_garmin as fixtures
import test_health17
from garmin_data import merge_sources, METRICS
from garmin_charts import activity_color, activity_shapes
from garmin_exports import activity_label
from nightscout import NightscoutError
from nightscout_charts import graph_figures, normalize_layers
from graph_view import prepared_graphs, viewer_html

class Health19Tests(unittest.TestCase):
    setUp=fixtures.GarminTests.setUp
    load=fixtures.GarminTests.load
    enriched=test_health17.Health17Tests.enriched

    def test_activity_colors_classification_and_order(self):
        expected={'walking':'#9ccc65','running':'#f16a43','mountain biking':'#a96c32','cycling':'#42a5f5','squash':'#ab6bd5'}
        for sport,color in expected.items():self.assertEqual(activity_color(sport),color)
        self.assertEqual(activity_label('cycling','mountain'),'mountain biking')
        self.assertEqual(activity_color('mountain_cycling'),expected['mountain biking'])
        self.assertEqual(activity_color('biking'),expected['cycling'])
        self.assertEqual(activity_label(None,None,'squash'),'squash')
        self.assertIn('unavailable',activity_label(None))
        loaded=merge_sources(None,self.load());bands=activity_shapes(loaded,[self.last],'One day')
        self.assertTrue(bands[0]['fillcolor'].endswith(',0.055)'))
        fig=go.Figure();fig.update_layout(title='Health data')
        figures=graph_figures(fig,loaded,[self.last],'One day',['Garmin · Workout'],'mmol/L',True)
        self.assertEqual([f.layout.meta['dataset'] for f in figures[1:]],['g_workout_hr','g_workout_speed','g_workout_altitude','g_workout_power','g_workout_cadence'])
        self.assertTrue(all(f.layout.title.text.startswith('Activity ') for f in figures[1:]))
        self.assertEqual(normalize_layers(['Garmin · Workout','Garmin · Activities','Garmin · Workout speed']),['Garmin · Activity'])

    def app(self):
        return AppTest.from_string("from nightscout_ui import sidebar_controls\nsidebar_controls('Europe/Amsterdam')",default_timeout=30).run()

    def configure(self,app):
        app.text_input(key='ns_url').set_value('https://example.invalid')
        app.text_input(key='ns_token').set_value('private-test-token')
        app.text_input(key='garmin_folder').set_value(str(self.folder))
        app.date_input(key='ns_from').set_value(self.first)
        app.date_input(key='ns_until').set_value(self.last)

    def test_refresh_all_reads_both_sources_once_and_keeps_selected_date(self):
        garmin=self.load();ns=merge_sources(None,garmin)
        with patch('nightscout_ui.load_nightscout',return_value=ns) as ns_read,patch('garmin_ui.load_garmin',return_value=garmin) as garmin_read:
            app=self.app();self.configure(app);app.run()
            self.assertEqual(ns_read.call_count,0);self.assertEqual(garmin_read.call_count,0)
            app.session_state.ns_day=self.first
            app.button(key='health_refresh_all').click().run()
            self.assertFalse(app.exception,[e.value for e in app.exception])
            ns_read.assert_called_once_with('https://example.invalid','private-test-token',self.first,self.last,'Europe/Amsterdam')
            garmin_read.assert_called_once_with(str(self.folder),self.first,self.last,'Europe/Amsterdam','Europe/Amsterdam','Metric')
            self.assertEqual(app.session_state.ns_day,self.first)
            app.run();self.assertEqual(ns_read.call_count,1);self.assertEqual(garmin_read.call_count,1)
            self.assertEqual(app.session_state.garmin_loaded['loaded_at'],garmin['loaded_at'])

    def test_refresh_all_still_reads_garmin_when_nightscout_fails(self):
        with patch('nightscout_ui.load_nightscout',side_effect=NightscoutError('Test connection failure')) as ns_read,patch('garmin_ui.load_garmin',return_value=self.load()) as garmin_read:
            app=self.app();self.configure(app);app.button(key='health_refresh_all').click().run()
            self.assertFalse(app.exception);self.assertEqual(ns_read.call_count,1);self.assertEqual(garmin_read.call_count,1)
            self.assertTrue(any('Test connection failure' in e.value for e in app.error))

    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_graph_controls_all_modes_and_saved_options(self):
        loaded=self.enriched()
        moments=[0,5/60,1,1+5/60,2,8,8+5/60]
        for key,values in {'g_workout_hr':[40,150,160,170,180,80,130],
                           'g_workout_speed':[0,8,10,12,14,0,9],
                           'g_workout_cadence':[10,160,165,170,180,0,150],
                           'g_workout_power':[0,200,250,300,350,0,180],
                           'g_workout_altitude':[30,30.5,32,34,35,40,42]}.items():
            loaded['data'][key]=pd.DataFrame([dict(time=pd.Timestamp('2026-09-26T08:00Z')+pd.Timedelta(minutes=m),value=v,label=METRICS[key][0]) for m,v in zip(moments,values)])
        loaded['data']['glucose']=pd.DataFrame([dict(time=pd.Timestamp('2026-09-26T08:00Z'),value=6,label='Glucose')])
        fig=go.Figure();fig.update_layout(title='Health data')
        paths=[]
        for mode in ('One day','Multiple days','Median + band'):
            view=dict(loaded=loaded,days=[self.last] if mode=='One day' else [self.first,self.last],mode=mode,
                      layers=['Glucose','Garmin · Activity','Garmin · Sleep','Garmin · Stress','Custom graph'],data_only=True)
            figures,nav=prepared_graphs(fig,view,'mmol/L',True)
            path=self.folder/f'viewer{len(paths)}.js';path.write_text(viewer_html(figures,True,nav).split('<script>')[-1].split('</script>')[0],encoding='utf-8');paths.append(str(path))
        target=self.folder/'rendered.json'
        result=subprocess.run(['node',str(Path(__file__).with_name('health19_viewer_checks.cjs')),*paths,str(target)],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        for figure in json.loads(target.read_text()):go.Figure(figure)

if __name__=='__main__':unittest.main()
