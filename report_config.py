"""PDF export presets, deliberately separate from graph configurations."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from copy import deepcopy
from datetime import date

FOLDER=Path(__file__).resolve().parent/'report_configurations'
BLOCKS=('overview','profiles','profile_graphs','statistics','distribution','daily','summary','insights')
SECTIONS=BLOCKS+('median','overlay')


def settings(raw):
    if not isinstance(raw,dict):raise ValueError('Invalid report settings.')
    layout=raw.get('layout','landscape');count=raw.get('graphs_per_page',2)
    if layout not in ('portrait','landscape'):raise ValueError('Choose portrait or landscape.')
    if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=6:raise ValueError('Choose 1–6 graphs per page.')
    selected=raw.get('sections',[])
    if not isinstance(selected,list) or any(s not in SECTIONS for s in selected):raise ValueError('Invalid report sections.')
    blocks=raw.get('blocks')
    if blocks is None:
        keys=[]
        for section in selected:
            for key in (['summary','insights'] if section=='median' else ['summary'] if section=='overlay' else [section]):
                if key not in keys:keys.append(key)
        blocks=[dict(key=k,graphs_per_page=count) for k in keys]
    if not isinstance(blocks,list):raise ValueError('Invalid report blocks.')
    clean=[];seen=set()
    for block in blocks:
        if not isinstance(block,dict) or block.get('key') not in BLOCKS:raise ValueError('Invalid report block.')
        key=block['key'];n=block.get('graphs_per_page',count)
        if key in seen:raise ValueError('A report block can only be included once.')
        if isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=6:raise ValueError('Choose 1–6 graphs per page for '+key+'.')
        seen.add(key);item=dict(key=key,graphs_per_page=n)
        if 'viewer' in block:
            if not isinstance(block['viewer'],dict):raise ValueError('Invalid block graph settings.')
            item['viewer']=block['viewer']
        clean.append(item)
    result=dict(blocks=clean,layout=layout,graphs_per_page=count,sections=selected,title=str(raw.get('title','Profile Studio report'))[:120])
    if 'overview_fields' in raw:
        fields=raw['overview_fields']
        if not isinstance(fields,list) or any(k not in ('coverage','glucose','treatments','events','app_range','comparison_range') for k in fields):raise ValueError('Invalid overview selections.')
        result['overview_fields']=fields
    if 'viewer' in raw:
        if not isinstance(raw['viewer'],dict):raise ValueError('Invalid export graph settings.')
        result['viewer']=raw['viewer']
    for key in ('first','last'):
        if raw.get(key):result[key]=date.fromisoformat(raw[key]).isoformat()
    date_mode=raw.get('date_mode','fixed' if result.get('first') and result.get('last') else 'loaded')
    if date_mode not in ('fixed','loaded'):raise ValueError('Choose loaded dates or specific dates.')
    result['date_mode']=date_mode
    if date_mode=='fixed':
        if not result.get('first') or not result.get('last'):raise ValueError('Choose both report dates.')
        if result['first']>result['last']:raise ValueError('The first report date must not follow the last date.')
        if (date.fromisoformat(result['last'])-date.fromisoformat(result['first'])).days>365:raise ValueError('Export up to 366 days at a time.')
    from report_stats import time_minute
    for key,default in [('from_time','00:00'),('until_time','24:00')]:
        value=raw.get(key,default);time_minute(value);result[key]=value
    if time_minute(result['from_time'])>=time_minute(result['until_time']):raise ValueError('The daily start time must be earlier than the end time.')
    return result


def save_preset(name,raw,folder=None):
    if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('Enter a report preset name of 1–80 characters.')
    name=name.strip();data=dict(format='profile-studio-report',version=2,name=name,settings=settings(raw))
    folder=Path(folder or FOLDER);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(hashlib.sha256(name.casefold().encode()).hexdigest()[:20]+'.json')
    fd,temp=tempfile.mkstemp(dir=folder,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:json.dump(data,out,indent=2,ensure_ascii=False)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return path


def presets(folder=None,errors=None):
    result=[]
    for path in sorted(Path(folder or FOLDER).glob('*.json')):
        try:
            raw=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(raw,dict) or raw.get('format')!='profile-studio-report' or raw.get('version') not in (1,2):raise ValueError('Invalid report preset format.')
            if not isinstance(raw.get('name'),str) or not raw['name'].strip():raise ValueError('Missing preset name.')
            result.append(dict(name=raw['name'],settings=settings(raw['settings'])))
        except (ValueError,TypeError,KeyError,OSError) as exc:
            if errors is not None:errors.append(path.name+': '+str(exc))
    return sorted(result,key=lambda p:p['name'].casefold())


def delete_preset(name,folder=None):
    from configuration_trash import remove_saved
    return remove_saved(name,folder or FOLDER,'profile-studio-report')


def request_for_preset(name,folder=None,loaded=None):
    preset=next((p for p in presets(folder) if p['name']==name),None)
    if preset is None:raise ValueError('Choose a saved PDF preset.')
    request=deepcopy(preset['settings'])
    if loaded is not None:
        if request['date_mode']=='loaded':request.update(first=str(loaded['first']),last=str(loaded['last']))
        from report_stats import report_range
        report_range(request,loaded)
    request['config']=request.get('viewer',{})
    return request
