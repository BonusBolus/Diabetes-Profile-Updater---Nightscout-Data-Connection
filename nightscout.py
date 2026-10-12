"""Read-only Nightscout V1 client and recorded-data normalization.

API reference: https://github.com/nightscout/cgm-remote-monitor/blob/master/lib/server/swagger.yaml
All times are stored in UTC. No settings or treatments are written to Nightscout.
"""
from datetime import date, datetime, time, timedelta, timezone
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

import pandas as pd

UTC = timezone.utc
PAGE_SIZE = 1000


class NightscoutError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward a token to another host or to an HTTP login page.
        return None


def site_url(value):
    value = value.strip().rstrip("/")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise NightscoutError("Enter the HTTPS Nightscout site URL without a token, login details or query parameters.")
    if "/api/" in parts.path or parts.path.endswith("/api"):
        raise NightscoutError("Use the Nightscout site URL, not an API endpoint.")
    return value


def timestamp(value):
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return datetime.fromtimestamp(value / 1000, UTC)
        if not isinstance(value, str):
            return None
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(UTC) if result.tzinfo else None
    except (ValueError, OverflowError, OSError):
        return None


def numeric(value):
    try:
        result = float(value)
        return result if not isinstance(value, bool) and math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def utc_bounds(first, last, zone):
    tz = ZoneInfo(zone)
    if not isinstance(first, date) or not isinstance(last, date):
        raise NightscoutError("Select both a start date and an end date.")
    if first > last:
        raise NightscoutError("The end date must be on or after the start date.")
    if (last - first).days >= 366:
        raise NightscoutError("Load up to 366 days at a time.")
    return (datetime.combine(first, time.min, tz).astimezone(UTC),
            datetime.combine(last + timedelta(days=1), time.min, tz).astimezone(UTC))


def _iso(value):
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class NightscoutClient:
    def __init__(self, url, token):
        self.url = site_url(url)
        self.token = token.strip()
        self.opener = build_opener(NoRedirect())

    def get(self, collection, parameters):
        params = dict(parameters)
        if self.token:
            params["token"] = self.token
        request = Request(self.url + "/api/v1/" + collection + ".json?" + urlencode(params),
                          headers={"Accept": "application/json", "User-Agent": "Profile-Studio"}, method="GET")
        try:
            with self.opener.open(request, timeout=20) as response:
                data = json.load(response)
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise NightscoutError("Access denied. Check your Nightscout read-only token.") from None
            if 300 <= exc.code < 400:
                raise NightscoutError("Nightscout redirected the request. Enter its final HTTPS site URL.") from None
            raise NightscoutError(f"Nightscout returned HTTP {exc.code} for {collection}.") from None
        except (URLError, TimeoutError, OSError):
            raise NightscoutError("Could not reach Nightscout. Check the URL, connection and HTTPS certificate.") from None
        except (ValueError, UnicodeError):
            raise NightscoutError("Nightscout did not return valid JSON. Check that the API is available.") from None
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise NightscoutError(f"Unexpected response from {collection}; expected a list of records.")
        return data

    def records(self, collection, start, end, filters=None):
        field = "date" if collection == "entries/sgv" else "created_at"
        def boundary(t):
            return int(t.timestamp() * 1000) if field == "date" else _iso(t)
        def window(a, b):
            batch = self.get(collection, {**(filters or {}), f"find[{field}][$gte]": boundary(a), f"find[{field}][$lt]": boundary(b), "count": PAGE_SIZE})
            # Split full result windows instead of assuming an undocumented skip
            # parameter. Half-open windows keep boundary events exactly once.
            if len(batch) >= PAGE_SIZE:
                if (b-a).total_seconds() <= 1:
                    raise NightscoutError("Too many records at the same time; the result cannot be loaded completely.")
                middle = a + (b-a)/2
                return window(a, middle) + window(middle, b)
            for row in batch:
                at = timestamp(row.get(field))
                if at is not None and not a <= at < b:
                    raise NightscoutError("The server did not honor the requested date filter. No partial result was used.")
            return batch
        rows = []
        at = start
        while at < end:
            until = min(end, at + timedelta(days=7 if collection=="treatments" else 2))
            rows.extend(window(at, until))
            at = until
        return rows


