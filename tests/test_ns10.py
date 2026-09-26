"""Timestamp precision, genuine gaps, retained VSENS and removed approximate telemetry."""
from datetime import datetime, timedelta, timezone
import unittest
import pandas as pd
import plotly.graph_objects as go
from nightscout_charts import dataset_traces, graph_figures, interval_points, hourly_figure, LAYERS, OVERLAY_CHOICES
from nightscout_stats import hourly_events
from test_nightscout import sample_data


class GraphRevisionTests(unittest.TestCase):
    def test_fractional_seconds_do_not_create_shared_breaks(self):
        loaded=sample_data();start=datetime(2026,9,16,tzinfo=timezone.utc)
        times=[start+timedelta(seconds=s) for s in (.95,300.05,600.95,2400.05)]
        for key in ('iob','cob','variable_sens'):
            loaded['data'][key]=pd.DataFrame([dict(time=at,value=2,label=key) for at in times])
            trace=dataset_traces(key,loaded,[loaded['first']],'One day','mg/dL',True)[0]
            for actual,expected in zip(trace.x[:3],[s/60 for s in (.95,300.05,600.95)]):
                self.assertAlmostEqual(actual,expected)
            self.assertEqual(sum(x is None for x in trace.x),1)  # Actual 30-minute gap remains.
        intervals=pd.DataFrame([dict(time=times[0],end=times[1],value=1)])
        xs,ys,_=interval_points(intervals,'UTC',loaded['first'])
        self.assertEqual(len(xs),3)  # Start, end, separator; no spurious split within interval.
        self.assertAlmostEqual(xs[0],.95/60)
        self.assertAlmostEqual(xs[1],300.05/60)

    def test_dst_jump_remains_a_gap(self):
        loaded=sample_data();loaded['zone']='Europe/Amsterdam'
        at=datetime(2026,10,25,0,55,tzinfo=timezone.utc)
        loaded['data']['cob']=pd.DataFrame([dict(time=t,value=2,label='cob') for t in (at,at+timedelta(minutes=5))])
        traces=dataset_traces('cob',loaded,[at.date()],'One day','mmol/L',False)
        self.assertEqual(list(traces[0].x),[175,None,120])

    def test_removed_layers_and_retained_variable_sensitivity(self):
        for label in ('SENS%','Deviation + BGI','IOB + COB + SENS%'):
            self.assertNotIn(label,LAYERS)
            self.assertNotIn(label,OVERLAY_CHOICES)
        loaded=sample_data();at=datetime(2026,9,16,tzinfo=timezone.utc)
        loaded['data']['variable_sens']=pd.DataFrame([dict(time=at,value=90,label='variable_sens')])
        profile=go.Figure(go.Scatter(x=[0,1440],y=[9,9],meta=dict(kind='profile')))
        figures=graph_figures(profile,loaded,[at.date()],'One day',
            ['IOB + boluses','COB + carbs','Variable sensitivity'],'mmol/L',True,overlay='Variable sensitivity')
        self.assertEqual(figures[0].layout.yaxis2.title.text,'mmol/L/U')
        overlay=next(t for t in figures[0].data if (t.meta or {}).get('kind')=='variable_sens')
        self.assertEqual(list(overlay.y),[5])
        variable=next(f for f in figures if (f.layout.meta or {}).get('dataset')=='variable_sens')
        self.assertEqual(variable.layout.yaxis.title.text,'mmol/L/U')
        self.assertEqual(list(variable.data[0].y),[5])

    def test_default_hourly_average_includes_zero_days(self):
        loaded=sample_data();loaded['last']+=timedelta(days=1);loaded['loaded_at']+=timedelta(days=1)
        days=[loaded['first']+timedelta(days=i) for i in range(3)]
        stats=hourly_events(loaded,'carbs',days)
        self.assertEqual(stats['average'][5],10)  # totals 30, 0, 0
        self.assertEqual(stats['median'][5],0)
        fig=hourly_figure(loaded,'carbs',days,True)
        self.assertEqual(fig.data[1].y[5],10)
        self.assertEqual(fig.layout.yaxis2.title.text,'Average g')
