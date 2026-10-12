"""Independent profile history, visible switch labels and bounded sleep stacks."""
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
import subprocess
import unittest
import numpy as np
import pandas as pd
from nightscout import load_nightscout
from garmin_charts import hourly_sleep_distribution,garmin_traces

class Health29Tests(unittest.TestCase):
    def test_profile_history_loaded_without_treatment_selection(self):
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        profile={'units':'mmol/L','basal':[{'time':'00:00','value':1}]}
        effective={'created_at':start.isoformat(),'originalProfileName':'Standard v18','originalPercentage':80,'profileJson':profile}
        requested=dict(effective,eventType='Profile Switch',originalPercentage=100)
        def records(collection,a,b,filters=None):
            if collection=='entries/sgv':return []
            self.assertEqual(collection,'treatments')
            return [requested] if filters=={'find[eventType]':'Profile Switch'} else [effective]
        with patch('nightscout.NightscoutClient') as factory:
            client=factory.return_value;client.url='https://example.test';client.get.return_value=[];client.records.side_effect=records
            for categories in (['glucose'],[]):
                snapshot=load_nightscout(client.url,'',start.date(),start.date(),'UTC',categories=categories)
                self.assertFalse(snapshot['availability']['treatments'])
                self.assertTrue(snapshot['availability']['profiles'])
                self.assertEqual(snapshot['recorded_profiles'][0]['name'],'Standard v18')
                self.assertEqual(snapshot['recorded_profiles'][0]['percentage'],80)
                self.assertEqual(snapshot['recorded_profiles'][0]['base_profile'],profile)
                self.assertTrue(snapshot['data']['changes'].empty)
            client.reset_mock();client.records.side_effect=lambda *a,**k:[effective,requested] if a[0]=='treatments' else []
            load_nightscout(client.url,'',start.date(),start.date(),'UTC',categories=['treatments'])
            self.assertEqual(client.records.call_count,1,'Reuse a full treatment import for profiles')

    def test_median_sleep_stages_preserve_median_asleep_total(self):
        start=pd.Timestamp('2026-01-01T00:00Z');days=[(start+pd.Timedelta(days=i)).date() for i in range(3)]
        rows=[]
        for i,stage in enumerate(['deep_sleep','light_sleep','rem_sleep']):
            rows.append(dict(time=start+pd.Timedelta(days=i,hours=2),end=start+pd.Timedelta(days=i,hours=3),stage=stage,value=i,label=stage))
        frame=pd.DataFrame(rows);stats,count=hourly_sleep_distribution(frame,days,'UTC')
        self.assertEqual(count,3);self.assertEqual(stats.attrs['median'][2],60)
        self.assertEqual(sum(v[2] for v in stats.attrs['median_stages'].values()),60)
        traces=garmin_traces('g_sleep',dict(data={'g_sleep':frame},zone='UTC'),days,'Median + band')
        for aggregation in ['Average','Median']:
            bars=[t for t in traces if t.meta.get('aggregation')==aggregation]
            self.assertEqual(len(bars),3)
            self.assertTrue(all(len(t.x)==24 and t.width==54 for t in bars))
            total=np.sum([t.y for t in bars],axis=0)
            self.assertAlmostEqual(total[2],1);self.assertTrue(np.all(total<=1))
            self.assertEqual(len({t.name for t in bars}),3)
        self.assertTrue(all('recorded stage share' in t.hovertemplate for t in bars))

    def test_profile_labels_reflow_at_narrow_width(self):
        code=(Path(__file__).parents[1]/'garmin_view.js').read_text();code=code[code.index('function profileEventLayout'):]
        context="""const assert=require('assert');const annotations=[];
for(let i=0;i<3;i++){annotations.push({name:'Effective | '+i,x:600+i*20,y:-.001,text:'LenStandardV18',font:{size:10}});annotations.push({name:'Effective | '+i,x:600+i*20,y:1.015,text:'80%',font:{size:10}});}
const layout={height:400,width:1400,margin:{l:62,r:62,t:36,b:62},meta:{},xaxis:{range:[0,1440]},annotations};
"""
        check="""profileEventLayout(layout);layout.width=430;profileEventLayout(layout);
const names=layout.annotations.filter(a=>a.y<0);assert.equal(new Set(names.map(a=>a.yshift)).size,3);assert(names.every(a=>a.xanchor==='left'));
assert.equal(layout.meta.profile_label_levels,3);assert(layout.margin.b>=100);
for(const a of names){const p=annotations.find(v=>v.name===a.name&&v.y>1);assert.equal(p.xshift,a.xshift);}
"""
        r=subprocess.run(['node','-e',context+code+check],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_nonaggregate_panels_keep_multiple_days_without_mode_control(self):
        source=(Path(__file__).parents[1]/'panel_view.js').read_text()
        source=source[source.index('function panelHasMedian'):source.index('function panelModeControls')]
        context="""const assert=require('assert');const selectedDays=['2026-01-01','2026-01-02'];const dateCycled=false;const currentOverlay='Glucose';
const specs=[{layout:{meta:{dataset:'target'}}},{layout:{meta:{dataset:'glucose'}}},{layout:{meta:{kind:'custom',custom_id:'custom-1'}}}];
function panelStateAt(){return {mode:'Median + band'};}function customState(){return {selected:new Set(['ns:target','profile:basal:0'])};}
"""
        check="""assert(!panelHasMedian(specs[0]));assert(panelHasMedian(specs[1]));assert(!panelHasMedian(specs[2]));
assert.equal(effectivePanelMode(0),'Multiple days');assert.equal(effectivePanelMode(1),'Median + band');assert.equal(effectivePanelMode(2),'Multiple days');
assert(!panelHasMedian({layout:{meta:{kind:'hourly'}}}));
"""
        r=subprocess.run(['node','-e',context+source+check],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

if __name__=='__main__':unittest.main()
