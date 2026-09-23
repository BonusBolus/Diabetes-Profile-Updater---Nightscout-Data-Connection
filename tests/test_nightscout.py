from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import plotly.graph_objects as go

from nightscout import (NightscoutClient, NightscoutError, glucose_summary, load_nightscout,
                        local_points, normalize_data, site_url, timestamp, utc_bounds)
from nightscout_charts import graph_figures, interval_points

UTC = timezone.utc


def sample_data():
    start = datetime(2026, 9, 16, tzinfo=UTC)
    end = start + timedelta(days=2)
    entries = [{"date": (start+timedelta(days=day, minutes=minute)).timestamp()*1000,
                "sgv": value} for day, minute, value in ((0,0,180),(0,1,180),(0,2,180),(1,0,360))]
    treatments = [
        {"_id":"prior", "created_at":"2026-09-15T23:50:00Z", "eventType":"Temp Basal", "absolute":.8,"duration":60},
        {"_id":"cancel", "created_at":"2026-09-16T00:10:00Z", "eventType":"Temp Basal", "duration":0},
        {"_id":"zero", "created_at":"2026-09-16T01:00:00Z", "eventType":"Temp Basal", "absolute":0,"duration":30},
        {"_id":"percent", "created_at":"2026-09-16T02:00:00Z", "eventType":"Temp Basal", "percent":-50,"duration":30},
        {"_id":"meal", "created_at":"2026-09-16T05:00:00Z", "eventType":"Meal Bolus", "insulin":2,"carbs":30}]
    statuses = [{"created_at":"2026-09-16T05:05:00Z", "openaps":{
        "iob":[{"time":"2026-09-16T05:00:00Z", "iob":-0.2},{"time":"2026-09-16T05:10:00Z", "iob":1}],
        "suggested":{"timestamp":"2026-09-16T05:00:00Z", "COB":0}}}]
    data, warnings = normalize_data(entries, treatments, statuses, start, end)
    return {"data":data, "warnings":warnings, "zone":"UTC", "first":date(2026,9,16),
            "last":date(2026,9,17), "site":"https://example.test", "loaded_at":end}


