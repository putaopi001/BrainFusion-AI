"""Persisted conversion behavior and tamper refusal, isolated synthetic originals."""
import copy
import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from app.services.dicom_conversion import convert_and_verify
from app.services.dicom_conversion_integrity import inspect_conversion_version
from test_dicom_conversion import files_fixture


@pytest.fixture
def version(tmp_path):
    proposal, snapshots, files, _ = files_fixture(tmp_path, negative=True, scaled=True)
    folder = tmp_path / 'version'
    report = convert_and_verify(proposal, snapshots, files, folder)
    sha = hashlib.sha256((folder / 'conversion-report.json').read_bytes()).hexdigest()
    return folder, sha, proposal, snapshots, report


def saved_bytes(folder):
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*') if p.is_file()}


def rewrite_report(folder, report):
    path = folder / 'conversion-report.json'
    path.write_text(json.dumps(report), encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reopen_actual_persisted_four_sequence_version_readonly(version):
    folder, sha, proposal, snapshots, _ = version
    before = saved_bytes(folder)
    first = inspect_conversion_version(folder, sha, proposal, snapshots)
    second = inspect_conversion_version(folder, sha, proposal, snapshots)
    assert first['status'] == second['status'] == 'verified_readonly'
    assert first['all_converted_voxels_rechecked'] and first['current_plan_matched']
    assert sum(row['all_voxels_compared'] for row in first['outputs'].values()) == 72
    assert all(row['maximum_absolute_intensity_error'] == 0 for row in first['outputs'].values())
    for key in ['model_input_eligible', 'inference_performed', 'source_files_written',
                'archive_or_business_database_written', 'reviewer_authenticated', 'live_archive_reconciled']:
        assert first[key] is False
    assert saved_bytes(folder) == before


@pytest.mark.parametrize('mode,reason,status', [
    ('report', 'conversion_report_sha_mismatch', 'invalid'),
    ('nifti', 'conversion_nifti_sha_mismatch', 'invalid'),
    ('snapshot', 'conversion_snapshot_sha_mismatch', 'invalid'),
    ('missing_nifti', 'conversion_file_missing', 'unavailable'),
    ('missing_report', 'conversion_file_missing', 'unavailable'),
    ('reviewer', 'conversion_source_stale', 'stale'),
    ('case', 'conversion_source_stale', 'stale'),
    ('archive', 'conversion_source_stale', 'stale'),
    ('unanchored', 'conversion_receipt_anchor_required', 'invalid'),
])
def test_real_file_or_current_source_changes_never_reuse_success(version, mode, reason, status):
    folder, sha, proposal, snapshots, report = version
    if mode == 'report':
        report['case_id'] = 18; rewrite_report(folder, report)
    elif mode == 'nifti':
        with (folder / 't1c.nii.gz').open('ab') as handle: handle.write(b'changed')
    elif mode == 'snapshot':
        with Path(report['outputs']['t1c']['source_instances'][0]['snapshot_path']).open('ab') as handle: handle.write(b'changed')
    elif mode == 'missing_nifti': (folder / 't1c.nii.gz').unlink()
    elif mode == 'missing_report': (folder / 'conversion-report.json').unlink()
    elif mode == 'reviewer': proposal['assignments'][0]['evidence']['reviewer_reference'] = 'new-reviewer'
    elif mode == 'case':
        proposal['case_id'] = 18
        for row in snapshots['series']: row['source_case_id'] = 18
    elif mode == 'archive':
        proposal['archive_fingerprint'] = 'a' * 64
        for row in snapshots['series']: row['archive_fingerprint'] = 'a' * 64
    else: sha = None
    before = saved_bytes(folder)
    result = inspect_conversion_version(folder, sha, proposal, snapshots)
    assert (result['reason'], result['status']) == (reason, status)
    assert not result['model_input_eligible'] and saved_bytes(folder) == before


@pytest.mark.parametrize('mode,reason', [
    ('uid', 'conversion_source_identity_mismatch'),
    ('order', 'conversion_instance_set_mismatch'),
    ('outside', 'conversion_path_mismatch'),
    ('eligible', 'conversion_report_invalid'),
    ('voxels', 'conversion_output_claim_mismatch'),
    ('false_geometry', 'conversion_output_claim_mismatch'),
    ('pixel_rehashed', 'conversion_pixels_mismatch'),
    ('layout_bomb', 'conversion_nifti_layout_invalid'),
])
def test_rehashed_claims_still_require_actual_source_and_voxels(version, mode, reason):
    folder, _, proposal, snapshots, report = version
    row = report['outputs']['t1c']
    if mode == 'uid': row['source_series_uid'] = '2.25.999'
    elif mode == 'order': row['source_instances'].reverse()
    elif mode == 'outside': row['nifti_path'] = str(folder.parent / 'outside.nii.gz')
    elif mode == 'eligible': report['model_input_eligible'] = True
    elif mode == 'voxels': row['all_voxels_compared'] = 19
    elif mode == 'false_geometry': row['affine_ras_mm'][0][3] += 1
    elif mode == 'pixel_rehashed':
        image = nib.load(folder / 't1c.nii.gz')
        pixels = np.asarray(image.dataobj).copy(); pixels[0, 0, 0] += 1
        nib.save(nib.Nifti1Image(pixels, image.affine, image.header.copy()), folder / 't1c.nii.gz')
        row['sha256'] = hashlib.sha256((folder / 't1c.nii.gz').read_bytes()).hexdigest()
    else:
        with gzip.open(folder / 't1c.nii.gz', 'rb') as handle: expanded = handle.read()
        (folder / 't1c.nii.gz').write_bytes(gzip.compress(expanded + b'\x00' * 1000000))
        row['sha256'] = hashlib.sha256((folder / 't1c.nii.gz').read_bytes()).hexdigest()
    sha = rewrite_report(folder, report)
    result = inspect_conversion_version(folder, sha, proposal, snapshots)
    assert result['status'] == 'invalid' and result['reason'] == reason


def test_change_during_window_and_symlink_snapshot_rejected(version, monkeypatch):
    import app.services.dicom_conversion_integrity as service
    folder, sha, proposal, snapshots, report = version
    original = service.source_dataset
    calls = 0
    def mutate(raw, source, planned):
        nonlocal calls
        calls += 1
        if calls == 12:
            with (folder / 'conversion-report.json').open('ab') as handle: handle.write(b' ')
        return original(raw, source, planned)
    monkeypatch.setattr(service, 'source_dataset', mutate)
    result = inspect_conversion_version(folder, sha, proposal, snapshots)
    assert result['reason'] == 'conversion_changed_during_inspection'


def test_snapshot_redirection_refused_before_read(version, monkeypatch):
    folder, sha, proposal, snapshots, report = version
    redirected = Path(report['outputs']['t1c']['source_instances'][0]['snapshot_path'])
    original_resolve = Path.resolve
    def resolving(path, *args, **kwargs):
        if path == redirected: return folder.parent / 'outside.dcm'
        return original_resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'resolve', resolving)
    result = inspect_conversion_version(folder, sha, proposal, snapshots)
    assert result['reason'] == 'conversion_path_escape'


def test_cli_second_process_reopens_without_writing_source_and_never_overwrites(version):
    folder, sha, proposal, snapshots, _ = version
    paths = []
    for name, value in [('proposal', proposal), ('snapshots', snapshots)]:
        path = folder.parent / (name + '.json'); path.write_text(json.dumps(value), encoding='utf-8'); paths.append(path)
    tool = Path(__file__).resolve().parents[1] / 'tools/inspect_dicom_conversion.py'
    output = folder.parent / 'inspection.json'
    args = [sys.executable, str(tool), '--version-dir', str(folder), '--report-sha256', sha,
            '--proposal', str(paths[0]), '--snapshots', str(paths[1]), '--output', str(output)]
    before = saved_bytes(folder)
    done = subprocess.run(args, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(output.read_text(encoding='utf-8'))['status'] == 'verified_readonly'
    retry = subprocess.run(args, capture_output=True, text=True)
    assert retry.returncode == 2 and saved_bytes(folder) == before
    inside = args[:-1] + [str(folder / 'new-inspection.json')]
    refused = subprocess.run(inside, capture_output=True, text=True)
    assert refused.returncode == 2 and not (folder / 'new-inspection.json').exists()
