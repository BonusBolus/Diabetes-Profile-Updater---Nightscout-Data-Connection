# Profile Studio

## Health-37: individual graph restoration and consistent event/Insight overlays

**+ Add graph** in Data layers lists deleted base graphs and restores one with its existing settings. If its layer was deselected, selecting it again also enables that layer. This replaces the toolbar restore-all button. Restoration does not reload Nightscout/Garmin or recreate an unchanged graph iframe, so the current time window remains intact. Duplicate copies are permanently removed when deleted; create another with Duplicate when needed.

Each event type has its own **Off / Glucose only / All time graphs** selector: site changes, sensor changes, profile switches, profile-percentage shading, automation notes and activity shading. Glucose-only also includes profile/custom panels actually displaying glucose. Daily views filter events to the displayed date; median/summary and multiple-day views retain actual dated events at their time of day. These are recorded context, not average events. Elapsed-time Insights and non-time scatter plots are excluded. Automation markers still require a loaded note beginning with `Automation:`. Settings are saved with graph configurations and used by reports; older shared-scope configurations are migrated. Coincident activity intervals keep their recorded regions/colors but share one readable label identifying the types and number of dates.

Insight IOB/COB overlays now use the same **Average or Median** selection as glucose, including the within-period bin calculation. Each has its own **25–75%** band, split at missing bins and available only with at least two contributing periods. Their lines and bands are subdued; absolute/Δ glucose lines and bands use green, with the existing red out-of-range highlighting on absolute Insights. Glucose target shading follows the actual X-axis domain, preventing extension under auxiliary axes. The compact methods note reflects the selected overlay statistic.

The graph display selector now says **Multiple days / Summary** to distinguish display mode from statistical aggregation. Insight statistics explicitly say **glucose + overlays**. Other controls identify **Hourly bars**, **Step bars**, **Stress bars**, **Sleep bars** or **Restless bars**, and are hidden when the corresponding aggregate bars are not displayed. Standard daily curve/marker behavior remains unchanged apart from the requested event scope controls. Reports continue to support a maximum of six graphs per page and omit empty plots even when automation markers are present.

Validation: 44 affected regression tests passed, plus real-browser checks of daily/median/custom routing, saved settings, overlay statistics and individual restoration without reloading the viewer. Portrait and landscape HTML/PDF reports were rendered and visually checked; the six-graphs-per-page limit remains unchanged. Checks use synthetic data.

Extract **all included update files**, including the JavaScript files and `graph_component/`. Preserve data/configuration folders and `.venv/`, restart, and check **Build: Health-37**. No new dependencies.

## Health-36: concise, settings-aware Insight notes

Insight graphs now show a small, always-visible methods note below the plot; the existing expandable methods/period tables remain available. The same generated note is printed beneath each Insight in HTML/PDF reports. Notes are derived after applying that panel's settings and the report section's display mode, so copies, saved configurations and exports reflect their own cutoffs, time window, aggregation, absolute/Δ glucose, overlays and actual contributor counts.

Notes explain next-carb/replacement/sleep boundaries, including rejected carb entries ending preceding meal windows; starting-COB freshness/missing-value rules; activity/sleep confounders; gap handling; baseline exclusions; 25–75% variation versus confidence intervals; and differing IOB/COB upload coverage. Sleep relationship notes describe the actual paired metrics and following-day window. When the report has a restricted clock-hour range, elapsed-time Insights explicitly state that this crop does not apply to them. The contradictory starting-COB sentence in the longer meal methods text is corrected.

PDF captions use compact 8 px text and are measured before rendering. Their height is taken from the existing chart slot rather than added beneath it, preserving the **1–6 graphs per page** setting. Dense five/six-graph Insights use smaller graph chrome and fewer Y ticks; Insight X units appear on ticks, with the alignment described in the note. Normal interactive graphs keep their existing axes and height. No new settings or dependencies.

Validation: 29 affected regression tests passed. Real-browser checks verified note updates, seven Insight types plus a sleep relationship copy, active cutoffs and overlays, export-specific notes, and portrait/landscape reports at 2, 4 and 6 graphs per page. Rendered PDF pages were visually checked; captions fit their slots and legends do not cover X tick labels. Synthetic data was used.

Extract **all included files**, preserve your data/configuration folders and `.venv/`, restart and check **Build: Health-36**.

## Health-35: selected automation notes and Insight context

Validation: 43 affected regression tests passed. Real-browser checks covered independent overlays, inclusive zero/5 g cutoff behavior, saved/reloaded filter and overlay settings, visible/hoverable above-plot markers, and shared portrait/landscape HTML/PDF rendering without page overflow. Tests use synthetic records, not a live Nightscout account.

Extract **all included files**, preserve your data/configuration folders and `.venv/`, restart and check **Build: Health-35**. No new dependencies. Select **Automation notes** under Nightscout imports and refresh once; old snapshots do not contain note records.

Use a CarePortal note with the exact prefix `Automation:`, for example `Automation: Evening activity`. Only these explicitly tagged notes become markers; ordinary notes and inferred automation names are not included. Under **Graph settings → Events → Automation notes**, choose **Off**, **Glucose**, or **All time graphs**. Small teal diamonds above the plot show the note name and date/time on hover, without long permanent text. Actual events are omitted on median/hourly and event-aligned axes, where a specific absolute timestamp would be misleading. The same renderer and settings are used for expanded view and HTML/PDF reports.

Meal, activity, sleep and replacement-aligned glucose Insights have independent **Median IOB** and **Median COB** content toggles. Their colored U/g axes remain separate from the glucose scale and glucose normalization. Each signal uses its own uploaded timestamps, the same selected event windows and five-minute bins, one median contribution per event/bin and then the median across events. Missing bins stay missing; curves do not forward-fill outages. Hover shows contributing periods, which may differ between glucose, IOB and COB. Sleep relationship scatter plots do not display elapsed-time overlays.

**Meal-response glucose** additionally has a **Start COB filter** and **Starting COB ≤ … g** slider. The filter is off by default, preserving existing selections. At 0, only recorded starting COB equal to zero qualifies; at 5, COB ≤5 g qualifies. Starting COB is the last uploaded estimate at/before the carb timestamp, no older than ten minutes. Missing/stale starting COB is excluded while the filter is on. This is not a measurement of actual unabsorbed food. The meal summary now displays starting COB alongside starting IOB, and reports state the cutoff/missing count. Graph configurations and reports retain this filter and both overlay toggles independently for each panel.

Meal windows still start at each positive recorded carb timestamp (simultaneous entries summed) and end at the next positive carb entry, loaded-data end or the displayed window, whichever comes first. Both carb and starting-COB cutoffs affect inclusion only: even a later entry rejected by either filter still ends the preceding window. No automatic meal clustering, confounder exclusion or significance test is introduced.

## Health-34: optional daily matrices

Validation: 12 affected regression tests passed. Workspace-navigation testing confirmed zero Nightscout/Garmin load calls and reuse of the combined snapshot/cache. Real-browser checks verified that all five matrices default off, the whole panel grows/shrinks with the toggle, bars retain their values, SMB and Average/Median still work, settings survive reload/expanded view/day cycling, and deletion/restore works for summaries, custom panels, duplicates, the pinned profile and Insights. Portrait/landscape reports retained matrix visibility, excluded deleted graphs and had no overflow. Tests use synthetic records.

**Delete graph** is available on every panel, including the pinned profile and Custom Graphs. Deleted base graphs remain excluded from the layout, saved configurations and reports until **Restore deleted graphs** is used. Duplicate copies are removed completely. Source data is retained. Activity/event controls remain available after deleting the profile graph.

Hourly bolus, carb, profile-percentage, site-change and sensor-change graphs have a **Daily grid: on/off** content control. The day-by-hour matrix is **off by default**, including configurations saved before this option existed. Hiding it shrinks the entire graph to **280 px** and gives that compact plot area to the hourly bars; showing it restores the original taller layout. Average/Median, missing/partial-hour exclusions and Exclude SMB calculations remain unchanged. The setting is independent for each graph/copy, survives saved configurations and is honored by HTML/PDF reports and local date navigation.

