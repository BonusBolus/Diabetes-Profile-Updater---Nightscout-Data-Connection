"""Consolidated workspace, source independence and compact basal accounting."""
from pathlib import Path
from copy import deepcopy
from tempfile import TemporaryDirectory
import unittest
import subprocess
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
from compact_glucose import basal_records
from nightscout import glucose_summary
from report_config import save_preset,presets
from test_health31 import fixture
from view_config import apply_configuration

ROOT=Path(__file__).parents[1]

class Health38Tests(unittest.TestCase):
    def test_percentiles_weight_days_equally_and_leave_gaps(self):
        time=pd.Timestamp('2026-09-25T00:00Z')
        values=[1,2,9]
        data=pd.DataFrame([dict(time=time+pd.Timedelta(days=d,seconds=i),value=v*18) for d,v in enumerate(values) for i in range(1 if d else 9)])
        result=glucose_summary(data,'UTC',[(time+pd.Timedelta(days=d)).date() for d in range(3)],'mmol/L')
        row=result.iloc[0]
        self.assertEqual(row['median'],2);self.assertEqual(row['average'],4)
        self.assertAlmostEqual(row['p10'],1.2);self.assertAlmostEqual(row['p90'],7.6)
        self.assertTrue(pd.isna(result.iloc[1]['p10']))

    def test_compact_basal_effective_profile_and_exact_temp_boundaries(self):
        loaded,days=fixture();start=pd.Timestamp('2026-09-25T00:00Z');end=start+pd.Timedelta(days=1)
        loaded['recorded_profiles']=[dict(start=start.isoformat(),end=end.isoformat(),percentage=80,profile={'timezone':'UTC','basal':[{'time':'00:00','value':1},{'time':'10:00','value':.8}]})]
        loaded['data']['basal']=pd.DataFrame([dict(time=start+pd.Timedelta(hours=8,seconds=15),end=start+pd.Timedelta(hours=8,minutes=30,seconds=15),value=2)])
        result=basal_records(loaded,[days[0]])[0]
        self.assertAlmostEqual(result['basal'],21.7);self.assertAlmostEqual(result['known_hours'],24)
        self.assertLess(len(result['x']),15) # Coalesce unchanged scheduled rates.
        self.assertIn(480.25,result['x'])
        # Effective JSON already includes percentage. Do not multiply by 80% again.
        self.assertEqual(result['scheduled'][0],1)
        loaded['data']['basal_percent']=pd.DataFrame([dict(time=start+pd.Timedelta(hours=12),end=start+pd.Timedelta(hours=13),value=80)])
        self.assertAlmostEqual(basal_records(loaded,[days[0]])[0]['known_hours'],23)
        loaded['availability']['treatments']=False;loaded['data']['basal']=pd.DataFrame()
        self.assertEqual(basal_records(loaded,[days[0]])[0]['known_hours'],0)

    def test_compact_basal_dst_uses_elapsed_hours(self):
        loaded,_=fixture();loaded['zone']='Europe/Amsterdam'
        loaded['loaded_at']='2026-11-01T00:00:00Z'
        loaded['data']['basal']=pd.DataFrame();loaded['data']['basal_percent']=pd.DataFrame()
        loaded['recorded_profiles']=[dict(start='2026-03-01T00:00:00Z',end='2026-11-01T00:00:00Z',profile={'timezone':'Europe/Amsterdam','basal':[{'time':'00:00','value':1}]})]
        for day,hours in [('2026-03-29',23),('2026-10-25',25)]:
            result=basal_records(loaded,[pd.Timestamp(day).date()])[0]
            self.assertAlmostEqual(result['basal'],hours)
            self.assertAlmostEqual(result['known_hours'],hours)

    def test_summary_iob_statistic_and_gap_bands(self):
        setup="""const window={addEventListener(){}};const assert=require('assert');let state={bands:'Both',statistic:'Median'};function panelStateAt(){return state;}
const input={data:[{x:[0,5,10],y:[-2,null,3],name:'Median IOB',line:{color:'#177cb8'},meta:{kind:'median',dataset:'iob',label:'Median IOB',summary:{median:[-2,null,3],average:[1,null,4],p10:[-4,null,1],p90:[4,null,6],count:[3,0,3]}}}],layout:{meta:{}}};
"""
        checks="""let v=JSON.parse(JSON.stringify(input));applySummaryBands(v,0);
assert(v.data.some(t=>t.name==='Median negative IOB' && t.y[0]===-2));
assert(v.data.filter(t=>t.meta.kind==='percentile_band').every(t=>Math.max(...t.x)-Math.min(...t.x)<=5));
state.statistic='Average';v=JSON.parse(JSON.stringify(input));applySummaryBands(v,0);
assert.deepEqual(v.data.find(t=>t.meta.kind==='median').y,[1,null,4]);
assert(!v.data.some(t=>t.name.includes('negative')));assert.equal(input.data[0].y[0],-2);
"""
        result=subprocess.run(['node','-e',setup+(ROOT/'workspace_view.js').read_text()+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_export_presets_keep_independent_graph_instances(self):
        config=dict(layout='portrait',graphs_per_page=6,sections=['daily','median'],viewer={'workspaceVersion':2,'panels':[{'id':'x','graphType':'daily','events':{'site':'hide'},'bands':'Both'}]})
        with TemporaryDirectory() as folder:
            save_preset('Compact',config,folder)
            self.assertEqual(presets(folder)[0]['settings']['viewer'],config['viewer'])

    def test_loading_graph_configuration_preserves_import_selection(self):
        code='''import streamlit as st
from view_config import apply_configuration
st.session_state.ns_load_layers=['Glucose']
st.session_state.garmin_load_layers=['Garmin · Steps']
st.session_state.ns_from='keep'
apply_configuration(dict(format='profile-studio-view',version=1,layers=['IOB + Boluses'],mode='Median + band',viewer=dict(workspaceVersion=2,panels=[])))
assert st.session_state.ns_load_layers==['Glucose']
assert st.session_state.garmin_load_layers==['Garmin · Steps']
assert st.session_state.ns_from=='keep'
'''
        result=AppTest.from_string(code).run();self.assertFalse(result.exception)

    def test_workspace_navigation_does_not_fetch_or_mutate_loaded_data(self):
        loaded,days=fixture()
        for key in ('basal','basal_percent','target','cob','variable_sens'):loaded['data'].setdefault(key,pd.DataFrame(columns=['time','value','label']))
        loaded.update(warnings=[],has_nightscout=True,loaded_categories=['glucose','loop','treatments'])
        with TemporaryDirectory() as folder,patch.dict('os.environ',PROFILE_STUDIO_DATA=folder),patch('graph_view.render_graphs'):
            at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=40).run();self.assertFalse(at.exception)
            at.session_state.ns_loaded=loaded
            with patch('nightscout_ui.load_nightscout') as ns,patch('garmin_ui.load_garmin') as garmin:
                at.session_state.workspace_type='Data';at.run();self.assertFalse(at.exception)
                snapshot=at.session_state.ns_loaded
                at.session_state.data_workspace='Export';at.run();self.assertFalse(at.exception)
                at.session_state.workspace_type='Profile';at.run();self.assertFalse(at.exception)
                at.session_state.workspace_type='Data';at.session_state.data_workspace='View Data';at.run();self.assertFalse(at.exception)
                self.assertIs(at.session_state.ns_loaded,snapshot);ns.assert_not_called();garmin.assert_not_called()
                self.assertEqual(at.session_state.ns_load_layers,['Glucose','COB + Carbs','IOB + Boluses','Temporary Basal','Temporary Targets','Variable Sensitivity','Site / sensor events','Automation notes'])

if __name__=='__main__':unittest.main()
