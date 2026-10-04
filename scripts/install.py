"""Install or remove BMDynIP's executable and cron job."""

import argparse
import getpass
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipapp

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.Configuration import Configuration
from bmdynip.interface.Credentials import Credentials
from bmdynip.interface.IpState import IpState


def read_token() -> str:
    token = os.environ.get("GDDY_PAT")
    if token:
        return token
    source = Path(DBMDynIP.ROOT_CREDENTIALS_FILE)
    if source.exists() or source.is_symlink():
        return Credentials.import_token(source)
    if not sys.stdin.isatty():
        raise ValueError("Credentials are missing. Run installation in a terminal to enter a "
                         "GoDaddy PAT, or supply GDDY_PAT in the environment.")
    print("Generate a GoDaddy PAT named bmdynip with domains.dns:update permission at")
    print("https://developer.godaddy.com/personal-access-token")
    try:
        return getpass.getpass("GoDaddy PAT (hidden): ")
    except EOFError:
        raise ValueError("No GoDaddy PAT was supplied.") from None


def install() -> None:
    for executable in ("/usr/bin/python3", "/usr/bin/curl", "/usr/bin/logger", DBMDynIP.GODADDY_CLI):
        if not os.access(executable, os.X_OK):
            raise ValueError(f"Required executable is missing: {executable}")
    root = Path(DBMDynIP.INSTALL_DIR)
    config = root / "conf" / "bmdynip.json"
    Configuration.load(config if config.exists() else REPOSITORY / "conf" / "bmdynip.json")
    Credentials.provision(Path(DBMDynIP.CREDENTIALS_FILE), read_token)
    for name in ("bin", "conf", "data"):
        (root / name).mkdir(parents=True, exist_ok=True)
        (root / name).chmod(0o700 if name != "bin" else 0o755)
    with IpState(root / "data").lock(blocking=True):
        if not config.exists():
            shutil.copyfile(REPOSITORY / "conf" / "bmdynip.json", config)
        config.chmod(0o600)
        with tempfile.TemporaryDirectory(prefix="bmdynip-install-") as staging:
            staged = Path(staging)
            shutil.copytree(REPOSITORY / "bmdynip", staged / "bmdynip",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
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
        cron = Path(DBMDynIP.CRON_FILE)
        text = ("# Managed by BMDynIP's installer.\n"
                "SHELL=/bin/sh\nHOME=/root\nPATH=/usr/bin:/bin\n"
                f"{DBMDynIP.CRON_SCHEDULE} root {root}/bin/bmdynip 2>&1 | /usr/bin/logger -t bmdynip\n")
        temporary_cron = cron.with_name(".bmdynip.new")
        try:
            temporary_cron.write_text(text)
            temporary_cron.chmod(0o644)
            temporary_cron.replace(cron)
        finally:
            temporary_cron.unlink(missing_ok=True)
    print(f"Installed BMDynIP {DBMDynIP.VERSION}; cron runs every five minutes.")
    print(f"Configure DNS names in {config}. Existing configuration and data were preserved.")


def uninstall() -> None:
    root = Path(DBMDynIP.INSTALL_DIR)
    Path(DBMDynIP.CRON_FILE).unlink(missing_ok=True)
    if (root / "data").is_dir():
        with IpState(root / "data").lock(blocking=True):
            (root / "bin" / "bmdynip").unlink(missing_ok=True)
    else:
        (root / "bin" / "bmdynip").unlink(missing_ok=True)
    print("Removed BMDynIP's cron job and executable; configuration, data, and credentials were preserved.")


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
        print(f"BMDynIP: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