Changing Data/Editor workspaces does **not** reload Nightscout or reread Garmin files. Source snapshots and their chart/statistics caches stay in session; only explicit load/refresh submits replace them. The combined snapshot is reused while sources remain unchanged. Viewer construction differs between Data and Editor because the latter adds profile comparisons and overlays, so graph preparation can still take time on the first switch. Revisiting an unchanged prepared view reuses the bounded cache. This update preserves that behavior.

Extract **all included files**, preserve your data/configuration folders and `.venv/`, then restart and check **Build: Health-34**. No new dependencies.

## Health-33: one replacement-bounded site Insight

**Site-age glucose** now replaces both previous site Insights. Its **Site window** setting offers **Until next replacement** (the default) or **First hours**, with the existing adjustable 0.5–72 h window. Both modes always stop at the next recorded site replacement or loaded-data end; glucose at/after that replacement belongs to the new site. Source periods are bounded before individual curves, Average/Median and the 25–75% band are calculated. Selected dates and recorded gaps remain respected.

Old layer selections resolve to this single layer. Post-site-change-only saved views retain their early-window duration; when both old base graphs were selected, the Site-age settings take precedence and no duplicate base panel is restored. Intentionally duplicated graph copies retain independent settings. Normal/expanded views, saved graph configurations and HTML/PDF exports share the same mechanism. The Health-32 carb cutoff remains available.

Extract **all included files**, preserve your data/configuration folders and `.venv/`, then restart and check **Build: Health-33**. No new dependencies.

Validation: 24 affected regression tests passed, including replacement bounds, excluded dates, strict meal cutoffs and legacy panel migration. Real-browser checks confirmed one site panel from either/both legacy selections, full/limited controls, reload and expanded view. Portrait/landscape reports restored the requested window, produced one site graph and had no overflow. Verification uses synthetic records.

## Health-32: meal-response carb cutoff

Meal-response glucose has a compact **Carbs > [amount] g** control in its graph settings. Set 20 to include only recorded entries strictly above 20 g; zero preserves all positive entries. Simultaneous entries are summed before filtering. The cutoff applies to individual curves, Average/Median, the 25–75% band and the recorded-period summary, in normal/expanded views and HTML/PDF exports. Configurations retain the cutoff independently for each graph copy. Excluded entries still end the preceding response window, so a small later carb entry cannot silently extend that earlier response. Empty selections are identified and omitted from report plots through the existing empty-plot behavior.

Extract **all files** into the existing project, preserving your data/configuration folders and `.venv/`, then restart and check **Build: Health-32**. No new dependencies.

Insight distinctions: **Site-age glucose** covers each site from its change until the next change; **Post-site-change glucose** shows an adjustable early window (up to 72 h), which currently can cross another site change. They overlap and could be consolidated into one graph with a full-lifetime/early-window setting. **Activity glucose** covers the recorded activity; **Post-activity glucose** starts at its end. **Sensor-age variability** measures glucose changes rather than the glucose level plotted by **Sensor-age glucose**. These existing layers are preserved in this update.

Validation: 20 affected regression tests passed, including strict cutoff boundaries, empty selections, cache invalidation and preservation of the next-carb window boundary. Real-browser checks verified the cutoff control, independent copies, reload, expanded view and both glucose units. Portrait/landscape HTML-to-PDF rendering retained cutoff labels without page overflow. Checks use synthetic records; no live account or personal Garmin database was accessed.

## Health-31.1: verification correction

Clock-time profile-change guides are excluded from event-aligned Insights and sleep–glucose relationship graphs. Their X axes represent elapsed hours, sleep duration or HRV, rather than minutes since midnight. This fixes a guide at 10:00 stretching an HRV axis to 600 ms, including in HTML/PDF reports. Normal clock-time profile guides are preserved. All Health-31 analysis settings and calculations remain unchanged. Check **Build: Health-31.1** after restarting.

Verification: the full 159-test suite passed in an existing-project installation fixture. After the guide correction, 24 affected tests passed, including a new regression for non-time axes. Real browser checks verified controls, independent settings, reload, expanded view, mmol/L and mg/dL; landscape and portrait reports rendered without page overflow and retained the corrected HRV axis. Additional checks covered uneven HRV sampling, DST sleep duration, missing next-day pairs and simultaneous/nonpositive carb records. These checks used synthetic records, not a live Nightscout account or your personal Garmin database.

## Health-31: meal responses, sleep–glucose relationships and fitted Insight axes

Extract all update files into the existing project, preserve your data/configuration folders and `.venv/`, and restart. Check **Build: Health-31**. Reload Garmin once to retain its explicit DB/JSON sleep-session boundaries. No new dependencies.

- Select **Meal-response glucose** under **Analysis** in a date range with glucose and recorded carbs. Every positive carb timestamp is an event; simultaneous entries are summed. Entries are not classified as actual meals. Curves align to the recorded entry and stop at the next carb entry or loaded-data end; the graph window is adjustable from 0.5–12 h. Average/Median, individual periods, 25–75% bands and Δ glucose reuse the existing Insight mechanism.
- Expand **Recorded periods · methods and summary** below the graph for carb amount, starting glucose/IOB, observed peak, rise from baseline, peak timing, observed return to 4–10 mmol/L, coverage, and nearby User/SMB/unknown bolus totals. Return means the first recorded in-range reading after an above-range peak, without bridging a gap >10 min; — means unavailable or no observed return. Nearby boluses use −30/+60 min and are context, not insulin attributed to a meal. Starting IOB uses the last uploaded reading at most ten minutes before entry. Summary metrics follow the selected window.
- Select **Sleep–glucose** when glucose and Garmin sleep data are loaded. Choose **During sleep**, **After waking**, or **Sleep → next-day glucose**. The relationship view shows one point per recorded period; X is recorded asleep duration or median recorded overnight HRV, and Y is next-day mean glucose, time in range, or time below range. Missing pairs are excluded. It deliberately has no Median/Multiple-days selector because it represents individual periods.
- Sleep episodes prefer explicit Garmin DB/JSON boundaries. If only stage records exist, consecutive intervals are grouped across gaps no longer than 30 min and the source is identified. Asleep duration counts the union of Deep/Light/REM intervals; duplicate/overlapping uploads do not double-count. Unknown stages are not declared asleep. Stage coverage is shown. HRV uses one median per observed five-minute overnight bin, then the median across those bins; it is not Garmin's official nightly average. No synthetic HRV curve is created.
- **Next-day** is defined as the interval after waking, ending at the next recorded sleep, the selected duration (0.5–24 h), or loaded-data end. Wake dates must be selected and glucose is restricted to selected dates. Night and following-window coverage are shown, including partial nights/last days. Glucose means/TIR use five-minute bin medians. These are descriptive associations, without significance tests or causal claims.
- Every absolute-glucose Insight has **Y axis: 0–20 / fitted** in its graph settings (0–360 mg/dL). Fitted uses the displayed curves/bands with a small margin. The fixed 4–10 range and red high/low coloring remain; the range band clips naturally to a fitted axis. Δ/variability do not use this absolute-glucose toggle; percentage outcomes use 0–100%. Changing display/metric/axis modes clears stale manual ranges. Settings remain independent between copies, round-trip in saved graph configurations, and are retained in exported reports.
- Interactive graphs, expanded view and HTML/PDF reports use the same analysis renderer. Original glucose, sleep, editor and configuration behavior is preserved.

Validation: all 159 regression checks passed. Browser checks cover new summaries, view/metric controls, fitted/default axes, independent copies, reload, expanded view and mg/dL. Landscape and portrait reports preserve the selected meal/sleep representations without page overflow.

## Health-30: glucose styling for event-aligned Insights

Extract all update files into the existing project, preserve your data/configuration folders and `.venv/`, and restart. Check **Build: Health-30**. No new dependencies.

