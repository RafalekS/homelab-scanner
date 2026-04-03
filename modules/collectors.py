import subprocess
import logging
from .ssh_client import SSHClient, ps_encode

logger = logging.getLogger(__name__)

_ALL_COLLECT = ["disk", "docker", "ips", "services"]


# ── Linux / QNAP commands ─────────────────────────────────────────────────────

LINUX_DISK_CMD = (
    "df -h --output=source,size,used,avail,pcent,target "
    "| grep -v tmpfs | grep -v udev | tail -n +2"
)
LINUX_IPS_CMD = "hostname -I"
LINUX_DOCKER_CMD = (
    "docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}' 2>/dev/null || echo ''"
)

# ── Windows PowerShell scripts (passed via -EncodedCommand) ──────────────────

_WIN_DISK_PS = (
    "Get-PSDrive -PSProvider FileSystem | "
    "ForEach-Object { $_.Name + '|' + [math]::Round($_.Used/1GB,1) + '|' + [math]::Round($_.Free/1GB,1) }"
)
_WIN_IPS_PS = (
    "(Get-NetIPAddress -AddressFamily IPv4 "
    "| Where-Object { $_.IPAddress -ne '127.0.0.1' }).IPAddress -join ' '"
)
_WIN_DOCKER_PS = "docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}' 2>$null"
_WIN_SERVICE_PS_TMPL = "(Get-Service -Name '{service}' -ErrorAction SilentlyContinue).Status"

WIN_DISK_CMD = f"powershell -NoProfile -EncodedCommand {ps_encode(_WIN_DISK_PS)}"
WIN_IPS_CMD = f"powershell -NoProfile -EncodedCommand {ps_encode(_WIN_IPS_PS)}"
WIN_DOCKER_CMD = f"powershell -NoProfile -EncodedCommand {ps_encode(_WIN_DOCKER_PS)}"


def win_service_cmd(service: str) -> str:
    return f"powershell -NoProfile -EncodedCommand {ps_encode(_WIN_SERVICE_PS_TMPL.format(service=service))}"


# ── QNAP commands ─────────────────────────────────────────────────────────────

QNAP_DOCKER = "/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker"
QNAP_DISK_CMD = "df -h /mnt/HDA_ROOT /share/CACHEDEV*_DATA 2>/dev/null"
QNAP_IPS_CMD = "ip addr show | grep 'inet 192\\.168'"
QNAP_DOCKER_CMD = f"{QNAP_DOCKER} ps --format '{{{{.Names}}}}|{{{{.Image}}}}|{{{{.Status}}}}' 2>/dev/null || echo ''"


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_linux_disk(raw: str) -> list[dict]:
    rows = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        mount = parts[-1]
        use_pct = parts[-2]
        avail = parts[-3]
        used = parts[-4]
        size = parts[-5]
        source = " ".join(parts[:-5])
        rows.append({
            "source": source,
            "size": size,
            "used": used,
            "avail": avail,
            "use_pct": use_pct,
            "mount": mount,
        })
    return rows


def _parse_win_disk(raw: str) -> list[dict]:
    rows = []
    for line in raw.splitlines():
        parts = line.strip().split("|")
        if len(parts) != 3:
            continue
        name, used_str, free_str = parts
        try:
            used = float(used_str)
            free = float(free_str)
            total = used + free
            pct = f"{round(used / total * 100)}%" if total > 0 else "N/A"
            rows.append({
                "source": name + ":",
                "size": f"{round(total, 1)}G",
                "used": f"{used}G",
                "avail": f"{free}G",
                "use_pct": pct,
                "mount": name + ":",
            })
        except ValueError:
            pass
    return rows


def _parse_qnap_disk(raw: str) -> list[dict]:
    """Parse QNAP df output — busybox df wraps long source lines onto the next line."""
    import re as _re
    rows = []
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("Filesystem"):
            i += 1
            continue
        parts = line.split()
        if len(parts) == 1 and i + 1 < len(lines):
            parts = parts + lines[i + 1].split()
            i += 2
        else:
            i += 1
        if len(parts) < 6:
            continue
        source = parts[0]
        size, used, avail, use_pct, mount = parts[1], parts[2], parts[3], parts[4], parts[5]
        if mount == "/mnt/HDA_ROOT" or _re.match(r"^/share/CACHEDEV\d+_DATA$", mount):
            rows.append({
                "source": source,
                "size": size,
                "used": used,
                "avail": avail,
                "use_pct": use_pct,
                "mount": mount,
            })
    return rows


def _parse_docker(raw: str) -> list[dict]:
    containers = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            containers.append({"name": parts[0], "image": parts[1], "status": parts[2]})
    return containers


# ── Collector ─────────────────────────────────────────────────────────────────

