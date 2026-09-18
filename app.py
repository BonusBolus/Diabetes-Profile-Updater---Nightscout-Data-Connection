"""Run with: python -m streamlit run app.py"""
from copy import deepcopy
from datetime import date
from io import BytesIO
import json
import os
from pathlib import Path
import zipfile

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from appearance import COLORS, LIGHT_COLORS, palette, reference_color, sync_native_theme
from comparison_tables import comparison_table, styled_comparison
from editor_history import record_edit, reset_history, restore_edit
from nightscout_charts import graph_figures
from graph_view import render_graphs, navigation_bundle
from nightscout_ui import sidebar_controls, graph_date_controls

from profiles import (METRICS, adjust_range, clock, daily_basal, differences,
                      excel_sheets, export_excel, import_excel, load_profiles, minute,
                      next_version, normalize_schedule, overwrite_profile, profile_changes,
                      save_profile, validate_link, validate_profile)

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("PROFILE_STUDIO_DATA", ROOT / "data" / "profiles"))
st.set_page_config(page_title="Profile Studio", page_icon="◷", layout="wide")
dark = st.session_state.get("dark_mode", st.get_option("theme.base") == "dark")
theme = palette(dark)
metric_colors = COLORS if dark else LIGHT_COLORS
st.markdown("""<style>
.block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1500px;}
div[data-testid="stMetric"] {background:var(--secondary-background-color); border:1px solid #80808040;
    padding:14px 18px; border-radius:10px;}
h1 {letter-spacing:-.04em;} h3 {letter-spacing:-.02em;}
</style>""", unsafe_allow_html=True)
st.markdown("<style>" + "".join(
    f'[data-testid="stTabs"] [role="tab"]:nth-child({index}) {{color:{metric_colors[metric]};}}'
    for index, metric in enumerate(METRICS, 2)) + "</style>", unsafe_allow_html=True)


def fingerprint(profile):
    return json.dumps(profile, sort_keys=True, default=str)


def start_draft(source, profiles, *, imported=False, editing=False):
    draft = deepcopy(source)
    st.session_state.editing_original = deepcopy(source) if editing else None
    if not editing:
        draft["parent_id"] = None if imported else source.get("id")
    for field in ("id", "version", "created_at", "updated_at", "comparison_id", "second_comparison_id"):
        draft.pop(field, None)
    if not imported and not editing:
        draft["name"] = f"{draft['category']} v{next_version(profiles, draft['category'])}"
        draft["effective_date"] = None
        draft["notes"] = ""
    draft["version"] = next_version(profiles, draft["category"])
    st.session_state.version_category = draft["category"].casefold()
    st.session_state.draft = draft
    st.session_state.initial = fingerprint(draft)
    st.session_state.saved_fingerprint = None
    st.session_state.epoch = st.session_state.get("epoch", 0) + 1
    st.session_state.seeds = deepcopy(draft["schedules"])
    st.session_state.raw_schedules = deepcopy(draft["schedules"])
    st.session_state.invalid_edits = False
    st.session_state.revisions = {key: 0 for key in METRICS}
    st.session_state.extra_seed = [
        {"Field": k, "Type": "Number" if isinstance(v, (float, int)) and not isinstance(v, bool) else "Text", "Value": str(v)}
        for k,v in draft["overview"].get("extra", {}).items()]
    st.session_state.raw_extra = deepcopy(st.session_state.extra_seed)
    st.session_state.review_baseline = deepcopy(source)
    reset_history(st.session_state)


def unit_for(metric, profile):
    unit = profile["overview"]["glucose_unit"]
    return {"ic": "g/U", "isf": f"{unit}/U", "basal": "U/h", "target": unit}[metric]


def profile_label(profile):
    return f"{profile['category']} v{profile['version']}"


def compare_linked(profile):
    # Widget callbacks run before the sidebar renders on the next run.
    if st.session_state.get("page") == "View":
        st.session_state.page = "Compare"
    st.session_state.compare_second = True
    st.session_state.second_reference_category = profile["category"]
    st.session_state.second_reference_id = profile["id"]