class NightscoutTests(unittest.TestCase):
    def test_timezone_days_and_unambiguous_timestamps(self):
        for day, hours in ((date(2026,3,29),23),(date(2026,10,25),25)):
            start,end = utc_bounds(day,day,'Europe/Amsterdam')
            self.assertEqual((end-start).total_seconds()/3600, hours)
        self.assertIsNone(timestamp('2026-09-16T05:00:00'))
        self.assertEqual(timestamp('2026-09-16T07:00:00+02:00'),timestamp('2026-09-16T05:00:00Z'))
        with self.assertRaises(NightscoutError):
            utc_bounds(date(2026,1,1),date(2026,2,1),'UTC')

    def test_get_only_token_encoding_and_sanitized_errors(self):
        client = NightscoutClient('https://example.test/nightscout/', 'secret+token')
        client.opener = MagicMock()
        client.opener.open.return_value = BytesIO(b'[]')
        self.assertEqual(client.get('entries/sgv',{'count':1}), [])
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(parse_qs(urlsplit(request.full_url).query)['token'], ['secret+token'])
        client.opener.open.side_effect = HTTPError(request.full_url,403,'secret+token',{},None)
        with self.assertRaises(NightscoutError) as caught:
            client.get('entries/sgv',{})
        self.assertNotIn('secret',str(caught.exception))
        for bad in ('http://example.test','https://example.test?token=private','https://user:password@example.test'):
            with self.assertRaises(NightscoutError): site_url(bad)

    def test_full_windows_split_without_losing_boundary_records(self):
        start = datetime(2026,9,16,tzinfo=UTC)
        entries = [{'date':int((start+timedelta(hours=h)).timestamp()*1000),'sgv':100+h} for h in (0,6,12,18)]
        client = NightscoutClient('https://example.test','')
        def get(collection, params):
            self.assertEqual(collection,'entries/sgv')
            return [r for r in entries if params['find[date][$gte]'] <= r['date'] < params['find[date][$lt]']][:2]
        with patch.object(client,'get',side_effect=get), patch('nightscout.PAGE_SIZE',2):
            result = client.records('entries/sgv',start,start+timedelta(days=1))
        self.assertEqual(result, entries)
        with patch.object(client,'get',return_value=[{'date':start.timestamp()*1000-1}]):
            with self.assertRaisesRegex(NightscoutError,'date filter'):
                client.records('entries/sgv',start,start+timedelta(days=1))

    def test_recorded_temps_cancel_overlap_and_zero_is_not_a_gap(self):
        data = sample_data()['data']
        self.assertEqual(data['basal'].iloc[0]['time'],datetime(2026,9,16,tzinfo=UTC))
        self.assertEqual(data['basal'].iloc[0]['end'],datetime(2026,9,16,0,10,tzinfo=UTC))
        self.assertEqual(data['basal'].iloc[1]['value'],0)
        self.assertEqual(data['basal_percent'].iloc[0]['value'],-50)
        self.assertEqual(data['iob']['value'].tolist(),[-.2])
        self.assertEqual(data['cob']['value'].tolist(),[0])
        self.assertEqual(data['bolus']['value'].tolist(),[2])
        xs,ys,_ = interval_points(data['basal'],'UTC',date(2026,9,16))
        self.assertEqual(xs,[0,10,None,60,90,None])
        self.assertEqual(ys,[.8,.8,None,0,0,None])

    def test_glucose_daily_weight_units_and_missing_bins(self):
        data = sample_data()
        summary = glucose_summary(data['data']['glucose'],'UTC',[data['first'],data['last']],'mmol/L')
        self.assertEqual(summary.iloc[0]['median'],15)
        self.assertEqual(summary.iloc[0]['low'],12.5)
        self.assertEqual(summary.iloc[0]['high'],17.5)
        self.assertEqual(summary.iloc[0]['days'],2)
        self.assertTrue(pd.isna(summary.iloc[1]['median']))
        local = local_points(data['data']['glucose'],'Europe/Amsterdam',[data['first']])
        self.assertEqual(local.iloc[0]['minute'],120)

    def test_load_partial_data_has_explicit_warning_and_no_credentials(self):
        with patch('nightscout.NightscoutClient') as factory:
            client = factory.return_value
            client.url = 'https://example.test'
            client.records.side_effect = [[], [], NightscoutError('Device status unavailable')]
            client.get.return_value = []
            result = load_nightscout(client.url,'private-token',date(2026,9,16),date(2026,9,16),'UTC')
        self.assertTrue(any('IOB/COB' in w for w in result['warnings']))
        self.assertNotIn('private-token',repr(result))

    def test_aligned_panels_keep_profile_and_share_time_axes(self):
        loaded = sample_data()
        profile = go.Figure(go.Scatter(x=[0,1440],y=[1,1],name='Draft',line_shape='hv'))
        profile.update_layout(yaxis_title='U/h',uirevision='basal')
        figures = graph_figures(profile,loaded,[loaded['first'],loaded['last']],'Median + band',
                             ['Glucose','Temporary basal','Boluses','Carbs','IOB','COB'],'mmol/L',True,overlay='Glucose')
        fig=figures[0]
        self.assertEqual(fig.data[0].name,'Draft')
        self.assertEqual(list(fig.data[0].y),[1,1])
        self.assertEqual(fig.layout.yaxis2.side,'right')
        self.assertTrue(any(t.name=='Median glucose' and t.yaxis=='y2' for t in fig.data))
        self.assertEqual(len(figures),8)  # profile, glucose, basal, percent, IOB, COB, two hourly summaries
        self.assertTrue(any(t.meta and t.meta.get('dataset')=='iob' for t in figures[4].data))
        self.assertFalse(any(t.meta and t.meta.get('kind')=='bolus' for t in figures[4].data))
        self.assertTrue(any(t.meta and t.meta.get('dataset')=='cob' for t in figures[5].data))
        self.assertEqual(figures[6].layout.meta['dataset'],'bolus')
        self.assertEqual(figures[7].layout.meta['dataset'],'carbs')
        for figure in figures:
            self.assertIn('2026-09-16',figure.layout.title.text)
            self.assertIn('2026-09-17',figure.layout.title.text)
            self.assertEqual(list(figure.layout.xaxis.range),[0,1440])
        self.assertEqual(len(profile.data),1)
        for key,frame in loaded['data'].items():
            pd.testing.assert_frame_equal(frame,sample_data()['data'][key])

