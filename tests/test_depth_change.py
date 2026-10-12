import numpy as np
import pytest

from oak_events.events import DepthChangeDetector, Zone, cell_medians

H, W = 60, 80  # 6 x 8 grid -> 10 x 10 pixel cells
NOISY_CELL = (5, 7)


def scene(rng, base=2000, noise=10):
    d = (base + rng.integers(-noise, noise + 1, size=(H, W))).astype(np.uint16)
    return d


def noisy_scene(rng, i):
    d = scene(rng)
    r, c = NOISY_CELL
    d[r * 10:(r + 1) * 10, c * 10:(c + 1) * 10] = 1000 if i % 2 else 3000  # wobbles 50 %
    return d


def build(det, rng, frames=10, t=0.0):
    evs = []
    for i in range(frames):
        evs += det.update(noisy_scene(rng, i), t)
        t += 0.1
    return evs, t


def test_cell_medians_marks_mostly_invalid_cells_zero():
    d = np.full((H, W), 1500, dtype=np.uint16)
    d[0:10, 0:10] = 0
    g = cell_medians(d, (6, 8))
    assert g.shape == (6, 8)
    assert g[0, 0] == 0
    assert g[1, 1] == 1500


def test_baseline_counts_and_noisy_exclusion():
    rng = np.random.default_rng(0)
    det = DepthChangeDetector(baseline_frames=10, hold_seconds=5)
    evs, _ = build(det, rng)
    assert len(evs) == 1
    ev = evs[0]
    assert ev["kind"] == "depth_baseline"
    assert ev["zone"] == "view"
    assert ev["grid"] == [6, 8]
    assert ev["cells_noisy"] == 1
    assert ev["cells_judged"] == 47
    assert det.baseline[NOISY_CELL] == 0


def test_change_reported_only_after_hold():
    rng = np.random.default_rng(1)
    det = DepthChangeDetector(baseline_frames=10, hold_seconds=5)
    _, t = build(det, rng)
    start = t  # first changed frame
    moved = None
    events = []
    for _ in range(60):  # 6 s of frames at 10 fps
        d = noisy_scene(rng, 0)
        d[10:20, 20:30] = 1500  # cell r1c2 moves 500 mm closer
        events += det.update(d, t)
        if moved is None and events:
            moved = t
        t += 0.1
    changes = [e for e in events if e["kind"] == "depth_change"]
    assert len(changes) == 1
    assert changes[0]["cells"] == ["r1c2"]
    assert changes[0]["delta_mm"][0] == pytest.approx(-500, abs=15)
    assert moved - start >= 5.0 - 1e-9
    # the change became the new baseline: no repeat
    assert det.update(d, t + 100) == []


def test_brief_change_is_not_reported():
    rng = np.random.default_rng(2)
    det = DepthChangeDetector(baseline_frames=10, hold_seconds=5)
    _, t = build(det, rng)
    d = noisy_scene(rng, 0)
    d[10:20, 20:30] = 1500
    assert det.update(d, t) == []
    assert det.update(noisy_scene(rng, 0), t + 3) == []  # back to normal: pending cleared
    d2 = noisy_scene(rng, 0)
    d2[10:20, 20:30] = 1500
    assert det.update(d2, t + 6) == []  # timer restarted, not 6 s held


def test_noisy_cell_never_reports():
    rng = np.random.default_rng(3)
    det = DepthChangeDetector(baseline_frames=10, hold_seconds=1)
    _, t = build(det, rng)
    evs = []
    for _ in range(30):
        d = scene(rng)
        r, c = NOISY_CELL
        d[r * 10:(r + 1) * 10, c * 10:(c + 1) * 10] = 500
        evs += det.update(d, t)
        t += 0.1
    assert evs == []


def test_no_change_while_person_present():
    rng = np.random.default_rng(4)
    det = DepthChangeDetector(baseline_frames=10, hold_seconds=2)
    _, t = build(det, rng)
    evs = []
    for _ in range(50):  # 5 s, well past hold, but someone is standing there
        d = noisy_scene(rng, 0)
        d[0:30, 0:40] = 900
        evs += det.update(d, t, person_present=True)
        t += 0.1
    assert evs == []
    # person leaves; the scene is back to normal -> still nothing
    for _ in range(30):
        evs += det.update(noisy_scene(rng, 0), t, person_present=False)
        t += 0.1
    assert evs == []


def test_baseline_waits_while_person_present():
    rng = np.random.default_rng(5)
    det = DepthChangeDetector(baseline_frames=5)
    for i in range(20):
        assert det.update(scene(rng), i * 0.1, person_present=True) == []
    assert not det.ready


def test_zone_crop_and_names():
    rng = np.random.default_rng(6)
    zone = Zone("shelf", bbox=(0.5, 0.0, 1.0, 0.5))
    det = DepthChangeDetector(grid=(3, 4), baseline_frames=5, hold_seconds=1, zone=zone)
    evs = []
    t = 0.0
    for _ in range(5):
        evs += det.update(scene(rng), t)
        t += 0.1
    assert evs[0]["zone"] == "shelf"
    assert evs[0]["cells_judged"] == 12
    for _ in range(15):
        d = scene(rng)
        d[0:10, 40:50] = 1200  # top-left cell of the zone crop
        d[50:60, 0:10] = 300   # outside the zone: ignored
        evs += det.update(d, t)
        t += 0.1
    changes = [e for e in evs if e["kind"] == "depth_change"]
    assert [c["cells"] for c in changes] == [["r0c0"]]


def test_rejects_non_2d():
    det = DepthChangeDetector()
    with pytest.raises(ValueError):
        det.update(np.zeros((2, 2, 2)), 0.0)
