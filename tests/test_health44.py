"""Unified profile-switch text, stacking and percentage shading across graph types."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).parents[1]


class Health44Tests(unittest.TestCase):
    def test_unified_switch_labels_in_daily_summary_custom_and_compact(self):
        source=(ROOT/'garmin_view.js').read_text()
        source=source[source.index('function eventAllowed'):source.index('function eventScopeControl')]+source[source.index('function profileLineStyle'):]
        setup="""
const assert=require('assert'),window={addEventListener(){}},panelStates=new Map();
const selectedDays=['2026-10-01','2026-10-02'],eventScopes={profiles:'all',percentage:'all'};
const navigation={unit:'mmol/L',profile_events:[80,100,120,90].map((percentage,i)=>({name:i===2?'Drinking v19':'Standard v18',
percentage,date:selectedDays[i%2],minute:600+i*3,intervals:[{date:selectedDays[i%2],start:600+i*3,end:700}]}))};
"""
        checks="""
for(const kind of ['','custom','compact'])for(const mode of ['One day','Median + band','Multiple days']){
 const v={data:[],layout:{height:515,width:1000,margin:{l:58,r:24,t:38,b:66},meta:{kind,display_mode:mode},
 xaxis:{range:[0,1440]},yaxis:{},...(kind==='compact'?{yaxis4:{}}:{}),shapes:[],annotations:[]}};
 applyProfileEvents(v);
 assert.deepEqual(v.layout.annotations.map(a=>a.text),['Standard v18 · 80%','Standard v18 · 100%','Drinking v19 · 120%','Standard v18 · 90%']);
 assert(!v.layout.annotations.some(a=>a.y>1));assert.equal(v.layout.meta.profile_label_levels,4);
 assert.equal(new Set(v.layout.annotations.map(a=>kind==='compact'?a.y:a.yshift)).size,4);
 const rects=v.layout.shapes.filter(s=>s.type==='rect');assert.equal(rects.length,3);assert(rects.every(s=>s.fillcolor==='rgba(153,102,204,.14)'));
 const previous=JSON.stringify(v.layout.annotations);applyProfileEvents(v);assert.equal(JSON.stringify(v.layout.annotations),previous);
 const legends=v.layout.shapes.filter(s=>s.type==='line'&&s.showlegend);assert.equal(legends.length,2);assert.notEqual(legends[0].line.dash,legends[1].line.dash);
 if(kind!=='compact'){
  v.layout.xaxis.range=[0,500];profileEventLayout(v.layout,500);assert(v.layout.annotations.every(a=>a.visible===false));
  v.layout.xaxis.range=[0,1440];profileEventLayout(v.layout,500);assert(v.layout.annotations.every(a=>a.visible===true));
 }
}
navigation.report_render={reserve_automation:true,compact:true};eventScopes.automation='all';
const empty={data:[],layout:{height:126,margin:{t:20,b:40},meta:{},yaxis:{domain:[0,1]},shapes:[],annotations:[]}};
applyAutomationNotes(empty,0);const domain=JSON.stringify(empty.layout.yaxis.domain);
applyAutomationNotes(empty,0);assert.equal(JSON.stringify(empty.layout.yaxis.domain),domain,'An empty reserved note strip must not shrink the plot twice');
eventScopes.automation='off';applyAutomationNotes(empty,0);assert.deepEqual(empty.layout.yaxis.domain,[0,1]);
"""
        result=subprocess.run(['node','-e',setup+(ROOT/'workspace_view.js').read_text()+source+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_report_keeps_local_time_for_data_switches_and_notes(self):
        import pandas as pd
        import plotly.graph_objects as go
        from test_health42 import data
        from graph_view import navigation_bundle
        from report_export import graph_bundle
        loaded,days=data();loaded['zone']='Europe/Amsterdam'
        at=pd.Timestamp(str(days[0])+'T05:25Z')
        loaded['recorded_profiles'][0].update(start=at.isoformat(),active_at=at.isoformat())
        loaded['data']['automation_notes']=pd.DataFrame([dict(time=at,value=1,label='Automation: Test')])
        profile=go.Figure();profile.update_layout(title='Basal')
        nav=navigation_bundle(profile,dict(loaded=loaded,days=[days[0]],mode='One day',layers=['Glucose'],overlay='None',data_only=True),'mmol/L',False)
        config=dict(workspaceVersion=2,panels=[dict(id=':glucose',base=':glucose',graphType='daily')])
        bundle=graph_bundle(loaded,nav,config,[days[0]],[360,600],'One day','timezone-test',block='daily')
        self.assertEqual(bundle['navigation']['profile_events'][0]['minute'],445)
        self.assertEqual(bundle['navigation']['automation_notes'],nav['automation_notes'])
        self.assertEqual(bundle['navigation']['automation_notes'][0]['minute'],445)
        xs=[x for spec in bundle['specs'] for t in spec['data'] if t.get('meta',{}).get('kind')=='glucose' for x in t['x']]
        self.assertIn(445,xs)
        self.assertEqual(bundle['navigation']['report_render']['range'],[360,600])
