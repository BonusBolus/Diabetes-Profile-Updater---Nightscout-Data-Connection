"""Report blocks, historical schedule identity, selective builds and DST targets."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
import plotly.graph_objects as go
from report_config import settings,save_preset,presets
from report_profiles import base_profiles,graphical_profiles
from report_export import graph_bundle,build_report
from nightscout import recorded_targets
from test_health31 import fixture


def data():
    loaded,days=fixture()
    for key in ('basal','basal_percent','target','cob','variable_sens'):
        loaded['data'].setdefault(key,pd.DataFrame(columns=['time','value','label']))
    loaded.update(warnings=[],has_nightscout=True)
    p=dict(timezone='Africa/Johannesburg',units='mmol/l',dia=8.5,basal=[dict(time='00:00',value=1)],carbratio=[dict(time='00:00',value=10)],sens=[dict(time='00:00',value=2)],target_low=[dict(time='00:00',value=6.6)],target_high=[dict(time='00:00',value=6.6)])
    start=pd.Timestamp(str(days[0]),tz='UTC')
    loaded['recorded_profiles']=[dict(name='Standard v18',percentage=100,profile=p,base_profile=p,start=start.isoformat(),end=(start+timedelta(days=4)).isoformat())]
    return loaded,days


class Health42Tests(unittest.TestCase):
    def test_block_order_round_trip_and_legacy_migration(self):
        raw=dict(layout='portrait',graphs_per_page=6,blocks=[dict(key='daily',graphs_per_page=3,viewer={'panels':[{'id':'a','showAmounts':False}]}),dict(key='overview'),dict(key='summary',graphs_per_page=4)],viewer={'panels':[]})
        with tempfile.TemporaryDirectory() as folder:
            save_preset('Blocks',raw,folder);result=presets(folder)[0]['settings']
        self.assertEqual([b['key'] for b in result['blocks']],['daily','overview','summary'])
        self.assertFalse(result['blocks'][0]['viewer']['panels'][0]['showAmounts'])
        self.assertEqual(result['blocks'][2]['graphs_per_page'],4)
        old=settings(dict(sections=['daily','median','overlay','overview']))
        self.assertEqual([b['key'] for b in old['blocks']],['daily','summary','insights','overview'])
        with self.assertRaises(ValueError):settings(dict(blocks=[dict(key='daily'),dict(key='daily')]))

    def test_schedule_identity_ignores_metadata_but_exposes_real_variants(self):
        loaded,days=data();base=loaded['recorded_profiles'][0]
        same=deepcopy(base);same['percentage']=80;same['base_profile']['dia']='8.500';same['base_profile']['timezone']='Europe/Amsterdam'
        same['base_profile']['basal']=[dict(timeAsSeconds=0,value='1.0'),dict(timeAsSeconds=3600,value=1)]
        loaded['recorded_profiles'].append(same)
        groups=base_profiles(loaded,days,[0,1440]);self.assertEqual(len(groups),1)
        self.assertEqual(groups[0]['timezones'],['Africa/Johannesburg','Europe/Amsterdam'])
        different=deepcopy(base);different['base_profile']['basal'][0]['value']=1.2;loaded['recorded_profiles'].append(different)
        groups=base_profiles(loaded,days,[0,1440]);self.assertEqual(len(groups),2)
        self.assertTrue(all('schedule variant' in g['label'] for g in groups))

    def test_graphical_profiles_use_recorded_base_schedules(self):
        loaded,days=data();figs=graphical_profiles(loaded,days,[0,1440],'mmol/L')
        self.assertEqual(len(figs),4)
        basal=next(f for f in figs if f['title'].startswith('Basal'))
        self.assertEqual(basal['figure']['data'][0]['y'],[1,1])
        self.assertIn('Recorded profile timezone: Africa/Johannesburg',basal['note'])
        self.assertIn('Report/data timezone: UTC',basal['note'])
        self.assertEqual(len(next(f for f in figs if f['title'].startswith('Target'))['figure']['data']),2)

    def test_unknown_profile_units_are_not_assumed(self):
        loaded,days=data();loaded['recorded_profiles'][0]['base_profile'].pop('units')
        figs=graphical_profiles(loaded,days,[0,1440],'mmol/L')
        target=next(f for f in figs if f['title'].startswith('Target'))
        self.assertIn('unspecified',target['figure']['layout']['yaxis']['title']['text'])

    def test_custom_export_builds_only_requested_fields(self):
        from custom_graph import custom_bundle
        loaded,days=data()
        with patch('custom_graph.dataset_traces',return_value=[]) as traces:
            result=custom_bundle(loaded,days,days,'Median + band','mmol/L',False,{},field_ids={'ns:iob'})
        self.assertEqual([f['id'] for f in result['fields']],['ns:iob'])
        self.assertTrue(all(call.args[0]=='iob' for call in traces.call_args_list))

    def test_report_order_and_unneeded_statistics(self):
        loaded,days=data();nav=dict(unit='mmol/L',layers=[],data_only=True)
        request=dict(first=str(days[0]),last=str(days[-1]),blocks=[dict(key='profile_graphs'),dict(key='profiles')],config={'workspaceVersion':2,'panels':[]})
        with patch('report_export.observed_stats',side_effect=AssertionError('unneeded statistics')):
            html=build_report(loaded,nav,request)
        source=html.split('const report=',1)[1].split(';</script>',1)[0];info=json.loads(source)
        self.assertEqual([j['block'] for j in info['jobs']],['profile_graphs','profiles'])

    def test_summary_keeps_modes_and_omits_unselected_datasets(self):
        loaded,days=data();nav=dict(unit='mmol/L',layers=['Glucose','IOB + Boluses','Garmin · Sleep'],data_only=True,report_profile=go.Figure().to_dict())
        config=dict(workspaceVersion=2,panels=[dict(id='g',base=':glucose',duplicate=True,graphType='summary',mode='Median + band'),dict(id='i',base=':iob',duplicate=True,graphType='summary',mode='Multiple days'),dict(id='s',base=':g_sleep',graphType='summary',deleted=True)])
        result=graph_bundle(loaded,nav,config,days,[0,1440],'Median + band','test',block='summary')
        self.assertEqual(set(result['navigation']['mode_banks']),{'Median + band','Multiple days'})
        self.assertNotIn('Garmin · Sleep',result['navigation']['layers'])
        self.assertFalse(any(f['layout'].get('meta',{}).get('dataset')=='g_sleep' for f in result['specs']))
        self.assertFalse(config['panels'][0].get('deleted',False))

    def test_target_events_match_wall_clock_across_both_dst_transitions(self):
        for date in ('2026-03-29','2026-10-25'):
            start=pd.Timestamp(date,tz='Europe/Amsterdam').tz_convert('UTC');end=(pd.Timestamp(date)+pd.Timedelta(days=1)).tz_localize('Europe/Amsterdam').tz_convert('UTC')
            values=[dict(time='00:00',value=5),dict(time='02:30',value=6),dict(time='03:30',value=7)]
            profile=dict(timezone='Europe/Amsterdam',units='mmol/l',target_low=values,target_high=values)
            frame,_=recorded_targets([dict(created_at=start.isoformat(),originalProfileName='Standard',profileJson=profile)],[],start,end)
            for at in pd.date_range(start,end,freq='5min',inclusive='left'):
                local=at.tz_convert('Europe/Amsterdam');minute=local.hour*60+local.minute
                expected=5 if minute<150 else 6 if minute<210 else 7
                row=frame[(frame.time<=at)&(frame.end>at)].iloc[0]
                self.assertAlmostEqual(row.low/18,expected)
            self.assertLess(len(frame),8)

    def test_year_target_processing_does_not_expand_minutes(self):
        start=pd.Timestamp('2026-01-01T00:00Z');end=start+pd.Timedelta(days=365)
        p=dict(timezone='Europe/Amsterdam',units='mmol/l',target_low=[dict(time='00:00',value=6.6)],target_high=[dict(time='00:00',value=6.6)])
        with patch('nightscout.pd.date_range',side_effect=AssertionError('minute expansion')):
            frame,_=recorded_targets([dict(created_at=start.isoformat(),originalProfileName='Standard',profileJson=p)],[],start,end)
        self.assertEqual(len(frame),1);self.assertEqual(frame.iloc[0]['end'],end)


if __name__=='__main__':unittest.main()
