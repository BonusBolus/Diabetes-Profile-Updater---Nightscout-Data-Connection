"""Open graph controls, sidebar custom panels, steps views, and precise hover."""
from pathlib import Path
import json
import shutil
import subprocess
import unittest
import pandas as pd
import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest
import test_garmin as fixtures
import test_health17
from garmin_charts import garmin_traces
from graph_view import prepared_graphs, viewer_html
from nightscout_charts import normalize_layers


class Health21Tests(unittest.TestCase):
    setUp=fixtures.GarminTests.setUp
    load=fixtures.GarminTests.load
    enriched=test_health17.Health17Tests.enriched

    def test_custom_layers_add_hide_delete_and_restore(self):
        app=AppTest.from_string('''
import streamlit as st
from nightscout_ui import custom_layer_controls
from view_config import apply_configuration
st.session_state.setdefault('ns_layers',['Garmin · Steps'])
st.session_state.setdefault('ns_layers_garmin',['Garmin · Steps'])
custom_layer_controls()
''').run()
        for _ in range(2):app.button(key='add_custom_layer').click().run()
        self.assertFalse(app.exception,[e.value for e in app.exception])
        self.assertEqual(app.session_state.health_custom_catalog,['custom-1','custom-2'])
        self.assertEqual(app.session_state.health_custom_visible,['custom-1','custom-2'])
        app.checkbox(key='show_custom-1').uncheck().run()
        self.assertEqual(app.session_state.health_custom_visible,['custom-2'])
        app.button(key='delete_custom-2').click().run()
        self.assertNotIn('Custom graph',app.session_state.ns_layers)
        app.button(key='add_custom_layer').click().run()
        self.assertEqual(app.session_state.health_custom_visible,['custom-3'])
        self.assertEqual(app.session_state.ns_layers,['Garmin · Steps','Custom graph'])
        self.assertFalse(app.exception)

    def test_steps_layer_alias_and_per_day_cumulative(self):
        self.assertEqual(normalize_layers(['Garmin · Steps','Garmin · Cumulative steps']),['Garmin · Steps'])
        loaded=self.enriched()
        loaded['data']['g_steps']=pd.DataFrame([
            dict(time=pd.Timestamp('2026-09-25T08:00Z'),value=10),dict(time=pd.Timestamp('2026-09-25T09:00Z'),value=20),
            dict(time=pd.Timestamp('2026-09-26T08:00Z'),value=100),dict(time=pd.Timestamp('2026-09-26T09:00Z'),value=200)])
        traces=garmin_traces('g_steps_cumulative',loaded,[self.first,self.last],'Multiple days')
        self.assertEqual(len(traces),2)
        self.assertEqual([t.y[-1] for t in traces],[30,300])
        self.assertNotEqual(traces[0].line.dash,traces[1].line.dash)
        self.assertTrue(all(t.meta['date'] for t in traces))

    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_control_layout_slider_stability_sidebar_restore_and_hover(self):
        loaded=self.enriched()
        loaded['data']['g_steps']=pd.concat([loaded['data']['g_steps'],pd.DataFrame([dict(time=pd.Timestamp('2026-09-25T08:00Z'),value=100,label='Steps')])],ignore_index=True)
        profile=go.Figure();profile.update_layout(title='Health data')
        paths=[]
        for mode in ('One day','Multiple days','Median + band'):
            view=dict(loaded=loaded,days=[self.last] if mode=='One day' else [self.first,self.last],mode=mode,
                      layers=['Garmin · Steps','Garmin · Activity','Garmin · Sleep','Custom graph'],data_only=True,
                      custom_ids=['custom-1','custom-2'],custom_catalog=['custom-1','custom-2'])
            figures,nav=prepared_graphs(profile,view,'mmol/L',True)
            path=self.folder/f'{len(paths)}.js';path.write_text(viewer_html(figures,True,nav).split('<script>')[-1].split('</script>')[0],encoding='utf-8');paths.append(str(path))
        target=self.folder/'plots.json'
        result=subprocess.run(['node',str(Path(__file__).with_name('health21_viewer_checks.cjs')),*paths,str(target)],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        for figure in json.loads(target.read_text()):go.Figure(figure)

if __name__=='__main__':unittest.main()
