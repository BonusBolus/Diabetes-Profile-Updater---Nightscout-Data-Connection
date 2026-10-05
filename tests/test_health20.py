"""Independent cumulative statistics and dynamic custom graph lifecycle."""
from datetime import date
import json
from pathlib import Path
import shutil
import subprocess
import unittest
import pandas as pd
import plotly.graph_objects as go
import test_garmin as fixtures
import test_health17
from garmin_data import merge_sources, METRICS
from garmin_charts import garmin_traces, activity_shapes, activity_color
from garmin_exports import activity_label
from graph_view import prepared_graphs, viewer_html

class Health20Tests(unittest.TestCase):
    setUp=fixtures.GarminTests.setUp
    load=fixtures.GarminTests.load
    enriched=test_health17.Health17Tests.enriched

    def test_median_of_cumulative_curves_is_not_sum_of_median_bars(self):
        loaded=merge_sources(None,self.load());loaded['zone']='UTC'
        days=[date(2026,9,d) for d in (24,25,26)]
        loaded['data']['g_steps']=pd.DataFrame([dict(time=pd.Timestamp(day,tz='UTC')+pd.Timedelta(hours=h),value=v)
            for day,values in zip(days,[(0,10),(10,0),(10,10)]) for h,v in enumerate(values)])
        for mode in ('Median + band',):
            bars=garmin_traces('g_steps',loaded,days,mode)
            increments=next(t for t in bars if t.meta['aggregation']=='Median')
            self.assertEqual(sum(increments.y[:2]),20)
            curves=garmin_traces('g_steps_cumulative',loaded,days,mode)
            median=next(t for t in curves if t.name=='Median');band=next(t for t in curves if t.name=='25–75%')
            self.assertEqual(median.y[list(median.x).index(60)],10)
            self.assertEqual({y for x,y in zip(band.x,band.y) if x==65},{10,15})
            self.assertTrue(band.showlegend);self.assertNotIn('aggregation',median.meta)
            self.assertTrue(all(t.type=='bar' for t in bars))

    def test_unconfigured_sport_keeps_name_interval_and_neutral_color(self):
        loaded=merge_sources(None,self.load());rows=loaded['data']['g_activity'].copy()
        rows['label']=activity_label('rowing');loaded['data']['g_activity']=rows
        bands=activity_shapes(loaded,[self.last],'One day')
        self.assertEqual(bands[0]['label']['text'],'Rowing')
        self.assertEqual((bands[0]['x0'],bands[0]['x1']),(600,640))
        self.assertEqual(activity_color('rowing'),'#90a4ae')
        self.assertEqual(activity_color('new sport'),'#90a4ae')
        self.assertNotEqual(activity_color('cycling'),activity_color('rowing'))

    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_multiple_custom_panels_controls_and_restore(self):
        loaded=self.enriched()
        moments=[0,5/60,10/60,20/60]
        for key,values in {'g_workout_hr':[40,150,160,170],'g_workout_speed':[8,10,12,14],
                           'g_workout_cadence':[100,160,165,170],'g_workout_power':[100,200,250,300],
                           'g_workout_altitude':[30,31,33,35]}.items():
            loaded['data'][key]=pd.DataFrame([dict(time=pd.Timestamp('2026-09-26T08:00Z')+pd.Timedelta(minutes=m),value=v,label=METRICS[key][0]) for m,v in zip(moments,values)])
        loaded['data']['g_steps']=pd.concat([loaded['data']['g_steps'],pd.DataFrame([dict(time=pd.Timestamp('2026-09-25T08:00Z'),value=100,label='Steps')])],ignore_index=True)
        loaded['data']['glucose']=pd.DataFrame([dict(time=pd.Timestamp('2026-09-26T08:00Z'),value=6,label='Glucose')])
        fig=go.Figure();fig.update_layout(title='Health data')
        paths=[]
        for mode in ('One day','Multiple days','Median + band'):
            view=dict(loaded=loaded,days=[self.last] if mode=='One day' else [self.first,self.last],mode=mode,
                      layers=['Glucose','Garmin · Activity','Garmin · Sleep','Garmin · Steps','Garmin · Cumulative steps','Custom graph'],data_only=True)
            figures,nav=prepared_graphs(fig,view,'mmol/L',True)
            path=self.folder/f'viewer{len(paths)}.js';path.write_text(viewer_html(figures,True,nav).split('<script>')[-1].split('</script>')[0],encoding='utf-8');paths.append(str(path))
        target=self.folder/'rendered.json'
        result=subprocess.run(['node',str(Path(__file__).with_name('health20_viewer_checks.cjs')),*paths,str(target)],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        for figure in json.loads(target.read_text()):go.Figure(figure)

if __name__=='__main__':unittest.main()
