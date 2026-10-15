"""Independent imports, historical profile layers, event combinations and day colors."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from threading import Event
import json
import subprocess
import tempfile
import unittest
import pandas as pd
import plotly.graph_objects as go
from source_loading import start_load,collect_loads,loading
from recorded_profile_values import profile_intervals
from custom_graph import custom_bundle
from test_health42 import data

ROOT=Path(__file__).parents[1]

class Health50Tests(unittest.TestCase):
    def test_export_reordering_stays_inside_the_visible_report_block(self):
        source=(ROOT/'graph_view.py').read_text(encoding='utf-8')
        start=source.index('function reorderScope')
        finish=source.index('async function toggleScale',start)
        script="""const assert=require('assert');let ready=true,syncing=false,reportEditorBlock='summary';
const navigation={export_workspace:true};const panelOrder=[10,11,12,13],panelCards={10:{},11:{},12:{},13:{}};
const states={10:{graphType:'daily',deleted:false},11:{graphType:'summary',deleted:false},12:{graphType:'daily',deleted:false},13:{graphType:'summary',deleted:false}};
const panelStateAt=i=>states[i],reportBlockOf=s=>s.graphType,panels={appendChild:()=>{}},clearHover=()=>{},controls=()=>{};
"""+source[start:finish]+"""
assert.deepEqual(reorderScope(13),[11,13]);movePanel(13,-1);assert.deepEqual(panelOrder,[10,13,12,11]);
assert.deepEqual(reorderScope(13),[13,11]);movePanel(13,-1);assert.deepEqual(panelOrder,[10,13,12,11]);
reportEditorBlock='daily';assert.deepEqual(reorderScope(10),[10,12]);movePanel(12,-1);assert.deepEqual(panelOrder,[12,13,10,11]);
states[10].deleted=true;assert.deepEqual(reorderScope(10),[12]);movePanel(10,1);assert.deepEqual(panelOrder,[12,13,10,11]);
"""
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'reorder.cjs';path.write_text(script,encoding='utf-8')
            result=subprocess.run(['node',str(path)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_custom_profile_steps_connect_jumps_with_a_very_light_shade(self):
        from recorded_profile_values import profile_traces
        loaded,days=data();profile=deepcopy(loaded['recorded_profiles'][0]['profile'])
        profile['carbratio']=[dict(time='00:00',value=10),dict(time='06:00',value=8),dict(time='12:00',value=12)]
        loaded['recorded_profiles'][0]['profile']=profile;loaded['_chart_cache']={}
        trace=profile_traces(loaded,'ic',[days[0]],'One day','mmol/L','#c76b00')[0]
        jump=next(i for i in range(1,len(trace.x)) if trace.x[i]==trace.x[i-1] and trace.y[i-1]!=trace.y[i])
        self.assertEqual([trace.y[jump-1],trace.y[jump]],[10,8])
        self.assertEqual(trace.line.shape,'hv')
        self.assertEqual(trace.fill,'tozeroy');self.assertEqual(trace.fillcolor,'rgba(199,107,0,0.055)')
        self.assertNotIn(None,trace.x[:jump+1])

    def test_standard_sleep_does_not_hide_cached_custom_signal_traces(self):
        from nightscout_charts import dataset_traces,graph_figures
        loaded,days=data()
        graph_figures(go.Figure(),loaded,days,'Median + band',['Garmin · Sleep'],'mmol/L',False)
        traces=dataset_traces('g_sleep_hrv',loaded,days,'Median + band','mmol/L',False)
        self.assertTrue(traces)
        self.assertTrue(all(t.visible is not False for t in traces))
        self.assertTrue(all(not (t.meta or {}).get('sleep_overlay') for t in traces))
        self.assertIn('markers',next(t for t in traces if t.meta['kind']=='median').mode)

    def test_visual_offset_keeps_values_visible_and_is_idempotent(self):
        source=(ROOT/'custom_graph.js').read_text(encoding='utf-8')
        fn=source[source.index('function applyCustomRanges'):source.index('function composeCustom')]
        js="""const assert=require('assert');const field={id:'hr',dataset:'g_workout_hr'},customFields=[field];