class UpdatedChartTests(unittest.TestCase):
    def test_bolus_type_and_target_schedule_overrides(self):
        start=datetime(2026,9,16,tzinfo=UTC); end=start+timedelta(days=1)
        profile={'timezone':'UTC','units':'mmol','target_low':[{'time':'00:00','value':6.6}],
                 'target_high':[{'time':'00:00','value':6.6}]}
        treatments=[{'_id':'eps','created_at':'2026-09-15T00:00:00Z','originalProfileName':'Standard',
                     'profileJson':json.dumps(profile)},
                    {'created_at':'2026-09-15T23:50:00Z','eventType':'Temporary Target','duration':60,
                     'units':'mg/dl','targetBottom':90,'targetTop':108},
                    {'created_at':'2026-09-16T00:10:00Z','eventType':'Temporary Target','duration':0},
                    {'created_at':'2026-09-16T01:00:00Z','eventType':'Temporary Target','duration':10,
                     'durationInMilliseconds':615000,'units':'mmol','targetBottom':7,'targetTop':8}]
        for i,extra in enumerate(({'type':'SMB'},{'type':'NORMAL'},{},{'type':'PRIMING'},{'isSMB':True},{'isSMB':False})):
            treatments.append(dict(created_at=f'2026-09-16T02:0{i}:00Z',insulin=.2,**extra))
        data,warnings=normalize_data([],treatments,[],start,end)
        self.assertEqual(data['bolus']['label'].tolist(),['SMB','User bolus','Bolus · unknown type','SMB','User bolus'])
        self.assertTrue(any('unknown' in w for w in warnings))
        targets=data['target'].to_dict('records')
        self.assertEqual(targets[0]['low'],90)
        self.assertEqual(targets[0]['end'],start+timedelta(minutes=10))
        self.assertAlmostEqual(targets[1]['low']/18,6.6)
        self.assertAlmostEqual(targets[1]['high']/18,6.6)
        self.assertEqual(targets[2]['end'],start+timedelta(hours=1,minutes=10,seconds=15))
        self.assertEqual(targets[-1]['end'],end)
        self.assertEqual(targets[-1]['source'],'Scheduled target')
        # Unknown target units must mask known baseline until the temp ends.
        treatments.append({'created_at':'2026-09-16T03:00:00Z','eventType':'Temporary Target','duration':30,
                           'targetBottom':6,'targetTop':6})
        unknown,_=normalize_data([],treatments,[],start,end)
        self.assertFalse(any(r['time']<=start+timedelta(hours=3,minutes=5)<r['end'] for r in unknown['target'].to_dict('records')))

    def test_glucose_range_fixed_band_and_every_overlay(self):
        loaded=sample_data(); days=[loaded['first']]
        profile=go.Figure(go.Scatter(x=[0,1440],y=[5,5],name='Draft'))
        profile.update_layout(yaxis_title='g/U',title='I:C · Viewed: 2026-09-17')
        from nightscout_charts import LAYERS
        for overlay in LAYERS:
            figures=graph_figures(profile,loaded,days,'One day',list(LAYERS),'mmol/L',False,overlay=overlay)
            top=figures[0]
            self.assertEqual(top.layout.yaxis.title.text,'g/U')
            self.assertEqual(top.layout.yaxis2.side,'right')
            self.assertEqual(top.data[0].yaxis,'y')
            for fig in figures:
                self.assertIn(days[0].isoformat(),fig.layout.title.text)
        glucose=graph_figures(profile,loaded,days,'One day',['Glucose'],'mmol/L',True)[1]
        self.assertEqual(list(glucose.layout.yaxis.range),[0,20])
        self.assertEqual((glucose.layout.shapes[0].y0,glucose.layout.shapes[0].y1),(4,10))
        loaded['data']['glucose'].loc[0,'value']=450
        figures=graph_figures(profile,loaded,days,'Median + band',['Glucose'],'mmol/L',True,overlay='Glucose')
        self.assertGreater(figures[0].layout.yaxis2.range[1],25)
        self.assertGreater(figures[1].layout.yaxis.range[1],25)
        mgdl=graph_figures(profile,loaded,days,'One day',['Glucose'],'mg/dL',False)[1]
        self.assertGreater(mgdl.layout.yaxis.range[1],450)
        self.assertEqual((mgdl.layout.shapes[0].y0,mgdl.layout.shapes[0].y1),(72,180))

    def test_target_schedule_timezone_and_dst(self):
        start,end=utc_bounds(date(2026,10,25),date(2026,10,25),'Europe/Amsterdam')
        profile={'timezone':'Europe/Amsterdam','units':'mg/dl',
                 'target_low':[{'time':'00:00','value':100},{'time':'02:30','value':110},{'time':'03:00','value':120}],
                 'target_high':[{'time':'00:00','value':100},{'time':'02:30','value':110},{'time':'03:00','value':120}]}
        treatments=[{'created_at':'2026-10-24T00:00:00Z','originalProfileName':'Standard','profileJson':profile}]
        data,_=normalize_data([],treatments,[],start,end)
        self.assertEqual(data['target']['low'].tolist(),[100,110,100,110,120])
        self.assertEqual(data['target'].iloc[0]['time'],start)
        self.assertEqual(data['target'].iloc[-1]['end'],end)

    def test_pinned_viewer_keeps_json_labels_inert(self):
        from graph_view import viewer_html
        fig=go.Figure(go.Scatter(x=[0],y=[1],name='</script><script>alert(1)</script>'))
        html=viewer_html([fig],True)
        self.assertNotIn('</script><script>alert(1)',html)
        self.assertIn('overflow-y:auto',html)
        self.assertIn('plotly_relayout',html)




