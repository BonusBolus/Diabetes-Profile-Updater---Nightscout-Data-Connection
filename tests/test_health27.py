"""Independent modes, event alignment, coarse location and selective loading."""
import unittest
from datetime import date,timedelta
from unittest.mock import patch
import pandas as pd
import plotly.graph_objects as go
from insights import aligned_series,baseline_at,insight_figures
from nightscout import utc_bounds,load_nightscout,NightscoutError
from garmin_exports import coarse_location
from garmin_charts import garmin_traces
from graph_view import mode_banks,viewer_html
from nightscout_charts import graph_figures
class Health27Tests(unittest.TestCase):
 def loaded(self):
  start=pd.Timestamp('2026-01-01T00:00Z');days=[date(2026,1,1)+timedelta(days=i) for i in range(3)]
  glucose=pd.DataFrame([dict(time=start+pd.Timedelta(minutes=m),value=90+18*(m%60)/60,label='Glucose') for m in range(0,3*1440,5)])
  changes=pd.DataFrame([dict(time=start,label='Sensor Start'),dict(time=start+pd.Timedelta(hours=24),label='Sensor Start'),dict(time=start+pd.Timedelta(hours=12),label='Site Change'),dict(time=start+pd.Timedelta(hours=48),label='Site Change')])
  data={k:pd.DataFrame() for k in ('basal','basal_percent','target','iob','cob','bolus','carbs','variable_sens')};data.update(glucose=glucose,changes=changes)
  return dict(data=data,zone='UTC',first=days[0],last=days[-1],loaded_at=start+pd.Timedelta(days=3),availability=dict(treatments=True),recorded_profiles=[],_chart_cache={}),days
 def test_year_bound_and_selective_collections(self):
  a,b=utc_bounds(date(2025,1,1),date(2026,1,1),'UTC');self.assertEqual((b-a).days,366)
  with self.assertRaises(NightscoutError):utc_bounds(date(2025,1,1),date(2026,1,2),'UTC')
  with patch('nightscout.NightscoutClient') as c:
   c.return_value.records.return_value=[];c.return_value.get.return_value=[];c.return_value.url='https://test'
   snapshot=load_nightscout('https://test','',date(2025,1,1),date(2025,12,31),'UTC',categories=['glucose'])
   self.assertEqual(c.return_value.records.call_count,3);self.assertEqual(c.return_value.records.call_args_list[0].args[0],'entries/sgv');self.assertTrue(all(call.kwargs.get('filters') for call in c.return_value.records.call_args_list[1:]));self.assertTrue(snapshot['availability']['profiles']);self.assertFalse(snapshot['availability']['treatments']);self.assertEqual(snapshot['loaded_categories'],['glucose'])
 def test_variable_sensor_periods_and_outages(self):
  loaded,days=self.loaded();periods=aligned_series(loaded,days,'sensor','mmol/L');self.assertEqual([s['duration'] for s in periods],[1440,2880]);self.assertEqual(periods[1]['x'][1],5);self.assertAlmostEqual(periods[0]['rate'][1],1/60);self.assertEqual(periods[0]['baseline'],5)
  frame=loaded['data']['glucose'];at=frame.time.iloc[1]+pd.Timedelta(minutes=2);self.assertIn('Interpolated',baseline_at(frame,at)[1]);frame=frame.drop(index=range(1,6));self.assertIsNone(baseline_at(frame,at)[0]);loaded['data']['glucose']=frame;loaded['_chart_cache']={}
  period=aligned_series(loaded,days,'sensor','mmol/L')[0];self.assertIn(None,period['x']);self.assertIsNone(period['rate'][2])
 def test_site_metrics_and_immutable_data(self):
  loaded,days=self.loaded();before=loaded['data']['glucose'].copy(deep=True);s=aligned_series(loaded,days,'site_age','mmol/L');self.assertEqual(set(s[0]['statistics']),{'cv','tir','above_exposure','observed_bins'});pd.testing.assert_frame_equal(before,loaded['data']['glucose'])
 def test_valid_modes_and_stable_panel_bank(self):
  loaded,days=self.loaded();profile=go.Figure();profile.update_layout(title='I:C',yaxis_title='g/U');layers=['Glucose','IOB + Boluses','Insights','Site changes']
  one=graph_figures(profile,loaded,days[:1],'One day',layers,'mmol/L',False);self.assertFalse(any((f.layout.meta or {}).get('kind') in ('insight','hourly') for f in one))
  banks=mode_banks(profile,dict(loaded=loaded,days=days,mode='Multiple days',layers=layers),'mmol/L',False);self.assertEqual(set(banks['Multiple days']),set(banks['Median + band']));self.assertIn('insight:insight_sensor',banks['Median + band']);self.assertIn('restoreGraphPanels',viewer_html(one,False,None))
 def test_garmin_category_skips_unselected_exports(self):
  import sqlite3,tempfile
  from pathlib import Path
  from garmin_data import load_garmin
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'FitFiles'/'Activities').mkdir(parents=True);(root/'Sleep').mkdir()
   (root/'FitFiles'/'Activities'/'invalid.fit').write_bytes(b'not FIT');(root/'Sleep'/'sleep_2026-01-01.json').write_text('invalid JSON')
   with sqlite3.connect(root/'garmin_monitoring.db') as conn:conn.executescript("CREATE TABLE monitoring_hr(timestamp TEXT,heart_rate INTEGER);INSERT INTO monitoring_hr VALUES('2026-01-01 10:00:00',72);")
   with patch('garmin_exports.read_fit',side_effect=AssertionError('FIT must not be decoded')),patch('garmin_exports.read_sleep',side_effect=AssertionError('Sleep must not be read')):
    loaded=load_garmin(root,date(2026,1,1),date(2026,1,1),'UTC','UTC',categories=['heart_rate'])
   self.assertEqual(loaded['loaded_categories'],['heart_rate']);self.assertEqual(set(loaded['data']),{'g_hr'});self.assertEqual(loaded['data']['g_hr'].value.iloc[0],72)
 def test_sleep_stage_stack_in_hours_and_coarse_location(self):
  days=[date(2026,1,1),date(2026,1,2)];start=pd.Timestamp('2026-01-01T00:00Z');frame=pd.DataFrame([dict(time=start+pd.Timedelta(hours=12),end=start+pd.Timedelta(hours=13),stage='light_sleep'),dict(time=start+pd.Timedelta(hours=25),end=start+pd.Timedelta(hours=26),stage='deep_sleep')])
  traces=garmin_traces('g_sleep',dict(data={'g_sleep':frame},zone='UTC'),days,'Median + band');bars=[t for t in traces if t.meta.get('aggregation')=='Average'];self.assertTrue(all(t.width==54 and len(t.x)==24 and t.offsetgroup=='sleep-stage' and t.meta['unit']=='h/hour' for t in bars));light=next(t for t in bars if t.name.startswith('Light'));self.assertEqual(light.y[12],.5)
  label=coarse_location(52.221532,6.893412);self.assertIn('52.25',label);self.assertNotIn('221532',label);self.assertIsNone(coarse_location(None,6));self.assertEqual(coarse_location(52.221532*(2**31)/180,6.893412*(2**31)/180,True),label)
if __name__=='__main__':unittest.main()
