import importlib
import sys
from pathlib import Path

from oak_events import privacy

SRC = Path(__file__).resolve().parents[1] / "src" / "oak_events"


def test_defaults_set_at_import(monkeypatch):
    for key in privacy.PRIVACY_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv(privacy.OPT_IN_ENV, raising=False)
    import os

    importlib.reload(privacy)
    assert os.environ["DEPTHAI_TELEMETRY"] == "0"
    assert os.environ["DEPTHAI_DISABLE_CRASHDUMP_COLLECTION"] == "1"
    assert os.environ["DEPTHAI_AUTOCALIBRATION"] == "OFF"
    assert privacy.state()["private"] is True


def test_preset_values_are_overwritten(monkeypatch):
    import os

    monkeypatch.setenv("DEPTHAI_TELEMETRY", "1")
    monkeypatch.setenv("DEPTHAI_AUTOCALIBRATION", "ON")
    monkeypatch.delenv(privacy.OPT_IN_ENV, raising=False)
    importlib.reload(privacy)
    assert os.environ["DEPTHAI_TELEMETRY"] == "0"
    assert os.environ["DEPTHAI_AUTOCALIBRATION"] == "OFF"


def test_explicit_opt_in_leaves_env_alone(monkeypatch):
    import os

    monkeypatch.setenv(privacy.OPT_IN_ENV, "1")
    monkeypatch.setenv("DEPTHAI_TELEMETRY", "1")
    monkeypatch.delenv("DEPTHAI_AUTOCALIBRATION", raising=False)
    importlib.reload(privacy)
    assert privacy.APPLIED == {}
    assert os.environ["DEPTHAI_TELEMETRY"] == "1"
    assert "DEPTHAI_AUTOCALIBRATION" not in os.environ
    assert privacy.state()["opted_in_to_telemetry"] is True
    monkeypatch.delenv(privacy.OPT_IN_ENV)
    importlib.reload(privacy)  # restore defaults for later tests


def test_apply_on_custom_mapping():
    env = {"DEPTHAI_TELEMETRY": "1"}
    privacy.apply(env)
    assert env == privacy.PRIVACY_ENV


def test_camera_imports_privacy_first_and_depthai_lazily():
    lines = [ln for ln in (SRC / "camera.py").read_text().splitlines()
             if ln.startswith(("import ", "from "))]
    assert lines[0].startswith("from . import privacy")
    assert not any("depthai" in ln.split("#")[0] for ln in lines)  # top-level imports never pull depthai


def test_importing_camera_without_depthai_is_safe(monkeypatch):
    import os

    monkeypatch.setitem(sys.modules, "depthai", None)  # simulate "not installed"
    monkeypatch.setenv("DEPTHAI_TELEMETRY", "1")
    monkeypatch.delenv(privacy.OPT_IN_ENV, raising=False)
    importlib.reload(privacy)
    import oak_events.camera as camera

    importlib.reload(camera)
    assert os.environ["DEPTHAI_TELEMETRY"] == "0"
    try:
        camera.import_depthai()
    except camera.CameraUnavailable as exc:
        assert "oak-events[camera]" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected CameraUnavailable")
