"""Verify upgrade delegation without changing the installed application."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="bmdynip-upgrade-")
        self.addCleanup(directory.cleanup)
        self.checkout = Path(directory.name) / "checkout with spaces"
        scripts = self.checkout / "scripts"
        scripts.mkdir(parents=True)
        self.script = scripts / "upgrade.sh"
        self.script.write_bytes((ROOT / "scripts/upgrade.sh").read_bytes())
        self.script.chmod(0o755)
        self.marker = self.checkout / "installed"
        self.installer = scripts / "install.sh"
        self.installer.write_text('#!/usr/bin/env bash\npwd > installed\nexit 0\n')
        self.installer.chmod(0o755)

    def run_upgrade(self, *arguments):
        return subprocess.run([str(self.script), *arguments], cwd=self.checkout.parent,
                              text=True, capture_output=True, timeout=10)

    def test_upgrade_runs_installer_from_checkout(self):
        result = self.run_upgrade()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.marker.read_text().strip(), str(self.checkout))

    def test_installer_failure_is_reported(self):
        self.installer.write_text('#!/usr/bin/env bash\nprintf "Installation failed\\n" >&2\nexit 7\n')
        result = self.run_upgrade()
        self.assertEqual(result.returncode, 7)
        self.assertIn("Installation failed", result.stderr)

    def test_help_does_not_install(self):
        result = self.run_upgrade("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage: sudo scripts/upgrade.sh", result.stdout)
        self.assertFalse(self.marker.exists())

    def test_invalid_arguments_do_not_install(self):
        for arguments in (("--unknown",), ("--help", "extra")):
            with self.subTest(arguments=arguments):
                result = self.run_upgrade(*arguments)
                self.assertEqual(result.returncode, 1)
                self.assertIn("Usage:", result.stderr)
                self.assertFalse(self.marker.exists())
