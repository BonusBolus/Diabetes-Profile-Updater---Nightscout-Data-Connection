"""Manual connection controls; credentials and loaded records stay in session memory."""
from datetime import datetime, timedelta
import os
import pandas as pd
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from nightscout import NightscoutError, load_nightscout
from source_loading import start_load, loading, loading_status, collect_loads
from date_controls import day_calendar
from garmin_ui import source_controls, source_inputs, combined_snapshot
from garmin_data import GARMIN_LAYERS, SLEEP_OVERLAYS
from insights import INSIGHT_LAYERS
from nightscout_charts import LAYERS, GROUP_KEYS, DIABETES_LAYERS, GARMIN_MAIN_LAYERS, normalize_layers, date_label

NS_IMPORTS={'Glucose':{'glucose'},'COB + Carbs':{'loop','treatments'},
            'IOB + Boluses':{'loop','treatments'},'Temporary Basal':{'treatments'},
            'Temporary Targets':{'treatments'},'Variable Sensitivity':{'loop'},
            'Site / sensor events':{'treatments'},'Automation notes':{'treatments'}}
GARMIN_IMPORTS=dict(zip(GARMIN_MAIN_LAYERS,('steps','heart_rate','activity','stress','sleep','respiration')))


def _select_import_all(key,choices):
    st.session_state[key]=list(choices)


def import_selection(label,choices,key):
    if key not in st.session_state:st.session_state[key]=list(choices)
    elif key=='ns_load_layers' and 'Profile / site / sensor events' in st.session_state[key]:
        st.session_state[key]=['Site / sensor events' if v=='Profile / site / sensor events' else v for v in st.session_state[key]]
    st.pills(label,list(choices),selection_mode='multi',key=key,
             format_func=lambda value:value.removeprefix('Garmin · '))
    st.form_submit_button('Select all',key=key+'_all',on_click=_select_import_all,args=(key,list(choices)))
    return st.session_state.get(key,[])


def imported_layers(snapshot,requested):
    """Enable populated, successfully imported layers, without changing import choices."""
    data=snapshot['data'];result=[]
    for label in requested:
        if label not in LAYERS:continue
        key=LAYERS[label]
        fields=list(SLEEP_OVERLAYS.values())+['g_sleep'] if key=='g_sleep' else GROUP_KEYS.get(key,[key])
        if any(not data.get(field,pd.DataFrame()).empty for field in fields):result.append(label)
    return result


def select_imported_layers(snapshot,requested):
    current=normalize_layers(st.session_state.get('ns_layers',[]))
    st.session_state.ns_layers=list(dict.fromkeys(current+imported_layers(snapshot,requested)))


