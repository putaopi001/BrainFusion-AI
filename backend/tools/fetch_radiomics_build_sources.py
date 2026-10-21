"""Fetch checksum-verified upstream compiler/source archives to E:, not installers.

Does not execute downloaded content or mutate the main/legacy Python environments.
Interrupted HTTP downloads retain .part and support Range continuation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import time
import urllib.request
import zipfile

CACHE = Path('E:/BrainFusion-Runtime/cache/radiomics-build')
TOOLCHAINS = Path('E:/BrainFusion-Runtime/toolchains')
ZIG_VERSION = '0.15.2'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def download(url, filename, expected, size):
    target = CACHE / filename
    if target.exists():
        if target.stat().st_size != size or digest(target) != expected:
            raise ValueError('Existing cache does not match upstream checksum: ' + str(target))
        print('Verified cached archive: ' + filename, flush=True)
        return target
    partial = target.with_name(target.name + '.part')
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {'User-Agent': 'BrainFusion-isolated-build'}
    if offset:
        headers['Range'] = 'bytes=' + str(offset) + '-'
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        resumed = bool(offset and response.status == 206)
        if resumed and not response.headers.get('Content-Range', '').startswith('bytes ' + str(offset) + '-'):
            raise ValueError('Invalid resume offset from server')
        with partial.open('ab' if resumed else 'wb') as stream:
            written = offset if resumed else 0
            last = 0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                stream.write(block)
                written += len(block)
                if written > size:
                    raise ValueError('Archive larger than published size')
                if time.monotonic() - last > 10:
                    print(filename + ': ' + str(written) + '/' + str(size) + ' bytes', flush=True)
                    last = time.monotonic()
    if partial.stat().st_size != size or digest(partial) != expected:
        raise ValueError('Incomplete or checksum-mismatched download; partial retained')
    partial.replace(target)
    return target


def safe_target(root, name):
    path = (root / name).resolve()
    path.relative_to(root.resolve())
    if path == root.resolve():
        raise ValueError('Archive member must be inside extraction directory')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pypi-metadata', type=Path, required=True)
    parser.add_argument('--pypi-metadata-sha256', required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    CACHE.mkdir(parents=True, exist_ok=True)
    TOOLCHAINS.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(CACHE).free < 2 * 1024**3:
        raise ValueError('Need at least 2GiB free for isolated compiler/source/build')
    if digest(args.pypi_metadata) != args.pypi_metadata_sha256:
        raise ValueError('Previously verified PyPI metadata changed')
    pypi = json.loads(args.pypi_metadata.read_text(encoding='utf-8'))
    with urllib.request.urlopen('https://ziglang.org/download/index.json', timeout=20) as response:
        raw = response.read(2 * 1024**2)
    (output / 'zig-index.json').write_bytes(raw)
    zig = json.loads(raw)[ZIG_VERSION]['x86_64-windows']
    source = next(item for item in pypi['urls'] if item['packagetype'] == 'sdist')
    if not zig['tarball'].startswith('https://ziglang.org/download/') or not source['url'].startswith('https://files.pythonhosted.org/'):
        raise ValueError('Unexpected archive origins')
    items = [dict(role='portable C compiler', url=zig['tarball'], sha256=zig['shasum'], bytes=int(zig['size']), license='MIT/LLVM/mingw bundled license files'),
             dict(role='PyRadiomics upstream source', url=source['url'], sha256=source['digests']['sha256'], bytes=source['size'], license='BSD-3-Clause')]
    plan = {'pid': os.getpid(), 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'sources': items, 'download_bytes': sum(item['bytes'] for item in items),
            'space_budget_bytes': 2 * 1024**3, 'executed_downloaded_content': False}
    (output / 'plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    print(json.dumps(plan), flush=True)
    compiler_archive = download(items[0]['url'], Path(items[0]['url']).name, items[0]['sha256'], items[0]['bytes'])
    source_archive = download(items[1]['url'], source['filename'], items[1]['sha256'], items[1]['bytes'])
    # New extraction directories; existing complete archives are reusable, not overwritten.
    compiler_root = TOOLCHAINS / ('zig-' + ZIG_VERSION)
    reuse_compiler = compiler_root.exists()
    compiler_root.mkdir(exist_ok=True)
    with zipfile.ZipFile(compiler_archive) as archive:
        for member in archive.infolist():
            target = safe_target(compiler_root, member.filename)
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Archive symlink rejected')
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                if reuse_compiler:
                    # Reuse only a complete byte-identical original extraction.
                    # A partial/different tree is never overwritten or executed.
                    with archive.open(member) as src:
                        expected = hashlib.sha256()
                        for block in iter(lambda: src.read(1024 * 1024), b''):
                            expected.update(block)
                    if not target.is_file() or target.stat().st_size != member.file_size or digest(target) != expected.hexdigest():
                        raise ValueError('Existing compiler tree differs; preserve it and use a separately verified directory: ' + str(target))
                else:
                    with archive.open(member) as src, target.open('xb') as dst:
                        shutil.copyfileobj(src, dst)
    source_root = output / 'pyradiomics-source'
    source_root.mkdir()
    with tarfile.open(source_archive) as archive:
        for member in archive.getmembers():
            # Do not unpack data/test scripts: only package and build provenance.
            parts = Path(member.name).parts
            if len(parts) < 2 or not (parts[1] == 'radiomics' or parts[1] in {'setup.py', 'setup.cfg', 'PKG-INFO', 'LICENSE.txt', 'LICENSE', 'README.md', 'requirements.txt'}):
                continue
            target = safe_target(source_root, str(Path(*parts[1:])))
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
            else:
                raise ValueError('Non-regular source member rejected')
    result = {**plan, 'status': 'fetched_and_verified_not_executed',
              'compiler': str(next(compiler_root.rglob('zig.exe'))), 'source_root': str(source_root),
              'compiler_reused_identical': reuse_compiler,
              'metadata_sha256': {'zig-index.json': hashlib.sha256(raw).hexdigest(), 'pypi': args.pypi_metadata_sha256}}
    (output / 'sources.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