def excel_download(profile, label, key):
    st.download_button(label, export_excel(profile, ROOT / "examples" / "profile-import.xlsx"),
                       file_name=f"profile-v{profile['version']}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=key)


def comparison_figure(rows, references, metric, unit, primary_label="Draft", effective_date=None, primary_name=None):
    fig = go.Figure()
    fields = ("low", "high") if metric == "target" else ("value",)
    series = [(profile["name"], profile["schedules"][metric], reference_color(metric_colors[metric], 1 if dash == "dot" else index), dash, False)
              for index, (_, profile, _, dash) in enumerate(references)]
    name = primary_name or st.session_state.get("draft", {}).get("name", primary_label)
    series.append((name, rows, metric_colors[metric], "solid", True))
    for index, (label, values, color, dash, primary) in enumerate(series):
        xs = [minute(row["time"]) for row in values] + [1440]
        for field in fields:
            ys = [row[field] for row in values] + [values[-1][field]]
            suffix = f" · {field}" if metric == "target" else ""
            legend_entry = metric != "target" or field == "high"
            fig.add_trace(go.Scatter(x=xs, y=ys, name=label, mode="lines",
                legendgroup=f"profile-{index}", showlegend=legend_entry,
                line=dict(color=color, width=3 if primary else 2, dash=dash, shape="hv"),
                customdata=[clock(x) for x in xs], meta=dict(label=label+suffix,unit=unit,kind="profile",legend_entry=legend_entry),
                hovertemplate="%{customdata}<br>%{y:.4g} "+unit+"<extra>%{fullData.name}</extra>"))
    effective = effective_date if primary_label != "Draft" else st.session_state.get("draft", {}).get("effective_date")
    date_text = "Effective: " + effective if effective else "Viewed: " + date.today().isoformat() + " · effective date not set"
    fig.update_layout(title=dict(text=METRICS[metric]+" · "+date_text, font=dict(size=16)),
        height=350, margin=dict(l=12,r=12,t=58,b=15),
        template="plotly_dark" if dark else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=theme["surface"], font=dict(color=theme["text"],size=14),
        legend=dict(orientation="h", y=-0.24, font=dict(size=13)), hovermode="x unified",
        xaxis=dict(range=[0,1440], tickvals=list(range(0,1441,240)), ticktext=[clock(x) for x in range(0,1441,240)],
                   title="Time of day", gridcolor=theme["grid"]),
        yaxis=dict(title=unit, gridcolor=theme["grid"], rangemode="tozero" if metric == "basal" else "normal"), uirevision=metric)
    return fig


profiles, load_errors = load_profiles(DATA)
for error in load_errors:
    st.error("History file could not be read: " + error)
by_id = {p["id"]:p for p in profiles}
categories = sorted({p["category"] for p in profiles}, key=str.casefold)
if "draft" not in st.session_state and profiles:
    start_draft(max(profiles, key=lambda p:p["created_at"]), profiles)
if "draft" in st.session_state and "last_edit" not in st.session_state:
    st.session_state.review_baseline = deepcopy(st.session_state.get("editing_original") or st.session_state.draft)
    reset_history(st.session_state)

# Retain hidden reference selectors when changing workspace modes.
for state_key in ('compare_second','second_reference_category','second_reference_id'):
    if state_key in st.session_state:
        st.session_state[state_key] = st.session_state[state_key]

with st.sidebar:
    st.title("Profile Studio")
    st.caption("Build: Nightscout-6")
    st.caption("Create · compare · keep your history")
    st.toggle("Dark mode", value=dark, key="dark_mode")
    if st.session_state.pop("open_editor", False):
        st.session_state.page = "Editor"
        st.session_state.show_history = False
    page = st.radio("Workspace", ["View", "Compare", "Editor"], index=2,
        format_func=lambda item: {"View":"View one profile", "Compare":"Compare two profiles", "Editor":"Edit draft"}[item], key="page")
    show_history = st.checkbox("Browse history / export", key="show_history")
    if show_history:
        page = "History"
    st.divider()
    st.subheader("Selected profile" if page == "View" else "Profile 1" if page == "Compare" else "Reference 1")
    reference = None
    second_reference = None
    if profiles:
        category = st.selectbox("Reference category", categories, key="reference_category")
        candidates = sorted([p for p in profiles if p["category"]==category], key=lambda p:p["version"], reverse=True)
        if st.session_state.get("reference_id") not in [p["id"] for p in candidates]:
            st.session_state.reference_id = candidates[0]["id"]
        reference_id = st.selectbox("Reference version", [p["id"] for p in candidates],
            format_func=lambda key:f"v{by_id[key]['version']} · {by_id[key]['name']}", key="reference_id")
        reference = by_id[reference_id]
        linked_id = reference.get("linked_profile_id")
        if linked_id in by_id and linked_id != reference_id:
            st.caption("Corresponding profile: " + profile_label(by_id[linked_id]))
            st.button("Compare linked profile", on_click=compare_linked, args=(by_id[linked_id],))
        elif linked_id:
            st.caption("The corresponding profile is unavailable in this history.")
        compare_second = (page == "Compare") or (st.checkbox("Compare with a second profile", key="compare_second", disabled=len(profiles)<2) if page == "Editor" else False)
        if compare_second and len(profiles) >= 2:
            st.subheader("Reference 2")
            other_profiles = [p for p in profiles if p["id"] != reference_id]
            other_categories = sorted({p["category"] for p in other_profiles}, key=str.casefold)
            if st.session_state.get("second_reference_category") not in other_categories:
                st.session_state.second_reference_category = next(
                    (c for c in other_categories if c.casefold()=="standard"), other_categories[0])
            second_category = st.selectbox("Second reference category", other_categories, key="second_reference_category")
            second_candidates = sorted([p for p in other_profiles if p["category"]==second_category],
                                       key=lambda p:p["version"], reverse=True)
            if st.session_state.get("second_reference_id") not in [p["id"] for p in second_candidates]:
                st.session_state.second_reference_id = second_candidates[0]["id"]
            second_id = st.selectbox("Second reference version", [p["id"] for p in second_candidates],
                format_func=lambda key:f"v{by_id[key]['version']} · {by_id[key]['name']}", key="second_reference_id")
            second_reference = by_id[second_id]
        if page == "Editor":
            st.caption("Changing references keeps your draft intact. Copying starts a new draft from Reference 1.")
    else:
        st.info("Import an Excel or JSON profile to begin.")
    with st.expander("Create or load a draft", expanded=page == "Editor"):
        draft_now = st.session_state.get("draft")
        dirty = draft_now is not None and (fingerprint(draft_now) != st.session_state.get("initial") or st.session_state.get("invalid_edits",False))
        replace_ok = not dirty
        if dirty:
            replace_ok = st.checkbox("Discard my unsaved draft when loading another profile", key=f"discard_{st.session_state.epoch}")
        if reference and st.button("Copy reference to a new draft", disabled=not replace_ok, width="stretch"):
            start_draft(reference, profiles)
            st.session_state.open_editor = True
            st.rerun()
        if reference and st.button("Edit existing profile", disabled=not replace_ok, width="stretch"):
            start_draft(reference, profiles, editing=True)
            st.session_state.open_editor = True
            st.rerun()
        with st.expander("Import Excel or JSON"):
            st.download_button("Download Excel template", (ROOT / "examples" / "profile-import.xlsx").read_bytes(),
                               "Profile-Import.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            uploaded = st.file_uploader("Choose a profile", type=["xlsx", "json"], key="upload")
            if uploaded:
                try:
                    content = uploaded.getvalue()
                    is_excel = uploaded.name.lower().endswith(".xlsx")
                    if is_excel:
                        sheet = st.selectbox("Worksheet to import", excel_sheets(content), key="import_sheet")
                    if st.button("Import selected worksheet" if is_excel else "Import JSON profile", disabled=not replace_ok):
                        incoming = import_excel(content, sheet) if is_excel else validate_profile(json.loads(content))
                        incoming.setdefault("source", {})["filename"] = uploaded.name
                        start_draft(incoming, profiles, imported=True)
                        st.session_state.open_editor = True
                        st.session_state.notice = f"Imported {incoming['name']} as a draft. Review it, then save when ready."
                        st.rerun()
                except (ValueError, TypeError, KeyError, OSError, zipfile.BadZipFile) as exc:
                    st.error(str(exc))
            st.caption("Import is manual, one worksheet at a time. Category comes from the file and can be edited in Overview. Nothing is saved until you click Save as new version.")
    st.divider()
    nightscout_view = sidebar_controls((reference if page in ("View", "Compare") and reference else st.session_state.get("draft", {})).get("overview", {}).get("timezone", "UTC"))
    st.caption("Changes remain in this browser session until saved. Save or download your draft before closing or refreshing.")


references = []
if reference:
    references.append((f"Reference 1 · {profile_label(reference)} · {reference['name']}", reference, "#8394a8", "dash"))
if second_reference:
    references.append((f"Reference 2 · {profile_label(second_reference)} · {second_reference['name']}", second_reference, "#a65d12", "dot"))

if page in ("View", "Compare"):
    # Preserve table widget edits when leaving the draft workspace.
    if "draft" in st.session_state:
        st.session_state.seeds = deepcopy(st.session_state.raw_schedules)
        st.session_state.extra_seed = deepcopy(st.session_state.raw_extra)
    st.title("View one profile" if page == "View" else "Compare two saved profiles")
    if not reference:
        st.info("Import a profile to begin.")
        sync_native_theme(dark)
        st.stop()
    primary_label = f"Profile 1 · {profile_label(reference)} · {reference['name']}" if page == "Compare" else f"{profile_label(reference)} · {reference['name']}"
    st.subheader(primary_label)
    readonly_refs = [(f"Profile 2 · {profile_label(second_reference)} · {second_reference['name']}", second_reference, "", "dash")] if page == "Compare" and second_reference else []
    if page == "Compare" and not readonly_refs:
        st.info("Save or import a second profile to compare two saved versions.")
    readonly_tabs = st.tabs(["Overview", "I:C", "ISF", "Basal", "Target"])
    with readonly_tabs[0]:
        inspected = [(primary_label, reference)] + [(label, profile) for label, profile, *_ in readonly_refs]
        details = {label: pd.Series({"Category": profile['category'], "Version":str(profile['version']), "Name":profile['name'],
            "Effective date":profile.get('effective_date') or 'Not set', "DIA (hours)":str(profile['overview']['dia_hours']),
            "Timezone":profile['overview']['timezone'], "Glucose unit":profile['overview']['glucose_unit'],
            "Notes":profile.get('notes',''), **{k:str(v) for k,v in profile['overview'].get('extra',{}).items()}}) for label, profile in inspected}
        st.dataframe(pd.DataFrame(details).fillna('').rename_axis('Field').reset_index(),hide_index=True,width='stretch')
        st.download_button("Download selected profile JSON", json.dumps(reference,indent=2),f"profile-v{reference['version']}.json","application/json")
        excel_download(reference,"Download selected profile Excel","readonly_excel")
    if nightscout_view and (not nightscout_view['days'] or nightscout_view['loaded']['zone'] != reference['overview']['timezone']):
        st.info("Select recorded days and reload Nightscout if the selected profile uses another timezone.")
        nightscout_view = None
    for tab, metric in zip(readonly_tabs[1:], METRICS):
        with tab:
            compatible = [item for item in readonly_refs if metric in ('ic','basal') or item[1]['overview']['glucose_unit'] == reference['overview']['glucose_unit']]
            if len(compatible) != len(readonly_refs):
                st.warning("Different glucose units: Profile 2 is hidden for this metric.")
            frame, mask = comparison_table(reference['schedules'][metric], compatible, metric, primary_label)
            st.dataframe(styled_comparison(frame, mask, dark), hide_index=True, width='stretch')
            fig = comparison_figure(reference['schedules'][metric], compatible, metric, unit_for(metric,reference), primary_label, reference.get('effective_date'), primary_name=reference['name'])
            if nightscout_view:
                view = graph_date_controls(nightscout_view, metric)
                render_graphs(graph_figures(fig, **view, unit=reference['overview']['glucose_unit'],dark=dark),dark,
                              navigation_bundle(fig,view,reference['overview']['glucose_unit'],dark))
            else:
                st.plotly_chart(fig,width='stretch',key=f'readonly_plot_{metric}')
    sync_native_theme(dark)
    st.stop()

if page == "History":
    # Streamlit removes widgets that are not rendered. Keep their latest table
    # contents, including incomplete rows, to restore the editor on return.
    if "draft" in st.session_state:
        st.session_state.seeds = deepcopy(st.session_state.raw_schedules)
        st.session_state.extra_seed = deepcopy(st.session_state.raw_extra)
    st.title("Profile history")
    st.caption("Saved versions, grouped by category. Select the reference in the sidebar to inspect it.")
    if not profiles:
        st.info("No saved profiles yet.")
        sync_native_theme(dark)
        st.stop()
    selected_category = st.selectbox("Category", categories, key="history_category")
    selected = sorted([p for p in profiles if p["category"] == selected_category], key=lambda p:p["version"])
    records = [{"Version":p["version"], "Name":p["name"], "Effective date":p.get("effective_date") or "",
        "Saved (UTC)":p["created_at"][:19].replace("T"," "),
        "Updated (UTC)":p.get("updated_at", "")[:19].replace("T", " "), "Basal (U/day)":daily_basal(p["schedules"]["basal"]),
        "DIA (h)":p["overview"]["dia_hours"], "Notes":p.get("notes","")} for p in selected]
    st.dataframe(pd.DataFrame(records), hide_index=True, width="stretch")
    trend_metric = st.selectbox("Trend", ["Basal (U/day)", "DIA (h)"])
    fig = go.Figure(go.Scatter(x=[r["Version"] for r in records], y=[r[trend_metric] for r in records],
        mode="lines+markers", line=dict(color=metric_colors["basal"] if trend_metric.startswith("Basal") else theme["text"]), customdata=[r["Name"] for r in records],
        hovertemplate="v%{x} · %{customdata}<br>%{y:.4g}<extra></extra>"))
    history_dates = sorted(p.get("effective_date") or p["created_at"][:10] for p in selected)
    fig.update_layout(title=dict(text=f"{selected_category} · {history_dates[0]} – {history_dates[-1]} (effective / saved dates)",font=dict(size=16)),
                      font_size=14, height=330, xaxis=dict(title="Version", dtick=1), yaxis_title=trend_metric,
                      template="plotly_dark" if dark else "plotly_white",
                      paper_bgcolor=theme["background"], plot_bgcolor=theme["surface"], font_color=theme["text"],
                      margin=dict(l=10,r=10,t=58,b=10))
    st.plotly_chart(fig, width="stretch")
    st.subheader("Selected reference")
    st.write(f"**{reference['category']} · v{reference['version']} · {reference['name']}**")
    for label, field in (("Saved reference 1", "comparison_id"), ("Saved reference 2", "second_comparison_id"),
                         ("Corresponding profile", "linked_profile_id")):
        linked_id = reference.get(field)
        if linked_id:
            st.caption(f"{label}: {profile_label(by_id[linked_id]) if linked_id in by_id else 'Profile unavailable in this history'}")
    overview = reference["overview"]
    st.write({"DIA (h)":overview["dia_hours"], "Glucose unit":overview["glucose_unit"], "Timezone":overview["timezone"], **overview.get("extra",{})})
    cols = st.columns(2)
    for i, metric in enumerate(METRICS):
        with cols[i%2]:
            st.markdown(f"**{METRICS[metric]} ({unit_for(metric, reference)})**")
            st.dataframe(reference["schedules"][metric], hide_index=True, width="stretch")
    st.download_button("Download selected profile JSON", json.dumps(reference,indent=2),
                       file_name=f"profile-v{reference['version']}.json", mime="application/json")
    excel_download(reference, "Download selected profile Excel", "excel_selected")
    st.caption("Excel includes the template's overview and schedules. JSON also preserves links, history metadata and additional overview fields.")
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for p in profiles:
            bundle.writestr(f"{p['id']}.json", json.dumps(p,indent=2,ensure_ascii=False))
    st.download_button("Download all profile history", archive.getvalue(), "profile-history.zip", "application/zip")
    sync_native_theme(dark)
    st.stop()


editing = st.session_state.get("editing_original")
st.title("Edit existing profile" if editing else "Build your next profile")
st.caption("I:C: orange · ISF: yellow · Basal: blue · Target: green. Draft: solid; references use distinct tints and dashed/dotted lines.")
if editing:
    st.info(f"Editing {profile_label(editing)} · {editing['name']}. Overwrite replaces this saved version. Changing references keeps this edit target.")
    if st.button("Cancel changes", help="Discard unsaved edits and restore this profile to when you opened or last saved it."):
        start_draft(editing, profiles, editing=True)
        st.session_state.notice = f"Unsaved changes discarded for {profile_label(editing)}. Your saved profile is unchanged."
        st.rerun()
if "draft" not in st.session_state:
    st.info("Use the sidebar to import your first profile.")
    sync_native_theme(dark)
    st.stop()
draft = st.session_state.draft
epoch = st.session_state.epoch
if st.session_state.pop("advance_version_after_save", False):
    draft["version"] = next_version(profiles, draft["category"])
    st.session_state[f"version_{epoch}_{draft['category'].strip().casefold()}"] = draft["version"]
    st.session_state.saved_fingerprint = fingerprint(draft)
    st.session_state.initial = fingerprint(draft)
    reset_history(st.session_state)
if st.session_state.get("notice"):
    st.success(st.session_state.pop("notice"))
summary = st.empty()
edit_controls = st.empty()
errors = []
tabs = st.tabs(["Overview", "I:C", "ISF", "Basal", "Target"])
with tabs[0]:
    left, right = st.columns([1.3,1], gap="large")
    with left:
        st.subheader("Draft details")
        draft["name"] = st.text_input("Profile name", draft["name"], key=f"name_{epoch}")
        draft["category"] = st.text_input("Category", draft["category"], key=f"category_{epoch}", disabled=bool(editing))
        st.caption("Category and version stay fixed when overwriting. Copy to a new draft to change category." if editing else
                   "Use an existing category name or enter a new one. " + ("Existing: " + ", ".join(categories) if categories else ""))
        version_category = draft["category"].strip().casefold()
        if st.session_state.get("version_category") != version_category:
            draft["version"] = next_version(profiles, draft["category"].strip())
            st.session_state.version_category = version_category
        draft["version"] = st.number_input("Version for new save", min_value=1,
            value=int(draft.get("version", next_version(profiles, draft["category"]))), step=1,
            key=f"version_{epoch}_{version_category}", help="Defaults to the next unused number. Choose any unused number, or explicitly confirm replacement of an existing version below.")
        if editing:
            st.caption(f"Overwrite existing profile keeps v{editing['version']}; this selector is for the separate save action.")
        a,b = st.columns(2)
        with a:
            draft["overview"]["dia_hours"] = st.number_input("DIA (hours)", min_value=0.01,
                value=float(draft["overview"]["dia_hours"]), step=0.1, key=f"dia_{epoch}")
        with b:
            effective = st.date_input("Effective date (optional)", value=date.fromisoformat(draft["effective_date"]) if draft.get("effective_date") else None, key=f"date_{epoch}")
            draft["effective_date"] = effective.isoformat() if effective else None
        draft["overview"]["timezone"] = st.text_input("Timezone", draft["overview"]["timezone"], key=f"tz_{epoch}")
        st.caption(f"Glucose unit: {draft['overview']['glucose_unit']} · I:C: g/U · Basal: U/h")
        draft["notes"] = st.text_area("Notes / reason for changes", draft.get("notes",""), key=f"notes_{epoch}")
        link_options = [None] + [p["id"] for p in profiles if not editing or p["id"] != editing["id"]]
        current_link = draft.get("linked_profile_id")
        if current_link is not None and current_link not in link_options:
            link_options.append(current_link)
        draft["linked_profile_id"] = st.selectbox("Corresponding profile", link_options,
            index=link_options.index(current_link), key=f"link_{epoch}",
            format_func=lambda key: "None" if key is None else
                f"{profile_label(by_id[key])} · {by_id[key]['name']}" if key in by_id else "Unavailable profile",
            help="For example, link a Drinking version to its corresponding Standard version. Saved with this profile.")
        linked_id = draft["linked_profile_id"]
        if linked_id in by_id:
            st.button("Compare corresponding profile", on_click=compare_linked, args=(by_id[linked_id],),
                      disabled=bool(reference and linked_id == reference["id"]),
                      help="Load this profile as Reference 2. If it is already Reference 1, no change is needed.")
    with right:
        st.subheader("Reference overview")
        if references:
            metadata = {}
            for label, profile, _, _ in references:
                metadata[label] = pd.Series({"Name":profile["name"], "Category":profile["category"],
                    "Version":str(profile["version"]), "DIA (hours)":str(profile["overview"]["dia_hours"]),
                    "Timezone":profile["overview"]["timezone"], "Glucose unit":profile["overview"]["glucose_unit"],
                    "Notes":profile.get("notes",""), **{k:str(v) for k,v in profile["overview"].get("extra",{}).items()}})
            st.dataframe(pd.DataFrame(metadata).fillna("").rename_axis("Field").reset_index(), hide_index=True, width="stretch")
        st.markdown("**Additional overview fields**")
        st.caption("Add text or numeric fields whenever you need them.")
        extra = st.data_editor(pd.DataFrame(st.session_state.extra_seed, columns=["Field","Type","Value"]),
            num_rows="dynamic", hide_index=True, width="stretch", key=f"extra_{epoch}",
            column_config={"Type":st.column_config.SelectboxColumn(options=["Text","Number"], default="Text", required=True),
                           "Field":st.column_config.TextColumn(required=True), "Value":st.column_config.TextColumn(required=True)})
        st.session_state.raw_extra = extra.to_dict("records")
        extras = {}
        try:
            for item in extra.to_dict("records"):
                name, value = item["Field"], item["Value"]
                if not isinstance(name,str) or not name.strip() or pd.isna(value):
                    raise ValueError("Complete or delete empty overview fields.")
                if name.strip() in extras:
                    raise ValueError("Additional overview field names must be unique.")
                extras[name.strip()] = float(value) if item["Type"] == "Number" else str(value)
            draft["overview"]["extra"] = extras
        except (ValueError, TypeError) as exc:
            errors.append(str(exc))
            st.error(str(exc))

for label, profile, _, _ in references:
    if profile["overview"]["glucose_unit"] != draft["overview"]["glucose_unit"]:
        st.warning(f"{label} uses different glucose units. Its ISF and target comparisons are hidden; choose a reference with matching units.")
if nightscout_view and nightscout_view["loaded"]["zone"] != draft["overview"]["timezone"]:
    st.warning("Your profile timezone changed. Reload Nightscout data to align the recorded days with this profile.")
    nightscout_view = None
if nightscout_view and not nightscout_view["days"]:
    st.info("Select at least one Nightscout day to display recorded data.")
    nightscout_view = None
for tab, metric in zip(tabs[1:], METRICS):
    with tab:
        unit = unit_for(metric,draft)
        st.markdown(f'<h3 style="color:{metric_colors[metric]}">{METRICS[metric]} schedule</h3>', unsafe_allow_html=True)
        left,right = st.columns([1,1.6], gap="large")
        revision = st.session_state.revisions[metric]
        with left:
            st.caption(f"Values in {unit}. Each value stays active until the next start time.")
            config = {"time":st.column_config.TextColumn("Start time", required=True, validate=r"(?:[01]\d|2[0-3]):[0-5]\d", help="HH:MM; first entry must be 00:00.")}
            fields = ("low","high") if metric=="target" else ("value",)
            for field in fields:
                config[field] = st.column_config.NumberColumn(field.capitalize(), required=True, min_value=0.0, format="%.4f")
            table = st.data_editor(pd.DataFrame(st.session_state.seeds[metric]), hide_index=True, num_rows="dynamic",
                width="stretch", key=f"schedule_{epoch}_{metric}_{revision}", column_config=config)
            st.session_state.raw_schedules[metric] = table.to_dict("records")
            valid = True
            try:
                rows = normalize_schedule(table.to_dict("records"), metric)
                draft["schedules"][metric] = rows
            except (ValueError, TypeError) as exc:
                valid = False
                errors.append(str(exc))
                st.error(str(exc))
            with st.expander("Adjust a time range by percentage"):
                st.caption("Applies to the current draft. Start is included; end is excluded. Target changes scale both limits.")
                with st.form(f"bulk_{epoch}_{metric}"):
                    a,b = st.columns(2)
                    start = a.text_input("From", "00:00", key=f"from_{epoch}_{metric}")
                    end = b.text_input("Until", "24:00", key=f"until_{epoch}_{metric}")
                    pct = st.number_input("Change (%)", value=0.0, step=1.0, key=f"pct_{epoch}_{metric}")
                    apply = st.form_submit_button("Apply percentage", disabled=not valid)
                if apply:
                    try:
                        record_edit(st.session_state)
                        updated = adjust_range(draft["schedules"][metric], metric, start, end, pct)
                        draft["schedules"][metric] = updated
                        st.session_state.seeds[metric] = deepcopy(updated)
                        st.session_state.raw_schedules[metric] = deepcopy(updated)
                        st.session_state.revisions[metric] += 1
                        record_edit(st.session_state)
                        st.rerun()
                    except (ValueError, TypeError) as exc:
                        st.error(str(exc))
        with right:
            matching_references = [item for item in references
                if metric in ("ic","basal") or item[1]["overview"]["glucose_unit"] == draft["overview"]["glucose_unit"]]
            if valid:
                if matching_references:
                    changes_only = st.checkbox("Show only changed intervals", value=True, key=f"changes_{metric}")
                frame, mask = comparison_table(rows, matching_references, metric)
                if matching_references and changes_only:
                    changed = mask.any(axis=1)
                    frame, mask = frame.loc[changed], mask.loc[changed]
                st.markdown("**Draft and references · " + unit + "**")
                if frame.empty:
                    st.caption("No changes to this schedule.")
                else:
                    st.dataframe(styled_comparison(frame, mask, dark), hide_index=True, width="stretch")
                    st.caption("Amber cells differ: the draft and each affected reference are highlighted. Intervals include changes from all compared schedules.")
            else:
                st.info("Complete the schedule to update its comparisons.")
        if valid:
            st.markdown("**Profile and recorded data**" if nightscout_view and nightscout_view["layers"] else "**Profile graph**")
            fig = comparison_figure(rows, matching_references, metric, unit)
            if nightscout_view:
                graph_view = graph_date_controls(nightscout_view, metric)
                figures = graph_figures(fig, **graph_view, unit=draft["overview"]["glucose_unit"], dark=dark)
                navigation = navigation_bundle(fig, graph_view, draft["overview"]["glucose_unit"], dark)
                render_graphs(figures, dark, navigation)
            else:
                st.plotly_chart(fig, width="stretch", key=f"plot_{metric}")
        else:
            st.info("Complete the schedule to update its graph.")

try:
    normalized = validate_profile(draft)
    validate_link(normalized, profiles, editing["id"] if editing else None)
except (ValueError, TypeError) as exc:
    errors.append(str(exc))
st.session_state.invalid_edits = bool(errors)
record_edit(st.session_state)
with edit_controls.container():
    undo_col, redo_col, help_col = st.columns([1, 1, 4])
    if undo_col.button("Undo", disabled=not st.session_state.undo_stack, width="stretch"):
        restore_edit(st.session_state, "undo")
        st.rerun()
    if redo_col.button("Redo", disabled=not st.session_state.redo_stack, width="stretch"):
        restore_edit(st.session_state, "redo")
        st.rerun()
    help_col.caption("Undo/redo applies to committed edits in this draft. Saving or loading a profile starts a new edit history.")
with summary.container():
    a,b,c = st.columns(3)
    if errors:
        a.metric("Daily basal", "Incomplete draft")
    else:
        total = daily_basal(draft["schedules"]["basal"])
        old = daily_basal(reference["schedules"]["basal"]) if reference else None
        a.metric("Daily basal", f"{total:.3f} U", f"{total-old:+.3f} U vs Reference 1" if old is not None else None, delta_color="off")
        if second_reference:
            second_total = daily_basal(second_reference["schedules"]["basal"])
            a.caption(f"{total-second_total:+.3f} U vs Reference 2 ({profile_label(second_reference)})")
    b.metric("DIA", f"{draft['overview']['dia_hours']:g} h",
             f"{draft['overview']['dia_hours']-reference['overview']['dia_hours']:+g} h vs Reference 1" if reference else None, delta_color="off")
    if second_reference:
        b.caption(f"{draft['overview']['dia_hours']-second_reference['overview']['dia_hours']:+g} h vs Reference 2 ({profile_label(second_reference)})")
    c.metric("Editing version" if editing else "Next saved version", f"v{editing['version'] if editing else draft['version']}")

st.divider()
with st.expander("Review changes before saving", expanded=True):
    baseline = st.session_state.review_baseline
    st.caption("Compared with " + (profile_label(baseline) + " · " + baseline["name"] if baseline.get("version") else "the imported profile") +
               ". Changing references does not change this baseline.")
    if errors:
        st.info("Complete the draft to review all changes.")
    else:
        metadata_changes, schedule_changes = profile_changes(baseline, normalized)
        for row in metadata_changes:
            for field in ("Before", "After"):
                value = row[field]
                if row["Setting"] == "Corresponding profile" and value:
                    value = profile_label(by_id[value]) if value in by_id else "Unavailable profile"
                row[field] = "—" if value is None or value == "" else str(value)
        if metadata_changes:
            st.dataframe(pd.DataFrame(metadata_changes), hide_index=True, width="stretch")
        if schedule_changes:
            st.dataframe(pd.DataFrame(schedule_changes).rename(columns={"Reference": "Before", "Draft": "After"}),
                         hide_index=True, width="stretch",
                         column_config={"Before": st.column_config.NumberColumn(format="%.6f"),
                                        "After": st.column_config.NumberColumn(format="%.6f"),
                                        "Change": st.column_config.NumberColumn(format="%+.6f"),
                                        "Change (%)": st.column_config.NumberColumn(format="%+.2f")})
            before_total, after_total = daily_basal(baseline["schedules"]["basal"]), daily_basal(normalized["schedules"]["basal"])
            st.caption(f"Daily basal: {before_total:.3f} → {after_total:.3f} U/day ({after_total-before_total:+.3f}). Percentage change is blank when the previous value is zero.")
        if not metadata_changes and not schedule_changes:
            st.caption("No changes from the review baseline.")
if errors:
    st.error("Fix before saving: " + " · ".join(dict.fromkeys(errors)))
same_as_saved = st.session_state.get("saved_fingerprint") == fingerprint(draft)
save_col, download_col = st.columns([1,2])
with save_col:
    if editing and st.button("Overwrite existing profile", type="primary", disabled=bool(errors) or same_as_saved, width="stretch"):
        try:
            saved = overwrite_profile(DATA, normalized, editing, reference["id"] if reference else None,
                                      second_reference["id"] if second_reference else None)
            st.session_state.editing_original = deepcopy(saved)
            st.session_state.saved_fingerprint = fingerprint(draft)
            st.session_state.initial = fingerprint(draft)
            st.session_state.last_saved = saved
            st.session_state.review_baseline = deepcopy(saved)
            reset_history(st.session_state)
            st.session_state.notice = f"Updated {profile_label(saved)} · {saved['name']}. The version number is unchanged."
            st.rerun()
        except (ValueError, OSError) as exc:
            st.error(f"Could not overwrite: {exc}")
    destination = next((p for p in profiles if p['category'].casefold() == draft['category'].strip().casefold() and p['version'] == draft['version']), None)
    confirmed_replace = False
    if destination and not same_as_saved:
        st.warning(f"Selected version exists: {profile_label(destination)} · {destination['name']}.")
        confirmed_replace = st.checkbox(f"Replace {profile_label(destination)} · {destination['name']} with this draft",
            key="replace_version_" + fingerprint(destination))
    save_label = "Replace selected version" if destination and not same_as_saved else "Save as new version"
    if st.button(save_label, type="secondary" if editing else "primary",
                 disabled=bool(errors) or same_as_saved or bool(destination and not confirmed_replace), width="stretch"):
        try:
            if editing:
                normalized["parent_id"] = editing["id"]
            if destination:
                normalized["category"] = destination["category"]
                saved = overwrite_profile(DATA, normalized, destination, reference["id"] if reference else None,
                                          second_reference["id"] if second_reference else None)
            else:
                saved = save_profile(DATA, normalized, reference["id"] if reference else None,
                                     second_reference["id"] if second_reference else None, version=int(draft["version"]))
            st.session_state.saved_fingerprint = fingerprint(draft)
            st.session_state.initial = fingerprint(draft)
            st.session_state.last_saved = saved
            st.session_state.editing_original = None
            st.session_state.advance_version_after_save = True
            st.session_state.review_baseline = deepcopy(saved)
            reset_history(st.session_state)
            st.session_state.notice = f"{'Replaced' if destination else 'Saved'} {profile_label(saved)} · {saved['name']}."
            st.rerun()
        except (ValueError, OSError) as exc:
            st.error(f"Could not save: {exc}")
with download_col:
    if not errors:
        st.download_button("Download draft JSON", json.dumps(normalized,indent=2,ensure_ascii=False,allow_nan=False),
                           "profile-draft.json", "application/json")
    st.caption("Settings comparison only. Graphs show your profile values, not predicted glucose outcomes.")
if st.session_state.get("last_saved"):
    saved = st.session_state.last_saved
    st.download_button(f"Download saved {saved['category']} v{saved['version']}", json.dumps(saved,indent=2,ensure_ascii=False),
                       f"profile-v{saved['version']}.json", "application/json")
    excel_download(saved, "Download saved profile Excel", "excel_saved")
    st.caption("Excel includes the template's overview and schedules. Use JSON to preserve links and additional overview fields.")
sync_native_theme(dark)
