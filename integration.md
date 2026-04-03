# Homelab Scanner — Integration Guide for profile_manager

## Goal

Add a **Homelab** tab to `profile_manager` that embeds the scanner UI directly, with no separate window.

---

## Repository

`~/claude/homelab-scanner/` (also on GitHub: RafalekS/homelab-scanner)

---

## What the scanner does

Collects disk, docker containers, IPs, and service status from all homelab hosts via SSH (or locally). Saves results to:
- `homelab-data.yaml` — structured scan data
- `homelab-context.md` — human-readable summary for Obsidian

Both paths are platform-specific (configured in `config/config.json` under `platforms.pi` / `platforms.windows`).

---

## Module map

| File | Purpose |
|------|---------|
| `config/config.json` | All config: SSH settings, host list, output paths, hardware context |
| `main.py` | Entry point. `resolve_config(raw)` flattens platform overrides |
| `modules/gui_app.py` | PyQt6 GUI — `MainWindow`, `SettingsDialog`, `ScanWorker` |
| `modules/cli_runner.py` | CLI entry. `scan(cfg, host_filter)` returns list of host dicts |
| `modules/collectors.py` | Per-host data collection (linux/windows/qnap/local) |
| `modules/ssh_client.py` | Paramiko SSH wrapper with key/password fallback |
| `modules/data_store.py` | `save_data(results, path)` / `load_data(path)` — YAML |
| `modules/context_builder.py` | Builds `homelab-context.md` from scan data |

---

## Integration approach

### Option A — Embed `MainWindow` content as a tab widget (recommended)

Do not embed `QMainWindow` directly — Qt does not support nested main windows.

Instead, extract the scanner UI into a plain `QWidget` subclass and host it in profile_manager as a tab.

**Steps:**

1. **Create `modules/scanner_widget.py`** — extract `MainWindow._build_ui()` content into a `QWidget`.
   - Move toolbar buttons into a `QHBoxLayout` row at the top (no `QToolBar`).
   - Keep all scan logic, state persistence, and worker threads unchanged.
   - Remove `QMainWindow`-specific calls (`addDockWidget`, `addToolBar`, `setStatusBar`).
   - Replace dock widget log panel with a plain `QGroupBox` + `QPlainTextEdit` at the bottom.

2. **Add tab in profile_manager** — in `main_window.py`:
   ```python
   from homelab_scanner.modules.scanner_widget import ScannerWidget
   self._scanner_tab = ScannerWidget(raw_cfg, cfg, cfg_path)
   self.tabs.addTab(self._scanner_tab, "Homelab")
   ```

3. **Config loading** — profile_manager needs to load scanner config on startup:
   ```python
   import json, copy, platform as _platform
   _SCANNER_CFG = "/home/pi/claude/homelab-scanner/config/config.json"

   with open(_SCANNER_CFG) as f:
       raw_cfg = json.load(f)

   platform_key = "windows" if _platform.system() == "Windows" else "pi"
   cfg = copy.deepcopy(raw_cfg)
   cfg["output"] = cfg["platforms"][platform_key]
   for host in cfg.get("hosts", []):
       win_ov = host.pop("windows", None)
       pi_ov = host.pop("pi", None)
       if platform_key == "windows" and win_ov:
           host.update(win_ov)
       elif platform_key == "pi" and pi_ov:
           host.update(pi_ov)
   ```
   Or import `resolve_config` from `homelab_scanner.main` directly.

### Option B — Subprocess launch (minimal effort, not embedded)

Add a toolbar button in profile_manager that launches `python main.py` in the scanner directory.

```python
import subprocess, os
subprocess.Popen(
    ["python", "main.py"],
    cwd="/home/pi/claude/homelab-scanner",
    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
)
```

This keeps the scanner as a separate window — not a real tab integration but takes 10 minutes.

---

## Key classes and signatures

### `ScanWorker(cfg, host_names=None)` — `QThread`
Runs scan in background. `host_names` is an optional list to scan a subset.

Signals:
- `host_done(dict)` — emitted after each host completes
- `all_done(list)` — emitted when all hosts finish
- `log_msg(str)` — log line for display

### `scan(cfg, host_filter=None)` — `cli_runner.py`
Synchronous scan, returns `list[dict]`. Use this from a non-GUI context or a `QThread.run()`.

### `save_data(results, path)` / `load_data(path)` — `data_store.py`
YAML persistence. `results` is `list[dict]` with keys: `name`, `type`, `disk`, `docker`, `ips`, `services`, optionally `error`.

### `build_context(data, context_cfg, path)` — `context_builder.py`
Writes `homelab-context.md`. `data` is what `load_data()` returns. `context_cfg` is `cfg["context"]`.

---

## State persistence

Scanner saves GUI state to `config/gui_state.json` (next to `config.json`).

Keys:
- `geometry` — base64-encoded window geometry
- `splitter` — list of splitter sizes
- `disk_cols`, `docker_cols`, `services_cols`, `settings_hosts_cols` — list of column widths (int)
- `selected_host` — last selected host name
- `auto_refresh`, `refresh_interval` — auto-scan settings

When embedded as a widget, `geometry` is irrelevant but all column widths and selection state still persist correctly via the same file.

---

## Dependencies

```
PyQt6
paramiko
pyyaml
```

Install on ThinkPad: `pip install PyQt6 paramiko pyyaml`

---

## Config file location

`config/config.json` — single file, version-controlled. Contains:
- `ssh` — global SSH settings (key path, timeouts)
- `platforms.pi` / `platforms.windows` — output file paths per OS
- `hosts[]` — host definitions with per-host `pi`/`windows` overrides
- `context` — hardware descriptions and static services (used in context builder)

Per-host overrides example (ThinkPad is `local` on Windows, SSH target on Pi):
```json
{
  "name": "ThinkPad",
  "hostname": "localhost",
  "type": "local",
  "pi": { "hostname": "192.168.0.106", "type": "windows" }
}
```

---

## Suggested refactor before integration

Before embedding, extract scanner UI into `ScannerWidget(QWidget)` in its own file. The current `MainWindow` is straightforward to split — the entire UI is built in `_build_ui()` with no hard dependency on `QMainWindow` beyond the toolbar and dock widget, both of which can be replaced with plain widgets.
