"""Portable display configurations. Never store credentials or health records."""
import json
import hashlib
import os
import re
from pathlib import Path
import tempfile
import streamlit as st


def parse_configuration(content):
    if len(content)>200_000:raise ValueError('Configuration is too large.')
    data=json.loads(content)
    if not isinstance(data,dict) or data.get('format')!='profile-studio-view' or data.get('version')!=1:
        raise ValueError('Choose a Profile Studio view configuration JSON file.')
    if not isinstance(data.get('layers'),list) or not all(isinstance(v,str) for v in data['layers']):
        raise ValueError('Invalid data layers.')
    if data.get('mode') not in ('One day','Multiple days','Median + band'):
        raise ValueError('Invalid recorded data view.')
    if not isinstance(data.get('viewer'),dict):raise ValueError('Invalid graph settings.')
    return {k:data[k] for k in ('format','version','layers','mode','viewer')}


CONFIG_FOLDER=Path(__file__).resolve().parent/'graph_configurations'


def save_configuration(name, config, folder=None):
    if not isinstance(name,str) or not name.strip() or len(name.strip())>80:
        raise ValueError('Enter a configuration name of 1–80 characters.')
    name=name.strip()
    config=parse_configuration(json.dumps(config))
    config['name']=name
    folder=Path(folder or CONFIG_FOLDER);folder.mkdir(parents=True,exist_ok=True)
    # Names are display labels, never filesystem paths. Same name updates that view.
    stem=re.sub('[^a-z0-9]+','-',name.casefold()).strip('-')[:40] or 'view'
    path=folder/(stem+'-'+hashlib.sha256(name.casefold().encode()).hexdigest()[:12]+'.json')
    fd,temp=tempfile.mkstemp(dir=folder,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:json.dump(config,out,indent=2,ensure_ascii=False)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return path


def saved_configurations(folder=None):
    configs=[];errors=[]
    for path in sorted(Path(folder or CONFIG_FOLDER).glob('*.json')):
        try:
            raw=json.loads(path.read_text(encoding='utf-8'));config=parse_configuration(json.dumps(raw))
            name=raw.get('name',path.stem)
            if not isinstance(name,str):raise ValueError('Invalid name')
            configs.append((name,config))
        except (ValueError,OSError,TypeError) as exc:errors.append(f'{path.name}: {exc}')
    return sorted(configs,key=lambda c:c[0].casefold()),errors


def apply_configuration(config):
    from nightscout_charts import normalize_layers
    st.session_state.ns_layers=normalize_layers(config['layers'])
    st.session_state.ns_mode=config['mode']
    st.session_state.health_date_view='One day' if config['mode']=='One day' else 'Date range'
    st.session_state.health_median_mode=config['mode']=='Median + band'
    viewer=dict(config['viewer'])
    garmin=dict(viewer.get('garmin') or {})
    legacy={'Garmin · HRV':'g_sleep_hrv','Garmin · SpO₂':'g_sleep_spo2',
            'Garmin · Sleep movement':'g_sleep_movement','Garmin · Restless moments':'g_sleep_restless','Garmin · Sleep respiration':'g_sleep_rr'}
    selected=list(garmin.get('sleepFields') or [])
    for label in config['layers']:
        if label in legacy and legacy[label] not in selected:selected.append(legacy[label])
    garmin['sleepFields']=selected;viewer['garmin']=garmin
    panels=viewer.get('customPanels',[])
    keys=[p['id'] for p in panels if isinstance(p,dict) and isinstance(p.get('id'),str) and re.fullmatch(r'custom-[0-9]+',p['id'])]
    if not keys and 'Custom graph' in st.session_state.ns_layers:keys=['custom-1']
    st.session_state.health_custom_catalog=keys
    st.session_state.health_custom_visible=[k for k in viewer.get('customVisible',keys) if k in keys] if 'Custom graph' in st.session_state.ns_layers else []
    st.session_state.health_view_config=viewer
    st.session_state.health_config_revision=st.session_state.get('health_config_revision',0)+1


def configuration_controls():
    st.markdown('**Saved graph configurations**')
    configs,errors=saved_configurations()
    for index,(name,config) in enumerate(configs):
        st.button(name,key=f'health_saved_config_{index}',on_click=apply_configuration,args=(config,),width='stretch')
    if not configs:st.caption('Name and save the current view in the graph toolbar. Saved views appear here.')
    for error in errors:st.warning(error)
