"""Merged site Insights stop before every recorded replacement in all views."""
import json
from pathlib import Path
import subprocess
import unittest
import pandas as pd
from insights import aligned_series, insight_figures, INSIGHT_LAYERS
from nightscout_charts import normalize_layers
from test_health31 import fixture


def site_fixture():
    loaded,days=fixture()
    start=pd.Timestamp('2026-09-25T00:00Z')
    loaded['data']['changes']=pd.DataFrame([
        dict(time=start+pd.Timedelta(hours=h),label='Site Change') for h in (3,25,52)])
    return loaded,days


class Health33Tests(unittest.TestCase):
    def test_periods_stop_before_replacement_including_legacy_source(self):
        loaded,days=site_fixture()
        for key in ('site_age','site_after'):
            periods=aligned_series(loaded,days,key,'mmol/L')
            self.assertEqual([p['duration'] for p in periods],[22*60,27*60,44*60])
            for left,right in zip(periods,periods[1:]):
                self.assertEqual(left['end'],right['start'])
                self.assertTrue(all(x<left['duration'] for x in left['x'] if x is not None))
        # A replacement still bounds the previous site when its own day is not selected.
        periods=aligned_series(loaded,[days[0],days[2]],'site_age','mmol/L')
        self.assertEqual(periods[0]['duration'],22*60)
        self.assertTrue(all(x<22*60 for x in periods[0]['x'] if x is not None))

    def test_old_layer_selection_produces_one_site_panel(self):
        loaded,days=site_fixture()
        self.assertNotIn('Post-site-change glucose',INSIGHT_LAYERS)
        self.assertEqual(normalize_layers(['Post-site-change glucose','Site-age glucose']),['Site-age glucose'])
        figures=insight_figures(loaded,days,'mmol/L',False,{'insight_site_after','insight_site_age'})
        self.assertEqual(len(figures),1)
        self.assertEqual(figures[0].layout.meta['insight'],'site_age')

    def test_full_and_limited_transforms_keep_replacement_boundaries(self):
        loaded,days=site_fixture()
        meta=insight_figures(loaded,days,'mmol/L',False,{'insight_site_age'})[0].layout.meta
        code="""const assert=require('assert'),navigation={unit:'mmol/L'};
let state={base:'site',mode:'Multiple days',insight:{siteWindow:'full',duration:72,aggregation:'Median',normalization:'absolute'}};
function panelStateAt(){return state;}function applyPanelRanges(){}
const meta="""+json.dumps(meta)+";\n"+(Path(__file__).parents[1]/'insights_view.js').read_text()+"""
function render(){const v={data:[],layout:{meta:JSON.parse(JSON.stringify(meta)),xaxis:{},yaxis:{}}};transformInsight(v,0);return v;}
let v=render(),traces=v.data.filter(t=>t.meta.kind==='insight_event');assert.equal(traces.length,3);
for(let i=0;i<traces.length;i++)assert(Math.max(...traces[i].x.filter(Number.isFinite))<meta.series[i].duration/60);
state.insight.siteWindow='limited';state.insight.duration=6;v=render();
for(const t of v.data.filter(t=>t.meta.kind==='insight_event'))assert(Math.max(...t.x.filter(Number.isFinite))<6);
assert(v.layout.title.text.includes('First 6 h'));
state.insight.duration=72;v=render();traces=v.data.filter(t=>t.meta.kind==='insight_event');
assert(Math.max(...traces[0].x.filter(Number.isFinite))<22,'Long window cannot cross a replacement');
state.mode='Median + band';v=render();assert(v.data.some(t=>t.meta.kind==='insight_band'));
state.insight.siteWindow='full';v=render();assert(!v.layout.title.text.includes('First'));
"""
        result=subprocess.run(['node','-e',code],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_saved_post_change_settings_merge_without_duplicate_base(self):
        source=(Path(__file__).parents[1]/'panel_view.js').read_text()
        code="""const assert=require('assert'),garminOptions={},hourlyModes={},excludeSMB=false,currentOverlay='None',currentMetric='ic';
const merged='insight:insight_site_age',legacy='insight:insight_site_after';
const specs=[{layout:{meta:{kind:'insight',dataset:'insight_site_age',insight:'site_age'},title:{text:'Site-age glucose'}}}],navigation={figures:[]};
function createPanel(){}
"""+source+"""
ensurePanelState(specs[0]);assert.equal(panelStates.get(merged).insight.siteWindow,'full');
const old={id:legacy,base:legacy,mode:'Multiple days',insight:{duration:12,normalization:'delta',aggregation:'Average'}};
const before=JSON.stringify(old);restoreGraphPanels([old]);
assert.equal(panelStates.size,1);let state=panelStates.get(merged);assert.equal(state.insight.siteWindow,'limited');assert.equal(state.insight.duration,12);assert.equal(state.insight.normalization,'delta');assert.equal(JSON.stringify(old),before);
restoreGraphPanels([old,{id:merged,base:merged,insight:{aggregation:'Median'}}]);
assert.equal(panelStates.size,1);assert.equal(panelStates.get(merged).insight.siteWindow,'full');assert.equal(dormantPanelStates.length,0);
restoreGraphPanels([{id:merged,base:merged},{...old,id:'intentional-copy',duplicate:true,insight:{duration:4}}]);
assert.equal(specs.length,2);assert.equal(panelStates.get('intentional-copy').base,merged);assert.equal(panelStates.get('intentional-copy').insight.duration,4);assert.equal(panelStates.get('intentional-copy').insight.siteWindow,'limited');assert.equal(panelStates.get(merged).insight.siteWindow,'full');
"""
        result=subprocess.run(['node','-e',code],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