- Absolute **Sensor-age glucose**, **Site-age glucose**, **Activity glucose**, **Post-activity glucose** and **Post-site-change glucose** use the fixed green **4–10 mmol/L** band (72–180 mg/dL). Both low and high points are red; the Average/Median reference is green within range and red outside it. The default Y-axis is 0–20 mmol/L (0–360 mg/dL), expanding for higher displayed readings. Explicit panel axis ranges still take precedence.
- Elapsed-time axes, faint blue individual event curves and the blue 25–75% band distinguish Insights from ordinary clock-time glucose graphs. Average/Median, duplicated panels, saved configurations, expanded view and HTML/PDF exports use the same transform. Ordinary glucose colors are unchanged.
- **Δ glucose from t=0** and **Sensor-age variability** retain their own scales without an absolute-glucose range. The methods note explains that 25–75% describes variation between periods, not a confidence interval or a significance test. Insights still require glucose plus recorded source events; missing observations and unavailable baselines remain excluded.

Validation: all 155 regression checks passed. Browser checks cover absolute/Δ switching, independent copies and expanded view. Landscape and portrait HTML/PDF rendering preserves the band and red excursions without page overflow.

## Health-29: profile overlays, compact sidebar and sleep-stage medians

Extract all update files into the existing project, keep your data/configuration folders and `.venv/`, and restart. Check **Build: Health-29**. No new dependencies.

- Nightscout profile history is loaded on every explicit Nightscout refresh, independent of the import chips. The event chip is now **Site / sensor events**. Full treatment imports reuse their profile records; other imports request only profile history and its starting state. Profile overlays and profile-percentage analysis no longer depend on selecting treatment layers.
- Switch names and percentages use separated vertical levels. Label placement is refined using Plotly's measured plot width after axes/automargins, including resizing, expanded view and PDF rendering. Purple percentage shading uses a constant 14% opacity, with its height indicating the percentage; 100% remains unshaded.
- The sidebar has paired From/Through date controls, a compact workspace selector, tighter spacing and fewer explanatory captions. Import, refresh, configuration, warning and status controls remain available.
- Graphs without a median representation no longer show a Median/Multiple-days selector. Temporary targets retain their actual multi-day intervals. Profile-only/target-only custom graphs also keep the multi-day view; copied profile graphs retain independent overlay choices.
- Median hourly sleep now has stage colors and legends. The median **total asleep duration** is calculated across recorded dates, including zero sleep in an hour on those dates. It is divided among Deep/Light/REM using the recorded duration-weighted stage mix for that hour. These colored portions are **not independent stage medians**: such medians can sum to more than an hour, or all become zero despite everyone sleeping. Awake uses its median recorded duration. Hover identifies this calculation. Average stage durations and conditional stage composition are unchanged.
- Simple hourly sleep bars occupy the same report slot in Average and Median, respecting graphs per page. Recorded multi-day sleep timelines and additional underneath metrics retain their extra space. Compact sleep-axis titles fit within the exported graph.

Validation: 153 automated regression checks passed. Browser checks verified stage colors, 0–1 hourly sleep range, independent saved overlays and non-overlapping switch names after resizing. Average and Median sleep exports have identical one-slot sizing; landscape and portrait reports render without clipping.

## Health-28: import chips, separate Insights and year-long reports

Extract **all** update files into the existing project, preserve your `data/`, `examples/`, `graph_configurations/`, `report_configurations/` and `.venv/`, then restart. Check **Build: Health-28**. No new application dependencies.

- Nightscout and Garmin imports use compact chips with **Select all**, matching Data Layers. Import choices remain separate from visibility. Successful loads automatically enable the populated requested layers; manual visibility changes do not reload data. Related Nightscout layers share API collections, so related records may be available too.
- **Median** is the default per graph for two or more dates. Single-day viewing is unchanged. Individual graph choices, copies and saved configurations remain independent; explicit saved modes are preserved.
- Six separate analysis chips: **Sensor-age glucose**, **Sensor-age variability**, **Site-age glucose**, **Activity glucose**, **Post-activity glucose**, **Post-site-change glucose**. They appear only for multiple dates with the required source records. Old saved `Insights` selections expand to these chips. Each graph defaults to Median and has an **Average / Median** reference-curve selector. Each event contributes one statistic per time bin before events are aggregated, so dense uploads do not give an event extra weight. Multiple-days mode keeps the individual periods alongside the chosen reference curve. Sensor variability offers rate magnitude and jumpiness.
- Sensor-age axes end near the last finite aligned observation of the selected signal, with a small margin. Unknown sensor changes are never invented to shorten an age. Activity-aligned graphs have compact legends, useful Y autoscaling, consistent heights, and explicit gap breaks.
- Profile percentage shading is subtle purple. Its height is proportional to the percentage: 50% covers half the plot's Y height, 80% covers 80%, and percentages above 100% extend into reserved headroom. The 100% state has no shade. Close labels use three compact levels, with nearby names offset along their level when needed; hover retains each exact event. Median graphs continue to use percentage summaries rather than individual switch events.
- Multi-day Sleep uses **`SLEEP_DAY_HEIGHT = 28`** pixels per recorded date, shared by stage sizing and viewer layout. Single-night stage bars remain large. Hourly sleep distribution now uses **24 actual hourly stacks** with consistent widths and gaps, rather than repeating each statistic in adjacent five-minute bars. Average stacks show stage hours per included date; Median retains the representative total asleep duration. Conditional stage composition remains available.
- **Location presentation is disabled.** Supported GarminDB coordinates and FIT GPS samples are tied to activities; these cannot establish a reliable location timeline outside activities. Activity labels no longer show coarse areas or cities. No geocoder, invented location changes or route display has been added. The unused coordinate-label helper is retained for a possible future data source.
- Performance: unchanged FIT files keep their signature-keyed parse cache; only selected Insights are prepared; glucose normalization, event lookup and aggregation are reused; graph preparation reuses already-built mode/overlay banks; reports avoid constructing an unused alternate mode. Explicit refresh still rereads source data. These improvements do not discard observations or downsample source records.
- **PDF/HTML reports support up to 366 dates**, within the loaded range. Load the desired range first. Reports prepare charts sequentially, omit empty plots, and retain the existing layouts, graph settings and saved export presets. Long sleep overlays are split into readable date groups across pages. Dense profile annotations use additional page slots to keep the data region readable. Daily statistics use indexed time slices. A year of Daily graphs can create hundreds of pages and take longer than summary-only sections.

Validation: 149 automated regression checks validated, plus browser checks of saved graph copies, axes, filters and Insight aggregation. Synthetic 366-date reports rendered without clipping in landscape and portrait, including paginated statistics and multi-day sleep. Live Nightscout accounts and your local Garmin files were not used in these checks. A focused annual sensor/site analysis benchmark improved from 29.5 to 1.53 seconds for 105,120 readings, preserving the aligned values and exposure statistics; this measures that analysis pipeline, not total app or network loading time.

## Health-27: independent graph modes, duplicates and event-aligned Insights

Extract **all** update files into your existing project. Preserve `data/`, `examples/`, `graph_configurations/`, `report_configurations/` and `.venv/`. Restart and check **Build: Health-27**. No new dependencies.

- Choose **One day** or **Date range** in the sidebar. For two or more dates, each graph has its own **Multiple days / Median** control in its settings box. Activity selection and shared time zoom leave these modes unchanged. The pinned profile overlay also has its own mode control.
- **Duplicate** copies the profile graph, a recorded graph or a Custom Graph, including its current mode, overlays, filters and manually adjusted Y-axis ranges. Copies can be edited and removed independently. Saved graph configurations retain copies, their order, contents and settings. Legacy configurations still load.
- Profile switches use distinct dashed styles, a percentage above the line and base profile name below. Close switches keep their hoverable lines but share limited annotation space. Median graphs use the hourly profile summary instead of pretending an individual switch is a median event. Site/sensor/profile hourly summaries and Insights are unavailable for a single date.
- Median Sleep defaults to stage-colored, aligned stacks showing **hours recorded per clock hour per included date**, on a 0–1 hour scale. For example, one hour of sleep at noon on one of two recorded dates contributes 0.5 h at noon. Dates without any stage records are excluded; the other clock hours within recorded dates contribute zero. The five-minute drawing bins repeat the clock-hour statistic; they do not invent finer observations. Conditional stage composition (%) remains optional.
- **Insights** adds sensor-age glucose, variability `|ΔBG/Δt|` and jumpiness `|Δ slope|`; site-age glucose; glucose during/after activity; and glucose after site changes. Each offers individual periods or Median; post-event durations are adjustable from 0.5 to 72 h. Site summaries include CV, observed TIR (4–10 mmol/L), and trapezoidal above-range AUC over observed adjacent readings.
- Event-aligned glucose can switch from Absolute to **Δ glucose from t=0**. Normalization happens independently for every event before median/25–75% calculation. The baseline must be an exact event-time reading or be bracketed by readings no more than ten minutes apart. Missing baselines are excluded and counted. Long gaps break curves; bands require two periods. These are descriptive signal analyses, **not sensor accuracy**. Sensor uploads can represent restarts; missing event uploads cannot be inferred. Sensor/site ages keep actual elapsed time and variable recorded durations.
- Loading supports **up to 366 calendar dates**. First choose range and high-level Nightscout/Garmin categories, then explicitly load or refresh. No new read occurs merely from adjusting a control. Unselected collections/FIT/sleep sources are skipped; dated chart/statistic caches are reused between controls. Long sparse treatment windows and bounded continuous windows reduce request overhead; full response windows are split rather than silently truncated. One year can take appreciably longer than a week. PDF reports retain their existing 31-day limit.
- Where recorded Garmin city fields exist, the activity label can show the city. FIT coordinates otherwise produce one coarse regional **0.25° cell label**, not a route or precise GPS points. No external geocoder is called. Coordinates without reliable source units are not guessed. Named cities from GPS would require a local place-name database; city-level lookup is not supplied in this update.

