import os
import logging
from datetime import datetime, timezone
import yaml

logger = logging.getLogger(__name__)


def save_data(results: list[dict], path: str) -> None:
    path = os.path.expandvars(os.path.expanduser(path))
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    payload = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hosts": results,
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    logger.info(f"Data saved to {path}")


def load_data(path: str) -> dict:
    path = os.path.expandvars(os.path.expanduser(path))
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
