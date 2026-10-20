"""Resolve listener defaults and production overrides once at process startup."""

from ipaddress import IPv4Address
from pathlib import Path

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.Configuration import Configuration


class Network:
    def __init__(self, path: Path | None = None):
        path = Configuration.path() if path is None else path
        self.bindings = {use: (interface, port)
                         for use, interface, port in DBMDynIP.CMDB_NETWORK}
        try:
            data = Configuration.read(path)
        except FileNotFoundError:
            data = {}
        overrides = data.get("network", {})
        if not isinstance(overrides, dict) or overrides.keys() - self.bindings.keys():
            raise ValueError(f"Invalid network uses in {path}.")
        for use, fields in overrides.items():
            if not isinstance(fields, dict) or fields.keys() - {"interface", "port"}:
                raise ValueError(f"Invalid network.{use} fields in {path}.")
            interface, port = self.bindings[use]
            self.bindings[use] = (fields.get("interface", interface), fields.get("port", port))
        for use, (interface, port) in self.bindings.items():
            self.validate(interface, port, f"{path}: network.{use}")

    @staticmethod
    def validate(interface, port, setting: str) -> None:
        try:
            if not isinstance(interface, str):
                raise ValueError
            IPv4Address(interface)
        except ValueError:
            raise ValueError(f"{setting}.interface must be an IPv4 address.") from None
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError(f"{setting}.port must be an integer between 1 and 65535.")

    def binding(self, use: str) -> tuple[str, int]:
        return self.bindings[use]

    def destination(self, use: str) -> tuple[str, int]:
        interface, port = self.binding(use)
        return ("127.0.0.1" if interface == "0.0.0.0" else interface), port