## Health-26: compact events and multi-day distributions

Extract all update files into your existing project, including `event_stats.py` and all JavaScript files. Preserve `data/`, `examples/`, `graph_configurations/`, `report_configurations/` and `.venv/`. Restart and check **Build: Health-26**. No new application dependencies.

- Profile switches use separate line styles per base profile, with base names in the legend. Only percentages appear above the plot; hover reveals the date, base name and percentage. Close switches keep their lines but share annotation space, preventing stacks of repeated names. Actual switches are not drawn on an across-day median.
- SMB uses compact alternating triangles; manual boluses use squares; carbs use circles. Amount-based sizes have a cap, and legends use fixed-size symbols. Hover retains exact amounts, including large doses beyond the size cap.
- Event controls immediately reflect the selected state and save it with graph configurations.
- New **Profile percentage**, **Site changes** and **Sensor changes** layers use day/hour grids plus Average/Median bars. Profile percentages are duration-weighted per hour; only fully known hours contribute to the aggregate bars. Change events count explicit uploaded records. Sensor starts can be restarts, not necessarily physical replacements.
- Choose **One day** or **Date range**, then use the global Median toggle to switch all selected graphs between multiple-day overlays and median summaries. Existing saved mode strings remain supported.
- Median sleep defaults to hourly average minutes asleep, split by stage, across selected dates with known sleep-stage records. Within included dates, hours without recorded sleep contribute zero. Entire dates without stage records are excluded and are not assumed awake. Awake intervals are excluded from minutes asleep. This is a distribution of recorded sleep, not evidence of uninterrupted coverage. Hover shows the denominator. The Average/Median bar toggle also supports median hourly sleep duration (all stages combined). **Stage composition** retains the old conditional percentages among observed dates in each five-minute bin.
- Report preview appears above its download button. Reports skip plots without visible recorded values after graph settings are applied. Valid observed zeros are retained. Legends use fixed-size symbols; the existing HTML/PDF graph renderer is shared.

## Health-25: in-graph hover, effective profile events and report layouts

Extract **all update files** into your existing project, including `filled_regions.js`, `profile_events.py`, `report_config.py`, all report JavaScript/CSS and `graph_component/`. Keep `data/`, `examples/`, `graph_configurations/`, `report_configurations/` and `.venv/`. Restart and check **Build: Health-25**. No new application dependencies. Reload Nightscout after installing so the snapshot includes the updated effective-profile history.

- **Hover:** a small readout follows the selected point inside its graph. The selection outline is thinner and less prominent. The actual SMB dose is retained, along with the existing synchronized time guides. Hover values no longer occupy the overview toolbar.
- **General settings:** subtle dividers group Profile, Activity and Events controls. Site and sensor visibility can be selected independently; their existing Glucose / All time graphs / Off scope remains available.
- **Profile switches:** enable **Profile switches** and/or **Profile % shading** in Events. Only uploaded AAPS effective states establish activation times. Labels show the base profile and its percentage; consecutive states within the same base may show the percentage alone to reduce overlap. Labels include the recorded date in multi-day views. Requested switches supply base definitions but are not assumed to be active events. Controls are disabled when effective history is unavailable.
- **Percentage shading:** periods below 100% use blue, above 100% orange; opacity increases with distance from 100%. The 100% state is unshaded. Intervals stop at the next effective switch or an explicitly uploaded end, and are clipped to the loaded day and observation window. No return to 100% is invented when the corresponding record is missing. Event selections are retained in saved graph configurations.
- **Base profiles in reports:** percentage-adjusted schedules no longer produce duplicate profile definitions or pages of repeated active intervals. The base schedule comes from uploaded unmodified switch JSON or a known 100%, unshifted state. If a base schedule is unavailable, its fields are marked unavailable instead of substituting adjusted values. Distinct changes to a base schedule remain distinct definitions.
- **Shading:** disconnected filled curves and variability bands are converted to separate, explicitly closed regions after the shared graph transformations. This prevents diagonal shading across missing data in both interactive graphs and exported SVG/HTML/PDF charts. Temporary-target regions and activity/event overlays use the same renderer in both views.
- **Report layout:** choose **Landscape** or **Portrait · vertical stack**, then **1–6 graphs per page**. Plotly dimensions, axis fonts and legend spacing adapt to the available slots. Complex sleep graphs with multiple panels occupy additional slots to keep their axes readable. Page titles describe the plots on that page, including selected data in custom graphs.
- **Saved PDF settings:** in **Export report**, enter a preset name and click **Save PDF settings**. Select it later from **Saved PDF settings**. Presets are JSON files in `report_configurations/` and restore title, dates, daily time window, sections, orientation and page capacity. They are separate from graph configurations; the report still uses the currently selected graphs. Dates outside the loaded snapshot must be adjusted or loaded first.
- **Valid selections:** median and multi-day pages are disabled for a one-day export. Options requiring Nightscout records or profile history are disabled when that source is unavailable. Invalid dates/time windows and ranges over 31 days disable report preparation.

Export remains **Prepare report → download/open the HTML preview → Print / Save as PDF**. Select A4 and the orientation chosen in the report; disable browser headers/footers.

Validation: 132 automated regression checks passed. Browser checks cover actual point hovering, PDF preset save/reload, single-day option prevention, and report settings capture. Four-slot portrait and landscape reports were rendered and visually checked, including filled curves with missing sections and sleep/custom graphs. Testing used synthetic records, not your live Nightscout account.

These notes take precedence over earlier releases below.

## Health-24: report export and site/sensor change markers

Extract **all update files** into your existing project, including the new `report_*.py`, `report_*.js`, `report_document.css`, and `graph_component/` files. Keep `data/`, `examples/`, `graph_configurations/` and `.venv/`. Restart and check **Build: Health-24**. No new application dependencies.

- **Export report:** in the graph toolbar, choose the dates, daily time window and report sections, then **Prepare report**. Download the report preview beneath the graphs, open the HTML file in Chrome or Edge, wait for its charts, and choose **Print / Save as PDF**. Use A4 landscape with browser headers/footers disabled. The preview works offline and includes the graph renderer; there is no external reporting service.
- **Seven optional sections:** overview, used profiles, median selected graphs, daily statistics, daily graphs, all days overlaid, and glucose distribution. Small graphs share pages; larger graphs get a full page. Your selected layers, graph order, custom graphs, overlays and filters are retained. Export up to 31 loaded days per report. Time windows clip graphs; hourly bins retain whole-hour totals and cumulative steps remain totals since the start of each day.
- **Used profiles:** includes effective profiles recorded by Nightscout during the export period, with active intervals and schedules. It does not substitute the editor draft or saved profile collection. Missing profile history is identified explicitly. Reload Nightscout after installing this update to retrieve this history.
- **Core statistics:** glucose mean, minimum/maximum, SD, CV, quartiles, coverage, range percentages, recorded boluses/carbs and explicit change counts. Glucose statistics use one median per observed five-minute bin to avoid giving duplicate uploads extra weight. Range summaries show 4–10 mmol/L and 3.9–10 mmol/L, converted for mg/dL. Missing data is not filled with invented readings. Estimated A1c, GVI, PGS and other risk scores are omitted. Recorded bolus totals are not total insulin delivery.
- **Site/sensor changes:** reload Nightscout, then use **Site / sensor changes** in the general graph settings: **Glucose**, **All time graphs**, or **Off**. Blue dotted markers show explicit Site Change records; purple markers show Sensor Start/Sensor Change records. Simultaneous site and sensor labels occupy separate rows. Events are not inferred from glucose gaps or free-text notes. The selection is saved with graph configurations.
- **Local files:** the downloaded preview contains personal health data, including the selected graph data used to render the report. Credentials are excluded. Both Profile Studio and printing run on your computer; keep it awake until generation finishes.

