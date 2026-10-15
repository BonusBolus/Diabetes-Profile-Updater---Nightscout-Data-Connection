"""Custom fields preserve source units, averages, target bounds and references."""
import unittest
import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest
from custom_graph import custom_bundle
from nightscout_charts import graph_figures, LAYERS
from test_nightscout import sample_data

class CustomGraphTests(unittest.TestCase):
    def test_custom_profiles_use_recorded_nightscout_values_instead_of_drafts(self):
        from test_health42 import data
        loaded,days=data()
        draft=go.Figure(go.Scatter(x=[0,1440],y=[999,999]))
        draft.update_layout(title='Target · unsaved draft')
        bundle=custom_bundle(loaded,days,days,'Median + band','mmol/L',True,{'target':draft})
        profiles=[f for f in bundle['fields'] if f['group']=='Profiles']
        self.assertEqual({f['id'] for f in profiles},{'profile:ic:nightscout','profile:isf:nightscout','profile:basal:nightscout','profile:target:nightscout'})
        target=next(f for f in profiles if f['id']=='profile:target:nightscout')
        self.assertEqual(len(target['selected']),2)
        self.assertEqual({y for t in target['selected'] for y in t['y'] if y is not None},{6.6})
        self.assertTrue(all(t['meta']['profile_source']=='nightscout' for t in target['daily']))

    def test_grouped_layers_control_their_hourly_panels(self):
        loaded=sample_data();profile=go.Figure()
        for label,key,continuous in [('IOB + Boluses','bolus','iob'),('COB + Carbs','carbs','cob')]:
            figs=graph_figures(profile,loaded,[loaded['first'],loaded['last']],'Median + band',[label],'mmol/L',True)
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
        self.assertEqual(at.session_state.ns_layers,['IOB + Boluses','COB + Carbs'])
        at.button(key='add_custom_layer').click().run()
        self.assertFalse(at.exception)
