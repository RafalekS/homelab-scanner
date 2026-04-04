# Homelab Scanner — TODO

## Status: CLI working on Pi. GUI needs Windows test.

---

## Pending

### Windows GUI Testing
- [ ] Transfer project to ThinkPad: `git clone https://github.com/RafalekS/homelab-scanner`
- [ ] Install deps: `pip install PyQt6 paramiko pyyaml`
- [ ] Run `python main.py` — verify GUI launches
- [ ] Test Scan All and Scan Host buttons
- [ ] Test per-host status colours in left panel (green/red/grey)
- [ ] Test Disk/Docker/Services tabs populate correctly
- [ ] Test last scan loads on restart (no re-scan needed to see data)
- [ ] Test Settings dialog (SSH, Output, Hosts tabs, Browse buttons)
- [ ] Test column resize/reorder/sort + widths persist after restart
- [ ] Test auto-refresh toggle + interval
- [ ] Verify output paths write to X:/Obsidian/... on Windows

---

## Completed
- [x] SSH working — key auth to all hosts (Pi4, Pi5-AI, QNAP, ThinkPad)
- [x] QNAP hang fixed — channel.settimeout() + socket.timeout handling
- [x] modules/config_loader.py — resolve_config moved here (no fragile `from main import`)
- [x] modules/ssh_client.py — per-host key_path override
- [x] modules/collectors.py — per-host collect field, linux/windows/local/qnap
- [x] modules/data_store.py — YAML read/write with timestamp
- [x] modules/context_builder.py — all content from config, no hardcoded strings
- [x] modules/cli_runner.py — CLI entry with argparse, --hosts/--context-only/--data-only
- [x] modules/gui_app.py — PyQt6 GUI with Scan All, Scan Host, startup data load, persistent column widths
- [x] main.py / scanner.py — use config_loader, sys.path set so runnable from any cwd
- [x] config/config.json — single file, platforms.pi + platforms.windows, all paths/context in config
- [x] Full scan test on Pi — all 5 hosts, data saved to Obsidian vault
- [x] integration.md — guide for embedding as profile_manager tab
- [x] GitHub repo: https://github.com/RafalekS/homelab-scanner
