"""Theme and metric colors for the pinned Streamlit 1.64 app."""
import streamlit as st
from streamlit import config

COLORS = {"ic": "#ff9800", "isf": "#e5dc36", "basal": "#19b5ed", "target": "#64d86a"}
LIGHT_COLORS = {"ic": "#c76b00", "isf": "#8a7400", "basal": "#087cac", "target": "#24843b"}


def palette(dark):
    return ({"background": "#181b20", "surface": "#22272e", "text": "#eef2f6", "grid": "#3a414b"}
            if dark else
            {"background": "#ffffff", "surface": "#f2f6f8", "text": "#24354b", "grid": "#dce4eb"})


def reference_color(color, index):
    """Two nearby shades of the metric hue; main profile keeps the base color."""
    destination, amount = ((255, .26) if index % 2 == 0 else (0, .20))
    channels = [int(color[i:i+2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(channel*(1-amount)+destination*amount):02x}' for channel in channels)


def sync_native_theme(dark):
    """Update native widgets too; call after rendering so table edits survive.

    Streamlit has no public runtime theme setter. This small, version-pinned
    adapter updates its process-wide config; the next run sends a new theme to
    the frontend. The app is intended for one local user, not shared hosting.
    No files, browser storage, or installed Streamlit sources are modified.
    """
    base = "dark" if dark else "light"
    if config.get_option("theme.base") == base:
        return
    colors = palette(dark)
    for key, value in {"base": base, "backgroundColor": colors["background"],
                       "secondaryBackgroundColor": colors["surface"], "textColor": colors["text"],
                       "primaryColor": "#19b5ed" if dark else "#007f83"}.items():
        config.set_option(f"theme.{key}", value)
    st.rerun()
