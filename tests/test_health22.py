"""Atomic source submissions and global graph layout/state regressions."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch
import pandas as pd
import plotly.graph_objects as go
import test_health19
from nightscout import NightscoutError
from garmin_data import merge_sources
from graph_view import prepared_graphs, viewer_html


class Health22Tests(unittest.TestCase):
    setUp=test_health19.Health19Tests.setUp
    load=test_health19.Health19Tests.load
    enriched=test_health19.Health19Tests.enriched
    app=test_health19.Health19Tests.app
    configure=test_health19.Health19Tests.configure

    def test_one_submit_reads_current_fields_once(self):
        snapshot=merge_sources(None,self.load())
        with patch('nightscout_ui.load_nightscout',return_value=snapshot) as read:
            app=self.app()
            self.configure(app)
            # No intermediate rerun: one submit commits every input in the form.
            app.button(key='ns_refresh').click().run()
            self.assertFalse(app.exception,[e.value for e in app.exception])
            read.assert_called_once_with('https://example.invalid','private-test-token',self.first,self.last,'Europe/Amsterdam')
            self.assertEqual(app.session_state.ns_loaded['loaded_at'],snapshot['loaded_at'])
            app.run()
            self.assertEqual(read.call_count,1,'Unrelated reruns must not refresh data')

    def test_failed_refresh_preserves_successful_snapshots(self):
        garmin=self.load();snapshot=merge_sources(None,garmin)
        with patch('nightscout_ui.load_nightscout',return_value=snapshot) as ns,patch('garmin_ui.load_garmin',return_value=garmin) as gr:
            app=self.app();self.configure(app)
            app.button(key='health_refresh_all').click().run()
            self.assertFalse(app.exception)
            ns.side_effect=NightscoutError('Test rejected request')
            gr.side_effect=ValueError('Test unavailable folder')
            app.button(key='health_refresh_all').click().run()
            self.assertFalse(app.exception,[e.value for e in app.exception])
            self.assertEqual(app.session_state.ns_loaded['loaded_at'],snapshot['loaded_at'])
            self.assertEqual(app.session_state.garmin_loaded['loaded_at'],garmin['loaded_at'])
            self.assertTrue(any('Nightscout load failed' in e.value for e in app.error))
            self.assertTrue(any('Previously loaded Nightscout' in e.value for e in app.caption))
            self.assertEqual(ns.call_count,2);self.assertEqual(gr.call_count,2)
            app.run();self.assertEqual(ns.call_count,2);self.assertEqual(gr.call_count,2)

    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_global_shading_fit_preserves_modes_and_axis_rail(self):
        loaded=self.enriched()
        loaded['data']['glucose']=pd.DataFrame([
            dict(time=pd.Timestamp('2026-09-25T08:00Z'),value=5,label='Glucose'),
            dict(time=pd.Timestamp('2026-09-26T08:00Z'),value=9,label='Glucose')])
        profile=go.Figure(go.Scatter(x=[0,1440],y=[10,10],meta=dict(kind='profile'),name='Standard v17'))
        profile.update_layout(title='I:C',xaxis=dict(range=[0,1440]),yaxis=dict(title='g/U'))
        paths=[]
        for mode in ('One day','Multiple days','Median + band'):
            view=dict(loaded=loaded,days=[self.last] if mode=='One day' else [self.first,self.last],mode=mode,
                      layers=['Glucose','COB + Carbs','IOB + Boluses','Garmin · Steps','Garmin · Activity','Garmin · Sleep','Custom graph'])
            figures,nav=prepared_graphs(profile,view,'mmol/L',True)
            path=self.folder/f'viewer{len(paths)}.js'
            path.write_text(viewer_html(figures,True,nav).split('<script>')[-1].split('</script>')[0],encoding='utf-8');paths.append(str(path))
        target=self.folder/'rendered.json'
        result=subprocess.run(['node',str(Path(__file__).with_name('health22_viewer_checks.cjs')),*paths,str(target)],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        for figure in json.loads(target.read_text()):go.Figure(figure)

if __name__=='__main__':unittest.main()