Validation: 128 automated checks passed (full regression suite plus the final report checks). A synthetic report covering all seven sections was rendered in Chromium, printed to a 34-page PDF and checked for clipped page content. Export controls were also exercised in the browser. Your live Nightscout installation was not accessed for these tests.

These notes take precedence over earlier releases below.

## Health-23: clear hover selection and a compact overlay dropdown

Extract all update files into your existing project. Keep `data/`, `examples/`, `graph_configurations/` and `.venv/`. Restart and check **Build: Health-23**. No dependency changes.

- **Top overlay selection:** a single dropdown replaces the many overlay buttons. All datasets, saved selections, same-axis controls and expanded-view behavior remain available.
- **Selected point:** the hover outline follows the actual rendered event marker. This accounts for the offset and alternating direction of SMB triangles, and outlines user bolus and carb markers at their visible positions. Bars, sleep stages, heatmap cells and line points retain their existing selection highlights.
- **Readout:** the selected value is larger, boxed and briefly emphasized. The series name has a matching color accent. The readout always describes the selected point; SMB uses its recorded dose, not its plotting baseline. Reduced-motion preferences disable the emphasis animation.
- **Normal-view scrolling:** when the toolbar is clipped by the outer page, a floating copy appears at the visible upper-right edge. It updates when the outer page scrolls and disappears when the toolbar is visible again. Scrolling the recorded panels clears the previous hover so the readout cannot remain attached to a point that moved away. No manual graph expansion is required. Viewport tracking uses the app's same-origin Streamlit frames; a cross-origin third-party embed may restrict ancestor viewport access.
- **Hover performance:** rendered marker lookup is cached per plot render; hover/readout positioning is batched per animation frame and never redraws Plotly. Repeated events for the same point preserve the readout rather than restarting its animation.

Validation: 123 automated checks passed, including rendered-marker geometry, scrolling viewport calculations, overlay selection, expanded view and saved configurations. Browser rendering on your installation has not been visually verified.

These notes take precedence over earlier releases below.


## Health-22: shared activity controls and compact graph layout

Extract **all update files** into your existing project, including the JavaScript files and `graph_component/`. Keep `data/`, `examples/`, `graph_configurations/` and `.venv/`. Restart and check **Build: Health-22**. No dependency changes.

- **Loading:** dates, Nightscout credentials and Garmin inputs are submitted together in one form. Each load button makes one explicit refresh with the submitted values; typing does not load data. A failed refresh retains the last successful snapshot, and the displayed loaded-date label identifies that snapshot. Refresh all still attempts the other source if one fails. The exact reported intermittent “invalid combination” message has not been reproduced; this release hardens input submission and failure handling, rather than claiming a verified server-side diagnosis. If it recurs, capture the complete error text, without credentials.
- **Activity settings:** one Activity shading toggle beside **Fit time axis to activity** controls profile, Nightscout, Garmin and custom time graphs. Date/hour heatmaps and other non-time plots are excluded. Activity colors, labels and intervals use the same shared data. Multi-day/median shading identifies the actual recorded date; it is contextual and does not represent a median activity.
- **Preserved graph mode:** selecting or fitting an activity only zooms the shared time axis (with five minutes of padding). Median/multi-day dates and traces remain unchanged. **Full day** restores the normal time range.
- **Compact layout:** full-width horizontal overlay chips replace the narrow column; settings remain visible in a separate, subtly colored box. Empty control boxes are hidden. The profile graph is 250 px tall, and the combined graph viewer is 1040 px tall, leaving more space for scrolling recorded graphs. Expanded view still uses the available screen.
- **Axis controls:** move arrows sit above the Y-axis rail. The lower-bound slider follows the actual plot height and position, including after resizing, so it no longer extends into the legend or following panel.

Validation: 122 automated regression checks passed, including Streamlit input submission and JavaScript graph-state/Plotly schema checks. The exact reported Nightscout error and visual rendering on your machine still need confirmation.

These notes take precedence over earlier release notes below.


## Health-21: open control boxes, sidebar custom graphs and precise hover

Extract **all update files** into your existing project, including the JavaScript files and `graph_component/`. Keep `data/`, `examples/`, `graph_configurations/` and `.venv/`. Restart and check **Build: Health-21**. No dependency changes.

- **Graph controls:** Graph settings are always visible in a box above the graph on the left. Overlays have their own box on the right, including the pinned profile/glucose overlay controls. Move up/down buttons sit beside the left axis. Activity lower-axis sliders are vertical and next to that axis.
- **Smoothing:** sliders retain their position and focus while dragging. Labels use a consistent minutes-and-seconds format. Activity and custom filtering offer 5 seconds through 30 minutes, with more slider positions allocated to short intervals. A change commits when the slider is released; activity/stress changes redraw the affected panels instead of the complete stack. Saved filter values remain supported.
- **Custom Graphs:** use **Data layers → Custom → +** to create Custom 1, Custom 2, and so on. Each has a visibility checkbox and a delete button. Hiding retains its private dataset/filter/axis settings; deleting removes the panel. Named configurations include all panels and which ones are visible. The in-graph add/remove controls have moved to this sidebar section.
- **One Steps layer:** cumulative steps are the default. One day shows that day's observed running total; Multiple days overlays independently accumulated daily curves with dated legends. Median + band shows the independently calculated **Median** and **25–75%** band. **Histogram** switches to hourly step increments, with an **Average/Median** toggle for aggregate views. The histogram statistic never changes the cumulative median. A band requires at least two observed days; identical totals give a zero-width band. Missing periods before the first observation stay unknown. Held totals remain last observed values, not proof of zero steps during gaps. The old Cumulative steps layer selection maps to Steps.
- **Hover selection:** a contrasting outline follows the exact point supplying the readout, scaled to event marker size. Bars and heatmap cells receive rectangular outlines; secondary axes use their own coordinate transform. Only the selected graph's value is shown. Existing synchronized time guides remain. Hover updates are batched per animation frame, reuse cached graph bounds, and never trigger Plotly redraws. Filled bands and background annotations without hover data remain non-selectable.

The notes below describe earlier releases; Health-21 takes precedence where behavior changed.

## Health-20: independent custom panels and cumulative-step statistics

Extract **all update files** into your existing project, including the JavaScript files and `graph_component/`. Keep `data/`, `examples/`, `graph_configurations/` and `.venv/`. Restart and check **Build: Health-20**. No dependency changes.

