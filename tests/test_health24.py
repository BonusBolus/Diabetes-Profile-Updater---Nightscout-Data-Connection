"""Observed event provenance, report statistics and reuse of graph rendering."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import subprocess
import unittest
import pandas as pd
import plotly.graph_objects as go
from nightscout import normalize_data, recorded_profiles
from report_stats import observed_stats, report_range
from report_export import build_report, graph_bundle, profile_pages, histogram
from graph_view import prepared_graphs, viewer_html
import test_health23

UTC=timezone.utc

class Health24Tests(unittest.TestCase):
    setUp=test_health23.Health23Tests.setUp
    enriched=test_health23.Health23Tests.enriched
    load=test_health23.Health23Tests.load

    def fixture(self):
        loaded=self.enriched();loaded['has_nightscout']=True;loaded['availability']={'treatments':True}
        start=datetime(2026,9,25,tzinfo=UTC);end=start+timedelta(days=2)
        profile=dict(timezone='UTC',units='mmol/L',dia=8.5,carbratio=[dict(time='00:00',value=9)],sens=[dict(time='00:00',value=3)],basal=[dict(time='00:00',value=.8)],target_low=[dict(time='00:00',value=6.6)],target_high=[dict(time='00:00',value=6.6)])
        events=[dict(_id='profile',created_at=(start-timedelta(days=1)).isoformat(),originalProfileName='Standard v17',profileJson=profile),
                dict(_id='site',created_at=(start+timedelta(hours=10)).isoformat(),eventType='Site Change'),
                dict(_id='sensor',created_at=(start+timedelta(hours=10)).isoformat(),eventType='Sensor Start'),
                dict(_id='bolus',created_at=(start+timedelta(hours=10)).isoformat(),eventType='Meal Bolus',type='SMB',insulin=.3,carbs=20)]
        entries=[dict(date=(start+timedelta(days=d,hours=10,minutes=m)).timestamp()*1000,sgv=v) for d,m,v in [(0,0,90),(0,1,90),(0,5,180),(1,0,270)]]
        data,_=normalize_data(entries,events,[],start,end);loaded['data'].update(data)
        loaded.update(zone='UTC',loaded_at=end,recorded_profiles=recorded_profiles(events,start,end))
        return loaded

    def test_changes_require_explicit_events_and_keep_simultaneous_types(self):
        start=datetime(2026,9,25,tzinfo=UTC);end=start+timedelta(days=1)
        base=dict(created_at=start.isoformat())
        events=[dict(base,_id='a',eventType='Site Change'),dict(base,_id='b',eventType='Sensor Start'),dict(base,_id='a',eventType='Site Change'),dict(base,eventType='Note',notes='Site Change'),dict(base,eventType='Sensor Change',isValid=False)]
        data,_=normalize_data([],events,[],start,end)
        self.assertEqual(data['changes'].label.tolist(),['Site Change','Sensor Start'])

    def test_profile_history_stops_at_unknown_switch(self):
        start=datetime(2026,9,25,tzinfo=UTC);end=start+timedelta(days=1)
        events=[dict(created_at=(start-timedelta(days=1)).isoformat(),originalProfileName='Known',originalPercentage=150,profileJson={'basal':[{'time':'00:00','value':1.5}]}),dict(created_at=(start+timedelta(hours=12)).isoformat(),originalProfileName='Unknown',profileJson='invalid')]
        history=recorded_profiles(events,start,end)
        self.assertEqual(history[0]['end'],events[1]['created_at']);self.assertEqual(history[0]['profile']['basal'][0]['value'],1.5)
        self.assertEqual(history[1]['profile'],{})

    def test_observed_statistics_weight_bins_not_upload_density(self):
        loaded=self.fixture();stats=observed_stats(loaded,[self.first,self.last],[0,1440],'mmol/L')
        self.assertEqual(stats['total']['readings'],4);self.assertEqual(stats['total']['bins'],3)
        self.assertEqual(stats['total']['mean'],10);self.assertAlmostEqual(stats['total']['own_within'],200/3)
        self.assertEqual(stats['total']['changes']['Site Change'],1);self.assertEqual(stats['total']['bolus'],.3)
        limited=observed_stats(loaded,[self.first],[601,606],'mmol/L');self.assertEqual(limited['total']['coverage'],100)
        loaded['availability']['treatments']=False
        self.assertIsNone(observed_stats(loaded,[self.first],[0,1440],'mmol/L')['total']['bolus'])
        with self.assertRaises(ValueError):report_range(dict(first='2026-09-24',last='2026-09-26'),loaded)
        with self.assertRaises(ValueError):report_range(dict(first=str(self.first),last=str(self.last),from_time='23:00',until_time='01:00'),loaded)

    def test_histogram_colors_classify_values_not_bin_centers(self):
        for unit,values in [('mmol/L',[3.9,4,10,10.1]),('mg/dL',[70.2,72,180,181.8])]:
            fig=histogram({'values':values},unit)
            self.assertEqual([sum(t['y']) for t in fig['data']],[25,50,25])

    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_report_sections_render_with_live_configuration(self):
        loaded=self.fixture();profile=go.Figure(go.Scatter(x=[0,1440],y=[10,10],meta=dict(kind='profile'),name='Standard v17'))
        profile.update_layout(title='I:C',xaxis=dict(range=[0,1440]),yaxis=dict(title='g/U'))
        view=dict(loaded=loaded,days=[self.first,self.last],mode='Median + band',layers=['Glucose','IOB + Boluses','Garmin · Steps','Garmin · Activity','Custom graph'])
        figs,nav=prepared_graphs(profile,view,'mmol/L',False)
        config=dict(overlay='Glucose',sameScale=False,showTargets=True,changeScope='all',excludeSMB=True,hourlyModes={'bolus':'Median'},
                    garmin={'activityShading':True,'stepsHistogram':False,'activity':{'g_workout_hr':{'smooth':True,'tauSeconds':15,'lower':100}}},
                    customPanels=[dict(id='custom-1',selected=['ns:glucose','garmin:g_hr'],fieldOptions={},axisRanges={})],customVisible=['custom-1'])
        request=dict(title='<test> report',first=str(self.first),last=str(self.last),sections=['overview','profiles','median','statistics','daily','overlay','distribution'],config=config)
        report=build_report(loaded,nav,request);self.assertNotIn('example.test',report);self.assertIn('Standard v17',report);self.assertIn('Print / Save as PDF',report)
        self.assertIn('const payload = __REPORT_PAYLOAD__',report)
        # Persist an inspectable synthetic report as a test artifact, never real credentials.
        (self.folder/'report.html').write_text(report,encoding='utf-8')
        paths=[]
        for mode in ('One day','Multiple days','Median + band'):
            bundle=graph_bundle(loaded,nav,config,[self.last] if mode=='One day' else [self.first,self.last],[540,780],mode,mode)
            html=viewer_html([go.Figure(f) for f in bundle['specs']],False,bundle['navigation'])
            path=self.folder/f'{len(paths)}.js';path.write_text(html.split('<script>')[-1].split('</script>')[0],encoding='utf-8');paths.append(str(path))
        target=self.folder/'figures.json'
        result=subprocess.run(['node',str(Path(__file__).with_name('health24_viewer_checks.cjs')),*paths,str(target)],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        for fig in json.loads(target.read_text()):go.Figure(fig)

if __name__=='__main__':unittest.main()