def normalize_data(entries, treatments, statuses, start, end):
    points = {key: [] for key in ("glucose", "bolus", "carbs", "iob", "cob", "variable_sens", "changes", "automation_notes")}
    temps, targets, warnings = [], [], []
    rejected = 0
    def add(key, at, value, label=""):
        nonlocal rejected
        value = numeric(value)
        if at is None or value is None:
            rejected += 1
        elif start <= at < end and (key == "iob" or value >= 0):
            points[key].append({"time": at, "value": value, "label": str(label)})
    seen = set()
    for row in entries:
        if row.get("isValid") is False:
            continue
        value = numeric(row.get("sgv"))
        if value is not None and value > 12:  # Low numeric status codes are not glucose readings.
            add("glucose", timestamp(row.get("date")) or timestamp(row.get("dateString")), value)
        else:
            rejected += 1
    for row in treatments:
        if row.get("isValid") is False:
            continue
        identity = row.get("_id")
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        at = timestamp(row.get("created_at")) or timestamp(row.get("date"))
        event = row.get("eventType", "Treatment")
        # Only explicitly tagged notes are automation markers; never infer an
        # automation execution from ordinary treatments or user-entry logs.
        note = row.get("notes")
        if isinstance(note, str) and note.strip().lower().startswith("automation:"):
            label = note.strip().split(":", 1)[1].strip()
            if label:
                add("automation_notes", at, 1, label)
        if event in ("Site Change", "Sensor Start", "Sensor Change", "Insulin Change"):
            add("changes", at, 1, event)
        for field, key in (("insulin", "bolus"), ("carbs", "carbs")):
            if numeric(row.get(field)) is not None and numeric(row[field]) > 0:
                if key == "bolus":
                    kind = str(row.get("type", row.get("bolusType", ""))).upper()
                    if kind == "PRIMING":
                        continue
                    label = "SMB" if kind == "SMB" or row.get("isSMB") is True else "User bolus" if kind == "NORMAL" or row.get("isSMB") is False else "Bolus · unknown type"
                    add(key, at, row[field], label)
                else:
                    add(key, at, row[field], event)
        if event == "Temporary Target":
            duration_ms = numeric(row.get("durationInMilliseconds"))
            duration = duration_ms / 60000 if duration_ms is not None else numeric(row.get("duration"))  # V1 minutes.
            low, high = numeric(row.get("targetBottom")), numeric(row.get("targetTop"))
            units = str(row.get("units", "")).lower().replace(" ", "")
            factor = 18 if units in ("mmol/l", "mmol") else 1 if units in ("mg/dl", "mgdl") else None
            if at is None or duration is None or duration < 0:
                rejected += 1
            else:
                valid = factor is not None and low is not None and high is not None and 0 < low <= high
                # Even an unknown range ends the previous target; never guess units.
                targets.append({"time": at, "end": at + timedelta(minutes=duration),
                                "low": low * factor if valid else None,
                                "high": high * factor if valid else None, "reason": str(row.get("reason") or "")})
                if duration > 0 and not valid:
                    rejected += 1
        if event == "Temp Basal":
            duration = numeric(row.get("duration"))
            absolute, percent = numeric(row.get("absolute")), numeric(row.get("percent"))
            if at is None or duration is None or duration < 0:
                rejected += 1
                continue
            # Zero-duration records cancel the preceding temp. Unknown values
            # still end a previous record, but are never treated as zero basal.
            kind, value = ("basal", absolute) if absolute is not None and absolute >= 0 else ("basal_percent", percent)
            temps.append({"time": at, "end": at + timedelta(minutes=duration), "kind": kind, "value": value})
    for row in sorted(statuses, key=lambda r: str(r.get("created_at", ""))):
        if row.get("isValid") is False:
            continue
        at = timestamp(row.get("created_at"))
        openaps = row.get("openaps")
        if not isinstance(openaps, dict):
            continue
        iob = openaps.get("iob", {})
        if isinstance(iob, list):
            iob = iob[0] if iob else {}
        if isinstance(iob, dict) and "iob" in iob:
            sample_time = timestamp(iob.get("time")) or timestamp(iob.get("timestamp")) or at
            add("iob", sample_time, iob["iob"], row.get("device", ""))
        suggested = openaps.get("suggested", {})
        if isinstance(suggested, dict) and "COB" in suggested:
            add("cob", timestamp(suggested.get("timestamp")) or at, suggested["COB"], row.get("device", ""))
        if isinstance(suggested, dict):
            sample_time = timestamp(suggested.get('timestamp')) or at
            value = numeric(suggested.get('variable_sens'))
            if value is not None and value > 0:
                add('variable_sens', sample_time, value, 'openaps.suggested.variable_sens')
    data = {}
    for key, values in points.items():
        frame = pd.DataFrame(values, columns=["time", "value", "label"]).sort_values("time")
        if key not in ("bolus", "carbs", "changes", "automation_notes"):
            frame = frame.drop_duplicates("time", keep="last")
        if key == "automation_notes":
            frame = frame.drop_duplicates(["time", "label"])
        data[key] = frame.reset_index(drop=True)
    intervals = {"basal": [], "basal_percent": []}
    temps.sort(key=lambda item: item["time"])
    for index, item in enumerate(temps):
        until = min(item["end"], temps[index+1]["time"] if index+1 < len(temps) else end, end)
        at = max(item["time"], start)
        if item["value"] is not None and until > at:
            intervals[item["kind"]].append({"time": at, "end": until, "value": item["value"]})
    for key, values in intervals.items():
        data[key] = pd.DataFrame(values, columns=["time", "end", "value"])
    target_intervals = []
    targets.sort(key=lambda item: item["time"])
    for index, item in enumerate(targets):
        until = min(item["end"], targets[index+1]["time"] if index+1 < len(targets) else end, end)
        at = max(item["time"], start)
        if until > at:
            target_intervals.append({"time": at, "end": until, "low": item["low"], "high": item["high"], "reason": item["reason"]})
    data["target"], target_issues = recorded_targets(treatments, target_intervals, start, end)
    warnings.extend(target_issues)
    if not data["bolus"].empty and data["bolus"]["label"].str.contains("unknown").any():
        warnings.append("Some boluses have no explicit SMB/user flag; these are labeled unknown, not inferred from dose size.")
    if rejected:
        warnings.append(f"Skipped {rejected} records/values with missing, invalid or sensor-status data.")
    if not data["basal_percent"].empty:
        warnings.append("Some temporary basals have only a percent field. They are shown separately as reported, without conversion to U/h.")
    return data, warnings


