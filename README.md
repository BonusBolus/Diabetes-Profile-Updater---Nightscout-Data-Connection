# Profile Studio

## Nightscout-13: setting/source colors and compact custom axes

Replace the app files, restart and check **Build: Nightscout-13**. Keep your `data/` and `examples/` folders. No new dependency is needed.

- Custom profile selectors highlight I:C orange, ISF yellow, basal blue and target range green. Each button separates the setting color from the profile-name color and includes a Ref 1 / Ref 2 / Current label.
- Ref 1 is purple and Ref 2 pink, with darker variants in light mode. The sidebar selections and identity labels use the same colors as profile names in custom selectors and legends. The identity follows the reference slot, including compare-only mode and references filtered from regular comparisons due to differing units. Profile lines keep their setting colors and reference tints.
- Custom axes use compact 54-pixel lanes alternating left/right, with smaller tick labels and shorter numeric formatting. This replaces large proportional gaps on the right and preserves more plot width on wide screens. Margins grow only for the number of unit axes present and shrink when fields are removed.
- Axis lines, ticks and titles follow the first selected dataset for that unit. Multiple datasets sharing a unit still share one axis, so a single axis cannot show all their colors. Different temporary-target reasons and negative IOB retain their individual trace colors.
- Date navigation, fullscreen and the independent custom same-scale toggle retain their existing behavior.

## Nightscout-12: grouped layers and Custom graph

Replace the app files, including **custom_graph.py** and **custom_graph.js**, restart and check **Build: Nightscout-12**. Keep your `data/` and `examples/` folders. No new dependency is needed.

- **IOB + boluses** and **COB + carbs** are single data-layer toggles. In Median mode, each toggle controls its median timeline and corresponding hourly grid/histogram. The separate IOB + COB layer is removed.
- Select **Custom graph** in Data layers, then open **Choose custom data** above that graph. Choose any combination of glucose, absolute or percentage temp basal, IOB, boluses, COB, carbs, temp targets and VSENS.
- I:C, ISF, basal and target schedules from the current profile/draft and selected references are individual options. Low/high target bounds stay together. Reference tints are preserved. Each source keeps its units, including references with different glucose units. General scalar settings such as DIA are not graph fields.
- One axis per distinct unit; the first selected unit uses the left axis and further units use labeled right axes. More axes use more horizontal space. For one/two selected fields, **Same axis scale** can match two different unit axes numerically. A shared unit already uses the same scale. The toggle is hidden above two fields and resets when fields change.
- Median mode uses median continuous curves with their existing variability bands, and **average hourly totals** for carb/bolus bars. Complete zero-event hours count, missing/partial hours are excluded. Selecting a specific day returns to its individual events.
- Custom controls work in expanded view, preserving zoom and local date navigation without a server rerun. They are independent of the pinned graph's overlay and axis controls. A Streamlit rerun/reload resets custom selection to glucose; it does not save graph choices into a profile.
- Dates, glucose 4–10 band, target-reason colors, signed IOB, event markers and profile-change guides remain. Profile schedules show the current draft/reference, not the historical active profile. Custom graph temp-target shading continues to use Nightscout's historical baseline.

Historical fields still absent: **DEV, −BGI and SENS%**, removed in Nightscout-11 at the user's request. This update does not restore those approximate telemetry sources or add an AAPS log importer. All other previously available underlying recorded datasets remain selectable.

## Nightscout-11: keep VSENS, remove approximate telemetry

Replace the app code, restart and check **Build: Nightscout-11**. Keep your `data/` and `examples/` folders, then click **Load / refresh data**. No new dependency is required.

- Removed DEV, −BGI and SENS% from data loading, graph layers and profile overlays.
- Removed the extra AndroidAPS source-unit selector used for Dev/BGI reason text. Your profile glucose-unit setting remains.
- **Variable sensitivity (VSENS)** stays available as a graph layer and profile overlay, including expanded view. It uses uploaded `openaps.suggested.variable_sens`, converted from mg/dL/U when the profile uses mmol/L.
- The combined panel is now **IOB + COB**, with U and g axes. Existing layer selections are filtered to the supported choices.

Identical AAPS Autosens, raw deviation and insulin-impact curves would require the original internal calculated graph data through a suitable export or custom upload. The standard Nightscout fields previously used here cannot guarantee an identical reconstruction. No such export or uploader is implemented.

The notes below describe earlier releases. The DEV/BGI/SENS features and source-unit selector documented for Nightscout-9/10 are superseded by this removal.

## Nightscout-10: unified controls, SENS scale and timestamp fix

Replace the app code, restart and check **Build: Nightscout-10**. Keep your `data/` and `examples/` folders. No new dependency is required.

- Overlay selection, matching axes, previous/next day and the date calendar now live in a single graph toolbar. The same controls remain in expanded view. Axis limits are recomputed for the selected overlay and profile, so a stale external selector cannot change the wrong axes. Matching is numeric only; it does not convert different quantities into equivalent units.
- **SENS%** is available as its own layer as well as in the IOB/COB/SENS panel and profile overlay. Its percentage axis stays centered on 100%, normally 80–120%, expanding symmetrically in 10-point steps (for example 70–130%). A dotted 100% baseline helps interpretation. Matching both profile and SENS axes may require a wider common range.
- Each recorded panel has **↑ / ↓** controls to change its position; the profile remains pinned. Order survives local day, overlay, scale and profile-setting changes, including fullscreen. A Streamlit rerun or reload starts a new viewer with the default order.
- The **hourly bolus and carb bars default to Average**; the toggle still offers Median. Both use each selected day's complete hourly total, including complete zero-event hours and excluding partial/unavailable hours. IOB/COB timelines and heatmap cells are unchanged.
- Fractional seconds are now retained when converting UTC timestamps to local minute coordinates. Previously, losing fractions could falsely trigger the daylight-saving discontinuity check, breaking several curves at once. Genuine gaps over 15 minutes, actual DST clock jumps and empty median bins remain visible. No readings are interpolated or invented.
- Reported **Dev** is now shown as neutral blue bars and **−BGI** as a line on a shared axis symmetric around zero. Units still follow the profile's glucose unit. The optional variable-sensitivity overlay remains on its own right axis.

