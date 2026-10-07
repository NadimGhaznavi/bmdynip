"""Shared BMDynIP constants."""

from typing import Final


class DBMDynIP:
    VERSION: Final[str] = "2.1.3"
    CMDB_SUBTYPE: Final[str] = "Dynamic DNS Service"
    CMDB_SUPPLIER: Final[str] = "Nadim-Daniel"
    CMDB_CODENAME: Final[str] = "octopus"
    WEB_HOST: Final[str] = "0.0.0.0"
    WEB_PORT: Final[int] = 49700
    WEB_REQUEST_TIMEOUT: Final[int] = 15
    WEB_READY_PATH: Final[str] = "/ready"
    WEB_RUNNER_TIMEOUT: Final[int] = 600
    WEB_SERVICE_FILE: Final[str] = "/etc/systemd/system/bmdynip-web.service"
    SYSTEMCTL: Final[str] = "/usr/bin/systemctl"
    INSTALL_DIR: Final[str] = "/opt/prod/bmdynip"
    STATUS_MESSAGES_FILE: Final[str] = "status-messages.json"
    CREDENTIALS_FILE: Final[str] = "/etc/bmdynip/auto.env"
    ROOT_CREDENTIALS_FILE: Final[str] = "/root/.godaddy-cli"
    GODADDY_CREDENTIAL_NAME: Final[str] = ".godaddy-cli"
    DATABASE_ENV: Final[str] = "/etc/bmdynip/database.env"
    DATABASE_NAME: Final[str] = "bmdynip"
    DATABASE_USER: Final[str] = "bmdynip"
    MARIADB: Final[str] = "/usr/bin/mariadb"
    IP_COMMAND: Final[str] = "/usr/sbin/ip"
    DISCOVERY_TIMEOUT: Final[int] = 10
    ROUTE_TARGET: Final[str] = "1.1.1.1"
    CRON_FILE: Final[str] = "/etc/cron.d/bmdynip"
    GODADDY_CLI: Final[str] = "/opt/prod/godaddy-cli/gddy"
    DNS_SHELL: Final[str] = "/bin/sh"
    GETENT: Final[str] = "/usr/bin/getent"
    DNS_LOOKUP_TIMEOUT: Final[int] = 3
    CRON_SCHEDULE: Final[str] = "*/5 * * * *"
    PUBLIC_IP_URLS: Final[tuple[str, ...]] = (
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
    )
