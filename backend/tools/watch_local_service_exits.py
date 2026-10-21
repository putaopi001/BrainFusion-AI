"""Bounded read-only Windows exit observation; no restart and no development lock."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import time
import os

KERNEL=ctypes.WinDLL('kernel32',use_last_error=True) if os.name=='nt' else None
if KERNEL:
    KERNEL.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];KERNEL.OpenProcess.restype=wintypes.HANDLE
    KERNEL.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    KERNEL.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    KERNEL.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    KERNEL.CloseHandle.argtypes=[wintypes.HANDLE]


def created_filetime(handle):
    values=[wintypes.FILETIME() for _ in range(4)]
    if not KERNEL.GetProcessTimes(handle,*(ctypes.byref(x) for x in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    return (values[0].dwHighDateTime<<32)|values[0].dwLowDateTime


def iso_filetime(value):
    seconds,fraction=divmod(value,10_000_000)
    date=datetime(1601,1,1,tzinfo=timezone.utc)+timedelta(seconds=seconds)
    return date.strftime('%Y-%m-%dT%H:%M:%S')+f'.{fraction:07d}Z'


def parse_filetime(value):
    match=re.fullmatch(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,7}))?Z',value)
    if not match:raise ValueError('UTC process identity required')
    date=datetime.strptime(match[1],'%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
    seconds=int((date-datetime(1601,1,1,tzinfo=timezone.utc)).total_seconds())
    return seconds*10_000_000+int((match[2] or '').ljust(7,'0'))


def observe(plan_path,output,max_seconds):
    if KERNEL is None:raise RuntimeError('Windows process observation required')
    output=Path(output).resolve()
    base=Path('E:/BrainFusion-Runtime/results/nightly').resolve()
    if output==base or not output.is_relative_to(base) or output.exists():raise ValueError('Fresh nightly child output required')
    plan=json.loads(Path(plan_path).read_text(encoding='utf-8-sig'))
    entries=plan['services']
    if not 1<=len(entries)<=8:raise ValueError('Require one to eight process identities')
    opened=[];names=set()
    try:
        for entry in entries:
            name=entry['name']
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',name) or name in names:raise ValueError('Invalid observation name')
            names.add(name)
            handle=KERNEL.OpenProcess(0x100000|0x1000,False,int(entry['pid']))
            if not handle:raise ctypes.WinError(ctypes.get_last_error())
            opened.append(dict(entry=entry,handle=handle,observed=False))
            if created_filetime(handle)!=parse_filetime(entry['started_utc']):raise ValueError('Process identity mismatch')
        self_handle=KERNEL.OpenProcess(0x1000,False,os.getpid())
        try:self_started=iso_filetime(created_filetime(self_handle))
        finally:KERNEL.CloseHandle(self_handle)
        output.mkdir()
        utc=lambda:datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        deadline=time.monotonic()+max_seconds
        job=dict(pid=os.getpid(),started_utc=self_started,state='running',deadline_utc=(datetime.now(timezone.utc)+timedelta(seconds=max_seconds)).isoformat().replace('+00:00','Z'),holds_development_lock=False,restarts_services=False,writes_project_or_business_data=False)
        def save():
            temporary=output/'job.tmp';temporary.write_text(json.dumps(job,indent=2),encoding='utf-8');temporary.replace(output/'job.json')
        save();events=[];last_heartbeat=time.monotonic()
        try:
            while time.monotonic()<deadline:
                for row in opened:
                    state=KERNEL.WaitForSingleObject(row['handle'],0)
                    if state==0 and not row['observed']:
                        code=wintypes.DWORD()
                        if not KERNEL.GetExitCodeProcess(row['handle'],ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
                        event=dict(row['entry'],event='exited',exit_code=code.value,observed_utc=utc())
                        with (output/'events.jsonl').open('a',encoding='utf-8') as file:file.write(json.dumps(event)+'\n')
                        events.append(event);row['observed']=True
                    elif state not in (0,258):raise ctypes.WinError(ctypes.get_last_error())
                if all(row['observed'] for row in opened):break
                if time.monotonic()-last_heartbeat>=30:
                    job['last_check_utc']=utc();save();last_heartbeat=time.monotonic()
                time.sleep(.1)
            job['state']='all_exits_observed' if all(row['observed'] for row in opened) else 'deadline_reached'
        except BaseException:
            job['state']='failed';raise
        finally:
            job['ended_utc']=utc();save()
            (output/'summary.json').write_text(json.dumps(dict(state=job['state'],events=events,still_unobserved=[row['entry'] for row in opened if not row['observed']]),indent=2),encoding='utf-8')
    finally:
        for row in opened:KERNEL.CloseHandle(row['handle'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--max-seconds',type=int,default=7200)
    args=parser.parse_args()
    if not 1<=args.max_seconds<=21600:parser.error('Observation must be between 1 and 21600 seconds')
    observe(args.plan,args.output,args.max_seconds)
