"""Read installed metadata and dependency-list drift without changing an environment.

An installed-package snapshot is not an upstream hash lock or install recipe.
Missing original package URLs are explicitly unknown, never fabricated.
"""
import argparse
from datetime import datetime, timezone
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import subprocess
import sys


def normalize(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    installed = {normalize(d.metadata['Name']): d.version for d in metadata.distributions() if d.metadata.get('Name')}
    root = Path(__file__).resolve().parents[1]
    lists = {}
    for name in ('requirements.txt', 'requirements-core.txt', 'requirements-research.txt'):
        raw = (root / name).read_bytes()
        text = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
        differences, matched = [], 0
        for line in text.splitlines():
            match = re.fullmatch(r'\s*([A-Za-z0-9_.-]+)==([^\s#]+)\s*', line)
            if not match:
                continue
            package, requested = match.groups()
            actual = installed.get(normalize(package))
            if actual != requested:
                differences.append(dict(package=package, listed=requested, installed=actual))
            else:
                matched += 1
        lists[name] = dict(exact_matches=matched, differences=differences, source_encoding='utf16' if text and raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf8')
    pip_check = subprocess.run([sys.executable, '-B', '-m', 'pip', 'check'], capture_output=True, text=True)
    essential = ['fastapi', 'uvicorn', 'sqlalchemy', 'pydantic', 'pydantic-settings',
                 'python-multipart', 'nibabel', 'simpleitk', 'numpy', 'pillow', 'scipy',
                 'monai', 'scikit-learn', 'joblib', 'pytest', 'httpx']
    (output / 'installed-main-snapshot.txt').write_text('# Observed installed metadata only, NOT an installation/hash lock\n' + '\n'.join(k + '==' + v for k,v in sorted(installed.items())) + '\n', encoding='utf-8')
    (output / 'minimal-main-observed.txt').write_text('# Observed required packages; CUDA torch intentionally excluded from generic pip installation\n' + '\n'.join(k + '==' + installed[k] for k in essential) + '\n', encoding='utf-8')
    result = dict(status='captured', python=sys.version, interpreter=str(Path(sys.executable).resolve()),
                  created_utc=datetime.now(timezone.utc).isoformat(), installed_packages=installed,
                  requirement_list_comparisons=lists, main_pip_check=dict(returncode=pip_check.returncode, output=(pip_check.stdout+pip_check.stderr).strip()),
                  original_install_urls='Unknown for historical main packages unless separately recorded; not inferred from installed versions',
                  worker_provenance='E:/BrainFusion-Runtime/envs/radiomics311-candidate/source.json',
                  no_environment_changes=True)
    (output / 'inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(status='captured', python=sys.version.split()[0], package_count=len(installed),
                         requirement_list_comparisons=lists, main_pip_check=result['main_pip_check']), ensure_ascii=False))


if __name__ == '__main__':
    main()
