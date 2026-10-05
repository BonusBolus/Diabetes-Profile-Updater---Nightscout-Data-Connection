"""Recorded activity recovery and cumulative-step variability regressions."""
from datetime import date, datetime, timezone
import sqlite3
import struct
import unittest
import pandas as pd
import plotly.graph_objects as go
import test_garmin as fixtures
from test_health16 import crc
from garmin_data import load_garmin, merge_sources
from garmin_exports import read_fit
from garmin_charts import activity_shapes, garmin_traces
from graph_view import prepared_graphs


def multisport_fit(path):
    epoch=datetime(1989,12,31,tzinfo=timezone.utc)
    start=int((datetime(2026,9,26,8,tzinfo=timezone.utc)-epoch).total_seconds())
    fields=[(2,4,0x86),(253,4,0x86),(5,1,0),(7,4,0x86)]
    data=bytes([0x40,0,0])+struct.pack('<H',18)+bytes([len(fields)])+b''.join(bytes(f) for f in fields)
    for offset,sport in [(0,1),(1800,2),(3600,1)]:
        # Timestamp repeats parent start, elapsed time is recorded in milliseconds.
        data+=bytes([0])+struct.pack('<IIBI',start+offset,start,sport,1200000)
    header=struct.pack('<BBHI4s',12,0x20,2100,len(data),b'.FIT')
    content=header+data;path.write_bytes(content+struct.pack('<H',crc(content)))


class Health18Tests(unittest.TestCase):
    setUp=fixtures.GarminTests.setUp
    load=fixtures.GarminTests.load

    def test_multisport_parent_timestamps_recover_all_sessions_and_shared_bands(self):
        with sqlite3.connect(self.folder/'garmin_activities.db') as c:
            c.executescript("ALTER TABLE activities ADD COLUMN activity_id TEXT; UPDATE activities SET activity_id='12345_1';")
        folder=self.folder/'FitFiles'/'Activities';folder.mkdir(parents=True)
        path=folder/'12345.fit';multisport_fit(path)
        _,sessions=read_fit(str(path),path.stat().st_mtime_ns,path.stat().st_size)
        self.assertEqual([s['label'] for s in sessions],['running','cycling','running'])
        self.assertEqual([(s['end']-s['time']).total_seconds() for s in sessions],[1200]*3)
        loaded=merge_sources(None,self.load())
        self.assertEqual(loaded['data']['g_activity'].activity_id.tolist(),['12345_1','12345_2','12345_3'])
        bands=activity_shapes(loaded,[self.last],'One day')
        self.assertEqual([s['label']['text'] for s in bands],['Running 1','Cycling','Running 2'])
        self.assertEqual([(s['x0'],s['x1']) for s in bands],[(600,620),(630,650),(660,680)])
        self.assertEqual(bands[0]['fillcolor'],bands[2]['fillcolor'])
        self.assertNotEqual(bands[0]['fillcolor'],bands[1]['fillcolor'])
        fig=go.Figure();fig.update_layout(title='Health data')
        view=dict(loaded=loaded,days=[self.last],mode='One day',layers=['Garmin · Heart rate','Garmin · Steps','Garmin · Stress','Garmin · Sleep','Garmin · Workout'],data_only=True)
        figures,nav=prepared_graphs(fig,view,'mmol/L',True)
        self.assertEqual(len(nav['activity_bands']),3)
        for f in figures[1:]:
            actual=[(s.x0,s.x1,s.label.text) for s in f.layout.shapes if (s.name or '').startswith('Activity | ')]
            self.assertEqual(actual,[(600,620,'Running 1'),(630,650,'Cycling'),(660,680,'Running 2')])

    def test_db_invalid_end_uses_elapsed_then_linked_records(self):
        with sqlite3.connect(self.folder/'garmin_activities.db') as c:
            c.executescript("ALTER TABLE activities ADD COLUMN elapsed_time TIME; ALTER TABLE activities ADD COLUMN activity_id TEXT; UPDATE activities SET stop_time=start_time,elapsed_time='00:40:00',activity_id='run'; ALTER TABLE activity_records ADD COLUMN activity_id TEXT; UPDATE activity_records SET activity_id='run';")
        interval=self.load()['data']['g_activity'].iloc[0]
        self.assertEqual((interval.end-interval.time).total_seconds(),2400)
        with sqlite3.connect(self.folder/'garmin_activities.db') as c:c.execute('UPDATE activities SET elapsed_time=NULL')
        interval=self.load()['data']['g_activity'].iloc[0]
        self.assertEqual((interval.end-interval.time).total_seconds(),300)
        self.assertIn('last recorded',interval.source)

    def test_missing_sport_column_uses_explicit_type(self):
        with sqlite3.connect(self.folder/'garmin_activities.db') as c:
            c.executescript("ALTER TABLE activities RENAME COLUMN sport TO type; UPDATE activities SET type='cycling';")
        self.assertEqual(self.load()['data']['g_activity'].label.tolist(),['cycling'])

    def test_cumulative_quartiles_use_actual_per_day_curves(self):
        loaded=merge_sources(None,self.load());loaded['zone']='UTC'
        days=[date(2026,9,d) for d in (24,25,26)]
        loaded['data']['g_steps']=pd.DataFrame([dict(time=pd.Timestamp(t,tz='UTC'),value=v) for t,v in [
            ('2026-09-24 00:00',10),('2026-09-24 01:00',10),('2026-09-25 01:00',40),('2026-09-26 01:00',100)]])
        for mode in ('Median + band',):
            traces=garmin_traces('g_steps_cumulative',loaded,days,mode)
            bands=[t for t in traces if t.meta['kind']=='garmin_band']
            self.assertEqual(len(bands),1)
            for b in bands:
                self.assertEqual(b.fill,'toself')
                self.assertEqual(min(b.x),60) # At least two observed days; never invent early zeros.
                self.assertEqual(set(y for x,y in zip(b.x,b.y) if x==60),{30,70})
                self.assertEqual(b.meta['variant'],'cumulative')
            self.assertTrue(bands[0].showlegend)
            self.assertEqual(bands[0].name,'25–75%')
        single=garmin_traces('g_steps_cumulative',loaded,[days[0]],'Median + band')
        self.assertFalse(any(t.meta['kind']=='garmin_band' for t in single))

if __name__=='__main__':unittest.main()
