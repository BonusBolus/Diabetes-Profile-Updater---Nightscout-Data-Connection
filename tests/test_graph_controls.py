"""Graph filtering, calendar interaction and active schedule guides."""
from datetime import date, datetime, timezone
import unittest
import pandas as pd
import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest
from test_nightscout import sample_data
from nightscout_charts import hourly_figure, graph_figures, schedule_changes, add_profile_guides
from nightscout_stats import hourly_events


class GraphControlTests(unittest.TestCase):
    def test_large_event_labels_have_space_on_panels_and_overlay_axes(self):
        loaded=sample_data()
        for key,value,label in [('carbs',200,'Carbs'),('bolus',20,'User bolus')]:
            loaded['data'][key]=pd.DataFrame([
                dict(time=datetime(2026,9,16,h,m,tzinfo=timezone.utc),value=value,label=label)
                for h,m in [(0,0),(23,59)]])
        profile=go.Figure(go.Scatter(x=[0,1440],y=[9,9]))
        for overlay in ['COB + carbs','IOB + boluses']:
            for matched in (False,True):
                figures=graph_figures(profile,loaded,[loaded['first']],'One day',
                    ['Carbs','Boluses','IOB','COB'],'mmol/L',True,overlay=overlay,same_scale=matched)
                for fig in figures:
                    for trace in fig.data:
                        if trace.mode and 'text' in trace.mode:
                            self.assertFalse(trace.cliponaxis)
                            axis=fig.layout['yaxis'+(trace.yaxis or 'y')[1:]]
                            ceiling=axis.range[1] if axis.autorange is False else axis.autorangeoptions.include
                            self.assertGreaterEqual(ceiling,max(trace.y)*1.2)
                if matched:
                    self.assertEqual(figures[0].layout.yaxis.range,figures[0].layout.yaxis2.range)

    def test_smb_filter_matches_grid_and_median_without_removing_unknown(self):
        loaded=sample_data();loaded['_chart_cache']={}
        loaded['data']['bolus']=pd.DataFrame([
            dict(time=datetime(2026,9,day,10,tzinfo=timezone.utc),value=value,label=label)
            for day,value,label in [(16,.5,'SMB'),(16,2,'User bolus'),(16,1,'Bolus · unknown'),(17,1,'SMB')]])
        days=[loaded['first'],loaded['last']]
        original=loaded['data']['bolus'].copy(deep=True)
        all_events=hourly_events(loaded,'bolus',days)
        filtered=hourly_events(loaded,'bolus',days,True)
        self.assertEqual(all_events['median'][10],2.25)
        self.assertEqual(filtered['values'][0][10],3)
        self.assertEqual(filtered['values'][1][10],0)
        self.assertEqual(filtered['median'][10],1.5)
        self.assertEqual(filtered['counts'][0][10],2)
        first=hourly_figure(loaded,'bolus',days,True)
        without=hourly_figure(loaded,'bolus',days,True,True)
        again=hourly_figure(loaded,'bolus',days,True)
        self.assertEqual(first.to_json(),again.to_json())
        self.assertEqual(without.data[0].z[0][10],3)
        self.assertEqual(without.data[1].y[10],1.5)
        pd.testing.assert_frame_equal(original,loaded['data']['bolus'])

    def test_primary_changes_propagate_and_replace_when_metric_changes(self):
        loaded=sample_data()
        rows=[dict(time=t,value=v) for t,v in [('00:00',1),('08:00',1),('10:00',.8),('20:00',1)]]
        changes=schedule_changes(rows,['value'])
        self.assertEqual(changes,[600,1200])
        self.assertEqual(schedule_changes([dict(time='00:00',low=6.6,high=6.6),dict(time='07:00',low=6.6,high=7)],['low','high']),[420])
        profile=go.Figure(go.Scatter(x=[0,600,1440],y=[1,.8,.8]))
        add_profile_guides(profile,changes,True)
        for times in (changes,[420]):
            profile.layout.meta={'profile_changes':times}
            figs=graph_figures(profile,loaded,[loaded['first']],'Median + band',['Glucose','IOB','COB','Temporary basal'],'mmol/L',True)
            for fig in figs:
                self.assertEqual([s.x0 for s in fig.layout.shapes if s.name=='Profile change'],times)

    def test_calendar_selection_and_pills_without_network(self):
        at=AppTest.from_string('''
from datetime import date, datetime, timezone
import streamlit as st
from nightscout_ui import sidebar_controls, graph_date_controls
from test_nightscout import sample_data
if 'ns_loaded' not in st.session_state:
    st.session_state.ns_loaded=sample_data()
    st.session_state.ns_loaded['first']=date(2026,8,30)
    st.session_state.ns_loaded['last']=date(2026,9,2)
with st.sidebar:
    view=sidebar_controls('UTC')
if view:
    graph_date_controls(view,'ic')
''').run()
        self.assertFalse(at.exception)
        self.assertTrue(at.button(key='ns_calendar_2026-08-29').disabled)
        at.button(key='ns_calendar_2026-08-31').click().run()
        self.assertEqual(at.session_state.ns_day,date(2026,8,31))
        at.radio(key='ns_mode').set_value('Median + band').run()
        at.button(key='ns_calendar_2026-08-31').click().run()
        self.assertNotIn(date(2026,8,31),at.session_state.ns_days)
        at.button(key='ns_clear_days').click().run()
        self.assertEqual(at.session_state.ns_days,[])
        at.button(key='ns_all_days').click().run()
        self.assertEqual(len(at.session_state.ns_days),4)
        at.button_group(key='ns_layers').set_value(['Glucose','IOB']).run()
        at.button_group(key='ns_overlay_ic').set_value('IOB + boluses').run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state.ns_overlay,'IOB + boluses')
        at.button(key='ns_next_ic').click().run()
        self.assertEqual(at.session_state.ns_mode,'One day')
        self.assertEqual(at.session_state.ns_day,date(2026,8,30))
        self.assertFalse(at.exception)
