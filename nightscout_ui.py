"""Manual connection controls; credentials and loaded records stay in session memory."""
from datetime import datetime, timedelta
import os
import pandas as pd
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from nightscout import NightscoutError, load_nightscout
from view_config import configuration_controls
from date_controls import day_calendar
from garmin_ui import source_controls, source_inputs, combined_snapshot
from garmin_data import GARMIN_LAYERS, SLEEP_OVERLAYS
from nightscout_charts import LAYERS, GROUP_KEYS, DIABETES_LAYERS, GARMIN_MAIN_LAYERS, normalize_layers, date_label


def sidebar_controls(profile_zone):
    try:ZoneInfo(profile_zone)
    except (ValueError,ZoneInfoNotFoundError):
        st.info('Enter a valid display/profile timezone before loading data.');return None
    today=datetime.now(ZoneInfo(profile_zone)).date()
    # Submit dates and both connection sections as one snapshot. Typing alone never reloads.
    with st.form('health_sources',enter_to_submit=False):
        st.markdown('**Load date range · all sources**')
        first=st.date_input('From date',today-timedelta(days=6),key='ns_from')
        last=st.date_input('Through date',today,key='ns_until')
        st.caption('One range for Nightscout and Garmin · '+profile_zone+'. Up to 31 days.')
        refresh_all=st.form_submit_button('Refresh all data',key='health_refresh_all',help='Submit these dates and connection details, then read both configured sources once.')
        with st.expander('Nightscout data'):
            st.caption('Read-only connection. Enter a readable access token here, not in chat.')
            url=st.text_input('Nightscout site URL',value=os.environ.get('NIGHTSCOUT_URL',''),placeholder='https://your-nightscout.example',key='ns_url')
            token=st.text_input('Read-only access token',value=os.environ.get('NIGHTSCOUT_TOKEN',''),type='password',key='ns_token')
            load=st.form_submit_button('Load / refresh data',key='ns_refresh')
        with st.expander('GarminDB data'):
            garmin_inputs=source_inputs(profile_zone,st.form_submit_button)
    if load or (refresh_all and url.strip()):
        try:
            with st.spinner('Loading Nightscout records…'):
                snapshot=load_nightscout(url,token,first,last,profile_zone)
            st.session_state.ns_loaded=snapshot
        except (NightscoutError, ValueError, ZoneInfoNotFoundError) as exc:
            st.error('Nightscout load failed: '+str(exc))
            if st.session_state.get('ns_loaded') is not None:st.caption('Previously loaded Nightscout data is still displayed.')
    ns_loaded=st.session_state.get('ns_loaded')
    if ns_loaded is not None:
        st.caption(f"Nightscout loaded: {ns_loaded['first']}–{ns_loaded['last']} · {ns_loaded['zone']}")
        if st.button('Clear loaded Nightscout data'):
            del st.session_state.ns_loaded
            st.rerun()
    else:st.caption('Submit Load / refresh data or Refresh all data to contact Nightscout.')
    garmin=source_controls(profile_zone,first,last,refresh_all=refresh_all,inputs=garmin_inputs)
    if refresh_all and not url.strip() and not garmin_inputs[0].strip():
        st.info('Enter a Nightscout URL or Garmin folder before refreshing.')
    loaded = combined_snapshot(ns_loaded, garmin)
    if loaded is None:
        return None
    with st.expander("Recorded data display", expanded=True):
        loaded.setdefault("_chart_cache", {})
        st.caption(f"Loaded {loaded['first']} through {loaded['last']} · {loaded['zone']}\n\n"
                   f"Updated {loaded['loaded_at'].astimezone(ZoneInfo(loaded['zone'])).strftime('%Y-%m-%d %H:%M %Z')}")
        for warning in loaded["warnings"]:
            st.warning(warning)
        previous=st.session_state.get('ns_mode','One day')
        if 'health_date_view' not in st.session_state:st.session_state.health_date_view='One day' if previous=='One day' else 'Date range'
        if 'health_median_mode' not in st.session_state:st.session_state.health_median_mode=previous=='Median + band'
        selection=st.segmented_control('Recorded data view',['One day','Date range'],key='health_date_view') or 'One day'
        if selection=='Date range':
            median=st.toggle('Median · off: Multiple days',key='health_median_mode')
            mode='Median + band' if median else 'Multiple days'
        else:mode='One day'
        st.session_state.ns_mode=mode
        days = day_calendar(loaded, multiple=mode != "One day")
        st.markdown('**Data layers**')
        options=[label for label,key in GARMIN_MAIN_LAYERS.items()
                 if any(not loaded['data'].get('g_steps' if k=='g_steps_cumulative' else k,pd.DataFrame()).empty for k in
                        (list(SLEEP_OVERLAYS.values())+['g_sleep'] if key=='g_sleep' else GROUP_KEYS.get(key,[key])))]
        categories={'diabetes':list(DIABETES_LAYERS) if ns_loaded is not None else [],'garmin':options}
        defaults=['Glucose'] if ns_loaded is not None else [next(iter(options),'Custom graph')]
        available=[x for group in categories.values() for x in group]+['Custom graph']
        current=[x for x in normalize_layers(st.session_state.get('ns_layers',defaults)) if x in available]
        st.session_state.ns_layers=current
        for category,choices in categories.items():
            st.session_state['ns_layers_'+category]=[x for x in current if x in choices]
        for category,choices in categories.items():
            if not choices:continue
            st.pills(category.title(),choices,selection_mode='multi',key='ns_layers_'+category,
                     format_func=lambda value:value.removeprefix('Garmin · '),on_change=_layers_changed)
        custom_ids=custom_layer_controls()
        layers=st.session_state.ns_layers
        configuration_controls()
        if st.session_state.get("health_config_notice"):st.caption(st.session_state.pop("health_config_notice"))
        if "Custom graph" in layers:
            st.caption("Choose recorded data and profile schedules directly above the Custom graph, including in expanded view. Schedules use the current draft and selected references; they are not historical active-profile records.")
        overlay = "None"
        show_targets = True  # Controlled locally on the graph, including fullscreen.
        for label in set(layers):
            key = LAYERS[label]
            if key=='g_steps_cumulative':key='g_steps'
            if key == 'custom':continue
            if key in ('profile_percentage','site_changes','sensor_changes'):continue
            if all(k not in loaded["data"] or loaded["data"][k].empty for k in GROUP_KEYS.get(key, [key])) and (key != "basal" or loaded["data"]["basal_percent"].empty):
                st.caption(f"No {label.lower()} records were returned for the loaded dates.")
        if mode == "Median + band":
            st.caption("Glucose, temp basal, IOB and COB: median and 25–75% band in 5-minute bins, with one contribution per day. Missing intervals stay blank. Temp basal summarizes recorded temp rates only. Bolus and carb heatmaps show hourly totals; bar plots default to the average hourly total across complete hours, with an in-graph Median toggle. Zero means no event returned; unavailable and future hours stay blank.")
        st.caption('Site / sensor change markers use uploaded Site Change, Sensor Start and Sensor Change events. Use Graph settings to show them on glucose, all time graphs, or neither. Reload Nightscout after updating to import these events and active-profile history.')
        st.caption("Temporary targets use rectangular shading toward the historical profile target range. Missing target history: line only. Reason colors: Eating Soon orange, Activity cyan, Hypo red, other/missing green. The 4–10 band is a fixed guide.")
        if 'Variable Sensitivity' in layers:
            st.caption("Variable sensitivity is the uploaded variable_sens, not the scheduled ISF. Values are displayed in the profile's glucose units per U. Missing fields stay blank.")
        st.caption("Temporary basal shows recorded intervals, not a reconstructed delivery total. Gaps are not filled with your draft basal. IOB/COB are uploaded values.")
        st.caption("Select historical days manually; they are not automatically matched to profile versions. Editing your profile never changes the recorded data.")
        if garmin:
            st.caption("Garmin: sleep stages appear only in recorded intervals. Median sleep defaults to average minutes asleep per hour across dates with recorded stages. Dates with no stage records are excluded; within recorded dates, hours without sleep contribute zero. Stage composition is an optional conditional view. Activities stay recorded intervals. Sleep signals are optional within Sleep. Activity intervals shade Garmin graphs. Daily resting heart rate is labelled as a reference. Units are Metric.")
            if ns_loaded is not None:
                st.caption("The calendar includes dates from either source. Missing source records stay blank. Refresh all data applies the shared load range to both configured sources.")
        return {"loaded": loaded, "days": sorted(days), "mode": mode, "layers": layers, "overlay": overlay, "show_targets": show_targets, "custom_ids": custom_ids, "custom_catalog": st.session_state.health_custom_catalog}



