"""Clickable loaded-day calendar; selecting dates never performs a fetch."""
import calendar
from datetime import date, timedelta

import streamlit as st


def loaded_days(loaded):
    days = [loaded['first'] + timedelta(days=i)
            for i in range((loaded['last'] - loaded['first']).days + 1)]
    return [d for d in days if loaded['day_sources'].get(d)] if 'day_sources' in loaded else days


def select_day(day, multiple):
    st.session_state.health_date_revision=st.session_state.get("health_date_revision",0)+1
    if multiple:
        selected = set(st.session_state.get('ns_days', []))
        selected.symmetric_difference_update([day])
        st.session_state.ns_days = sorted(selected)
    else:
        st.session_state.ns_day = day


def select_days(days):
    st.session_state.health_date_revision=st.session_state.get("health_date_revision",0)+1
    st.session_state.ns_days = list(days)


def day_calendar(loaded, multiple=False):
    available = loaded_days(loaded)
    if not available:
        st.caption('No recorded dates available. Load another date range.');return []
    allowed = set(available)
    if st.session_state.get('ns_day') not in allowed:
        st.session_state.ns_day = available[-1]
    if 'ns_days' not in st.session_state:
        st.session_state.ns_days = available
    else:
        st.session_state.ns_days = sorted(set(st.session_state.ns_days) & allowed)
    selected = set(st.session_state.ns_days if multiple else [st.session_state.ns_day])
    st.markdown('**Days to display**' if multiple else '**Day to display**')
    st.caption('Colored = selected · enabled = loaded · gray = outside loaded range. Selection does not refresh data. G = Garmin records.')
    with st.container(key='ns_calendar'):
        st.markdown('''<style>
.st-key-ns_calendar [data-testid="stHorizontalBlock"] {gap:3px;}
.st-key-ns_calendar button {padding:2px;min-height:30px;}
.st-key-ns_calendar [data-testid="stMarkdownContainer"] p {text-align:center;}
</style>''', unsafe_allow_html=True)
        if multiple:
            left, right = st.columns(2)
            left.button('All loaded',key='ns_all_days',on_click=select_days,args=(available,),width='stretch')
            right.button('Clear',key='ns_clear_days',on_click=select_days,args=([],),width='stretch')
        months = sorted({(day.year, day.month) for day in available})
        for year, month in months:
            st.markdown(f'**{calendar.month_name[month]} {year}**')
            for column, label in zip(st.columns(7), ['M','T','W','T','F','S','S']):
                column.caption(label)
            for week in calendar.Calendar().monthdayscalendar(year, month):
                for column, number in zip(st.columns(7), week):
                    if not number:
                        column.empty()
                        continue
                    day = date(year, month, number)
                    column.button(str(number)+(' · G' if 'Garmin records' in loaded.get('day_sources',{}).get(day,[]) else ''),key=f'ns_calendar_{day}',disabled=day not in allowed,
                        type='primary' if day in selected else 'secondary',width='stretch',
                        help=f'{day} · '+(', '.join(loaded['day_sources'].get(day,[])) or 'No Garmin records' if 'day_sources' in loaded and day in allowed else 'Loaded (records may contain gaps)' if day in allowed else 'Not loaded'),
                        on_click=select_day,args=(day,multiple))
    return sorted(selected)
