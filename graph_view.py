"""An offline Plotly viewer: profile pinned above scrollable recorded panels."""
from functools import lru_cache
from datetime import timedelta
import json
import hashlib
import uuid
from pathlib import Path
from custom_graph import custom_bundle
from garmin_data import GARMIN_LAYERS
from profile_events import profile_events
from garmin_charts import activity_shapes, SLEEP_DAY_HEIGHT
from date_controls import loaded_days

from plotly.offline import get_plotlyjs
import streamlit as st
from streamlit.components.v1 import declare_component
from view_config import save_configuration

graph_component=declare_component("profile_studio_graphs",path=str(Path(__file__).with_name("graph_component")))

from appearance import palette
from chart_cache import cached
from nightscout import daily_summary
from nightscout_charts import graph_figures, OVERLAY_CHOICES, hourly_figure, add_profile_guides


@lru_cache(maxsize=1)
def plotly_script():
    return get_plotlyjs()


def figure_identity(figure):
    meta=figure.layout.meta or {}
    if not meta.get('dataset') and not meta.get('kind'):return 'profile:settings'
    return str(meta.get('kind',''))+':'+str(meta.get('dataset') or figure.layout.title.text.split(' · ')[0])


def mode_banks(profile,view,unit,dark,initial=None):
    if len(set(view['days']))<2:return {}
    result={}
    for mode in ('Multiple days','Median + band'):
        figs=initial if initial is not None and mode==view['mode'] else graph_figures(profile,**dict(view,mode=mode),unit=unit,dark=dark)
        result[mode]={figure_identity(f):json.loads(f.to_json()) for f in figs}
    return result


def navigation_bundle(profile, view, unit, dark, profiles=None, metric=None, custom_profiles=None, initial=None, progress=None):
    if view.get('export_workspace'):
        report_days=loaded_days(view['loaded'])
        if list(view['days'])!=report_days:initial=None
        view=dict(view,days=report_days,mode='Median + band' if len(report_days)>1 else 'One day')
    workspace_graphs=view.get('workspace_graphs',False);export_workspace=view.get('export_workspace',False)
    initial_targets=view.get('show_targets',True)
    initial_scale=view.get('same_scale',False)
    custom_ids=view.get('custom_ids');custom_catalog=view.get('custom_catalog')
    view={k:v for k,v in view.items() if k not in ('custom_ids','custom_catalog','workspace_graphs','export_workspace')}
    view=dict(view,show_targets=True,same_scale=False)
    loaded = view['loaded']
    days = loaded_days(loaded)
    if initial is None:initial=graph_figures(profile,**view,unit=unit,dark=dark)
    if progress:progress(1,6,'Summary data and Insights')
    banks=mode_banks(profile,view,unit,dark,initial)
    # One batch of dated traces lets the browser filter locally without an app
    # rerun, which would destroy fullscreen. No tokens or server URLs are sent.
    if progress:progress(2,6,'Daily timelines')
    daily = graph_figures(profile, **dict(view, days=days, mode='One day'), unit=unit, dark=dark)
    by_id={figure_identity(f):f for f in daily}
    daily=[by_id.get(figure_identity(f),f) for f in initial]
    if progress:progress(3,6,'Profile overlays')
    overlays = {}
    for option in (['None'] if view.get('data_only') else OVERLAY_CHOICES):
        if option in GARMIN_LAYERS and ('g_steps' if GARMIN_LAYERS[option]=='g_steps_cumulative' else GARMIN_LAYERS[option]) not in loaded["data"]:continue
        options = dict(view, layers=[], overlay=option,profile_only=True)
        # Initial variants preserve median/multiple-day mode; daily variants
        # support local date navigation without requests or leaving fullscreen.
        initial_top = initial[0] if option==view.get('overlay','None') else graph_figures(profile, **options, unit=unit, dark=dark)[0]
        daily_top = daily[0] if option == view.get('overlay', 'None') else graph_figures(
            profile, **dict(options, days=days, mode='One day'), unit=unit, dark=dark)[0]
        overlays[option] = dict(selected=json.loads(initial_top.to_json()), daily=json.loads(daily_top.to_json()),modes={})
        if len(set(view['days']))>1:
            for display_mode in ('Multiple days','Median + band'):
                if display_mode==view['mode']:serialized=overlays[option]['selected']
                elif option==view.get('overlay','None'):serialized=banks[display_mode]['profile:settings']
                else:serialized=json.loads(graph_figures(profile,**dict(options,mode=display_mode),unit=unit,dark=dark)[0].to_json())
                overlays[option]['modes'][display_mode]=serialized
    if progress:progress(4,6,'Hourly distributions and custom graph data')
    bolus_variants = {}
    if len(set(view['days']))>1 and 'IOB + Boluses' in view['layers']:
        for label, selected in [('selected',view['days']),('daily',days)]:
            fig = hourly_figure(loaded,'bolus',selected,dark,exclude_smb=True)
            add_profile_guides(fig,(profile.layout.meta or {}).get('profile_changes',[]),dark)
            bolus_variants[label] = json.loads(fig.to_json())
    custom=custom_bundle(loaded,view['days'],days,view['mode'],unit,dark,custom_profiles if custom_profiles is not None else profiles or {}) if 'Custom graph' in view['layers'] else None
    if custom and len(set(view['days']))>1:
        for custom_mode in ('Multiple days','Median + band'):
            bank=custom if custom_mode==view['mode'] else custom_bundle(loaded,view['days'],days,custom_mode,unit,dark,custom_profiles if custom_profiles is not None else profiles or {})
            by_id={f['id']:f for f in bank['fields']}
            for field in custom['fields']:field.setdefault('modes',{})[custom_mode]=by_id.get(field['id'],field)['selected']
    changes=loaded['data'].get('changes')
    events=[]
    if changes is not None:
        for row in changes.itertuples():
            if row.label not in ('Site Change','Sensor Start','Sensor Change'):continue
            at=row.time.tz_convert(loaded['zone'])
            events.append(dict(date=at.date().isoformat(),minute=at.hour*60+at.minute+at.second/60,label=row.label))
    notes=[]
    frame=loaded['data'].get('automation_notes')
    if frame is not None:
        for row in frame.itertuples():
            at=row.time.tz_convert(loaded['zone'])
            notes.append(dict(date=at.date().isoformat(),minute=at.hour*60+at.minute+at.second/60,label=row.label))
    if progress:progress(5,6,'Compact overview and event context')
    from compact_glucose import basal_records
    basal=cached(loaded,'compact_basal',tuple(days),lambda: basal_records(loaded,days)) if 'Glucose Compact' in view['layers'] else []
    from nightscout_charts import LAYERS, GROUP_KEYS
    from garmin_data import METRICS
    from insights import INSIGHT_LAYERS
    unavailable=[]
    present={f.layout.meta.get('dataset') for f in initial if f.layout.meta}
    for label,key in LAYERS.items():
        if label in view['layers']:continue
        if key.startswith('insight_'):unavailable.append(dict(group='Insights',label=label));continue
        if key in ('profile_percentage','site_changes','sensor_changes'):unavailable.append(dict(group='Summary',label=label+' hourly'));continue
        for field in GROUP_KEYS.get(key,[key]):
            name=METRICS[field][0] if field in METRICS else label.removeprefix('Garmin · ')
            if field in present or field in ('bolus','carbs'):continue
            unavailable.append(dict(group='Daily',label=name+' — Daily'))
    return dict(unavailable_graphs=unavailable,compact_basal=basal,workspace_graphs=workspace_graphs,export_workspace=export_workspace,automation_notes=notes,mode_banks=banks,sleep_day_height=SLEEP_DAY_HEIGHT,report_capabilities=dict(profiles=bool(loaded.get('recorded_profiles'))),profile_events=profile_events(loaded),change_events=events,report_profile=json.loads(profile.to_json()),
                report_profiles={k:json.loads(f.to_json()) for k,f in (custom_profiles if custom_profiles is not None else profiles or {}).items()},
                day_color_dates=[str(day) for day in days],source_first=str(loaded['first']),source_last=str(loaded['last']),activity_bands=activity_shapes(loaded,days,'One day'),garmin_sleep_notes=loaded.get('garmin_sleep_notes',[]),garmin_units=loaded.get('garmin_units','Unknown'),layers=view['layers'],state_scope=st.session_state.setdefault('health_view_scope',uuid.uuid4().hex)+('-export' if export_workspace else '-view'),
                date_revision=st.session_state.get('health_date_revision',0),config_revision=st.session_state.get('health_config_revision',0),
                custom_ids=custom_ids,custom_catalog=custom_catalog,saved_config=None if export_workspace else st.session_state.get('health_view_config'),has_nightscout=loaded.get('has_nightscout',True),data_only=view.get('data_only',False),garmin_daily=loaded.get('garmin_daily',[]),garmin_activities=loaded.get('garmin_activities',[]),custom=custom,
                profiles={key:json.loads(fig.to_json()) for key,fig in (profiles or {}).items()},metric=metric,
                show_targets=initial_targets,bolus_without_smb=bolus_variants, days=[day.isoformat() for day in days], selected=[day.isoformat() for day in view['days']],
                mode=view['mode'], same_scale=initial_scale, unit=unit,
                glucose_overlay=view.get('overlay')=='Glucose', overlay=view.get('overlay','None'), overlays=overlays,
                figures=[json.loads(fig.to_json()) for fig in daily],
                summaries=cached(loaded,'daily_stats',(tuple(days),unit),lambda: daily_summary(loaded,days,unit)))


def prepared_graphs(profile, view, unit, dark, profiles=None, metric=None, custom_profiles=None):
    if view.get('export_workspace'):
        days=loaded_days(view['loaded']);view=dict(view,days=days,mode='Median + band' if len(days)>1 else 'One day')
    # The loaded snapshot is immutable until manual refresh. Profile edits only
    # rebuild the viewer; recorded traces and statistics remain reusable.
    key=(st.session_state.get('health_date_revision',0),st.session_state.get('health_config_revision',0),profile.to_json(),tuple(view['days']),view['mode'],tuple(view['layers']),
         view.get('workspace_graphs',False),view.get('export_workspace',False),view.get('data_only',False),tuple(view.get('custom_ids') or []),tuple(view.get('custom_catalog') or []),view.get('overlay','None'),view.get('show_targets',True),view.get('same_scale',False),unit,dark,metric,tuple((k,f.to_json()) for k,f in (profiles or {}).items()),
         tuple((k,f.to_json()) for k,f in (custom_profiles or {}).items()))
    def build():
        bar=st.progress(0.,text='Preparing graph data and Insights…')
        try:
            chart_view={k:v for k,v in view.items() if k not in ('custom_ids','custom_catalog','workspace_graphs','export_workspace')}
            figures=graph_figures(profile,**dict(chart_view,show_targets=True,same_scale=False),unit=unit,dark=dark)
            navigation=navigation_bundle(profile,view,unit,dark,profiles,metric,custom_profiles,initial=figures,progress=lambda n,total,label:bar.progress(n/total,text=label+' · '+str(n)+' / '+str(total)+' stages'))
            navigation['render_key']=hashlib.sha256(repr(key).encode()).hexdigest()
            bar.progress(1.,text="Graph data ready")
            return figures,navigation
        finally:bar.empty()
    return cached(view['loaded'],'prepared',key,build,limit=3)


def pack_payload(raw_payload):
    trace_pool=[];trace_index={};period_pool=[];period_index={};array_pool=[];array_index={}
    def intern(value):
        if isinstance(value,list):return [intern(v) for v in value]
        if not isinstance(value,dict):return value
        if 'glucose' in value and 'baseline' in value and 'x' in value and 'id' in value:
            encoded=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
            index=period_index.get(encoded)
            if index is None:index=len(period_pool);period_index[encoded]=index;period_pool.append(value)
            return {'$period':index}
        if 'type' in value and ('x' in value or 'z' in value) and ('y' in value or 'z' in value):
            encoded=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
            index=trace_index.get(encoded)
            if index is None:index=len(trace_pool);trace_index[encoded]=index;trace_pool.append(value)
            return {'$trace':index}
        return {k:intern(v) for k,v in value.items()}
    packed=intern(raw_payload)
    def intern_arrays(value):
        if isinstance(value,list):
            if len(value)>24:
                encoded=json.dumps(value,separators=(',',':'),allow_nan=False)
                index=array_index.get(encoded)
                if index is None:index=len(array_pool);array_index[encoded]=index;array_pool.append(value)
                return {'$array':index}
            return [intern_arrays(v) for v in value]
        if isinstance(value,dict):return {k:intern_arrays(v) for k,v in value.items()}
        return value
    packed['trace_pool']=[intern_arrays(t) for t in trace_pool];packed['period_pool']=[intern_arrays(p) for p in period_pool];packed['array_pool']=array_pool
    return packed