- **Content versus settings:** dataset and annotation controls use compact chips in a **Content** area. Display controls live in collapsible **Graph settings** areas. The shared activity selector, **Fit time axis to activity**, and **Full day** are in the top Graph settings area, including expanded view.
- **Cumulative steps:** select **Garmin · Cumulative steps** as its own layer. In Multiple days and Median + band, its **Median** line and **25–75%** band are calculated from each day's independently accumulated curve, aligned to five-minute bins. They are independent of the step histogram's Average/Median setting. Both have legend entries. At least two observed days are needed for a band; identical daily totals produce a zero-width band. Missing periods before the first observation and future bins are excluded. Held totals indicate the last observed count, not proof that no steps occurred during a gap. Single-day mode retains the observed cumulative stair line.
- **Activity filtering:** the five Activity metrics use the shared low-pass filter with a **5-second to 30-minute** time constant, adjustable in five-second increments. Standard stress filtering retains its existing 1–30 minute range. Filtering changes the displayed line; variability bands retain raw quartiles.
- **Multiple Custom Graphs:** select Custom graph, then use **+ Add graph** or **+ Add custom graph**. Each panel has its own dataset chips, activity shading, speed/pace mode, per-field filtering, unit-shared or separate axes, and optional minimum/maximum axis limits. **Same axis scale** is available for one or two selected datasets with distinct axes. **Autoscale axes** clears manual limits. Each panel can be reordered or removed, including the final one; the add control remains available. Time navigation remains linked across panels. There is no fixed panel limit, although many panels increase browser rendering work.
- **Saved configurations:** all Custom Graph panels and their settings are included in the existing named configuration save/load flow. Legacy single-panel configurations and minute-based activity filters migrate automatically. Old configurations that enabled cumulative steps also select its new layer. Dates remain navigation state rather than fixed configuration dates.
- **Activity colors:** the existing low-opacity shared regions retain walking green, running orange/red, cycling blue, mountain biking brown and squash purple. Other recorded activity types keep their readable name, interval and shading with a neutral blue-grey fallback (`#90a4ae`). Unknown types are not discarded. Activities continue to come from Garmin/FIT records.

Earlier release notes below describe behavior at the time of each release; the Health-20 notes take precedence.

## Health-19: activity controls, sleep overlays and refresh all

Extract **all update files** into your existing project, including the JavaScript files and `graph_component/`. Keep `data/`, `examples/`, `graph_configurations/` and `.venv/`. Restart and check **Build: Health-19**. No dependency changes. Use **Refresh all data** beneath the load date range to reload both configured sources.

- **Activity shading:** fill opacity is now 5.5%, with subtle boundaries and readable labels. Recorded Walking is light green (`#9ccc65`), Running orange/red (`#f16a43`), Mountain biking brown (`#a96c32`), Cycling/biking blue (`#42a5f5`), and Squash purple (`#ab6bd5`). Sport/sub-sport classification and colors are shared by all graphs. Activity regions remain actual recorded intervals, not inferred exercise.
- **Activity naming and order:** user-facing Workout labels are now Activity; existing configurations and internal dataset IDs still work. Standard panels are Heart rate, Speed, Altitude, Power, Cadence. A saved custom panel order continues to take priority.
- **Low-pass:** each of those five Activity panels has its own toggle and 1–30 minute slider. It uses the existing time-aware exponential filter, resets at existing trace breaks and gaps longer than five minutes, and preserves original timestamps and source samples. Higher values mean slower smoothing. The filtered line is a display transform; median variability bands remain the raw quartiles. The same signal settings apply to profile/custom overlays.
- **Lower axis limits:** Heart rate, Speed, Power and Cadence each have a Lower slider. At 0 the existing min/max autoscale remains active. Raising it clips the lower displayed range while the upper bound follows samples within the visible time range. Move back to Auto to reset. Speed limits remain in **km/h**, including when viewing reversed **min/km** pace, where slow pace values are clipped instead. Limits do not delete samples. Existing same-scale settings and axes shared by multiple datasets retain priority.
- **Glucose activity shading:** the toggle beside **Temp targets** enables the same Garmin regions, labels and colors, including in expanded view and a glucose/profile overlay. It starts off. Actual activity intervals remain hidden behind across-day median curves; selecting/fitting a day shows that day's intervals.
- **Sleep layout:** **Sleep: Underneath / Overlay** switches between the existing aligned signal rows and overlays on the stage graph. Metric selection stays unchanged. Overlay axes reuse Custom Graph's compact colored axis lanes; the two respiration signals share their unit scale and both names appear on it. Sleep stages remain visible with reduced opacity beneath the signals, with the stage legend below. Single-day, multiple-day and median modes use the same mechanism.
- **Refresh all data:** performs one explicit read of each configured source using From/Through and current connection inputs. It refreshes Nightscout records and rereads Garmin databases/Sleep/FIT files; it is not a graph-only redraw. Editing inputs or changing layers does not fetch data. Sources can still be refreshed separately. A failure in one source is shown without preventing the other source from refreshing. Available selected display dates are retained.
- **Saved configurations:** per-signal filtering, smoothing strength, lower limits, Sleep layout/selected metrics and glucose Activity shading all round-trip with the existing configuration save/load controls. Credentials and records are not exported.


## Health-18: recovered activity regions and cumulative-step variability

Copy **all update files**, including `graph_component/` and the JavaScript files, into your existing project. Keep `data/`, `examples/`, `graph_configurations/` and `.venv/`. Restart, check **Build: Health-18**, then **reload Garmin data**. Select the parent Garmin folder containing `DBs` and `FitFiles` so activity FIT sessions are available. No new dependencies.

- **Shared activity shading:** each recorded activity supplies one faint, labeled region at the same start/end time on every Garmin panel and Garmin custom/overlay graph. Recorded sport/sub-sport supplies the type; unknown types stay explicitly unknown. Repeated types have separate labels, for example **Running 1** and **Running 2**, with the same color. Each activity remains separately selectable.
- **Interval recovery:** FIT sessions with missing/invalid end timestamps now use recorded elapsed duration. Valid timestamps retain priority. GarminDB summaries similarly use elapsed duration, then the last sample explicitly linked by activity ID when no valid duration/end exists. That final fallback is an observed bound, not a guaranteed exact workout finish. Matching FIT sessions replace DB parent summaries without removing unrelated overlapping activities. No episodes are inferred from heart rate, steps or pace.
- **Zoom controls:** the graph toolbar shows the recorded activity selector, **Fit time axis to activity**, and **Full day**, including in expanded view. Fit applies the selected interval plus five minutes of padding to all linked time graphs. If no valid intervals are available, the controls remain visible but disabled with an explanation; the Garmin source inventory reports the interval count. Across-day medians have no actual-activity shading; fitting an activity first opens its recorded day.
- **Cumulative steps 25–75% band:** available with Cumulative steps in both Multiple days and Median + band. The band uses quartiles of the independently accumulated per-day curves, with stepped edges. Average/Median changes the centerline, not the quartiles. At least two observed days must contribute to a band; no pre-recording zeros or future-day totals are invented. Held totals remain observed counts, not proof of zero steps during gaps.

The missing-region cause cannot be confirmed for an individual private data set without inspecting its activity metadata. The importer fixes above are covered by synthetic GarminDB/FIT regressions, including the repeated-parent-timestamp case.

## Health-17: activity focus, grouped sleep and consistent data layers

Copy **all update files**, including `graph_component/` and the JavaScript files, into the existing project. Keep `data/`, `examples/`, `graph_configurations/` and `.venv/`. Restart and check **Build: Health-17**. No dependency changes from Health-16.

### Activity and workout graphs

- Workout axes follow the **visible** samples, with a 6% margin (a small nonzero margin for constant values). They rescale when you zoom, change dates or switch speed/pace. Shared-axis settings still take priority.
- The old **Activities** graph was a constant “Exercise” strip, not an activity measurement. It has been removed from standard/custom selection. Recorded DB/FIT activity intervals now supply the same faint, labelled backgrounds to all Garmin panels and Garmin overlays/custom graphs. No activity is inferred from heart rate or steps.
- Choose a recorded activity beside **Fit time axis to activity** in the graph toolbar. The button sets every linked time axis to that interval plus five minutes on either side. **Full day** restores 00:00–24:00. These controls work in expanded view. Selecting an activity from a median/multiple-day view first opens its recorded day. Activities crossing midnight have one selectable part per calendar day.
- Actual activity intervals are not shaded behind across-day median curves. Multiple-day views show each selected day's recorded intervals at their time of day.

### One Sleep layer

Sleep stages remain the main visualization, with a larger stage ribbon and an always-visible key below the graph. **Sleep overlays** enables Movement, Restless moments, Respiration, Resting heart rate, Pulse Ox, Sleep respiration and Overnight HRV in aligned rows inside this same graph. All start off for a clean stage view; unavailable signals are disabled. The same controls work in daily, multi-day and median views.

