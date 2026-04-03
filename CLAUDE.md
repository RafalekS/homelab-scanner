# Homelab Scanner

Cross-platform Python tool that collects dynamic homelab data via paramiko SSH and builds homelab-context.md for Obsidian.

## Run

```bash
cd /home/pi/claude/homelab-scanner
python scanner.py                          # full scan + context rebuild
python scanner.py --hosts Pi4 ThinkPad    # specific hosts only
python scanner.py --context-only          # rebuild context from existing YAML
python scanner.py --data-only             # scan only, skip context build
```

## Config

`config/config.json` — hosts, SSH settings, output paths

## Data flow

SSH collect → `homelab-data.yaml` → `homelab-context.md`

## Modules

- `modules/ssh_client.py` — paramiko, key→password fallback
- `modules/collectors.py` — per-host collection (linux/windows/qnap/local)
- `modules/data_store.py` — YAML read/write
- `modules/context_builder.py` — builds Obsidian context note
