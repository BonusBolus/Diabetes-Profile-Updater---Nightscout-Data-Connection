"""Uploaded-field semantics, signed IOB and optional settings round trips."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

import pandas as pd
import plotly.graph_objects as go
from openpyxl import Workbook, load_workbook

from aaps_settings import SETTINGS, read_settings, write_settings
from nightscout import normalize_data
from nightscout_charts import dataset_traces, graph_figures, split_iob
from nightscout_stats import continuous_summary
from profiles import import_excel, export_excel, profile_changes, validate_profile, save_profile, load_profiles
from test_nightscout import sample_data


class TelemetryTests(unittest.TestCase):
    def test_only_variable_sensitivity_is_imported_from_suggested(self):
        start=datetime(2026,9,16,tzinfo=timezone.utc)
        row={'created_at':start.isoformat(),'openaps':{'suggested':{
            'sensitivityRatio':.85,'variable_sens':90,'units':.2,
            'reason':'COB: 0, Dev: -1,2, BGI: -0,3, ISF: 5,0, CR: 10'}}}
        data,warnings=normalize_data([],[],[row,row],start,start+timedelta(days=1))
        self.assertFalse({'sens_ratio','deviation','bgi'} & data.keys())
        self.assertFalse(any('glucose units' in w for w in warnings))
        self.assertEqual(data['variable_sens'].value.tolist(),[90])
        row['openaps']['suggested']['variable_sens']=0
        data,_=normalize_data([],[],[row],start,start+timedelta(days=1))
        self.assertTrue(data['variable_sens'].empty)

    def test_iob_zero_crossing_gaps_and_median(self):
        trace=go.Scatter(x=[0,10,20,30,None,60],y=[1,-1,-2,2,None,-.5],
            customdata=['a']*6,meta=dict(kind='iob',unit='U'),line_color='#2196f3',fill='tozeroy',name='IOB')
        positive,negative=split_iob([trace],True)
        self.assertEqual(list(positive.x),[0,5,10,20,25,30,None,60])
        self.assertTrue(all(y is None or y>=0 for y in positive.y))
        self.assertTrue(all(y is None or y<=0 for y in negative.y))
        self.assertIsNone(negative.y[-2])
        self.assertNotEqual(positive.line.color,negative.line.color)
        loaded=sample_data()
        median=dataset_traces('iob',loaded,[loaded['first']],'Median + band','mmol/L',True)
        self.assertTrue(any(t.name=='Negative IOB' and t.meta['dataset']=='iob' for t in median))

    def test_medians_use_equal_daily_weight_and_panels_separate_units(self):
        loaded=sample_data();start=loaded['loaded_at']-timedelta(days=2)
        for key,values in [('variable_sens',[90,90,180])]:
            loaded['data'][key]=pd.DataFrame([dict(time=start+offset,value=value,label=key) for offset,value in zip(
                [timedelta(minutes=0),timedelta(minutes=1),timedelta(days=1)],values)])
        days=[loaded['first'],loaded['last']]
        self.assertEqual(continuous_summary(loaded,'variable_sens',days,'mmol/L').iloc[0]['median'],7.5)
        profile=go.Figure(go.Scatter(x=[0,1440],y=[1,1],meta=dict(kind='profile')))
        profile.update_layout(title='Basal',yaxis_title='U/h')
        for mode in ('One day','Median + band'):
            figures=graph_figures(profile,loaded,days,mode,['IOB + boluses','COB + carbs','Variable sensitivity'],'mmol/L',True)
            variable=next(f for f in figures if (f.layout.meta or {}).get('dataset')=='variable_sens')
            self.assertEqual(variable.layout.yaxis.title.text,'mmol/L/U')
            self.assertTrue(variable.data)


class SettingsTests(unittest.TestCase):
    def test_settings_are_optional_and_roundtrip_and_show_in_review(self):
        root=Path(__file__).resolve().parents[1]
        before=import_excel((root/'examples/example-profile.xlsx').read_bytes(),'Sheet1')
        self.assertNotIn('aaps_settings',before['overview'])
        profile=deepcopy(before)
        profile['overview']['aaps_settings']={key:float(i) for i,key in enumerate(SETTINGS,1)}
        metadata,_=profile_changes(before,profile)
        self.assertEqual(len(metadata),8)
        exported=export_excel(profile,root/'examples/profile-import.xlsx')
        book=load_workbook(BytesIO(exported))
        self.assertEqual(read_settings(book,book.active.title),profile['overview']['aaps_settings'])
        imported=import_excel(exported,book.active.title)
        self.assertEqual(imported['overview']['aaps_settings'],profile['overview']['aaps_settings'])
        with tempfile.TemporaryDirectory() as folder:
            save_profile(folder,profile)
            self.assertEqual(load_profiles(folder)[0][0]['overview']['aaps_settings'],profile['overview']['aaps_settings'])
        for bad in [float('nan'),-1,True,'3']:
            profile['overview']['aaps_settings']['smbinterval']=bad
            with self.assertRaises(ValueError):validate_profile(profile)
