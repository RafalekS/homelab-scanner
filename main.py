#!/usr/bin/env python
"""
Homelab Scanner — entry point.
Detects OS and launches GUI (Windows) or CLI (Pi/Linux).
"""
import os
import sys
import platform

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.path.join(_BASE_DIR, "config", "config.json")

# Ensure project root is on sys.path so modules are importable regardless of cwd
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from modules.config_loader import load_raw_config, resolve_config  # noqa: E402


if __name__ == "__main__":
    raw_cfg = load_raw_config(_CFG_PATH)
    cfg = resolve_config(raw_cfg)

    if platform.system() == "Windows":
        from modules.gui_app import run_gui
        run_gui(raw_cfg, cfg, _CFG_PATH)
    else:
        from modules.cli_runner import run_cli
        run_cli(cfg, _CFG_PATH)
