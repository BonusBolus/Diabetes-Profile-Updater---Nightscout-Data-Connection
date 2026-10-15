"""Compact event boundaries, color transitions and complete Custom field catalog."""
import json
from pathlib import Path
import subprocess
import unittest
from custom_graph import custom_bundle
from garmin_data import METRICS
from test_health31 import fixture

ROOT = Path(__file__).parents[1]


class Health40Tests(unittest.TestCase):
    def run_js(self, checks):
        setup = "const window={addEventListener(){}};const assert=require('assert');const navigation={unit:'mmol/L'};\n"
        result = subprocess.run(['node','-e',setup+(ROOT/'workspace_view.js').read_text()+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_glucose_lines_split_at_thresholds_and_keep_gaps(self):
        self.run_js("""
const view={data:[{x:[0,5,null,20,25],y:[2,12,null,3,3],mode:'lines+markers',line:{color:'#218c24'},meta:{kind:'glucose',date:'2026-10-01'}}]};
colorGlucoseLines(view);
const point=view.data.find(t=>t.meta.kind==='glucose');
assert.equal(point.mode,'markers');assert.equal(point.marker.color[0],'#f44336');
const lines=view.data.filter(t=>t.meta.kind==='glucose_line');
assert.equal(lines.length,3);assert(lines.every(t=>t.showlegend===false));
for(const t of lines)for(let i=1;i<t.x.length;i++)if(Number.isFinite(t.x[i-1])&&Number.isFinite(t.x[i]))assert(t.x[i]-t.x[i-1]<=5);
const red=lines.find(t=>t.line.color==='#f44336');assert.deepEqual(red.x.slice(0,2),[0,1]);
const orange=lines.find(t=>t.line.color==='#ff9800');assert.deepEqual(orange.x.slice(0,2),[4,5]);
""")

    def test_compact_lanes_and_clipping_are_stable_on_reflow(self):
        self.run_js("""
const l={height:515,width:1000,margin:{l:58,r:24,t:38,b:66},meta:{kind:'compact'},xaxis:{range:[0,1440]},yaxis:{},yaxis4:{},
shapes:[{name:'Activity | day | Running',type:'rect',yref:'paper',y0:0,y1:1},{name:'Change | day',type:'line',yref:'paper',y0:0,y1:1},{name:'compact-tir',y0:0,y1:0}],
annotations:[1000,1004,1010].map(x=>({name:'Effective | '+x,text:'Standard v18 · 80%',xref:'x',yref:'paper',x,y:-.001,font:{size:10}}))};
compactLayout(l,650);assert.equal(l.meta.profile_label_levels,3);
assert(l.annotations.every(a=>a.y<l.yaxis4.domain[0]&&a.y>l.shapes[2].y1));
assert(l.shapes.slice(0,2).every(s=>s.y0===l.yaxis4.domain[0]&&s.y1===l.yaxis.domain[1]));
const before=JSON.stringify(l);compactLayout(l,650);assert.equal(JSON.stringify(l),before);
l.meta.compact_automation=true;compactLayout(l,650);assert.equal(l.shapes[0].y1,.9);assert(l.shapes[2].y1<l.yaxis4.domain[0]);
""")

    def test_custom_catalog_includes_unloaded_supported_garmin_fields(self):
        loaded, days = fixture()
        catalog = custom_bundle(loaded,days,days,'One day','mmol/L',False,{})
        ids = {f['id'] for f in catalog['fields']}
        self.assertTrue({'garmin:'+k for k in METRICS if k!='g_activity'} <= ids)
        self.assertTrue({'ns:glucose','ns:bolus','ns:carbs','ns:target','ns:variable_sens'} <= ids)
        power = next(f for f in catalog['fields'] if f['id']=='garmin:g_workout_power')
        self.assertEqual(power['daily'],[])


if __name__ == '__main__':
    unittest.main()
