"""Audit/build a local source-only handoff candidate; never publish or copy data.

Uses an explicit source allowlist, bounded credential patterns and per-file size
limits. Findings contain paths/line numbers/rule names, never credential values.
This is not a comprehensive security or redistribution-license certification.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import zipfile

DOCS = {
    'USER_OPERATION_GUIDE.md', 'LOCAL_RUN.md', 'AUTOMATIC_FEATURE_OPERATION_GUIDE.md',
    'RESEARCH_OPERATION_GUIDE.md', 'SYSTEM_BACKUP_RESTORE.md',
    'RADIOMICS_ENVIRONMENT_MIGRATION.md', 'DOCKER_PREREQUISITES.md',
    'FIXED_DEMO_GUIDE.md', 'RELEASE_SCOPE.md', 'RELEASE_CHECKLIST.md',
    'FEATURE_OVERVIEW.md', 'SOURCE_DELIVERY.md', 'ENVIRONMENT_INVENTORY.md',
    'THESIS_ENGINEERING_MATERIALS.md',
    'INDEPENDENT_MAINTENANCE_GUIDE.md',
    'LOCAL_DELIVERY_ACCEPTANCE.md',
    'CPU_RUNTIME_CANDIDATE.md',
    'CPU_DELIVERY_BOOTSTRAP.md',
    'FRONTEND_DELIVERY.md',
    'RADIOMICS_DELIVERY_BOOTSTRAP.md',
    'E5_DOCKER_CORE_LOCK_VALIDATION_20261018.md',
}
# Public operating guides and bounded validation summaries, never internal handoffs.
DOCS.update({
    'CPU_PACS_RUNTIME.md', 'E6_CPU_PACS_LIVE_VALIDATION.md',
    'PACS_LOCAL_PREPARATION.md', 'LOCAL_REVIEW_ACCOUNTS.md',
    'SYSTEM_ARCHITECTURE_CURRENT.md', 'E6_ARCHITECTURE_FIGURES.md',
    'E6_FULL_ACCOUNT_RECOVERY_VALIDATION.md',
    'P1_CORNERSTONE_VALIDATION.md', 'P1_MEASUREMENT_VIEW_VALIDATION.md',
    'P2_ORTHANC_ENV_VALIDATION.md', 'P2_SOURCE_BOUND_PREPARATION_VALIDATION.md',
    'P2_V2_REAL_IMPORT_VALIDATION.md', 'P2_PUBLIC_MR_SAMPLE_20261014.md',
    'P2_CONTROLLED_IMPORT_VALIDATION.md', 'P2_REAL_DICOM_VIEWING_VALIDATION.md',
    'P2_WADO_VALIDATION.md', 'P2_READ_PROXY_VALIDATION.md',
    'P2_PACS_RECONCILIATION_VALIDATION.md',
    'P2_DICOM_VIEWER_VALIDATION.md', 'P2_DICOM_SERIES_VALIDATION.md',
    'P2_DICOM_PREFLIGHT_VALIDATION.md', 'P2_DICOM_CUSTODY_VALIDATION.md',
    'P3_DICOM_RESAMPLING_ENGINEERING_VALIDATION_20261018.md',
    'P4_PACS_JOINT_RECOVERY_VALIDATION.md',
    'P3_DICOM_INPUT_CONVERSION_VALIDATION.md', 'P3_CONVERSION_INTEGRITY_VALIDATION.md',
    'P4_DICOM_MEASUREMENTS_VALIDATION.md', 'P4_DICOM_VIEW_STATE_VALIDATION.md',
    'P4_DICOM_READING_REPORT_VALIDATION.md', 'P4_DICOM_REVIEW_VALIDATION.md',
    'P4_REPORT_BOUNDARIES_VALIDATION.md', 'P4_JOINT17_RECOVERY_VALIDATION.md',
    'P4_LOCAL_REVIEW_IDENTITY_VALIDATION.md', 'P4_JOINT_ACCOUNT_RECOVERY_VALIDATION.md',
    'P4_EDGE_READONLY_VALIDATION.md', 'P4_EDGE_PERSISTENCE_VALIDATION.md',
    'P4_EDGE_NIFTI_VALIDATION.md', 'P4_VIEWER_PERFORMANCE_VALIDATION.md',
    'PACS_METADATA_PAGE_VALIDATION_20261020.md',
    'USER_ACCEPTANCE_QA_20261020.md', 'PROJECT_DEMO_QA.md',
})
DOCS.update({
    'RESEARCH_OFFLINE_REPLAY.md',
    'R2_ENTROPY_PROTOCOL.md', 'R2_ENTROPY_VALIDATION.md',
    'R2_ABLATION_PROTOCOL.md', 'R2_ABLATION_VALIDATION.md',
    'R3_FULL_PROTOCOL.md', 'R3_FULL_VALIDATION.md',
    'R4_STATISTICS_PROTOCOL.md', 'R4_STATISTICS_VALIDATION.md',
})
# Explicit filenames prevent unrelated screenshots/PHI being swept into the ZIP.
DOC_ASSETS = {
    'docs/assets/architecture-20261016/' + name for name in (
        'architecture-current.svg', 'architecture-current.png',
        'dicom-data-relations.svg', 'dicom-data-relations.png',
        'source-manifest.json', 'render-validation.json',
    )
}
PRIVATE_FILES = {'local-users.json', 'pacs-config.json', 'pacs-import-candidates.json',
                 'process.json', 'processes.json', 'runtime-supported.json',
                 'development-lock.json', 'dicom-conversions.json'}
SKIP_DIRS = {'.git', '.conda', '.venv', 'venv', '__pycache__', 'node_modules',
             '.pytest_cache', 'dist', 'uploads', 'processed', 'datasets', 'runtime',
             'test-results', 'playwright-report', 'daily', 'credentials', 'backups'}
SUFFIXES = {'.py', '.ps1', '.txt', '.ini', '.vue', '.js', '.mjs', '.json', '.css',
            '.scss', '.svg', '.png', '.jpg', '.ico', '.html', '.conf', '.md'}
ROOT_FILES = {'README.md', '.gitignore', 'docker-compose.yml'}
FRONT_CONFIG = {'package.json', 'package-lock.json', 'vite.config.js', 'playwright.config.js',
                'eslint.config.js', 'jsconfig.json', 'index.html', 'nginx.conf', 'Dockerfile',
                '.dockerignore', '.gitignore', '.editorconfig', '.gitattributes', '.prettierrc.json', 'README.md'}
RULES = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'aws_access_key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'github_token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b'),
    'huggingface_token': re.compile(r'\bhf_[A-Za-z0-9]{30,}\b'),
    'openai_token': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b'),
    'credential_in_url': re.compile(r'https?://[^\s/:@]+:[^\s/@]+@'),
}
MAX_BYTES = 2 * 1024**2


def permitted(relative):
    parts = relative.parts
    if (any(p.lower() in SKIP_DIRS for p in parts)
            or relative.name.lower().startswith('.env')
            or relative.name.lower() in PRIVATE_FILES
            or relative.name.lower().endswith(('.password.txt', '.token.txt'))):
        return False
    if len(parts) == 1:
        return relative.name in ROOT_FILES
    if parts[0] == 'docs':
        return (len(parts) == 2 and relative.name in DOCS) or relative.as_posix() in DOC_ASSETS
    if parts[0] == 'backend':
        return ((len(parts) == 2 and (relative.name.startswith('requirements') and relative.suffix == '.txt' or relative.name in {'Dockerfile', '.dockerignore', 'pytest.ini'}))
                or len(parts) >= 3 and parts[1] in {'app', 'tools', 'tests'} and relative.suffix in SUFFIXES)
    if parts[0] == 'frontend':
        return len(parts) == 2 and relative.name in FRONT_CONFIG or len(parts) >= 3 and parts[1] in {'src', 'public', 'tools', 'e2e'} and relative.suffix in SUFFIXES
    return False


def scan(root):
    files, findings, excluded = [], [], []
    for directory, directories, names in os.walk(root, followlinks=False):
        for name in list(directories):
            path = Path(directory) / name
            if name in SKIP_DIRS or getattr(path.stat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                directories.remove(name)
                excluded.append(path.relative_to(root).as_posix())
        for name in names:
            path = Path(directory) / name
            relative = path.relative_to(root)
            if not permitted(relative):
                continue
            info = path.stat()
            if getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                findings.append(dict(path=relative.as_posix(), rule='reparse_point'))
                continue
            if info.st_size > MAX_BYTES:
                findings.append(dict(path=relative.as_posix(), rule='oversize_source', bytes=info.st_size))
                continue
            raw = path.read_bytes()
            encoding = 'binary_asset'
            if relative.suffix not in {'.png', '.jpg', '.ico'}:
                encoding = 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
                try:
                    content = raw.decode(encoding)
                except UnicodeDecodeError:
                    findings.append(dict(path=relative.as_posix(), rule='unknown_source_encoding'))
                    continue
                for line_number, line in enumerate(content.splitlines(), 1):
                    for rule, pattern in RULES.items():
                        if pattern.search(line):
                            findings.append(dict(path=relative.as_posix(), line=line_number, rule=rule))
                if relative.suffix == '.py':
                    ast.parse(content, filename=relative.as_posix())
            files.append(dict(path=relative.as_posix(), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), encoding=encoding))
    return dict(status='passed' if not findings else 'rejected', files=sorted(files, key=lambda f:f['path']),
                findings=findings, excluded_directories=sorted(excluded),
                limits=dict(per_file_bytes=MAX_BYTES, credential_scan='Six bounded patterns, no values logged; not a full security or PHI assessment'),
                total_bytes=sum(f['bytes'] for f in files), created_utc=datetime.now(timezone.utc).isoformat())


def build(root, output, report):
    if report['status'] != 'passed':
        raise ValueError('Audit rejected source delivery; no archive created')
    archive_path = output / 'brainfusion-source-candidate.zip'
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in report['files']:
            raw = (root / entry['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise ValueError('Source changed after audit: ' + entry['path'])
            archive.writestr(entry['path'], raw)
    verification = output / 'unpacked-source'
    verification.mkdir()
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {entry['path'] for entry in report['files']}
        for entry in report['files']:
            target = (verification / entry['path']).resolve()
            target.relative_to(verification.resolve())
            raw = archive.read(entry['path'])
            assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(raw)
            assert hashlib.sha256(target.read_bytes()).hexdigest() == entry['sha256']
    return dict(status='passed', files=len(report['files']), archive_bytes=archive_path.stat().st_size,
                archive_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                scope='Local internal source-only candidate; no data/models/environments/frontend dependencies, no publication or complete deployment certification')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build-local-candidate', action='store_true')
    args = parser.parse_args()
    root = args.project.resolve(strict=True)
    root.relative_to(Path('E:/').resolve())
    output = args.output.resolve()
    output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    report = scan(root)
    (output / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(status=report['status'], files=len(report['files']), source_bytes=report['total_bytes'], findings=report['findings']), ensure_ascii=False))
    if report['status'] != 'passed':
        raise SystemExit(2)
    if args.build_local_candidate:
        validation = build(root, output, report)
        (output / 'validation.json').write_text(json.dumps(validation, indent=2), encoding='utf-8')
        print(json.dumps(validation))


if __name__ == '__main__':
    main()
