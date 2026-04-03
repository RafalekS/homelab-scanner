import os
import logging

logger = logging.getLogger(__name__)


def _disk_table(disk_list: list) -> str:
    if not disk_list:
        return "  _no disk data_"
    lines = ["  | Mount | Size | Used | Avail | Use% |",
             "  |-------|------|------|-------|------|"]
    for d in disk_list:
        lines.append(
            f"  | {d.get('mount','?')} | {d.get('size','?')} | "
            f"{d.get('used','?')} | {d.get('avail','?')} | {d.get('use_pct','?')} |"
        )
    return "\n".join(lines)


def _docker_list(containers: list) -> str:
    if not containers:
        return "  _none running_"
    return "\n".join(f"  - {c['name']} ({c['image']}) — {c['status']}" for c in containers)


def _services_list(services: dict) -> str:
    if not services:
        return "  _none checked_"
    return "\n".join(f"  - {svc}: {status}" for svc, status in services.items())


def build_context(data: dict, context_cfg: dict, output_path: str) -> None:
    updated = data.get("updated", "unknown")
    hosts = data.get("hosts", [])
    hardware = context_cfg.get("hardware", {})
    extra_hardware = context_cfg.get("extra_hardware", [])
    static_services = context_cfg.get("static_services", [])

    lines = ["# Homelab Context", "", f"_Last updated: {updated}_", "", "## Hardware"]

    for name, desc in hardware.items():
        lines.append(f"- **{name}**: {desc}")
    for item in extra_hardware:
        lines.append(f"- {item}")
    lines.append("")

    if static_services:
        lines.append("## Key services")
        for svc in static_services:
            lines.append(f"- {svc}")
        lines.append("")

    lines.append("## Live Status")
    lines.append("")

    host_map = {h["name"]: h for h in hosts if "error" not in h}

    for name in hardware:
        host = host_map.get(name)
        if not host:
            lines.append(f"### {name} _(unreachable)_")
            lines.append("")
            continue

        lines.append(f"### {name}")

        ips = host.get("ips", [])
        if ips:
            lines.append(f"**IPs:** {', '.join(ips)}")
        lines.append("")

        disk = host.get("disk")
        if disk is not None:
            lines.append("**Disk:**")
            lines.append(_disk_table(disk))

        docker = host.get("docker")
        if docker is not None:
            lines.append("")
            lines.append("**Docker containers:**")
            lines.append(_docker_list(docker))

        services = host.get("services", {})
        if services:
            lines.append("")
            lines.append("**Services:**")
            lines.append(_services_list(services))

        lines.append("")

    lines.append("## Active homelab projects")
    lines.append("- [add current projects here]")
    lines.append("- See [[Projects/]] folder for individual project notes")
    lines.append("")

    output_path = os.path.expandvars(os.path.expanduser(output_path))
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    logger.info(f"Context written to {output_path}")