const state={selected:new Set(['hr']),fieldOptions:{hr:{visualOffset:0}},axisRanges:{},garmin:{pace:false}};
const customState=()=>state,customAxisKey=()=> 'field:hr',customDisplayField=f=>f,customExtent=vs=>[Math.min(...vs),Math.max(...vs)];
"""+fn+"""
const view={data:[{x:[0,1,2],y:[140,145,150],meta:{dataset:'g_workout_hr'}}],layout:{meta:{kind:'custom',custom_axes:{yaxis:'field:hr'}},xaxis:{range:[0,2]},yaxis:{range:[139,151]}}};
const original=JSON.stringify(view.data);
for(const pace of [false,true])for(const offset of [-90,-30,30,90]){
 state.garmin.pace=pace;field.dataset=pace?'g_workout_speed':'g_workout_hr';view.data[0].meta.dataset=field.dataset;state.fieldOptions.hr.visualOffset=offset;
 const recorded=JSON.stringify(view.data);applyCustomRanges(view);const r=view.layout.yaxis.range.slice();
 assert(view.data[0].y.every(v=>v>=Math.min(...r)&&v<=Math.max(...r)));assert.equal(r[0]>r[1],pace);
 applyCustomRanges(view);assert.deepEqual(view.layout.yaxis.range,r);assert.equal(JSON.stringify(view.data),recorded);
}
"""
        result=subprocess.run(['node','-e',js],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_deleting_settings_is_recoverable_and_does_not_touch_other_files(self):
        from view_config import save_configuration,saved_configurations,delete_configuration
        from report_config import save_preset,presets,delete_preset
        with tempfile.TemporaryDirectory() as folder:
            graph=Path(folder)/'graphs';pdf=Path(folder)/'pdf'
            config=dict(format='profile-studio-view',version=1,layers=['Glucose'],mode='One day',viewer={})
            path=save_configuration('Remove / this',config,graph);original=path.read_bytes()
            keep=save_configuration('Keep',config,graph)
            report=save_preset('Remove / this',dict(blocks=[dict(key='daily')]),pdf);report_original=report.read_bytes()
            save_preset('Keep',dict(blocks=[dict(key='daily')]),pdf)
            self.assertEqual(delete_configuration('Remove / this',graph),1)
            self.assertEqual([name for name,_ in saved_configurations(graph)[0]],['Keep'])
            self.assertEqual(next((graph/'.trash').glob('*.json')).read_bytes(),original)
            self.assertTrue(keep.exists());self.assertTrue(report.exists())
            self.assertEqual(delete_preset('Remove / this',pdf),1)
            self.assertEqual([p['name'] for p in presets(pdf)],['Keep'])
            self.assertEqual(next((pdf/'.trash').glob('*.json')).read_bytes(),report_original)
            with self.assertRaises(ValueError):delete_preset('../Keep',pdf)

    def test_nights_signals_keep_recorded_values_and_share_app_report_layout(self):
        from insights import insight_figures
        loaded,days=data()
        start=pd.Timestamp(str(days[0])+'T22:00Z')
        loaded['data']['g_sleep_movement']=pd.DataFrame([dict(time=start,end=start+pd.Timedelta(hours=12),value=3,label='Movement')])
        figure=insight_figures(loaded,days,'mmol/L',False,{'insight_sleep'})[0]
        signal=figure.layout.meta['sleep_overview_rows'][0]['signals']['g_sleep_movement']
        self.assertEqual(signal['y'],[3,3]);self.assertEqual(signal['x'],[-2,10])
        setup="const assert=require('assert');const navigation={unit:'mmol/L'};\n"
        code=setup+(ROOT/'insights_view.js').read_text(encoding='utf-8')+(ROOT/'sleep_insight_view.js').read_text(encoding='utf-8')+'\nconst view='+figure.to_json()+";\n"+"""
