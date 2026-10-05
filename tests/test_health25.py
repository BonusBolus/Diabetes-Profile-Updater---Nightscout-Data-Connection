"""Base-profile provenance, export presets, event clipping and closed fills."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from nightscout import recorded_profiles
from report_export import profile_pages,build_report
from report_config import save_preset,presets
from profile_events import profile_events

class Health25Tests(unittest.TestCase):
    def test_percent_states_share_base_and_requested_switch_is_not_activation(self):
        start=datetime(2026,9,25,tzinfo=timezone.utc);end=start+timedelta(days=1)
        base=dict(basal=[dict(time='00:00',value=1)],units='mmol/L')
        events=[dict(created_at=start.isoformat(),eventType='Profile Switch',originalProfileName='Standard',profileJson=base)]
        for hour,p in [(1,100),(2,80),(3,90)]:
            events.append(dict(created_at=(start+timedelta(hours=hour)).isoformat(),originalProfileName='Standard',originalPercentage=p,profileJson=dict(basal=[dict(time='00:00',value=p/100)])))
        history=recorded_profiles(events,start,end)
        self.assertEqual(len(history),3);self.assertTrue(all(r['base_profile']==base for r in history))
        loaded=dict(recorded_profiles=history,loaded_at=end,zone='UTC',first=start.date(),last=start.date())
        pages=profile_pages(loaded,[start.date()],[0,1440]);self.assertEqual(len(pages),1)
        self.assertIn('Base profiles',pages[0]['title']);self.assertNotIn('0.8',pages[0]['html'])
        overlays=profile_events(loaded);self.assertEqual(overlays[1]['minute'],120)
        self.assertEqual(overlays[1]['intervals'],[dict(date='2026-09-25',start=120,end=180)])

    def test_expired_state_stops_without_fabricating_reversion(self):
        start=datetime(2026,9,25,tzinfo=timezone.utc);end=start+timedelta(days=1)
        expiry=start+timedelta(hours=2)
        history=recorded_profiles([dict(created_at=(start-timedelta(hours=1)).isoformat(),originalProfileName='Standard',originalPercentage=80,originalEnd=expiry.timestamp()*1000)],start,end)
        self.assertEqual(history[0]['end'],expiry.isoformat());self.assertEqual(history[0]['active_at'],(start-timedelta(hours=1)).isoformat())
        self.assertIsNone(history[0]['base_profile'])

    def test_report_presets_are_separate_and_validate_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings=dict(layout='portrait',graphs_per_page=4,sections=['daily'],first='2026-09-25',last='2026-09-25')
            save_preset('../Daily',settings,tmp);save_preset('../Daily',dict(settings,graphs_per_page=3),tmp)
            self.assertEqual(len(list(Path(tmp).glob('*.json'))),1)
            self.assertEqual(presets(tmp)[0]['settings']['graphs_per_page'],3)
            with self.assertRaises(ValueError):save_preset('bad',dict(settings,graphs_per_page=0),tmp)

    def test_closed_fills_never_bridge_gaps(self):
        script=Path(__file__).parents[1]/'filled_regions.js'
        code=script.read_text()+'''
const assert=require('assert');
const v={data:[{x:[0,5,null,600,605],y:[10,9,null,20,19],fill:'tozeroy',line:{shape:'hv'}}]};
closeFilledRegions(v);assert.equal(v.data.length,3);assert.equal(v.data[2].fill,'none');
assert(v.data[0].x.every(x=>x<=5));assert(v.data[1].x.every(x=>x>=600));
for(const t of v.data.slice(0,2)){assert.equal(t.y[0],0);assert.equal(t.y.at(-1),0);assert.equal(t.hoverinfo,'skip');}
const band={data:[{x:[0,5,10,15,20],y:[1,1,null,3,3]},{x:[0,5,10,15,20],y:[2,2,null,4,4],fill:'tonexty'}]};
closeFilledRegions(band);assert.equal(band.data.length,3);assert(band.data[1].x.every(x=>x<=5));assert(band.data[2].x.every(x=>x>=15));
'''
        result=subprocess.run(['node','-e',code],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
