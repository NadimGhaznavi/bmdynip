"""Verify immediate runner launch and process cleanup without DNS operations."""

import subprocess
import signal
import unittest
from unittest.mock import Mock, patch

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.interface.RunnerProcess import RunnerProcess


class RunnerProcessTests(unittest.TestCase):
    def test_launch_uses_installed_executable_without_waiting_in_request(self):
        with patch('bmdynip.interface.RunnerProcess.ThreadPoolExecutor') as executor, \
                patch('bmdynip.interface.RunnerProcess.subprocess.Popen') as launch, \
                patch.object(DBMDynIP, 'INSTALL_DIR', '/installation with spaces'):
            runner = RunnerProcess()
            runner.start()
            launch.assert_called_once_with(['/installation with spaces/bin/bmdynip'],
                                           stdin=subprocess.DEVNULL, start_new_session=True)
            launch.return_value.wait.assert_not_called()
            executor.return_value.submit.assert_called_once_with(runner._finish, launch.return_value)
            runner.close()
            executor.return_value.shutdown.assert_called_once_with(wait=True)

    def test_failed_launch_does_not_queue_waiter(self):
        with patch('bmdynip.interface.RunnerProcess.ThreadPoolExecutor') as executor, \
                patch('bmdynip.interface.RunnerProcess.subprocess.Popen', side_effect=FileNotFoundError):
            runner = RunnerProcess()
            with self.assertRaises(FileNotFoundError):
                runner.start()
            executor.return_value.submit.assert_not_called()
            runner.close()

    def test_completion_is_reaped_and_failure_is_logged(self):
        process = Mock()
        process.wait.return_value = 1
        with self.assertLogs(level='ERROR'):
            RunnerProcess._finish(process)
        process.wait.assert_called_once_with(timeout=DBMDynIP.WEB_RUNNER_TIMEOUT)

    def test_timeout_kills_and_reaps_process(self):
        process = Mock()
        process.pid = 12345
        process.wait.side_effect = [subprocess.TimeoutExpired('runner', 600), -9]
        with patch('bmdynip.interface.RunnerProcess.os.killpg') as kill, self.assertLogs(level='ERROR'):
            RunnerProcess._finish(process)
        kill.assert_called_once_with(12345, signal.SIGKILL)
        self.assertEqual(process.wait.call_count, 2)