def load_nightscout(url, token, first, last, zone, categories=None):
    start, end = utc_bounds(first, last, zone)
    client = NightscoutClient(url, token)
    selected=set(categories) if categories is not None else {'glucose','treatments','loop'}
    if not selected<={'glucose','treatments','loop'}:raise NightscoutError('Select supported Nightscout data categories.')
    entries = client.records("entries/sgv", start, end) if 'glucose' in selected else []
    successful=set(selected)
    warnings = []
    treatments_available = 'treatments' in selected
    try:
        treatments = client.records("treatments", start, end) if treatments_available else []
    except NightscoutError as exc:
        treatments = []
        treatments_available = False
        successful.discard('treatments')
        warnings.append("Treatments were not loaded: " + str(exc))
    alignment_events=[]
    if treatments_available:
        for event in ("Temp Basal", "Temporary Target"):
            try:
                prior = client.get("treatments", {"find[eventType]": event, "find[created_at][$lt]": _iso(start),
                                                "find[isValid][$ne]": "false", "count": 1})
                treatments = prior + treatments
            except NightscoutError as exc:
                warnings.append(f"The {event.lower()} crossing the start date could not be checked: " + str(exc))
    # Profile history is required by overlays even when treatment layers are off.
    # Reuse the full treatment load; otherwise fetch only requested/effective profiles.
    profiles_available=treatments_available
    if not treatments_available:
        try:
            treatments=client.records('treatments',start,end,filters={'find[originalProfileName][$exists]':'true'})
            treatments+=client.records('treatments',start,end,filters={'find[eventType]':'Profile Switch'})
            profiles_available=True
        except NightscoutError as exc:
            warnings.append('Profile history was not loaded: '+str(exc))
    if profiles_available:
        try:
            prior = client.get("treatments", {"find[originalProfileName][$exists]": "true", "find[eventType][$ne]": "Profile Switch", "find[created_at][$lt]": _iso(start),
                                            "find[isValid][$ne]": "false", "count": 1})
            treatments = prior + treatments
        except NightscoutError as exc:
            warnings.append("The effective profile at the start date could not be checked: " + str(exc))
    if treatments_available:
        # Alignment context is kept separately: origins before the range do not
        # become visible timeline events or invent a sensor/site start at midnight.
        for kind in ('Sensor Start','Sensor Change','Site Change'):
            try:
                for record in client.get('treatments',{'find[eventType]':kind,'find[created_at][$lt]':_iso(start),'find[isValid][$ne]':'false','count':1}):
                    at=pd.to_datetime(record.get('created_at'),utc=True,errors='coerce')
                    if pd.notna(at) and at<start and record.get('isValid') is not False:alignment_events.append(dict(time=at,label=kind))
            except NightscoutError as exc:warnings.append('Earlier '+kind.lower()+' context was not available: '+str(exc))
    try:
        statuses = client.records("devicestatus", start, end) if 'loop' in selected else []
    except NightscoutError as exc:
        statuses = []
        successful.discard('loop')
        warnings.append("IOB/COB were not loaded: " + str(exc))
    data, issues = normalize_data(entries, treatments, statuses, start, end)
    return {"data": data, "warnings": warnings + issues, "first": first, "last": last, "zone": zone,
            "site": client.url, "loaded_at": datetime.now(UTC),
            "availability": {"glucose": 'glucose' in selected, "treatments": treatments_available, "profiles": profiles_available},
            "loaded_categories": sorted(successful),
            "alignment_events":alignment_events, "recorded_profiles": recorded_profiles(treatments, start, end)}


