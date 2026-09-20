"""Manual connection controls; credentials and loaded records stay in session memory."""
from datetime import datetime, timedelta
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from nightscout import NightscoutError, available_days, load_nightscout
from nightscout_charts import LAYERS, OVERLAYS, OVERLAY_CHOICES, date_label

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _select_single_day(day):
    st.session_state.ns_day = day


def _toggle_selected_day(day):
    selected = set(st.session_state.get("ns_days", []))
    if day in selected:
        if len(selected) > 1:
            selected.discard(day)
    else:
        selected.add(day)
    st.session_state.ns_days = sorted(selected)


def calendar_picker(days, mode, available):
    """A clickable Mon–Sun calendar grid; dots mark days with recorded data."""
    days_set = set(days)
    start = days[0] - timedelta(days=days[0].weekday())
    end = days[-1] + timedelta(days=6 - days[-1].weekday())
    grid = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    for col, label in zip(st.columns(7), WEEKDAYS):
        col.markdown(f"<div style='text-align:center;font-size:11px;opacity:.6;font-weight:600'>{label}</div>",
                     unsafe_allow_html=True)
    if mode == "One day":
        current = st.session_state.get("ns_day", days[-1])
        if current not in days_set:
            current = days[-1]
    else:
        current = set(st.session_state.get("ns_days", days)) & days_set or days_set
    for week_start in range(0, len(grid), 7):
        for col, day in zip(st.columns(7), grid[week_start:week_start + 7]):
            if day not in days_set:
                col.markdown("&nbsp;")
                continue
            has_data = day in available
            selected = day == current if mode == "One day" else day in current
            label = f"{day.day} ·" if has_data else str(day.day)
            help_text = day.isoformat() + (" · has recorded data" if has_data else " · no recorded data")
            if mode == "One day":
                col.button(label, key=f"ns_cal_{day.isoformat()}", width="stretch", help=help_text,
                          type="primary" if selected else "secondary", on_click=_select_single_day, args=(day,))
            else:
                col.button(label, key=f"ns_cal_{day.isoformat()}", width="stretch", help=help_text,
                          type="primary" if selected else "secondary", on_click=_toggle_selected_day, args=(day,))
    if mode != "One day":
        if st.button("Select all days", key="ns_cal_select_all", width="stretch"):
            st.session_state.ns_days = list(days)
            st.rerun()
        st.caption("· marks a day with recorded Nightscout data.")
    if mode == "One day":
        return [st.session_state.get("ns_day", days[-1]) if st.session_state.get("ns_day", days[-1]) in days_set else days[-1]]
    return sorted(set(st.session_state.get("ns_days", days)) & days_set) or list(days)


def sidebar_controls(profile_zone):
    with st.expander("Nightscout data"):
        st.caption("Read-only connection. Enter a readable access token here, not in chat.")
        try:
            today = datetime.now(ZoneInfo(profile_zone)).date()
        except (ValueError, ZoneInfoNotFoundError):
            st.info("Enter a valid profile timezone before loading Nightscout.")
            return None
        with st.form("nightscout_connection"):
            url = st.text_input("Nightscout site URL", value=os.environ.get("NIGHTSCOUT_URL", ""),
                                placeholder="https://your-nightscout.example", key="ns_url")
            token = st.text_input("Read-only access token", value=os.environ.get("NIGHTSCOUT_TOKEN", ""),
                                  type="password", key="ns_token")
            first = st.date_input("From date", today-timedelta(days=6), key="ns_from")
            last = st.date_input("Through date", today, key="ns_until")
            st.caption("Dates use your profile timezone: " + profile_zone + ". Up to 31 days per load.")
            load = st.form_submit_button("Load / refresh data")
        if load:
            st.session_state.pop("ns_loaded", None)
            try:
                with st.spinner("Loading Nightscout records…"):
                    st.session_state.ns_loaded = load_nightscout(url, token, first, last, profile_zone)
                st.session_state.pop("ns_day", None)
                st.session_state.pop("ns_days", None)
            except (NightscoutError, ValueError, ZoneInfoNotFoundError) as exc:
                st.error(str(exc))
        loaded = st.session_state.get("ns_loaded")
        if loaded is None:
            st.caption("Only Load / refresh data contacts Nightscout. Loaded records and credentials are not saved with profiles.")
            return None
        loaded.setdefault("_chart_cache", {})
        if st.button("Clear loaded Nightscout data"):
            del st.session_state.ns_loaded
            st.rerun()
        st.caption(f"Loaded {loaded['first']} through {loaded['last']} · {loaded['zone']}\n\n"
                   f"Updated {loaded['loaded_at'].astimezone(ZoneInfo(loaded['zone'])).strftime('%Y-%m-%d %H:%M %Z')}")
        for warning in loaded["warnings"]:
            if "effective-profile" not in warning and "effective profile" not in warning:
                st.warning(warning)
        days = [loaded["first"]+timedelta(days=i) for i in range((loaded["last"]-loaded["first"]).days+1)]
        mode = st.radio("Nightscout view", ["One day", "Multiple days", "Median + band"], key="ns_mode")
        st.caption("Days to display" if mode != "One day" else "Day to display")
        days = calendar_picker(days, mode, available_days(loaded))
        layers = st.pills("Data layers", list(LAYERS), selection_mode="multi", default=["Glucose"], key="ns_layers")
        overlay = st.session_state.get("ns_overlay", "None")
        show_targets = st.checkbox("Show temporary targets on glucose", value=True, key="ns_show_targets")
        exclude_smb = st.checkbox("Exclude SMB from bolus grid/histogram", value=False, key="ns_exclude_smb",
            help="Hide automated micro-boluses (SMB) from the bolus day×hour heatmap and its hourly "
                 "histogram. User boluses on other bolus displays are unaffected.")
        for label in set(layers):
            key = LAYERS[label]
            if (key not in loaded["data"] or loaded["data"][key].empty) and (key != "basal" or loaded["data"]["basal_percent"].empty):
                st.caption(f"No {label.lower()} records were returned for the loaded dates.")
        if mode == "Median + band":
            st.caption("Glucose, temp basal, IOB and COB: median and 25–75% band in 5-minute bins, with one contribution per day. Missing intervals stay blank. Temp basal summarizes recorded temp rates only. Bolus and carb heatmaps show hourly totals; histograms show the median hourly total across complete hours. Zero means no event returned; unavailable and future hours stay blank.")
        st.caption("Only temporary-target events are drawn; scheduled profile targets are hidden. Reason colors: Eating Soon orange, Activity cyan, Hypo red, other/missing green. The 4–10 band is a fixed guide.")
        st.caption("Temporary basal shows recorded intervals, not a reconstructed delivery total. Gaps are not filled with your draft basal. IOB/COB are uploaded values.")
        st.caption("Select historical days manually; they are not automatically matched to profile versions. Editing your profile never changes the recorded data.")
        return {"loaded": loaded, "days": sorted(days), "mode": mode, "layers": layers, "overlay": overlay,
                "show_targets": show_targets, "exclude_smb": exclude_smb}


