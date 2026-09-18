"""Time-aligned comparison cells and highlights shared by all workspaces."""
import math
import pandas as pd
from profiles import minute, clock, value_at


def comparison_table(rows, references, metric, primary_label='Draft'):
    """Return display values and a matching boolean cell mask; never alter schedules."""
    fields = ('low', 'high') if metric == 'target' else ('value',)
    schedules = [(primary_label, rows)] + [(label, profile['schedules'][metric]) for label, profile, *_ in references]
    boundaries = sorted({minute(row['time']) for _, schedule in schedules for row in schedule} | {1440})
    records, masks = [], []
    for start, end in zip(boundaries, boundaries[1:]):
        values = [tuple(value_at(schedule, start, field) for field in fields) for _, schedule in schedules]
        changed = [not all(math.isclose(a,b,rel_tol=0,abs_tol=1e-10) for a,b in zip(values[0], other)) for other in values[1:]]
        record = {'From': clock(start), 'To': clock(end)}
        mask = {'From': False, 'To': False}
        for index, ((label, _), value) in enumerate(zip(schedules, values)):
            record[label] = ' - '.join(f'{v:g}' for v in value)
            mask[label] = any(changed) if index == 0 else changed[index-1]
        records.append(record); masks.append(mask)
    return pd.DataFrame(records), pd.DataFrame(masks)


def styled_comparison(frame, mask, dark):
    style = 'background-color: #654c1b; color: #fff1c2' if dark else 'background-color: #fff0bc; color: #513b00'
    return frame.style.apply(lambda _: mask.map(lambda changed: style if changed else ''), axis=None)