def local_points(frame, zone, days):
    if frame.empty:
        return pd.DataFrame(columns=["day", "minute", "time", "value", "label"])
    result = frame.copy()
    times = pd.to_datetime(result["time"], utc=True).dt.tz_convert(zone)
    result["day"] = times.dt.date
    result["minute"] = times.dt.hour * 60 + times.dt.minute + times.dt.second / 60 + times.dt.microsecond / 60000000
    result["time"] = times
    return result[result["day"].isin(days)].sort_values("time")


def glucose_summary(frame, zone, days, unit):
    values = local_points(frame, zone, days)
    if values.empty:
        return pd.DataFrame(columns=["minute", "median", "low", "high", "days"])
    values["bin"] = (values["minute"] // 5).astype(int) * 5
    # One value per day/bin prevents dense uploads or repeated DST hours from
    # giving a day extra weight. Missing bins are not interpolated.
    per_day = values.groupby(["day", "bin"])["value"].median()
    groups = per_day.groupby("bin")
    result = pd.DataFrame({"median": groups.median(), "low": groups.quantile(.25),
                           "high": groups.quantile(.75), "days": groups.count()}).reindex(range(0, 1440, 5))
    if unit == "mmol/L":
        result[["median", "low", "high"]] /= 18
    return result.rename_axis("minute").reset_index()


def recorded_targets(treatments, temporary, start, end):
    """Combine AAPS effective-profile target schedules with actual temp overrides.

    Effective Profile Switch uploads contain an already-customized profileJson;
    do not apply originalPercentage/originalTimeshift a second time. Retain the
    underlying scheduled limits as profile_low/profile_high during temp targets.
    """
    switches = []
    issues = []
    for row in treatments:
        if row.get('isValid') is False or 'originalProfileName' not in row:
            continue
        at = timestamp(row.get('created_at')) or timestamp(row.get('date'))
        if at is None:
            continue
        profile = row.get('profileJson')
        try:
            if isinstance(profile,str):
                profile = json.loads(profile)
            zone = ZoneInfo(profile['timezone'])
            units = str(profile['units']).lower()
            factor = 18 if units in ('mmol/l','mmol') else 1 if units in ('mg/dl','mgdl') else None
            if factor is None:
                raise ValueError('Unknown units')
            schedules = {}
            for field in ('target_low','target_high'):
                values = []
                for item in profile[field]:
                    seconds = numeric(item.get('timeAsSeconds'))
                    if seconds is None:
                        h,m = item['time'].split(':')[:2]
                        seconds = int(h)*3600+int(m)*60
                    value = numeric(item['value'])
                    if value is None or value<=0 or not 0<=seconds<86400:
                        raise ValueError('Invalid target schedule')
                    values.append((seconds,value*factor))
                values.sort()
                if not values or values[0][0]!=0 or len({x[0] for x in values})!=len(values):
                    raise ValueError('Incomplete target schedule')
                schedules[field]=values
            switches.append((at,zone,schedules))
        except (KeyError,TypeError,ValueError,AttributeError):
            # A malformed switch still ends the preceding known profile.
            switches.append((at,None,None))
            issues.append('An effective-profile target schedule was incomplete; its target history is left blank.')
    switches.sort(key=lambda item:item[0])
    baseline=[]
    for i,(at,zone,schedules) in enumerate(switches):
        stop=min(end,switches[i+1][0] if i+1<len(switches) else end)
        # Effective switches are historical state changes. originalEnd describes
        # the requested switch, not the lifetime of this effective state.
        # AAPS selects the last valid effective switch at/before a timestamp.
        at=max(at,start)
        if schedules is None or at>=stop:
            continue
        # Schedules are wall-clock times. UTC minute boundaries preserve DST
        # transitions; exact schedule boundaries are also included below.
        boundaries={at,stop}
        boundaries.update(pd.date_range(at.replace(second=0,microsecond=0)+timedelta(minutes=1),stop,freq='1min').to_pydatetime())
        day=at.astimezone(zone).date()
        last=stop.astimezone(zone).date()
        while day<=last:
            for values in schedules.values():
                for seconds,_ in values:
                    naive=datetime.combine(day,time.min)+timedelta(seconds=seconds)
                    for fold in (0,1):
                        boundary=naive.replace(tzinfo=zone,fold=fold).astimezone(UTC)
                        if at<boundary<stop:
                            boundaries.add(boundary)
            day+=timedelta(days=1)
        boundaries=sorted(boundaries)
        for a,b in zip(boundaries,boundaries[1:]):
            local=a.astimezone(zone)
            seconds=local.hour*3600+local.minute*60+local.second
            low,high=[next(v for t,v in reversed(schedules[field]) if t<=seconds) for field in ('target_low','target_high')]
            if low>high:
                continue
            item={'time':a,'end':b,'low':low,'high':high,'source':'Scheduled target','reason':''}
            if baseline and baseline[-1]['end']==a and baseline[-1]['low']==low and baseline[-1]['high']==high:
                baseline[-1]['end']=b
            else:
                baseline.append(item)
    temps=[dict(item,source='Temporary target',reason=item.get('reason','')) for item in temporary]
    boundaries=sorted({t for item in baseline+temps for t in (item['time'],item['end'])})
    merged=[]
    bi=ti=0
    for a,b in zip(boundaries,boundaries[1:]):
        while bi<len(baseline) and baseline[bi]['end']<=a:bi+=1
        while ti<len(temps) and temps[ti]['end']<=a:ti+=1
        historical=baseline[bi] if bi<len(baseline) and baseline[bi]['time']<=a<baseline[bi]['end'] else None
        chosen=temps[ti] if ti<len(temps) and temps[ti]['time']<=a<temps[ti]['end'] else historical
        if chosen is None or chosen['low'] is None:
            continue
        # Retain the historical scheduled range while a temp target overrides it.
        item=dict(chosen,time=a,end=b,profile_low=historical['low'] if historical else None,
                  profile_high=historical['high'] if historical else None)
        if merged and merged[-1]['end']==a and all(merged[-1][k]==item[k] for k in ('low','high','source','reason','profile_low','profile_high')):
            merged[-1]['end']=b
        else:
            merged.append(item)
    if not baseline:
        issues.append('No usable effective-profile target history was returned; only recorded temporary targets can be displayed.')
    return pd.DataFrame(merged,columns=['time','end','low','high','source','reason','profile_low','profile_high']),list(dict.fromkeys(issues))


def daily_summary(loaded, days, unit):
    """Observed 5-minute glucose-bin statistics and recorded treatment totals.

    Bins are anchored at local midnight and measured in UTC elapsed time so
    repeated DST hours remain separate. Dense uploads get no extra weight.
    """
    data, zone = loaded['data'], loaded['zone']
    result = []
    factor = 18 if unit == 'mmol/L' else 1
    availability = loaded.get('availability', {}).get('treatments')
    for day in sorted(set(days)):
        start, end = utc_bounds(day, day, zone)
        until = max(start, min(end, loaded['loaded_at']))
        in_source=loaded.get('nightscout_first',day)<=day<=loaded.get('nightscout_last',day)
        expected = math.ceil((until-start).total_seconds()/300) if in_source else 0
        points = data['glucose']
        points = points[(points['time']>=start) & (points['time']<until)].copy()
        if not points.empty:
            points['bin'] = ((pd.to_datetime(points['time'],utc=True)-start).dt.total_seconds()//300).astype(int)
            bins = points.groupby('bin')['value'].median()
        else:
            bins = pd.Series(dtype=float)
        count = len(bins)
        mean = float(bins.mean()) if count else None
        sd = float(bins.std(ddof=0)) if count>=2 else None
        row = dict(date=day.isoformat(),unit=unit,observed_bins=count,expected_bins=expected,
                   coverage=100*count/expected if expected else None,
                   mean=mean/factor if mean is not None else None,
                   sd=sd/factor if sd is not None else None,
                   cv=100*sd/mean if sd is not None and mean else None,
                   tir=100*float(bins.between(72,180,inclusive='both').mean()) if count else None,
                   below=100*float((bins<72).mean()) if count else None,
                   above=100*float((bins>180).mean()) if count else None,
                   partial=until<end,through=until.astimezone(ZoneInfo(zone)).strftime('%H:%M'),
                   glucose_max=float(bins.max())/factor if count else None)
        # Source failure is unknown, not a zero-treatment day. Older in-memory
        # snapshots can still report totals when they contain actual events.
        for key in ('carbs','bolus'):
            frame = data[key]
            known = (availability is True or (availability is None and not frame.empty)) and loaded.get('nightscout_first',day)<=day<=loaded.get('nightscout_last',day)
            selected = frame[(frame['time']>=start) & (frame['time']<until)]
            row[key] = float(selected['value'].sum()) if known and until>start else None
        result.append(row)
    return result


def recorded_profiles(treatments, start, end):
    """Only AAPS effective switches establish which profile actually ran.

    Their profileJson already includes percentage/time-shift changes. Missing
    JSON ends the known state; it must not extend the preceding valid profile.
    """
    fields=('timezone','units','dia','basal','carbratio','sens','target_low','target_high')
    bases={}
    for row in treatments:
        if row.get('isValid') is False or row.get('eventType')!='Profile Switch':continue
        at=timestamp(row.get('created_at')) or timestamp(row.get('date'))
        if at is None or at>=end:continue
        raw=row.get('profileJson')
        try:raw=json.loads(raw) if isinstance(raw,str) else raw
        except (ValueError,TypeError):continue
        if isinstance(raw,dict):
            name=row.get('originalProfileName') or row.get('profile')
            bases.setdefault(name,[]).append((at,{k:raw[k] for k in fields if k in raw}))
    switches={}
    for row in treatments:
        if row.get('isValid') is False or 'originalProfileName' not in row or row.get('eventType')=='Profile Switch':continue
        at=timestamp(row.get('created_at')) or timestamp(row.get('date'))
        if at is None or at>=end:continue
        raw=row.get('profileJson')
        try:raw=json.loads(raw) if isinstance(raw,str) else raw
        except (ValueError,TypeError):raw=None
        profile={k:raw[k] for k in fields if k in raw} if isinstance(raw,dict) else {}
        switches[at]=dict(name=str(row.get('originalProfileName') or 'Unnamed profile'),profile=profile,
                          percentage=numeric(row.get('originalPercentage')),timeshift=numeric(row.get('originalTimeshift')),
                          active_at=at.isoformat(),explicit_end=timestamp(row.get('originalEnd')))
    times=sorted(switches);result=[]
    for i,at in enumerate(times):
        stop=min(end,times[i+1] if i+1<len(times) else end)
        state=switches[at].copy();expiry=state.pop('explicit_end')
        if expiry is not None and expiry>at:stop=min(stop,expiry)
        base=None
        # Requested switches contain unmodified JSON; they do not prove activation.
        candidates=[item for item in bases.get(state['name'],[]) if item[0]<=at]
        if candidates:base=max(candidates,key=lambda c:c[0])[1]
        if base is None and state['percentage']==100 and state['timeshift'] in (None,0):base=state['profile']
        state['base_profile']=base
        if stop>max(start,at):result.append(dict(state,start=max(start,at).isoformat(),end=stop.isoformat()))
    return result
