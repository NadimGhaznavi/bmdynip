"""Install, restart, or remove BMDynIP's updater and Web UI service."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import venv
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import zipapp

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.Configuration import Configuration
from bmdynip.interface.IpState import IpState
from bmdynip.interface.DatabaseProvisioning import DatabaseProvisioning


def systemctl(*arguments: str) -> None:
    subprocess.run([DBMDynIP.SYSTEMCTL, *arguments], check=True, timeout=30)


def start_web(action: str) -> None:
    service = Path(DBMDynIP.WEB_SERVICE_FILE).name
    systemctl(action, service)
    url = f"http://127.0.0.1:{DBMDynIP.WEB_PORT}{DBMDynIP.WEB_READY_PATH}"
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + 10
    while True:
        try:
            systemctl("is-active", "--quiet", service)
            with opener.open(Request(url, method="HEAD"), timeout=1) as response:
                if response.status != 200:
                    raise ValueError(f"Web UI returned HTTP {response.status} on port {DBMDynIP.WEB_PORT}.")
            break
        except subprocess.CalledProcessError as error:
            if error.returncode != 3:
                raise
            if time.monotonic() >= deadline:
                raise ValueError(f"Web UI service did not become active; check "
                                 f"journalctl -u {service}.") from None
            time.sleep(0.1)
        except HTTPError as error:
            status = error.code
            error.close()
            if status != 503:
                raise ValueError(f"Web UI readiness returned HTTP {status} on port "
                                 f"{DBMDynIP.WEB_PORT}; check journalctl -u {service}.") from None
            if time.monotonic() >= deadline:
                raise ValueError(f"Web UI database readiness timed out on port {DBMDynIP.WEB_PORT}; "
                                 f"check database availability, credentials, and schema, and "
                                 f"journalctl -u {service}.") from None
            time.sleep(0.1)
        except (URLError, TimeoutError):
            if time.monotonic() >= deadline:
                raise ValueError(f"Web UI readiness did not respond on port {DBMDynIP.WEB_PORT}; "
                                 f"check journalctl -u {service}.") from None
            time.sleep(0.1)
    print(f"BMDynIP Web UI: active on port {DBMDynIP.WEB_PORT} (listening on {DBMDynIP.WEB_HOST})")


def restart() -> None:
    start_web("restart")


def install_dependencies(target: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="bmdynip-dependencies-") as directory:
        venv.EnvBuilder(with_pip=True).create(directory)
        python = Path(directory) / "bin/python"
        subprocess.run(
            [str(python), "-m", "pip", "--disable-pip-version-check", "install",
             "--no-cache-dir", "--no-compile", "--target", str(target),
             "-r", str(REPOSITORY / "requirements.txt")],
            check=True, timeout=180,
        )


def install(*, upgrading: bool = False) -> None:
    for executable in ("/usr/bin/python3", "/usr/bin/curl", "/usr/bin/logger",
                       DBMDynIP.GODADDY_CLI, DBMDynIP.SYSTEMCTL, DBMDynIP.MARIADB, DBMDynIP.GETENT):
        if not os.access(executable, os.X_OK):
            raise ValueError(f"Required executable is missing: {executable}")
    root = Path(DBMDynIP.INSTALL_DIR)
    config = root / "conf" / "bmdynip.json"
    Configuration.domain(config if config.exists() else REPOSITORY / "conf" / "bmdynip.json")
    DatabaseProvisioning(REPOSITORY / "schema/bmdynip-schema-v1.sql").provision()
    for name in ("bin", "conf", "data"):
        (root / name).mkdir(parents=True, exist_ok=True)
        (root / name).chmod(0o700 if name != "bin" else 0o755)
    root.chmod(0o755)
    with IpState(root / "data").lock(blocking=True):
        if not config.exists():
            shutil.copyfile(REPOSITORY / "conf" / "bmdynip.json", config)
        config.chmod(0o600)
        with tempfile.TemporaryDirectory(prefix="bmdynip-install-") as staging:
            staged = Path(staging)
            install_dependencies(staged)
            shutil.copytree(REPOSITORY / "bmdynip", staged / "bmdynip",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.copyfile(REPOSITORY / "pages/images/bmdynip-logo.png",
                            staged / "bmdynip/server/static/bmdynip-logo.png")
            if upgrading:
                systemctl("stop", Path(DBMDynIP.WEB_SERVICE_FILE).name)
            (staged / "__main__.py").write_text(
                "from bmdynip.app.main import main\nraise SystemExit(main())\n")
            temporary = root / "bin" / ".bmdynip.new"
            try:
                zipapp.create_archive(staged, target=temporary,
                                      interpreter="/usr/bin/python3")
                temporary.chmod(0o755)
                temporary.replace(root / "bin" / "bmdynip")
            finally:
                temporary.unlink(missing_ok=True)
            (staged / "__main__.py").write_text(
                "from bmdynip.server.__main__ import main\nmain()\n")
            temporary_web = root / "bin" / ".bmdynip-web.new"
            try:
                zipapp.create_archive(staged, target=temporary_web,
                                      interpreter="/usr/bin/python3")
                temporary_web.chmod(0o755)
                temporary_web.replace(root / "bin" / "bmdynip-web")
            finally:
                temporary_web.unlink(missing_ok=True)
            constants = root / "bmdynip" / "constants"
            for directory in (constants.parent, constants):
                directory.mkdir(exist_ok=True)
                directory.chmod(0o755)
            temporary_constants = constants / ".DBMDynIP.new"
            try:
                shutil.copyfile(staged / "bmdynip/constants/DBMDynIP.py", temporary_constants)
                temporary_constants.chmod(0o644)
                temporary_constants.replace(constants / "DBMDynIP.py")
            finally:
                temporary_constants.unlink(missing_ok=True)
            # Use the dependency staged for the archives, without requiring global packages.
            sys.path.insert(0, str(staged))
            try:
                from bmdynip.interface.RunnerSchedule import RunnerSchedule
                schedule = RunnerSchedule().install()
            finally:
                sys.path.remove(str(staged))
    service = Path(DBMDynIP.WEB_SERVICE_FILE)
    service.write_text(
        "[Unit]\nDescription=BMDynIP Web UI\nAfter=network.target\n\n"
        "[Service]\nType=exec\nUser=root\n"
        f"ExecStart={root}/bin/bmdynip-web --host {DBMDynIP.WEB_HOST} --port {DBMDynIP.WEB_PORT}\n"
        "Restart=on-failure\nRestartSec=2\n\n[Install]\nWantedBy=multi-user.target\n")
    service.chmod(0o644)
    systemctl("daemon-reload")
    systemctl("enable", service.name)
    if upgrading:
        start_web("start")
    else:
        restart()
    print(f"Installed BMDynIP {DBMDynIP.VERSION}; runner schedule: "
          f"{'enabled' if schedule['enabled'] else 'disabled'}; {schedule['expression']}.")
    print(f"Manage DNS names in the Web UI. Existing configuration and data were preserved.")


def upgrade() -> None:
    install(upgrading=True)


def uninstall() -> None:
    root = Path(DBMDynIP.INSTALL_DIR)
    service = Path(DBMDynIP.WEB_SERVICE_FILE)
    if service.exists():
        systemctl("disable", "--now", service.name)
        service.unlink()
        systemctl("daemon-reload")
    Path(DBMDynIP.CRON_FILE).unlink(missing_ok=True)
    if (root / "data").is_dir():
        with IpState(root / "data").lock(blocking=True):
            (root / "bin" / "bmdynip").unlink(missing_ok=True)
    else:
        (root / "bin" / "bmdynip").unlink(missing_ok=True)
    (root / "bin" / "bmdynip-web").unlink(missing_ok=True)
    (root / "bmdynip" / "constants" / "DBMDynIP.py").unlink(missing_ok=True)
    print("Removed BMDynIP's Web UI service, cron job, and executables; configuration, data, and credentials were preserved.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "upgrade", "uninstall", "restart"))
    args = parser.parse_args()
    if os.geteuid() != 0:
        print("Run this script as root.", file=sys.stderr)
        return 1
    if sys.version_info < (3, 10):
        print("Python 3.10 or newer is required.", file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        {"install": install, "upgrade": upgrade, "uninstall": uninstall, "restart": restart}[args.action]()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"BMDynIP: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
