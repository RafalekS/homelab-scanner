#!/usr/bin/env python
"""
Homelab Scanner — entry point.
Detects OS and launches GUI (Windows) or CLI (Pi/Linux).
"""
import os
import sys
import json
import copy
import platform

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.path.join(_BASE_DIR, "config", "config.json")


def load_raw_config() -> dict:
    with open(_CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_config(raw: dict) -> dict:
    """Flatten platform section into cfg['output'] and apply per-host platform overrides."""
    cfg = copy.deepcopy(raw)
    platform_key = "windows" if platform.system() == "Windows" else "pi"
    cfg["output"] = cfg["platforms"][platform_key]
    for host in cfg.get("hosts", []):
        overrides = host.pop("windows", None)
        host.pop("pi", None)
        if platform_key == "windows" and overrides:
            host.update(overrides)
    return cfg


if __name__ == "__main__":
    raw_cfg = load_raw_config()
    cfg = resolve_config(raw_cfg)

    if platform.system() == "Windows":
        from modules.gui_app import run_gui
        run_gui(raw_cfg, cfg, _CFG_PATH)
    else:
        from modules.cli_runner import run_cli
        run_cli(cfg, _CFG_PATH)
