"""Cron entry point for BMDynIP."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

from bmdynip.activity.UpdatePublicIp import UpdatePublicIp
from bmdynip.activity.DiscoveryCoordinator import DiscoveryCoordinator
from bmdynip.app.database import open_database
from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.Credentials import Credentials
from bmdynip.interface.GoDaddyCli import GoDaddyCli
from bmdynip.interface.IpState import IpState
from bmdynip.interface.PublicIpService import PublicIpService
from bmdynip.interface.DnsRecordDb import DnsRecordDb
from bmdynip.interface.PublicIpDb import PublicIpDb
from pymysql import MySQLError


def main() -> int:
    parser = argparse.ArgumentParser(description="Update configured GoDaddy A records to this host's public IPv4.")
    parser.add_argument("--version", action="version", version=DBMDynIP.VERSION)
    parser.parse_args()
    if os.geteuid() != 0:
        print("BMDynIP must run as root.", file=sys.stderr)
        return 1
    os.umask(0o077)
    root = Path(DBMDynIP.INSTALL_DIR)
    state = IpState(root / "data")
    try:
        with state.lock() as acquired:
            if not acquired:
                return 0
            db = open_database()
            try:
                connection = DiscoveryCoordinator().run(db)
                records = DnsRecordDb(db).list_records()
                audit = PublicIpDb(db, connection)
                public_ip = PublicIpService()
                if not records:
                    audit.observe(public_ip.current_address())
                    return 0
                token = Credentials.load(Path(DBMDynIP.CREDENTIALS_FILE))
                UpdatePublicIp(public_ip, GoDaddyCli(token), state, audit).run(records)
            finally:
                db.close()
    except MySQLError:
        print("BMDynIP: Database operation failed; check database availability and credentials.", file=sys.stderr)
        return 1
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"BMDynIP: {error}", file=sys.stderr)
        return 1
    return 0
