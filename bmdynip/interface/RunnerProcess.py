"""Launch the installed runner and own its background process lifecycle."""

from concurrent.futures import ThreadPoolExecutor
import logging
import os
from pathlib import Path
import signal
import subprocess

from bmdynip.constants.DBMDynIP import DBMDynIP


class RunnerProcess:
    def __init__(self, messages=None):
        self.messages = messages
        self.waiters = ThreadPoolExecutor(max_workers=1, thread_name_prefix='bmdynip-runner')

    def start(self) -> None:
        executable = Path(DBMDynIP.INSTALL_DIR) / 'bin/bmdynip'
        # Inherit service output so runner diagnostics appear in the service log.
        process = subprocess.Popen([str(executable)], stdin=subprocess.DEVNULL, start_new_session=True)
        if self.messages:
            self.messages.append('Immediate runner process started.')
        self.waiters.submit(self._finish, process, self.messages)

    @staticmethod
    def _finish(process, messages=None) -> None:
        try:
            status = process.wait(timeout=DBMDynIP.WEB_RUNNER_TIMEOUT)
            if status:
                logging.error('Immediate runner exited with status %s', status)
                if messages:
                    messages.append(f'Immediate runner exited with status {status}. Check the service log.')
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
            logging.error('Immediate runner timed out; check DNS change history and service logs')
            if messages:
                messages.append('Immediate runner timed out. Check DNS change history and service logs; '
                                'the next run will retry.')

    def close(self) -> None:
        self.waiters.shutdown(wait=True)
