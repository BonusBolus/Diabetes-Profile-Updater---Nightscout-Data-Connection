from datetime import date, datetime, timedelta, timezone
import unittest
import plotly.graph_objects as go
from nightscout import normalize_data
from nightscout_charts import dataset_traces, graph_figures

UTC=timezone.utc
START=datetime(2026,9,16,tzinfo=UTC)


def effective(at=START, low=6.6, high=7):
    return dict(created_at=at.isoformat(),originalProfileName='Historical Standard',profileJson={
        'timezone':'UTC','units':'mmol/l',
        'target_low':[dict(time='00:00',value=low),dict(time='11:00',value=7)],
        'target_high':[dict(time='00:00',value=high),dict(time='11:00',value=7.5)]})


def temporary(hour, minutes=30, low=8.5, high=None, reason='Activity'):
    return dict(created_at=(START+timedelta(hours=hour)).isoformat(),eventType='Temporary Target',
                units='mmol/l',duration=minutes,targetBottom=low,targetTop=low if high is None else high,reason=reason)


def loaded(events):
    data,warnings=normalize_data([],events,[],START,START+timedelta(days=2))
    return dict(data=data,warnings=warnings,zone='UTC',first=START.date(),last=(START+timedelta(days=1)).date(),loaded_at=START+timedelta(days=2))


def segments(xs,ys):
    result=[];part=[]
    for x,y in zip(xs,ys):
        if x is None:
            if part:result.append(part)
            part=[]
        else:part.append((x,y))
    return result


class TargetRectangleTests(unittest.TestCase):
    def test_temp_target_panel_and_overlay_use_fixed_glucose_scale(self):
        for events in ([],[effective(),temporary(8,low=8.5)],[effective(),temporary(8,low=25)]):
            snapshot=loaded(events)
            draft=go.Figure(go.Scatter(x=[0,1440],y=[5,5]))
            for mode in ('One day','Multiple days','Median + band'):
                for unit,upper in [('mmol/L',20),('mg/dL',360)]:
                    figures=graph_figures(draft,snapshot,[START.date()],mode,['Nightscout targets'],unit,False,
                                          overlay='Nightscout targets')
                    self.assertEqual(list(figures[0].layout.yaxis2.range),[0,upper])
                    self.assertEqual(list(figures[1].layout.yaxis.range),[0,upper])
                    self.assertFalse(figures[1].layout.yaxis.autorange)

    def test_historical_range_retained_and_split_at_schedule_changes(self):
        snapshot=loaded([effective(),temporary(10.5,60)])
        target=snapshot['data']['target']
        temp=target[target.source=='Temporary target']
        self.assertEqual(len(temp),2)
        self.assertEqual(list(temp['profile_high']/18),[7,7.5])
        self.assertEqual(temp.iloc[0]['end'],START+timedelta(hours=11))
        traces=dataset_traces('target',snapshot,[START.date()],'One day','mmol/L',True)
        fill=next(t for t in traces if t.meta['kind']=='target_fill')
        shapes=segments(fill.x,fill.y)
        self.assertEqual(shapes,[[(630,7),(660,7),(660,8.5),(630,8.5),(630,7)],
                                 [(660,7.5),(690,7.5),(690,8.5),(660,8.5),(660,7.5)]])
        self.assertEqual(fill.fill,'toself')
        edges=next(t for t in traces if t.meta['kind']=='target_boundary')
        self.assertEqual(edges.line.dash,'dot')
        self.assertTrue(all(points[0][0]==points[1][0] for points in segments(edges.x,edges.y)))
        self.assertTrue(all(t.fill!='tonexty' for t in traces))

    def test_disjoint_rectangles_lower_targets_ranges_and_unit_conversion(self):
        snapshot=loaded([effective(),temporary(8,low=8,high=9),temporary(14,low=4.5)])
        traces=dataset_traces('target',snapshot,[START.date()],'Multiple days','mmol/L',False)
        fill=next(t for t in traces if t.meta['kind']=='target_fill')
        shapes=segments(fill.x,fill.y)
        self.assertEqual(shapes[0],[(480,7),(510,7),(510,9),(480,9),(480,7)])
        self.assertEqual(shapes[1],[(840,4.5),(870,4.5),(870,7),(840,7),(840,4.5)])
        mg=dataset_traces('target',snapshot,[START.date()],'Multiple days','mg/dL',False)
        fill=next(t for t in mg if t.meta['kind']=='target_fill')
        self.assertEqual(list(fill.y),[y*18 if y is not None else None for t in traces if t.meta['kind']=='target_fill' for y in t.y])
        # These limits come only from Nightscout history, regardless of the draft.
        for value in (2,15):
            draft=go.Figure(go.Scatter(x=[0,1440],y=[value,value]))
            figure=graph_figures(draft,snapshot,[START.date()],'One day',[],'mmol/L',False,overlay='Nightscout targets')[0]
            rectangle=next(t for t in figure.data if t.meta and t.meta.get('kind')=='target_fill')
            self.assertEqual(list(rectangle.y),[y for t in traces if t.meta['kind']=='target_fill' for y in t.y])
            self.assertEqual(rectangle.yaxis,'y2')

    def test_missing_or_invalid_history_never_guessed(self):
        for events in ([temporary(8)], [effective(),dict(created_at=(START+timedelta(hours=7)).isoformat(),
                                                       originalProfileName='Invalid',profileJson={}),temporary(8)]):
            snapshot=loaded(events)
            traces=dataset_traces('target',snapshot,[START.date()],'One day','mmol/L',True)
            self.assertTrue(traces)
            self.assertEqual({t.meta['kind'] for t in traces},{'target'})
            self.assertTrue(all(t.fill=='none' for t in traces))
            self.assertTrue(all('unavailable' in item for t in traces for item in t.customdata))

    def test_day_clipping_cancellation_and_reason_colors(self):
        snapshot=loaded([effective(),temporary(23.75,60,reason='Hypo'),temporary(24.25,0)])
        traces=dataset_traces('target',snapshot,[START.date(),date(2026,9,17)],'Median + band','mmol/L',True)
        fills=[t for t in traces if t.meta['kind']=='target_fill']
        self.assertEqual(len(fills),2)
        self.assertEqual([sorted(set(x for x in t.x if x is not None)) for t in fills],[[1425,1440],[0,15]])
        self.assertEqual([t.meta['date'] for t in fills],['2026-09-16','2026-09-17'])
        self.assertTrue(all(t.fillcolor=='rgba(244,67,54,0.12)' for t in fills))
        self.assertEqual([min(y for y in t.y if y is not None) for t in fills],[7.5,7])
