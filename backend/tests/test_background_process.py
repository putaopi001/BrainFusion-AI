"""Real owned Windows job teardown, argument/environment fidelity, and no service leaks."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

pytestmark=pytest.mark.skipif(os.name!='nt' or not shutil.which('pwsh'),reason='Windows PowerShell 7 required')
HELPER=Path(__file__).resolve().parents[1]/'tools/background_process.ps1'


class BasicLimits(ctypes.Structure):
    _fields_=[('user',ctypes.c_int64),('job',ctypes.c_int64),('flags',wintypes.DWORD),
              ('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active',wintypes.DWORD),
              ('affinity',ctypes.c_size_t),('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]


class Limits(ctypes.Structure):
    _fields_=[('basic',BasicLimits),('io',ctypes.c_uint64*6),('process_mem',ctypes.c_size_t),
              ('job_mem',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]


def wait_for(predicate,seconds=15):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.05)
    raise AssertionError('Owned lifecycle fixture timed out')


def test_service_refuses_unsafe_launch_in_non_breakaway_owner_job(tmp_path):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    job=kernel.CreateJobObjectW(None,None);assert job
    # This owner job deliberately withholds BREAKAWAY_OK. The launcher must
    # refuse a service that would die with the owner and reap its child.
    limits=Limits();limits.basic.flags=0x2000
    assert kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits))
    child=tmp_path/'child.py'
    child.write_text('''import json,os,sys,time
from pathlib import Path
root=Path(__file__).parent
(root/'child-data.json').write_text(json.dumps({'pid':os.getpid(),'args':sys.argv[1:],'environment':os.environ.get('BF_BACKGROUND_TEST')}),encoding='utf-8')
deadline=time.monotonic()+30
while not (root/'finish').exists() and time.monotonic()<deadline:time.sleep(.05)
(root/'child-finished').write_text('finished')
''',encoding='utf-8')
    driver=tmp_path/'driver.ps1'
    # File arguments are passed as JSON data to Popen, never evaluated as a shell.
    driver.write_text('''param($Root,$Helper,$Python)
$ErrorActionPreference='Stop'
$deadline=[datetime]::UtcNow.AddSeconds(20)
while(-not(Test-Path -LiteralPath (Join-Path $Root 'begin'))){if([datetime]::UtcNow -gt $deadline){throw 'fixture start timeout'};Start-Sleep -Milliseconds 50}
. $Helper
$env:BF_BACKGROUND_TEST='environment passed in memory'
$normal=Start-Process -FilePath $Python -ArgumentList @('-B','-c','"import time;time.sleep(30)"') -WindowStyle Hidden -PassThru
$background=$null
try {
  $background=Start-BrainFusionBackgroundProcess -FilePath $Python -BootstrapPython $Python -ArgumentList @('-B',(Join-Path $Root 'child.py'),'space 中文','literal "quoted" & $()') -WorkingDirectory $Root -StandardOutput (Join-Path $Root 'out.log') -StandardError (Join-Path $Root 'err.log')
} catch {
  @{error=$_.Exception.Message}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $Root 'refused.json') -Encoding utf8
  exit 0
}
@{normal_pid=$normal.Id;background_pid=$background.Id}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $Root 'ready.json') -Encoding utf8
Start-Sleep -Seconds 30
''',encoding='utf-8')
    normal_handle=child_handle=None
    with (tmp_path/'driver-error.log').open('wb') as errors:
        parent=subprocess.Popen([shutil.which('pwsh'),'-NoProfile','-File',str(driver),str(tmp_path),str(HELPER),sys.executable],stdout=subprocess.DEVNULL,stderr=errors)
        try:
            assert kernel.AssignProcessToJobObject(job,int(parent._handle)),ctypes.get_last_error()
            (tmp_path/'begin').touch()
            wait_for(lambda:(tmp_path/'refused.json').exists() or parent.poll() is not None)
            assert (tmp_path/'refused.json').exists(),(tmp_path/'driver-error.log').read_text(encoding='utf-8')
            error=json.loads((tmp_path/'refused.json').read_text(encoding='utf-8-sig'))['error']
            assert 'remains subject to job cleanup' in error
            assert 'pid=' in error and 'child_terminated=True' in error
            assert not (tmp_path/'ready.json').exists()
            assert not (tmp_path/'child-data.json').exists()
            kernel.CloseHandle(job);job=None
            parent.wait(timeout=8)
        finally:
            (tmp_path/'finish').touch()
            if job:kernel.CloseHandle(job)
            parent.wait(timeout=8)


def test_missing_executable_is_rejected_before_start(tmp_path):
    script=tmp_path/'missing.ps1'
    script.write_text("param($Helper,$Root)\n. $Helper\nStart-BrainFusionBackgroundProcess -FilePath (Join-Path $Root 'absent.exe') -WorkingDirectory $Root -StandardOutput (Join-Path $Root 'out.log') -StandardError (Join-Path $Root 'err.log')\n",encoding='utf-8')
    result=subprocess.run([shutil.which('pwsh'),'-NoProfile','-File',str(script),str(HELPER),str(tmp_path)],capture_output=True,timeout=15)
    assert result.returncode!=0
    assert not (tmp_path/'out.log').exists()