def graph_date_controls(view, metric):
    # All graph controls live in one viewer, also used in fullscreen. Streamlit
    # controls here previously disagreed with the locally selected overlay.
    st.caption(date_label(view['days']) + ' · ' + view['loaded']['zone'] +
               ' · Dashed vertical lines mark changes in the selected profile setting.')
    return dict(view, overlay='None', same_scale=False)


def _layers_changed():
    st.session_state.ns_layers=[value for category in ('diabetes','garmin')
                              for value in st.session_state.get('ns_layers_'+category,[])]
    if st.session_state.get('health_custom_visible'):
        st.session_state.ns_layers.append('Custom graph')


def _add_custom_layer():
    catalog=st.session_state.setdefault('health_custom_catalog',[])
    serial=max(st.session_state.get('health_custom_serial',0),*(int(k.split('-')[1]) for k in catalog),0)+1
    key=f'custom-{serial}'
    st.session_state.health_custom_serial=serial
    st.session_state.health_custom_catalog=[*catalog,key]
    st.session_state.health_custom_visible=[*st.session_state.get('health_custom_visible',[]),key]
    if 'Custom graph' not in st.session_state.ns_layers:st.session_state.ns_layers.append('Custom graph')


def _custom_visibility(key):
    visible=st.session_state.health_custom_visible
    st.session_state.health_custom_visible=[k for k in visible if k!=key]+([key] if st.session_state['show_'+key] else [])
    _layers_changed()


