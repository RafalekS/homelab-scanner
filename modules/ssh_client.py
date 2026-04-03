import os
import base64
import logging
import socket
import paramiko

logger = logging.getLogger(__name__)


def ps_encode(script: str) -> str:
    """Base64-encode a PowerShell script for use with -EncodedCommand."""
    return base64.b64encode(script.encode("utf-16-le")).decode()


class SSHConnection:
    """A single open SSH connection. Use as a context manager."""

    def __init__(self, host: dict, cfg: dict):
        self.host = host
        self.command_timeout = cfg["ssh"]["command_timeout"]
        # Per-host key_path overrides the global default
        raw_key = host.get("key_path") or cfg["ssh"].get("key_path", "")
        self._key_path = os.path.expandvars(os.path.expanduser(raw_key)) if raw_key else ""
        self._connect_timeout = cfg["ssh"]["connect_timeout"]
        self._client: paramiko.SSHClient | None = None

    def __enter__(self):
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        hostname = self.host["hostname"]
        user = self.host["user"]
        password = self.host.get("password") or None

        kwargs = {
            "hostname": hostname,
            "username": user,
            "timeout": self._connect_timeout,
            "banner_timeout": self._connect_timeout,
            "auth_timeout": self._connect_timeout,
        }

        # Try key auth first
        if os.path.exists(self._key_path):
            try:
                self._client.connect(**kwargs, key_filename=self._key_path, look_for_keys=False)
                logger.debug(f"{self.host['name']}: connected via key")
                return self
            except (paramiko.AuthenticationException, paramiko.SSHException) as e:
                logger.debug(f"{self.host['name']}: key auth failed ({e}), trying password")

        # Fallback to password
        if password:
            self._client.connect(**kwargs, password=password, look_for_keys=False)
            logger.debug(f"{self.host['name']}: connected via password")
            return self

        raise ConnectionError(
            f"{self.host['name']}: key auth failed and no password configured"
        )

    def __exit__(self, *_):
        if self._client:
            self._client.close()
            self._client = None

    def run(self, command: str) -> str:
        """Run a command and return stdout. Enforces channel-level timeout."""
        transport = self._client.get_transport()
        channel = transport.open_session()
        channel.settimeout(self.command_timeout)
        channel.exec_command(command)

        out = b""
        err = b""
        try:
            while True:
                chunk = channel.recv(4096)
                if not chunk:
                    break
                out += chunk
        except socket.timeout:
            logger.warning(f"{self.host['name']}: command timed out after {self.command_timeout}s: {command[:60]}")

        # Drain stderr non-blocking
        channel.settimeout(2)
        try:
            while True:
                chunk = channel.recv_stderr(4096)
                if not chunk:
                    break
                err += chunk
        except socket.timeout:
            pass

        channel.close()

        if err:
            logger.debug(f"{self.host['name']} stderr: {err.decode('utf-8', errors='replace')[:200]}")
        return out.decode("utf-8", errors="replace").strip()


class SSHClient:
    """Factory for SSHConnection objects."""

    def __init__(self, cfg: dict):
        self._cfg = cfg

    def connect(self, host: dict) -> SSHConnection:
        return SSHConnection(host, self._cfg)
