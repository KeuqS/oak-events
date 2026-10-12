import json
from pathlib import Path

import pytest


def write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


@pytest.fixture
def events_dir(tmp_path: Path) -> Path:
    """Two days of synthetic events, plus a malformed line that must be skipped."""
    d = tmp_path / "events"
    write_jsonl(d / "2026-01-01.jsonl", [
        {"ts": "2026-01-01T08:00:00+00:00", "kind": "camera", "state": "up", "device_model": "OAK-D"},
        {"ts": "2026-01-01T08:01:00+00:00", "kind": "depth_baseline", "zone": "view", "cells_judged": 44,
         "cells_noisy": 4, "grid": [6, 8]},
        {"ts": "2026-01-01T09:00:00+00:00", "kind": "person_enter", "zone": "door", "count": 1, "nearest_mm": 1800},
        {"ts": "2026-01-01T09:05:00+00:00", "kind": "person_exit", "zone": "door", "dwell_s": 300},
    ])
    write_jsonl(d / "2026-01-02.jsonl", [
        {"ts": "2026-01-02T10:00:00+00:00", "kind": "person_enter", "zone": "desk", "count": 2, "nearest_mm": 900},
        {"ts": "2026-01-02T10:02:00+00:00", "kind": "depth_change", "zone": "view", "cells": ["r1c2"],
         "delta_mm": [-400]},
        {"ts": "2026-01-02T10:05:00+00:00", "kind": "alive", "det_fps": 9.8, "person": True, "occupied": ["desk"]},
    ])
    with open(d / "2026-01-02.jsonl", "a", encoding="utf-8") as fh:
        fh.write("{not json\n\n")
    return d
