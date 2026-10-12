# Piping events to a webhook

Every event is one JSON line, so a shell loop is enough to forward them.

```bash
oak-events run --model ~/models/yolov6-nano.rvc2.tar.xz \
  | grep --line-buffered -E '"kind": "(person_enter|person_exit|camera)"' \
  | while IFS= read -r line; do
      curl -sS -X POST -H 'Content-Type: application/json' \
        --data-binary "$line" "$WEBHOOK_URL" > /dev/null
    done
```

- Set `WEBHOOK_URL` to your endpoint (Home Assistant, n8n, a chat webhook...).
  Prefer HTTPS; event lines say when people were present.
- `grep --line-buffered` matters: without it events are held in a buffer.
- Need a different payload shape? Reshape each line with `jq`, e.g.
  `jq -c '{text: "\(.kind) in \(.zone // "camera")"}'`.

Following the daily files instead of stdout (for example from another host
user) works the same way:

```bash
tail -F ~/.local/share/oak-events/events/"$(date +%F)".jsonl | ...
```

Note that `tail -F` on a dated file does not roll over at midnight; restart it
daily or read stdout instead.
