"""Expose a bounded exception summary, not the worker's complete traceback."""
import re
from pathlib import Path


def worker_failure(log_path, worker_name):
    try:
        with Path(log_path).open('rb') as log:
            log.seek(0, 2)
            log.seek(max(0, log.tell() - 8192))
            lines = log.read().decode('utf-8', errors='replace').splitlines()
        for line in reversed(lines):
            if re.match(r'^[\w.]+(?:Error|Exception): ', line):
                return f'{worker_name} failed: {line[:400]}'
    except OSError:
        pass
    return f'{worker_name} failed; inspect the task worker.log for details'
