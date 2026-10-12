"""JSON-lines output: stdout and/or one file per local day.

Each event is serialised to a single line and appended with one ``write(2)``
on a file opened with ``O_APPEND``, so concurrent readers (the MCP server, a
``tail -f``) never see a half-written line on a local filesystem.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import IO, Any

from .events import Event, make_event


def encode(event: Event) -> str:
    """One event -> one line of JSON (no embedded newlines)."""
    return json.dumps(event, ensure_ascii=False, default=str)


class JsonlSink:
    """Write events to stdout and/or ``<out_dir>/YYYY-MM-DD.jsonl``.

    The day comes from the event's own ``ts`` (local date), so a file never
    mixes days. Files are created with mode 0600.
    """

    def __init__(self, out_dir: str | Path | None = None, stdout: bool = True, stream: IO[str] | None = None) -> None:
        self.out_dir = Path(out_dir).expanduser() if out_dir is not None else None
        self.stdout = stdout
        self.stream = stream
        if self.out_dir is not None:
            self.out_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, event: Event) -> Path | None:
        if self.out_dir is None:
            return None
        ts = str(event.get("ts", ""))
        day = ts[:10] if len(ts) >= 10 else _dt.date.today().isoformat()
        return self.out_dir / f"{day}.jsonl"

    def write(self, event: Event) -> str:
        line = encode(event)
        path = self.path_for(event)
        if path is not None:
            data = (line + "\n").encode("utf-8")
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                written = os.write(fd, data)
                while written < len(data):  # extremely rare partial write; finish the line
                    written += os.write(fd, data[written:])
            finally:
                os.close(fd)
        if self.stdout:
            out = self.stream or sys.stdout
            out.write(line + "\n")
            out.flush()
        return line

    def emit(self, kind: str, **fields: Any) -> Event:
        event = make_event(kind, **fields)
        self.write(event)
        return event