class HostCollector:
    def __init__(self, cfg: dict):
        self.ssh = SSHClient(cfg)

    def collect(self, host: dict) -> dict:
        htype = host["type"]
        if htype == "local":
            return self._collect_local(host)
        elif htype == "windows":
            return self._collect_windows(host)
        elif htype == "qnap":
            return self._collect_qnap(host)
        elif htype == "linux":
            return self._collect_linux(host)
        else:
            logger.warning(f"{host['name']}: unknown host type '{htype}', skipping")
            return {"name": host["name"], "error": f"unknown type: {htype}"}

    def _collect_local(self, host: dict) -> dict:
        import platform as _platform
        name = host["name"]
        data = {"name": name, "type": "local"}
        collect = set(host.get("collect", _ALL_COLLECT))
        is_windows = _platform.system() == "Windows"

        def run_local(cmd):
            try:
                return subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=10
                ).stdout.strip()
            except Exception as e:
                logger.error(f"{name}: local command failed — {e}")
                return ""

        if is_windows:
            if "disk" in collect:
                data["disk"] = _parse_win_disk(run_local(WIN_DISK_CMD))
            if "ips" in collect:
                data["ips"] = [
                    ip for ip in run_local(WIN_IPS_CMD).split()
                    if not ip.startswith("169.254")
                ]
            if "docker" in collect:
                data["docker"] = _parse_docker(run_local(WIN_DOCKER_CMD))
            if "services" in collect:
                data["services"] = {}
                for svc in host.get("services_check", []):
                    out = run_local(win_service_cmd(svc))
                    data["services"][svc] = out or "unknown"
        else:
            if "disk" in collect:
                data["disk"] = _parse_linux_disk(run_local(LINUX_DISK_CMD))
            if "ips" in collect:
                data["ips"] = [ip for ip in run_local(LINUX_IPS_CMD).split() if ":" not in ip]
            if "docker" in collect:
                data["docker"] = _parse_docker(run_local(LINUX_DOCKER_CMD))
            if "services" in collect:
                data["services"] = {}
                for svc in host.get("services_check", []):
                    out = run_local(f"systemctl is-active {svc} 2>/dev/null")
                    data["services"][svc] = out or "not-found"
        return data

    def _collect_linux(self, host: dict) -> dict:
        name = host["name"]
        data = {"name": name, "type": host["type"]}
        collect = set(host.get("collect", _ALL_COLLECT))
        try:
            with self.ssh.connect(host) as conn:
                if "disk" in collect:
                    data["disk"] = _parse_linux_disk(conn.run(LINUX_DISK_CMD))
                if "ips" in collect:
                    data["ips"] = [ip for ip in conn.run(LINUX_IPS_CMD).split() if ":" not in ip]
                if "docker" in collect:
                    data["docker"] = _parse_docker(conn.run(LINUX_DOCKER_CMD))
                if "services" in collect:
                    data["services"] = {}
                    for svc in host.get("services_check", []):
                        out = conn.run(f"systemctl is-active {svc} 2>/dev/null")
                        data["services"][svc] = out or "not-found"
        except Exception as e:
            logger.error(f"{name}: connection failed — {e}")
            data["error"] = str(e)
        return data

    def _collect_qnap(self, host: dict) -> dict:
        name = host["name"]
        data = {"name": name, "type": "qnap"}
        collect = set(host.get("collect", _ALL_COLLECT))
        try:
            with self.ssh.connect(host) as conn:
                if "disk" in collect:
                    data["disk"] = _parse_qnap_disk(conn.run(QNAP_DISK_CMD))
                if "ips" in collect:
                    ips = []
                    for line in conn.run(QNAP_IPS_CMD).splitlines():
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            ips.append(parts[1].split("/")[0])
                    data["ips"] = ips
                if "docker" in collect:
                    data["docker"] = _parse_docker(conn.run(QNAP_DOCKER_CMD))
                data["services"] = {}
        except Exception as e:
            logger.error(f"{name}: connection failed — {e}")
            data["error"] = str(e)
        return data

    def _collect_windows(self, host: dict) -> dict:
        name = host["name"]
        data = {"name": name, "type": "windows"}
        collect = set(host.get("collect", _ALL_COLLECT))
        try:
            with self.ssh.connect(host) as conn:
                if "disk" in collect:
                    data["disk"] = _parse_win_disk(conn.run(WIN_DISK_CMD))
                if "ips" in collect:
                    data["ips"] = [
                        ip for ip in conn.run(WIN_IPS_CMD).split()
                        if not ip.startswith("169.254")
                    ]
                if "docker" in collect:
                    data["docker"] = _parse_docker(conn.run(WIN_DOCKER_CMD))
                if "services" in collect:
                    data["services"] = {}
                    for svc in host.get("services_check", []):
                        out = conn.run(win_service_cmd(svc))
                        data["services"][svc] = out or "unknown"
        except Exception as e:
            logger.error(f"{name}: connection failed — {e}")
            data["error"] = str(e)
        return data
