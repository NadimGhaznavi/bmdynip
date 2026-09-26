"""Store the address and DNS names from the last completed update."""

from contextlib import contextmanager
import fcntl
from ipaddress import IPv4Address
import json
from pathlib import Path

from mydynip.entity.DnsRecord import DnsRecord


class IpState:
    def __init__(self, directory: Path):
        self.directory = directory
        self.path = directory / "state.json"

    @contextmanager
    def lock(self, *, blocking: bool = False):
        with (self.directory / "run.lock").open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    @staticmethod
    def _snapshot(address: IPv4Address, records: tuple[DnsRecord, ...]) -> dict:
        return {"ip": str(address), "records": sorted([r.domain, r.name] for r in records)}

    def is_current(self, address: IPv4Address, records: tuple[DnsRecord, ...]) -> bool:
        try:
            content = self.path.read_text()
        except FileNotFoundError:
            return False
        data = json.loads(content)
        if not isinstance(data, dict) or set(data) != {"ip", "records"}:
            raise ValueError(f"Invalid saved state in {self.path}.")
        if not isinstance(data["ip"], str):
            raise ValueError(f"Invalid saved IP in {self.path}.")
        IPv4Address(data["ip"])
        if not isinstance(data["records"], list) or any(
            not isinstance(pair, list) or len(pair) != 2 or
            any(not isinstance(value, str) for value in pair) for pair in data["records"]
        ):
            raise ValueError(f"Invalid saved record names in {self.path}.")
        return data == self._snapshot(address, records)

    def save(self, address: IPv4Address, records: tuple[DnsRecord, ...]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._snapshot(address, records), indent=2) + "\n")
        temporary.replace(self.path)
