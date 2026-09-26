"""Manual connection controls; credentials and loaded records stay in session memory."""
from datetime import datetime, timedelta
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from nightscout import NightscoutError, load_nightscout
from date_controls import day_calendar
from nightscout_charts import LAYERS, GROUP_KEYS, date_label


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
            st.warning(warning)
        mode = st.radio("Nightscout view", ["One day", "Multiple days", "Median + band"], key="ns_mode")
        days = day_calendar(loaded, multiple=mode != "One day")
        # Drop removed chart selections before creating the widget on a live reload.
        if 'ns_layers' in st.session_state:
            previous=st.session_state.ns_layers or []
            renamed={'IOB':'IOB + boluses','Boluses':'IOB + boluses','COB':'COB + carbs','Carbs':'COB + carbs'}
            migrated=[renamed.get(label,label) for label in previous]
            migrated=list(dict.fromkeys(label for label in migrated if label in LAYERS))
            if migrated!=previous:st.session_state.ns_layers=migrated
        layers = st.pills("Data layers", list(LAYERS), selection_mode="multi", default=["Glucose"], key="ns_layers")
        if "Custom graph" in layers:
            st.caption("Choose recorded data and profile schedules directly above the Custom graph, including in expanded view. Schedules use the current draft and selected references; they are not historical active-profile records.")
        overlay = "None"
        show_targets = True  # Controlled locally on the graph, including fullscreen.
        for label in set(layers):
            key = LAYERS[label]
            if key == 'custom':continue
            if all(k not in loaded["data"] or loaded["data"][k].empty for k in GROUP_KEYS.get(key, [key])) and (key != "basal" or loaded["data"]["basal_percent"].empty):
                st.caption(f"No {label.lower()} records were returned for the loaded dates.")
        if mode == "Median + band":
            st.caption("Glucose, temp basal, IOB and COB: median and 25–75% band in 5-minute bins, with one contribution per day. Missing intervals stay blank. Temp basal summarizes recorded temp rates only. Bolus and carb heatmaps show hourly totals; bar plots default to the average hourly total across complete hours, with an in-graph Median toggle. Zero means no event returned; unavailable and future hours stay blank.")
        st.caption("Temporary targets use rectangular shading toward the historical profile target range. Missing target history: line only. Reason colors: Eating Soon orange, Activity cyan, Hypo red, other/missing green. The 4–10 band is a fixed guide.")
        if 'Variable sensitivity' in layers:
            st.caption("Variable sensitivity is the uploaded variable_sens, not the scheduled ISF. Values are displayed in the profile's glucose units per U. Missing fields stay blank.")
        st.caption("Temporary basal shows recorded intervals, not a reconstructed delivery total. Gaps are not filled with your draft basal. IOB/COB are uploaded values.")
        st.caption("Select historical days manually; they are not automatically matched to profile versions. Editing your profile never changes the recorded data.")
        return {"loaded": loaded, "days": sorted(days), "mode": mode, "layers": layers, "overlay": overlay, "show_targets": show_targets}



def graph_date_controls(view, metric):
    # All graph controls live in one viewer, also used in fullscreen. Streamlit
    # controls here previously disagreed with the locally selected overlay.
    st.caption(date_label(view['days']) + ' · ' + view['loaded']['zone'] +
               ' · Dashed vertical lines mark changes in the selected profile setting.')
    return dict(view, overlay='None', same_scale=False)
