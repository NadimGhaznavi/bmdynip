"""Read protected database settings as data, never as shell code."""

from pathlib import Path

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.Credentials import Credentials


class DatabaseEnvironment:
    @staticmethod
    def read(path: Path | None = None) -> dict[str, str]:
        content = Credentials._read(path or Path(DBMDynIP.DATABASE_ENV))
        values = {}
        for line in content.splitlines():
            key, separator, value = line.partition("=")
            if not separator or key in values:
                raise ValueError("Invalid database environment file.")
            values[key] = value
        required = {"DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"}
        if values.keys() not in (required, required | {"DB_SOCKET"}) or not all(values.values()):
            raise ValueError("Unexpected database environment fields.")
        if not 1 <= int(values["DB_PORT"]) <= 65535:
            raise ValueError("Invalid database port.")
        return values
