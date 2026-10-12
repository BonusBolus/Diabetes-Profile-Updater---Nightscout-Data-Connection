"""Independent event scopes, aligned overlay statistics and graph restoration."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from test_nightscout import sample_data
from nightscout_ui import graph_layer

ROOT=Path(__file__).parents[1]


def js_check(setup,files,checks):
    result=subprocess.run(['node','-e',setup+'\n'+'\n'.join((ROOT/p).read_text() for p in files)+'\n'+checks],capture_output=True,text=True)
    if result.returncode:raise AssertionError(result.stderr)


class Health37Tests(unittest.TestCase):
    def test_overlay_statistics_bands_gaps_color_and_domain(self):
        setup="""const assert=require('assert');const navigation={unit:'mmol/L'};function applyPanelRanges(){};
let state={base:'asymmetric',mode:'Median + band',insight:{aggregation:'Median',normalization:'absolute',duration:6,showIOB:true,showCOB:true}};function panelStateAt(){return state;}
const series=[1,2,9].map((v,i)=>({id:i,label:'event '+i,x:[0,5,null,15],glucose:[5,6,null,7],baseline:5,
context:{iob:{x:[0,5,null,15],value:[v,v+1,null,v+2]},cob:{x:[0,5,null,15],value:[v*10,v*10+5,null,v*10+10]}}}));
const original=JSON.stringify(series);
function render(){const v={data:[],layout:{meta:{insight:'activity_after',dataset:'insight_activity_after',series},title:{text:'After activity'},xaxis:{},yaxis:{},shapes:[],margin:{}}};transformInsight(v,0);return v;}
"""
        checks="""
let v=render(),curves=v.data.filter(t=>t.meta.kind==='insight_context');assert.deepEqual(curves.map(t=>t.y[0]),[2,20]);assert(curves.every(t=>t.opacity<.8&&t.meta.aggregation==='Median'));assert(curves.every(t=>t.y[2]===null));
let bands=v.data.filter(t=>t.meta.kind==='insight_context_band');assert.equal(bands.length,4);assert(bands.every(t=>t.fill==='toself'));assert.deepEqual(bands.filter(t=>t.meta.dataset==='iob')[0].y,[1.5,2.5,6.5,5.5]);assert.equal(bands.filter(t=>t.meta.dataset==='iob')[1].x.length,4,'One-bin band has width and no gap bridging');
assert.equal(v.layout.shapes.find(s=>s.name==='Insight glucose range').xref,'x domain');assert.deepEqual(v.layout.xaxis.domain,[0,.8]);assert(v.data.filter(t=>t.meta.kind==='insight_band').every(t=>t.fillcolor==='rgba(50,205,50,.18)'));assert.equal(v.data.find(t=>t.meta.kind==='insight_median').line.color,'#32cd32');
state.insight.aggregation='Average';v=render();curves=v.data.filter(t=>t.meta.kind==='insight_context');assert.deepEqual(curves.map(t=>t.y[0]),[4,40]);assert(curves.every(t=>t.name.startsWith('Average')));assert(v.layout.meta.insight_note.includes('IOB/COB averages'));
state.insight.normalization='delta';v=render();assert.equal(v.data.find(t=>t.meta.kind==='insight_context'&&t.meta.dataset==='iob').y[0],4);assert(!v.layout.shapes.some(s=>s.name==='Insight glucose range'));
state.insight.showIOB=false;state.insight.showCOB=false;state.insight.normalization='absolute';v=render();assert.deepEqual(v.layout.xaxis.domain,[0,1]);assert(!v.data.some(t=>t.meta.kind.startsWith('insight_context')));
assert.equal(JSON.stringify(series),original);
"""
        js_check(setup,['insights_view.js'],checks)

    def test_all_event_scopes_in_daily_median_custom_and_histogram(self):
        setup="""const assert=require('assert');let dateCycled=false,selectedDays=['2026-09-25','2026-09-26'];
