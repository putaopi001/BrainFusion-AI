from pathlib import Path
import json
import zipfile
from tools.prepare_source_delivery import permitted, scan, build


def test_data_and_environments_are_excluded_even_if_git_tracks_them():
    for name in ['backend/uploads/case_1/patient.nii.gz', 'backend/brainfusion.db',
                 '.conda/main/python.exe', 'frontend/node_modules/module/index.js',
                 'frontend/.env', 'docs/NIGHTLY_HANDOFF.md', 'docs/daily/2026-10-10.md']:
        assert not permitted(Path(name))
    assert permitted(Path('backend/app/main.py'))
    assert permitted(Path('frontend/package-lock.json'))


def test_secret_findings_are_redacted_and_block_packaging(tmp_path):
    root = tmp_path / 'project'; root.mkdir()
    # Construct a synthetic key without embedding it in repository source.
    secret = 'ghp_' + 'A' * 36
    (root / 'README.md').write_text('credential=' + secret, encoding='utf-8')
    report = scan(root)
    assert report['status'] == 'rejected'
    assert secret not in json.dumps(report)
    assert report['findings'] == [{'path': 'README.md', 'line': 1, 'rule': 'github_token'}]
    import pytest
    with pytest.raises(ValueError, match='Audit rejected'):
        build(root, tmp_path, report)
    assert not (tmp_path / 'brainfusion-source-candidate.zip').exists()


def test_source_roundtrip_has_no_data_or_version_control(tmp_path):
    root = tmp_path / 'project'; root.mkdir()
    # Preserve original BOM/bytes while still auditing legacy UTF16 source text.
    (root / 'README.md').write_text('教学系统', encoding='utf-16')
    (root / 'backend').mkdir()
    (root / 'backend/brainfusion.db').write_bytes(b'synthetic database')
    (root / '.git').mkdir()
    (root / '.git/config').write_text('not for handoff', encoding='utf-8')
    report = scan(root)
    result = build(root, tmp_path, report)
    assert result['status'] == 'passed' and result['files'] == 1
    with zipfile.ZipFile(tmp_path / 'brainfusion-source-candidate.zip') as archive:
        assert archive.namelist() == ['README.md']
    assert (tmp_path / 'unpacked-source/README.md').read_text(encoding='utf-16') == '教学系统'


def test_current_public_guides_and_exact_architecture_assets_roundtrip(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    allowed = ['docs/LOCAL_REVIEW_ACCOUNTS.md', 'docs/SYSTEM_ARCHITECTURE_CURRENT.md',
               'docs/P2_V2_REAL_IMPORT_VALIDATION.md',
               'docs/INDEPENDENT_MAINTENANCE_GUIDE.md',
               'docs/PACS_METADATA_PAGE_VALIDATION_20261020.md',
               'docs/USER_ACCEPTANCE_QA_20261020.md',
               'docs/PROJECT_DEMO_QA.md',
               'docs/assets/architecture-20261016/architecture-current.png']
    excluded = ['docs/NIGHTLY_HANDOFF.md', 'docs/REVIEW_FEEDBACK.md',
                'docs/DAILY_SYSTEM_COMPLETION_TASK.md',
                'docs/assets/architecture-20261016/patient-screenshot.png',
                'docs/assets/unreviewed/architecture-current.png']
    for name in allowed + excluded:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'owned synthetic asset' if path.suffix == '.png' else b'public synthetic guide')
    report = scan(root)
    assert {row['path'] for row in report['files']} == set(allowed)
    build(root, tmp_path, report)
    assert all((tmp_path/'unpacked-source'/name).read_bytes() == (root/name).read_bytes() for name in allowed)
    assert all(not (tmp_path/'unpacked-source'/name).exists() for name in excluded)


def test_private_configuration_cannot_enter_allowed_source_trees(tmp_path):
    root = tmp_path/'project'
    private = ['backend/tools/local-users.json', 'backend/tools/pacs-config.json',
               'backend/tools/credentials/initial.txt', 'frontend/public/session.token.txt',
               'frontend/public/initial.password.txt', 'frontend/tools/processes.json',
               'backend/tools/Backups/copy.py', 'frontend/public/.ENV.production']
    for name in private:
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic private value', encoding='utf-8')
    report = scan(root)
    assert report['status'] == 'passed' and report['files'] == []


def test_research_protocols_travel_with_code_but_cohort_outputs_do_not(tmp_path):
    root = tmp_path/'project'
    guides = ['RESEARCH_OFFLINE_REPLAY.md', 'R2_ENTROPY_PROTOCOL.md', 'R2_ENTROPY_VALIDATION.md',
              'R2_ABLATION_PROTOCOL.md', 'R2_ABLATION_VALIDATION.md', 'R3_FULL_PROTOCOL.md',
              'R3_FULL_VALIDATION.md', 'R4_STATISTICS_PROTOCOL.md', 'R4_STATISTICS_VALIDATION.md']
    allowed = ['docs/'+name for name in guides] + ['backend/app/research/patient_statistics.py']
    excluded = ['docs/R4_PATIENT_RESULTS.json', 'docs/research/patient-probabilities.csv',
                'research/patient-probabilities.csv', 'backend/datasets/labels.csv',
                'docs/daily/private-research.md', 'docs/R4_UNREVIEWED_NOTES.md']
    for name in allowed + excluded:
        path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# synthetic source only\n' if path.suffix == '.py' else 'synthetic guide or excluded fixture', encoding='utf-8')
    report = scan(root)
    assert report['status'] == 'passed'
    assert {row['path'] for row in report['files']} == set(allowed)
    build(root, tmp_path, report)
    assert all((tmp_path/'unpacked-source'/name).read_bytes() == (root/name).read_bytes() for name in allowed)
    assert all(not (tmp_path/'unpacked-source'/name).exists() for name in excluded)
