import subprocess
from typing import Literal

from app.core.config import get_settings

settings = get_settings()

ServiceAction = Literal["status", "start", "stop", "restart"]


def service_action(action: ServiceAction) -> str:
    cmd = ["systemctl", action, settings.openvpn_service_name]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "OpenVPN service command failed")
    return result.stdout.strip() or "ok"


def reload_config_sigusr1() -> str:
    """Send SIGUSR1 to OpenVPN to reload config/CRL without dropping tunnels."""
    result = subprocess.run(["killall", "-SIGUSR1", "openvpn"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "OpenVPN reload failed")
    return "reloaded"