- **Respiration:** monitoring respiration samples inside recorded sleep sessions.
- **Sleep respiration:** Sleep JSON respiration where present, otherwise the existing monitoring-derived sleep values. These two options can contain the same observations.
- **Resting heart rate:** the recorded **daily reference**, drawn only over the associated sleep session and explicitly labelled. It is not an overnight heart-rate curve.
- **Pulse Ox / Overnight HRV:** actual timestamped samples within known sleep intervals. Daily-only summary values remain in the overview; they are not expanded into artificial curves.
- Movement intervals are weighted by their duration for median bins. Restless moment values use bars, with recorded values summed within each bin. Missing bins are not asserted to contain zero restless moments.
- Garmin breathing variations remain an available nightly category beneath Sleep, not an invented continuous signal.

### Stress, aggregation and gaps

Stress bars are slightly wider and more defined. **Line** keeps the colored line option; **Low-pass** always draws a line. The smoothing slider sets the exponential time constant from **1 to 30 minutes**, default 5. Higher values smooth more. Gaps over five minutes still reset it. In a median view the filtered line is the display-filtered median curve; the shaded band remains the raw 25–75% spread.

**Bars: Average / Median** controls Garmin aggregate bars and cumulative steps. Steps in both Multiple days and Median + band default to Average. Each day's observed cumulative total is calculated first, held between observations, and only then averaged or median-aggregated by five-minute bin. Missing pre-observation periods and future bins are excluded. Flat held portions indicate the last known total, not proof of no steps. Sleep stage percentages and other continuous median curves retain their previous aggregation.

HRV and other Garmin variability bands now use separate polygons for contiguous populated bins, so they cannot connect across missing daytime data. The screenshot's **`Â·`** (“A_hat”) was a UTF-8/Windows decoding error in JavaScript labels, not a data field. All JavaScript sources are now read explicitly as UTF-8.

### Layers and saved configurations

The sidebar has separate **Diabetes**, **Garmin** and **Custom** selectors, followed by named saved configurations. The standard graph order is:

- Diabetes: Glucose, COB + Carbs, IOB + Boluses, Temporary Basal, Temporary Targets, Variable Sensitivity.
- Garmin: Steps, Heart Rate, Workout, Stress, Sleep, Respiration outside sleep.

HRV and Pulse Ox are inside Sleep; raw fields remain available in custom graphs. **Nightscout Targets** is renamed **Temporary Targets**. Panel reordering still works. Existing saved configurations migrate renamed/grouped layers and old panel identities; old HRV/SpO2 selections activate the corresponding Sleep overlays. New saves also retain sleep selections, aggregation, smoothing enabled/disabled and filter strength. Dates and activity zoom are navigational state, not frozen into a named configuration.

---

The following sections are historical release notes; the newest release takes precedence where behavior differs.

## Health-16: named views, raw Garmin exports and detailed activity timelines

Extract **all files and the `graph_component/` folder** into the existing project. Keep `data/`, `examples/` and `graph_configurations/`. Restart and check **Build: Health-16**.

This release adds `fitdecode` for local FIT decoding. The updated `start.bat` / `start.sh` installs it if missing. If you launch manually, first run `python -m pip install -r requirements.txt` using the same Python environment as Streamlit.

### Save and reload graph configurations

Enter a name next to **Save configuration** in the graph toolbar, then save. The app writes a JSON file directly into the project's **graph_configurations/** folder. Saved names appear as buttons immediately below **Data layers**; clicking one applies it. Reusing a name (case-insensitive) updates that view. No manual download/import is required. These files are excluded from git by default.

Saved settings include layers, mode, custom fields, graph order, overlays, scales and display toggles. Credentials, source paths, dates and health records are not stored. As before, custom profile fields refer to the currently selected references/draft, not a frozen copy of a profile. Missing/unavailable fields are omitted.

### Garmin connection and source details

Select the **HealthData** folder containing **DBs**, **Sleep** and **FitFiles**. An existing path directly to **DBs** also resolves to its parent for the exports. Measurement units are fixed to **Metric**, as requested. The source files are read-only and refresh remains manual.

- `DBs/`: existing health timelines and activity summaries.
- `Sleep/sleep_YYYY-MM-DD.json`: recorded stages (including Awake), movement intervals, restless moments, respiration, awake/restless counts and available nightly breathing/restlessness labels. GMT fields are interpreted as UTC, independent of the DB's local timezone.
- `FitFiles/Activities/**/*.fit`: activity sessions and native workout records. FIT speed is converted from m/s to km/h; power is W and altitude is metres. Explicit enhanced speed/altitude fields take priority over legacy or decoder-synthesized values. Native UTC timestamps, recorded zeros and timer boundaries are retained. Corrupt files are reported while valid DB data remains available.
- Matching raw exports take priority over the corresponding DB time window for each populated field. Missing raw fields do not erase usable DB measurements. Raw files are not uploaded or modified.

The source inventory shows how many Sleep JSON nights and activity FIT files contributed. Missing fields stay absent. This importer reads **activity** FIT exports; it does not parse all monitoring FIT files. Monitoring data continues to come from GarminDB.

### Graph changes

- **Stress:** bars or a colored line; the optional five-minute low-pass always renders a line. Blue is 0–25, orange 26–75 and red 76–100. The histogram is removed. Filtering is display-only and resets after gaps longer than five minutes.
- **Cumulative steps:** the last observed total is held horizontally until another observation, and through the loaded portion of the day. A flat held segment during a data gap does **not** prove that no steps occurred. Hourly totals are unchanged. Median cumulative curves use each day's held observed totals.
- **Sleep:** thicker stage bars and a persistent colored stage key below the graph. Movement, restless moments and respiration appear as aligned rows inside the same sleep graph when available. Awake remains its original sleep-stage color. Additional nightly labels appear below the graph on the dates the sleep session overlaps.
- **Breathing variations:** the verified source field is `dailySleepDTO.breathingDisruptionSeverity`, a nightly category. The app displays that original category as a label; it does not invent a breathing-variation time series or infer one from respiration rate. If the watch/export omits it, no category is assumed.
- **Activities:** stronger, sport-colored shading on all Garmin day-view panels, Garmin profile overlays and custom graphs containing Garmin fields. Date navigation filters shading to the selected day. Actual episodes are not shaded onto an across-day median as if they happened every day.
- **Workout detail:** day views preserve native samples and sub-minute timestamps, replacing the earlier one-/five-minute binning. Timer boundaries and gaps over 30 seconds break lines. Days above 12,000 samples retain temporal bucket minima/maxima to bound payload size. Across-day median views intentionally keep five-minute statistical bins. Higher resolution exposes recorded detail; it cannot improve sensor accuracy.

Verified against GarminDB's importer and schema, go-garmin's `sleep_svc.go`, garth's public sleep fixtures, and fitdecode's documented field API. Tests use synthetic Sleep JSON and CRC-valid FIT records, configuration file round trips, Streamlit callbacks, and JavaScript graph/bridge lifecycle checks. The user's own export files and desktop-browser appearance have not been validated.

## Health-15: shared dates, saved views and Garmin display controls

Historical release notes below describe earlier behavior. For saved configurations, Garmin sources and display controls, the Health-16 instructions above take precedence.

Extract this update into the existing app folder and restart. Check **Build: Health-15**. Keep `data/` and `examples/`. All Python and JavaScript files in the archive are required. No new dependency is needed.

### Dates and configurations

- A single **Load date range** now appears before Nightscout credentials and the GarminDB folder. Each source's manual refresh reads that range. Changing dates alone does not fetch data.
- The calendar includes dates covered by either loaded source. Garmin is no longer clipped to the Nightscout range. Outside Nightscout's loaded range, treatment totals/histograms and glucose coverage remain unavailable, not zero.
- Locally navigated dates, graph options, custom selections and panel order survive adding/removing data layers. An explicit sidebar calendar selection or view-mode change takes precedence. This uses browser session storage; if browser storage is disabled, local state cannot survive an iframe rebuild.
- **Save configuration** in the graph toolbar downloads `Profile-Studio-view.json` in one click. **Data configuration → Load configuration → Apply configuration** reloads it. Included: selected layers, view mode, order, custom fields, overlays, scale toggles, SMB/target toggles, hourly statistics, and Garmin display options.
- Configurations exclude credentials, folder paths, dates, health records and saved profiles. Profile fields in custom graphs refer to the current draft/references when reopened; the file does not switch reference profiles. Unavailable fields are omitted.

