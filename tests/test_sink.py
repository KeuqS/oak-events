import io
import json
import os
import stat
import threading

from oak_events.events import make_event
from oak_events.sink import JsonlSink


def test_stdout_only_writes_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    buf = io.StringIO()
    sink = JsonlSink(stream=buf)
    sink.emit("alive", det_fps=10.0)
    line = buf.getvalue()
    assert line.endswith("\n") and line.count("\n") == 1
    ev = json.loads(line)
    assert ev["kind"] == "alive" and ev["det_fps"] == 10.0
    assert list(tmp_path.iterdir()) == []


def test_daily_file_named_from_event_ts(tmp_path):
    sink = JsonlSink(out_dir=tmp_path / "ev", stdout=False)
    sink.write(make_event("person_enter", ts="2026-03-04T23:59:59-08:00", zone="view", count=1, nearest_mm=900))
    sink.write(make_event("person_exit", ts="2026-03-05T00:00:10-08:00", zone="view", dwell_s=11))
    files = sorted(p.name for p in (tmp_path / "ev").iterdir())
    assert files == ["2026-03-04.jsonl", "2026-03-05.jsonl"]
    mode = stat.S_IMODE(os.stat(tmp_path / "ev" / "2026-03-04.jsonl").st_mode)
    assert mode == 0o600


def test_stdout_and_file_together(tmp_path):
    buf = io.StringIO()
    sink = JsonlSink(out_dir=tmp_path, stream=buf)
    ev = sink.emit("camera", state="up")
    path = sink.path_for(ev)
    assert path.read_text() == buf.getvalue()


def test_concurrent_appends_never_interleave(tmp_path):
    sink = JsonlSink(out_dir=tmp_path, stdout=False)
    payload = "x" * 2000

    def worker(n):
        for i in range(200):
            sink.write(make_event("alive", ts="2026-01-01T00:00:00+00:00", worker=n, i=i, pad=payload))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    lines = (tmp_path / "2026-01-01.jsonl").read_text().splitlines()
    assert len(lines) == 800
    assert all(json.loads(line)["pad"] == payload for line in lines)
