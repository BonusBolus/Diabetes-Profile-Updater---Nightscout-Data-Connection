"""Independent session-owned imports; worker threads never call Streamlit."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import streamlit as st

_POOL=ThreadPoolExecutor(max_workers=4,thread_name_prefix='health-import')
SOURCES={'nightscout':('Nightscout','ns_loaded'),'garmin':('Garmin','garmin_loaded')}


class SourceLoad:
    def __init__(self):
        self.lock=Lock();self.progress=(0,1,'Starting…');self.future=None;self.applied=False;self.error=None

    def update(self,n,total,label):
        with self.lock:self.progress=(n,total,str(label))

    def status(self):
        with self.lock:return self.progress


def loading(source,state=None):
    state=st.session_state if state is None else state
    job=state.get('_source_load_jobs',{}).get(source)
    return bool(job and not job.applied)


def start_load(source,loader,*args,state=None,**kwargs):
    state=st.session_state if state is None else state
    jobs=state.setdefault('_source_load_jobs',{})
    if loading(source,state):return False
    job=SourceLoad();jobs[source]=job
    job.future=_POOL.submit(loader,*args,progress=job.update,**kwargs)
    return True


def collect_loads(state=None):
    state=st.session_state if state is None else state
    changed=False
    for source,job in state.get('_source_load_jobs',{}).items():
        if job.applied or not job.future.done():continue
        try:state[SOURCES[source][1]]=job.future.result()
        except Exception as exc:job.error=str(exc) or type(exc).__name__
        job.applied=True;job.future=None;changed=True
    return changed


def _loading_status():
    changed=collect_loads()
    for source,job in st.session_state.get('_source_load_jobs',{}).items():
        label,key=SOURCES[source]
        if not job.applied:
            n,total,text=job.status();st.progress(min(1.,max(0.,n/max(1,total))),text=label+' · '+text)
        elif job.error:
            st.error(label+' load failed: '+job.error)
            if st.session_state.get(key) is not None:st.caption('Previously loaded '+label+' data is still available.')
        else:st.caption(label+' import finished.')
    if changed:st.rerun()


def loading_status():
    # Stop polling after the completion rerun; no idle background app reruns.
    st.fragment(run_every=.5 if any(loading(key) for key in SOURCES) else None)(_loading_status)()
