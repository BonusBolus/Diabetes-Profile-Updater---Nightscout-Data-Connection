"""Individual sleep/glucose nights: date boundaries, gaps and report reuse."""
from pathlib import Path
import json
import subprocess
import unittest
import pandas as pd
from insights import sleep_overview,insight_figures
from test_health31 import fixture

ROOT=Path(__file__).parents[1]


class Health46Tests(unittest.TestCase):
    def test_wake_date_selection_keeps_previous_evening_and_stops_at_next_sleep(self):
        loaded,days=fixture()
        rows=sleep_overview(loaded,[days[1]],'mmol/L')
        self.assertEqual(len(rows),1)
        row=rows[0]
        self.assertEqual(row['start'],-2)
        self.assertEqual(row['wake'],6)
        self.assertEqual(row['x'][0],-2)
        self.assertEqual(len(row['stages']),4)
        self.assertEqual(row['end'],18)
        self.assertEqual(row['glucose'][0],5)
        # A nap ends the post-wake window, independently of selected wake dates.
        loaded['garmin_sleep_sessions'].append(dict(time=pd.Timestamp('2026-09-26T09:00Z'),end=pd.Timestamp('2026-09-26T10:00Z')))
        loaded['_chart_cache']={}
        self.assertEqual(sleep_overview(loaded,[days[1]],'mmol/L')[0]['end'],9)

    def test_gaps_unknown_stages_and_dst_are_not_fabricated(self):
        loaded,days=fixture()
        frame=loaded['data']['glucose'];loaded['data']['glucose']=frame[~frame.time.between('2026-09-26T02:00Z','2026-09-26T03:00Z')]
        row=sleep_overview(loaded,[days[1]],'mg/dL')[0]
        self.assertIn(None,row['glucose']);self.assertEqual(row['glucose'][0],90)
        # Fall-back repeats 02:00; the curve breaks instead of drawing backwards.
        loaded['zone']='Europe/Amsterdam';loaded['last']=pd.Timestamp('2026-10-25').date();loaded['loaded_at']=pd.Timestamp('2026-10-26T00:00Z')
        loaded['data']['g_sleep']=pd.DataFrame()
        loaded['data']['g_sleep_hrv']=pd.DataFrame()
        loaded['garmin_sleep_sessions']=[dict(time=pd.Timestamp('2026-10-24T21:00Z'),end=pd.Timestamp('2026-10-25T06:00Z'))]
        loaded['data']['glucose']=pd.DataFrame(dict(time=pd.date_range('2026-10-24T21:00Z','2026-10-25T08:00Z',freq='5min'),value=108))
        loaded['_chart_cache']={}
        row=sleep_overview(loaded,[loaded['last']],'mmol/L')[0]
        self.assertEqual((row['start'],row['wake']),(-1,7))
        self.assertEqual(row['stages'],[])
        self.assertIn(None,row['x'])
        self.assertTrue(any(c and '+0200' in c for c in row['clocks']))
        self.assertTrue(any(c and '+0100' in c for c in row['clocks']))
        loaded['data']['g_sleep']=pd.DataFrame([dict(time=pd.Timestamp('2026-10-25T00:45Z'),end=pd.Timestamp('2026-10-25T01:15Z'),stage='rem_sleep')])
        loaded['_chart_cache']={}
        row=sleep_overview(loaded,[loaded['last']],'mmol/L')[0]
        self.assertEqual([(s['start'],s['end']) for s in row['stages']],[(2.75,3),(2,2.25)])

    def test_shared_renderer_clips_window_and_preserves_every_report_night(self):
        loaded,days=fixture()
        figure=insight_figures(loaded,days,'mmol/L',False,{'insight_sleep'})[0]
        setup="const assert=require('assert');const navigation={unit:'mmol/L'};\n"
        checks="""
const original=JSON.parse(JSON.stringify(view));
renderSleepOverview(view,view.layout.meta.sleep_overview_rows,{overviewAfterHours:0});
const curves=view.data.filter(t=>t.meta?.kind==='sleep_overview_glucose');
assert.equal(curves.length,3);
assert(curves.every(t=>Math.max(...t.x.filter(Number.isFinite))<=view.layout.meta.sleep_overview_rows.find(r=>r.date===t.meta.date).wake));
assert(view.data.some(t=>t.meta?.kind==='sleep_overview_stage'));
assert.deepEqual(view.layout.yaxis.range,view.layout.yaxis3.range);
assert(view.layout.meta.insight_note.includes('no averaging'));
const reports=reportSleepOverviewViews(view,{height:200,capacity:6});
assert.equal(reports.length,3);
assert(reports.every(v=>v.data.filter(t=>t.meta?.kind==='sleep_overview_glucose').length===1));
assert.deepEqual(reports[0].layout.xaxis.range,reports[2].layout.xaxis.range);
assert.deepEqual(original.layout.meta.sleep_overview_rows,view.layout.meta.sleep_overview_rows);
"""
        code=setup+(ROOT/'insights_view.js').read_text()+(ROOT/'sleep_insight_view.js').read_text()+"\nconst view="+figure.to_json()+";\n"+checks
        result=subprocess.run(['node','-e',code],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
