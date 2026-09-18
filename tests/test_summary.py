from datetime import datetime, timedelta, date, timezone
from pathlib import Path
import unittest
from unittest.mock import patch
import pandas as pd
import plotly.graph_objects as go
from test_nightscout import sample_data
from nightscout_stats import continuous_summary, hourly_events
from nightscout_charts import graph_figures
from graph_view import prepared_graphs
UTC=timezone.utc

class SummaryTests(unittest.TestCase):
    def test_iob_cob_medians_equal_day_weight_and_gaps(self):
        loaded=sample_data();start=datetime(2026,9,16,tzinfo=UTC)
        for key in ('iob','cob'):
            loaded['data'][key]=pd.DataFrame([dict(time=start+timedelta(minutes=m),value=v,label=key) for m,v in [(0,2),(1,2),(2,2),(1440,8)]])
            stats=continuous_summary(loaded,key,[loaded['first'],loaded['last']],'mmol/L')
            self.assertEqual(stats.iloc[0]['median'],5)
            self.assertEqual(stats.iloc[0]['days'],2)
            self.assertTrue(pd.isna(stats.iloc[1]['median']))
        profile=go.Figure(go.Scatter(x=[0,1440],y=[1,1]))
        figures=graph_figures(profile,loaded,[loaded['first'],loaded['last']],'Median + band',['IOB','COB','Boluses','Carbs'],'mmol/L',True)
        self.assertEqual(len(figures),5) # profile, IOB, COB, two hourly graphs
        for fig in figures[1:3]:
            self.assertEqual(sum(t.meta and t.meta.get('kind')=='median' for t in fig.data if t.meta),1)
            self.assertFalse(any(t.meta and t.meta.get('date') for t in fig.data))
        self.assertEqual([f.layout.meta['dataset'] for f in figures[-2:]],['bolus','carbs'])

    def test_basal_duration_weighted_within_day_missing_is_not_zero(self):
        loaded=sample_data();start=datetime(2026,9,16,tzinfo=UTC)
        loaded['data']['basal']=pd.DataFrame([
            dict(time=start,end=start+timedelta(minutes=1),value=1),
            dict(time=start+timedelta(minutes=1),end=start+timedelta(minutes=5),value=2),
            dict(time=start+timedelta(days=1),end=start+timedelta(days=1,minutes=5),value=4),
            dict(time=start+timedelta(minutes=10),end=start+timedelta(minutes=15),value=0)])
        stats=continuous_summary(loaded,'basal',[loaded['first'],loaded['last']],'mmol/L')
        self.assertAlmostEqual(stats.iloc[0]['median'],2.9) # median(1.8,4)
        self.assertTrue(pd.isna(stats.iloc[1]['median']))
        self.assertEqual(stats.iloc[2]['median'],0)
        self.assertEqual(stats.iloc[2]['days'],1)

    def test_hourly_sums_zero_hours_and_partial_day(self):
        loaded=sample_data();loaded['availability']={'treatments':True}
        stats=hourly_events(loaded,'carbs',[loaded['first'],loaded['last']])
        self.assertEqual(stats['values'][0][5],30)
        self.assertEqual(stats['median'][5],15)
        self.assertEqual(stats['median'][4],0)
        self.assertEqual(stats['counts'][0][5],1)
        loaded['loaded_at']=datetime(2026,9,17,5,30,tzinfo=UTC)
        stats=hourly_events(loaded,'carbs',[loaded['first'],loaded['last']])
        self.assertEqual(stats['values'][1][5],0)
        self.assertEqual(stats['status'][1][5],'Partial hour')
        self.assertEqual(stats['median'][5],30)
        self.assertIsNone(stats['values'][1][6])
        loaded['availability']['treatments']=False
        stats=hourly_events(loaded,'carbs',[loaded['first']])
        self.assertTrue(all(v is None for v in stats['values'][0]))
        self.assertTrue(all(v is None for v in stats['median']))

    def test_dst_missing_and_repeated_hour(self):
        loaded=sample_data();loaded['zone']='Europe/Amsterdam';loaded['loaded_at']=datetime(2026,11,1,tzinfo=UTC)
        stats=hourly_events(loaded,'carbs',[date(2026,3,29)])
        self.assertIsNone(stats['values'][0][2])
        self.assertFalse(stats['complete'][0][2])
        loaded['data']['bolus']=pd.DataFrame([dict(time=datetime(2026,10,25,h,30,tzinfo=UTC),value=v,label='SMB') for h,v in [(0,1),(1,2)]])
        stats=hourly_events(loaded,'bolus',[date(2026,10,25)])
        self.assertEqual(stats['values'][0][2],3)
        self.assertEqual(stats['counts'][0][2],2)
        self.assertEqual(stats['contributing'][2],1)

    def test_cache_reuse_profile_edits_and_refresh_isolation(self):
        loaded=sample_data();loaded['_chart_cache']={}
        profile=go.Figure(go.Scatter(x=[0,1440],y=[1,1]));profile.update_layout(title='Basal',yaxis_title='U/h')
        view=dict(loaded=loaded,days=[loaded['first']],mode='One day',layers=['Glucose'],overlay='None')
        first=prepared_graphs(profile,view,'mmol/L',True)
        with patch('graph_view.navigation_bundle',side_effect=AssertionError('Should reuse prepared viewer')):
            self.assertIs(prepared_graphs(profile,view,'mmol/L',True),first)
        from nightscout_charts import _dataset_traces
        profile.data[0].y=[2,2]
        with patch('nightscout_charts._dataset_traces',wraps=_dataset_traces) as build:
            changed=prepared_graphs(profile,view,'mmol/L',True)
            self.assertEqual(build.call_count,0)
        self.assertEqual(changed[0][0].data[0].y[0],2)
        fresh=sample_data();fresh['_chart_cache']={};fresh['data']['glucose'].loc[:,'value']=90
        refreshed=prepared_graphs(profile,dict(view,loaded=fresh),'mmol/L',True)
        self.assertEqual(refreshed[0][1].data[0].y[0],5)
        self.assertEqual(first[0][1].data[0].y[0],10)