### What SENS% actually represents here

The source remains `openaps.suggested.sensitivityRatio × 100`. A ratio of 1 is 100%. In the standard Autosens adjustment branch, a higher ratio increases basal and divides the profile ISF by that ratio; it generally represents compensation for resistance, not a higher numerical ISF. However, the uploaded loop ratio can instead incorporate a temporary-target or TDD adjustment.

AAPS's on-device SENS graph reads `autosensData.autosensResult.ratio`. That internal curve is not identical to the uploaded loop ratio in all cases. The app therefore labels the uploaded series **SENS% (loop ratio)** and explains the distinction beneath the graph. It does not claim to reconstruct missing Autosens state.

### Why the Dev graph cannot exactly reproduce AAPS yet

The app reads `Dev:` and `BGI:` from `openaps.suggested.reason`, interpreting them in the AndroidAPS source units selected in the connection form. In AAPS's SMB calculation, the reported Dev is approximately `6 × (selected glucose trend − 5-minute BGI)`, projected over 30 minutes, rounded and then formatted in the phone's units. For negative results it may select a longer averaged glucose trend.

Dividing that number by six rescales the projection without itself discarding more information, but cannot recover the original five-minute deviation, undo rounding, or supply a meal/UAM classification. The on-device graph uses raw Autosens deviation and an insulin-impact calculation based on the sensitivity used for absorption; it can differ from the loop reason for more than the factor of six. This release preserves the original reported Dev and labels its 30-minute basis, alongside the sign-reversed five-minute BGI. Comparing their heights as though they had the same time basis would be misleading. The AAPS graph code also plots these internal mg/dL-based values directly, whereas Profile Studio converts to the glucose unit shown on its axis; that is another reason the axis numbers can differ from the screenshot.

AAPS's documented classification is grey for carbs, green/red for positive/negative deviations used by Autosens, yellow for UAM, and black for small deviations excluded from sensitivity calculations. Black is not an unknown-data category. Its implementation uses internal `type` and `pastSensitivity` values. Those flags and raw deviations are not standard fields of the uploaded suggested result. The current bars therefore use a separate neutral blue and explicitly say classification is unavailable; no colors are guessed from COB or the sign of Dev. An export containing raw Autosens state would be needed for faithful classified bars.

