from pathlib import Path
import json,subprocess,unittest
from insights import insight_figures
from test_health31 import fixture
from report_config import settings

class Health36Tests(unittest.TestCase):
    def test_settings_aware_shared_notes_and_actual_contributors(self):
        loaded,days=fixture();meta=insight_figures(loaded,days,'mmol/L',False,{'insight_meal'})[0].layout.meta
        for s,cob in zip(meta['series'],[0,5,None]):s['meal']['cob']=cob
        src=Path('insights_view.js').read_text()
        setup="const assert=require('assert');const navigation={unit:'mmol/L'};function applyPanelRanges(){};let state={base:'notes',mode:'Median + band',insight:{duration:6,aggregation:'Median',normalization:'absolute',filterStartCOB:true,maxStartCOB:5,minCarbs:0,showIOB:true}};function panelStateAt(){return state;}const meta="+json.dumps(meta)+";function render(){const v={data:[],layout:{meta:JSON.parse(JSON.stringify(meta)),xaxis:{},yaxis:{},margin:{}}};transformInsight(v,0);return v;}\n"
        checks="""
let v=render(),note=v.layout.meta.insight_note;
assert(note.includes('Carbs >0 g'));assert(note.includes('start COB ≤5 g'));assert(note.includes('next carbs (even excluded), 6 h or data end'));assert(note.includes('2 periods'));assert(note.includes('25–75%: between-period variation, not a confidence interval'));assert(note.includes('IOB medians'));assert(note.includes('missing excluded'));
state.insight.filterStartCOB=false;state.insight.aggregation='Average';state.insight.normalization='delta';state.insight.duration=1;state.insight.minCarbs=20;
v=render();note=v.layout.meta.insight_note;assert(note.includes('start COB unfiltered'));assert(!note.includes('start COB ≤'));assert(note.includes('Average Δ glucose'));assert(note.includes('1 h or data end'));assert(note.includes('Baseline exact/bracketed'));
navigation.report_render={range:[480,1200]};v=render();assert(v.layout.meta.insight_note.includes('Clock-hour crop does not apply'));
for(const key of ['activity_during','activity_after','site_age','sensor','sensor_variability','sleep']){
 v.layout.meta.insight=key;state.insight.siteWindow='limited';state.insight.sleepView='after';let n=insightMethodNote(v,state.insight);assert(n.length>30 && n.split(/\\s+/).length<110,n);
 if(key==='activity_after')assert(n.includes('later meals/activities remain included'));
 if(key==='site_age')assert(n.includes('next replacement/data end, limited to 1 h'));
 if(key==='sensor_variability')assert(n.includes('|glucose slope|')&&n.includes('60-min bins'));
 if(key==='sleep')assert(n.includes('next sleep or data end'));
}
v.layout.meta.insight_relationship=true;v.layout.meta.insight_pairs=3;state.insight.relationX='hrv';state.insight.relationY='below';note=insightMethodNote(v,state.insight);assert(note.includes('Recorded HRV (ms; 5-min median) vs next-day time below range'));assert(note.includes('3 paired sleeps'));assert(note.includes('Association, not causation'));
"""
        result=subprocess.run(['node','-e',setup+src+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_corrected_summary_and_six_page_limit(self):
        source=Path('insights_view.js').read_text()
        self.assertIn('earliest of the selected window, next carb entry (including excluded entries), or loaded-data end',source)
        self.assertNotIn('high starting COB does not exclude an event',source)
        self.assertEqual(settings(dict(graphs_per_page=6))['graphs_per_page'],6)
        with self.assertRaises(ValueError):settings(dict(graphs_per_page=7))

if __name__=='__main__':unittest.main()
