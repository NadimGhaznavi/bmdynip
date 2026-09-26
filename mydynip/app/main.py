"""Cron entry point for MyDynIP."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

from mydynip.activity.UpdatePublicIp import UpdatePublicIp
from mydynip.constants.DMyDynIP import DMyDynIP
from mydynip.interface.Configuration import Configuration
from mydynip.interface.Credentials import Credentials
from mydynip.interface.GoDaddyCli import GoDaddyCli
from mydynip.interface.IpState import IpState
from mydynip.interface.PublicIpService import PublicIpService


def main() -> int:
    parser = argparse.ArgumentParser(description="Update configured GoDaddy A records to this host's public IPv4.")
    parser.add_argument("--version", action="version", version=DMyDynIP.VERSION)
    parser.parse_args()
    if os.geteuid() != 0:
        print("MyDynIP must run as root.", file=sys.stderr)
        return 1
    os.umask(0o077)
    root = Path(DMyDynIP.INSTALL_DIR)
    state = IpState(root / "data")
    try:
        with state.lock() as acquired:
            if not acquired:
                return 0
            records = Configuration.load(root / "conf" / "mydynip.json")
            if not records:
                return 0
            token = Credentials.load(Path(DMyDynIP.CREDENTIALS_FILE))
            UpdatePublicIp(PublicIpService(), GoDaddyCli(token), state).run(records)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"MyDynIP: {error}", file=sys.stderr)
        return 1
    return 0
