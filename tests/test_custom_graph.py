"""Custom fields preserve source units, averages, target bounds and references."""
import unittest
import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest
from custom_graph import custom_bundle
from nightscout_charts import graph_figures, LAYERS
from test_nightscout import sample_data

class CustomGraphTests(unittest.TestCase):
    def test_profile_ranges_and_references_are_individual_fields(self):
        profile=go.Figure()
        for index,(name,color,values) in enumerate([('Reference','#aabbcc',[6,7]),('Draft','#008844',[6.6,6.6])]):
            for bound,value in zip(('low','high'),values):
                profile.add_trace(go.Scatter(x=[0,1440],y=[value,value],name=name,legendgroup=f'profile-{index}',
                    line=dict(color=color,shape='hv'),showlegend=bound=='high',
                    meta=dict(kind='profile',unit='mmol/L',label=name+' · '+bound,legend_entry=bound=='high',source_role='ref1' if index==0 else 'ref2')))
        profile.update_layout(title='Target · example')
        loaded=sample_data();days=[loaded['first'],loaded['last']]
        bundle=custom_bundle(loaded,days,days,'Median + band','mmol/L',True,{'target':profile})
        fields=bundle['fields'];schedules=[f for f in fields if f['group']=='Profiles']
        self.assertEqual(len(schedules),2)
        self.assertEqual(schedules[0]['label'],'Target · Reference')
        self.assertEqual(schedules[0]['metric_color'],'#64d86a')
        self.assertEqual(schedules[0]['source_color'],'#c4a4ff')
        self.assertEqual(schedules[1]['source_color'],'#ff9bc9')
        self.assertEqual(schedules[0]['color'],'#aabbcc')
        self.assertIn('color:#c4a4ff',schedules[0]['selected'][0]['name'])
        self.assertIn('color:#ff9bc9',schedules[1]['selected'][0]['name'])
        light=custom_bundle(loaded,days,days,'One day','mmol/L',False,{'target':profile})
        self.assertEqual(light['fields'][-1]['source_color'],'#b83378')
        self.assertEqual(light['fields'][0]['color'],'#218c24')
        self.assertEqual(len(schedules[1]['selected']),2)
        self.assertEqual(schedules[1]['selected'][0]['y'],[6.6,6.6])
        self.assertEqual(schedules[1]['selected'][1]['y'],[6.6,6.6])
        self.assertEqual(schedules[0]['selected'][0]['line']['color'],'#aabbcc')
        carb=next(f for f in fields if f['id']=='ns:carbs')
        self.assertEqual(carb['selected'][0]['y'][5],15)
        self.assertEqual(carb['selected'][0]['customdata'][5],2)
        self.assertTrue(all(t['type']=='scatter' for t in carb['daily']))
        self.assertNotIn('SENS%',str(bundle))

    def test_grouped_layers_control_their_hourly_panels(self):
        loaded=sample_data();profile=go.Figure()
        for label,key,continuous in [('IOB + boluses','bolus','iob'),('COB + carbs','carbs','cob')]:
            figs=graph_figures(profile,loaded,[loaded['first']],'Median + band',[label],'mmol/L',True)
            self.assertEqual(len(figs),3)
            self.assertTrue(any((t.meta or {}).get('dataset')==continuous for t in figs[1].data))
            self.assertEqual(figs[2].layout.meta['dataset'],key)
        self.assertNotIn('IOB + COB',LAYERS)
        self.assertNotIn('IOB',LAYERS)
        self.assertNotIn('Carbs',LAYERS)

    def test_old_layer_selections_migrate_without_removed_combination(self):
        at=AppTest.from_string('''
import streamlit as st
from test_nightscout import sample_data
from nightscout_ui import sidebar_controls
if 'ns_loaded' not in st.session_state:
    st.session_state.ns_loaded=sample_data()
    st.session_state.ns_layers=['IOB','Boluses','COB','Carbs','IOB + COB']
sidebar_controls('UTC')
''').run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state.ns_layers,['IOB + boluses','COB + carbs'])
        at.button_group(key='ns_layers').set_value(['Custom graph']).run()
        self.assertFalse(at.exception)
