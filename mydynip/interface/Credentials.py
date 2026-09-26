"""Load the root-owned GoDaddy PAT without evaluating shell code."""

import os
from pathlib import Path
import re
import stat


class Credentials:
    @staticmethod
    def load(path: Path) -> str:
        with path.open() as stream:
            info = os.fstat(stream.fileno())
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError(f"{path} must belong to the current user with mode 0600.")
            content = stream.read().strip()
        match = re.fullmatch(r"GDDY_PAT=(gd_pat_[A-Za-z0-9_-]+)", content)
        if not match:
            raise ValueError(f"{path} must contain a single GDDY_PAT assignment.")
        return match[1]
