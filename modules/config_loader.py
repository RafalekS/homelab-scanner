import os
import json
import copy
import platform


def load_raw_config(cfg_path: str) -> dict:
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_config(raw: dict) -> dict:
    """Flatten platform section into cfg['output'] and apply per-host platform overrides."""
    cfg = copy.deepcopy(raw)
    platform_key = "windows" if platform.system() == "Windows" else "pi"
    cfg["output"] = cfg["platforms"][platform_key]
    for host in cfg.get("hosts", []):
        win_overrides = host.pop("windows", None)
        pi_overrides = host.pop("pi", None)
        if platform_key == "windows" and win_overrides:
            host.update(win_overrides)
        elif platform_key == "pi" and pi_overrides:
            host.update(pi_overrides)
    return cfg
