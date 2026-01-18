"""OpenVPN management 接口相关工具函数（含中文注释）。"""

import socket
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings


settings = get_settings()


@dataclass
class OnlineClient:
    """在线客户端信息（来自 management 或 status 文件）。"""
    common_name: str
    real_address: str
    virtual_address: str
    bytes_received: int
    bytes_sent: int
    connected_since: str
    client_id: str | None = None


@dataclass
class RoutingEntry:
    """路由表条目（来自 status 3 输出）。"""
    virtual_address: str
    real_address: str
    last_ref: str
    common_name: str


@dataclass
class StatusDetails:
    """状态详情：标题、时间、全局指标、路由表。"""
    title: str | None
    time_unix: int | None
    time_str: str | None
    global_stats: dict[str, int | str]
    routing_table: list[RoutingEntry]


@dataclass
class LoadStats:
    """load-stats 汇总：在线数、流量、运行时长。"""
    nclients: int | None
    bytes_in: int | None
    bytes_out: int | None
    uptime: int | None


@dataclass
class StateEvent:
    """连接状态事件（state 输出）。"""
    timestamp: int | None
    state: str
    detail: str | None
    virtual_address: str | None
    common_name: str | None
    real_address: str | None


def _send_command(cmd: str) -> list[str]:
    """向 management 接口发送命令并返回行列表。"""
    with socket.create_connection((settings.openvpn_management_host, settings.openvpn_management_port), timeout=3) as sock:
        sock.recv(4096)  # banner
        sock.sendall((cmd + "\n").encode())
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"END" in chunk or b"SUCCESS" in chunk or b"ERROR" in chunk:
                # management interface typically ends status output with "END"
                break
        return data.decode().splitlines()


def _parse_client_lines(lines: list[str]) -> list[OnlineClient]:
    """解析 CLIENT_LIST 行（management 或 status 文件）。"""
    clients: list[OnlineClient] = []
    for line in lines:
        if not line.startswith("CLIENT_LIST"):
            continue
        # Support both comma and tab separated formats
        parts = line.split("\t") if "\t" in line else line.split(",")
        if len(parts) < 3:
            continue
        cn = parts[1]
        real_addr = parts[2] if len(parts) > 2 else ""
        virt_addr = parts[3] if len(parts) > 3 else ""
        try:
            b_recv = int(parts[5]) if len(parts) > 5 and parts[5] else 0
        except ValueError:
            b_recv = 0
        try:
            b_sent = int(parts[6]) if len(parts) > 6 and parts[6] else 0
        except ValueError:
            b_sent = 0
        connected_since = parts[7] if len(parts) > 7 else ""
        client_id = parts[10] if len(parts) > 10 else None
        clients.append(
            OnlineClient(
                common_name=cn,
                real_address=real_addr,
                virtual_address=virt_addr,
                bytes_received=b_recv,
                bytes_sent=b_sent,
                connected_since=connected_since,
                client_id=client_id,
            )
        )
    return clients


def _parse_status_file(path: Path) -> list[OnlineClient]:
    """兜底：无法访问 management 时解析 status 文件。"""
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    return _parse_client_lines(lines)


def list_online() -> list[OnlineClient]:
    """获取在线客户端，优先 management，失败则读 status 文件。"""
    try:
        lines = _send_command("status 3")
        clients = _parse_client_lines(lines)
        if clients:
            return clients
    except Exception:
        # fall back to status file below
        pass
    return _parse_status_file(settings.openvpn_status_path)


def disconnect(common_name: str) -> str:
    """按证书 CN 踢下线客户端。"""
    lines = _send_command(f"kill {common_name}")
    if any("SUCCESS" in line for line in lines):
        return "disconnected"
    raise RuntimeError("Disconnect failed: " + ";".join(lines))


def _split(line: str) -> list[str]:
    return line.split("\t") if "\t" in line else line.split(",")


def status_details() -> StatusDetails:
    """解析 `status 3` 获取标题、时间、全局指标与路由表。"""
    lines = _send_command("status 3")
    title = None
    time_unix: int | None = None
    time_str: str | None = None
    global_stats: dict[str, int | str] = {}
    routing_table: list[RoutingEntry] = []
    for line in lines:
        if line.startswith("TITLE"):
            parts = _split(line)
            if len(parts) >= 2:
                title = ",".join(parts[1:]).strip()
        elif line.startswith("TIME"):
            parts = _split(line)
            if len(parts) >= 3:
                try:
                    time_unix = int(parts[1])
                except ValueError:
                    time_unix = None
                time_str = parts[2]
        elif line.startswith("GLOBAL_STATS"):
            parts = _split(line)
            if len(parts) >= 3:
                key = parts[1]
                raw = parts[2]
                try:
                    global_stats[key] = int(raw)
                except ValueError:
                    global_stats[key] = raw
        elif line.startswith("ROUTING_TABLE"):
            parts = _split(line)
            # ROUTING_TABLE,10.8.0.2,client/1.2.3.4:5678,1700000000,client1
            if len(parts) >= 5:
                routing_table.append(
                    RoutingEntry(
                        virtual_address=parts[1],
                        real_address=parts[2],
                        last_ref=parts[3],
                        common_name=parts[4],
                    )
                )
    return StatusDetails(
        title=title,
        time_unix=time_unix,
        time_str=time_str,
        global_stats=global_stats,
        routing_table=routing_table,
    )


def load_stats() -> LoadStats:
    """
    使用 `load-stats`（若可用）获取在线数、流量、运行时长。
    格式示例：SUCCESS: nclients=1,bytesin=100,bytesout=200,uptime=3600
    """
    lines = _send_command("load-stats")
    for line in lines:
        if "SUCCESS" not in line:
            continue
        payload = line.split("SUCCESS:", 1)[1].strip()
        parts = [p.strip() for p in payload.split(",") if "=" in p]
        data: dict[str, int | None] = {"nclients": None, "bytesin": None, "bytesout": None, "uptime": None}
        for part in parts:
            k, v = part.split("=", 1)
            try:
                data[k] = int(v)
            except ValueError:
                data[k] = None
        return LoadStats(
            nclients=data.get("nclients"),
            bytes_in=data.get("bytesin"),
            bytes_out=data.get("bytesout"),
            uptime=data.get("uptime"),
        )
    raise RuntimeError("load-stats not supported")


def state_history(limit: int = 10) -> list[StateEvent]:
    """返回最近的连接状态事件（默认 10 条）。"""
    lines = _send_command("state")
    events: list[StateEvent] = []
    for line in lines:
        if not line or line.startswith(("END", "SUCCESS", ">")):
            continue
        parts = _split(line)
        if len(parts) < 2:
            continue
        ts = None
        try:
            ts = int(parts[0])
        except ValueError:
            pass
        state = parts[1]
        detail = parts[2] if len(parts) > 2 else None
        virtual = parts[3] if len(parts) > 3 else None
        common = parts[4] if len(parts) > 4 else None
        real = parts[5] if len(parts) > 5 else None
        events.append(
            StateEvent(
                timestamp=ts,
                state=state,
                detail=detail,
                virtual_address=virtual,
                common_name=common,
                real_address=real,
            )
        )
    return events[:limit]