const rows=view.layout.meta.sleep_overview_rows,settings={sleepFields:['g_sleep_hrv','g_sleep_movement'],sleepOverlay:false,overviewAfterHours:0};
renderSleepOverview(view,rows,settings);
const signals=view.data.filter(t=>t.meta?.kind==='sleep_overview_signal'),movement=signals.find(t=>t.meta.dataset==='g_sleep_movement');
assert.deepEqual(movement.y,[3,3]);assert.equal(movement.x.at(-1),rows[0].wake);
assert(view.layout['yaxis'+movement.yaxis.slice(1)].domain[1]<view.layout.yaxis.domain[0]);
const values=signals.map(t=>t.y);renderSleepOverview(view,rows,{...settings,sleepOverlay:true});
assert.deepEqual(view.data.filter(t=>t.meta?.kind==='sleep_overview_signal').map(t=>t.y),values);
assert.deepEqual(view.layout['yaxis'+movement.yaxis.slice(1)].domain,view.layout.yaxis.domain);
renderSleepOverview(view,rows,settings);const reports=reportSleepOverviewViews(view,{height:350});
assert.equal(reports.length,rows.length);assert(reports.every(r=>r.data.some(t=>t.meta?.kind==='sleep_overview_signal')));
assert.deepEqual(reports.flatMap(r=>r.layout.meta.sleep_overview_visible.map(n=>n.date)),rows.map(r=>r.date));
"""
        result=subprocess.run(['node','-e',code],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_imports_run_together_survive_reruns_and_finish_independently(self):
        state={};started=Event();release=Event()
        def nightscout(progress):
            progress(1,2,'Still reading');started.set();release.wait(5);return {'source':'Nightscout'}
        try:
            self.assertTrue(start_load('nightscout',nightscout,state=state));self.assertTrue(started.wait(2))
            self.assertTrue(start_load('garmin',lambda progress:{'source':'Garmin'},state=state))
            state['_source_load_jobs']['garmin'].future.result(timeout=2)
            collect_loads(state);self.assertEqual(state['garmin_loaded']['source'],'Garmin');self.assertTrue(loading('nightscout',state))
            self.assertFalse(start_load('nightscout',lambda progress:None,state=state))
            self.assertEqual(state['_source_load_jobs']['nightscout'].status()[2],'Still reading')
        finally:release.set()
        state['_source_load_jobs']['nightscout'].future.result(timeout=2);collect_loads(state)
        self.assertEqual(state['ns_loaded']['source'],'Nightscout');self.assertFalse(loading('nightscout',state));self.assertFalse(collect_loads(state))

    def test_failed_import_preserves_previous_snapshot_and_other_result(self):
        state={'ns_loaded':{'previous':True}}
        def fail(progress):raise ValueError('Example failure')
        start_load('nightscout',fail,state=state);start_load('garmin',lambda progress:{'ready':True},state=state)
        for job in state['_source_load_jobs'].values():
            try:job.future.result(timeout=2)
            except ValueError:pass
        collect_loads(state);self.assertEqual(state['ns_loaded'],{'previous':True});self.assertTrue(state['garmin_loaded']['ready'])
        self.assertEqual(state['_source_load_jobs']['nightscout'].error,'Example failure')

    def test_effective_profile_values_do_not_reapply_percentage_or_use_editor_draft(self):
        loaded,days=data();record=loaded['recorded_profiles'][0];record.update(percentage=50)
        record['profile']=deepcopy(record['profile']);record['profile']['carbratio'][0]['value']=5
        intervals=profile_intervals(loaded,'carbratio','mmol/L');self.assertEqual(set(intervals.value),{5})
        fake=go.Figure(go.Scatter(x=[0,1440],y=[999,999],meta=dict(kind='profile',unit='g/U'),name='Unsaved draft'));fake.update_layout(title='I:C · draft')
        bundle=custom_bundle(loaded,days,days,'Multiple days','mmol/L',False,{'ic':fake},field_ids={'profile:ic:nightscout','profile:target:nightscout'})
        fields=bundle['fields'];self.assertEqual(len(fields),2)
        for field in fields:
            self.assertEqual(field['source_role'],'nightscout');self.assertTrue(field['daily']);self.assertTrue(all(t['meta']['profile_source']=='nightscout' for t in field['daily']))
        ic=next(f for f in fields if f['id']=='profile:ic:nightscout');self.assertEqual({y for t in ic['daily'] for y in t['y'] if y is not None},{5})
        self.assertEqual(set(profile_intervals(loaded,'sens','mg/dL').value),{36})

    def test_missing_effective_profile_history_stays_empty(self):
        loaded,days=data();loaded['recorded_profiles']=[dict(loaded['recorded_profiles'][0],profile={})]
        self.assertTrue(profile_intervals(loaded,'carbratio','mmol/L').empty)
        fields=custom_bundle(loaded,days,days,'One day','mmol/L',False,{},field_ids={'profile:ic:nightscout'})['fields']
        self.assertEqual(len(fields),1);self.assertEqual(fields[0]['daily'],[])

    def test_custom_summary_can_combine_site_and_sensor_changes(self):
        loaded,days=data();days=days[:2];loaded['availability']={'treatments':True};loaded['loaded_at']=pd.Timestamp(str(days[-1]),tz='UTC')+pd.Timedelta(days=1)
        loaded['data']['changes']=pd.DataFrame([dict(time=pd.Timestamp(str(day)+'T10:20Z'),value=1,label=label) for day,label in [(days[0],'Site Change'),(days[0],'Sensor Start'),(days[1],'Sensor Change')]])
        fields=custom_bundle(loaded,days,days,'Median + band','mmol/L',False,{},field_ids={'summary:site_changes','summary:sensor_changes'})['fields']
        self.assertEqual({f['id'] for f in fields},{'summary:site_changes','summary:sensor_changes'})
        values={f['id']:f['selected'][0]['meta']['hourly_values'] for f in fields}
        self.assertEqual(values['summary:site_changes']['average'][10],.5)
        self.assertEqual(values['summary:sensor_changes']['average'][10],1)

    def test_activity_clock_ticks_and_date_colors_are_shared_across_graphs(self):
        source=(ROOT/'workspace_view.js').read_text(encoding='utf-8');source=source[source.index('function timeAxisTicks'):source.index('function panelSourceView')]
        js="""const assert=require('assert');const navigation={days:['2026-10-12','2026-10-13']},selectedDays=navigation.days;
