"""Export exact Conda URLs and hash-locked pip dependencies without installing.

Checks package URL/hash/size against official PyPI version metadata. Writes only
to a fresh nightly directory; does not change gate-bound worker provenance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    source_bytes = args.source.read_bytes()
    source = json.loads(source_bytes)
    packages = source['conda_packages']
    assert all(p['url'].startswith('https://conda.anaconda.org/conda-forge/') and p['sha256'] and p['size'] for p in packages)
    # Conda explicit files support SHA256 fragments; all builds/URLs frozen.
    (output / 'conda-explicit.txt').write_text('@EXPLICIT\n' + '\n'.join(p['url'] + '#sha256:' + p['sha256'] for p in packages) + '\n', encoding='utf-8')
    records = []
    for dep in source['pypi_dependencies'] + source.get('supplemental_dependencies', []):
        name, version = dep['metadata']['name'], dep['metadata']['version']
        url = f'https://pypi.org/pypi/{name}/{version}/json'
        with urllib.request.urlopen(url, timeout=20) as response:
            raw = response.read(2 * 1024**2)
        (output / (name + '-pypi.json')).write_bytes(raw)
        selected = next(p for p in json.loads(raw)['urls'] if p['url'] == dep['download_info']['url'])
        expected = dep['download_info']['archive_info']['hashes']['sha256']
        assert selected['digests']['sha256'] == expected and selected['size'] > 0
        records.append(dict(name=name, version=version, url=selected['url'], bytes=selected['size'], sha256=expected,
                            metadata_url=url, metadata_sha256=hashlib.sha256(raw).hexdigest()))
    (output / 'pip-dependencies.txt').write_text('\n'.join(p['name'] + ' @ ' + p['url'] + ' --hash=sha256:' + p['sha256'] for p in records) + '\n', encoding='utf-8')
    wheel = Path(source['wheel'])
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == source['wheel_sha256']
    (output / 'pyradiomics-wheel.txt').write_text('pyradiomics @ ' + wheel.as_uri() + ' --hash=sha256:' + source['wheel_sha256'] + '\n', encoding='utf-8')
    result = dict(status='passed', source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                  conda_packages=packages, pip_packages=records, wheel=dict(path=str(wheel), bytes=wheel.stat().st_size, sha256=source['wheel_sha256']),
                  no_installation=True, license_details='Full dependency metadata and original licenses preserved in source.json/site-packages and compiler source.')
    (output / 'validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(status='passed', conda_packages=len(packages), pip_dependencies=len(records), output=str(output))))


if __name__ == '__main__':
    main()
