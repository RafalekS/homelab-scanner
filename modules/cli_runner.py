"""CLI runner for Pi/Linux."""
import os
import sys
import logging
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from modules.collectors import HostCollector
from modules.data_store import save_data, load_data
from modules.context_builder import build_context


def _setup_logging(log_file: str, base_dir: str) -> None:
    if not os.path.isabs(log_file):
        log_file = os.path.join(base_dir, log_file)
    log_file = os.path.expandvars(os.path.expanduser(log_file))
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def scan(cfg: dict, host_filter: list | None = None) -> list[dict]:
    logger = logging.getLogger("scanner")
    collector = HostCollector(cfg)
    hosts = [h for h in cfg["hosts"] if h.get("enabled", True)]
    if host_filter:
        hosts = [h for h in hosts if h["name"] in host_filter]

    results = []

    def collect_one(host):
        logger.info(f"Collecting: {host['name']} ({host['hostname']})")
        try:
            data = collector.collect(host)
            logger.info(f"Done: {host['name']}")
            return data
        except Exception as e:
            logger.error(f"Failed: {host['name']} — {e}")
            return {"name": host["name"], "error": str(e)}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(collect_one, h): h for h in hosts}
        for future in as_completed(futures):
            results.append(future.result())

    order = {h["name"]: i for i, h in enumerate(cfg["hosts"])}
    results.sort(key=lambda r: order.get(r.get("name", ""), 999))
    return results


def run_cli(cfg: dict, cfg_path: str, args: list | None = None) -> None:
    base_dir = os.path.dirname(os.path.abspath(cfg_path))
    _setup_logging(cfg["output"]["log_file"], os.path.dirname(base_dir))
    logger = logging.getLogger("scanner")

    parser = argparse.ArgumentParser(description="Homelab Scanner")
    parser.add_argument("--hosts", nargs="*", metavar="HOST")
    parser.add_argument("--context-only", action="store_true")
    parser.add_argument("--data-only", action="store_true")
    parsed = parser.parse_args(args)

    data_path = os.path.expandvars(os.path.expanduser(cfg["output"]["data_file"]))
    context_path = os.path.expandvars(os.path.expanduser(cfg["output"]["context_file"]))

    if parsed.context_only:
        logger.info("Rebuilding context from existing data...")
        data = load_data(data_path)
        build_context(data, cfg.get("context", {}), context_path)
        return

    results = scan(cfg, host_filter=parsed.hosts)
    save_data(results, data_path)

    if not parsed.data_only:
        data = load_data(data_path)
        build_context(data, cfg.get("context", {}), context_path)
