"""Read and update the runner's root cron entry."""

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import shlex
from tempfile import NamedTemporaryFile

from crontab import CronSlices, CronTab

from bmdynip.constants.DBMDynIP import DBMDynIP


class RunnerSchedule:
    COMMENT = "bmdynip-runner"

    def __init__(self, cron_file: Path | None = None, directory: Path | None = None):
        self.cron_file = Path(DBMDynIP.CRON_FILE) if cron_file is None else Path(cron_file)
        self.directory = (Path(DBMDynIP.INSTALL_DIR) / "data"
                          if directory is None else Path(directory))

    @staticmethod
    def validate(enabled: bool, expression: str) -> dict:
        if (type(enabled) is not bool or not isinstance(expression, str)
                or len(expression) > 255 or "\n" in expression or "\r" in expression):
            raise ValueError("Provide an enabled flag and a five-field cron expression.")
        expression = " ".join(expression.split())
        if len(expression.split()) != 5 or not CronSlices.is_valid(expression):
            raise ValueError("Use five cron fields: minute hour day-of-month month day-of-week.")
        return {"enabled": enabled, "expression": expression}

    @property
    def command(self) -> str:
        executable = str(Path(DBMDynIP.INSTALL_DIR) / "bin/bmdynip")
        return shlex.quote(executable).replace("%", r"\%") + " 2>&1 | /usr/bin/logger -t bmdynip"

    @contextmanager
    def lock(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with (self.directory / "runner-schedule.lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def _tab(self):
        if self.cron_file.is_symlink():
            raise ValueError("Runner cron file must not be a symlink.")
        try:
            text = self.cron_file.read_text()
        except FileNotFoundError:
            text = "SHELL=/bin/sh\nHOME=/root\nPATH=/usr/bin:/bin\n"
        return CronTab(tab=text, user=False)

    def _jobs(self, tab):
        # Recognize the entry installed before it had a managed comment.
        return [job for job in tab if job.comment == self.COMMENT or job.command == self.command]

    def _values(self, tab):
        jobs = self._jobs(tab)
        if not jobs:
            return {"enabled": True, "expression": DBMDynIP.CRON_SCHEDULE}
        if len(jobs) != 1 or jobs[0].user != "root":
            raise ValueError("Expected one root BMDynIP runner cron entry.")
        return self.validate(jobs[0].is_enabled(), str(jobs[0].slices))

    def read(self) -> dict:
        return self._values(self._tab())

    @staticmethod
    def _require_root():
        if os.geteuid() != 0:
            raise PermissionError("Run schedule changes as root.")

    def _write(self, tab, values):
        for job in self._jobs(tab):
            tab.remove(job)
        job = tab.new(command=self.command, comment=self.COMMENT, user="root")
        job.setall(values["expression"])
        job.enable(values["enabled"])
        with NamedTemporaryFile(mode="w", dir=self.cron_file.parent,
                                prefix=".bmdynip-cron-", delete=False) as stream:
            candidate = Path(stream.name)
            try:
                stream.write(str(tab))
                stream.flush()
                os.fsync(stream.fileno())
                candidate.chmod(0o644)
                candidate.replace(self.cron_file)
            finally:
                candidate.unlink(missing_ok=True)

    def update(self, enabled: bool, expression: str) -> dict:
        values = self.validate(enabled, expression)
        self._require_root()
        with self.lock():
            self._write(self._tab(), values)
        return values

    def install(self) -> dict:
        """Create the default entry or retain the installed schedule."""
        self._require_root()
        with self.lock():
            tab = self._tab()
            values = self._values(tab)
            self._write(tab, values)
        return values
