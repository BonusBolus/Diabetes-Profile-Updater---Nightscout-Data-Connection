"""Reusable report dates and resilient saved-preset loading."""
from datetime import date
from pathlib import Path
import json
import tempfile
import unittest
from report_config import settings, save_preset, presets, request_for_preset

class Health49Tests(unittest.TestCase):
    def test_loaded_dates_resolve_against_each_data_snapshot_without_mutating_preset(self):
        raw=dict(date_mode='loaded',first='2026-09-01',last='2026-09-07',blocks=[dict(key='daily')],viewer={'panels':[]})
        with tempfile.TemporaryDirectory() as folder:
            save_preset('Daily',raw,folder)
            for first,last in [(date(2026,10,1),date(2026,10,7)),(date(2026,10,8),date(2026,10,15))]:
                request=request_for_preset('Daily',folder,loaded=dict(first=first,last=last))
                self.assertEqual((request['first'],request['last']),(str(first),str(last)))
            self.assertEqual(presets(folder)[0]['settings']['first'],'2026-09-01')

    def test_legacy_fixed_dates_remain_explicit_and_unavailable_dates_have_repair_guidance(self):
        with tempfile.TemporaryDirectory() as folder:
            save_preset('Legacy',dict(first='2026-09-01',last='2026-09-07',blocks=[dict(key='daily')]),folder)
            self.assertEqual(presets(folder)[0]['settings']['date_mode'],'fixed')
            with self.assertRaisesRegex(ValueError,'Use loaded dates'):
                request_for_preset('Legacy',folder,loaded=dict(first=date(2026,10,1),last=date(2026,10,7)))

    def test_one_corrupt_preset_does_not_break_the_remaining_presets(self):
        with tempfile.TemporaryDirectory() as folder:
            save_preset('Good',dict(blocks=[dict(key='daily')]),folder)
            for name,value in [('broken','{'),('list','[]'),('missing-name',json.dumps(dict(format='profile-studio-report',version=2,settings={})) )]:
                (Path(folder)/(name+'.json')).write_text(value)
            errors=[];available=presets(folder,errors=errors)
            self.assertEqual([p['name'] for p in available],['Good']);self.assertEqual(len(errors),3)
            self.assertEqual(request_for_preset('Good',folder,loaded=dict(first=date(2026,10,1),last=date(2026,10,2)))['first'],'2026-10-01')

    def test_invalid_settings_cannot_overwrite_a_working_preset(self):
        with tempfile.TemporaryDirectory() as folder:
            valid=dict(first='2026-10-01',last='2026-10-02',blocks=[dict(key='daily')])
            save_preset('Daily',valid,folder)
            for changes in [dict(first='2026-10-03'),dict(date_mode='unknown'),dict(from_time='20:00',until_time='06:00')]:
                with self.assertRaises(ValueError):save_preset('Daily',dict(valid,**changes),folder)
                self.assertEqual(presets(folder)[0]['settings']['first'],'2026-10-01')

    def test_legacy_preset_without_dates_uses_loaded_dates(self):
        self.assertEqual(settings(dict(sections=['daily']))['date_mode'],'loaded')

    def test_empty_selected_graph_block_is_reported_before_export(self):
        from test_health42 import data
        from report_export import build_report
        loaded,days=data()
        with self.assertRaisesRegex(ValueError,'No report content'):
            build_report(loaded,dict(unit='mmol/L',layers=['Glucose'],data_only=True),dict(first=str(days[0]),last=str(days[1]),blocks=[dict(key='daily')],config=dict(workspaceVersion=2,panels=[])))

if __name__=='__main__':unittest.main()
