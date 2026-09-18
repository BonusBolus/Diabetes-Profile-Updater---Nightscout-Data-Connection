from copy import deepcopy
import tempfile
import unittest
from pathlib import Path
import json
import plotly.graph_objects as go
from comparison_tables import comparison_table
from profiles import save_profile
from nightscout_charts import dataset_traces, graph_figures
from test_nightscout import sample_data

class ComparisonTests(unittest.TestCase):
    def test_union_times_highlights_only_affected_reference(self):
        rows=[dict(time='00:00',value=10)]
        ref1={'schedules':{'ic':[dict(time='00:00',value=10),dict(time='06:00',value=12)]}}
        ref2={'schedules':{'ic':[dict(time='00:00',value=9)]}}
        frame,mask=comparison_table(rows,[('Ref 1',ref1),('Ref 2',ref2)],'ic')
        self.assertEqual(frame['From'].tolist(),['00:00','06:00'])
        self.assertEqual(mask['Draft'].tolist(),[True,True])
        self.assertEqual(mask['Ref 1'].tolist(),[False,True])
        self.assertEqual(mask['Ref 2'].tolist(),[True,True])
        frame,_=comparison_table([dict(time='00:00',low=6.6,high=6.6)],[],'target')
        self.assertEqual(frame.iloc[0]['Draft'],'6.6 - 6.6')

    def test_explicit_unused_version_does_not_silently_replace(self):
        profile=json.loads(next((Path(__file__).resolve().parents[1]/'data/profiles').glob('*.json')).read_text())
        with tempfile.TemporaryDirectory() as folder:
            saved=save_profile(folder,profile,version=7)
            self.assertEqual(saved['version'],7)
            with self.assertRaisesRegex(ValueError,'already exists'):
                save_profile(folder,profile,version=7)
            for bad in (0,True,1.5):
                with self.assertRaises(ValueError):save_profile(folder,profile,version=bad)

    def test_grouped_overlay_and_profile_axis(self):
        loaded=sample_data();profile=go.Figure(go.Scatter(x=[0,1440],y=[9,10]))
        profile.update_layout(yaxis=dict(title='g/U',rangemode='normal'))
        for overlay,kinds in [('IOB + boluses',{'iob','bolus'}),('COB + carbs',{'cob','carbs'})]:
            fig=graph_figures(profile,loaded,[loaded['first']],'One day',[],'mmol/L',True,overlay=overlay)[0]
            self.assertEqual({t.meta['kind'] for t in fig.data if t.meta},kinds)
            self.assertTrue(all(t.yaxis=='y2' for t in fig.data if t.meta))
            self.assertEqual(fig.layout.yaxis.rangemode,'normal')
            self.assertEqual(len(fig.data),3)

    def test_scheduled_targets_never_displayed(self):
        import pandas as pd
        from datetime import timedelta
        loaded=sample_data();start=loaded['loaded_at']-timedelta(days=2)
        loaded['data']['target']=pd.DataFrame([
            dict(time=start,end=start+timedelta(hours=7),low=118.8,high=118.8,source='Scheduled target',reason=''),
            dict(time=start+timedelta(hours=7),end=start+timedelta(hours=8),low=144,high=144,source='Temporary target',reason='Activity'),
            dict(time=start+timedelta(hours=8),end=start+timedelta(days=1),low=118.8,high=118.8,source='Scheduled target',reason='')])
        traces=dataset_traces('target',loaded,[loaded['first']],'One day','mmol/L',True)
        self.assertEqual(len(traces),2)
        for trace in traces:
            self.assertEqual(list(trace.x),[420,480,None])
            self.assertEqual(trace.line.color,'#59cddd')
        loaded['data']['target']=loaded['data']['target'].query("source == 'Scheduled target'")
        self.assertEqual(dataset_traces('target',loaded,[loaded['first']],'One day','mmol/L',True),[])

    def test_solid_fills_and_concise_legends_across_dates(self):
        import pandas as pd
        from datetime import timedelta
        loaded=sample_data()
        for key in ('iob','cob'):
            frame=loaded['data'][key]
            later=frame.copy();later['time']=later['time']+timedelta(days=1)
            loaded['data'][key]=pd.concat([frame,later],ignore_index=True)
        start=loaded['loaded_at']-timedelta(days=2)
        loaded['data']['target']=pd.DataFrame([
            dict(time=start+timedelta(days=d),end=start+timedelta(days=d,hours=1),low=118.8,high=144,source='Temporary target',reason='Activity') for d in (0,1)])
        days=[loaded['first'],loaded['last']]
        profile=go.Figure(go.Scatter(x=[0,1440],y=[9,10],name='LenStandardV17'))
        figs=graph_figures(profile,loaded,days,'Multiple days',['IOB','COB','Nightscout targets'],'mmol/L',True)
        for fig in figs[1:]:
            self.assertEqual(sum(bool(t.showlegend) for t in fig.data),1)
            for trace in fig.data:
                self.assertNotIn('2026-',trace.name)
                self.assertEqual(trace.line.dash,'solid')
                self.assertTrue(trace.meta['date'])
            if fig.data[0].meta['kind']=='target':
                self.assertEqual(fig.data[1].fill,'tonexty')
            else:
                self.assertTrue(all(t.fill=='tozeroy' for t in fig.data))

    def test_fullscreen_overlay_variants_keep_selected_median(self):
        from graph_view import navigation_bundle
        from nightscout_charts import OVERLAY_CHOICES
        loaded=sample_data()
        profile=go.Figure(go.Scatter(x=[0,1440],y=[9,10],name='LenStandardV17'))
        profile.update_layout(yaxis=dict(title='g/U',rangemode='normal'))
        view=dict(loaded=loaded,days=[loaded['first'],loaded['last']],mode='Median + band',layers=['Glucose'],overlay='None')
        bundle=navigation_bundle(profile,view,'mmol/L',True)
        self.assertEqual(set(bundle['overlays']),set(OVERLAY_CHOICES))
        self.assertEqual(bundle['overlay'],'None')
        self.assertTrue(any(t.get('meta',{}).get('kind')=='median' for t in bundle['overlays']['Glucose']['selected']['data']))
        self.assertEqual({t.get('meta',{}).get('date') for t in bundle['overlays']['Glucose']['daily']['data'] if t.get('meta',{}).get('kind')=='glucose'},set(bundle['days']))
        for name,kinds in [('IOB + boluses',{'iob','bolus'}),('COB + carbs',{'cob','carbs'})]:
            top=bundle['overlays'][name]['daily']
            self.assertEqual({t['meta']['kind'] for t in top['data'] if t.get('meta')},kinds)
            self.assertEqual(top['layout']['yaxis']['rangemode'],'normal')
        self.assertNotIn('yaxis2',bundle['overlays']['None']['selected']['layout'])