const navigation={unit:'mmol/L',automation_notes:[{date:selectedDays[0],minute:600,label:'Test'},{date:'2026-09-24',minute:600,label:'Out'}],
change_events:[{date:selectedDays[0],minute:610,label:'Site Change'},{date:selectedDays[1],minute:620,label:'Sensor Start'}],
profile_events:[{date:selectedDays[0],minute:630,name:'Standard',percentage:80,intervals:[{date:selectedDays[0],start:630,end:650}]}],
activity_bands:[{name:'Activity | '+selectedDays[0]+' | Running',type:'rect',x0:600,x1:650,y0:0,y1:1,yref:'paper',label:{text:'Running'}}]};
function view(dataset,mode,kind=''){return {data:dataset==='custom'?[{meta:{kind:'median',dataset:'glucose'}}]:[],layout:{meta:{dataset,kind,display_mode:mode},xaxis:{range:[0,1440]},yaxis:{},shapes:[],annotations:[],margin:{}}};}
"""
        checks="""
for(const mode of ['One day','Median + band','Multiple days'])for(const scope of ['off','glucose','all']){
 for(const key of Object.keys(eventScopes))eventScopes[key]=scope;
 for(const dataset of ['glucose','iob','custom']){
 const v=view(dataset,mode);applyActivityShading(v);applyChangeEvents(v,1);applyProfileEvents(v);applyAutomationNotes(v,1);
 const expected=scope==='all'||scope==='glucose'&&dataset!=='iob';
 assert.equal(v.data.filter(t=>t.meta?.kind==='automation_note').length,expected?1:0,mode+' '+scope+' '+dataset);
 assert.equal(v.layout.shapes.filter(s=>s.name?.startsWith('Change | ')).length,expected?2:0);
 assert.equal(v.layout.shapes.filter(s=>s.name?.startsWith('Activity | ')).length,expected?1:0);
 assert.equal(v.layout.shapes.filter(s=>s.type==='line'&&s.name?.startsWith('Profile · ')).length,expected?1:0);
 assert.equal(v.layout.shapes.filter(s=>s.name?.startsWith('Effective | ')&&s.type==='rect').length,expected?1:0);
 }
}
restoreEventScopes({changeScope:'all',automationScope:'glucose',eventOptions:{site:false,sensor:true,profiles:true,percentage:false},garmin:{activityShading:false}});assert.deepEqual(eventScopes,{site:'off',sensor:'all',profiles:'all',percentage:'off',automation:'glucose',activity:'off'});
restoreEventScopes({eventScopes:{site:'glucose',sensor:'all',profiles:'off',percentage:'glucose',automation:'all',activity:'all'}});assert.equal(eventScopes.percentage,'glucose');
eventScopes.site='glucose';eventScopes.sensor='all';eventScopes.automation='all';const v=view('iob','Median + band');applyChangeEvents(v,1);assert.equal(v.layout.shapes.length,1);assert(v.layout.shapes[0].name.includes('Sensor'));
eventScopes.activity='all';navigation.activity_bands.push({...navigation.activity_bands[0],name:'Activity | '+selectedDays[1]+' | Cycling',label:{text:'Cycling'}});const grouped=view('glucose','Median + band');applyActivityShading(grouped);assert.equal(grouped.layout.shapes.length,2);assert.equal(grouped.layout.shapes[0].label.text,'Running / Cycling · 2 dates');assert.equal(grouped.layout.shapes[1].label.text,'');
const hourly=view('carbs','Median + band','hourly');applyAutomationNotes(hourly,1);assert.equal(hourly.data.length,1);
const insight=view('insight_meal','Median + band','insight');insight.layout.meta.non_time=true;applyAutomationNotes(insight,1);applyChangeEvents(insight,1);applyProfileEvents(insight);applyActivityShading(insight);assert.equal(insight.data.length,0);assert.equal(insight.layout.shapes.length,0);
"""
        js_check(setup,['garmin_view.js'],checks)

    def test_restoration_retains_settings_and_consumes_request_once(self):
        setup="""const assert=require('assert');const garminOptions={},hourlyModes={},excludeSMB=false,currentOverlay='None',currentMetric='ic';
const specs=[{data:[],layout:{meta:{dataset:'glucose'},title:{text:'Glucose · dates'}}}];let appliedRestoreRevision=0;const navigation={restore_graph:{id:':glucose',revision:1}};
"""
        checks="""
