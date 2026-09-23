from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from profiles import daily_basal, load_profiles, save_profile

ROOT = Path(__file__).resolve().parents[1]


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        for path in (ROOT/'data/profiles').glob('*.json'):
            shutil.copyfile(path,Path(self.folder.name)/path.name)
        env = patch.dict(os.environ,{'PROFILE_STUDIO_DATA':self.folder.name})
        env.start()
        self.addCleanup(env.stop)
        self.at = AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run()
        self.clean()

    def clean(self):
        self.assertFalse(self.at.exception,[x.value for x in self.at.exception])

    def button(self,label):
        return next(x for x in self.at.button if x.label==label)

    def test_readonly_modes_preserve_draft_and_show_saved_only(self):
        self.add_reference('Drinking', .9)
        at=self.at;at.run()
        at.number_input(key='dia_1').set_value(9.7).run()
        before=deepcopy(at.session_state.draft)
        files={p.name:p.read_bytes() for p in Path(self.folder.name).glob('*.json')}
        for mode,count in [('View',1),('Compare',2)]:
            with patch('streamlit.plotly_chart') as draw:
                at.radio(key='page').set_value(mode).run();self.clean()
            figure=self.figures(draw.call_args_list)['readonly_plot_ic']
            self.assertEqual(len(figure.data),count)
            self.assertTrue(all(t.meta['label'] != 'Draft' for t in figure.data))
            self.assertEqual(figure.layout.yaxis.rangemode,'normal')
            self.assertFalse(any(b.label in ('Save as new version','Overwrite existing profile') for b in at.button))
            self.assertEqual(at.session_state.draft,before)
        at.radio(key='page').set_value('Editor').run();self.clean()
        self.assertEqual(at.session_state.draft,before)
        self.assertEqual(files,{p.name:p.read_bytes() for p in Path(self.folder.name).glob('*.json')})

    def test_chosen_version_and_explicit_replacement(self):
        at=self.at
        at.number_input(key='version_1_standard').set_value(23).run();self.clean()
        self.button('Save as new version').click().run();self.clean()
        self.assertEqual({p['version'] for p in load_profiles(self.folder.name)[0]},{17,23})
        original=next(p for p in load_profiles(self.folder.name)[0] if p['version']==17)
        at.number_input(key='version_1_standard').set_value(17).run();self.clean()
        self.assertTrue(self.button('Replace selected version').disabled)
        at.number_input(key='dia_1').set_value(9.3).run()
        next(c for c in at.checkbox if c.label.startswith('Replace Standard v17')).check().run()
        self.button('Replace selected version').click().run();self.clean()
        saved=load_profiles(self.folder.name)[0]
        self.assertEqual(len(saved),2)
        replaced=next(p for p in saved if p['version']==17)
        self.assertEqual(replaced['id'],original['id'])
        self.assertEqual(replaced['overview']['dia_hours'],9.3)

    def test_repeated_edits_bulk_save_reload_and_history(self):
        at = self.at
        baseline = next(Path(self.folder.name).glob('*.json')).read_bytes()
        key='schedule_1_basal_0'
        at.session_state[key]={'edited_rows':{0:{'value':1.0}},'added_rows':[],'deleted_rows':[]}
        at.run(); self.clean()
        self.assertAlmostEqual(daily_basal(at.session_state.draft['schedules']['basal']),18.8)
        # A second edit must not undo the first or apply it twice.
        at.session_state[key]={'edited_rows':{0:{'value':1.0},1:{'value':.7}},'added_rows':[],'deleted_rows':[]}
        at.run(); self.clean()
        self.assertAlmostEqual(daily_basal(at.session_state.draft['schedules']['basal']),19.2)
        at.text_input(key='from_1_basal').set_value('05:30')
        at.text_input(key='until_1_basal').set_value('09:15')
        at.number_input(key='pct_1_basal').set_value(10)
        # AppTest has no data_editor driver. Replay its frontend edit state on
        # the next event; a real browser sends this state automatically.
        at.session_state[key]={'edited_rows':{0:{'value':1.0},1:{'value':.7}},'added_rows':[],'deleted_rows':[]}
        at.button(key='FormSubmitter:bulk_1_basal-Apply percentage').click().run()
        self.clean()
        self.assertAlmostEqual(daily_basal(at.session_state.draft['schedules']['basal']),19.475)
        at.number_input(key='dia_1').set_value(9.0).run()
        self.button('Save as new version').click().run(); self.clean()
        profiles,errors=load_profiles(self.folder.name)
        self.assertFalse(errors)
        self.assertEqual(len(profiles),2)
        self.assertEqual(profiles[-1]['version'],18)
        self.assertEqual(profiles[-1]['overview']['dia_hours'],9)
        self.assertTrue(any(p.read_bytes()==baseline for p in Path(self.folder.name).glob('*.json')))
        self.assertTrue(self.button('Save as new version').disabled)
        # Switching reference must leave the draft intact.
        snapshot=deepcopy(at.session_state.draft)
        at.selectbox(key='reference_id').select(profiles[-1]['id']).run(); self.clean()
        self.assertEqual(at.session_state.draft,snapshot)
        at.checkbox(key='show_history').set_value(True).run(); self.clean()
        self.assertEqual(len(at.dataframe[0].value),2)
        at.checkbox(key='show_history').set_value(False).run(); self.clean()
        self.assertEqual(at.session_state.draft,snapshot)
        fresh=AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run()
        self.assertFalse(fresh.exception)
        self.assertEqual(fresh.session_state.draft['overview']['dia_hours'],9)

    def test_invalid_table_blocks_save_and_new_category_starts_at_one(self):
        at=self.at
        key='schedule_1_ic_0'
        at.session_state[key]={'edited_rows':{0:{'value':0}},'added_rows':[],'deleted_rows':[]}
        at.run(); self.clean()
        self.assertTrue(self.button('Save as new version').disabled)
        self.assertTrue(at.error)
        at.session_state[key]={'edited_rows':{},'added_rows':[],'deleted_rows':[]}
        at.text_input(key='category_1').set_value('Exercise').run(); self.clean()
        self.button('Save as new version').click().run(); self.clean()
        profiles,errors=load_profiles(self.folder.name)
        exercise=next(p for p in profiles if p['category']=='Exercise')
        self.assertEqual(exercise['version'],1)

    def test_navigation_keeps_unsaved_table_and_overview_fields(self):
        at=self.at
        edits={'edited_rows':{0:{'value':12.0}},'added_rows':[],'deleted_rows':[]}
        at.session_state['schedule_1_ic_0']=edits
        at.session_state['extra_1']={'edited_rows':{},'added_rows':[{'Field':'Activity','Type':'Text','Value':'Example note'}],'deleted_rows':[]}
        at.run(); self.clean()
        self.assertEqual(at.session_state.draft['schedules']['ic'][0]['value'],12)
        at.checkbox(key='show_history').set_value(True).run(); self.clean()
        at.checkbox(key='show_history').set_value(False).run(); self.clean()
        self.assertEqual(at.session_state.draft['schedules']['ic'][0]['value'],12)
        self.assertEqual(at.session_state.draft['overview']['extra']['Activity'],'Example note')

    def test_excel_import_is_manual_and_does_not_save_automatically(self):
        uploaded = BytesIO((ROOT/'examples/profile-import.xlsx').read_bytes())
        uploaded.name = 'profiles.xlsx'
        with patch('streamlit.file_uploader',return_value=uploaded):
            before = deepcopy(self.at.session_state.draft)
            self.at.run(); self.clean()
            self.assertEqual(self.at.session_state.draft,before)
            self.assertEqual(self.at.selectbox(key='import_sheet').value,'Standard-v17')
            self.button('Import selected worksheet').click().run(); self.clean()
            imported = self.at.session_state.draft
            self.assertEqual(imported['name'],'LenStandardV17')
            self.assertEqual(imported['category'],'Standard')
            self.assertEqual(imported['overview']['dia_hours'],8.5)
            self.assertEqual(imported['source']['sheet'],'Standard-v17')
            self.assertEqual(len(load_profiles(self.folder.name)[0]),1)
            self.button('Save as new version').click().run(); self.clean()
            saved,errors = load_profiles(self.folder.name)
            self.assertFalse(errors)
            self.assertEqual(len(saved),2)
            self.assertEqual(saved[-1]['schedules'],imported['schedules'])

    def test_edit_overwrite_keeps_target_when_reference_changes(self):
        original = load_profiles(self.folder.name)[0][0]
        other = self.add_reference('Drinking', .9)
        self.at.run()
        self.at.checkbox(key='show_history').set_value(True).run()
        self.button('Edit existing profile').click().run(); self.clean()
        at = self.at
        epoch = at.session_state.epoch
        self.assertEqual(at.radio(key='page').value, 'Editor')
        self.assertEqual(at.session_state.draft['name'], original['name'])
        self.assertEqual(at.session_state.draft['notes'], original['notes'])
        self.assertEqual(at.session_state.draft['effective_date'], original['effective_date'])
        self.assertTrue(at.text_input(key=f'category_{epoch}').disabled)
        at.text_input(key=f'name_{epoch}').set_value('Edited standard').run()
        at.number_input(key=f'dia_{epoch}').set_value(9).run()
        at.selectbox(key='reference_category').select('Drinking').run()
        self.button('Overwrite existing profile').click().run(); self.clean()
        saved, errors = load_profiles(self.folder.name)
        self.assertFalse(errors)
        self.assertEqual(len(saved), 2)
        changed = next(p for p in saved if p['id'] == original['id'])
        self.assertEqual(changed['version'], 17)
        self.assertEqual(changed['name'], 'Edited standard')
        self.assertEqual(changed['overview']['dia_hours'], 9)
        self.assertEqual(changed['created_at'], original['created_at'])
        self.assertEqual(changed['comparison_id'], other['id'])
        self.assertEqual(next(p for p in saved if p['id'] == other['id']), other)
        at.number_input(key=f'dia_{epoch}').set_value(9.1).run()
        self.button('Overwrite existing profile').click().run(); self.clean()
        self.assertEqual(len(load_profiles(self.folder.name)[0]), 2)
        at.number_input(key=f'dia_{epoch}').set_value(9.2).run()
        self.button('Save as new version').click().run(); self.clean()
        saved, errors = load_profiles(self.folder.name)
        self.assertFalse(errors)
        self.assertEqual(len(saved), 3)
        new = next(p for p in saved if p['category'] == 'Standard' and p['version'] == 18)
        self.assertEqual(new['parent_id'], original['id'])
        self.assertIsNone(at.session_state.editing_original)
        self.assertEqual(next(p for p in saved if p['id'] == original['id'])['overview']['dia_hours'], 9.1)

    def test_cancel_changes_restores_edit_target_and_never_writes_history(self):
        at = self.at
        other = self.add_reference('Drinking', .9)
        at.run()
        self.button('Edit existing profile').click().run(); self.clean()
        initial = deepcopy(at.session_state.draft)
        original = deepcopy(at.session_state.editing_original)
        epoch = at.session_state.epoch
        at.text_input(key=f'name_{epoch}').set_value('Unsaved name').run()
        at.number_input(key=f'dia_{epoch}').set_value(9).run()
        at.number_input(key=f'pct_{epoch}_basal').set_value(10)
        at.button(key=f'FormSubmitter:bulk_{epoch}_basal-Apply percentage').click().run()
        at.selectbox(key='reference_category').select('Drinking').run()
        at.session_state[f'schedule_{epoch}_ic_0'] = {'edited_rows':{0:{'value':0}},'added_rows':[],'deleted_rows':[]}
        at.session_state[f'extra_{epoch}'] = {'edited_rows':{},'added_rows':[{'Field':'Incomplete'}],'deleted_rows':[]}
        at.run(); self.clean()
        self.assertTrue(at.session_state.invalid_edits)
        before = {p.name:p.read_bytes() for p in Path(self.folder.name).glob('*.json')}
        self.button('Cancel changes').click().run(); self.clean()
        self.assertEqual(at.session_state.draft, initial)
        self.assertEqual(at.session_state.editing_original, original)
        self.assertEqual(at.selectbox(key='reference_id').value, other['id'])
        self.assertFalse(at.session_state.invalid_edits)
        self.assertEqual(at.session_state.raw_schedules, initial['schedules'])
        self.assertEqual({p.name:p.read_bytes() for p in Path(self.folder.name).glob('*.json')}, before)
        # Once an overwrite is saved, Cancel restores that save, not the older version.
        epoch = at.session_state.epoch
        at.number_input(key=f'dia_{epoch}').set_value(9).run()
        self.button('Overwrite existing profile').click().run(); self.clean()
        saved_draft = deepcopy(at.session_state.draft)
        before = {p.name:p.read_bytes() for p in Path(self.folder.name).glob('*.json')}
        at.number_input(key=f'dia_{epoch}').set_value(10).run()
        self.button('Cancel changes').click().run(); self.clean()
        self.assertEqual(at.session_state.draft, saved_draft)
        self.assertEqual({p.name:p.read_bytes() for p in Path(self.folder.name).glob('*.json')}, before)

    def test_dark_toggle_keeps_draft_and_updates_graphs(self):
        from appearance import COLORS, LIGHT_COLORS
        from streamlit import config
        # Restore process-wide native theme after testing this local-app adapter.
        keys = ['base', 'backgroundColor', 'secondaryBackgroundColor', 'textColor', 'primaryColor']
        original = {key: config.get_option('theme.' + key) for key in keys}
        self.addCleanup(lambda: [config.set_option('theme.' + k, v) for k, v in original.items()])
        at = self.at
        at.number_input(key='dia_1').set_value(9).run()
        at.number_input(key='pct_1_basal').set_value(10)
        at.button(key='FormSubmitter:bulk_1_basal-Apply percentage').click().run()
        draft = deepcopy(at.session_state.draft)
        for dark, colors in [(True, COLORS), (False, LIGHT_COLORS)]:
            with patch('streamlit.plotly_chart') as draw:
                at.toggle(key='dark_mode').set_value(dark).run(); self.clean()
            self.assertEqual(at.session_state.draft, draft)
            self.assertEqual(config.get_option('theme.base'), 'dark' if dark else 'light')
            figures = self.figures(draw.call_args_list)
            for metric, color in colors.items():
                self.assertEqual(figures['plot_' + metric].data[-1].line.color, color)
                self.assertNotEqual(figures['plot_' + metric].data[0].line.color, color)
                self.assertEqual(figures['plot_' + metric].data[-1].line.dash, 'solid')

    def test_undo_redo_metadata_invalid_table_and_bulk_changes(self):
        at = self.at
        self.assertTrue(self.button('Undo').disabled)
        self.assertTrue(self.button('Redo').disabled)
        at.number_input(key='dia_1').set_value(9).run(); self.clean()
        self.button('Undo').click().run(); self.clean()
        self.assertEqual(at.session_state.draft['overview']['dia_hours'], 8.5)
        self.button('Redo').click().run(); self.clean()
        self.assertEqual(at.session_state.draft['overview']['dia_hours'], 9)
        epoch = at.session_state.epoch
        invalid = {'edited_rows':{0:{'value':0}},'added_rows':[],'deleted_rows':[]}
        key = f'schedule_{epoch}_ic_0'
        at.session_state[key] = deepcopy(invalid)
        at.run(); self.clean()
        self.assertTrue(at.session_state.invalid_edits)
        at.session_state[key] = deepcopy(invalid)  # Replay the browser editor state.
        self.button('Undo').click().run(); self.clean()
        self.assertFalse(at.session_state.invalid_edits)
        self.button('Redo').click().run(); self.clean()
        self.assertTrue(at.session_state.invalid_edits)
        self.button('Undo').click().run(); self.clean()
        epoch = at.session_state.epoch
        before = deepcopy(at.session_state.draft)
        at.number_input(key=f'pct_{epoch}_basal').set_value(10)
        at.button(key=f'FormSubmitter:bulk_{epoch}_basal-Apply percentage').click().run(); self.clean()
        self.assertTrue(self.button('Redo').disabled)
        self.assertAlmostEqual(daily_basal(at.session_state.draft['schedules']['basal']), 19.8)
        self.button('Undo').click().run(); self.clean()
        self.assertEqual(at.session_state.draft, before)
        self.button('Redo').click().run(); self.clean()
        self.assertAlmostEqual(daily_basal(at.session_state.draft['schedules']['basal']), 19.8)
        self.button('Save as new version').click().run(); self.clean()
        self.assertTrue(self.button('Undo').disabled)
        self.assertTrue(self.button('Redo').disabled)

    def test_linked_profile_comparison_and_review_baseline(self):
        at = self.at
        standard = load_profiles(self.folder.name)[0][0]
        baseline = deepcopy(at.session_state.review_baseline)
        at.text_input(key='category_1').set_value('Drinking').run()
        at.selectbox(key='link_1').select(standard['id']).run()
        at.number_input(key='dia_1').set_value(9).run()
        self.button('Save as new version').click().run(); self.clean()
        drinking = next(p for p in load_profiles(self.folder.name)[0] if p['category']=='Drinking')
        self.assertEqual(drinking['linked_profile_id'], standard['id'])
        at.selectbox(key='reference_category').select('Drinking').run()
        snapshot = deepcopy(at.session_state.draft)
        self.button('Compare linked profile').click().run(); self.clean()
        self.assertEqual(at.selectbox(key='second_reference_id').value, standard['id'])
        self.assertEqual(at.session_state.draft, snapshot)
        self.button('Edit existing profile').click().run(); self.clean()
        epoch = at.session_state.epoch
        self.assertEqual(at.selectbox(key=f'link_{epoch}').value, standard['id'])
        at.number_input(key=f'dia_{epoch}').set_value(10).run()
        # Review remains bound to Drinking, even after changing Reference 1.
        at.selectbox(key='reference_category').select('Standard').run(); self.clean()
        self.assertEqual(at.session_state.review_baseline, drinking)
        rows = next(item.value for item in at.dataframe if 'Setting' in item.value.columns)
        dia = rows[rows['Setting']=='DIA (hours)'].iloc[0]
        self.assertEqual((dia['Before'], dia['After']), ('9.0', '10.0'))
        self.button('Cancel changes').click().run(); self.clean()
        self.assertTrue(self.button('Undo').disabled)
        self.assertTrue(self.button('Redo').disabled)

    def add_reference(self, category, multiplier=1.0, glucose_unit='mmol/L'):
        profile = deepcopy(load_profiles(self.folder.name)[0][0])
        profile['name'] = category + ' test profile'
        profile['category'] = category
        profile['overview']['glucose_unit'] = glucose_unit
        for row in profile['schedules']['basal']:
            row['value'] = round(row['value'] * multiplier,6)
        return save_profile(self.folder.name,profile)

    def figures(self, calls):
        return {call.kwargs['key']:call.args[0] for call in calls if 'key' in call.kwargs}

    def test_two_references_compare_edit_switch_save_and_reload(self):
        standard17 = load_profiles(self.folder.name)[0][0]
        drinking = self.add_reference('Drinking', .9)
        standard18 = self.add_reference('Standard', 1.1)
        before = {p.name:p.read_bytes() for p in Path(self.folder.name).glob('*.json')}
        at = self.at
        at.run(); self.clean()
        at.selectbox(key='reference_category').select('Drinking').run(); self.clean()
        self.button('Copy reference to a new draft').click().run(); self.clean()
        self.assertEqual(at.session_state.draft['parent_id'],drinking['id'])
        at.checkbox(key='compare_second').check().run(); self.clean()
        self.assertEqual(at.selectbox(key='second_reference_category').value,'Standard')
        self.assertEqual(at.selectbox(key='second_reference_id').value,standard18['id'])
        initial = deepcopy(at.session_state.draft)
        with patch('streamlit.plotly_chart') as draw:
            at.selectbox(key='second_reference_id').select(standard17['id']).run(); self.clean()
        self.assertEqual(at.session_state.draft,initial)
        fig = self.figures(draw.call_args_list)['plot_basal']
        self.assertEqual([trace.name for trace in fig.data],[drinking['name'],standard17['name'],initial['name']])
        self.assertEqual([trace.line.dash for trace in fig.data],['dash','dot','solid'])
        self.assertEqual(len({trace.line.color for trace in fig.data}),3)
        self.assertAlmostEqual(fig.data[0].y[0],.72)
        self.assertAlmostEqual(fig.data[1].y[0],.8)
        # Both references share one aligned table with the draft first.
        tables = [x.value for x in at.dataframe if 'Draft' in x.value.columns and any(c.startswith('Reference 2') for c in x.value.columns)]
        basal = next(x for x in tables if len(x) and x.iloc[0]['Draft'] == '0.72')
        ref2 = next(c for c in basal.columns if c.startswith('Reference 2'))
        self.assertEqual(basal.iloc[0][ref2], '0.8')
        epoch = at.session_state.epoch
        at.number_input(key=f'pct_{epoch}_basal').set_value(10)
        with patch('streamlit.plotly_chart') as draw:
            at.button(key=f'FormSubmitter:bulk_{epoch}_basal-Apply percentage').click().run(); self.clean()
        fig = self.figures(draw.call_args_list)['plot_basal']
        self.assertAlmostEqual(fig.data[-1].y[0],.792)
        self.assertAlmostEqual(fig.data[0].y[0],.72)
        self.assertAlmostEqual(fig.data[1].y[0],.8)
        edited = deepcopy(at.session_state.draft)
        at.checkbox(key='show_history').set_value(True).run(); self.clean()
        at.checkbox(key='show_history').set_value(False).run(); self.clean()
        self.assertEqual(at.session_state.draft,edited)
        # Changing the primary reference cannot overwrite the draft either.
        at.selectbox(key='reference_category').select('Standard').run(); self.clean()
        self.assertEqual(at.session_state.draft,edited)
        self.assertNotEqual(at.selectbox(key='reference_id').value,at.selectbox(key='second_reference_id').value)
        at.selectbox(key='reference_category').select('Drinking').run(); self.clean()
        at.selectbox(key='second_reference_id').select(standard17['id']).run(); self.clean()
        self.button('Save as new version').click().run(); self.clean()
        saved,errors = load_profiles(self.folder.name)
        self.assertFalse(errors)
        newest = next(p for p in saved if p['category']=='Drinking' and p['version']==2)
        self.assertEqual(newest['comparison_id'],drinking['id'])
        self.assertEqual(newest['second_comparison_id'],standard17['id'])
        self.assertEqual(newest['parent_id'],drinking['id'])
        for name,data in before.items():
            self.assertEqual((Path(self.folder.name)/name).read_bytes(),data)
        # Turn the extra comparison off without changing the draft.
        with patch('streamlit.plotly_chart') as draw:
            at.checkbox(key='compare_second').uncheck().run(); self.clean()
        self.assertEqual(len(self.figures(draw.call_args_list)['plot_basal'].data),2)
        self.assertEqual(at.session_state.draft,dict(edited,version=3))
        at.text_area(key=f'notes_{epoch}').set_value('Single reference again').run()
        self.button('Save as new version').click().run(); self.clean()
        saved = load_profiles(self.folder.name)[0]
        newest = next(p for p in saved if p['category']=='Drinking' and p['version']==3)
        self.assertIsNone(newest['second_comparison_id'])

    def test_mismatched_reference_units_only_hide_that_reference(self):
        other = self.add_reference('Other units',glucose_unit='mg/dL')
        at = self.at
        at.run(); self.clean()
        at.checkbox(key='compare_second').check().run(); self.clean()
        self.assertEqual(at.selectbox(key='second_reference_id').value,other['id'])
        with patch('streamlit.plotly_chart') as draw:
            at.run(); self.clean()
        figures = self.figures(draw.call_args_list)
        self.assertEqual(len(figures['plot_basal'].data),3)
        self.assertEqual(len(figures['plot_ic'].data),3)
        self.assertEqual(len(figures['plot_isf'].data),2)
        self.assertEqual(len(figures['plot_target'].data),4)
        self.assertTrue(any('Reference 2' in item.value for item in at.warning))
        # Swap which slot has the incompatible unit; the compatible slot survives.
        with patch('streamlit.plotly_chart') as draw:
            at.selectbox(key='reference_category').select('Other units').run(); self.clean()
        figures = self.figures(draw.call_args_list)
        self.assertEqual(len(figures['plot_isf'].data),2)
        self.assertEqual(figures['plot_isf'].data[0].name,next(p['name'] for p in load_profiles(self.folder.name)[0] if p['id']==at.session_state.second_reference_id))

    def test_nightscout_load_is_manual_and_never_changes_profile(self):
        from test_nightscout import sample_data
        loaded = sample_data()
        loaded['zone'] = 'Europe/Amsterdam'
        at = self.at
        before = deepcopy(at.session_state.draft)
        with patch('nightscout_ui.load_nightscout',return_value=loaded) as fetch:
            at.text_input(key='ns_url').set_value('https://example.test')
            at.text_input(key='ns_token').set_value('private-test-token')
            at.date_input(key='ns_from').set_value(loaded['first'])
            at.date_input(key='ns_until').set_value(loaded['last'])
            at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
            at.run(); self.clean()
            fetch.assert_not_called()
            at.session_state.editor_tab='I:C'
            with patch('graph_view.render_graphs') as draw:
                at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
                self.button('Load / refresh data').click().run(); self.clean()
            fetch.assert_called_once()
            self.assertEqual(draw.call_count,1)  # Only the active metric builds a viewer.
            self.assertEqual(at.session_state.draft,before)
            fig = draw.call_args_list[0].args[0][1]
            self.assertIn('Glucose',fig.layout.title.text)
            at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
            at.radio(key='ns_mode').set_value('Median + band').run(); self.clean()
            with patch('graph_view.render_graphs') as draw:
                at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
                at.button_group(key='ns_layers').set_value(['Glucose','Temporary basal','Boluses','Carbs','IOB','COB']).run()
                self.clean()
            fig = draw.call_args_list[0].args[0][1]
            self.assertTrue(any(t.name=='Median glucose' for t in fig.data))
            self.assertEqual(at.session_state.draft,before)
            at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
            at.button_group(key='ns_overlay_ic').set_value('Glucose').run(); self.clean()
            with patch('graph_view.render_graphs') as draw:
                at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
                at.button(key='ns_next_ic').click().run(); self.clean()
            self.assertEqual(at.session_state.ns_mode,'One day')
            self.assertEqual(at.session_state.ns_day,loaded['first'])
            top=draw.call_args_list[0].args[0][0]
            self.assertEqual(top.layout.yaxis2.side,'right')
            self.assertTrue(any(t.yaxis=='y2' for t in top.data))
            self.assertIn(str(loaded['first']),top.layout.title.text)
            self.assertEqual(at.session_state.ns_overlay,'Glucose')
            with patch('graph_view.render_graphs') as draw:
                at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
                at.toggle(key='ns_same_scale_ic').set_value(True).run(); self.clean()
            top=draw.call_args_list[0].args[0][0]
            self.assertEqual(list(top.layout.yaxis.range),list(top.layout.yaxis2.range))
            self.assertTrue(at.session_state.ns_same_scale)
            at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
            at.button(key='ns_previous_ic').click().run(); self.clean()
            self.assertEqual(at.session_state.ns_day,loaded['last'])
            self.assertEqual(at.session_state.draft,before)
            at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
            self.button('Save as new version').click().run(); self.clean()
            fetch.assert_called_once()
            for p in Path(self.folder.name).glob('*.json'):
                self.assertNotIn('private-test-token', p.read_text())
                self.assertNotIn('ns_loaded', p.read_text())
            at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
            at.checkbox(key='show_history').set_value(True).run(); self.clean()
            at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
            at.checkbox(key='show_history').set_value(False).run(); self.clean()
            fetch.assert_called_once()
            at.session_state.editor_tab='I:C'  # AppTest has no stateful-tab driver.
            at.text_input(key='tz_1').set_value('UTC').run(); self.clean()
            self.assertTrue(any('timezone changed' in w.value for w in at.warning))


if __name__=='__main__':
    unittest.main()