def sidebar_controls(profile_zone, display_slot=None, data_workspace=False):
    collect_loads()
    try:ZoneInfo(profile_zone)
    except (ValueError,ZoneInfoNotFoundError):
        st.info('Enter a valid display/profile timezone before loading data.');return None
    display_slot=display_slot if display_slot is not None else st.container()
    with st.expander('Load data settings',expanded=not (st.session_state.get('ns_loaded') or st.session_state.get('garmin_loaded'))):
        if data_workspace:
            profile_zone=st.text_input('Display timezone',value=profile_zone,key='health_timezone')
            st.selectbox('Glucose units',['mmol/L','mg/dL'],key='health_glucose_unit')
            try:ZoneInfo(profile_zone)
            except (ValueError,ZoneInfoNotFoundError):st.error('Enter a valid display timezone.');return None
        today=datetime.now(ZoneInfo(profile_zone)).date()
        # Submit dates and both connection sections as one snapshot. Typing alone never reloads.
        with st.form('health_sources',enter_to_submit=False):
            st.markdown('**Data to load**')
            ns_selection=import_selection('Diabetes',NS_IMPORTS,'ns_load_layers')
            garmin_selection=import_selection('Garmin',GARMIN_IMPORTS,'garmin_load_layers')
            st.markdown('**Load dates**')
            left,right=st.columns(2)
            first=left.date_input('From',today-timedelta(days=6),key='ns_from')
            last=right.date_input('Through',today,key='ns_until')
            refresh_all=st.form_submit_button('Refresh all data',key='health_refresh_all',help='Start both configured sources together. An import already running continues independently.')
            with st.expander('Nightscout data'):
                url=st.text_input('Nightscout URL',value=os.environ.get('NIGHTSCOUT_URL',''),placeholder='https://your-nightscout.example',key='ns_url')
                token=st.text_input('Access token',value=os.environ.get('NIGHTSCOUT_TOKEN',''),type='password',key='ns_token')
                load=st.form_submit_button('Load / refresh data',key='ns_refresh',disabled=loading('nightscout'))
            with st.expander('GarminDB data'):
                garmin_inputs=source_inputs(profile_zone,st.form_submit_button)
    status_slot=st.expander('Loading status',expanded=bool(load or refresh_all or garmin_inputs[2] or loading('nightscout') or loading('garmin')))
    with status_slot:
        if load or (refresh_all and url.strip()):
            collections=sorted(set().union(*(NS_IMPORTS[k] for k in ns_selection)))
            start_load('nightscout',load_nightscout,url,token,first,last,profile_zone,**({'categories':collections} if set(collections)!={'glucose','treatments','loop'} else {}))
        ns_loaded=st.session_state.get('ns_loaded')
        if ns_loaded is not None:
            st.caption(f"Nightscout loaded: {ns_loaded['first']}–{ns_loaded['last']} · {ns_loaded['zone']}")
            if st.button('Clear loaded Nightscout data',disabled=loading('nightscout')):
                del st.session_state.ns_loaded
                st.rerun()
        previous_garmin=st.session_state.get('garmin_loaded')
        garmin=source_controls(profile_zone,first,last,refresh_all=refresh_all,inputs=garmin_inputs,categories=[GARMIN_IMPORTS[k] for k in garmin_selection] if len(garmin_selection)!=len(GARMIN_IMPORTS) else None)
        if (load or refresh_all or garmin_inputs[2]) and (loading('nightscout') or loading('garmin')):st.rerun()
        loading_status()

        if refresh_all and not url.strip() and not garmin_inputs[0].strip():
            st.info('Enter a Nightscout URL or Garmin folder before refreshing.')
    loaded = combined_snapshot(ns_loaded, garmin)
    if loaded is None:
        with display_slot:st.caption('Recorded data to display · nothing loaded')
        return None
    with display_slot:
        st.markdown('**Recorded data to display**')
        loaded.setdefault("_chart_cache", {})
        st.caption(f"{loaded['zone']} · Updated {loaded['loaded_at'].astimezone(ZoneInfo(loaded['zone'])).strftime('%d %b %H:%M')}")
        with status_slot:
            for warning in loaded["warnings"]:st.warning(warning)
        days = day_calendar(loaded, multiple=True)
        mode = 'Median + band' if len(days)>1 else 'One day'
        # Every loaded source is available to graph instances. Importing never creates panels.
        from insights import insight_available
        layers=[]
        for label,key in LAYERS.items():
            if key=='compact':
                if not loaded['data'].get('glucose',pd.DataFrame()).empty:layers.append(label)
                continue
            if key=='custom':
                layers.append(label);continue
            if key.startswith('insight_'):
                if insight_available(loaded,key):layers.append(label)
                continue
            if key in ('profile_percentage','site_changes','sensor_changes'):
                if ns_loaded is not None:layers.append(label)
                continue
            fields=list(SLEEP_OVERLAYS.values())+['g_sleep'] if key=='g_sleep' else GROUP_KEYS.get(key,[key])
            if any(not loaded['data'].get(k,pd.DataFrame()).empty for k in fields):layers.append(label)
        if st.session_state.get('health_config_notice'):st.caption(st.session_state.pop('health_config_notice'))
        return dict(loaded=loaded,days=sorted(days),mode=mode,layers=layers,overlay='None',show_targets=True,
                    custom_ids=None,custom_catalog=None,workspace_graphs=True,
                    export_workspace=st.session_state.get('workspace_type')=='Data' and st.session_state.get('data_workspace')=='Export')



def graph_date_controls(view, metric):
    # All graph controls live in one viewer, also used in fullscreen. Streamlit
    # controls here previously disagreed with the locally selected overlay.
    st.caption(date_label(view['days']) + ' · ' + view['loaded']['zone'] +
               ' · Dashed vertical lines mark changes in the selected profile setting.')
    return dict(view, overlay='None', same_scale=False)


def _layers_changed():
    st.session_state.ns_layers=[value for category in ('diabetes','garmin','analysis')
                              for value in st.session_state.get('ns_layers_'+category,[])]
    if st.session_state.get('health_custom_visible'):
        st.session_state.ns_layers.append('Custom graph')


def graph_layer(base):
    """Resolve a panel's existing source identity back to its sidebar layer."""
    if base=='profile:settings':return None
    kind,_,dataset=base.partition(':')
    if kind=='custom':return 'Custom graph'
    if dataset=='basal_percent':dataset='basal'
    for label,key in LAYERS.items():
        if dataset==key or dataset in GROUP_KEYS.get(key,[]):return label
    return None


def _restore_graph():
    key=st.session_state.get('health_add_graph')
    row=next((r for r in st.session_state.get('health_hidden_graphs',[]) if r['id']==key),None)
    if row is None:return
    layer=graph_layer(row['base'])
    if layer and layer not in st.session_state.ns_layers:st.session_state.ns_layers.append(layer)
    if row['base'].startswith('custom:'):
        custom=key.removeprefix('custom:')
        if custom not in st.session_state.health_custom_visible:st.session_state.health_custom_visible.append(custom)
    revision=st.session_state.get('health_restore_graph',{}).get('revision',0)+1
    st.session_state.health_restore_graph=dict(id=key,revision=revision)
    st.session_state.health_hidden_graphs=[r for r in st.session_state.health_hidden_graphs if r['id']!=key]
    st.session_state.health_add_graph=None


def restore_graph_controls(available):
    hidden={row['id']:row for row in st.session_state.get('health_hidden_graphs',[])
            if graph_layer(row['base']) is None or graph_layer(row['base']) in available}
    if hidden:
        st.selectbox('+ Add graph',list(hidden),index=None,key='health_add_graph',placeholder='Restore a deleted graph',
                     format_func=lambda key:hidden[key]['label'],on_change=_restore_graph,
                     help='Restore one hidden graph with its settings. Duplicated copies are permanently removed when deleted.')


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
