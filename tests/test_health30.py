"""Glucose thresholds on shared event-aligned Insight views and exports."""
from pathlib import Path
import subprocess
import unittest

from insights import insight_figures
from nightscout_charts import dataset_color
import test_health27


class Health30Tests(unittest.TestCase):
    def test_insights_carry_theme_glucose_color_without_changing_readings(self):
        loaded, days = test_health27.Health27Tests().loaded()
        for dark in (False, True):
            figures = insight_figures(loaded, days, 'mmol/L', dark, {'insight_sensor'})
            self.assertEqual(len(figures), 1)
            self.assertEqual(figures[0].layout.meta['glucose_color'], dataset_color('glucose', dark))
            self.assertEqual(figures[0].layout.meta['series'][0]['glucose'][0], 5)

    def test_absolute_delta_variability_units_gaps_and_cached_panel_styles(self):
        source = (Path(__file__).parents[1] / 'insights_view.js').read_text()
        setup = """
const assert=require('assert');
let state={base:'post-activity',mode:'Multiple days',insight:{aggregation:'Median',normalization:'absolute',duration:6}};
const navigation={unit:'mmol/L'};
function panelStateAt(){return state;}
function applyPanelRanges(v){if(state.manualRange)v.layout.yaxis.range=state.manualRange;}
const series=[{id:'a',label:'Running',x:[0,5,10,15,null,60,65],glucose:[3,4,10,11,null,23,8],rate:[null,.2,1.2,.2,null,null,3],baseline:3},
{id:'b',label:'Cycling',x:[0,5,10,15,null,60,65],glucose:[3,4,10,11,null,23,8],rate:[null,.2,1.2,.2,null,null,3],baseline:3}];
function view(key='activity_after',s=series){return {data:[],layout:{height:350,margin:{},xaxis:{},yaxis:{},meta:{insight:key,dataset:'insight_'+key,series:s,glucose_color:'#218c24'}}};}
"""
        checks = """
let v=view();transformInsight(v,0);
const getBand=v=>v.layout.shapes.filter(s=>s.name==='Insight glucose range');
assert.equal(getBand(v).length,1);assert.deepEqual([getBand(v)[0].y0,getBand(v)[0].y1],[4,10]);
assert.equal(getBand(v)[0].xref,'paper');assert.equal(getBand(v)[0].layer,'below');
assert.deepEqual(v.layout.yaxis.range,[0,25]);assert.equal(v.layout.yaxis.autorange,false);
let ref=v.data.find(t=>t.meta.kind==='insight_median');
assert.deepEqual(ref.marker.color.slice(0,4),['#f44336','#218c24','#218c24','#f44336']);
assert.equal(ref.line.color,'#218c24');assert.equal(ref.y[4],null);assert.equal(ref.connectgaps,false);
const excursion=v.data.find(t=>t.meta.kind==='insight_excursion');assert.equal(excursion.line.color,'#f44336');
assert(excursion.y.every(y=>y===null || y<=4 || y>=10));assert(excursion.x.includes(null));assert.equal(excursion.hoverinfo,'skip');
const crossing=insightExcursions({x:[0,1,null,3,4],y:[3,11,null,11,3],line:{width:2.5}},4,10);
assert.deepEqual(crossing.x,[0,.125,null,.875,1,null,3.875,4,null,3,3.125]);
let event=v.data.find(t=>t.meta.kind==='insight_event');
assert.equal(event.y[4],null);assert.equal(event.marker.color[0],'#f44336');assert.equal(event.line.color,'#45a4c8');
const cacheBefore=JSON.stringify([...insightCalculations]);
v.data[0].y[0]=999;v=view();transformInsight(v,0);assert.equal(JSON.stringify([...insightCalculations]),cacheBefore);
transformInsight(v,0);assert.equal(getBand(v).length,1);assert.equal(v.data.filter(t=>t.meta.kind==='insight_range').length,2);
state.mode='Median + band';v=view();transformInsight(v,0);assert(v.data.some(t=>t.name==='25–75%'));assert.equal(v.data.filter(t=>t.meta.kind==='insight_event').length,0);
state.insight.aggregation='Average';v=view();transformInsight(v,0);assert(v.data.some(t=>t.name==='Average'));assert.equal(getBand(v).length,1);
state.manualRange=[2,12];v=view();transformInsight(v,0);assert.deepEqual(v.layout.yaxis.range,[2,12]);delete state.manualRange;
state.insight.normalization='delta';transformInsight(v,0);assert.equal(getBand(v).length,0);assert.equal(v.layout.yaxis.range,undefined);
assert.equal(v.layout.yaxis.autorange,true);assert.equal(v.layout.yaxis.title.text,'Δ mmol/L');
assert(v.data.every(t=>!['insight_range','insight_excursion'].includes(t.meta.kind) && !t.marker));
state.base='variability';state.insight.metric='rate';v=view('sensor_variability');transformInsight(v,0);
assert.equal(getBand(v).length,0);assert.equal(v.layout.yaxis.title.text,'mmol/L/min');assert.equal(v.layout.yaxis.autorange,true);
state.base='mgdl';state.insight.normalization='absolute';navigation.unit='mg/dL';
const mgSeries=series.map(s=>({...s,glucose:s.glucose.map(y=>Number.isFinite(y)?y*18:null)}));
v=view('activity_after',mgSeries);transformInsight(v,0);assert.deepEqual([getBand(v)[0].y0,getBand(v)[0].y1],[72,180]);
assert.deepEqual(v.layout.yaxis.range,[0,450]);ref=v.data.find(t=>t.meta.kind==='insight_median');assert.equal(ref.marker.color[0],'#f44336');assert.equal(ref.marker.color[2],'#218c24');
state.base='empty';v=view('activity_after',[]);transformInsight(v,0);assert.equal(v.layout.meta.empty,true);
assert.deepEqual(v.layout.yaxis.range,[0,360]);assert(v.layout.annotations[0].text.startsWith('No usable'));
"""
        result = subprocess.run(['node', '-e', setup + source + checks], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
