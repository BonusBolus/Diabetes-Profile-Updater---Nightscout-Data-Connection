"""Crowded compact carb labels share the downward bolus placement rules."""
import unittest
import test_health41


class Health43Tests(unittest.TestCase):
    js=test_health41.Health41Tests.js
    def test_dense_carb_labels_extend_down_without_changing_marker_data(self):
        self.js("""
for(const [width,height] of [[900,570],[420,570],[1200,760]]){
 const view={layout:{height,margin:{l:58,r:24,t:38,b:66},meta:{kind:'compact'},xaxis:{range:[0,1440]},
 yaxis:{domain:[.34,1],range:[0,20]},yaxis2:{range:[0,20]},yaxis3:{range:[100,0]},yaxis4:{domain:[.14,.29]},annotations:[]},
 data:[{x:[480,482,484,486,1100],y:[20,20,20,20,20],text:['20 g','20 g','20 g','20 g','20 g'],yaxis:'y3',meta:{kind:'carbs'},customdata:[[20],[20],[20],[20],[20]]}]};
 const original=JSON.stringify(view.data.map(t=>[t.x,t.y,t.customdata]));
 compactAmountLabels(view,width);
 const labels=view.layout.annotations;
 assert(labels.some(a=>!a.showarrow));assert(labels.some(a=>a.showarrow));
 assert(labels.filter(a=>a.showarrow).every(a=>a.ay>0&&a.ax>=0&&a.ax<=24));
 assert(labels.filter(a=>a.showarrow).some(a=>a.ax===0));
 assert.equal(JSON.stringify(view.data.map(t=>[t.x,t.y,t.customdata])),original);
 const before=JSON.stringify(labels);compactAmountLabels(view,width);assert.equal(JSON.stringify(view.layout.annotations),before);
 view.layout.meta.compact_amount_labels=false;compactAmountLabels(view,width);
 assert.equal(view.layout.annotations.length,0);assert.equal(view.data[0].mode,'markers');
}
""")
