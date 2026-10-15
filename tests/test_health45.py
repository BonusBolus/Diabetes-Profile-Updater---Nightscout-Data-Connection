"""PDF automation labels preserve events while avoiding crowded text."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).parents[1]


class Health45Tests(unittest.TestCase):
    def test_pdf_note_labels_and_crowded_key_preserve_unicode_and_event_scope(self):
        source=(ROOT/'garmin_view.js').read_text()
        source=source[source.index('function eventAllowed'):source.index('function eventScopeControl')]+source[source.index('function profileLineStyle'):]
        setup="""
const assert=require('assert'),window={addEventListener(){}},panelStates=new Map();
const document={createElement:()=>({getContext:()=>({measureText:s=>({width:Array.from(s).length*4})})})};
const selectedDays=['2026-10-01'],eventScopes={automation:'all'};
const navigation={report_render:{compact:true},automation_notes:[
 {date:selectedDays[0],minute:600,label:'🏃 Exercise'},
 {date:selectedDays[0],minute:602,label:'Meal reminder'},
 {date:selectedDays[0],minute:604,label:'♥ Check & confirm'},
 {date:selectedDays[0],minute:610,label:'Very long note '.repeat(50)}]};
"""
        checks="""
const v={data:[],layout:{height:250,width:700,margin:{l:60,r:60,t:20,b:40},
 meta:{dataset:'glucose'},xaxis:{range:[0,1440]},yaxis:{domain:[0,1]},shapes:[],annotations:[]}};
applyAutomationNotes(v);
assert.equal(v.data.filter(t=>t.meta.kind==='automation_note').length,4);
assert(v.layout.annotations.some(a=>a.text.includes('🏃')));
assert(v.layout.annotations.filter(a=>a.showarrow).every(a=>a.ay>0&&a.ax>=0&&a.ax<=24));
assert(v.layout.meta.automation_print_key.includes('♥ Check & confirm'));
assert(v.layout.meta.automation_print_key.includes('Very long note'));
const once=JSON.parse(JSON.stringify(v));applyAutomationNotes(v);assert.deepEqual(JSON.parse(JSON.stringify(v)),once);
eventScopes.automation='off';applyAutomationNotes(v);
assert.equal(v.data.length,0);assert.equal(v.layout.annotations.length,0);assert.deepEqual(v.layout.yaxis.domain,[0,1]);
"""
        result=subprocess.run(['node','-e',setup+(ROOT/'workspace_view.js').read_text()+source+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
