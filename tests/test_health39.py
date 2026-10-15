"""Real loading progress and sidebar picker must not refetch source data."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from streamlit.testing.v1 import AppTest
from nightscout import NightscoutClient, NightscoutError, load_nightscout
from test_health31 import fixture

ROOT = Path(__file__).parents[1]


class Health39Tests(unittest.TestCase):
    def test_window_progress_reports_completed_dates_and_record_counts(self):
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        client = NightscoutClient('https://example.test', '')
        updates = []
        client.on_window = lambda *args: updates.append(args)
        def get(collection, query):
            return [dict(date=query['find[date][$gte]'], sgv=100)]
        with patch.object(client, 'get', side_effect=get):
            rows = client.records('entries/sgv', start, start + timedelta(days=5))
        self.assertEqual(len(rows), 3)
        self.assertEqual([u[2] for u in updates], [start + timedelta(days=d) for d in (2, 4, 5)])
        self.assertEqual([u[3] for u in updates], [1, 2, 3])

    def test_load_progress_preserves_partial_source_failure_semantics(self):
        updates = []
        def records(client, collection, *args, **kwargs):
            if collection == 'devicestatus':
                raise NightscoutError('Test source unavailable')
            return []
        with patch.object(NightscoutClient, 'records', records), patch.object(NightscoutClient, 'get', return_value=[]):
            data = load_nightscout('https://example.test', '', date(2026,9,1), date(2026,9,2), 'UTC', progress=lambda *args: updates.append(args))
        self.assertEqual([u[0] for u in updates], list(range(6)))
        self.assertEqual(updates[-1][:2], (5,5))
        self.assertNotIn('loop', data['loaded_categories'])
        self.assertTrue(any('IOB/COB' in warning for warning in data['warnings']))

    def test_sidebar_add_graph_does_not_reload_sources(self):
        loaded, _ = fixture()
        import pandas as pd
        for key in ('basal','basal_percent','target','cob','variable_sens'):
            loaded['data'].setdefault(key,pd.DataFrame(columns=['time','value','label']))
        loaded.update(warnings=[],has_nightscout=True,loaded_categories=['glucose','loop','treatments'])
        with TemporaryDirectory() as folder, patch.dict('os.environ', PROFILE_STUDIO_DATA=folder), patch('graph_view.render_graphs'):
            at = AppTest.from_file(str(ROOT/'app.py'), default_timeout=40).run()
            at.session_state.ns_loaded = loaded
            at.session_state.workspace_type = 'Data'
            at.run()
            self.assertFalse(at.exception)
            snapshot = at.session_state.ns_loaded
            with patch('nightscout_ui.load_nightscout') as ns, patch('garmin_ui.load_garmin') as garmin:
                at.button(key='workspace_add_graph').click().run()
                self.assertFalse(at.exception)
                self.assertEqual(at.session_state.health_picker_revision, 1)
                self.assertIs(at.session_state.ns_loaded, snapshot)
                ns.assert_not_called(); garmin.assert_not_called()


if __name__ == '__main__':
    unittest.main()
