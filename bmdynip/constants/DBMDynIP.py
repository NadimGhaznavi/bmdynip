"""Shared BMDynIP constants."""

from typing import Final


class DBMDynIP:
    VERSION: Final[str] = "1.0.1"
    WEB_HOST: Final[str] = "0.0.0.0"
    WEB_PORT: Final[int] = 49700
    WEB_REQUEST_TIMEOUT: Final[int] = 15
    INSTALL_DIR: Final[str] = "/opt/prod/bmdynip"
    CREDENTIALS_FILE: Final[str] = "/etc/bmdynip/auto.env"
    CRON_FILE: Final[str] = "/etc/cron.d/bmdynip"
    GODADDY_CLI: Final[str] = "/opt/prod/godaddy-cli/gddy"
    CRON_SCHEDULE: Final[str] = "*/5 * * * *"
    PUBLIC_IP_URLS: Final[tuple[str, ...]] = (
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
    )
