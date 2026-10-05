"""Provision protected MariaDB credentials and apply the application schema."""

import fcntl
import hashlib
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.constants.DDbMgr import DDbMgr
from bmdynip.interface.DatabaseEnvironment import DatabaseEnvironment


class DatabaseProvisioning:
    def __init__(self, schema: Path, credentials: Path | None = None,
                 admin_socket: str | None = None):
        self.schema = Path(schema)
        self.credentials = Path(DBMDynIP.DATABASE_ENV) if credentials is None else Path(credentials)
        self.admin_socket = admin_socket

    @staticmethod
    def _require_root():
        if os.geteuid() != 0:
            raise PermissionError("Run database provisioning as root.")

    @staticmethod
    def _run(arguments, sql, message):
        environment = {key: value for key, value in os.environ.items()
                       if key not in {"MYSQL_PWD", "MYSQL_HOST", "MYSQL_TCP_PORT", "MYSQL_UNIX_PORT"}}
        try:
            return subprocess.run([DBMDynIP.MARIADB, *arguments], input=sql, text=True,
                                  capture_output=True, check=True, timeout=30, env=environment)
        except (OSError, subprocess.SubprocessError):
            # Client diagnostics may contain SQL or credentials; keep them out of output.
            raise ValueError(message) from None

    def _create_local(self):
        database = DBMDynIP.DATABASE_NAME
        user = DBMDynIP.DATABASE_USER
        if not all(re.fullmatch(r"[A-Za-z0-9_]+", value) for value in (database, user)):
            raise ValueError("Local database and account names must contain letters, digits, or underscores.")
        if user == "root" or database in {"mysql", "sys", "information_schema", "performance_schema"}:
            raise ValueError("Provisioning requires an application database and account.")
        password = secrets.token_hex(32)
        digest = hashlib.sha1(hashlib.sha1(password.encode()).digest()).hexdigest().upper()
        sql = f"""
CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
CREATE USER IF NOT EXISTS '{user}'@'localhost' IDENTIFIED BY PASSWORD '*{digest}';
ALTER USER '{user}'@'localhost' IDENTIFIED VIA mysql_native_password USING '*{digest}';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES ON `{database}`.* TO '{user}'@'localhost';
SELECT @@socket;
"""
        arguments = ["--no-defaults", "--user=root", "--protocol=socket", "--batch", "--skip-column-names"]
        if self.admin_socket:
            arguments.append("--socket=" + self.admin_socket)
        result = self._run(arguments, sql,
                           "Could not provision the local MariaDB database. Ensure MariaDB is running "
                           "and root can connect with mariadb --no-defaults --user=root --protocol=socket.")
        socket = result.stdout.strip()
        if not socket.startswith("/") or any(character in socket for character in ("\n", "\r", "\0")):
            raise ValueError("MariaDB returned an invalid Unix socket path.")
        return {"DB_HOST": "127.0.0.1", "DB_PORT": str(DDbMgr.PORT), "DB_NAME": database,
                "DB_USER": user, "DB_PASSWORD": password, "DB_SOCKET": socket}

    @staticmethod
    def _option(value):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _apply_schema(self, values, schema):
        with tempfile.NamedTemporaryFile(mode="w", prefix=".database-client-",
                                         dir=self.credentials.parent) as output:
            output.write("[client]\n")
            keys = (("NAME", "USER", "PASSWORD", "SOCKET") if "DB_SOCKET" in values
                    else ("HOST", "PORT", "NAME", "USER", "PASSWORD"))
            for key in keys:
                if "DB_" + key in values:
                    name = "database" if key == "NAME" else key.lower()
                    output.write(f"{name}={self._option(values['DB_' + key])}\n")
            output.flush()
            arguments = ["--defaults-file=" + output.name,
                         "--protocol=" + ("socket" if "DB_SOCKET" in values else "tcp"),
                         f"--connect-timeout={DDbMgr.CONNECT_TIMEOUT}", "--batch"]
            self._run(arguments, "SET SESSION lock_wait_timeout=15;\n" + schema,
                      "Could not apply the BMDynIP database schema. Check database availability "
                      "and the account's CREATE, ALTER, INDEX, and REFERENCES privileges.")

    def _publish(self, values):
        descriptor, temporary = tempfile.mkstemp(prefix=".database-", dir=self.credentials.parent)
        try:
            with os.fdopen(descriptor, "w") as output:
                os.fchmod(output.fileno(), 0o600)
                for key, value in values.items():
                    output.write(f"{key}={value}\n")
                output.flush()
                os.fsync(output.fileno())
            # Never overwrite an existing credentials file.
            os.link(temporary, self.credentials)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def provision(self) -> None:
        self._require_root()
        schema = self.schema.read_text()
        path = self.credentials
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Database credential file and directory must not be symlinks.")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            fcntl.flock(directory, fcntl.LOCK_EX)
            if os.fstat(directory).st_uid != os.geteuid():
                raise ValueError("Database credential directory must belong to the current user.")
            os.fchmod(directory, 0o700)
            existing = path.exists()
            values = DatabaseEnvironment.read(path) if existing else self._create_local()
            self._apply_schema(values, schema)
            if not existing:
                self._publish(values)
        finally:
            os.close(directory)
