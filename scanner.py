#!/usr/bin/env python
"""Legacy entry point — delegates to main.py / cli_runner."""
import os
import sys
import json
import copy
import platform

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.path.join(_BASE_DIR, "config", "config.json")


def main():
    with open(_CFG_PATH, "r", encoding="utf-8") as f:
        raw_cfg = json.load(f)

    platform_key = "windows" if platform.system() == "Windows" else "pi"
    cfg = copy.deepcopy(raw_cfg)
    cfg["output"] = cfg["platforms"][platform_key]
    for host in cfg.get("hosts", []):
        win_overrides = host.pop("windows", None)
        pi_overrides = host.pop("pi", None)
        if platform_key == "windows" and win_overrides:
            host.update(win_overrides)
        elif platform_key == "pi" and pi_overrides:
            host.update(pi_overrides)

    from modules.cli_runner import run_cli
    run_cli(cfg, _CFG_PATH, sys.argv[1:])


if __name__ == "__main__":
    main()
