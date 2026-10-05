"""Named project views and source-export integration regressions."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import struct
import subprocess
import unittest
from unittest.mock import patch

import pandas as pd
import plotly.graph_objects as go
from streamlit.testing.v1 import AppTest
import test_garmin as fixtures
from garmin_data import load_garmin, merge_sources
from garmin_charts import garmin_traces
from garmin_exports import read_fit
from graph_view import prepared_graphs, viewer_html
from view_config import save_configuration, saved_configurations


def crc(data):
    value=0
    for byte in data:
        value^=byte
        for _ in range(8):value=(value>>1)^0xA001 if value&1 else value>>1
    return value


def write_fit(path):
    """Generate a small CRC-valid FIT with native samples, power and enhanced fields."""
    epoch=datetime(1989,12,31,tzinfo=timezone.utc)
    start=int((datetime(2026,9,26,8,tzinfo=timezone.utc)-epoch).total_seconds())
    def definition(local,global_id,fields):
        return bytes([0x40|local,0,0])+struct.pack('<H',global_id)+bytes([len(fields)])+b''.join(bytes(f) for f in fields)
    data=definition(0,20,[(253,4,0x86),(6,2,0x84),(73,4,0x86),(2,2,0x84),(78,4,0x86),(7,2,0x84),(3,1,2)])
    for i in range(4):
        data+=bytes([0])+struct.pack('<IHIHIHB',start+i,2000,3000+i*100,2600,3000+i*5,200+i,140+i)
    data+=definition(1,18,[(2,4,0x86),(253,4,0x86),(5,1,0)])
    data+=bytes([1])+struct.pack('<IIB',start,start+4,1) # sport running
    header=struct.pack('<BBHI4s',12,0x20,2100,len(data),b'.FIT')
    content=header+data;path.write_bytes(content+struct.pack('<H',crc(content)))


class Health16Tests(unittest.TestCase):
    setUp=fixtures.GarminTests.setUp

    def parent_folder(self):
        dbs=self.folder/'DBs';dbs.mkdir()
        for p in self.folder.glob('*.db'):p.rename(dbs/p.name)
        return self.folder

    def sleep_export(self):
        folder=self.folder/'Sleep';folder.mkdir()
        raw={'remSleepData':True,'dailySleepDTO':{
            'sleepStartTimestampGMT':int(pd.Timestamp('2026-09-25T21:00Z').timestamp()*1000),
            'sleepEndTimestampGMT':int(pd.Timestamp('2026-09-26T05:00Z').timestamp()*1000),
            'breathingDisruptionSeverity':'NONE','awakeCount':2,'sleepScores':{'restlessness':{'qualifierKey':'GOOD'}}},
            'sleepLevels':[{'startGMT':'2026-09-25T21:00:00','endGMT':'2026-09-26T02:00:00','activityLevel':1},
                           {'startGMT':'2026-09-26T02:00:00','endGMT':'2026-09-26T02:05:00','activityLevel':3}],
            'sleepMovement':[{'startGMT':'2026-09-26T01:10:00','endGMT':'2026-09-26T01:11:00','activityLevel':1.5}],
            'sleepRestlessMoments':[{'startGMT':int(pd.Timestamp('2026-09-26T01:10Z').timestamp()*1000),'value':1}],
            'restlessMomentsCount':1,
            'wellnessEpochRespirationDataDTOList':[{'startTimeGMT':int(pd.Timestamp('2026-09-26T01:10Z').timestamp()*1000),'respirationValue':14.5}]}
        (folder/'sleep_2026-09-26.json').write_text(json.dumps(raw))

    def test_raw_sleep_and_fit_combination(self):
        root=self.parent_folder();self.sleep_export()
        folder=root/'FitFiles'/'Activities';folder.mkdir(parents=True);write_fit(folder/'example.fit')
        loaded=load_garmin(str(root),self.first,self.last,'Europe/Amsterdam','Europe/Amsterdam')
        data=loaded['data']
        self.assertEqual(loaded['measurement_units'],'Metric')
        self.assertEqual(data['g_sleep_movement'].value.tolist(),[1.5])
        self.assertEqual(data['g_sleep_restless'].value.tolist(),[1.])
        self.assertEqual(data['g_sleep_rr'].value.tolist(),[14.5])
        self.assertEqual(loaded['sleep_notes'][0]['breathing'],'NONE')
        self.assertIn('awake',set(data['g_sleep'].stage))
        native=data['g_workout_speed'][data['g_workout_speed'].time.lt(pd.Timestamp('2026-09-26T08:01Z'))]
        self.assertEqual(len(native),4)
        self.assertAlmostEqual(native.iloc[0].value,10.8) # enhanced m/s -> km/h
        self.assertEqual(data['g_workout_power'].value.tolist(),[200,201,202,203])
        self.assertEqual(data['g_workout_altitude'].value.tolist(),[100,101,102,103])
        snapshot=merge_sources(None,loaded)
        traces=garmin_traces('g_workout_speed',snapshot,[self.last],'One day')
        self.assertAlmostEqual(traces[0].x[1]-traces[0].x[0],1/60)
        profile=go.Figure();profile.update_layout(title='Health data')
        view=dict(loaded=snapshot,days=[self.last],mode='One day',layers=['Garmin · Stress','Garmin · Sleep','Garmin · Workout'],data_only=True)
        figures,nav=prepared_graphs(profile,view,'mmol/L',True)
        sleep=next(f for f in figures if f.layout.meta.get('dataset')=='g_sleep')
        self.assertIn('g_sleep_movement',sleep.layout.meta['sleep_fields']);self.assertTrue(all(t.visible is False for t in sleep.data if t.meta.get('sleep_overlay')))
        self.assertTrue(all(t.line.width==64 for t in sleep.data if t.meta.get('kind')=='garmin_sleep'))
        for fig in figures[1:]:self.assertTrue(any((s.name or '').startswith('Activity | ') for s in fig.layout.shapes))
        self.assertIn('garmin_sleep_notes',nav)
        json.dumps(nav,allow_nan=False)

    def test_named_configuration_roundtrip_and_project_buttons(self):
        config=dict(format='profile-studio-view',version=1,layers=['Garmin · Sleep'],mode='Median + band',viewer={'garmin':{'stressLine':True},'custom':['garmin:g_hr'],'order':[':g_sleep']})
        out=save_configuration('Night / sleep',config,self.folder/'views')
        self.assertEqual(out.parent,self.folder/'views')
        self.assertEqual(len(list((self.folder/'views').glob('*.json'))),1)
        save_configuration('night / sleep',dict(config,mode='One day'),self.folder/'views')
        configs,errors=saved_configurations(self.folder/'views')
        self.assertFalse(errors);self.assertEqual(len(configs),1);self.assertEqual(configs[0][1]['mode'],'One day')
        with patch('view_config.CONFIG_FOLDER',self.folder/'views'):
            app=AppTest.from_string("from view_config import configuration_controls\nimport streamlit as st\nst.pills('Data layers',['Garmin · Sleep'],selection_mode='multi',key='ns_layers_diabetes')\nconfiguration_controls()\n",default_timeout=20).run()
            next(b for b in app.button if b.label=='night / sleep').click().run()
            self.assertFalse(app.exception,[e.value for e in app.exception])
            self.assertEqual(app.session_state['ns_layers'],['Garmin · Sleep'])
            self.assertTrue(app.session_state['health_view_config']['garmin']['stressLine'])

    def test_corrupt_fit_is_reported_and_db_remains(self):
        root=self.parent_folder();folder=root/'FitFiles'/'Activities';folder.mkdir(parents=True)
        (folder/'broken.fit').write_bytes(b'not a FIT file')
        result=load_garmin(str(root),self.first,self.last,'Europe/Amsterdam','Europe/Amsterdam')
        self.assertIn('g_hr',result['data']);self.assertTrue(any('broken.fit' in w for w in result['warnings']))

    def test_config_bridge_accepts_only_its_viewer(self):
        if not shutil.which('node'):self.skipTest('Node required')
        result=subprocess.run(['node',str(Path(__file__).with_name('config_bridge_checks.cjs'))],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)

    def test_median_cumulative_steps_stops_at_load_time(self):
        loaded=merge_sources(None,load_garmin(str(self.folder),self.first,self.last,'Europe/Amsterdam','Europe/Amsterdam'))
        loaded['garmin_loaded_at']='2026-09-26T10:00:00Z'
        traces=garmin_traces('g_steps_cumulative',loaded,[self.last],'Median + band')
        line=next(t for t in traces if t.meta.get('variant')=='cumulative')
        self.assertTrue(any(pd.notna(y) for x,y in zip(line.x,line.y) if x<=720))
        self.assertTrue(all(pd.isna(y) for x,y in zip(line.x,line.y) if x>720))


if __name__=='__main__':unittest.main()