const effectivePanelMode=()=> 'Multiple days';function rgbaColor(c,a){return c;}
"""+source+"""
const ticks=timeAxisTicks([878,933],700);assert(ticks.ticktext.length>=4);assert(ticks.ticktext.every(t=>/^1[45]:[0-5][0-9]$/.test(t)));assert(!ticks.ticktext.includes('00:00'));
const v={data:[{x:[0,1],y:[2,3],line:{color:'red'},meta:{date:'2026-10-12',dataset:'glucose'}},{x:[0,1],y:[4,5],line:{color:'red'},meta:{date:'2026-10-13',dataset:'glucose'}}],layout:{meta:{}}};
applyOverlayDayColors(v,1);assert.notEqual(v.data[0].line.color,v.data[1].line.color);const colors=v.data.filter(t=>t.meta.day_color).map(t=>t.meta.day_color);applyOverlayDayColors(v,1);assert.deepEqual(v.data.filter(t=>t.meta.day_color).map(t=>t.meta.day_color),colors);assert.equal(v.data.filter(t=>t.meta.kind==='day_legend').length,2);
assert.equal(overlayDateColor('2026-10-12'),colors[0]);
const layout={meta:{},xaxis:{},xaxis2:{},width:700};applyClockTicks(layout,[878,933]);assert.deepEqual(layout.xaxis.ticktext,layout.xaxis2.ticktext);
"""
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'check.cjs';file.write_text(js,encoding='utf-8');r=subprocess.run(['node',str(file)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

if __name__=='__main__':unittest.main()