class TargetContinuityAndStyleTests(unittest.TestCase):
    def test_effective_target_survives_original_end_until_next_switch(self):
        start=datetime(2026,9,16,tzinfo=UTC); end=start+timedelta(days=1)
        profile={'timezone':'UTC','units':'mmol','target_low':[{'time':'00:00','value':6.6}],
                 'target_high':[{'time':'00:00','value':6.6}]}
        original_end=start+timedelta(hours=7)
        treatments=[{'created_at':start.isoformat(),'originalProfileName':'Standard','profileJson':profile,
                     'originalEnd':original_end.timestamp()*1000,'originalDuration':7*3600000},
                    {'created_at':(start+timedelta(hours=10)).isoformat(),'eventType':'Temporary Target',
                     'duration':30,'units':'mmol','targetBottom':8,'targetTop':8,'reason':'Activity'},
                    {'created_at':(start+timedelta(hours=10,minutes=30)).isoformat(),'eventType':'Temporary Target',
                     'duration':30,'units':'mmol','targetBottom':8,'targetTop':8,'reason':'Eating Soon'}]
        data,_=normalize_data([],treatments,[],start,end)
        target=data['target']
        self.assertEqual(target.iloc[0]['end'],start+timedelta(hours=10))
        self.assertEqual(target.iloc[-1]['end'],end)
        self.assertEqual(target['reason'].tolist(),['','Activity','Eating Soon',''])
        self.assertEqual(sum((r.end-r.time).total_seconds() for r in target.itertuples()),86400)
        # A later effective switch replaces the original target normally.
        newer=json.loads(json.dumps(profile));newer['target_low'][0]['value']=5;newer['target_high'][0]['value']=5
        treatments.append({'created_at':(start+timedelta(hours=14)).isoformat(),'originalProfileName':'New','profileJson':newer})
        updated,_=normalize_data([],treatments,[],start,end)
        self.assertEqual(updated['target'].iloc[-1]['low'],90)
        self.assertEqual(updated['target'].iloc[-1]['time'],start+timedelta(hours=14))

    def test_reason_colors_and_scaled_labeled_markers(self):
        from nightscout_charts import dataset_traces, TARGET_COLORS
        loaded=sample_data();start=datetime(2026,9,16,tzinfo=UTC)
        treatments=[]
        for i,reason in enumerate(('Activity','Eating Soon','Hypo','Custom')):
            treatments.append(dict(created_at=(start+timedelta(hours=i)).isoformat(),eventType='Temporary Target',
                                   duration=30,units='mmol',targetBottom=6.6,targetTop=6.6,reason=reason))
        for i,(kind,dose) in enumerate((('SMB',.1),('SMB',.4),('NORMAL',1),('NORMAL',4))):
            treatments.append(dict(created_at=(start+timedelta(hours=8,minutes=i)).isoformat(),type=kind,insulin=dose))
        treatments.extend([dict(created_at=(start+timedelta(hours=9)).isoformat(),carbs=10),
                           dict(created_at=(start+timedelta(hours=10)).isoformat(),carbs=40)])
        loaded['data'],_=normalize_data([],treatments,[],start,start+timedelta(days=1))
        targets=dataset_traces('target',loaded,[loaded['first']],'One day','mmol/L',True)
        self.assertEqual({t.line.color for t in targets},set(TARGET_COLORS.values()))
        self.assertTrue(all(t.y[0]==6.6 for t in targets))
        self.assertEqual({v.split(' · ')[0] for t in targets for v in t.customdata},{'Activity','Eating Soon','Hypo','Custom'})
        bolus=dataset_traces('bolus',loaded,[loaded['first']],'One day','mmol/L',True)
        smb,user=bolus
        self.assertEqual(smb.marker.symbol,'triangle-up')
        self.assertEqual(user.marker.symbol,'line-ew')
        self.assertGreater(user.marker.line.width[0],0)  # stroked line forms an actual rectangle
        self.assertGreater(smb.marker.size[1],smb.marker.size[0])
        self.assertGreater(user.marker.size[1],user.marker.size[0])
        self.assertEqual(list(user.text),['1 U','4 U'])
        carbs=dataset_traces('carbs',loaded,[loaded['first']],'One day','mmol/L',True)[0]
        self.assertEqual(list(carbs.text),['10 g','40 g'])
        self.assertGreater(carbs.marker.size[1],carbs.marker.size[0])

    def test_axis_matching_preserves_independent_mode(self):
        loaded=sample_data();profile=go.Figure(go.Scatter(x=[0,1440],y=[1,2],name='Draft'))
        profile.update_layout(yaxis_title='U/h')
        matched=graph_figures(profile,loaded,[loaded['first']],'One day',[], 'mmol/L',True,overlay='Glucose',same_scale=True)[0]
        self.assertEqual(matched.layout.yaxis.range,matched.layout.yaxis2.range)
        self.assertEqual(matched.layout.yaxis2.matches,'y')
        independent=graph_figures(profile,loaded,[loaded['first']],'One day',[], 'mmol/L',True,overlay='Glucose',same_scale=False)[0]
        self.assertIsNone(independent.layout.yaxis2.matches)
        self.assertEqual(list(independent.layout.yaxis2.range),[0,20])
        self.assertEqual(independent.layout.hovermode,'closest')
        self.assertEqual(list(profile.data[0].y),[1,2])




