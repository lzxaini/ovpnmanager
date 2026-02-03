import subprocess
from typing import Literal
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

ServiceAction = Literal["status", "start", "stop", "restart"]


def _check_process_running() -> bool:
    """检查 OpenVPN 进程是否在运行"""
    try:
        # 检查进程
        result = subprocess.run(
            ["pgrep", "-f", "openvpn.*server"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_management_socket() -> bool:
    """检查 Management Socket 是否存在(用于 Unix Socket 模式)"""
    try:
        if hasattr(settings, 'openvpn_management_socket'):
            socket_path = Path(settings.openvpn_management_socket)
            return socket_path.exists()
    except Exception:
        pass
    return False


def service_action(action: ServiceAction) -> str:
    """
    执行服务操作
    注意: 在容器环境中无法使用 systemctl,改为检查进程状态
    """
    
    if action == "status":
        # 在容器中,通过检查进程和 socket 判断状态
        is_running = _check_process_running()
        has_socket = _check_management_socket()
        
        if is_running or has_socket:
            return "Active: active (running)\nOpenVPN process detected"
        else:
            return "Active: inactive (dead)\nOpenVPN process not found"
    
    # start/stop/restart 操作在容器中无法执行
    # 返回提示信息
    return f"Container mode: Cannot perform '{action}' action. Please use host system to manage OpenVPN service: systemctl {action} {settings.openvpn_service_name}"


def reload_config_sigusr1() -> str:
    """Send SIGUSR1 to OpenVPN to reload config/CRL without dropping tunnels."""
    result = subprocess.run(["killall", "-SIGUSR1", "openvpn"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "OpenVPN reload failed")
    return "reloaded"
