"""Shared MyDynIP constants."""

from typing import Final


class DMyDynIP:
    VERSION: Final[str] = "0.2.0"
    INSTALL_DIR: Final[str] = "/opt/prod/mydynip"
    CREDENTIALS_FILE: Final[str] = "/etc/mydynip/auto.env"
    CRON_FILE: Final[str] = "/etc/cron.d/mydynip"
    GODADDY_CLI: Final[str] = "/opt/prod/godaddy-cli/gddy"
    CRON_SCHEDULE: Final[str] = "*/5 * * * *"
    PUBLIC_IP_URLS: Final[tuple[str, ...]] = (
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
    )
