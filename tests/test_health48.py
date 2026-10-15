"""Saved PDF presets, missing Plotly axes, compact reports and activity windows."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from copy import deepcopy
from report_config import save_preset,presets,request_for_preset

ROOT=Path(__file__).parents[1]

class Health48Tests(unittest.TestCase):
    def js(self,source):
        with tempfile.TemporaryDirectory() as folder:
            script=Path(folder)/'check.cjs';script.write_text(source,encoding='utf-8')
            result=subprocess.run(['node',str(script)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_all_pdf_settings_round_trip_and_generation_uses_saved_value(self):
        graph=dict(id='custom:custom-1',base='custom:Custom graph',graphType='daily',fitActivities=True,events={'automation':'show'},custom=dict(id='custom-1',selected=['garmin:g_workout_speed'],garmin={'pace':True},fieldOptions={'garmin:g_workout_speed':{'smooth':True,'tauSeconds':30}},axisRanges={'unit:min/km':[2,8]}))
        viewer=dict(workspaceVersion=2,panels=[graph],order=[graph['id']],customPanels=[graph['custom']])
        raw=dict(title='Daily',first='2026-09-25',last='2026-09-26',from_time='06:00',until_time='20:00',layout='portrait',graphs_per_page=6,overview_fields=['coverage'],blocks=[dict(key='daily',graphs_per_page=4,viewer=viewer)],viewer=viewer)
        with tempfile.TemporaryDirectory() as folder:
            save_preset('Daily',raw,folder);saved=presets(folder)[0]['settings'];request=request_for_preset('Daily',folder)
            self.assertEqual(saved['viewer'],viewer);self.assertEqual(saved['blocks'],raw['blocks'])
            self.assertEqual(request['config'],viewer)
            request['config']['panels'][0]['fitActivities']=False
            self.assertTrue(request_for_preset('Daily',folder)['config']['panels'][0]['fitActivities'])
            for key in ('first','last','title','from_time','until_time','layout','graphs_per_page','overview_fields'):self.assertEqual(saved[key],raw[key])
            with self.assertRaises(ValueError):request_for_preset('Missing',folder)

    def test_missing_primary_axis_is_never_passed_to_plotly_relayout(self):
        source=(ROOT/'garmin_view.js').read_text(encoding='utf-8');source=source[source.index('async function setTimeRange'):source.index('function activityShadingControl')]
        self.js("""const assert=require('assert');let syncing=false,updates;
const controls=()=>{},clearHover=()=>{},reflowProfileLabels=async()=>{},panelTimeRange=(_,r)=>r;
const timeAxisTicks=()=>({});
const workoutAxisUpdates=()=>({'yaxis.range':[0,1],'yaxis2.range':[2,4]});
const graphs=[{data:[],layout:{meta:{},xaxis:{visible:false},xaxis2:{}},_fullLayout:{xaxis2:{},yaxis2:{}}}];
const Plotly={relayout:async(g,u)=>{updates=u;assert(!('xaxis.range' in u));assert(!('yaxis.range' in u));}};
"""+source+"""
(async()=>{await setTimeRange([600,990]);assert.deepEqual(updates['xaxis2.range'],[600,990]);assert.deepEqual(updates['yaxis2.range'],[2,4]);assert.equal(syncing,false);})().catch(e=>{console.error(e);process.exit(1)});
""")

    def test_partial_older_garmin_settings_get_independent_defaults(self):
        source=(ROOT/'garmin_view.js').read_text(encoding='utf-8');source=source[source.index('const garminOptions'):source.index('const garminButtons')]
        self.js("const assert=require('assert');"+source+"""
const first=restoredGarminOptions({pace:true,sleepFields:['g_sleep_hrv']}),second=restoredGarminOptions();
assert(first.pace);assert.deepEqual(first.activity,{});assert.equal(first.sleepDistribution,true);
first.sleepFields.push('g_sleep_rr');first.activity.speed={lower:5};assert.deepEqual(second.sleepFields,[]);assert.deepEqual(second.activity,{});
garminOptions.pace=true;garminOptions.sleepFields=['g_sleep_hrv'];
for(const raw of [undefined,null]){const restored=restoredGarminOptions(raw);assert(restored.pace);assert.deepEqual(restored.sleepFields,['g_sleep_hrv']);restored.sleepFields.push('g_sleep_rr');assert.deepEqual(garminOptions.sleepFields,['g_sleep_hrv']);}
""")

    def test_block_specific_graph_settings_override_stale_global_settings(self):
        source=(ROOT/'report_ui.js').read_text(encoding='utf-8');source=source[source.index('function reportPresetViewer'):source.index('function reportBlockOf')]
        self.js("const assert=require('assert');"+source+"""
const settings={viewer:{workspaceVersion:2,panels:[{id:'a',fitActivities:false},{id:'b',graphType:'summary'}]},blocks:[{key:'daily',viewer:{panels:[{id:'a',fitActivities:true,showAmounts:false}]}}]};
const result=reportPresetViewer(settings);assert(result.panels.find(p=>p.id==='a').fitActivities);assert.equal(result.panels.length,2);assert.equal(settings.viewer.panels[0].fitActivities,false);
""")

    def test_daily_headers_omit_layer_names_and_repeated_method_notes(self):
        from test_health42 import data
        from report_export import build_report
        loaded,days=data();config=dict(workspaceVersion=2,panels=[dict(id=':glucose',base=':glucose',title='My long layer list',graphType='daily')])
        html=build_report(loaded,dict(unit='mmol/L',layers=['Glucose'],data_only=True),dict(first=str(days[0]),last=str(days[1]),blocks=[dict(key='daily')],config=config))
        report=json.loads(html.split('const report=',1)[1].split(';</script>',1)[0])
        self.assertEqual([j['title'] for j in report['jobs']],['Daily · '+str(d) for d in days[:2]])
        self.assertTrue(all(j['note']=='' for j in report['jobs']))

if __name__=='__main__':unittest.main()