### Garmin display

- **Heart rate:** starts at 35 bpm, or lower if an actual measurement requires it. Running, cycling, walking and other recorded activities shade HR and steps with consistent activity colors. Activity names form a key below each graph. Actual exercise intervals are not drawn behind across-day median curves.
- **Stress:** blue at 0–25, orange at 26–75, red at 76–100. The graph offers **Low-pass · 5 min** and **Histogram**. Low-pass is an optional, first-order exponential display filter: `alpha = 1 - exp(-dt/5 minutes)`. It resets after missing samples/gaps longer than five minutes and never fills them. This is not Garmin's internal stress algorithm. Histogram bins count observed display samples (one- or five-minute bins); in median view, they count the median bins. It is not a full-day time budget.
- **Steps:** switch between observed hourly totals and a cumulative line. The latter sums the same observed increments, resets each day, and leaves long gaps blank. Missing increments are excluded, so it can be lower than Garmin's complete daily total. In median view, the cumulative line is the median of each day's cumulative observed counts at recorded five-minute bins.
- **Sleep:** a single stage-colored bar per date with a stage legend. Multiple dates use separate rows. Gaps remain unknown. Median mode retains observed-stage percentage bars. **Sleep respiration** is shown in an aligned panel when actual respiration samples fall inside recorded sleep-stage/session intervals; samples outside known intervals are excluded. Daily average respiration remains in the overview.
- **Workout:** one layer adds activity intervals plus aligned speed/pace, power, cadence, elevation and activity-HR panels. Each panel can be reordered. Choose Metric or Statute when loading GarminDB; the speed toggle then switches **km/h ↔ min/km**, converting mph if needed. Zero-speed samples have no finite pace. Missing power is explicitly labelled. Workout respiration/temperature and individual workout fields remain available in custom graphs and overlays.
- Workout HR and all-day HR are different source streams: `activity_records.hr` versus `monitoring_hr.heart_rate`. The physiological quantity is the same, but sampling and sensor source may differ, so they are retained separately.
- **SMB:** successive triangles alternate above/below the zero baseline, offset in pixels, while marker area stays proportional to dose. The timestamp and actual dose remain unchanged. Direction/offset does not mean positive versus negative insulin. Dense events can still overlap; zoom preserves their exact times.

### Extra source data and limits

This connection reads DBs only. Standard GarminDB's `sleep`/`sleep_events` schema contains sleep stages, awake duration and summary values, but no breathing-variation or restlessness timeline. Awake stages are not substituted for restlessness, and variation in respiration rate is not relabelled as Garmin's breathing-variation score. Standard `activity_records` also lacks power; a populated `power` column is supported if present in a customized DB.

GarminDB retains original **Sleep JSON** and **FitFiles** exports. These are useful for fields not retained in the database, device-specific measurements, and rebuilding databases. Exactly which extra sleep fields are present depends on the watch/export. A separate importer requires a representative Sleep JSON or FIT sample/schema; it is not enabled by this update. No folder is scanned beyond the selected DBs folder.

References: [GarminDB](https://github.com/tcgoetz/GarminDB), its `garmindb/garmindb/garmin_db.py` and `activities_db.py` schemas and `import_monitoring.py` importer; [Garmin stress scale](https://support.garmin.com/en-IE/?faq=WT9BmhjacO4ZpxbCc0EKn9).

Validation uses synthetic databases, Streamlit application tests, JavaScript DOM/Plotly lifecycle mocks and Plotly schema validation. The user's actual databases and desktop-browser appearance have not been validated.

## Health-14: GarminDB, health-data workspace and aligned SMB markers

Extract the update into your existing app folder, replace the app files and restart. Check **Build: Health-14**. Keep your existing `data/` and `examples/` folders. This update adds no dependencies and does not change any saved profile or source database.

### Use GarminDB

1. Open **GarminDB data** in the sidebar.
2. Enter the folder containing `garmin.db`, `garmin_monitoring.db` and/or `garmin_activities.db` (typically `C:\Users\your-name\HealthData\DBs`). Files are read on the computer running Streamlit.
3. Set the timezone used by GarminDB's local timestamps and its measurement system (Metric or Statute). If unknown, units remain labelled as database units; values are never silently converted.
4. Select up to 366 dates and press **Load / refresh Garmin data**. Refresh after GarminDB has finished updating. The source connection is read-only; it does not log in to Garmin or run GarminDB downloads.
5. Choose populated **Garmin · …** layers or **Custom graph**. Fields are also available on profile overlays and in expanded view. Use `GARMINDB_FOLDER` as an environment variable for a persistent default folder; otherwise the entered path lasts for the browser session.

Supported timelines: heart rate, stress, steps, respiration, SpO₂, HRV samples, sleep stages, recorded activities, and available workout heart rate, respiration, cadence, speed, altitude and temperature. Daily values from `daily_summary`, `sleep`, `resting_hr`, `weight` and `hrv`, including Body Battery summaries, appear in the graph's expandable overview. Activity summary details appear there too. Only populated supported columns are exposed; newer or plugin-specific tables are not automatically interpreted as health measurements. No personal database upload is required.

- **Sleep:** categorical intervals at their recorded times, split at midnight. Missing periods stay blank; they are never called awake. A session with start/end but no stages is labelled “stages unavailable.” A partly recorded session's gaps remain gaps. In median mode, five-minute stacked bars show stage percentages among observed nights, excluding missing coverage. Unknown-stage sessions do not enter those percentages.
- **Steps:** hourly totals from successive cumulative counters per activity type/day. First observations, counter resets and intervals over 20 minutes are not assigned to an hour. These partial observed totals can be lower than the complete Garmin daily total, which remains in the overview. No missing hour is filled with zero.
- **Other numeric timelines:** daily traces preserve gaps; multiple-day medians and 25–75% bands use one within-bin median per day. Display samples use one-minute bins, or five-minute bins when more than seven days are loaded, to limit browser payload size.
- **Activities:** recorded exercise intervals, even in median mode. They are not averaged into a fictitious workout.
- **Time:** ambiguous/nonexistent naive local timestamps during DST are omitted with a warning. Stored timestamps without original offsets cannot reliably resolve travel or repeated hours. Check a known workout against Nightscout before interpreting alignment.
- **Calendar:** G marks dates with Garmin records. Hover explains which sources cover a date. With both sources loaded, the shared viewer includes the union of their loaded ranges. Garmin-only dates require no Nightscout connection.

### View health data

Choose **Workspace → View health data** to browse recorded data without profile overview, reference selectors, draft controls or a pinned profile graph. Display timezone and glucose units are independent controls. The graph toolbar retains the calendar, previous/next day, expanded view, custom graphs and panel reordering. Daily summaries remain available. Switching workspaces preserves the draft.

### SMB display

SMB triangles now share the zero baseline: their **area is proportional to dose** with a consistent scale across dates. Actual doses stay in hover and all source data/statistics. A compact size key illustrates 0.05, 0.2 and 0.5 U. Markers are not capped into indistinguishable large sizes. User boluses remain rectangles with numeric labels; hourly bolus totals and the Exclude SMB controls are unchanged. Closely spaced SMBs may still overlap—zoom in to distinguish exact event times. This drawing convention applies in normal, expanded, overlay and custom graphs.

### Validation and limits

Verified using synthetic SQLite fixtures based on GarminDB's public schema, Streamlit app tests, Plotly schema validation, and JavaScript DOM/Plotly lifecycle tests. Your personal database and an actual desktop browser rendering have not been inspected here. The importer does not modify AAPS, configure cloud backups or change insulin profiles. All data is descriptive recorded context.


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

Close the app, then copy **all files in this update**, including the `.js` files, `graph_component/` folder, requirements and launchers, into your existing app folder. Keep your existing `data/`, `examples/`, `graph_configurations/` and `.venv` folders. No profile migration is needed. Health-16 adds `fitdecode`; `start.bat` installs it if missing. If launching manually, first run `.venv\Scripts\python.exe -m pip install -r requirements.txt`, then `.venv\Scripts\python.exe -m streamlit run app.py`.

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
