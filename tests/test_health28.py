"""Import chips, independent analysis selections, bounded rendering and yearly reports."""
import json
from datetime import date,timedelta
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
import test_health27
from test_nightscout import sample_data
from nightscout_charts import graph_figures,normalize_layers
from nightscout_ui import imported_layers, NS_IMPORTS
from report_stats import report_range,observed_stats
from report_export import build_report,statistics_pages
import plotly.graph_objects as go

class Health28Tests(unittest.TestCase):
    def test_exposure_uses_elapsed_hours_for_all_timestamp_resolutions(self):
        from insights import aligned_series
        loaded,days=test_health27.Health27Tests().loaded();start=pd.Timestamp('2026-01-01T00:00Z')
        loaded['data']['glucose']=pd.DataFrame([dict(time=start+pd.Timedelta(minutes=m),value=y,label='Glucose') for m,y in [(0,200),(5,220),(25,240)]])
        loaded['data']['changes']=pd.DataFrame([dict(time=start,label='Site Change')]);loaded['_chart_cache']={}
        self.assertAlmostEqual(aligned_series(loaded,days,'site_age','mg/dL')[0]['statistics']['above_exposure'],2.5)
        self.assertAlmostEqual(aligned_series(loaded,days,'site_age','mmol/L')[0]['statistics']['above_exposure'],2.5/18)

    def test_import_chips_select_all_and_success_selection(self):
        snapshot=sample_data();snapshot['zone']='UTC'
        with patch('nightscout_ui.load_nightscout',return_value=snapshot) as load:
            app=AppTest.from_string("from nightscout_ui import sidebar_controls\nsidebar_controls('UTC')").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.multiselect),0)
            app.text_input(key='ns_url').set_value('https://example.invalid')
            app.button_group(key='ns_load_layers').set_value(['Glucose']).run()
            load.assert_not_called()
            app.button(key='ns_refresh').click().run()
            self.assertFalse(app.exception,[e.value for e in app.exception])
            self.assertEqual(app.session_state.ns_layers,['Glucose'])
            self.assertEqual(load.call_args.kwargs['categories'],['glucose'])
            app.button(key='ns_load_layers_all').click().run()
            self.assertEqual(set(app.session_state.ns_load_layers),set(NS_IMPORTS))
            app.button_group(key='garmin_load_layers').set_value([]).run()
            app.button(key='garmin_load_layers_all').click().run()
            self.assertEqual(len(app.session_state.garmin_load_layers),6)
            self.assertEqual(load.call_count,1)
            self.assertEqual(app.session_state.ns_layers,['Glucose'])
        data=dict(data={'g_workout_hr':pd.DataFrame({'value':[123]}),'g_sleep_hrv':pd.DataFrame({'value':[42]})})
        self.assertEqual(imported_layers(data,['Garmin · Activity','Garmin · Sleep','Garmin · Stress']),['Garmin · Activity','Garmin · Sleep'])

    def test_only_requested_insight_is_prepared_and_legacy_expands(self):
        loaded,days=test_health27.Health27Tests().loaded();profile=go.Figure();profile.update_layout(title='I:C')
        with patch('insights.aligned_series',return_value=[]) as aligned:
            graphs=graph_figures(profile,loaded,days,'Median + band',['Site-age glucose'],'mmol/L',False)
            self.assertEqual(aligned.call_count,1)
            self.assertEqual(aligned.call_args.args[2],'site_age')
            self.assertEqual([f.layout.meta.get('insight') for f in graphs[1:]],['site_age'])
        from insights import INSIGHT_LAYERS
        self.assertEqual(len(normalize_layers(['Insights'])),len(INSIGHT_LAYERS))

    def test_insight_average_equal_event_weight_axis_and_gaps(self):
        code=(Path(__file__).parents[1]/'insights_view.js').read_text()
        context="""const assert=require('assert');let state={base:'sensor',mode:'Median + band',axisRanges:{},insight:{aggregation:'Median',metric:'glucose'}};
const navigation={unit:'mmol/L'};function panelStateAt(){return state;}function applyPanelRanges(){}
const series=[{id:'a',label:'a',x:[0,5,10,60,180,72000],glucose:[5,5,50,6,7,null]},
{id:'b',label:'b',x:[0,60,180],glucose:[10,8,9]}];function view(){return {data:[],layout:{height:350,margin:{t:36,b:62},xaxis:{range:[0,1440]},yaxis:{},meta:{insight:'sensor',dataset:'insight_sensor',series}}};}
"""
        check="""let v=view();transformInsight(v,0);let t=v.data.find(t=>t.name==='Median');assert.equal(t.y[0],7.5);assert.equal(t.customdata[0],2);assert(v.layout.xaxis.range[1]<4);assert.equal(v.data.filter(t=>t.name==='25–75%').length,2);
state.insight.aggregation='Average';v=view();transformInsight(v,0);t=v.data.find(t=>t.name==='Average');assert.equal(t.y[0],15);
state.mode='Multiple days';v=view();transformInsight(v,0);assert.equal(v.data.filter(t=>t.meta.kind==='insight_event').length,2);assert(v.data.some(t=>t.name==='Average'));assert.equal(insightCalculations.size,2);
"""
        result=subprocess.run(['node','-e',context+code+check],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_percent_height_and_three_label_lanes(self):
        source=(Path(__file__).parents[1]/'garmin_view.js').read_text();source=source[source.index('function eventAllowed'):source.index('function eventScopeControl')]+source[source.index('function profileLineStyle'):]
        context="""const assert=require('assert');const selectedDays=['2026-01-01'];let dateCycled=false;const eventScopes={profiles:'all',percentage:'all'};
const navigation={profile_events:[50,80,100,120].map((p,i)=>({name:i<3?'Standard v18':'Drinking v19',percentage:p,date:selectedDays[0],minute:600+i*5,intervals:[{date:selectedDays[0],start:600+i*5,end:605+i*5}]}))};
const view={layout:{height:350,width:1000,margin:{t:36,b:62},xaxis:{range:[0,1440]},meta:{},shapes:[],annotations:[]},data:[]};
"""
        check="""applyProfileEvents(view);const rects=view.layout.shapes.filter(s=>s.type==='rect');assert.deepEqual(rects.map(s=>s.y1),[.5,.8,1.2]);assert(rects.every(s=>s.fillcolor==='rgba(153,102,204,.14)'));const top=view.layout.annotations.filter(a=>a.y>1),bottom=view.layout.annotations.filter(a=>a.y<0);assert.equal(top.length,4);assert.equal(bottom.length,4);assert.equal(new Set(bottom.map(a=>a.yshift)).size,3);assert(view.layout.margin.t>69);const count=view.layout.shapes.length;applyProfileEvents(view);assert.equal(view.layout.shapes.length,count);
"""
        result=subprocess.run(['node','-e',context+source+check],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)

    def test_yearly_report_range_statistics_and_generation(self):
        first=date(2025,1,1);last=first+timedelta(days=365);start=pd.Timestamp(first).tz_localize('UTC')
        records=pd.DataFrame([dict(time=start+pd.Timedelta(days=n,hours=12),value=90+n%18,label='Glucose') for n in range(366)])
        data={key:pd.DataFrame(columns=['time','value']) for key in ('bolus','carbs','iob','cob','target','basal','basal_percent','variable_sens','changes')};data['glucose']=records
        loaded=dict(data=data,first=first,last=last,zone='UTC',loaded_at=start+pd.Timedelta(days=366),availability={'treatments':True},_chart_cache={})
        request=dict(first=str(first),last=str(last),sections=['overview','statistics','median'],config={},graphs_per_page=4)
        days,window=report_range(request,loaded);self.assertEqual(len(days),366)
        stats=observed_stats(loaded,days,window,'mmol/L');self.assertEqual(stats['total']['readings'],366);self.assertEqual(len(stats['daily']),366)
        self.assertEqual(len(statistics_pages(stats,'mmol/L','landscape')),31)
        self.assertEqual(len(statistics_pages(stats,'mmol/L','portrait')),25)
        nav=dict(unit='mmol/L',layers=['Glucose'],report_profile={},data_only=True)
        html=build_report(loaded,nav,request);self.assertIn('2026-01-01',html);self.assertIn('Preparing charts',html)
        loaded['last']=last+timedelta(days=1)
        with self.assertRaisesRegex(ValueError,'366'):report_range(dict(request,last=str(loaded['last'])),loaded)

if __name__=='__main__':unittest.main()
