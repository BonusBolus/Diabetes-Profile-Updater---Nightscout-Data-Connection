"""In-memory undo/redo for profile edits, including incomplete table rows."""
from copy import deepcopy
import json


def snapshot(state):
    return deepcopy({key: state[key] for key in ("draft", "raw_schedules", "raw_extra")})


def reset_history(state):
    state["undo_stack"] = []
    state["redo_stack"] = []
    state["last_edit"] = snapshot(state)


def record_edit(state):
    current = snapshot(state)
    if json.dumps(current, sort_keys=True, default=str) != json.dumps(state["last_edit"], sort_keys=True, default=str):
        state["undo_stack"].append(state["last_edit"])
        state["redo_stack"] = []
        state["last_edit"] = current


def restore_edit(state, direction):
    source, destination = ("undo_stack", "redo_stack") if direction == "undo" else ("redo_stack", "undo_stack")
    if not state[source]:
        return
    state[destination].append(snapshot(state))
    restored = state[source].pop()
    for key, value in restored.items():
        state[key] = deepcopy(value)
    state["last_edit"] = deepcopy(restored)
    # New widget keys prevent old editor deltas from being applied again.
    state["epoch"] += 1
    state["seeds"] = deepcopy(state["raw_schedules"])
    state["extra_seed"] = deepcopy(state["raw_extra"])
    state["revisions"] = {metric: 0 for metric in state["raw_schedules"]}
