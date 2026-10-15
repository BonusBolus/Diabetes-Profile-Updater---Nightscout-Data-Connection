"""Recoverable removal of saved settings; health records are never touched."""
import json
from pathlib import Path
from uuid import uuid4


def remove_saved(name, folder, format_name):
    if not isinstance(name,str) or not name.strip():raise ValueError('Choose saved settings to delete.')
    folder=Path(folder)
    matches=[]
    for path in folder.glob('*.json'):
        try:raw=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError):continue
        if isinstance(raw,dict) and raw.get('format')==format_name and raw.get('name')==name:matches.append(path)
    if not matches:raise ValueError('These saved settings no longer exist. Refresh the list.')
    trash=folder/'.trash';trash.mkdir(parents=True,exist_ok=True)
    for path in matches:path.rename(trash/(uuid4().hex+'-'+path.name))
    return len(matches)
