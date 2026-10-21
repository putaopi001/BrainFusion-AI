"""Prepare local Orthanc configuration without downloading or running binaries.

--check-files only inspects downloaded bytes. --connect only reads a running
archive and installs the backend configuration after authentication/QIDO checks.
"""
import argparse
import hashlib
import json
import secrets
import struct
import urllib.error
import urllib.request
import base64
from pathlib import Path

ROOT = Path('E:/BrainFusion-Runtime/orthanc-local')
BIN = Path('E:/BrainFusion-Runtime/toolchains/orthanc-1.13.0-dicomweb-1.24')
FILES = {'Orthanc.exe': 27657216, 'OrthancDicomWeb-1.24.dll': 4914176}


def write_new(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def prepare():
    ROOT.mkdir(parents=True, exist_ok=True)
    BIN.mkdir(parents=True, exist_ok=True)
    for name in ['storage', 'index', 'logs']:
        (ROOT / name).mkdir(exist_ok=True)
    candidate = ROOT / 'brainfusion-pacs-candidate.json'
    config = ROOT / 'orthanc.json'
    if candidate.exists() or config.exists():
        raise FileExistsError('Configuration already exists; preserve it and inspect before changing.')
    user, password = 'brainfusion', secrets.token_urlsafe(32)
    orthanc = {
        'Name': 'BrainFusion Local PACS',
        'StorageDirectory': (ROOT / 'storage').as_posix(),
        'IndexDirectory': (ROOT / 'index').as_posix(),
        'HttpServerEnabled': True, 'HttpPort': 8042,
        'RemoteAccessAllowed': False, 'AuthenticationEnabled': True,
        'RegisteredUsers': {user: password},
        'DicomServerEnabled': False,
        'Plugins': [(BIN / 'OrthancDicomWeb-1.24.dll').as_posix()],
        'DicomWeb': {'Enable': True, 'Root': '/dicom-web/', 'EnableWado': True},
    }
    backend = {'format_version': 1, 'archive_id': 'brainfusion-local',
               'base_url': 'http://127.0.0.1:8042', 'username': user,
               'password': password, 'allow_pixel_read': False}
    write_new(config, orthanc)
    write_new(candidate, backend)
    print('Prepared private local configurations; credentials are not printed.')
    print('No binary download, execution, data import or live backend configuration change.')


def check_files():
    records = []
    for name, expected in FILES.items():
        path = BIN / name
        if not path.is_file():
            raise FileNotFoundError('Missing official file: ' + name)
        raw = path.read_bytes()
        if len(raw) != expected or raw[:2] != b'MZ' or len(raw) < 64:
            raise ValueError('Unexpected size or executable header: ' + name)
        offset = struct.unpack_from('<I', raw, 60)[0]
        if offset + 6 > len(raw) or raw[offset:offset + 4] != b'PE\0\0':
            raise ValueError('Invalid PE header: ' + name)
        if struct.unpack_from('<H', raw, offset + 4)[0] != 0x8664:
            raise ValueError('Expected Windows x64: ' + name)
        records.append({'name': name, 'bytes': len(raw),
                        'sha256': hashlib.sha256(raw).hexdigest()})
    output = ROOT / ('download-inspection-' + secrets.token_hex(4) + '.json')
    write_new(output, {'files': records, 'binary_executed': False,
                       'publisher_signature_verified': False,
                       'scope': 'local byte identity, size and architecture; not publisher authenticity'})
    print('Both files pass static size/x64 checks. No binary execution. Record:', output)


def connect():
    candidate = json.loads((ROOT / 'brainfusion-pacs-candidate.json').read_text(encoding='utf-8'))
    origin = candidate['base_url']
    if origin != 'http://127.0.0.1:8042':
        raise ValueError('Unexpected local origin')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(origin + '/system', timeout=3):
            pass
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise RuntimeError('Anonymous system request must return 401') from None
    else:
        raise RuntimeError('Archive did not enforce authentication')
    token = base64.b64encode((candidate['username'] + ':' + candidate['password']).encode()).decode()

    def get(path):
        req = urllib.request.Request(origin + path,
              headers={'Authorization': 'Basic ' + token, 'Accept': 'application/json'})
        with opener.open(req, timeout=5) as response:
            body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise RuntimeError('Response too large')
            return json.loads(body)

    system = get('/system')
    if system.get('Version') != '1.13.0':
        raise RuntimeError('Expected official candidate Orthanc 1.13.0; inspect actual installation first')
    studies = get('/dicom-web/studies?limit=1')
    if not isinstance(studies, list):
        raise RuntimeError('DICOMweb query did not return a list')
    server_id = system.get('DatabaseServerIdentifier')
    if not isinstance(server_id, str) or not server_id:
        raise RuntimeError('Missing database identity')
    candidate['expected_database_server_identifier'] = server_id
    destination = Path('E:/BrainFusion-Runtime/local/pacs-config.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Refuse to replace a previous archive binding or credentials.
    write_new(destination, candidate)
    print('Authenticated archive and DICOMweb are reachable; backend configuration installed.')
    print('Pixel reads remain disabled; no DICOM import or model activation performed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', action='store_true')
    group.add_argument('--check-files', action='store_true')
    group.add_argument('--connect', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.check_files:
        check_files()
    else:
        connect()


if __name__ == '__main__':
    main()