Verified against:
- [AAPS graph documentation](https://androidaps.readthedocs.io/en/latest/DailyLifeWithAaps/AapsScreens.html)
- [Graph preparation: Autosens ratio, raw deviation, colors and −BGI](https://github.com/nightscout/AndroidAPS/blob/598e2eb39c7e15876e4c42876a2162bffcb4fe5f/workflow/src/main/kotlin/app/aaps/workflow/PrepareIobAutosensGraphDataWorker.kt)
- [SMB projected Dev and BGI](https://github.com/nightscout/AndroidAPS/blob/598e2eb39c7e15876e4c42876a2162bffcb4fe5f/plugins/aps/src/main/kotlin/app/aaps/plugins/aps/openAPSSMB/DetermineBasalSMB.kt)


## Nightscout-9: sensitivity layers and expanded controls

Update your existing installation with the files in this ZIP (including **aaps_settings.py**), restart Streamlit, and check **Build: Nightscout-9**. Keep your existing `data/` and `examples/` folders. Click **Load / refresh data** once to load the new telemetry fields.

- Negative IOB is lavender, positive IOB remains blue. Lines split at zero crossings without joining missing intervals. This also applies to the median line; its 25–75% band retains the existing blue styling.
- The graph toolbar now switches **I:C / ISF / Basal / Target** locally, including expanded view. It preserves the displayed dates, zoom and graph toggles, updates the corresponding references, and moves all profile-change guides. Invalid draft schedules are omitted from these buttons until corrected.
- **Temp targets: on/off** appears directly above the glucose panel and beside the profile graph when its glucose overlay is selected. Both buttons control the same view; standalone temporary-target panels are unaffected.
- New data layers: **IOB + COB + SENS%** (separate U, g and % axes), **Deviation + BGI**, and **Variable sensitivity**. The Dev/BGI panel has its own variable-sensitivity overlay button using a separate right axis. Variable sensitivity and SENS% are also available as profile overlays.
- The hourly bolus and carb bar plots each have a **Bars: Median / Average** toggle, including expanded view. Average is the arithmetic mean of each selected day’s total for that hour. Both statistics include complete zero-event hours and exclude partial or unavailable hours, using the same SMB filter as the grid. Heatmap cells and IOB/COB curves are unchanged. Day navigation shows the selected day’s totals and disables this aggregate toggle.
- Each new continuous series uses the same per-day, five-minute median and 25–75% band in Median mode. Missing observations stay blank. Dates and controls stay local after loading; graph navigation makes no Nightscout requests.

### Sources and units

`openaps.suggested.sensitivityRatio × 100` supplies **SENS% (reported ratio)**. This field can reflect Autosens, a TDD-based ratio or temporary-target adjustments; it must not always be interpreted as pure Autosens. `openaps.suggested.variable_sens` supplies variable sensitivity in mg/dL/U, converted for mmol/L profiles. Missing or nonpositive sensitivity fields are omitted, without substituting the editable profile ISF.

AAPS commonly uploads **Dev** and **BGI** in the suggested result's `reason` text, formatted in the phone's glucose units. Choose **AndroidAPS glucose units (Dev/BGI reason text)** in the connection form, then refresh. Leaving it unspecified keeps those curves blank and shows a notice. Decimal points and decimal commas are supported. Select dates with consistent source units; do not combine a historical unit change in one load. The `units` field in a suggested result is an insulin amount, not a glucose-unit declaration.

**Dev is the uploaded 30-minute projected deviation**, while **BGI is the uploaded 5-minute insulin impact**. The legend and graph note identify these different time bases. This is not a reconstruction of AAPS's raw five-minute Autosens deviation graph. No insulin action or sensitivity values are calculated by this app.

Upstream references checked on 2026-09-24:
- [AndroidAPS preferences](https://androidaps.readthedocs.io/en/latest/SettingUpAaps/Preferences.html)
- [Dynamic ISF and TDD sensitivity ratio](https://androidaps.readthedocs.io/en/latest/DailyLifeWithAaps/DynamicISF.html)
- [AAPS serialized result fields](https://github.com/nightscout/AndroidAPS/blob/598e2eb39c7e15876e4c42876a2162bffcb4fe5f/core/interfaces/src/main/kotlin/app/aaps/core/interfaces/aps/RT.kt)
- [AAPS Dev/BGI calculation and formatted reason](https://github.com/nightscout/AndroidAPS/blob/598e2eb39c7e15876e4c42876a2162bffcb4fe5f/plugins/aps/src/main/kotlin/app/aaps/plugins/aps/openAPSSMB/DetermineBasalSMB.kt)

Other possible uploaded fields include insulin activity and basal IOB; effective ISF from the reason; `isfMgdlForCarbs`; eventual/predicted glucose; and insulin/carbohydrate requirements. Availability depends on AAPS version, algorithm and upload settings. Raw Autosens internals (such as valid-deviation flags, deviation slopes, absorption classification and full TDD inputs) are not all standard Nightscout device-status fields. These extra layers are not implemented in this release.

### General AndroidAPS settings

Overview → **General AndroidAPS settings** records eight optional preferences: `min_5m_carbimpact`, meal max absorption time, maximum temporary basal U/h, maximum total OpenAPS IOB, DynamicISF Adjustment Factor, SMB frequency, and the SMB/UAM basal-minute limits. Units and names follow AAPS. The carb-impact setting uses mg/dL per five minutes, even for a mmol/L profile. These are historical values, not clinical defaults or validated AAPS configuration limits.

Fields start blank and support undo/redo, review, save and overwrite. Viewing an older profile does not create an edit. They are stored in JSON under `overview.aaps_settings`. Excel exports include an **AAPS settings** sheet with the profile-sheet association, stable key, readable label, unit and value. Keep that association when importing. Old workbooks without this sheet remain compatible. These fields do not configure AndroidAPS or change recorded Nightscout data.


Build: **Nightscout-8.4**. This label also appears at the top of the sidebar, so you can confirm you are running this update.

A local Python app for creating diabetes profile versions by comparing a draft with one or two saved references. Includes your **LenStandardV17** example in the **Standard** category, with **DIA 8.5 hours**. The `Undefined` field is omitted.

## Nightscout-8.4 temporary-target axis

The temporary-target panel now uses a fixed 0–20 mmol/L vertical range (0–360 mg/dL), including empty days, median/multiple-day views and expanded day navigation. Values outside the range are clipped. The independent temporary-target overlay uses the same limits; selecting Same axis scale still matches both overlay axes to their combined data range.

## Nightscout-8.3 event labels

Carb and user-bolus amount labels can extend beyond the plotting boundary without being cut off. Axes with labeled events reserve extra headroom, including profile overlays and matched axes. Day navigation recalculates that space from the displayed day's data. Existing overlapping-label suppression remains in place.

## Nightscout-8.2 profile-change markers

Profile-change guides are now 2-pixel dashed lines with higher contrast in both light and dark mode, making them distinct from the standard grid. Their positions and historical temporary-target shading are unchanged.

## Nightscout-8.1 temporary-target shading

Temporary targets now use separate rectangular fills rather than fills connecting multiple intervals. Dotted vertical sides reach the nearest edge of the historical profile target range active at that time. A target below that range is shaded upward. A target range already overlapping the historical range is shaded only within its own limits. Colors still come from the uploaded reason.

The underlying historical limits are retained from AndroidAPS effective-profile uploads even during a temporary override. Rectangles split when those limits change, and at midnight. Each displayed day uses its own history. The draft and comparison profiles never supply this baseline. If historical target data is unavailable, the temporary-target line is shown without shading; a warning and the graph caption explain the limitation. No scheduled target line is drawn outside temporary-target intervals. The fixed glucose 4–10 band is separate.

The note appears beneath affected panels and profile overlays, including expanded view. Restart the app and click **Load / refresh data** after updating to load the historical limits. Confirm **Build: Nightscout-8.1** in the sidebar.

## Nightscout-8 graph controls

- Taller profile, recorded-data and hourly summary graphs provide more vertical plotting space. Glucose retains its 0–20 mmol/L minimum scale (expanding for higher values).
- Select loaded days using a month calendar. Colored buttons are selected; dates outside the loaded interval are disabled. Loaded dates may still contain gaps or have no records. In multiple-day and median views, click days to include/exclude them, or use All loaded / Clear. The From / Through calendars still define the manual download window; the app does not query Nightscout's entire history to discover dates.
- Data layers and the right-axis overlay use clickable pills. In expanded view, the date button opens a calendar for jumping to a single loaded day, and overlay buttons remain available.
- The bolus grid has an **Exclude SMB** toggle directly above it. It updates both the grid and histogram and remains active when navigating loaded days in that viewer. It removes only explicitly classified SMB events; unknown boluses stay included. It does not change other graphs, stored records or daily summary totals. Rebuilding the viewer (for example, switching profile settings) starts with all boluses included again.
- Dashed vertical guides mark actual changes in the primary profile/draft's selected setting. Switching Basal to I:C uses I:C changes. In Compare mode these follow Profile 1. Repeated values and the midnight boundary do not add lines. Guides also appear on recorded panels, heatmaps, histograms and expanded overlays.
- The hourly histogram remains the median of each hour's daily totals across complete hours, including zero-event hours; partial hours appear only in the grid. Both views use the same SMB filter and local timezone.

Updating an existing installation: stop Streamlit, copy the update files into the existing app folder (including the new `date_controls.py`), then restart with `start.bat` or your existing virtual environment. Check **Build: Nightscout-8.2** in the sidebar. Your existing `data/` and `examples/` folders are not part of this code update.

## Start on Windows

1. Install **Python 3.11 or newer** from https://www.python.org/downloads/ if needed. Enable **Add Python to PATH** during installation.
2. Extract this entire folder to a writable location.
3. Double-click **start.bat**. The first launch installs dependencies in a local `.venv` folder; this requires internet access.
4. The app opens in your browser. If it does not, open **http://localhost:8501**. Keep the terminal window open while using the app.

Later launches reuse the environment. Once dependencies are installed, the app runs locally without an account or internet connection. Stop it with Ctrl+C in the terminal.

On macOS/Linux, run `sh start.sh` from this folder (Python 3.11+ with venv support is required).

Manual setup, or recovery after an interrupted installation:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

On macOS/Linux, replace `.venv\Scripts\python.exe` with `.venv/bin/python` and use `python3` for the first command. Run from the app folder so Streamlit loads the local configuration.

## Workspaces

- **View one profile**: select a saved category/version; read its overview, schedules and graphs.
- **Compare two profiles**: select two saved profiles. Tables and graphs compare them directly, without a draft curve.
- **Edit draft**: edit a new draft or an existing profile with up to two references. Switching modes preserves the draft.

**Browse history / export** opens the history utility. Draft loading/import actions are grouped in their own sidebar expander. In Overview, **Version for new save** starts at the next unused number within the category. Choose another unused positive whole number if desired. After a successful save, the selector advances to the next unused number for subsequent edits. Choosing an existing category/version enables **Replace selected version** only after confirming its exact destination. This preserves that destination's identity and creation time. **Overwrite existing profile** still updates the profile originally opened for editing, keeping its version fixed.

Comparison tables align every time boundary and show **Draft | Reference 1 | Reference 2**, including category, version and name in the reference headings. Amber highlights mark the draft and each reference that differs at that interval. Equal target limits remain `6.6 - 6.6`. Editable schedules stay beside the comparison table; the combined table itself is read-only.

## Daily workflow

1. Choose a **reference category and version** under Reference 1 in the sidebar. Enable **Compare with a second profile** to select another category and version under Reference 2.
2. Click **Copy reference to a new draft** to copy Reference 1. A draft is already prepared from the included profile at first launch.
3. Enter a name, category, optional effective date and notes in **Overview**. DIA and timezone are editable. Add arbitrary text or numeric overview fields in the table.
4. Edit start times and values in **I:C**, **ISF**, **Basal** and **Target**. Press Enter or leave the cell to commit an edit. The graph and difference table update immediately after the edit is committed.
5. To scale a range, expand **Adjust a time range by percentage**, enter the start/end and percentage, then apply. The percentage always applies to current draft values, so repeated adjustments compound.
6. Click **Save as new version**. The version selected in Overview is saved within the category. The supplied Standard v17 is followed by v18; a new category begins at v1. The name is separate from the version number and remains editable.

Changing either reference or turning the second comparison off never replaces the draft. Copying, importing or opening an existing profile for editing replaces the draft; if it has changes, tick the discard checkbox first. **Unsaved changes last only for the current browser session.** Save or download the draft before closing, refreshing or restarting. This app is intended for one local user/session at a time.

### Edit an existing profile

Select the profile under **Reference 1**, then click **Edit existing profile**. Its name, notes, date, overview and schedules load without being reset. Make your changes and click **Overwrite existing profile**. The same JSON file is replaced atomically; its ID, category, version, creation time and original parent stay unchanged. An `updated_at` timestamp records the edit and appears in History. The old contents of that version are replaced; other saved versions remain unchanged. Use **Save as new version** instead to retain the original contents.

The banner names the profile you are editing. Changing either reference does not change the overwrite destination. Category is fixed in edit mode; use **Copy reference to a new draft** to create a profile in another category. If the saved profile was changed externally after you opened it, overwrite is blocked: download your draft, then reload the saved profile before applying your changes.

**Cancel changes**, below the editing banner, discards all unsaved edits, including incomplete table rows, and restores the profile to when you opened or last saved it. You stay in edit mode with the same references and appearance. Cancel does not write any files or undo an overwrite you already saved.

### Undo, redo and review

**Undo** and **Redo**, above the editor tabs, step through committed changes to profile fields, schedule tables, additional overview fields and percentage adjustments. A new edit after Undo clears the redo steps. Incomplete table rows can also be undone. Reference selection and appearance are not part of edit history. Saving, cancelling, copying or importing starts a fresh edit history. Undo never changes a file you already saved. There is no automatic draft recovery after the browser session ends.

**Review changes before saving**, above the save buttons, combines overview changes, added/removed start times and changed schedule intervals across all four metrics. It includes absolute and percentage changes and the daily basal difference. Its baseline is the profile you copied, imported, opened for editing or last saved; changing reference selectors does not move it. Incomplete drafts must be corrected before the summary or saving is available.

### Corresponding profiles

In Overview, choose an optional **Corresponding profile**. For example, link Drinking v3 to Standard v18. The link is saved as `linked_profile_id` when you save or overwrite, independently of the two comparison selections. It belongs to this profile; the linked profile is not edited. Copying a profile carries its link forward, so check it when creating a new version. Version numbers are never matched automatically.

Click **Compare corresponding profile** to load the draft's link into Reference 2. After reopening a saved profile under Reference 1, **Compare linked profile** in the sidebar does the same. Both actions keep the draft and Reference 1 intact. A profile already selected as Reference 1 does not need to be loaded again. Choose **None** to remove a link, then save. A linked profile must be present in your local history.

### Appearance

Use the **Dark mode** toggle in the sidebar. It changes native tables, inputs, page backgrounds and charts while preserving the current draft. Bright orange, blue, green and yellow identify I:C, basal, targets and ISF. Light mode uses darker shades of those colors for readability. Appearance is shared by tabs using the same local app process and resets to the configured theme when the app restarts. Use this toggle for appearance rather than Streamlit's separate toolbar theme selector.

For example, to make a new Drinking version, select the previous Drinking profile as Reference 1, copy it to a draft, then select the corresponding Standard profile as Reference 2. For a new category, edit the draft's Category field. Version numbers are independent within each category, so choose the corresponding Standard version explicitly. Each selector initially offers the latest version in its category; the app does not infer a relationship from equal version numbers. The same saved profile cannot occupy both reference slots.

## Graphs and calculations

Each schedule tab places the editable schedule on the left and one combined reference comparison table on the right. The full-width profile graph and optional aligned Nightscout panels appear below the tables.

- I:C is orange, ISF yellow, basal blue and targets green. Solid lines show the draft, dashed lines show Reference 1, and dotted lines show Reference 2. Reference lines use slightly different tints of the same metric color and remain thinner than the draft. Tabs and headings use the corresponding metric color. Profile legends use only the profile name, with one entry for a target range. Reference prefixes and dates are omitted from legends. Full reference identity remains in comparison-table headers. Hover for values, drag to zoom, and double-click to reset the zoom.
- Schedules are piecewise constant over a nominal 24-hour profile day. Every metric has its own change times. A value applies from its start time up to, but excluding, the next start time. The final entry extends to 24:00.
- One table compares intervals formed from **the draft and both references' change times**, even when row counts differ. Amber marks differing value cells. The save review separately retains absolute and percentage changes against the original editing baseline.
- Overview shows both reference profiles. Daily basal and DIA summaries show the difference against each selected reference.
- Daily basal is the sum of **rate × interval duration**, in U/day. It is the nominal schedule total, not measured delivered insulin and not a daylight-saving-date simulation.
- A percentage edit applies to `[start, end)`. Boundary entries are inserted when needed to preserve all values outside that interval. For a range crossing midnight, make two edits. A +5% I:C edit increases the stored ratio itself by 5%. Targets scale both low and high values. Percentage results retain up to six decimal places; the table displays four.
- DIA is shown in the overview and history; it does not modify the schedule graphs.
- Graphs compare profile settings and do not predict glucose outcomes or recommend settings. There is no pump connection or automatic profile activation.
- No conversion occurs between editable/reference profiles. Glucose units come from the imported profile and are displayed read-only. If a reference uses different glucose units, only that reference's ISF/target comparisons are hidden. I:C and basal remain comparable, and a compatible second reference stays visible.

## Nightscout data

Open **Nightscout data** in the sidebar. Enter your HTTPS Nightscout site URL and a **readable** access token, choose a date range, and click **Load / refresh data**. Enter the token only in the local app. In Nightscout, a read-only token can be created under **Admin Tools → Add New Subject**, with the `readable` role. See [Nightscout's token instructions](https://nightscout.github.io/nightscout/security/). Do not put the token in the URL field. A public, readable site can leave the token blank.

The connection uses only GET requests to Nightscout's V1 API. It never uploads profile changes, modifies treatments or controls AndroidAPS. The site must expose the V1 API even if AndroidAPS uploads using V3. Missing endpoints or permissions are reported in the sidebar. No connection to your account is required during installation; enter your details locally after starting the app.

Choose **One day**, **Multiple days**, or **Median + band**, then select the days and data layers you want to see:

- **Glucose:** recorded CGM points, displayed in the profile's glucose unit. Nightscout SGV values in mg/dL are divided by 18 for mmol/L. Missing intervals longer than 15 minutes break the line.
- **Temporary basal:** recorded absolute rates in U/h, clipped to their recorded durations, subsequent temp changes and cancellations. A preceding temp that overlaps the start date is requested as well. These are recorded rate intervals, not a reconstructed total of insulin delivered. No scheduled basal is inferred from your draft to fill gaps. Percent-only temp records appear in a separate panel using the raw Nightscout percent field; they are not converted to U/h.
- **Boluses / carbs (One day / Multiple days):** recorded amounts at their event times. Boluses share a panel with IOB; carb inputs share a panel with COB. SMBs are triangles, explicitly identified user boluses are rectangles, and boluses without a type flag are open diamonds. Marker area grows approximately with dose, using fixed scales across days and readable minimum/maximum sizes. User-bolus and carb markers have amount labels (U or g); SMB labels stay in the hover details to reduce clutter. Carb marker sizes likewise grow with grams, independently of the insulin scale. Classification uses `type` / `bolusType` and `isSMB`, never dose size or the generic Correction Bolus event name. Priming records are excluded. Each type is labeled in the legend and hover text.
- **IOB / COB:** uploaded AndroidAPS/OpenAPS values from device status. IOB uses the current `openaps.iob` record, not future entries in a prediction array; COB uses `openaps.suggested.COB`. Their own timestamps are used where available, so old status values are not shifted to newer upload times. Missing values remain gaps. The app does not recalculate IOB or COB from the edited profile.

Use **Overlay · right axis** beside the profile graph to choose a Nightscout dataset or combined IOB/bolus or COB/carbs group, or **None**. The selector is beside the graph rather than in the sidebar. **Same axis scale** sets identical numeric limits on the left and right axes and links their vertical zoom. It does not convert units or imply that different quantities are equivalent. Turn it off to restore independently scaled axes (including the default 0–20 glucose range). Profile settings use the left axis and the selected dataset uses the right axis. Dataset choice is independent of the panels selected below. The main-app controls are shared across profile tabs.

Hover now selects the **nearest point**, highlights it with a ring, and shows a vertical guide at that time across the panels. A fixed information box at the upper-right of the graph viewer shows a short series name, value/unit, date/time and target reason when available. It stays away from the pointer and replaces the repeated floating multi-series pop-ups. The median hover also shows the number of contributing days.

A compact 245-pixel profile stays pinned above a scrollable stack of 205-pixel recorded-data graphs. Reduced spacing and shorter legends make more data visible at once. Scroll **inside that graph area** to browse the panels. **Expand graphs** opens the viewer in browser fullscreen; use **Exit expanded view** or Escape to return. Previous/next buttons are also inside the viewer and remain available in fullscreen. They change that viewer locally, keep its time zoom and do not exit fullscreen. The sidebar date and other profile-tab viewers are unchanged by these local buttons; changing a main-app control rebuilds the viewer from the main-app selection. The viewer toolbar also has an **Overlay** selector, available in expanded view. It switches the right-axis dataset locally, keeps fullscreen and time zoom, and leaves the lower panels unchanged. Before day cycling it preserves the selected single-day, multi-day or median mode. After day cycling it uses that displayed day. Viewer choices remain local; a main-app rerun restores the main-app selections. If the browser blocks fullscreen, its own F11 fullscreen mode is available. All panels share the profile graph's 00:00–24:00 horizontal axis and zoom together. Plotly is included locally with the installed package; the viewer does not load scripts or send records to an external chart service.

**← Previous** and **Next →** above each graph cycle through the loaded calendar dates and wrap at either end. In a multi-day view, these switch to **One day** starting before/after the displayed selection. Empty days are still selectable and are labeled as having no records. Cycling never reloads Nightscout or edits the draft.

Every graph includes its displayed date or date range, including saved image exports. Profile-only graphs use the effective date when set, otherwise an explicitly labeled viewing date. With Nightscout loaded, the profile graph also names the selected recording dates. Nonconsecutive selections say “selected days.” Tick labels and legends are slightly larger.

Glucose axes start at **0–20 mmol/L** and expand upwards if any displayed-day reading exceeds 20. In mg/dL, the equivalent starting range is 0–360. A fixed green **4–10 mmol/L** band (72–180 mg/dL) is shown on both the glucose panel and glucose overlays. This band is separate from recorded Nightscout targets. Points below 4 are red, above 10 orange, and in range green. IOB uses blue, basal cyan/blue, and COB/carbs orange; IOB, COB and basal use filled curves. Multi-day traces retain data-type colors. Recorded legends show concise series names once, rather than repeating one dated label per day. Dates remain in graph titles and hover details. IOB, COB and temporary-target outlines are solid on every day. IOB/COB are filled to zero; temporary-target shading uses independent rectangles extending toward the historical profile target range, with dotted vertical sides. Basal and glucose retain day-specific line/marker styles.

**Nightscout targets displays temporary targets only**, using uploaded **Temporary Target** treatment intervals. Scheduled profile target lines are hidden in every recorded panel and overlay. An interval begins at its event timestamp and ends at its duration, a cancellation, a replacement, or the displayed date boundary. A target already active at the first loaded date is requested too. Missing/invalid intervals stay blank. Equal limits such as 6.6–6.6 remain equal; target units are converted for display. The fixed 4–10 background band is separate and stays visible.

Colors use the uploaded treatment's **`reason` string**, normalized for capitalization and surrounding spaces: **Eating Soon orange, Activity cyan, Hypo/Hypoglycemia red**. **Custom, missing, localized or other unrecognized reasons use green**. The original reason appears on hover; no reason is inferred from glucose, target level, dose or time. Cancel is an end event, not a fourth colored target. The app retains the underlying scheduled range during each temporary target to anchor its shading; standalone scheduled target lines remain hidden. Reload Nightscout after updating.

**IOB + boluses** and **COB + carbs** can each be selected as a combined overlay on the profile graph. Both members use the right axis (U or g); the profile stays on the left. I:C, ISF and Target profile axes use a fitted range and need not start at zero; basal retains zero. **Same axis scale** explicitly overrides that independent scaling. Charts wait until their tab has a visible width and fonts are ready before drawing. Redraw, overlay/date changes and resize operations are serialized, and charts receive explicit widths after resizing or returning to a tab. Concise deduplicated legends, short unit labels, reserved axis space and collision suppression for amount labels reduce overlap. If two amount labels collide, one is hidden while its marker and hover value remain available.

**Daily summary**, inside the graph viewer, shows mean glucose, SD, CV, in/below/above the fixed 4–10 range, recorded carbs and bolus totals, plus glucose coverage. Glucose statistics weight observed five-minute bins equally, with no interpolation. Missing bins are excluded from percentages and reported through coverage. Current-day coverage stops at the load timestamp; DST days use their actual elapsed duration. Unavailable treatments show a dash rather than a false zero. These are descriptive values from uploaded records, not estimated insulin delivery or dosing recommendations.

The AndroidAPS upload formats were checked against its upstream [bolus serializer](https://github.com/nightscout/AndroidAPS/blob/master/plugins/sync/src/main/kotlin/app/aaps/plugins/sync/nsclient/extensions/BolusExtension.kt), [temporary-target serializer](https://github.com/nightscout/AndroidAPS/blob/master/plugins/sync/src/main/kotlin/app/aaps/plugins/sync/nsclient/extensions/TemporaryTargetExtension.kt) and [effective-profile serializer](https://github.com/nightscout/AndroidAPS/blob/master/plugins/sync/src/main/kotlin/app/aaps/plugins/sync/nsclient/extensions/EffectiveProfileSwitchExtension.kt).

 Dates use the profile timezone, including daylight-saving transitions. Clock jumps break recorded lines; the repeated hour on an autumn DST day appears at the same local clock times. If you change the profile timezone, reload Nightscout before comparing. Days are selected manually and are not automatically matched to profile versions or historical profile switches.

The **Median + band** view shows one median curve with a 25th–75th percentile band for **glucose, IOB, COB and recorded temporary basal**. These panels and their profile overlays do not stack individual days. Glucose/IOB/COB use the median of readings within each day's five-minute bin, then the median across days. Temporary basal first uses the duration-weighted rate within each day's known five-minute interval, then takes the median across days. Each day contributes once, including repeated DST clock bins. Missing bins stay blank; recorded zero is a real observation. Hover reports contributing days. Basal is based only on recorded temp intervals, not a reconstruction of the full scheduled basal. Percent-only basal records are summarized separately in their original units.

Median mode adds two new panels automatically: **Boluses hourly** and **Carbs hourly**. Each contains a **day × hour heatmap** of recorded totals (U or g), with a **median hourly histogram** below it. Bolus totals include SMB, user and unclassified recorded boluses. A zero cell means no event was returned for an elapsed hour; unavailable treatments, nonexistent DST hours and future hours are blank. A partial current hour appears in the heatmap with a partial-hour hover label but is excluded from the histogram. Repeated autumn DST hours are combined within that day/hour. Complete zero-event hours participate in the median. Event markers are omitted from median IOB/COB panels and overlays, so they don't stack across days. Temporary targets retain their actual intervals and reason colors.

Expanded-view date buttons still switch to a single recorded day, including that day's heatmap row and hourly amounts. They preserve the panel arrangement and fullscreen view. Switching overlays before cycling dates preserves median mode.

## Performance

Only the active profile tab builds its Nightscout viewer; Overview builds none. The schedule editors remain available and preserve unsaved changes across tab switches. Recorded traces, medians, hourly totals, daily statistics and recent prepared viewers are reused from bounded caches within the current loaded snapshot. These caches are local to your session, contain no new files, and are replaced on Load / refresh or discarded with Clear loaded data. Profile edits rebuild the relevant profile comparison without reprocessing the same recorded series. Unchanged viewers reuse their generated HTML. Nightscout is still contacted only by the manual load button.

A local synthetic benchmark with seven days of five-minute glucose/IOB/COB data, half-hourly temp basals and recorded events measured one median-viewer's server-side preparation at **2.50 → 1.83 seconds** for a first build, and **2.36 → 0.0023 seconds** for an unchanged repeat. This includes the new summary panels. Additionally, hidden profile tabs no longer prepare duplicate viewers. These timings exclude Nightscout network requests and browser rendering; they are not a guarantee of total app latency on your computer. No dependency upgrade is needed.


Loading is manual and limited to 31 days per request. Changing graph options, references, profile values or themes does not fetch data. The sidebar shows the loaded dates, timezone and refresh time; changing the connection form does not change this loaded snapshot until you submit it. Data and credentials stay in browser-session/server memory, are not saved in profile JSON or Excel, and are not automatically recovered after closing the session. **Clear loaded Nightscout data** removes the recorded-data snapshot. Optional `NIGHTSCOUT_URL` and `NIGHTSCOUT_TOKEN` environment variables can prefill the connection fields.

The client requests bounded time windows and splits full result windows to avoid silently accepting a full page as a complete dataset. Invalid values and unavailable data sources are reported. Endpoint access and uploader formats can vary; automated tests use synthetic Nightscout records and mocked requests. Your own server connection has not been tested as part of this package.

## History and storage

Each saved profile is a complete JSON file in **data/profiles/**. Files contain category, version, name, creation time, optional effective date, parent profile ID, comparison profile IDs, overview fields, notes and schedules. `comparison_id` records Reference 1 and `second_comparison_id` records Reference 2 (or null when disabled). The copied source stays recorded separately as `parent_id`. The History page shows the references used when a version was saved. Older JSON profiles without a second comparison field still load normally. **Save as new version** retains the original profile; **Overwrite existing profile** replaces the selected version. Reference links identify profiles, not frozen copies of their contents, so overwriting a referenced version changes what that link displays. The included example's save timestamp records its import into this package, not its original clinical creation date; no effective date has been invented.

The **History** page groups versions by category, shows daily basal and DIA trends, and lets you download an individual profile or all history as a ZIP. To move to another computer, copy `data/profiles/` into the new installation, or extract a history ZIP into that folder. Keep a copy of this folder as your backup; JSON files contain personal health information and are stored as ordinary local files.

To keep data elsewhere, set the `PROFILE_STUDIO_DATA` environment variable to your preferred folder before starting the app. By default it always uses the folder beside `app.py`, regardless of your working directory.

## Excel import

Use **examples/profile-import.xlsx**, also available from **Download Excel template** in the app. It contains the original Standard v17 data in the new layout. Keep **one profile per worksheet**; duplicate the worksheet to add another profile. The overview is at the top, with four schedule tables side by side below it.

Import is always manual:

1. Open **Import Excel or JSON** in the sidebar and choose your workbook.
2. Select the worksheet you want to import.
3. Click **Import selected worksheet** to load that profile as a draft.
4. Review the draft, then click **Save as new version** to save it to JSON.

Choosing a file or worksheet alone does not load a draft or save a profile. Category is read from the worksheet, and the version number is selected in Overview before you save. Only the predefined overview fields below are imported from Excel. Name and category can also be edited in the app after importing.

| Cells | Content |
|---|---|
| C5 | Profile name |
| C6 | Category |
| C7 | DIA in hours |
| C8 | Glucose unit: `mmol/L` or `mg/dL` |
| F5 | IANA timezone, e.g. `Europe/Amsterdam` |
| F6 | Optional effective date: Excel date or `YYYY-MM-DD` |
| I5 | Optional notes |
| B13:C… | I:C start time and g/U |
| E13:F… | ISF start time and glucose units/U |
| H13:I… | Basal start time and U/h |
| K13:L… | Target start time and one `low - high` column, e.g. `6.6 - 6.6` |

Edit the amber input cells and retain the labels and header rows. Every schedule has its own start times and must begin at 00:00 with unique times. Blank rows are allowed. Enter times as Excel times or `HH:MM`; add schedule entries below the existing ones as needed, including below the shaded area. Use numeric cells for I:C, ISF, basal and DIA. Keep targets in a single column as `6.6 - 6.6`, `6.1 - 6.1`, etc. Existing target values are preserved; the template does not force every target to 6.6.

The ISF and target unit headers follow the glucose unit selected in C8. Changing the unit does not convert your numbers. I:C, ISF, DIA and targets must be positive; basal may be zero. Formula input cells need calculated values saved by Excel; plain input values are preferable. The original **examples/example-profile.xlsx** layout remains readable; it imports into Standard, which you can change in Overview.

JSON import accepts this application's JSON schema, including draft downloads. Importing creates a draft and assigns a new category version on save. For an exact history restore, copy the saved JSON files into `data/profiles/` instead. JSON is not an AndroidAPS or pump export format.

## Excel export

After saving, use **Download saved profile Excel**. On the History page, select a saved profile under Reference 1 and use **Download selected profile Excel**. Each export contains one profile worksheet with the same fixed overview fields and four schedule tables as the import template. Equal target limits remain ranges such as `6.6 - 6.6`. Start times, dates and numeric settings retain their spreadsheet types. The exported worksheet can be imported manually as a new draft.

Excel does not include arbitrary additional overview fields, profile links or JSON history metadata. Use JSON to preserve those details or restore history exactly. Excel import/export does not change any saved profile automatically.

## Updating an existing installation

Close the app, then copy **all top-level `.py` files** and `README.md` from this package into your existing app folder. This includes `app.py`, `profiles.py`, `appearance.py`, `editor_history.py`, **`nightscout.py`**, **`nightscout_charts.py`** and **`nightscout_ui.py`**, **`graph_view.py`**, **`comparison_tables.py`**, **`nightscout_stats.py`**, and **`chart_cache.py`**. If you have not installed the labelled Excel import update yet, also copy `examples/profile-import.xlsx`. Keep your existing `data/profiles/` folder and `.venv` environment. No data migration or new dependencies are needed. Restart with `start.bat` or `.venv\Scripts\python.exe -m streamlit run app.py`.

## Source and tests

- `app.py`: Streamlit interface and Plotly charts.
- `comparison_tables.py`: time-aligned values and per-reference cell highlights.
- `profiles.py`: validation, interval calculations, importer and file storage.
- `editor_history.py`: in-memory undo/redo for draft changes.
- `nightscout.py`: read-only API requests, date windows and recorded-data normalization.
- `nightscout_stats.py`: equal-day continuous medians and hourly event summaries.
- `chart_cache.py`: bounded per-snapshot calculation and viewer caches.
- `nightscout_charts.py`: aligned historical panels and glucose summaries.
- `nightscout_ui.py`: manual connection, date cycling and display controls.
- `graph_view.py`: offline Plotly viewer with a pinned profile and synchronized time zoom.
- `appearance.py`: metric palette and native theme adapter for the pinned Streamlit 1.64.0. Streamlit has no public runtime theme setter; this small adapter updates its process-wide theme configuration and triggers a rerun. Recheck it before upgrading Streamlit or deploying for multiple users.
- `tests/`: regression tests for import, interval boundaries, version preservation and editor state.

Run with the installed environment:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests use temporary history folders and leave your profiles unchanged. If Node.js is installed, the viewer test also checks overlay changes, fullscreen/date navigation, median preservation, hidden-tab initialization, resize serialization and label reset with a DOM/Plotly mock. This is not a real-browser visual test.
