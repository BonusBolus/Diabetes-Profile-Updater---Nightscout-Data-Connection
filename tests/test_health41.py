"""Shared compact event lanes, downward dose labels and sidebar config access."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parents[1]


class Health41Tests(unittest.TestCase):
    def js(self, checks):
        setup = "const window={addEventListener(){}};const assert=require('assert');const navigation={unit:'mmol/L'};\n"
        result = subprocess.run(['node','-e',setup+(ROOT/'workspace_view.js').read_text()+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_mixed_event_labels_share_lanes_on_resize_and_zoom(self):
        self.js("""
const l={height:515,margin:{l:58,r:24,t:38,b:66},meta:{kind:'compact'},xaxis:{range:[0,1440]},yaxis:{},yaxis4:{},
shapes:[{name:'Change | day',type:'line',yref:'paper',y0:0,y1:1},{name:'compact-tir',y0:0,y1:0}],
annotations:[['Effective | a','Standard v18 · 80%'],['Change | b','Site 17:24'],['Change | c','Sensor 17:30']].map(([name,text],i)=>({name,text,xref:'x',yref:'paper',x:1040+i*4,y:.94}))};
for(const width of [1000,650,400]){
 compactLayout(l,width);assert.equal(new Set(l.annotations.map(a=>a.y)).size,3);
 assert(l.annotations.every(a=>a.y<l.yaxis4.domain[0]&&a.y>l.shapes[1].y1));
 assert.equal(l.shapes[0].y0,l.yaxis4.domain[0]);
 const before=JSON.stringify(l);compactLayout(l,width);assert.equal(JSON.stringify(l),before);
}
l.xaxis.range=[0,600];compactLayout(l,650);assert(l.annotations.every(a=>a.visible===false));
assert.equal(l.meta.profile_label_levels,0);
""")

    def test_bolus_leaders_downward_and_labels_can_be_hidden(self):
        self.js("""
const view={layout:{height:570,margin:{l:58,r:24,t:38,b:66},meta:{kind:'compact'},xaxis:{range:[0,1440]},yaxis:{domain:[.34,1],range:[0,20]},yaxis2:{range:[0,20]},yaxis3:{range:[100,0]},yaxis4:{domain:[.14,.29]},annotations:[]},data:[
{x:[480,482,484,486,1100],y:[2,2,2,2,2],text:['2 U','2 U','2 U','2 U','2 U'],yaxis:'y2',meta:{kind:'bolus'},customdata:[[2],[2],[2],[2],[2]]},
{x:[800],y:[40],text:['40 g'],yaxis:'y3',meta:{kind:'carbs'},customdata:[[40]]}]};
const original=JSON.stringify(view.data.map(t=>[t.x,t.y,t.customdata]));
compactAmountLabels(view,900);
const bolus=view.layout.annotations.filter(a=>a.name.startsWith('compact-dose-bolus'));
assert(bolus.some(a=>!a.showarrow));assert(bolus.some(a=>a.showarrow));
assert(bolus.filter(a=>a.showarrow).every(a=>a.ay>0&&a.ax>=0&&a.ax<=24));
assert(bolus.filter(a=>a.showarrow).some(a=>a.ax===0));
view.layout.meta.compact_amount_labels=false;compactAmountLabels(view,900);
assert.equal(view.layout.annotations.length,0);assert(view.data.every(t=>t.mode==='markers'));
assert.equal(JSON.stringify(view.data.map(t=>[t.x,t.y,t.customdata])),original);
view.layout.meta.compact_amount_labels=true;compactAmountLabels(view,900);assert(view.layout.annotations.length>0);
""")

    def test_saved_config_accessible_before_loading_data(self):
        config=dict(format='profile-studio-view',version=1,layers=['Glucose'],mode='One day',viewer={'panels':[]})
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ',PROFILE_STUDIO_DATA=folder), patch('view_config.saved_configurations',return_value=([('My view',config)],[])):
            at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=40).run()
            self.assertFalse(at.exception)
            keys=[b.key for b in at.sidebar.button]
            self.assertEqual(keys[keys.index('workspace_add_graph')+1],'health_saved_config_0')
            with patch('nightscout_ui.load_nightscout') as ns,patch('garmin_ui.load_garmin') as garmin:
                at.button(key='health_saved_config_0').click().run()
                self.assertFalse(at.exception)
                self.assertEqual(at.session_state.health_view_config['panels'],[])
                ns.assert_not_called();garmin.assert_not_called()


if __name__=='__main__':unittest.main()