def _remove_custom_layer(key):
    st.session_state.health_custom_catalog=[k for k in st.session_state.health_custom_catalog if k!=key]
    st.session_state.health_custom_visible=[k for k in st.session_state.health_custom_visible if k!=key]
    _layers_changed()


def custom_layer_controls():
    # The graph renderer keeps each panel's settings by ID; the sidebar owns which exist/are visible.
    if 'health_custom_catalog' not in st.session_state:
        saved=st.session_state.get('health_view_config',{}).get('customPanels',[])
        keys=[p['id'] for p in saved if isinstance(p,dict) and isinstance(p.get('id'),str)]
        if not keys and 'Custom graph' in st.session_state.ns_layers:keys=['custom-1']
        st.session_state.health_custom_catalog=keys
        st.session_state.health_custom_visible=keys.copy() if 'Custom graph' in st.session_state.ns_layers else []
    title,add=st.columns([4,1]);title.markdown('**Custom**')
    add.button('+',key='add_custom_layer',help='Add a Custom Graph',on_click=_add_custom_layer)
    for key in st.session_state.health_custom_catalog:
        label,remove=st.columns([4,1])
        st.session_state['show_'+key]=key in st.session_state.health_custom_visible
        label.checkbox('Custom '+key.split('-')[1],key='show_'+key,on_change=_custom_visibility,args=(key,))
        remove.button('×',key='delete_'+key,help='Delete this Custom Graph',on_click=_remove_custom_layer,args=(key,))
    return st.session_state.health_custom_visible.copy()
