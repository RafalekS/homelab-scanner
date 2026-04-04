#!/usr/bin/env python
"""Legacy entry point — delegates to main.py / cli_runner."""
import os
import sys
import platform

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CFG_PATH = os.path.join(_BASE_DIR, "config", "config.json")

if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from modules.config_loader import load_raw_config, resolve_config  # noqa: E402


def main():
    raw_cfg = load_raw_config(_CFG_PATH)
    cfg = resolve_config(raw_cfg)

    from modules.cli_runner import run_cli
    run_cli(cfg, _CFG_PATH, sys.argv[1:])


if __name__ == "__main__":
    main()