class DailySummaryTests(unittest.TestCase):
    def test_summary_bins_missing_values_units_and_totals(self):
        from nightscout import daily_summary
        loaded=sample_data();start=datetime(2026,9,16,tzinfo=UTC)
        entries=[dict(date=(start+timedelta(minutes=m)).timestamp()*1000,sgv=v)
                 for m,v in [(0,54),(1,54),(2,54),(5,108),(10,216)]]
        data,_=normalize_data(entries,[],[],start,start+timedelta(days=1))
        loaded['data']['glucose']=data['glucose'];loaded['availability']={'treatments':True}
        row=daily_summary(loaded,[loaded['first']],'mmol/L')[0]
        self.assertEqual(row['observed_bins'],3)
        self.assertEqual(row['expected_bins'],288)
        self.assertAlmostEqual(row['mean'],7)
        self.assertAlmostEqual(row['sd'],(14)**.5)
        self.assertAlmostEqual(row['tir'],100/3)
        self.assertAlmostEqual(row['coverage'],100*3/288)
        self.assertEqual(row['carbs'],30);self.assertEqual(row['bolus'],2)
        mg=daily_summary(loaded,[loaded['first']],'mg/dL')[0]
        self.assertAlmostEqual(mg['mean'],row['mean']*18)
        self.assertAlmostEqual(mg['cv'],row['cv'])
        loaded['availability']['treatments']=False
        failed=daily_summary(loaded,[loaded['first']],'mmol/L')[0]
        self.assertIsNone(failed['carbs']);self.assertIsNone(failed['bolus'])

    def test_partial_day_dst_and_no_readings(self):
        from nightscout import daily_summary
        loaded=sample_data();loaded['availability']={'treatments':True}
        loaded['loaded_at']=datetime(2026,9,16,1,tzinfo=UTC)
        row=daily_summary(loaded,[loaded['first']],'mmol/L')[0]
        self.assertEqual(row['expected_bins'],12);self.assertTrue(row['partial'])
        self.assertEqual(row['through'],'01:00')
        self.assertEqual(row['carbs'],0)
        self.assertIsNone(row['sd'])
        for day,hours in ((date(2026,3,29),23),(date(2026,10,25),25)):
            start,end=utc_bounds(day,day,'Europe/Amsterdam')
            loaded['zone']='Europe/Amsterdam';loaded['loaded_at']=end
            row=daily_summary(loaded,[day],'mmol/L')[0]
            self.assertEqual(row['expected_bins'],hours*12)
            self.assertEqual(row['coverage'],0)
            self.assertIsNone(row['tir']);self.assertIsNone(row['mean'])

    def test_navigation_has_all_loaded_days_and_no_credentials(self):
        from graph_view import navigation_bundle,viewer_html
        loaded=sample_data();loaded['token']='not-for-browser'
        profile=go.Figure(go.Scatter(x=[0,1440],y=[1,1],name='SPECS NAVIGATION'))
        profile.update_layout(title='Basal',yaxis_title='U/h')
        view=dict(loaded=loaded,days=[loaded['last']],mode='Median + band',layers=['Glucose'],overlay='Glucose')
        bundle=navigation_bundle(profile,view,'mmol/L',True)
        self.assertEqual(bundle['days'],['2026-09-16','2026-09-17'])
        self.assertNotIn('not-for-browser',json.dumps(bundle))
        self.assertNotIn(loaded['site'],json.dumps(bundle))
        self.assertEqual({t.get('meta',{}).get('date') for t in bundle['figures'][1]['data'] if t.get('meta')},set(bundle['days']))
        html=viewer_html([profile],True,bundle)
        self.assertIn('previous-day',html);self.assertIn('Plotly.react',html)
        self.assertIn('Daily summary',html);self.assertIn('SPECS NAVIGATION',html)


if __name__ == '__main__':
    unittest.main()
