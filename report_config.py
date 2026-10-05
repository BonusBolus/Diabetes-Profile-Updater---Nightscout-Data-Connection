"""PDF export presets, deliberately separate from graph configurations."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import date

FOLDER=Path(__file__).resolve().parent/'report_configurations'
SECTIONS=('overview','profiles','median','statistics','daily','overlay','distribution')


def settings(raw):
    if not isinstance(raw,dict):raise ValueError('Invalid report settings.')
    layout=raw.get('layout','landscape');count=raw.get('graphs_per_page',2)
    if layout not in ('portrait','landscape'):raise ValueError('Choose portrait or landscape.')
    if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=6:raise ValueError('Choose 1–6 graphs per page.')
    selected=raw.get('sections',[])
    if not isinstance(selected,list) or any(s not in SECTIONS for s in selected):raise ValueError('Invalid report sections.')
    result=dict(layout=layout,graphs_per_page=count,sections=selected,title=str(raw.get('title','Profile Studio report'))[:120])
    for key in ('first','last'):
        if raw.get(key):result[key]=date.fromisoformat(raw[key]).isoformat()
    from report_stats import time_minute
    for key,default in [('from_time','00:00'),('until_time','24:00')]:
        value=raw.get(key,default);time_minute(value);result[key]=value
    return result


def save_preset(name,raw,folder=None):
    if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('Enter a report preset name of 1–80 characters.')
    name=name.strip();data=dict(format='profile-studio-report',version=1,name=name,settings=settings(raw))
    folder=Path(folder or FOLDER);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(hashlib.sha256(name.casefold().encode()).hexdigest()[:20]+'.json')
    fd,temp=tempfile.mkstemp(dir=folder,suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:json.dump(data,out,indent=2,ensure_ascii=False)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return path


def presets(folder=None):
    result=[]
    for path in sorted(Path(folder or FOLDER).glob('*.json')):
        raw=json.loads(path.read_text(encoding='utf-8'))
        if raw.get('format')!='profile-studio-report' or raw.get('version')!=1:raise ValueError('Invalid report preset: '+path.name)
        result.append(dict(name=raw['name'],settings=settings(raw['settings'])))
    return sorted(result,key=lambda p:p['name'].casefold())
