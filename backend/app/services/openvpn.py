import subprocess
from typing import Literal

from app.core.config import get_settings

settings = get_settings()

ServiceAction = Literal["status", "start", "stop", "restart"]


def service_action(action: ServiceAction) -> str:
    """
    执行 systemd 服务操作
    注意: 需要容器以 privileged 模式运行并挂载 systemd socket
    """
    cmd = ["systemctl", action, settings.openvpn_service_name]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        # systemctl status 返回非0状态码也是正常的(服务未运行时)
        if action == "status":
            # 返回完整输出用于状态判断
            return result.stdout + result.stderr
        
        # 其他操作必须成功
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "OpenVPN service command failed"
            raise RuntimeError(error_msg)
            
        return result.stdout.strip() or "ok"
        
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Command timeout: systemctl {action} {settings.openvpn_service_name}")
    except FileNotFoundError:
        raise RuntimeError("systemctl command not found. Container may not have systemd access.")
    except Exception as e:
        raise RuntimeError(f"Failed to execute systemctl: {str(e)}")


def reload_config_sigusr1() -> str:
    """Send SIGUSR1 to OpenVPN to reload config/CRL without dropping tunnels."""
    result = subprocess.run(["killall", "-SIGUSR1", "openvpn"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "OpenVPN reload failed")
    return "reloaded"