const state=ensurePanelState(specs[0]);state.deleted=true;state.hourly='Median';state.axisRanges={yaxis:[4,14]};
assert.deepEqual(hiddenGraphCatalog(),[{id:':glucose',base:':glucose',label:'Glucose'}]);applyGraphRestore();assert(!state.deleted);assert.equal(state.hourly,'Median');assert.deepEqual(state.axisRanges,{yaxis:[4,14]});
state.deleted=true;applyGraphRestore();assert(state.deleted,'An old restore request must not undo a later delete');navigation.restore_graph.revision=2;applyGraphRestore();assert(!state.deleted);
dormantPanelStates=[{id:'hidden',base:'hourly:carbs',title:'Carbs hourly',deleted:true}];navigation.restore_graph={id:'hidden',revision:3};applyGraphRestore();assert(!dormantPanelStates[0].deleted);
"""
        js_check(setup,['panel_view.js'],checks)
        for base,label in [(':glucose','Glucose'),('hourly:carbs','COB + Carbs'),('hourly:bolus','IOB + Boluses'),('hourly:site_changes','Site changes'),(':g_workout_power','Garmin · Activity'),('insight:insight_meal','Meal-response glucose'),('custom:Custom graph','Custom graph'),('profile:settings',None)]:
            self.assertEqual(graph_layer(base),label)

    def test_report_sleep_chunks_rebuild_event_axes_for_each_date(self):
        setup="""const assert=require('assert');let selectedDays=['2026-09-25','2026-09-26'],dateCycled=false;
const navigation={sleep_day_height:28,automation_notes:selectedDays.map(date=>({date,minute:600,label:'Note'})),change_events:[],profile_events:[],activity_bands:[]};
function graphOptions(){return garminOptions;}function garminAxes(){};
"""
        checks="""eventScopes.automation='all';garminOptions.sleepFields=[];
const graph={data:selectedDays.map(date=>({type:'scatter',x:[600,660],y:[1,1],line:{width:20},meta:{kind:'garmin_sleep',dataset:'g_sleep',date}})),layout:{meta:{dataset:'g_sleep'},xaxis:{range:[0,1440]},yaxis:{domain:[0,1]},shapes:[],annotations:[],title:{text:'Sleep'},margin:{}}};
composeSleep(graph);applyAutomationNotes(graph);const pages=reportSleepViews(graph,{height:100,capacity:1});assert.equal(pages.length,2);
for(const view of pages){const notes=view.data.filter(t=>t.meta?.kind==='automation_note');assert.equal(notes.length,1);assert.equal(notes[0].meta.date,view.data.find(t=>t.meta?.kind==='garmin_sleep').meta.date);const axis=view.layout['yaxis'+notes[0].yaxis.slice(1)];assert.deepEqual(axis.domain,[.93,1]);assert.deepEqual(view.layout.yaxis.domain,[0,.9]);}
assert.deepEqual(selectedDays,['2026-09-25','2026-09-26']);
"""
        js_check(setup,['garmin_view.js','report_ui.js'],checks)

    def test_sidebar_restoration_does_not_reload_sources(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'PROFILE_STUDIO_DATA':folder}):
            for path in (ROOT/'data/profiles').glob('*.json'):shutil.copyfile(path,Path(folder)/path.name)
            at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run();self.assertFalse(at.exception)
            ns=sample_data();at.session_state.ns_loaded=ns;at.session_state.ns_layers=['Glucose'];at.session_state.health_hidden_graphs=[dict(id=':glucose',base=':glucose',label='Glucose')]
            with patch('nightscout_ui.load_nightscout') as fetch,patch('garmin_ui.load_garmin') as read,patch('graph_view.render_graphs'):
                at.radio(key='page').set_value('Data').run();self.assertFalse(at.exception)
                at.selectbox(key='health_add_graph').select(':glucose').run();self.assertFalse(at.exception)
                self.assertEqual(at.session_state.health_restore_graph,dict(id=':glucose',revision=1));self.assertEqual(at.session_state.health_hidden_graphs,[])
                self.assertIs(at.session_state.ns_loaded,ns);fetch.assert_not_called();read.assert_not_called()

if __name__=='__main__':unittest.main()
