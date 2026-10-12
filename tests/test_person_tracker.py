import pytest

from oak_events.events import PersonTracker, Zone

PERSON = ("person", 0.9, 0.0, 0.0, 2000.0)
NEAR = ("person", 0.8, 100.0, 0.0, 1200.0)
CHAIR = ("chair", 0.95, 0.0, 0.0, 1500.0)
WEAK = ("person", 0.2, 0.0, 0.0, 1500.0)


def feed(tracker, frames, t0=0.0, dt=0.1):
    events, t = [], t0
    for dets in frames:
        events += tracker.update(dets, t)
        t += dt
    return events, t


def test_enter_needs_confirm_frames():
    tr = PersonTracker(confirm_frames=3, gone_seconds=10)
    assert tr.update([PERSON], 0.0) == []
    assert tr.update([PERSON], 0.1) == []
    evs = tr.update([PERSON, NEAR], 0.2)
    assert len(evs) == 1
    ev = evs[0]
    assert ev["kind"] == "person_enter"
    assert ev["zone"] == "view"
    assert ev["count"] == 2
    assert ev["nearest_mm"] == 1200
    assert "ts" in ev and "T" in ev["ts"]
    assert tr.present
    # no duplicate enter while present
    assert tr.update([PERSON], 0.3) == []


def test_flicker_is_suppressed():
    tr = PersonTracker(confirm_frames=3, gone_seconds=10)
    frames = [[PERSON], [PERSON], [], [PERSON], [], [PERSON], [PERSON], []]
    evs, _ = feed(tr, frames)
    assert evs == []
    assert not tr.present


def test_low_confidence_and_other_labels_ignored():
    tr = PersonTracker(confirm_frames=1, min_confidence=0.5)
    assert tr.update([CHAIR, WEAK], 0.0) == []
    assert not tr.present


def test_exit_after_gone_seconds_with_dwell():
    tr = PersonTracker(confirm_frames=2, gone_seconds=10)
    tr.update([PERSON], 0.0)
    assert tr.update([PERSON], 1.0)[0]["kind"] == "person_enter"
    tr.update([PERSON], 30.0)  # last sighting
    assert tr.update([], 35.0) == []  # gone 5 s: not yet
    assert tr.update([], 40.0) == []  # gone exactly 10 s: not yet (strictly greater)
    evs = tr.update([], 40.5)
    assert len(evs) == 1
    assert evs[0]["kind"] == "person_exit"
    assert evs[0]["dwell_s"] == 29
    assert not tr.present
    assert tr.update([], 60.0) == []


def test_single_sighting_while_present_keeps_person():
    tr = PersonTracker(confirm_frames=3, gone_seconds=10)
    feed(tr, [[PERSON]] * 3)
    assert tr.present
    tr.update([], 5.0)
    tr.update([PERSON], 9.0)  # one frame is enough to refresh while present
    assert tr.update([], 15.0) == []
    assert tr.update([], 19.5)[0]["kind"] == "person_exit"


def test_zone_bbox_and_depth_range():
    zone = Zone("door", bbox=(0.0, 0.0, 0.5, 1.0), z_min_mm=500, z_max_mm=2500)
    tr = PersonTracker(confirm_frames=1, zone=zone)
    outside_box = ("person", 0.9, 0, 0, 1000.0, 0.8, 0.5)
    too_far = ("person", 0.9, 0, 0, 4000.0, 0.2, 0.5)
    assert tr.update([outside_box, too_far], 0.0) == []
    inside = ("person", 0.9, 0, 0, 1000.0, 0.2, 0.5)
    evs = tr.update([inside], 0.1)
    assert evs[0]["zone"] == "door"
    # a detection without image position matches on depth only
    tr2 = PersonTracker(confirm_frames=1, zone=zone)
    assert tr2.update([("person", 0.9, 0, 0, 1000.0)], 0.0)[0]["kind"] == "person_enter"


def test_invalid_args():
    with pytest.raises(ValueError):
        PersonTracker(confirm_frames=0)
    with pytest.raises(ValueError):
        Zone("bad", bbox=(0.5, 0.0, 0.4, 1.0))
