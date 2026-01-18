from ipaddress import ip_network
from pathlib import Path
from typing import Iterable

from app.core.config import get_settings
from app.models.client import Client


settings = get_settings()


def _format_route(route: str) -> str:
    """Convert route string to iroute line; accept '192.168.1.0/24' or '192.168.1.0 255.255.255.0'."""
    route = route.strip()
    if "/" in route:
        net = ip_network(route, strict=False)
        return f"iroute {net.network_address} {net.netmask}"
    parts = route.split()
    if len(parts) == 2:
        return f"iroute {parts[0]} {parts[1]}"
    # fallback: treat as comment
    return f"# invalid route format: {route}"


def write_ccd(client: Client, *, fixed_ip: str | None, routes: Iterable[str] | None = None) -> Path:
    """Write CCD file for client with optional static IP and per-client routes."""
    ccd_dir = Path(settings.ccd_path)
    ccd_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if fixed_ip:
        # default netmask assumes /24; adjust if you maintain different pool netmask
        lines.append(f"ifconfig-push {fixed_ip} 255.255.255.0")
    if routes:
        lines.extend(_format_route(r) for r in routes if r)
    path = ccd_dir / client.common_name
    path.write_text("\n".join(lines) + ("\n" if lines else ""))
    return path
