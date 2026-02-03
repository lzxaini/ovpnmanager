from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_name: str = "OpenVPN Web Admin"
    api_v1_prefix: str = "/api"
    deploy_env: str = "DEV"  # DEV / PROD
    log_level: str = "INFO"
    log_file: Path | None = None
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5
    sqlite_path: Path = Path(__file__).resolve().parents[2] / "data" / "app.db"
    cors_origins: list[AnyHttpUrl] | list[str] = [
        "http://localhost:8010",
        "http://127.0.0.1:8010",
        "http://192.168.1.182:8010",
    ]
    secret_key: str = "change-me-in-prod"
    access_token_expire_minutes: int = 60
    openvpn_service_name: str = "openvpn@server"
    openvpn_status_path: Path = Path("/var/log/openvpn/openvpn-status.log")
    openvpn_management_host: str = "127.0.0.1"
    openvpn_management_port: int = 7505
    openvpn_crl_path: Path = Path("/etc/openvpn/crl.pem")
    openvpn_client_export_path: Path = Path("/etc/openvpn/client-configs")
    ta_key_path: Path = Path("/etc/openvpn/server/ta.key")
    tls_auth_mode: str = "tls-crypt-v2"  # tls-crypt-v2 | tls-crypt | tls-auth
    tls_crypt_v2_key_path: Path = Path("/etc/openvpn/server/tls-crypt-v2.key")
    tls_crypt_key_path: Path = Path("/etc/openvpn/server/tls-crypt.key")
    server_conf_path: Path = Path("/etc/openvpn/server.conf")
    public_ip: str | None = None
    public_port: int | None = None
    default_admin_username: str = "admin"
    default_admin_password: str = "admin123"  # override via env
    openvpn_base_path: Path = Path("/etc/openvpn")
    easyrsa_path: Path = Path("/etc/openvpn/easy-rsa")
    ccd_path: Path = Path("/etc/openvpn/ccd")

@lru_cache
def get_settings() -> Settings:
    return Settings()
