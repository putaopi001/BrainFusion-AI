"""Local Windows service bootstrap. No scheduling, elevation or automatic restart."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import struct
import subprocess


def job_membership(handle):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    in_job = wintypes.BOOL()
    if not kernel.IsProcessInJob(handle, None, ctypes.byref(in_job)):
        raise ctypes.WinError(ctypes.get_last_error())
    limits = ctypes.create_string_buffer(64)
    flags = None
    if kernel.QueryInformationJobObject(None, 2, limits, len(limits), None):
        flags = struct.unpack_from('<I', limits.raw, 16)[0]
    return bool(in_job.value), flags


def process_details(process):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    created, ended, system, user = (wintypes.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(int(process._handle), ctypes.byref(created), ctypes.byref(ended), ctypes.byref(system), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())
    in_job, flags = job_membership(int(process._handle))
    if in_job:
        rendered_flags = 'unknown' if flags is None else f'0x{flags:08x}'
        raise RuntimeError(
            'Background service process remains subject to job cleanup '
            f'(launcher process job limits={rendered_flags})'
        )
    return dict(pid=process.pid,
                started_filetime=(created.dwHighDateTime << 32) | created.dwLowDateTime,
                target_in_job=in_job, bootstrap_job_limits=flags,
                launch_mode='local_subprocess_detached', independent_of_caller_job=not in_job)


def start(request):
    command = request['command']
    if not command or not all(isinstance(value, str) and '\x00' not in value for value in command):
        raise ValueError('Invalid background command')
    executable = Path(command[0])
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError('Background executable missing')
    paths = [Path(request[key]) for key in ('cwd', 'stdout', 'stderr')]
    if any(not path.is_absolute() or path.drive.upper() != 'E:' for path in paths):
        raise ValueError('Background working directory and logs must stay on E:')
    if paths[1] == paths[2] or not paths[0].is_dir():
        raise ValueError('Invalid background log/working directory')
    process = None
    try:
        with paths[1].open('wb') as stdout, paths[2].open('wb') as stderr:
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            in_launcher_job, _ = job_membership(kernel.GetCurrentProcess())
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            if in_launcher_job:
                # Request breakaway only when the bootstrap itself is job-managed.
                # If Windows denies it, create a regular child; process_details
                # will reject and reap it if it remains subject to that job.
                try:
                    process = subprocess.Popen(command, cwd=paths[0], stdin=subprocess.DEVNULL,
                        stdout=stdout, stderr=stderr, close_fds=True,
                        creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB)
                except OSError as error:
                    if getattr(error, 'winerror', None) != 5:
                        raise
                    process = subprocess.Popen(command, cwd=paths[0], stdin=subprocess.DEVNULL,
                        stdout=stdout, stderr=stderr, close_fds=True, creationflags=flags)
            else:
                process = subprocess.Popen(command, cwd=paths[0], stdin=subprocess.DEVNULL,
                    stdout=stdout, stderr=stderr, close_fds=True, creationflags=flags)
        return process, process_details(process)
    except BaseException as error:
        child_terminated = False
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        if process is not None:
            child_terminated = process.poll() is not None
        if process is not None and 'remains subject to job cleanup' in str(error):
            raise RuntimeError(
                f'{error}; pid={process.pid}; child_terminated={child_terminated}'
            ) from error
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    args = parser.parse_args()
    request_path = Path(args.request).resolve(strict=True)
    receipt = request_path.with_suffix('.result.json')
    child = None
    try:
        request = json.loads(request_path.read_text(encoding='utf-8-sig'))
        child, result = start(request)
        result['status'] = 'started'
        temporary = receipt.with_suffix('.tmp')
        temporary.write_text(json.dumps(result), encoding='utf-8')
        os.replace(temporary, receipt)
    except BaseException as error:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        receipt.write_text(json.dumps({'status': 'failed', 'error': str(error)}), encoding='utf-8')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
