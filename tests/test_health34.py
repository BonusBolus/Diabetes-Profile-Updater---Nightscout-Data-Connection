"""Daily-grid visibility preserves data; workspace navigation preserves sources."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
from nightscout_charts import hourly_figure
from garmin_data import merge_sources
from test_nightscout import sample_data

ROOT=Path(__file__).parents[1]


class Health34Tests(unittest.TestCase):
    def test_hourly_grid_default_and_copies_preserve_bar_statistics(self):
        loaded=sample_data();days=[loaded['first'],loaded['last']]
        keys=['bolus','carbs','profile_percentage','site_changes','sensor_changes']
        loaded['recorded_profiles']=[dict(start='2026-09-16T00:00Z',end='2026-09-18T00:00Z',percentage=80)]
        figures=[json.loads(hourly_figure(loaded,key,days,False).to_json()) for key in keys]
        setup="""const assert=require('assert'),garminOptions={},hourlyModes={},excludeSMB=false,currentOverlay='None',currentMetric='ic';
const specs="""+json.dumps(figures)+";\n"
        checks="""
for(let i=0;i<specs.length;i++){
 const state=ensurePanelState(specs[i]);assert.equal(state.showDailyGrid,false);
 const original=JSON.stringify(specs[i]),v=JSON.parse(original),barsBefore=JSON.stringify(v.data.find(t=>t.meta.kind==='hourly_histogram'));
 applyHourlyGrid(v,i);assert.equal(v.data[0].visible,false);assert.equal(v.data[0].showscale,false);assert.equal(v.layout.yaxis.visible,false);assert.deepEqual(v.layout.yaxis2.domain,[0,1]);assert.equal(v.layout.height,280);
 assert.equal(JSON.stringify(v.data.find(t=>t.meta.kind==='hourly_histogram')),barsBefore);
 assert.deepEqual(v.data[0].z,specs[i].data[0].z);assert.equal(JSON.stringify(specs[i]),original);
 state.showDailyGrid=true;const shown=JSON.parse(original);applyHourlyGrid(shown,i);assert.equal(shown.data[0].visible,true);assert.notDeepEqual(shown.layout.yaxis2.domain,[0,1]);assert.equal(shown.layout.height,specs[i].layout.height);
 const copy=JSON.parse(original);specs.push(copy);ensurePanelState(copy,{id:'copy-'+i,base:state.base,duplicate:true,showDailyGrid:false});
 const hidden=JSON.parse(JSON.stringify(copy));applyHourlyGrid(hidden,specs.length-1);assert.equal(hidden.data[0].visible,false);assert.equal(state.showDailyGrid,true);
 if(i===4)break;
}
"""
        result=subprocess.run(['node','-e',setup+(ROOT/'panel_view.js').read_text()+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_data_editor_navigation_never_reads_sources_and_reuses_combined_snapshot(self):
        ns=sample_data();ns['zone']='Europe/Amsterdam'
        garmin=dict(first=ns['first'],last=ns['last'],zone=ns['zone'],loaded_at=ns['loaded_at'],warnings=[],inventory=[],daily=[],activities=[],measurement_units='Metric',
                    data={'g_hr':pd.DataFrame([dict(time=pd.Timestamp('2026-09-16T10:00Z'),value=70,label='Heart rate')])})
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'PROFILE_STUDIO_DATA':folder}):
            for path in (ROOT/'data/profiles').glob('*.json'):shutil.copyfile(path,Path(folder)/path.name)
            at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
            self.assertFalse(at.exception)
            at.session_state.ns_loaded=ns;at.session_state.garmin_loaded=garmin
            at.session_state.ns_layers=['Glucose'];at.session_state.editor_tab='I:C'
            with patch('nightscout_ui.load_nightscout') as fetch,patch('garmin_ui.load_garmin') as read,patch('garmin_ui.merge_sources',wraps=merge_sources) as merge,patch('graph_view.render_graphs'):
                at.radio(key='page').set_value('Data').run();self.assertFalse(at.exception)
                combined=at.session_state._combined_health[1]
                combined['_chart_cache']['navigation_sentinel']={'keep':True}
                draft=deepcopy(at.session_state.draft)
                for page in ('Editor','Data','Editor'):
                    at.session_state.editor_tab='I:C'
                    at.radio(key='page').set_value(page).run();self.assertFalse(at.exception)
                    self.assertIs(at.session_state.ns_loaded,ns);self.assertIs(at.session_state.garmin_loaded,garmin)
                    self.assertIs(at.session_state._combined_health[1],combined)
                    self.assertEqual(combined['_chart_cache']['navigation_sentinel'],{'keep':True})
                fetch.assert_not_called();read.assert_not_called();merge.assert_called_once()
                self.assertEqual(at.session_state.draft,draft)


if __name__=='__main__':unittest.main()
