"""Shared BMDynIP constants."""

from typing import Final


class DBMDynIP:
    VERSION: Final[str] = "1.3.0"
    WEB_HOST: Final[str] = "0.0.0.0"
    WEB_PORT: Final[int] = 49700
    WEB_REQUEST_TIMEOUT: Final[int] = 15
    WEB_READY_PATH: Final[str] = "/ready"
    WEB_SERVICE_FILE: Final[str] = "/etc/systemd/system/bmdynip-web.service"
    SYSTEMCTL: Final[str] = "/usr/bin/systemctl"
    INSTALL_DIR: Final[str] = "/opt/prod/bmdynip"
    CREDENTIALS_FILE: Final[str] = "/etc/bmdynip/auto.env"
    ROOT_CREDENTIALS_FILE: Final[str] = "/root/.godaddy-cli"
    DATABASE_ENV: Final[str] = "/etc/bmdynip/database.env"
    DATABASE_NAME: Final[str] = "bmdynip"
    DATABASE_USER: Final[str] = "bmdynip"
    MARIADB: Final[str] = "/usr/bin/mariadb"
    IP_COMMAND: Final[str] = "/usr/sbin/ip"
    DISCOVERY_TIMEOUT: Final[int] = 10
    ROUTE_TARGET: Final[str] = "1.1.1.1"
    CRON_FILE: Final[str] = "/etc/cron.d/bmdynip"
    GODADDY_CLI: Final[str] = "/opt/prod/godaddy-cli/gddy"
    CRON_SCHEDULE: Final[str] = "*/5 * * * *"
    PUBLIC_IP_URLS: Final[tuple[str, ...]] = (
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
    )
