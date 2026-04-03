# Homelab Scanner — TODO

## Status: CLI working on Pi. GUI needs Windows test.

---

## Pending

### Windows GUI Testing
- [ ] Transfer project to ThinkPad and install PyQt6 (`pip install PyQt6 paramiko pyyaml`)
- [ ] Run `python main.py` on Windows — verify GUI launches
- [ ] Test Scan All button — all 5 hosts
- [ ] Test per-host left panel status (green/red)
- [ ] Test Disk/Docker/Services tabs populate correctly
- [ ] Test Settings dialog (SSH, Output, Hosts tabs)
- [ ] Test column resize/reorder/sort + state persistence after restart
- [ ] Test auto-refresh toggle + interval
- [ ] Verify output paths write to X:/Obsidian/... on Windows

### Known gaps
- [ ] `gui_app.py` imports `resolve_config` from `main` — fragile if run via `python -m` or different working dir; consider moving `resolve_config` to a shared module

---

## Completed
- [x] SSH working — key auth to all hosts (Pi4, Pi5-AI, QNAP, ThinkPad)
- [x] QNAP hang fixed — channel.settimeout() + socket.timeout handling
- [x] modules/ssh_client.py
- [x] modules/collectors.py — per-host collect field, linux/windows/local/qnap
- [x] modules/data_store.py — YAML read/write with timestamp
- [x] modules/context_builder.py — all content from config, no hardcoded strings
- [x] modules/cli_runner.py — CLI entry with argparse, --hosts/--context-only/--data-only
- [x] modules/gui_app.py — PyQt6 GUI (ScanWorker, tables, settings dialog, state persist)
- [x] main.py — unified entry, OS detection, config platform resolution
- [x] scanner.py — thin legacy wrapper → cli_runner
- [x] config/config.json — single file, platforms.pi + platforms.windows, all paths/context in config
- [x] Full scan test on Pi — all 5 hosts, data saved to Obsidian vault
- [x] GitHub repo: https://github.com/RafalekS/homelab-scanner
