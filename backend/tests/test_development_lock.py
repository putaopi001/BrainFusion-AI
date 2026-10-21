"""Exercise the actual cross-process Windows lock with isolated runtime fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


PWSH = shutil.which('pwsh')
WRAPPER = Path(__file__).resolve().parents[1] / 'tools' / 'run_development_step.ps1'


@unittest.skipUnless(PWSH and os.name == 'nt', 'Windows PowerShell 7 required')
class DevelopmentLockTests(unittest.TestCase):
    def setUp(self):
        root = Path('E:/BrainFusion-Runtime/automation-tests')
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def command(self, name, source):
        step = self.root / (name + '.ps1')
        step.write_text(source, encoding='utf-8')
        return [PWSH, '-NoProfile', '-File', str(WRAPPER), '-RunId', name,
                '-ScriptPath', str(step), '-AutomationRoot', str(self.root)]

    def run_step(self, name, source):
        return subprocess.run(self.command(name, source), capture_output=True,
                              text=True, timeout=20)

    def metadata(self):
        return json.loads((self.root / 'development-lock.json').read_text(encoding='utf-8-sig'))

    def test_success_releases_and_allows_next_step(self):
        first = self.run_step('success', "'actual work'")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(self.metadata()['state'], 'released')
        second = self.run_step('next', "'next work'")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.metadata()['run_id'], 'next')

    def test_exception_releases_lock(self):
        failed = self.run_step('failure', "throw 'expected failure'")
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertEqual(self.metadata()['exit_code'], 1)
        self.assertEqual(self.run_step('recovery', "'work'").returncode, 0)

    def test_native_failure_is_not_reported_as_success(self):
        failed = self.run_step('native', '& (Join-Path $PSHOME pwsh.exe) -NoProfile -Command "exit 7"')
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertEqual(self.metadata()['state'], 'released')
        self.assertEqual(self.metadata()['exit_code'], 1)

    def test_competitor_cannot_write_or_replace_owner(self):
        # The fixture is bounded even if the test runner is interrupted.
        ready = self.root / 'ready'
        release = self.root / 'finish'
        source = """
$root = Split-Path -Parent $PSCommandPath
'ready' | Set-Content -LiteralPath (Join-Path $root 'ready')
$deadline = [DateTime]::UtcNow.AddSeconds(12)
while (-not (Test-Path -LiteralPath (Join-Path $root 'finish'))) {
    if ([DateTime]::UtcNow -gt $deadline) { throw 'fixture timeout' }
    Start-Sleep -Milliseconds 100
}
"""
        owner = subprocess.Popen(self.command('owner', source), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 8
            while not ready.exists() and time.monotonic() < deadline:
                if owner.poll() is not None:
                    self.fail(str(owner.communicate()))
                time.sleep(0.05)
            self.assertTrue(ready.exists())
            contender = self.run_step('contender', "'forbidden' | Set-Content -LiteralPath (Join-Path (Split-Path -Parent $PSCommandPath) 'forbidden')")
            self.assertEqual(contender.returncode, 73, contender.stderr)
            self.assertFalse((self.root / 'forbidden').exists())
            self.assertEqual(self.metadata()['run_id'], 'owner')
            self.assertEqual(self.metadata()['state'], 'held')
        finally:
            release.touch()
            out, err = owner.communicate(timeout=18)
        self.assertEqual(owner.returncode, 0, err)
        self.assertEqual(self.metadata()['state'], 'released')


if __name__ == '__main__':
    unittest.main()
