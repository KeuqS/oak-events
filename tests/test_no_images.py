"""Guard: the code paths under test never produce image files.

Runs the tracker, depth detector, sink and MCP tool functions against a
temporary run directory, then scans that directory and the repository for
image-like files. Virtualenvs and VCS/cache directories are skipped (third-party
packages ship their own icons; they are not our output).
"""

import io
from pathlib import Path

import numpy as np

from oak_events import mcp_server
from oak_events.events import DepthChangeDetector, PersonTracker
from oak_events.sink import JsonlSink

REPO = Path(__file__).resolve().parents[1]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".npy", ".npz", ".bmp", ".gif", ".tif", ".tiff", ".webp", ".ppm", ".pgm"}
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist", "node_modules"}


def image_files(root: Path) -> list[Path]:
    found = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in path.relative_to(root).parts):
            continue
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            found.append(path)
    return found


def test_run_paths_write_only_jsonl(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    monkeypatch.chdir(tmp_path)
    sink = JsonlSink(out_dir=run_dir, stream=io.StringIO())
    tracker = PersonTracker(confirm_frames=2, gone_seconds=1)
    detector = DepthChangeDetector(baseline_frames=5, hold_seconds=0.5)
    rng = np.random.default_rng(0)
    t = 0.0
    for i in range(40):
        dets = [("person", 0.9, 0, 0, 1500.0)] if 5 <= i < 15 else []
        for ev in tracker.update(dets, t):
            sink.write(ev)
        depth = (2000 + rng.integers(-5, 6, size=(48, 64))).astype(np.uint16)
        if i >= 25:
            depth[0:8, 0:8] = 1000
        for ev in detector.update(depth, t, person_present=tracker.present):
            sink.write(ev)
        t += 0.2
    sink.emit("alive", det_fps=5.0, person=False, occupied=[])

    kinds = {e["kind"] for e in mcp_server.recent_events(run_dir, limit=500)}
    assert {"person_enter", "person_exit", "depth_baseline", "depth_change", "alive"} <= kinds
    mcp_server.zone_state(run_dir)
    mcp_server.camera_health(run_dir)

    produced = {p.suffix for p in tmp_path.rglob("*") if p.is_file()}
    assert produced == {".jsonl"}
    assert image_files(tmp_path) == []


def test_repo_contains_no_image_files():
    assert image_files(REPO) == []
