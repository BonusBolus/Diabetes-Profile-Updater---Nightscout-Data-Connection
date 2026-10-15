"""Local GarminDB source controls; all reads happen on explicit refresh."""
import os
import sqlite3
from zoneinfo import ZoneInfoNotFoundError

import streamlit as st
from garmin_data import load_garmin, merge_sources
from source_loading import start_load, loading


def source_inputs(profile_zone, submit_button=st.button):
    folder=st.text_input('Garmin health-data folder',value=os.environ.get('GARMINDB_FOLDER',''),key='garmin_folder',
                        placeholder=r'C:\Users\your-name\HealthData',help='HealthData: parent of DBs, Sleep and FitFiles.')
    zone=st.text_input('Garmin database timezone',value=profile_zone,key='garmin_zone',
                      help='Timezone of GarminDB’s stored local timestamps. Travel or ambiguous DST times may need separate imports.')
    submit=submit_button('Load / refresh Garmin data',key='garmin_refresh',disabled=loading('garmin'))
    return folder,zone,submit


def source_controls(profile_zone, first, last, refresh_all=False, inputs=None, categories=None):
    with st.expander('Garmin load status' if inputs is not None else 'GarminDB data',expanded=bool(inputs and (inputs[2] or refresh_all))):
        folder,zone,submit=inputs if inputs is not None else source_inputs(profile_zone)
        if submit or (refresh_all and folder.strip()):
            start_load('garmin',load_garmin,folder,first,last,zone,profile_zone,"Metric",**({"categories":categories} if categories is not None else {}))
        loaded=st.session_state.get('garmin_loaded')
        if loaded:
            st.caption(f"Loaded {loaded['first']}–{loaded['last']} · displayed in {loaded['zone']}")
            if st.button('Clear loaded Garmin data',disabled=loading('garmin')):
                st.session_state.pop('garmin_loaded');st.rerun()
            for message in loaded['warnings']:st.warning(message)
            if loaded['inventory']:st.dataframe(loaded['inventory'],hide_index=True,width='stretch')
            if loaded['zone']!=profile_zone:
                st.info('Reload Garmin data after changing the profile timezone.');return None
        return loaded


def combined_snapshot(ns,garmin):
    if not garmin:return ns
    identity=(ns.get('loaded_at') if ns else None,garmin['loaded_at'],garmin['zone'],garmin.get('measurement_units'))
    cached=st.session_state.get('_combined_health')
    if not cached or cached[0]!=identity:
        cached=(identity,merge_sources(ns,garmin));st.session_state._combined_health=cached
    return cached[1]
