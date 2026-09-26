"""Optional historical AAPS preferences; never applied to a pump or Nightscout."""
import math

# Stable AAPS preference keys, display names and native preference units.
SETTINGS = {
    'openaps_smb_min_5m_carbimpact': ('min_5m_carbimpact', 'mg/dL / 5 min'),
    'absorption_maxtime': ('Meal max absorption time', 'h'),
    'openapsma_max_basal': ('Max U/h a Temp Basal can be set to', 'U/h'),
    'openapsmb_max_iob': ("Maximum total IOB OpenAPS can't go over", 'U'),
    'DynISFAdjust': ('DynamicISF Adjustment Factor', '%'),
    'smbinterval': ('SMB frequency', 'min'),
    'smbmaxminutes': ('Max minutes of basal to limit SMB to', 'min'),
    'uamsmbmaxminutes': ('Max minutes of basal to limit SMB to for UAM', 'min'),
}
SHEET = 'AAPS settings'


def validate_settings(values):
    if not isinstance(values, dict) or any(key not in SETTINGS for key in values):
        raise ValueError('Unrecognized AAPS settings. Use Additional overview fields for custom settings.')
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(SETTINGS[key][0] + ': enter a finite, nonnegative number or leave blank.')
    return dict(values)


def display_settings(profile):
    return {f'{SETTINGS[key][0]} ({SETTINGS[key][1]})': str(value)
            for key, value in profile['overview'].get('aaps_settings', {}).items() if key in SETTINGS}


def write_settings(book, profile, profile_sheet):
    if SHEET in book.sheetnames:
        del book[SHEET]
    ws = book.create_sheet(SHEET)
    ws.append(['Profile sheet', 'Setting key', 'AndroidAPS setting', 'Unit', 'Value'])
    for key, (label, unit) in SETTINGS.items():
        ws.append([profile_sheet, key, label, unit, profile['overview'].get('aaps_settings', {}).get(key)])
        for cell in ws[ws.max_row][:4]:
            cell.data_type = 's'
    ws.freeze_panes = 'A2'
    for col, width in [('A', 28), ('B', 34), ('C', 58), ('D', 20), ('E', 16)]:
        ws.column_dimensions[col].width = width


def read_settings(book, profile_sheet):
    values = {}
    if SHEET in book.sheetnames:
        for row in book[SHEET].iter_rows(min_row=2, values_only=True):
            if len(row) < 5 or row[0] != profile_sheet or row[4] is None:
                continue
            key, value = row[1], row[4]
            if key in values:
                raise ValueError('Duplicate AAPS setting: ' + str(key))
            values[key] = value
    return validate_settings(values)
