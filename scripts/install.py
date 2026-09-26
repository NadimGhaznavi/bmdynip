"""Install or remove MyDynIP's executable and cron job."""

import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipapp

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

from mydynip.constants.DMyDynIP import DMyDynIP
from mydynip.interface.Configuration import Configuration
from mydynip.interface.Credentials import Credentials
from mydynip.interface.IpState import IpState


def install() -> None:
    for executable in ("/usr/bin/python3", "/usr/bin/curl", "/usr/bin/logger", DMyDynIP.GODADDY_CLI):
        if not os.access(executable, os.X_OK):
            raise ValueError(f"Required executable is missing: {executable}")
    Credentials.load(Path(DMyDynIP.CREDENTIALS_FILE))
    root = Path(DMyDynIP.INSTALL_DIR)
    config = root / "conf" / "mydynip.json"
    Configuration.load(config if config.exists() else REPOSITORY / "conf" / "mydynip.json")
    for name in ("bin", "conf", "data"):
        (root / name).mkdir(parents=True, exist_ok=True)
        (root / name).chmod(0o700 if name != "bin" else 0o755)
    with IpState(root / "data").lock(blocking=True):
        if not config.exists():
            shutil.copyfile(REPOSITORY / "conf" / "mydynip.json", config)
        config.chmod(0o600)
        with tempfile.TemporaryDirectory(prefix="mydynip-install-") as staging:
            staged = Path(staging)
            shutil.copytree(REPOSITORY / "mydynip", staged / "mydynip",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            (staged / "__main__.py").write_text(
                "from mydynip.app.main import main\nraise SystemExit(main())\n")
            temporary = root / "bin" / ".mydynip.new"
            try:
                zipapp.create_archive(staged, target=temporary,
                                      interpreter="/usr/bin/python3")
                temporary.chmod(0o755)
                temporary.replace(root / "bin" / "mydynip")
            finally:
                temporary.unlink(missing_ok=True)
        cron = Path(DMyDynIP.CRON_FILE)
        text = ("# Managed by MyDynIP's installer.\n"
                "SHELL=/bin/sh\nHOME=/root\nPATH=/usr/bin:/bin\n"
                f"{DMyDynIP.CRON_SCHEDULE} root {root}/bin/mydynip 2>&1 | /usr/bin/logger -t mydynip\n")
        temporary_cron = cron.with_name(".mydynip.new")
        try:
            temporary_cron.write_text(text)
            temporary_cron.chmod(0o644)
            temporary_cron.replace(cron)
        finally:
            temporary_cron.unlink(missing_ok=True)
    print(f"Installed MyDynIP {DMyDynIP.VERSION}; cron runs every five minutes.")
    print(f"Configure DNS names in {config}. Existing configuration and data were preserved.")


def uninstall() -> None:
    root = Path(DMyDynIP.INSTALL_DIR)
    Path(DMyDynIP.CRON_FILE).unlink(missing_ok=True)
    if (root / "data").is_dir():
        with IpState(root / "data").lock(blocking=True):
            (root / "bin" / "mydynip").unlink(missing_ok=True)
    else:
        (root / "bin" / "mydynip").unlink(missing_ok=True)
    print("Removed MyDynIP's cron job and executable; configuration, data, and credentials were preserved.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    args = parser.parse_args()
    if os.geteuid() != 0:
        print("Run this script as root.", file=sys.stderr)
        return 1
    if sys.version_info < (3, 10):
        print("Python 3.10 or newer is required.", file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        (install if args.action == "install" else uninstall)()
    except (OSError, ValueError) as error:
        print(f"MyDynIP: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
