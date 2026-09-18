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
from nightscout_charts import aligned_figure, interval_points

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
        fig = aligned_figure(profile,loaded,[loaded['first'],loaded['last']],'Median + band',
                             ['Glucose','Temporary basal','Boluses','Carbs','IOB','COB'],'mmol/L',True)
        self.assertEqual(fig.data[0].name,'Draft')
        self.assertEqual(list(fig.data[0].y),[1,1])
        self.assertEqual(fig.layout.xaxis.matches,'x8')
        self.assertTrue(any(t.name=='Median glucose' for t in fig.data))
        self.assertEqual(fig.layout.yaxis3.title.text,'Recorded temp basal · U/h')
        self.assertEqual(len(profile.data),1)
        for key,frame in loaded['data'].items():
            pd.testing.assert_frame_equal(frame,sample_data()['data'][key])


if __name__ == '__main__':
    unittest.main()
