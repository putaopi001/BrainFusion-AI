"""Read-only Windows container prerequisites; no install, elevation or reboot."""
import argparse
import ctypes
import json
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    result = {'elevated': bool(ctypes.windll.shell32.IsUserAnAdmin()), 'commands': {}, 'checks': {}}
    for name in ('docker', 'wsl', 'cl', 'cmake', 'clang-cl'):
        result['commands'][name] = shutil.which(name)
    for name, flags in (('wsl', ['--status']), ('docker', ['info'])):
        executable = result['commands'][name]
        if not executable:
            result['checks'][name] = {'status': 'not_on_path'}
            continue
        try:
            completed = subprocess.run([executable, *flags], capture_output=True, timeout=20, check=False)
            decoded = {}
            for channel in ('stdout', 'stderr'):
                raw = getattr(completed, channel)
                (output / (name + '-' + channel + '.bin')).write_bytes(raw)
                # wsl.exe's redirected localized output is UTF-16LE, not UTF-8.
                encoding = 'utf-16le' if b'\x00' in raw else 'utf-8'
                decoded[channel] = raw.decode(encoding, errors='replace').strip('\ufeff\r\n ')
            result['checks'][name] = {'returncode': completed.returncode, **decoded}
        except subprocess.TimeoutExpired:
            result['checks'][name] = {'status': 'timeout', 'seconds': 20}
    result['mutations'] = []
    result['scope'] = 'Read-only prerequisite probe, not Docker/WSL installation or container acceptance'
    (output / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
