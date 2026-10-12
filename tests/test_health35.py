import json
from pathlib import Path
import subprocess
import unittest
import pandas as pd
from nightscout import normalize_data
from insights import aligned_series,insight_figures
from test_health31 import fixture

class Health35Tests(unittest.TestCase):
    def test_explicit_note_tag_only_valid_unique_records(self):
        start=pd.Timestamp('2026-09-25T00:00Z');end=start+pd.Timedelta(days=1)
        rows=[dict(_id='a',created_at=start.isoformat(),eventType='Note',notes='Automation: Morning'),
              dict(_id='b',created_at=start.isoformat(),eventType='Announcement',notes=' automation: Evening '),
              dict(_id='c',created_at=start.isoformat(),notes='ordinary note'),
              dict(_id='d',created_at=start.isoformat(),notes='Automation: '),
              dict(_id='e',created_at=start.isoformat(),notes='Automation: invalid',isValid=False),
              dict(_id='f',created_at=end.isoformat(),notes='Automation: outside'),
              dict(_id='g',created_at='invalid',notes='Automation: invalid timestamp')]
        rows.extend([rows[0],dict(_id='h',created_at=start.isoformat(),notes='Automation: Morning')])
        data,_=normalize_data([],rows,[],start,end)
        self.assertEqual(data['automation_notes'].label.tolist(),['Morning','Evening'])

    def test_context_own_sampling_gaps_windows_and_start_cob(self):
        loaded,days=fixture();at=loaded['data']['carbs'].time.iloc[0]
        loaded['data']['cob']=pd.DataFrame([dict(time=at+pd.Timedelta(minutes=m),value=v,label='COB') for m,v in [(-5,80),(1,75),(6,70),(30,55),(119,20),(120,25)]])
        loaded['data']['iob']=pd.DataFrame([dict(time=at+pd.Timedelta(minutes=m),value=v,label='IOB') for m,v in [(2,-.5),(7,.2),(120,1)]])
        periods=aligned_series(loaded,days,'meal','mmol/L')
        self.assertEqual(periods[0]['meal']['cob'],80)
        self.assertEqual(periods[0]['context']['cob']['x'],[1,6,None,30,None,119])
        self.assertEqual(periods[0]['context']['iob']['x'],[2,7])
        self.assertEqual(periods[0]['context']['iob']['value'],[-.5,.2])
        self.assertEqual(periods[1]['context']['cob']['x'],[0])
        self.assertEqual(periods[0]['duration'],120)

    def test_shared_context_medians_filter_counts_axes_and_delta(self):
        loaded,days=fixture();meta=insight_figures(loaded,days,'mmol/L',False,{'insight_meal'})[0].layout.meta
        for i,s in enumerate(meta['series']):
            s['context']={'iob':{'x':[1,6,None,30],'value':[i+1,i+2,None,i+3]},'cob':{'x':[2,7],'value':[20*(i+1),10*(i+1)]}}
        src=Path('insights_view.js').read_text()
        setup="const assert=require('assert');const navigation={unit:'mmol/L'};function applyPanelRanges(){};let state={base:'context',mode:'Median + band',insight:{duration:6,showIOB:true,showCOB:true,minCarbs:20,aggregation:'Average',normalization:'absolute'}};function panelStateAt(){return state;}const meta="+json.dumps(meta)+";function render(){const v={data:[],layout:{meta:JSON.parse(JSON.stringify(meta)),xaxis:{},yaxis:{},margin:{}}};transformInsight(v,0);return v;}\n"
        checks="""
let v=render();let t=v.data.find(t=>t.meta.dataset==='iob' && t.meta.kind==='insight_context');assert.equal(t.y[0],2);assert.equal(t.customdata[0],2);assert.equal(t.y[2],null);assert.equal(t.meta.unit,'U');assert.equal(t.yaxis,'y2');assert.deepEqual(v.layout.yaxis.range,[0,20]);assert.equal(v.layout.yaxis3.title.text,'COB (g)');
state.insight.showIOB=false;v=render();assert(!v.data.some(t=>t.meta.dataset==='iob' && t.meta.kind==='insight_context'));assert.equal(v.data.find(t=>t.meta.dataset==='cob' && t.meta.kind==='insight_context').yaxis,'y2');
state.insight.normalization='delta';v=render();assert.equal(v.data.find(t=>t.meta.dataset==='cob' && t.meta.kind==='insight_context').y[0],40,'Context stays absolute');
state.insight.minCarbs=50;v=render();assert(v.layout.meta.empty);assert(!v.data.find(t=>t.meta.dataset==='cob' && t.meta.kind==='insight_context').y.some(Number.isFinite));
"""
        result=subprocess.run(['node','-e',setup+src+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_starting_cob_filter_zero_inclusive_missing_and_cache(self):
        loaded,days=fixture();meta=insight_figures(loaded,days,'mmol/L',False,{'insight_meal'})[0].layout.meta
        for s,cob in zip(meta['series'],[0,5,None]):s['meal']['cob']=cob
        src=Path('insights_view.js').read_text()
        setup="const assert=require('assert');const navigation={unit:'mmol/L'};function applyPanelRanges(){};let state={base:'cob-cutoff',mode:'Median + band',insight:{duration:6,aggregation:'Median',normalization:'absolute',filterStartCOB:true,maxStartCOB:0}};function panelStateAt(){return state;}const meta="+json.dumps(meta)+";function render(){const v={data:[],layout:{meta:JSON.parse(JSON.stringify(meta)),xaxis:{},yaxis:{},margin:{}}};transformInsight(v,0);return v;}\n"
        checks="""
let v=render();assert.deepEqual(v.layout.meta.insight_summary.map(r=>r.meal.cob),[0]);assert.equal(v.layout.meta.insight_summary[0].duration,2);
state.insight.maxStartCOB=5;v=render();assert.deepEqual(v.layout.meta.insight_summary.map(r=>r.meal.cob),[0,5]);assert.equal(v.layout.meta.insight_missing_cob,1);
state.insight.filterStartCOB=false;v=render();assert.equal(v.layout.meta.insight_summary.length,3);assert.equal(v.layout.meta.insight_cob_cutoff,null);
state.insight.filterStartCOB=true;state.insight.maxStartCOB=0;state.insight.minCarbs=30;v=render();assert(v.layout.meta.empty);
assert.equal(insightCOBCutoff({maxStartCOB:-5}),0);assert.equal(insightCOBCutoff({maxStartCOB:'bad'}),0);
"""
        result=subprocess.run(['node','-e',setup+src+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