def viewer_html(figures, dark, navigation=None):
    # Escape all '<' in JSON so uploaded labels cannot terminate a script tag.
    specs='['+','.join(fig.to_json() for fig in figures)+']'
    specs=specs.replace('<','\\u003c')
    if navigation and not navigation.get('report_render'):
        from report_config import presets
        preset_errors=[]
        navigation=dict(navigation,report_presets=presets(errors=preset_errors),report_preset_errors=preset_errors,report_selected_preset=st.session_state.get('health_report_selected_preset'))
    navigation_json=json.dumps(navigation,allow_nan=False).replace('<','\\u003c')
    raw_payload=dict(specs=json.loads(specs),navigation=json.loads(navigation_json))
    payload_json=json.dumps(pack_payload(raw_payload),separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    theme=palette(dark)
    return """<!doctype html><html><head><meta charset="utf-8"><style>
[hidden] {display:none!important;}
html,body {margin:0;height:100%;font-family:Arial,sans-serif;background:BACKGROUND;color:TEXT;}
#viewer {height:100vh;display:flex;flex-direction:column;}
#toolbar {min-height:38px;flex:0 0 auto;flex-wrap:wrap;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 10px;box-sizing:border-box;border-bottom:1px solid GRID;}
#toolbar-left {display:flex;flex-wrap:wrap;align-items:center;gap:6px;}
#overlay-control {font-size:12px;display:flex;align-items:center;gap:5px;}

.export-workspace {padding:6px 12px;border-bottom:1px solid GRID;max-height:250px;overflow:auto;flex:0 0 auto;}
.export-workspace .report-options {position:static;width:auto;max-height:none;display:flex;flex-wrap:wrap;gap:8px 14px;box-shadow:none;border:0;padding:8px 0;}
.export-workspace h4 {flex-basis:100%;margin:3px 0;font-size:12px;color:#35a0a0;}
.export-workspace label {display:inline-flex;gap:5px;align-items:center;font-size:12px;}
.export-workspace p {flex-basis:100%;margin:0;}
.graph-picker {padding:10px 14px;border:1px solid GRID;border-radius:7px;margin:8px;background:SURFACE;}
.graph-picker .tiles {display:flex;flex-wrap:wrap;gap:6px;margin:8px 0;}
.graph-picker h4 {margin:10px 0 4px;color:#35a0a0;}
.graph-picker button {padding:7px 10px;border:1px solid #80808060;border-radius:5px;background:transparent;color:inherit;cursor:pointer;}
.graph-events {padding:4px 7px;border:1px solid #80808050;border-radius:5px;font-size:12px;}
.graph-events summary {cursor:pointer;}
.graph-events .event-options {display:flex;flex-wrap:wrap;gap:8px;padding:8px 0;}
.graph-events label {display:flex;gap:4px;align-items:center;}
button[aria-pressed="true"] {outline:2px solid #22a6bb;}
.bolus-controls {padding:5px 12px;display:flex;flex-wrap:wrap;align-items:center;gap:10px;font-size:12px;}
.bolus-controls button {background:transparent;color:inherit;border:1px solid #80808080;border-radius:5px;padding:5px 10px;cursor:pointer;}
.custom-data-layers{flex-basis:100%;width:100%;border-top:1px solid GRID;padding-top:6px;}
.custom-data-layers>summary{font-weight:600;cursor:pointer;margin-bottom:6px;}
.custom-data-layers>input{width:min(100%,260px);margin:3px 0;}
.custom-options>strong{flex-basis:100%;font-size:11px;}
.custom-options button[aria-pressed="true"]{background:rgba(66,165,245,.15)!important;box-shadow:inset 0 0 0 1px #42a5f5;}
.custom-options button[hidden]{display:none;}
.custom-options {display:flex;flex-wrap:wrap;gap:4px;padding:4px 0;}
.report-builder{display:grid!important;grid-template-columns:minmax(170px,1fr) minmax(320px,2fr);gap:14px;grid-column:1/-1;}
.report-builder>div{display:flex;flex-direction:column;gap:5px;}
.report-builder>div>strong{font-size:12px;color:#358276;margin-bottom:5px;}
.report-block-row{display:flex;align-items:center;gap:4px;border-bottom:1px solid GRID;padding:4px 0;flex-wrap:wrap;}
.report-block-row>span{flex:1;min-width:130px;font-size:12px;}.report-block-row button{padding:3px 6px;font-size:11px;}
.report-block-row.unavailable{opacity:.45;}.report-block-editor{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:8px 10px;border-block:1px solid GRID;font-size:12px;}
.report-block-editor>div{display:flex;gap:6px;}.report-block-editor button{font-size:12px;padding:5px 8px;}
@media(max-width:700px){.report-builder{grid-template-columns:1fr;}}
.report-controls {position:relative;font-size:12px;}
.insight-method-note {font-size:11px;line-height:1.25;margin:3px 0 5px;opacity:.85;}
.report-controls summary {cursor:pointer;border:1px solid GRID;border-radius:5px;padding:5px 9px;}
.report-options {position:absolute;top:30px;right:0;width:340px;max-height:70vh;overflow:auto;z-index:40;border:1px solid GRID;border-radius:7px;padding:12px;background:SURFACE;box-shadow:0 4px 16px #0005;}
.report-options label {display:flex;justify-content:space-between;gap:8px;margin:6px 0;}
.report-options input:not([type=checkbox]) {width:170px;min-width:0;background:BACKGROUND;color:TEXT;border:1px solid GRID;border-radius:4px;padding:4px;}
.report-options p {font-size:11px;line-height:1.4;}
.custom-help {flex-basis:100%;font-size:12px;opacity:.8;}
#date-calendar {position:absolute;z-index:20;top:42px;left:10px;background:SURFACE;border:1px solid GRID;border-radius:6px;padding:12px;max-height:65vh;overflow:auto;}
.calendar-grid {display:grid;grid-template-columns:repeat(7,32px);gap:3px;}
.calendar-grid button {padding:5px 2px!important;}
.calendar-month {font-weight:bold;margin:8px 0;}
#date-calendar[hidden] {display:none;}
#toolbar button,#toolbar select {border:1px solid GRID;border-radius:5px;background:SURFACE;color:TEXT;padding:4px 9px;cursor:pointer;white-space:nowrap;}
#toolbar button:disabled {opacity:.35;cursor:default;}
#day-label {font-size:12px;}
#daily-summary {font-size:12px;padding:5px 10px;border-bottom:1px solid GRID;}
#daily-summary summary {cursor:pointer;}
#summary-body {max-height:135px;overflow:auto;}
#summary-body table {border-collapse:collapse;width:100%;font-size:12px;}
#summary-body th,#summary-body td {padding:4px 8px;text-align:right;white-space:nowrap;border-bottom:1px solid GRID;}
#summary-body th:first-child,#summary-body td:first-child {text-align:left;}
#summary-body p {margin:6px 0;opacity:.8;}
#hover-card {min-width:0;max-width:100%;overflow-wrap:anywhere;font-size:13px;line-height:1.25;text-align:right;display:flex;flex-wrap:wrap;justify-content:flex-end;gap:3px 12px;pointer-events:none;}
.hover-readout strong {font-size:12px;font-weight:600;color:TEXT;}
.hover-readout strong:empty {display:none;}
.hover-readout .muted {opacity:.8;font-size:11px;}
.hover-readout .hover-name {font-weight:600;border-left:3px solid var(--series-color,TEXT);padding-left:6px;}
#hover-floating {position:absolute;z-index:50;display:flex;align-items:center;flex-wrap:wrap;justify-content:flex-end;gap:4px 9px;padding:4px 6px;border:1px solid GRID;border-radius:7px;background:SURFACE;color:TEXT;box-shadow:none;pointer-events:none;font-size:11px;box-sizing:border-box;}
#hover-card {align-items:center;}
@keyframes hover-value-in {from {transform:scale(.94);background:rgba(66,165,245,.3);} to {transform:scale(1);}}
@media (prefers-reduced-motion:reduce) {.hover-readout strong {animation:none;}}
#profile {flex:0 0 250px;border-bottom:1px solid GRID;background:BACKGROUND;}
#panels {flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;}
.graph {width:100%;min-width:0;position:relative;}
.target-note {flex:0 0 auto;margin:0;padding:4px 12px 10px;font-size:12px;line-height:1.4;opacity:.8;}
.target-note[hidden] {display:none;}
.hoverlayer {visibility:hidden;}
.time-guide {position:absolute;width:0;border-left:1px dashed TEXT;opacity:.65;pointer-events:none;z-index:4;display:none;}
.point-highlight {position:absolute;box-sizing:border-box;border:1px solid TEXT;border-radius:50%;box-shadow:none;background:transparent;transform:translate(-50%,-50%);pointer-events:none;z-index:5;display:none;}
.graph-content[hidden],.graph-settings[hidden] {display:none!important;}
.graph-content {display:flex;align-items:center;flex-wrap:wrap;gap:5px;}
.control-label {font-size:11px;text-transform:uppercase;letter-spacing:.05em;opacity:.65;margin-right:3px;}
.graph-content button {border-radius:14px!important;padding:3px 9px!important;}
.graph-content button[aria-pressed="true"] {box-shadow:inset 0 0 0 1px #42a5f5;background:rgba(66,165,245,.15)!important;}
.graph-settings {border:1px solid GRID;border-radius:5px;padding:4px 8px;font-size:12px;}
.settings-body {display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:8px 0 3px;}
.settings-body button {border-radius:4px!important;}
.settings-body label {display:flex;align-items:center;gap:5px;font-size:12px;}
.custom-field-settings {flex-basis:100%;}
.custom-setting-row {display:flex;flex-wrap:wrap;align-items:center;gap:5px;border-top:1px solid GRID;padding:5px 0;}
.custom-layer-heading {display:inline-flex;align-items:center;gap:5px;min-width:130px;max-width:100%;}
.custom-layer-heading strong {font-size:12px;overflow-wrap:anywhere;}
.custom-layer-remove {font-size:16px!important;line-height:1;padding:2px 5px!important;margin-left:auto;}
.custom-setting-row input[type="range"] {width:115px!important;}
.custom-graph-controls .graph-settings {flex:4 1 70%;}
.custom-graph-controls .graph-content {flex:1 1 150px;}
.custom-graph-controls .settings-body {gap:5px;padding-top:3px;}
.graph-control-row {display:flex;align-items:flex-start;justify-content:space-between;gap:12px;width:100%;box-sizing:border-box;}
.graph-settings,.graph-content {border:1px solid GRID;border-radius:7px;padding:7px 9px;box-sizing:border-box;min-width:0;}
.graph-settings {background:rgba(128,128,128,.08);flex:1 1 42%;}
.graph-content {background:rgba(66,165,245,.045);flex:1 1 42%;margin-left:auto;justify-content:flex-end;}
.graph-content>.control-label {flex-basis:100%;text-align:right;}
.settings-body {padding:4px 0 0;}
.graph-body {display:flex;align-items:stretch;}
.graph-body>.graph {flex:1;min-width:0;}
.axis-controls {flex:0 0 54px;width:54px;padding:28px 5px 0;display:flex;flex-direction:column;align-items:center;gap:6px;font-size:11px;}
.axis-controls button {background:SURFACE;color:TEXT;border:1px solid GRID;border-radius:4px;width:28px;cursor:pointer;}
.axis-floor {display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center;}
.axis-slider {writing-mode:vertical-lr;direction:rtl;}
.smoothing-value {display:inline-block;min-width:137px;font-variant-numeric:tabular-nums;white-space:nowrap;}
.settings-body input[type=range] {flex-shrink:0;}
#toolbar {padding:6px 10px;gap:6px;background:SURFACE;}
#toolbar-left {flex:1;}
#hover-card:empty {display:none;}
.settings-group {display:flex;align-items:center;flex-wrap:wrap;gap:5px;padding:2px 8px;border-left:1px solid GRID;}
.settings-group:first-child {border-left:0;padding-left:0;}
.settings-group-title {font-size:10px;opacity:.65;margin-right:3px;}
#top-graph-controls {padding:6px 10px;flex:0 0 auto;display:flex;flex-direction:column;gap:6px;}
#top-graph-controls>.graph-settings,#top-graph-controls>.graph-content {width:100%;flex:none;margin:0;padding:5px 9px;}
#top-graph-controls>.graph-content {justify-content:flex-start;align-items:flex-start;}
#top-graph-controls>.graph-content>.control-label {flex-basis:auto;line-height:26px;text-align:left;}
#top-graph-controls .settings-body {display:inline-flex;padding:0;gap:7px;margin-left:8px;}
#overlay-control {flex:1;min-width:0;font-size:0;}
#overlay-select {width:100%;max-width:380px;min-width:160px;}
#top-graph-controls button,#top-graph-controls select {font-size:12px;border:1px solid GRID;background:SURFACE;color:TEXT;border-radius:5px;padding:4px 7px;}
#panels {background:SURFACE;}
.graph-panel {margin:7px 6px 10px;background:BACKGROUND;border:1px solid GRID;border-radius:7px;overflow:hidden;}
.graph-panel .bolus-controls {padding:6px 9px;gap:8px;}
.graph-settings {border-left:3px solid #8095ab;}
.graph-content {border-left:3px solid #58a3a8;}
.axis-controls {position:relative;flex:0 0 44px;width:44px;padding:0 4px;}
.axis-move {position:absolute;top:5px;left:4px;right:4px;display:flex;gap:2px;justify-content:center;}
.axis-move button {width:23px;padding:2px;}
.axis-floor {position:absolute;top:36px;bottom:auto;width:44px;gap:3px;}
.axis-floor span {font-size:10px;line-height:12px;min-height:24px;}
.axis-slider {margin:0;min-height:35px;}

@media(max-width:650px){.graph-control-row{gap:6px;}.smoothing-value{min-width:125px;}.settings-body label{flex-wrap:wrap;}}


.graph-actions{flex:0 0 auto;max-width:145px;border:1px solid GRID;border-left:3px solid #9a91aa;background:rgba(128,128,128,.035);border-radius:6px;padding:6px 8px;display:flex;flex-wrap:wrap;gap:4px;font-size:12px;}
.graph-actions>.control-label{flex-basis:100%;font-size:10px;}
.graph-actions button{font-size:11px;padding:3px 6px;}
.graph-control-row{gap:7px;}
.graph-settings,.graph-content{padding:5px 8px;}
.settings-body{gap:5px;}
.graph-picker{width:min(680px,calc(100vw - 40px));max-height:80vh;overflow:auto;padding:15px;margin:auto;background:SURFACE;color:TEXT;box-shadow:0 12px 45px #0003;border:1px solid GRID;border-radius:10px;}
.graph-picker::backdrop{background:rgba(20,30,45,.22);}
.picker-heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}
.graph-picker input{box-sizing:border-box;width:100%;padding:8px;border:1px solid GRID;border-radius:5px;background:BACKGROUND;color:TEXT;}
.graph-picker section+section{border-top:1px solid GRID;margin-top:10px;padding-top:2px;}
.graph-picker .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:7px;}
.graph-picker .tiles button{text-align:left;border-left:4px solid var(--graph-color);background:color-mix(in srgb,var(--graph-color) 7%,SURFACE);font-size:12px;min-height:34px;}
#empty-workspace{margin:12px;font-size:13px;opacity:.7;}
.empty-workspace #panels{display:none;}
.empty-workspace #daily-summary{display:none;}
#work-progress{padding:4px 12px;display:flex;align-items:center;gap:10px;font-size:12px;flex:0 0 auto;}
#work-progress progress{width:130px;height:5px;accent-color:#399f9e;}
.export-workspace{max-height:300px;padding:6px 10px;}
.export-workspace .report-options{display:grid;grid-template-columns:repeat(2,minmax(230px,1fr));gap:8px;}
.report-section{margin:0;min-width:0;border:1px solid GRID;border-radius:6px;padding:6px 9px;background:BACKGROUND;display:flex;flex-wrap:wrap;align-items:center;gap:5px 12px;}
.report-section legend{font-size:11px;color:#469e9e;padding:0 4px;font-weight:600;}
.export-workspace .report-section label{margin:2px 0;flex-wrap:wrap;}
.export-workspace .report-section input:not([type=checkbox]){max-width:160px;}
.report-footer{grid-column:1/-1;display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;padding:5px 0;}
.report-footer p{flex-basis:100%;}
@media(max-width:650px){.graph-actions{max-width:90px;}.export-workspace .report-options{grid-template-columns:1fr;}}

.graph-actions:not(:has(button)),.graph-settings:has(> .settings-body:empty){display:none;}
.pdf-workspace{overflow-y:auto;overflow-x:hidden;}
.pdf-workspace #panels{flex:0 0 auto;overflow:visible;}
.report-workspace{flex:0 0 auto;margin:8px;border:1px solid GRID;border-radius:9px;background:SURFACE;padding:14px;font-size:12px;box-sizing:border-box;}
.report-heading{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:12px;}
.report-heading strong{font-size:16px;}.report-heading span{opacity:.7;}
.report-actions{display:flex;align-items:end;flex-wrap:wrap;gap:8px;}
.report-workspace label{display:flex;flex-direction:column;gap:5px;min-width:0;}
.report-actions label{flex:1 1 160px;}
.report-workspace input:not([type=checkbox]),.report-workspace select{box-sizing:border-box;min-width:0;width:100%;max-width:none!important;min-height:34px;padding:7px 9px;border:1px solid GRID;border-radius:5px;background:BACKGROUND;color:TEXT;font:inherit;}
.report-workspace button,.report-block-editor button{min-height:34px;padding:7px 11px;border:1px solid GRID;border-radius:5px;background:BACKGROUND;color:TEXT;font:inherit;cursor:pointer;}
.report-workspace button:disabled{opacity:.45;cursor:default;}
.report-workspace button.report-primary{background:#237d77;border-color:#237d77;color:white;font-weight:600;}
.report-workspace .report-status{margin:10px 0 0;line-height:1.5;overflow-wrap:anywhere;}
.report-status[data-state=error],.report-warning{color:#c24747;}.report-status[data-state=changed]{color:#a16c18;}
.report-workspace .report-repair{margin-top:8px;}
.report-workspace .report-controls{padding:0;margin-top:12px;max-height:none;overflow:visible;border:0;}
.report-workspace .report-controls>summary{padding:10px 0;border:0;border-top:1px solid GRID;border-radius:0;font-weight:600;}
.report-workspace .report-options{position:static;display:grid;grid-template-columns:1fr;width:auto;max-height:none;overflow:visible;box-shadow:none;border:0;padding:6px 0 0;gap:12px;z-index:auto;}
.report-workspace .report-section{padding:12px;background:BACKGROUND;}
.report-workspace .report-section:first-child{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;}
.report-workspace .report-section label{display:flex;align-items:stretch;margin:0;}
.report-workspace .report-section legend{font-size:12px;}
.report-workspace .report-builder{grid-template-columns:minmax(200px,1fr) minmax(0,2fr);align-items:start;}
.report-workspace .report-builder>div:first-of-type{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;}.report-workspace .report-builder>div:first-of-type>strong{grid-column:1/-1;}
.report-workspace .report-block-row select{width:82px;}.report-workspace .report-block-row button{padding:4px 8px;}
.report-workspace .report-measures{display:flex;gap:12px 20px;}.report-workspace .report-measures label{flex-direction:row;align-items:center;}
@media(max-width:700px){.report-workspace .report-section:first-child{grid-template-columns:repeat(2,minmax(0,1fr));}.report-workspace .report-builder{grid-template-columns:1fr;}.report-actions button{flex:1 1 auto;}}
@media(max-width:420px){.report-workspace .report-section:first-child{grid-template-columns:1fr;}}
.custom-graph-controls{display:grid;grid-template-columns:auto minmax(0,1fr) 230px;align-items:start;}
.custom-graph-controls .custom-field-settings{width:100%;min-width:0;}
.custom-graph-controls .graph-events{width:100%;min-width:0;box-sizing:border-box;}
.custom-graph-controls .event-options{display:grid;gap:6px;}
.custom-graph-controls .event-options label{display:grid;grid-template-columns:minmax(0,1fr) 100px;align-items:center;}
.custom-graph-controls .event-options select{width:100%;min-width:0;}
@media(max-width:700px){.custom-graph-controls{grid-template-columns:auto minmax(0,1fr);}.custom-graph-controls .graph-content{grid-column:1/-1;width:100%;}.custom-graph-controls .event-options{grid-template-columns:repeat(auto-fit,minmax(190px,1fr));}}
</style></head><body><div id="viewer"><div id="toolbar"><div id="toolbar-left"><button id="expand" type="button">⛶ Expand graphs</button>
<button id="previous-day" type="button" aria-label="Previous loaded day">← Previous</button>
<button id="day-label" type="button" aria-label="Choose loaded day" aria-expanded="false"></button><div id="date-calendar" hidden></div><button id="next-day" type="button" aria-label="Next loaded day">Next →</button>
<div id="metric-select" role="group" aria-label="Profile setting"></div><button id="show-targets" type="button">Temp targets: on</button>
<button id="same-scale" type="button" title="Match numeric limits; this does not convert units.">Same axis scale: off</button>
<div id="overlay-control">Overlay <select id="overlay-select" aria-label="Recorded data overlay on profile"></select></div></div>
<div id="hover-card" class="hover-readout" role="status" aria-live="polite"></div></div>
<details id="daily-summary"><summary id="summary-title">Daily summary</summary><div id="summary-body"></div></details>
<div id="profile" class="graph"></div><p id="profile-target-note" class="target-note" hidden></p><div id="panels" tabindex="0" aria-label="Recorded data graphs; scroll here. Profile remains pinned."></div></div>
<script>""".replace('BACKGROUND',theme['background']).replace('SURFACE',theme['surface']).replace('TEXT',theme['text']).replace('GRID',theme['grid']) + plotly_script()+"""</script><script>
const payload = __VIEWER_PAYLOAD__;
const specs = payload.specs;
function hydrate(value){
  if(Array.isArray(value))return value.map(hydrate);
  if(value && typeof value==='object'){if('$array' in value)return payload.array_pool[value.$array];if('$trace' in value)return payload.trace_pool[value.$trace];if('$period' in value)return payload.period_pool[value.$period];for(const key of Object.keys(value))value[key]=hydrate(value[key]);}return value;
}
if(payload.trace_pool)hydrate(payload.trace_pool);if(payload.period_pool)hydrate(payload.period_pool);
hydrate(payload.specs);if(payload.navigation)hydrate(payload.navigation);
const navigation = payload.navigation;
const dataOnly=!!navigation?.data_only;
if(dataOnly)document.getElementById('profile').style.display='none';
let selectedDays = navigation ? navigation.selected.slice() : [];
let dailyDate=selectedDays.at(-1) || navigation?.days?.at(-1);
const workspaceGraphs=!!navigation?.workspace_graphs;
const previousDay=document.getElementById('previous-day'),nextDay=document.getElementById('next-day');
const dayLabel=document.getElementById('day-label'),dateCalendar=document.getElementById('date-calendar');
const overlayControl=document.getElementById('overlay-control'),overlaySelect=document.getElementById('overlay-select');
let currentOverlay=navigation ? navigation.overlay || 'None' : 'None', dateCycled=false, excludeSMB=false;
const bolusButtons=[],metricButtons=[],targetButtons=[],hourlyButtons=[];
const hourlyModes={bolus:"Average",carbs:"Average",profile_percentage:"Average",site_changes:"Average",sensor_changes:"Average"};
let sameScale=navigation?.same_scale || false;
const scaleButton=document.getElementById("same-scale");
scaleButton.addEventListener("click",toggleScale);
let currentMetric=navigation?.metric || null, showTargets=navigation?.show_targets !== false;
const metricSelect=document.getElementById('metric-select'),targetButton=document.getElementById('show-targets');
targetButtons.push(targetButton);targetButton.addEventListener('click',toggleTargets);
Object.entries(navigation?.profiles || {}).forEach(([key,spec])=>{
  const button=document.createElement('button');button.type='button';button.value=key;button.textContent=spec.layout.title.text.split(' · ')[0];
  button.addEventListener('click',()=>changeMetric(key));metricSelect.appendChild(button);metricButtons.push(button);
});
if(navigation && navigation.overlays) {
  Object.keys(navigation.overlays).forEach(value=>{const option=document.createElement('option');option.value=value;option.textContent=value;overlaySelect.appendChild(option);});
  overlaySelect.addEventListener('change',()=>changeOverlay(overlaySelect.value));
} else overlayControl.hidden=true;
if(dataOnly){overlayControl.hidden=true;scaleButton.hidden=true;targetButton.hidden=true;document.getElementById('metric-select').hidden=true;}
const summary=document.getElementById('daily-summary'),summaryTitle=document.getElementById('summary-title'),summaryBody=document.getElementById('summary-body');
function number(value,digits=1) {return value===null || value===undefined ? '—' : Number(value.toFixed(digits)).toString();}
function updateSummary() {
  if(!navigation) {summary.hidden=true;previousDay.hidden=true;nextDay.hidden=true;return;}
  const days=navigation.summaries.filter(r=>selectedDays.includes(r.date));
  dayLabel.textContent=workspaceGraphs?dailyDate:(selectedDays.length===1 ? selectedDays[0] : selectedDays.length+' days');
  summaryTitle.textContent=days.length===1 ? 'Daily summary · In range '+number(days[0].tir)+'% · CGM coverage '+number(days[0].coverage)+'%' : 'Daily summary · '+days.length+' selected days';
  summaryBody.replaceChildren();
  const table=document.createElement('table');
  const labels=['Date','In 4–10 (%)','Below (%)','Above (%)','Mean','SD','CV (%)','Carbs (g)','Bolus (U)','CGM coverage (%)'];
  labels[1]=navigation.unit==='mmol/L'?'In 4–10 (%)':'In 72–180 (%)';
  const head=document.createElement('tr');labels.forEach(label=>{const cell=document.createElement('th');cell.textContent=label;head.appendChild(cell);});table.appendChild(head);
  days.forEach(r=>{const row=document.createElement('tr');
    [r.date+(r.partial?' · through '+r.through:''),r.tir,r.below,r.above,r.mean,r.sd,r.cv,r.carbs,r.bolus,r.coverage].forEach((value,i)=>{
      const cell=document.createElement('td');cell.textContent=i===0?value:number(value,i===8?2:1);row.appendChild(cell);
    });table.appendChild(row);
  });
  if(navigation.has_nightscout!==false)summaryBody.appendChild(table);
  const note=document.createElement('p');note.textContent='Glucose: '+navigation.unit+'. Five-minute bin medians; SD is population standard deviation; CV = SD / mean. Percentages use observed glucose only. Missing bins are excluded. Coverage uses elapsed time through the load timestamp, including DST. Treatment totals are recorded uploads; unavailable data is —.';
  if(navigation.has_nightscout!==false)summaryBody.appendChild(note);
  else summaryTitle.textContent='Garmin overview · '+(days.length===1?days[0].date:days.length+' selected days');
  const health=(navigation.garmin_daily || []).filter(r=>selectedDays.includes(r.date));
  const activities=(navigation.garmin_activities || []).filter(r=>selectedDays.includes(String(r.start_time).slice(0,10)));
  for(const [title,rows] of [['Garmin daily health',health],['Garmin activities (original database units)',activities]]) {
    if(!rows.length)continue;
    const heading=document.createElement('h4');heading.textContent=title;summaryBody.appendChild(heading);
    const grid=document.createElement('table'),keys=[...new Set(rows.flatMap(r=>Object.keys(r)))];
    const header=document.createElement('tr');keys.forEach(k=>{const th=document.createElement('th');th.textContent=k;header.appendChild(th);});grid.appendChild(header);
    rows.forEach(r=>{const tr=document.createElement('tr');keys.forEach(k=>{const td=document.createElement('td');td.textContent=r[k]===null || r[k]===undefined?'—':typeof r[k]==='number'?number(r[k],2):String(r[k]);tr.appendChild(td);});grid.appendChild(tr);});summaryBody.appendChild(grid);
  }
}
updateSummary();
const graphs = [document.getElementById('profile')];
const targetNotes = [document.getElementById('profile-target-note')];
function updateTargetNote(div,index) {
  const note=targetNotes[index];
  if(panelStateAt(index).deleted){note.hidden=true;return;}
  if(div.layout.meta?.kind==='insight'){
    note.hidden=false;note.replaceChildren();const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Recorded periods · methods and summary';details.appendChild(summary);
    const text=document.createElement('p');text.textContent=div.layout.meta.sleep_overview?div.layout.meta.insight_note:div.layout.meta.insight_relationship?
      'One point per recorded sleep period with both selected metrics; periods are not averaged together. Glucose mean and percentages use observed five-minute bin medians. Range: 4–10 mmol/L (72–180 mg/dL). Absolute-glucose points use red high/low coloring; percentage outcomes use their own scale. Missing readings are excluded, not filled.':
      'One '+(div.layout.meta.insight_aggregation || 'Median').toLowerCase()+' contribution per event/time bin, then the same aggregation across events; bands need at least two periods. The 25–75% band describes variation between periods, not a confidence interval. Absolute glucose uses the fixed 4–10 mmol/L range (72–180 mg/dL); high and low points are red. Δ and variability do not use absolute-glucose thresholds. Glucose gaps >10 min stay blank. Δ uses the recorded t=0 value or adjacent bracketed readings ≤10 min apart. Excluded baselines: '+(div.layout.meta.insight_excluded_baselines || 0)+'. Sensor changes can include restarts. Variability measures the signal, not sensor accuracy.';details.appendChild(text);
    insightSummaryTable(div,details);
    if(!['meal','sleep'].includes(div.layout.meta.insight))for(const s of div.layout.meta.series || []){const row=document.createElement('div');row.textContent=s.label+' · observed duration '+number(s.duration/60,1)+' h'+(div.layout.meta.insight.startsWith('site')?' · CV '+number(s.statistics.cv)+'% · TIR '+number(s.statistics.tir)+'% · above-range AUC '+number(s.statistics.above_exposure)+' '+navigation.unit+'·h':'')+' · baseline: '+s.baseline_note;details.appendChild(row);}
    const compact=document.createElement('p');compact.className='insight-method-note';compact.textContent=div.layout.meta.insight_note || '';note.appendChild(compact);
    note.appendChild(details);return;
  }
  const targets=div.data.some(trace=>trace.meta?.kind==='target'),smb=div.data.some(trace=>trace.meta?.baseline_smb);
  const bands=(div.layout.shapes || []).filter(s=>s.name?.startsWith('Activity | '));
  const garminKey=div.layout.meta?.dataset;
  note.hidden=!targets && !smb && !bands.length && !garminKey?.startsWith('g_');
  note.replaceChildren();
  note.textContent=targets?'Shading reaches the historical profile target active that day. Dotted sides mark interval boundaries; missing history: line only. ':'';
  if(smb){const text=document.createElement('span');text.textContent='SMB · alternate above/below zero to separate nearby doses; capped triangle size shows dose; hover gives the exact amount. ';note.appendChild(text);
    for(const dose of [.05,.2,.5]){const icon=document.createElement('span');icon.textContent='▲';icon.style.fontSize=(32*Math.sqrt(dose))+'px';icon.style.color='#42baf5';note.appendChild(icon);const label=document.createElement('span');label.textContent=' '+dose+' U  ';note.appendChild(label);}}
  const seenBands=new Set();
  for(const band of bands){const name=band.name.split(' | ')[2];if(seenBands.has(name))continue;seenBands.add(name);
    const legend=document.createElement('span');legend.textContent=' ▰ '+name+' ';legend.style.color=band.fillcolor.slice(0,band.fillcolor.lastIndexOf(','))+',1)';note.appendChild(legend);}
  const descriptions={g_stress:' Blue 0–25 · orange 26–75 · red 76–100. Bars or colored line; low-pass always uses a line. Adjustable exponential smoothing; higher minutes means a slower trend. Reset after gaps >5 min.',
    g_steps:' Cumulative: each day is accumulated independently. Median mode shows the median and 25–75% band (at least two days). Histogram switches to hourly increments; Average/Median affects only those bars. Missing pre-recording periods remain unknown.',
    g_steps_cumulative:' Each day is accumulated independently, then aligned by time. Median and 25–75% summarize those curves; the band needs at least two observed days. Held values in data gaps do not prove no steps occurred.',
    g_sleep:' Colors show recorded stages; blank intervals are unknown. Awake is a stage, not a restlessness measurement. Enable optional signals with Sleep overlays. Resting heart rate is a daily reference; Respiration uses monitoring samples within sleep, Sleep respiration prefers the sleep export.',
    g_sleep_rr:' Recorded respiration inside known sleep intervals; no interpolation into missing stages.',
    g_workout_power:' Power from the activity FIT file, or a populated DB power column. Only recorded power is shown.',
    g_workout_hr:' Activity-record heart rate; sampling and sensor source can differ from all-day monitoring.',
    g_workout_speed:' Native activity samples in Metric units. FIT samples take priority; stops have no finite pace. Long days retain temporal extrema.'};
  if(descriptions[garminKey]){const text=document.createElement('span');text.textContent=descriptions[garminKey];note.appendChild(text);}
  if(garminKey==='g_sleep'){
    const legend=document.createElement('div');
    for(const [label,color] of [['Deep','#673ab7'],['Light','#9575cd'],['REM','#ce93d8'],['Awake','#ffb74d'],['Unknown','#90a4ae']]){
      const item=document.createElement('span');item.textContent=' ▰ '+label+' ';item.style.color=color;legend.appendChild(item);
    }note.appendChild(legend);
    for(const row of navigation?.garmin_sleep_notes || []){
      // A night can cross midnight. Include it on every overlapping displayed date.
      if(!(row.days || [row.date]).some(day=>selectedDays.includes(day)))continue;
      const info=document.createElement('div');const values=[row.date];
      if(row.breathing!=null)values.push('Breathing variations: '+String(row.breathing).toLowerCase().replaceAll('_',' ')+' (nightly category)');
      if(row.awake_count!=null)values.push('Awakenings: '+row.awake_count);
      if(row.restless_count!=null)values.push('Restless moments: '+row.restless_count);
      if(row.restlessness!=null)values.push('Restlessness: '+String(row.restlessness).toLowerCase());
      info.textContent=values.join(' · ');note.appendChild(info);
    }
  }




}
__CUSTOM_GRAPH__
__GARMIN_VIEW__
__FILLED_REGIONS__
__PANEL_VIEW__
__INSIGHTS_VIEW__
__WORKSPACE_VIEW__

const panels = document.getElementById('panels');
const panelCards={},panelOrder=[],moveButtons=[];
const card = document.getElementById('hover-card');
const floatingCard=document.createElement('div');floatingCard.id='hover-floating';floatingCard.className='hover-readout';floatingCard.hidden=true;
floatingCard.setAttribute('aria-hidden','true');document.getElementById('viewer').appendChild(floatingCard);
let hoverActive=false,readoutFrame=false;
let hoverAnchor=null;
function positionHoverReadout() {
  if(!hoverActive || !hoverAnchor){floatingCard.hidden=true;return;}
  const {div,x,y}=hoverAnchor;
  if(floatingCard.parentElement!==div)div.appendChild(floatingCard);
  floatingCard.hidden=false;
  const width=floatingCard.offsetWidth || 180,height=floatingCard.offsetHeight || 32;
  const maxWidth=div.clientWidth || 900,maxHeight=div.clientHeight || 300;
  Object.assign(floatingCard.style,{left:Math.max(4,Math.min(maxWidth-width-4,x+12))+'px',top:Math.max(4,Math.min(maxHeight-height-4,y-height-10))+'px',right:'auto',maxWidth:'260px'});
}
function scheduleHoverReadout() {
  if(readoutFrame || !hoverActive)return;readoutFrame=true;
  requestAnimationFrame(()=>{readoutFrame=false;positionHoverReadout();});
}
function renderHoverReadout(parts,color) {
  for(const box of [floatingCard]){
    box.replaceChildren();
    parts.filter(text=>text!==null && text!==undefined).forEach((text,i)=>{
      const el=document.createElement(i===1?'strong':'span');el.textContent=text;
      el.className=i===0?'hover-name':i>1?'muted':'';
      if(i===0 && color)el.style.borderLeftColor=color;
      box.appendChild(el);
    });
  }
  hoverActive=true;positionHoverReadout();
}

const expand = document.getElementById('expand');
function createPanel(i) {
  if(specs[i].layout.meta?.kind==='custom' && !specs[i].layout.meta.custom_id){const state=newCustomState();specs[i].layout.meta.custom_id=state.id;if(navigation?.figures?.[i])navigation.figures[i].layout.meta.custom_id=state.id;}
  const instance=ensurePanelState(specs[i]);
  const panel=document.createElement('section');panel.className='graph-panel';panel.graphIndex=i;panelCards[i]=panel;panelOrder.push(i);panels.appendChild(panel);
  const orderBar=document.createElement('div');orderBar.className='bolus-controls';panel.appendChild(orderBar);const areas=controlAreas(orderBar);
  const move=document.createElement('div');move.className='axis-move';areas.axis.appendChild(move);
  for(const [direction,label] of [[-1,'↑'],[1,'↓']]) {
    const button=document.createElement('button');button.type='button';button.textContent=label;
    button.title='Move '+specs[i].layout.title.text.split(' · ')[0]+(direction<0?' up':' down');
    button.setAttribute('aria-label',button.title);button.addEventListener('click',()=>movePanel(panel.graphIndex,direction));
    moveButtons.push({button,panel,direction});move.appendChild(button);
  }
  panelModeControls(areas.settings,panel,specs[i],areas.actions);
  workspacePanelControls(areas,panel,specs[i]);
  garminControls(orderBar,specs[i]);
  insightControls(areas.settings,panel,specs[i],areas.content);profileCopyControls(areas,panel,specs[i]);
  if(specs[i].layout.meta?.kind==='custom')setupCustomControls(orderBar,specs[i].layout.meta.custom_id);
  if(specs[i].layout.title.text.startsWith('Glucose ·') || specs[i].layout.meta?.kind==='compact') {
    const button=document.createElement('button');button.type='button';
    button.addEventListener('click',()=>changePanelState(panel.graphIndex,s=>{s.showTargets=!s.showTargets;}));button.panel=panel;targetButtons.push(button);areas.content.appendChild(button);
  }
  if(specs[i].layout.meta?.kind==='hourly' || summaryEventKey(specs[i])) {
    const bar=areas.content;
    hourlyGridControls(bar,panel,specs[i]);
    const average=document.createElement('button');average.type='button';average.value=specs[i].layout.meta.dataset;
    average.title='Switch the hourly bars between median and arithmetic mean of complete daily hour totals. Zero-event hours count; missing and partial hours do not.';
    average.addEventListener('click',()=>toggleHourly(panel.graphIndex));areas.settings.appendChild(average);average.panel=panel;hourlyButtons.push(average);
    if((specs[i].layout.meta.dataset==='bolus' || summaryEventKey(specs[i])==='bolus') && navigation?.bolus_without_smb?.selected) {
      const button=document.createElement('button');button.type='button';button.textContent='Exclude SMB';button.addEventListener('click',()=>toggleSMB(panel.graphIndex));bar.appendChild(button);button.panel=panel;bolusButtons.push(button);
      const note=document.createElement('span');note.textContent='Unknown boluses remain included';bar.appendChild(note);
    }

  }
  const body=document.createElement('div');body.className='graph-body';body.appendChild(areas.axis);panel.appendChild(body);
  const div=document.createElement('div');div.className='graph';body.appendChild(div);graphs.push(div);
  const note=document.createElement('p');note.className='target-note';note.hidden=true;panel.appendChild(note);targetNotes.push(note);
}
const customTemplate=specs.find(s=>s.layout.meta?.kind==='custom');
const customDailyTemplate=customTemplate?navigation.figures[specs.indexOf(customTemplate)]:null;
for(let i=1;i<specs.length;i++)createPanel(i);
let syncing=false;
const guides=[], highlights=[];
let ready=false;
previousDay.disabled=true;nextDay.disabled=true;
let pendingHover=null,hoverFrame=false,lastHoverKey=null;
function clearHover() {
  pendingHover=null;lastHoverKey=null;hoverActive=false;floatingCard.hidden=true;
  guides.forEach(g=>g.style.display='none');highlights.forEach(g=>g.style.display='none');
  card.textContent='';
}
function queueHover(div,event) {
  pendingHover=event?{div,event}:null;
  if(hoverFrame)return;
  hoverFrame=true;
  requestAnimationFrame(()=>{hoverFrame=false;const latest=pendingHover;pendingHover=null;if(latest)showHover(latest.div,latest.event);else clearHover();});
}
function hoverGeometry(div) {
  div.hoverGlyphs=new Map();
  const axes=Object.entries(div._fullLayout || {}).filter(([name,a])=>/^yaxis[0-9]*$/.test(name) && Number.isFinite(a._offset)).map(([,a])=>a);
  div.hoverBounds={top:Math.min(...axes.map(a=>a._offset)),bottom:Math.max(...axes.map(a=>a._offset+a._length))};
}
function highlightPoint(div,point) {
  const index=graphs.indexOf(div),marker=highlights[index],trace=point.data || {},full=point.fullData || trace;
  const xa=point.xaxis || div._fullLayout['xaxis'+(trace.xaxis || 'x').slice(1)],ya=point.yaxis || div._fullLayout['yaxis'+(trace.yaxis || 'y').slice(1)];
  if(!marker || !xa || !ya)return;
  const pixel=(axis,v)=>axis._offset+(axis.d2p?axis.d2p(v):axis.l2p(v));
  const at=(v)=>Array.isArray(v)?v[point.pointNumber]:v;
  let x=pixel(xa,point.x),y=pixel(ya,point.y),width=9,height=9,radius='50%';
  const size=Number(at(full.marker?.size));if(Number.isFinite(size))width=height=Math.max(9,Math.min(90,size+4));
  const symbol=String(at(full.marker?.symbol) || '');
  if(symbol.includes('square') || symbol.includes('diamond'))radius='3px';
  if(trace.type==='bar'){
    const bin=Number(at(full.width) ?? at(trace.width));
    if(Number.isFinite(bin))width=Math.max(6,Math.abs(pixel(xa,point.x+bin/2)-pixel(xa,point.x-bin/2)));
    const base=Number(at(full.base) || 0),clip=v=>Math.max(ya._offset,Math.min(ya._offset+ya._length,v)),edge=clip(pixel(ya,base));
    y=clip(y);
    height=Math.max(6,Math.abs(y-edge));y=(y+edge)/2;radius='2px';
  } else if(trace.type==='heatmap'){
    const col=trace.x?.indexOf(point.x),xs=trace.x || [];
    const bin=xs.length>1?Math.abs(xs[Math.min(xs.length-1,col+1)]-xs[Math.max(0,col-1)])/(col>0 && col<xs.length-1?2:1):60;
    width=Math.max(6,Math.abs(pixel(xa,Number(point.x)+bin/2)-pixel(xa,Number(point.x)-bin/2)));
    height=Math.max(6,ya._length/Math.max(1,trace.y?.length || 1));radius='2px';
  } else if(trace.meta?.kind==='garmin_sleep') {height=Math.min(130,Number(full.line?.width) || 20);width=14;radius='3px';}
  if(div.querySelectorAll && full.uid && Number.isInteger(point.pointNumber)){
    div.hoverGlyphs ||= new Map();
    if(!div.hoverGlyphs.has(full.uid)){
      const group=Array.from(div.querySelectorAll('.scatterlayer .trace')).find(node=>node.classList.contains('trace'+full.uid));
      div.hoverGlyphs.set(full.uid,new Map(group?Array.from(group.querySelectorAll('.points path.point')).map(node=>[node.__data__?.i,node]):[]));
    }
    const glyph=div.hoverGlyphs.get(full.uid).get(point.pointNumber);
    if(glyph){
      const b=glyph.getBoundingClientRect(),g=div.getBoundingClientRect();
      if(b.width>0 || b.height>0){
        const stroke=Number(at(full.marker?.line?.width)) || 0;
        x=(b.left+b.right)/2-g.left;y=(b.top+b.bottom)/2-g.top;
        width=Math.max(8,b.width+stroke+4);height=Math.max(8,b.height+stroke+4);
        // A box clearly isolates the shifted triangle, bolus rectangle or carb diamond.
        radius=['bolus','carbs'].includes(trace.meta?.kind) || full.marker?.standoff?'3px':radius;
      }
    }
  }
  if(!Number.isFinite(x)||!Number.isFinite(y))return;
  hoverAnchor={div,x,y};
  Object.assign(marker.style,{display:'block',left:x+'px',top:y+'px',width:width+'px',height:height+'px',borderRadius:radius});
}
function showHover(div,event) {
  const point=event.points && event.points[0];
  if(!point)return;
  const key=graphs.indexOf(div)+':'+point.curveNumber+':'+JSON.stringify(point.pointNumber)+':'+point.x+':'+point.y;
  if(key===lastHoverKey)return;
  lastHoverKey=key;
  highlights.forEach(h=>h.style.display='none');

  if(point && point.data?.meta?.kind==='hourly_heatmap') {
    const d=point.customdata;
    if(!d || d[2]===null)return;
    clearHover();highlightPoint(div,point);renderHoverReadout([point.data.meta.label,number(d[2],3)+' '+point.data.meta.unit,d[0]+' '+d[1],Number.isFinite(d[3])?d[3]+' events':'',d[4]]);lastHoverKey=key;
    return;
  }
  if(point?.data?.meta?.kind==='stress_histogram'){clearHover();highlightPoint(div,point);renderHoverReadout(['Stress '+(point.x-5)+'–'+(point.x+5),point.y+' observed bins']);lastHoverKey=key;return;}
  if(!point || !Number.isFinite(point.x) || !Number.isFinite(point.y))return;
  const trace=point.data, meta=trace.meta || {};
  const minute=Math.round(point.x), clock=String(Math.floor(minute/60)).padStart(2,'0')+':'+String(minute%60).padStart(2,'0');
  const value=Number(point.y.toFixed(3)).toString();
  const label=meta.label || trace.name || 'Value';
  card.replaceChildren();
  const parts=[label,value+(meta.unit?' '+meta.unit:''),(meta.date?meta.date+' · ':'')+clock];
  if(meta.kind==='automation_note'){parts[1]='';parts[2]=meta.date+' · '+clock;}
  if(meta.kind==='profile_event'){parts[1]=Number.isFinite(meta.percentage)?meta.percentage+'%':'';parts[2]=meta.date+' · '+clock;}
  if(div.layout.meta?.non_time){parts[2]=number(point.x,2)+' hours since event';if(point.customdata)parts.push(point.customdata+' contributing periods');}
  if(meta.kind==='sleep_overview_glucose')parts.splice(0,parts.length,'Glucose',value+' '+meta.unit,point.customdata);
  if(meta.kind==='sleep_overview_signal')parts.splice(0,parts.length,label,value+' '+meta.unit,point.customdata);
  if(meta.kind==='sleep_overview_stage')parts.splice(0,parts.length,...(point.customdata || [meta.label]));
  if(meta.kind==='insight_relationship')parts.splice(0,parts.length,point.customdata[0],value+' '+meta.unit,meta.x_label+': '+number(point.x,2)+' '+meta.x_unit,
    'Glucose coverage '+number(point.customdata[1],1)+'% · '+point.customdata[3]+' observed bins','Recorded stages '+number(point.customdata[2],1)+'%');
  if((meta.baseline_smb || meta.compact_smb) && Array.isArray(point.customdata))parts[1]=number(point.customdata[1],3)+' U';
  if(meta.kind==='garmin_sleep' || meta.kind==='garmin_interval') {parts[1]='';if(point.customdata)parts.push(String(point.customdata));}
  if(meta.kind==='target' && point.customdata)parts.push(String(point.customdata));
  if(['median','hourly_histogram','garmin_aggregate','sleep_distribution'].includes(meta.kind) && point.customdata)parts.push(point.customdata+' contributing days');
  const rawColor=trace.marker?.color || trace.line?.color;
  const color=Array.isArray(rawColor)?rawColor[point.pointNumber]:rawColor;
  highlightPoint(div,point);renderHoverReadout(parts,typeof color==='string'?color:null);
  // Plotly 6.9 supplies axis transforms with its hover event. Reusing them also
  // places highlights correctly on the secondary axis and after zoom/pan.
  graphs.forEach((g,i)=>{
    if(!g._fullLayout || !guides[i])return;
    if(div.layout.meta?.non_time || g.layout.meta?.non_time){guides[i].style.display='none';highlights[i].style.display='none';return;}
    const axis=g._fullLayout.xaxis;
    const px=axis._offset+axis.l2p(point.x);
    const inside=px>=axis._offset && px<=axis._offset+axis._length;
    if(!g.hoverBounds)hoverGeometry(g);
    const {top,bottom}=g.hoverBounds;
    Object.assign(guides[i].style,{display:inside?'block':'none',left:px+'px',top:top+'px',height:(bottom-top)+'px'});
    highlights[i].style.display='none';
  });
  highlightPoint(div,point);
}
// Keep amount labels readable without hiding their markers or hover values.
// Re-evaluate from scratch after zoom, resize and changing day/dataset.
function tidyLabels(div) {
  if(!div.querySelectorAll)return;
  const accepted=[];
  div.querySelectorAll('.scatterlayer .textpoint text').forEach(node=>{
    node.style.visibility='visible';
    const box=node.getBoundingClientRect();
    if(!box.width || !box.height)return;
    if(accepted.some(other=>box.left<other.right+4 && box.right>other.left-4 && box.top<other.bottom+2 && box.bottom>other.top-2))node.style.visibility='hidden';
    else accepted.push(box);
  });
}
// Plotly cannot measure hidden tabs correctly. Wait for width and fonts, then
// serialize initialization, redraws and resizes so stale layouts cannot race.
const viewer=document.getElementById('viewer');
let jobs=Promise.resolve(), starting=false, resizePending=false, lastSize='';
let intersects=!!navigation?.report_render || typeof IntersectionObserver==='undefined';
function enqueue(task) {const next=jobs.then(async()=>{startGraphWork();try{await new Promise(resolve=>setTimeout(resolve,0));return await task();}finally{finishGraphWork();}});jobs=next.catch(()=>{});return next;}
function visibleWidth() {return intersects ? Math.floor(viewer.getBoundingClientRect().width) : 0;}
function axisPolicy(view,index) {
  const {data,layout}=view;
  const valuesFor=axis=>data.filter(t=>(t.yaxis || 'y')===axis && t.visible!==false).flatMap(t=>t.y || []).filter(Number.isFinite);
  if((index===0 || layout.meta?.profile_copy) && !dataOnly) {
    const originalGlucoseRange=currentOverlay==='Glucose'?layout.yaxis2?.range:null;
    for(const axis of [layout.yaxis,layout.yaxis2].filter(Boolean)) {
      delete axis.range;delete axis.matches;delete axis.autorangeoptions;axis.autorange=true;
    }
    if(layout.yaxis2 && currentOverlay==='Glucose') {
      const scale=navigation.unit==='mmol/L'?1:18;
      const glucose=data.filter(t=>t.meta?.kind==='glucose' || t.meta?.dataset==='glucose').flatMap(t=>t.y || []).filter(Number.isFinite);
      const peak=Math.max(0,...glucose),maximum=peak>20*scale?Math.ceil(peak*1.05/scale)*scale:20*scale;
      layout.yaxis2.range=[0,Math.max(maximum,originalGlucoseRange?.[1] || 0)];layout.yaxis2.autorange=false;
    }
    if(layout.yaxis2 && currentOverlay==='Temporary Targets') {
      layout.yaxis2.range=[0,navigation.unit==='mmol/L'?20:360];layout.yaxis2.autorange=false;
    }
  }
  if((index===0 || layout.meta?.profile_copy) && sameScale && layout.yaxis2 && !data.some(t=>['garmin_sleep','garmin_interval'].includes(t.meta?.kind))) {
    const values=[0,...valuesFor('y'),...valuesFor('y2'),...(layout.yaxis2.range || [])];
    const low=Math.min(...values),high=Math.max(...values),span=Math.max(1,high-low);
    const limits=[low<0?low-.05*span:0,high+(data.some(t=>t.mode?.includes('text')) ? .20 : .08)*span];
    layout.yaxis.range=limits;layout.yaxis2.range=limits;layout.yaxis.autorange=false;layout.yaxis2.autorange=false;
  }
  // Any matched limits already have label headroom. Independent axes need it too.
  for(const name of new Set(data.filter(t=>t.mode?.includes('text')).map(t=>t.yaxis || 'y'))) {
    const axis=layout['yaxis'+name.slice(1)],values=valuesFor(name);
    if(axis.autorange!==false && values.length)axis.autorangeoptions={include:Math.max(...values)+.2*Math.max(1,Math.max(...values)-Math.min(0,...values))};
  }
  smbAxes(view);
  garminAxes(view);
}
function smbAxes(view) {
  for(const t of view.data.filter(t=>t.meta?.baseline_smb)) {
    const name=t.yaxis || 'y',axis=view.layout['yaxis'+name.slice(1)];
    if(!axis || axis.autorange===false)continue;
    const values=view.data.filter(v=>(v.yaxis || 'y')===name).flatMap(v=>v.y || []).filter(Number.isFinite);
    const peak=Math.max(1,...values),low=Math.min(0,...values);
    axis.autorangeoptions={...axis.autorangeoptions,minallowed:Math.min(low,-.18*peak)};
  }
}
function garminAxes(view) {
  if(view.layout.meta?.dataset==='g_hr' && !view.data.length)Object.assign(view.layout.yaxis,{range:[35,100],autorange:false});
  for(const t of view.data) {
    const axis=view.layout['yaxis'+(t.yaxis || 'y').slice(1)];
    if(!axis)continue;
    if(t.meta?.kind==='garmin_sleep'){
      const dates=[...new Set(view.data.filter(v=>v.meta?.kind==='garmin_sleep').map(v=>v.meta.date))].sort();
      const lane=dates.indexOf(t.meta.date);t.y=t.y.map(v=>v===null?null:lane);
      Object.assign(axis,{tickvals:dates.map((_,i)=>i),ticktext:dates.length>1?dates:['Sleep'],range:[dates.length-.5,-.5],autorange:false});

    }
    if(t.meta?.dataset==='g_hr' && !(view.layout.meta?.kind==='custom' && customState(view.layout.meta.custom_id).sameScale) && !(sameScale && view.layout.yaxis2 && currentOverlay==='Garmin · Heart rate')){
      const values=view.data.filter(v=>(v.yaxis || 'y')===(t.yaxis || 'y')).flatMap(v=>v.y || []).filter(Number.isFinite);
      Object.assign(axis,{range:[Math.min(35,...values),Math.max(100,...values)*1.08],autorange:false});
    }
    if(t.meta?.dataset==='g_stress' && !(view.layout.meta?.kind==='custom' && customState(view.layout.meta.custom_id).sameScale) && !(sameScale && view.layout.yaxis2 && currentOverlay==='Garmin · Stress'))Object.assign(axis,{range:[0,100],autorange:false});
    if(t.meta?.kind==='garmin_interval')Object.assign(axis,{tickvals:[1],ticktext:['Exercise'],range:[0,2],autorange:false});
    if(t.meta?.dataset==='g_sleep' && t.meta?.kind==='median')Object.assign(axis,{range:[0,100],autorange:false});
  }
  if(view.layout.meta?.display_mode==='Median + band' && !dateCycled){
    const options=displayOptions(view.layout),refs=new Set(view.data.filter(t=>t.meta?.sleep_variant).map(t=>t.yaxis || 'y'));
    if(view.layout.meta?.dataset==='g_sleep')refs.add('y');
    if(!view.layout.meta?.dataset && view.layout.meta?.kind!=='custom' && currentOverlay==='Garmin · Sleep' && view.layout.yaxis2)refs.add('y2');
    for(const ref of refs){const axis=view.layout['yaxis'+ref.slice(1)];
      if(axis)Object.assign(axis,{range:[0,options.sleepDistribution?1:100],autorange:false});}
  }
}
function reorderScope(index) {
  const active=panelOrder.filter(i=>!panelStateAt(i).deleted);
  if(!navigation?.export_workspace || typeof reportBlockOf!=='function')return active;
  return active.filter(i=>reportBlockOf(panelStateAt(i))===reportEditorBlock);
}
function movePanel(index,direction) {
  if(!ready || syncing)return;
  const scope=reorderScope(index),from=scope.indexOf(index),to=from+direction;
  if(from<0 || to<0 || to>=scope.length)return;
  const other=scope[to],left=panelOrder.indexOf(index),right=panelOrder.indexOf(other);
  if(left<0 || right<0)return;
  [panelOrder[left],panelOrder[right]]=[panelOrder[right],panelOrder[left]];
  panelOrder.forEach(key=>panels.appendChild(panelCards[key]));clearHover();controls();
}
async function toggleScale() {
  if(!ready || syncing || currentOverlay==='None')return;
  return enqueue(async()=>{
    const previous=sameScale;syncing=true;controls();clearHover();
    try {sameScale=!sameScale;await redrawLocal();}
    catch(error){sameScale=previous;card.textContent='Could not change axis scale.';}
    finally {syncing=false;controls();}
  });
}
function decorate(source,index) {
  if(workspaceGraphs && selectedDays.length<2 && panelStateAt(index).graphType!=='daily'){
    const view={data:[],layout:JSON.parse(JSON.stringify(source.layout))};view.layout.meta={...view.layout.meta,empty:true};view.layout.shapes=[];
    view.layout.annotations=[{text:'Select at least two dates for this graph',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false}];nameWorkspaceGraph(view,index);return view;
  }
  return panelDateContext(index,()=>decorateInstance(source,index));
}
function decorateInstance(source,index) {
  const state=panelStateAt(index);if(!state.profileCopy)return decorateCore(source,index);
  const original=[currentOverlay,currentMetric,sameScale];
  try{currentOverlay=state.overlay;currentMetric=state.metric;sameScale=state.sameScale;return decorateCore(source,index);}
  finally{[currentOverlay,currentMetric,sameScale]=original;}
}
function decorateCore(source,index) {
  const isProfile=index===0 || panelStateAt(index).profileCopy;
  const view=JSON.parse(JSON.stringify(source)),profile=navigation?.profiles?.[currentMetric];
  view.layout.meta={...view.layout.meta,profile_copy:panelStateAt(index).profileCopy,profile_same_scale:panelStateAt(index).profileCopy?sameScale:undefined,custom_id:specs[index].layout.meta?.custom_id,panel_id:specs[index].layout.meta?.panel_id,display_mode:effectivePanelMode(index)};
  if(view.layout.meta.kind==='insight'){transformInsight(view,index);applySummaryBands(view,index);nameWorkspaceGraph(view,index);applyOverlayDayColors(view,index);return view;}
  if(view.layout.meta.kind==='compact'){composeCompact(view,index);applyActivityShading(view);applyChangeEvents(view,index);applyProfileEvents(view);applyAutomationNotes(view,index);compactLayout(view.layout);compactAmountLabels(view);colorGlucoseLines(view);nameWorkspaceGraph(view,index);return view;}
  if(view.layout.meta?.kind==='custom')composeCustom(view);
  if(profile) {
    const guides=(profile.layout.shapes || []).filter(s=>s.name==='Profile change');
    view.layout.shapes=(view.layout.shapes || []).filter(s=>s.name!=='Profile change').concat(guides);
    view.layout.meta={...view.layout.meta,profile_changes:profile.layout.meta?.profile_changes || []};
    if(isProfile) {
      view.data=profile.data.map(t=>({...t,yaxis:'y',xaxis:'x'})).concat(view.data.filter(t=>t.meta?.kind!=='profile'));
      view.layout.title.text=profile.layout.title.text.split(' · ')[0]+' · '+view.layout.title.text.split(' · ').slice(1).join(' · ');
      view.layout.yaxis.title=profile.layout.yaxis.title;
      view.layout.yaxis.rangemode=profile.layout.yaxis.rangemode;
      delete view.layout.yaxis.range;view.layout.yaxis.autorange=true;
      view.layout.uirevision=currentMetric+':'+currentOverlay;
    }
  }
  const glucose=isProfile?currentOverlay==='Glucose':view.layout.title.text.startsWith('Glucose ·');
  if(glucose && !(index===0?showTargets:panelStateAt(index).showTargets))view.data=view.data.filter(t=>!['target','target_fill','target_boundary'].includes(t.meta?.kind));
  if(view.layout.meta?.kind==='hourly' && !view.layout.meta.single_day) {
    const mode=panelStateAt(index).hourly || 'Average';
    const heat=view.data.find(t=>t.meta?.kind==='hourly_heatmap'),bars=view.data.find(t=>t.meta?.kind==='hourly_histogram');
    bars.y=Array.from({length:24},(_,hour)=>{
      const values=heat.z.map((row,i)=>heat.customdata[i][hour]?.[5]?row[hour]:null).filter(Number.isFinite);
      if(!values.length)return null;
      if(mode==='Average')return values.reduce((sum,value)=>sum+value,0)/values.length;
      values.sort((a,b)=>a-b);const mid=Math.floor(values.length/2);
      return values.length%2?values[mid]:(values[mid-1]+values[mid])/2;
    });
    bars.name=mode+' hourly '+heat.meta.label.toLowerCase();bars.meta.label=bars.name;
    view.layout.yaxis2.title.text=mode+' '+heat.meta.unit;
    view.layout.meta.statistic=mode;
  }
  applyHourlyGrid(view,index);
  composeSleep(view);
  if(view.layout.meta?.kind!=='custom')transformGarmin(view,index);
  applyActivityShading(view);
  applyChangeEvents(view,index);
  axisPolicy(view,index);
  workoutAxes(view);
  applySummaryBands(view,index);compactDistribution(view,index);
  closeFilledRegions(view);
  colorGlucoseLines(view);nameWorkspaceGraph(view,index);compactLegend(view.data);composeSummaryGroup(view,index);applyPanelRanges(view,index);applyProfileEvents(view);applyAutomationNotes(view,index);
  applyClockTicks(view.layout,panelTimeRange(index,view.layout.xaxis?.range || [0,1440]));applyOverlayDayColors(view,index);
  return view;
}
function localSource(index) {
  const instance=panelStateAt(index);
  if(workspaceGraphs){const summary=summarySource(index);if(summary)return summary;}
  if(workspaceGraphs && instance.graphType==='daily'){
    if(index===0 || instance.profileCopy)return navigation.overlays?.[instance.overlay || currentOverlay]?.daily || specs[index];
    return navigation.figures.find(f=>sourceIdentity(f)===instance.base) || specs[index];
  }
  if(instance.profileCopy && navigation?.overlays?.[instance.overlay]){const bank=navigation.overlays[instance.overlay];return dateCycled?bank.daily:(bank.modes?.[effectivePanelMode(index)] || bank.selected);}
  if(index===0 && navigation?.overlays)return dateCycled?navigation.overlays[currentOverlay].daily:(navigation.overlays[currentOverlay].modes?.[effectivePanelMode(0)] || navigation.overlays[currentOverlay].selected);
  const state=panelStateAt(index),identity=state.base,mode=effectivePanelMode(index);
  if(state.excludeSMB && specs[index].layout.meta?.kind==='hourly' && specs[index].layout.meta.dataset==='bolus' && navigation?.bolus_without_smb)return navigation.bolus_without_smb[dateCycled?'daily':'selected'];
  if((workspaceGraphs || !dateCycled) && navigation?.mode_banks?.[mode]?.[identity])return navigation.mode_banks[mode][identity];
  return dateCycled?(navigation.figures.find(f=>sourceIdentity(f)===identity) || specs[index]):specs[index];
}

async function redrawLocal(include=null) {
  const range=graphs[0]._fullLayout.xaxis.range.slice();
  const indices=graphs.map((_,i)=>i).filter(i=>!panelStateAt(i).deleted && (!include || include(specs[i],i)));
  for(let n=0;n<indices.length;n++){
    const i=indices[n],div=graphs[i];await graphWorkStep('Rendering graphs',n,indices.length);
    const view=decorate(panelSourceView(localSource(i),i,range),i);view.layout=sizedLayout(view,i);
    if(!view.layout.meta?.non_time){const local=panelTimeRange(i,range);view.layout.xaxis.range=local;view.layout.xaxis.autorange=false;applyClockTicks(view.layout,local);workoutAxes(view,local);}
    await Plotly.react(div,view.data,view.layout);await reflowProfileLabels(div);
  }
  await graphWorkStep('Rendering graphs',indices.length,indices.length);
}
async function toggleTargets() {
  if(!ready || syncing)return;
  return enqueue(async()=>{
    syncing=true;controls();clearHover();
    const previous=showTargets;
    try {showTargets=!showTargets;await redrawLocal();}
    catch(error){showTargets=previous;card.textContent='Could not update graph option.';}
    finally{syncing=false;controls();}
  });
}
async function toggleHourly(index) {return changePanelState(index,s=>{s.hourly=s.hourly==='Median'?'Average':'Median';});}

async function changeMetric(metric) {
  if(!ready || syncing)return;
  return enqueue(async()=>{
    const previous=currentMetric;syncing=true;controls();clearHover();
    try {currentMetric=metric;await redrawLocal();}
    catch(error){currentMetric=previous;card.textContent='Could not change profile setting.';}
    finally{syncing=false;controls();}
  });
}
function sizedLayout(spec, index) {
  const layout=JSON.parse(JSON.stringify(spec.layout));
  layout.width=Math.max(1, (panels.clientWidth || visibleWidth())-(index>0?66:0));
  if(index===0 && !dataOnly)layout.height=250;
  profileEventLayout(layout);
  layout.autosize=false;
  return layout;
}
function controls() {
  customControls();panelControls();workspaceControls();workspaceSize();
  for(const panel of Object.values(panelCards))panel.hidden=panelStateAt(panel.graphIndex).deleted || (navigation?.export_workspace && reportBlockOf(panelStateAt(panel.graphIndex))!==reportEditorBlock) || (!workspaceGraphs && selectedDays.length<2 && (specs[panel.graphIndex].layout.meta?.kind==='insight' || ['profile_percentage','sensor_changes','site_changes'].includes(specs[panel.graphIndex].layout.meta?.dataset)));
  graphs[0].hidden=dataOnly || panelStateAt(0).deleted;
  if(panelStateAt(0).deleted)targetNotes[0].hidden=true;
  const profileGroup=document.getElementById('profile-settings-group');if(profileGroup)profileGroup.hidden=dataOnly || panelStateAt(0).deleted;
  eventControlState();
  if(reportControlsRefresh)reportControlsRefresh();
  for(const panel of Object.values(panelCards)){const bar=panel.children[0],a=bar.graphAreas;if(a){a.content.hidden=a.content.children.length<=1;a.settings.parentElement.hidden=a.settings.children.length===0;}}
  garminControlState();activityControlState();
  if(ready && !syncing){persistViewer();notifyHiddenGraphs();}
  previousDay.disabled=!ready || syncing || !navigation || navigation.days.length<2;
  nextDay.disabled=previousDay.disabled;dayLabel.disabled=!ready || syncing || !navigation;
  overlaySelect.disabled=!ready || syncing;overlaySelect.value=currentOverlay;
  hourlyButtons.forEach(button=>{if(panelCards[button.panel.graphIndex]!==button.panel)return;button.hidden=Boolean(summaryEventKey(specs[button.panel.graphIndex]) && (panelStateAt(button.panel.graphIndex).graphType==='daily' || panelStateAt(button.panel.graphIndex).summaryView==='Timeline'));button.disabled=!ready || syncing || dateCycled;button.textContent=dateCycled?'Hourly bars: selected day':'Hourly bars: '+panelStateAt(button.panel.graphIndex).hourly;button.setAttribute('aria-pressed',String(!dateCycled && panelStateAt(button.panel.graphIndex).hourly==='Average'));});
  scaleButton.disabled=!ready || syncing || (currentOverlay==='None' || currentOverlay==='Garmin · Sleep' || currentOverlay==='Garmin · Activities');scaleButton.textContent='Same axis scale: '+(sameScale?'on':'off');scaleButton.setAttribute('aria-pressed',String(sameScale));
  moveButtons.forEach(({button,panel,direction})=>{const scope=reorderScope(panel.graphIndex),position=scope.indexOf(panel.graphIndex)+direction;button.disabled=!ready || syncing || position<0 || position>=scope.length;});
  targetButton.hidden=dataOnly || currentOverlay!=='Glucose';
  if(topControlAreas){topControlAreas.content.hidden=panelStateAt(0).deleted || (overlayControl.hidden && targetButton.hidden);topControlAreas.settings.parentElement.hidden=Array.from(topControlAreas.settings.children).every(el=>el.hidden);}
  metricButtons.forEach(button=>{button.disabled=!ready || syncing;button.setAttribute('aria-pressed',String(button.value===currentMetric));});
  targetButtons.forEach(button=>{if(button.panel && panelCards[button.panel.graphIndex]!==button.panel)return;button.disabled=!ready || syncing;button.setAttribute('aria-pressed',String(button.panel?panelStateAt(button.panel.graphIndex).showTargets:showTargets));button.textContent='Temp targets: '+((button.panel?panelStateAt(button.panel.graphIndex).showTargets:showTargets)?'on':'off');});
  bolusButtons.forEach(button=>{if(panelCards[button.panel.graphIndex]!==button.panel)return;button.hidden=Boolean(summaryEventKey(specs[button.panel.graphIndex]) && (panelStateAt(button.panel.graphIndex).graphType==='daily' || panelStateAt(button.panel.graphIndex).summaryView==='Timeline'));if(button.nextSibling?.tagName==='SPAN')button.nextSibling.hidden=button.hidden;button.disabled=!ready || syncing;button.setAttribute('aria-pressed',String(panelStateAt(button.panel.graphIndex).excludeSMB));button.textContent=panelStateAt(button.panel.graphIndex).excludeSMB?'Exclude SMB: on':'Exclude SMB: off';});
}
function compactLegend(data) {
  const seen=new Set();
  data.forEach(trace=>{
    const eligible=trace.meta?.legend_entry ?? (trace.showlegend!==false);
    const group=trace.legendgroup || trace.name;
    trace.showlegend=eligible && !seen.has(group);
    if(eligible)seen.add(group);
  });
}
function resizeVisible() {
  if(!ready || visibleWidth()<50)return;
  const width=Math.floor(panels.clientWidth || visibleWidth());
  const size=width+':'+viewer.clientHeight;
  if(size===lastSize)return;
  lastSize=size;
  clearHover();
  return Promise.all(graphs.map((div,i)=>div._fullLayout?Plotly.relayout(div,{width:Math.max(1,width-(i>0?66:0)),height:i===0 && !dataOnly?250:(div.layout.height || specs[i].layout.height),autosize:false}):Promise.resolve()))
    .then(()=>Promise.all(graphs.map(reflowProfileLabels))).then(()=>graphs.forEach(tidyLabels));
}
function scheduleLayout() {
  if(visibleWidth()<50) {lastSize='';return;}
  if(!ready) {startPlots();return;}
  if(resizePending)return;
  resizePending=true;
  requestAnimationFrame(()=>enqueue(async()=>{
    try {await resizeVisible();} finally {resizePending=false;}
  }).catch(()=>{card.textContent='Could not resize graphs. Reopen this tab.';}));
}
function positionAxisControls(div) {
  const index=graphs.indexOf(div),panel=panelCards[index];if(!panel)return;
  const key=div.layout.meta?.dataset,floor=activityFloors.find(f=>f.key===key && f.id===specs[index].layout.meta?.panel_id);if(!floor)return;
  const axis=div._fullLayout.yaxis;if(!axis)return;
  floor.slider.parentElement.style.top=axis._offset+'px';
  floor.slider.style.height=Math.max(35,axis._length-30)+'px';
}
function bindGraph(div,index) {
        if(!div._fullLayout)return;
        const guide=document.createElement('div');guide.className='time-guide';div.appendChild(guide);guides[index]=guide;
        const marker=document.createElement('div');marker.className='point-highlight';div.appendChild(marker);highlights[index]=marker;
        div.on('plotly_afterplot',()=>{positionAxisControls(div);hoverGeometry(div);tidyLabels(div);updateTargetNote(div,graphs.indexOf(div));});positionAxisControls(div);hoverGeometry(div);tidyLabels(div);updateTargetNote(div,graphs.indexOf(div));
        div.on('plotly_hover',event=>queueHover(div,event));div.on('plotly_unhover',()=>queueHover(div,null));
        div.on('plotly_relayout',event=>{
          if(syncing || div.layout.meta?.non_time)return;
          rememberCustomAxes(div,event);rememberPanelAxes(div,event);
          let range=event['xaxis.range'];
          if(event['xaxis.range[0]']!==undefined)range=[event['xaxis.range[0]'],event['xaxis.range[1]']];
          if(event['xaxis.autorange'])range=[0,1440];
          if(!range)return;
          enqueue(()=>setTimeRange(range)).catch(()=>{card.textContent='Could not synchronize zoom.';});
        });

}
async function startPlots() {
  if(starting || ready || visibleWidth()<50)return;
  starting=true;
  try {
    if(document.fonts)await document.fonts.ready;
    await enqueue(async()=>{
      if(visibleWidth()<50)return;
      await Promise.all(graphs.map((div,i)=>{if(workspaceGraphs && i>0 && panelStateAt(i).deleted){div.layout=JSON.parse(JSON.stringify(specs[i].layout));div.data=[];return Promise.resolve();}const source=localSource(i);const view=workspaceGraphs && panelStateAt(i).deleted?{data:[],layout:{...specs[i].layout,height:190}}:decorate(panelSourceView(source,i,[0,1440]),i);return Plotly.newPlot(div,view.data,sizedLayout(view,i),
        {responsive:false,displaylogo:false,scrollZoom:false,toImageButtonOptions:{format:'png',scale:2}}).then(()=>reflowProfileLabels(div));}));
      graphs.forEach(bindGraph);
      ready=true;controls();await resizeVisible();
      if(navigation?.report_render)await exportReportFigures();
    });
  } catch(error) {console.error(error);card.textContent='Could not draw graphs: '+error.message;if(navigation?.report_render)window.parent.postMessage({type:'profile-studio:report-rendered',id:navigation.report_render.id,error:String(error)},'*');}
  finally {starting=false;}
}
function dailyView(spec,index,day,range) {
  const clone=JSON.parse(JSON.stringify(spec));
  if(clone.layout.meta?.kind==='insight')return clone;
  if(clone.layout.meta?.kind==='custom') {
    clone.layout=sizedLayout(clone,index);clone.layout.meta.custom_day=day;clone.layout.xaxis.range=range;return clone;
  }
  const data=clone.data.filter(trace=>!trace.meta?.date || trace.meta.date===day);
  compactLegend(data);
  const layout=sizedLayout(clone,index);
  layout.shapes=(layout.shapes || []).filter(s=>!s.name?.startsWith('Activity | ') || s.name.split(' | ')[1]===day);
  layout.title.text=layout.title.text.replace(/[0-9]{4}-[0-9]{2}-[0-9]{2}(?: – [0-9]{4}-[0-9]{2}-[0-9]{2}(?: · selected days)?)?/g,day);
  layout.xaxis.range=range;layout.xaxis.autorange=false;layout.annotations=[];
  if(layout.meta?.kind==='hourly') {
    layout.meta.single_day=true;
    const heat=data.find(t=>t.meta?.kind==='hourly_heatmap');
    const bars=data.find(t=>t.meta?.kind==='hourly_histogram');
    const row=heat.y.indexOf(day);
    heat.y=[day];heat.z=row>=0?[heat.z[row]]:[Array(24).fill(null)];
    heat.customdata=row>=0?[heat.customdata[row]]:[[]];
    bars.y=heat.z[0].map((value,h)=>heat.customdata[0][h]?.[5]?value:null);
    bars.customdata=bars.y.map(v=>v===null?0:1);
    bars.name='Hourly '+heat.meta.label.toLowerCase();bars.meta.label=bars.name;
    layout.yaxis.autorange='reversed';delete layout.yaxis.range;
    layout.yaxis2.autorange=true;delete layout.yaxis2.range;
    layout.yaxis2.title.text=heat.meta.unit;
    if(heat.z[0].every(v=>v===null))layout.annotations=[{text:heat.meta.dataset==='profile_percentage'?'No known effective profile data':'No available treatment data',xref:'paper',yref:'paper',x:.5,y:.7,showarrow:false}];
    return {data,layout};
  }

  const recorded=data.filter(t=>t.meta?.date===day);
  const relevant=layout.title.text.startsWith('Glucose ·')?recorded.filter(t=>t.meta.kind==='glucose'):recorded;
  if(index>0 && !relevant.some(t=>Array.isArray(t.y) && t.y.some(v=>v!==null)))layout.annotations=[{text:'No recorded data for this day',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false}];
  const isGlucose=index===0?currentOverlay==='Glucose':layout.title.text.startsWith('Glucose ·');
  const isTarget=index===0?currentOverlay==='Temporary Targets':layout.title.text.startsWith('Temp targets ·');
  const scale=navigation.unit==='mmol/L'?1:18;
  let peak=0;data.filter(t=>t.meta?.kind==='glucose').forEach(t=>t.y.forEach(y=>{if(y!==null)peak=Math.max(peak,y);}));
  const maximum=Math.max(20*scale,peak>20*scale?Math.ceil(peak*1.05/scale)*scale:20*scale);
  [layout.yaxis,layout.yaxis2,layout.yaxis3].filter(Boolean).forEach(axis=>{delete axis.range;axis.autorange=true;delete axis.matches;delete axis.autorangeoptions;});
  if(isGlucose){const axis=index===0?layout.yaxis2:layout.yaxis;axis.range=[0,maximum];axis.autorange=false;}
  if(isTarget){const axis=index===0?layout.yaxis2:layout.yaxis;axis.range=[0,20*scale];axis.autorange=false;}
  // Recompute per displayed day; do not retain a larger day's label padding.
  const labelAxes=new Set(data.filter(t=>t.mode?.includes('text')).map(t=>t.yaxis || 'y'));
  labelAxes.forEach(name=>{
    const axis=layout['yaxis'+name.slice(1)];axis.layer='below traces';layout.xaxis.layer='below traces';
    if(axis.autorange===false)return;
    const values=data.filter(t=>(t.yaxis || 'y')===name).flatMap(t=>t.y || []).filter(Number.isFinite);
    if(values.length){const high=Math.max(...values),span=Math.max(high-Math.min(0,...values),1);axis.autorangeoptions={include:high+.20*span};}
  });
  layout.uirevision=day+':'+currentOverlay;
  return {data,layout};
}
function drawCalendar() {
  dateCalendar.replaceChildren();
  if(!navigation)return;
  const months=[...new Set(navigation.days.map(day=>day.slice(0,7)))];
  months.forEach(month=>{
    const [year,number]=month.split('-').map(Number);
    const title=document.createElement('div');title.className='calendar-month';title.textContent=new Date(year,number-1,1).toLocaleDateString(undefined,{month:'long',year:'numeric'});dateCalendar.appendChild(title);
    const grid=document.createElement('div');grid.className='calendar-grid';dateCalendar.appendChild(grid);
    ['M','T','W','T','F','S','S'].forEach(text=>{const label=document.createElement('span');label.textContent=text;grid.appendChild(label);});
    const offset=(new Date(year,number-1,1).getDay()+6)%7;
    for(let i=0;i<offset;i++)grid.appendChild(document.createElement('span'));
    for(let i=1;i<=new Date(year,number,0).getDate();i++) {
      const day=month+'-'+String(i).padStart(2,'0'),button=document.createElement('button');button.type='button';button.textContent=String(i);button.disabled=!navigation.days.includes(day);button.title=day+(button.disabled?' · not loaded':' · loaded');button.setAttribute('aria-pressed',String(workspaceGraphs?dailyDate===day:selectedDays.includes(day)));
      button.addEventListener('click',()=>{dateCalendar.hidden=true;dayLabel.setAttribute('aria-expanded','false');cycleDay(0,day);});grid.appendChild(button);
    }
  });
}
dayLabel.addEventListener('click',()=>{drawCalendar();dateCalendar.hidden=!dateCalendar.hidden;dayLabel.setAttribute('aria-expanded',String(!dateCalendar.hidden));});
async function toggleSMB(index) {return changePanelState(index,s=>{s.excludeSMB=!s.excludeSMB;});}

async function cycleDay(direction,requestedDay=null) {
  if(!navigation || !ready || syncing)return;
  return enqueue(async()=>{
    const current=workspaceGraphs?dailyDate:(direction>0?selectedDays[selectedDays.length-1]:selectedDays[0]);
    const index=(navigation.days.indexOf(current)+direction+navigation.days.length)%navigation.days.length;
    const day=requestedDay || navigation.days[index], range=graphs[0]._fullLayout.xaxis.range.slice();
    syncing=true;controls();clearHover();
    const previousDays=selectedDays,previousCycled=dateCycled;
    if(workspaceGraphs){try{dailyDate=day;await redrawLocal((_,i)=>panelStateAt(i).graphType==='daily');updateSummary();graphs.forEach(tidyLabels);}finally{syncing=false;controls();}return;}
    try {
      selectedDays=[day];dateCycled=true;
      const source=specs.map((_,i)=>localSource(i));
      if(excludeSMB)source.forEach((spec,i)=>{if(spec.layout.meta?.kind==='hourly' && spec.layout.meta.dataset==='bolus')source[i]=navigation.bolus_without_smb.daily;});
      if(navigation.overlays)source[0]=navigation.overlays[currentOverlay].daily;
      const views=source.map((spec,i)=>decorate(dailyView(spec,i,day,range),i));
      await Promise.all(graphs.map((div,i)=>views[i]?Plotly.react(div,views[i].data,views[i].layout).then(()=>reflowProfileLabels(div)):Promise.resolve()));
      selectedDays=[day];dateCycled=true;updateSummary();graphs.forEach(tidyLabels);
    } catch(error) {selectedDays=previousDays;dateCycled=previousCycled;card.textContent='Could not change the displayed day. Reopen the graph view.';}
    finally {syncing=false;controls();}
  });
}
async function changeOverlay(requested) {
  if(!navigation?.overlays || !ready || syncing)return;
  return enqueue(async()=>{
    const previous=currentOverlay;
    syncing=true;controls();clearHover();
    try {
      currentOverlay=requested;
      const range=graphs[0]._fullLayout.xaxis.range.slice();
      let view;
      if(workspaceGraphs)view=panelSourceView(localSource(0),0,range);
      else if(dateCycled)view=dailyView(navigation.overlays[currentOverlay].daily,0,selectedDays[0],range);
      else {
        view=JSON.parse(JSON.stringify(localSource(0)));
        view.layout=sizedLayout(view,0);view.layout.xaxis.range=range;view.layout.xaxis.autorange=false;workoutAxes(view,range);
        view.layout.uirevision='overlay:'+currentOverlay;
      }
      view=decorate(view,0);
      await Plotly.react(graphs[0],view.data,view.layout);await reflowProfileLabels(graphs[0]);tidyLabels(graphs[0]);
    } catch(error) {currentOverlay=previous;card.textContent='Could not change overlay. Reopen the graph view.';}
    finally {syncing=false;controls();}
  });
}
panels.addEventListener('scroll',clearHover,{passive:true});
previousDay.addEventListener('click',()=>cycleDay(-1));
nextDay.addEventListener('click',()=>cycleDay(1));
expand.addEventListener('click',async()=>{
  try {
    if(document.fullscreenElement)await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  }catch(error){card.textContent='Browser blocked fullscreen. Use browser fullscreen (F11) for more room.';}
});
document.addEventListener('fullscreenchange',()=>{expand.textContent=document.fullscreenElement?'↙ Exit expanded view':'⛶ Expand graphs';workspaceSize();scheduleLayout();});
const observer=new ResizeObserver(scheduleLayout);
observer.observe(viewer);observer.observe(panels);
if(!navigation?.report_render && typeof IntersectionObserver!=='undefined')new IntersectionObserver(entries=>{
  intersects=entries.some(entry=>entry.isIntersecting);
  if(!intersects)lastSize='';
  scheduleLayout();
}).observe(viewer);
__VIEWER_STATE__
__REPORT_UI__
setupTopControlAreas();setupActivityControls();setupChangeControls();setupReportControls();
restoreViewer();applyGraphRestore();setupWorkspace();updateSummary();controls();startPlots();
window.addEventListener('message',event=>{
  if(event.source!==window.parent || event.data?.type!=='profile-studio:restore-graph')return;
  enqueue(()=>{navigation.restore_graph=event.data.request;applyGraphRestore();
    graphs.forEach((div,i)=>{if(div.layout)updateTargetNote(div,i);});controls();lastSize='';scheduleLayout();});
});
</script></body></html>""".replace('__FILLED_REGIONS__',Path(__file__).with_name('filled_regions.js').read_text(encoding='utf-8'),1).replace('__GARMIN_VIEW__',Path(__file__).with_name('garmin_view.js').read_text(encoding='utf-8'),1).replace('__PANEL_VIEW__',Path(__file__).with_name('panel_view.js').read_text(encoding='utf-8'),1).replace('__WORKSPACE_VIEW__',Path(__file__).with_name('workspace_view.js').read_text(encoding='utf-8'),1).replace('__INSIGHTS_VIEW__',Path(__file__).with_name('insights_view.js').read_text(encoding='utf-8')+'\n'+Path(__file__).with_name('sleep_insight_view.js').read_text(encoding='utf-8'),1).replace('__REPORT_UI__',Path(__file__).with_name('report_ui.js').read_text(encoding='utf-8'),1).replace('__VIEWER_STATE__',Path(__file__).with_name('viewer_state.js').read_text(encoding='utf-8'),1).replace('__CUSTOM_GRAPH__',Path(__file__).with_name('custom_graph.js').read_text(encoding='utf-8'),1).replace('__VIEWER_PAYLOAD__',payload_json,1)


def render_graphs(figures, dark, navigation=None, cache=None):
    # A fixed profile plus a separately scrollable stack works on short screens
    # without a page-level overlay covering the editor or save controls.
    html = cached(cache,'html',(navigation['render_key'],dark,st.session_state.get('health_report_preset_revision',0)),lambda: viewer_html(figures,dark,navigation),limit=3) if cache is not None and navigation and 'render_key' in navigation else viewer_html(figures,dark,navigation)
    event=graph_component(html=html,height=1040 if len(figures)>1 else 540,
                          restore_graph=st.session_state.get('health_restore_graph'),picker_revision=st.session_state.get('health_picker_revision',0),
                          report_result=st.session_state.get('health_report_result'),
                          key='health_graph_'+str((navigation or {}).get('metric') or 'data'),default=None)
    handled=st.session_state.setdefault('health_graph_events',{})
    scope=str((navigation or {}).get('metric') or 'data')
    if isinstance(event,dict) and event.get('id') and event['id']!=handled.get(scope):
        handled[scope]=event['id']
        try:
            if event.get('kind')=='graph-visibility':
                hidden=event.get('hidden')
                if not isinstance(hidden,list) or not all(isinstance(row,dict) and all(isinstance(row.get(k),str) for k in ('id','base','label')) for row in hidden):
                    raise ValueError('Invalid hidden graph selection.')
                if hidden!=st.session_state.get('health_hidden_graphs',[]):
                    st.session_state.health_hidden_graphs=hidden
                    st.rerun()
            elif event.get('kind')=='report-delete':
                from report_config import delete_preset
                name=event.get('preset_name');delete_preset(name)
                st.session_state.pop('health_report_selected_preset',None)
                st.session_state.health_report_preset_revision=st.session_state.get('health_report_preset_revision',0)+1
                st.session_state.health_report_result=dict(id=event['id'],status='deleted',message='Deleted PDF preset: '+name)
                st.rerun()
            elif event.get('kind')=='report-preset':
                from report_config import save_preset
                save_preset(event.get('name'),event.get('settings'))
                st.session_state.health_report_selected_preset=event.get('name').strip()
                st.session_state.health_report_preset_revision=st.session_state.get('health_report_preset_revision',0)+1
                st.session_state.health_report_result=dict(id=event['id'],status='saved',message='Saved PDF settings: '+event['name'].strip())
                st.rerun()
            elif event.get('kind')=='report':
                if cache is None or navigation is None:raise ValueError('Load recorded data before exporting.')
                st.session_state.pop('health_report_html',None)
                st.session_state.pop('health_report_description',None)
                if event.get('preset_name'):
                    from report_config import request_for_preset
                    event=dict(event,**request_for_preset(event['preset_name'],loaded=cache))
                    st.session_state.health_report_selected_preset=event['preset_name']
                from report_export import build_report
                bar=st.progress(0.,text='Preparing report…')
                try:st.session_state.health_report_html=build_report(cache,navigation,event,progress=lambda n,total,label:bar.progress(n/total,text=label+' · '+str(n)+' / '+str(total)))
                finally:bar.empty()
                st.session_state.health_report_name='profile-studio-'+str(event.get('first',cache['first']))+'-'+str(event.get('last',cache['last']))+'.html'
                st.session_state.health_report_description=str(event.get('preset_name') or event.get('title') or 'Report')+' · '+str(event['first'])+' – '+str(event['last'])
                st.session_state.health_report_result=dict(id=event['id'],status='ready',message='Report prepared. Open the preview below to print or save as PDF.')
                st.rerun()
            else:
                save_configuration(event.get('name'),event.get('config'))
                st.session_state.health_config_notice='Saved graph configuration: '+event['name'].strip()
                st.rerun()
        except (ValueError,TypeError,KeyError,OSError) as exc:
            if event.get('kind') in ('report','report-preset','report-delete'):
                st.session_state.health_report_result=dict(id=event['id'],status='error',message=str(exc))
                st.rerun()
            st.error('Could not process graph request: '+str(exc))
    if st.session_state.get('health_report_html'):
        import streamlit.components.v1 as components
        with st.expander('Report preview'+(' · '+st.session_state.health_report_description if st.session_state.get('health_report_description') else ''),expanded=True):
            st.iframe(st.session_state.health_report_html,height=650)
        st.caption('Use Download HTML in the preview to save this exact layout, or Print / Save as PDF. Print at 100% on the selected A4 orientation, without browser headers/footers.')