def cycle_day(direction):
    loaded = st.session_state.ns_loaded
    dates = [loaded["first"] + timedelta(days=i) for i in range((loaded["last"]-loaded["first"]).days+1)]
    current = st.session_state.get("ns_day", dates[-1])
    if st.session_state.get("ns_mode") != "One day":
        selected = st.session_state.get("ns_days", dates)
        if selected:
            current = max(selected) if direction > 0 else min(selected)
    index = dates.index(current) if current in dates else 0
    st.session_state.ns_day = dates[(index+direction) % len(dates)]
    st.session_state.ns_mode = "One day"


def sync_graph_option(metric, field):
    value = st.session_state[f"{field}_{metric}"]
    st.session_state[field] = value
    for other in ('ic','isf','basal','target'):
        st.session_state[f"{field}_{other}"] = value


def graph_date_controls(view, metric):
    overlay_col, scale_col, date_col, previous_col, next_col = st.columns([2.3,1.6,2.2,1.2,1.2],vertical_alignment="bottom")
    choices = OVERLAY_CHOICES
    old_overlay = st.session_state.get("ns_overlay", "None")
    migrated = {"IOB":"IOB + boluses", "Boluses":"IOB + boluses", "COB":"COB + carbs", "Carbs":"COB + carbs"}.get(old_overlay, old_overlay)
    if migrated != old_overlay:
        st.session_state.ns_overlay = migrated
        for key in ("ic", "isf", "basal", "target"):
            st.session_state[f"ns_overlay_{key}"] = migrated
    overlay = overlay_col.selectbox("Overlay · right axis", choices,
        format_func=lambda option: "Temp targets" if option == "Nightscout targets" else option,
        index=choices.index(st.session_state.get('ns_overlay','None')),key=f"ns_overlay_{metric}",
        on_change=sync_graph_option,args=(metric,'ns_overlay'))
    same_scale = scale_col.toggle("Same axis scale", value=st.session_state.get('ns_same_scale',False),
        key=f"ns_same_scale_{metric}",disabled=overlay=='None',on_change=sync_graph_option,args=(metric,'ns_same_scale'),
        help="Use identical numeric limits on both axes. This does not convert units or make different quantities equivalent.")
    date_col.caption(date_label(view['days']) + " · " + view['loaded']['zone'])
    disabled = view['loaded']['first'] == view['loaded']['last'] and view['mode'] == 'One day'
    previous_col.button("← Previous",key=f"ns_previous_{metric}",on_click=cycle_day,args=(-1,),disabled=disabled,
        help="Previous loaded day; switches to One day view and wraps at the ends.",width="stretch")
    next_col.button("Next →",key=f"ns_next_{metric}",on_click=cycle_day,args=(1,),disabled=disabled,
        help="Next loaded day; switches to One day view and wraps at the ends.",width="stretch")
    return dict(view,overlay=overlay,same_scale=same_scale and overlay!='None')
