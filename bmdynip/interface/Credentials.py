"""Load the root-owned GoDaddy PAT without evaluating shell code."""

import fcntl
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Callable


class Credentials:
    @staticmethod
    def provision(path: Path, token_source: Callable[[], str]) -> str:
        """Retain existing credentials or securely publish a supplied GoDaddy PAT."""
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Credential file and directory must not be symlinks.")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            fcntl.flock(directory, fcntl.LOCK_EX)
            if path.exists():
                return Credentials.load(path)
            info = os.fstat(directory)
            if info.st_uid != os.geteuid():
                raise ValueError(f"{path.parent} must belong to the current user.")
            os.fchmod(directory, 0o700)
            token = token_source()
            if not re.fullmatch(r"gd_pat_\S+", token):
                raise ValueError("Supply a GoDaddy-issued PAT beginning with gd_pat_.")
            descriptor, temporary = tempfile.mkstemp(prefix=".auto-", dir=path.parent)
            try:
                with os.fdopen(descriptor, "w") as output:
                    os.fchmod(output.fileno(), 0o600)
                    output.write(f"GDDY_PAT={token}\n")
                    output.flush()
                    os.fsync(output.fileno())
                os.link(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)
            return token
        finally:
            os.close(directory)

    @staticmethod
    def import_token(path: Path) -> str:
        """Read root's PAT file, accepting an assignment or a bare PAT."""
        content = Credentials._read(path)
        match = re.fullmatch(r"(?:GDDY_PAT=)?(gd_pat_\S+)", content)
        if not match:
            raise ValueError(f"{path} must contain a GoDaddy PAT or a single GDDY_PAT assignment.")
        return match[1]

    @staticmethod
    def _read(path: Path) -> str:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor) as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o600):
                raise ValueError(f"{path} must belong to the current user with mode 0600.")
            return stream.read().strip()

    @staticmethod
    def load(path: Path) -> str:
        content = Credentials._read(path)
        match = re.fullmatch(r"GDDY_PAT=(gd_pat_\S+)", content)
        if not match:
            raise ValueError(f"{path} must contain a single GDDY_PAT assignment.")
        return match[1]
