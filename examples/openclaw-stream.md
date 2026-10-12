# Stream automation example (OpenClaw)

Any agent runtime that can run a command and react to matching output lines can
consume `oak-events run` directly, because every event is one line on stdout.

OpenClaw's stream automations are one example. This wakes the agent whenever a
person enters a zone or a lasting depth change is seen:

```bash
openclaw automations add \
  --stream-command '["oak-events", "run", "--model", "~/models/yolov6-nano.rvc2.tar.xz", "--zones", "~/oak/zones.json", "--out-dir", "~/.local/share/oak-events/events"]' \
  --stream-mode match \
  --stream-match '"kind": "(person_enter|depth_change)"'
```

Notes:

- The match is a regular expression over each stdout line. Events are written
  as `{"ts": ..., "kind": "person_enter", ...}` with a space after the colon.
- `--out-dir` keeps a copy on disk so `oak-events mcp` can answer follow-up
  questions (`zone_state`, `camera_health`) when the agent wakes.
- To also be told when the camera drops, add `camera` to the match:
  `'"kind": "(person_enter|depth_change|camera)"'`.
- If `oak-events` is not on the supervisor's `PATH`, use the absolute path of
  the virtualenv's `oak-events` script. Paths starting with `~` are expanded by
  `oak-events` itself.
- On macOS, the supervisor running the command needs local-network permission
  for PoE cameras (see the README's PoE notes).
