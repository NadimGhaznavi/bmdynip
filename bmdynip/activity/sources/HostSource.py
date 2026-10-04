"""Collect local host identity and OS release as observations."""

from pathlib import Path
import shlex
import socket


class HostSource:
    def collect(self) -> dict:
        hostname = socket.gethostname()
        if not hostname or len(hostname) > 255 or any(c.isspace() or ord(c) < 32 for c in hostname):
            raise ValueError('Invalid runtime hostname.')
        path = Path('/etc/os-release')
        if not path.exists():
            path = Path('/usr/lib/os-release')
        system = {}
        if path.exists():
            for line in path.read_text().splitlines():
                key, separator, value = line.partition('=')
                if separator and key in ('ID', 'VERSION_ID', 'PRETTY_NAME'):
                    words = shlex.split(value, comments=True)
                    if len(words) != 1 or len(words[0]) > 255:
                        raise ValueError('Invalid OS release observation.')
                    system[key] = words[0]
        return {'hostname': hostname, 'system': system}
