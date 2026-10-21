"""Synthetic MR only: replay, missing coverage and byte drift must block import."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image
import pydicom
import pytest

from app.services import public_mr_preparation as preparation
from app.services import pacs_import
from app.services.pacs_client import load_config
from test_dicom_conversion import files_fixture
from test_pacs_import import archive, submit


@pytest.fixture
def source(tmp_path):
    _, _, files, _ = files_fixture(tmp_path)
    directory = tmp_path / 'source'
    directory.mkdir()
    for i, row in enumerate(list(files.values())[:3]):
        shutil.copyfile(row['path'], directory / f'{i}.dcm')
    ds = pydicom.dcmread(directory / '0.dcm')
    record = tmp_path / 'source-record.json'
    preparation.write_json(record, dict(collection='SYNTHETIC-OTHER-COLLECTION',
        collection_doi='10.9999/synthetic-fixture', expected_instances=3,
        source=dict(Collection='SYNTHETIC-OTHER-COLLECTION', PatientID=str(ds.PatientID),
                    StudyInstanceUID=str(ds.StudyInstanceUID), SeriesInstanceUID=str(ds.SeriesInstanceUID),
                    ImageCount=3, Modality='MR', LicenseURI=preparation.LICENSE)))
    return directory, record


def reviewed(source, tmp_path):
    folder = tmp_path / 'review'
    manifest = preparation.render_review(*source, folder)
    review = preparation.read_json(folder / 'review-template.json')
    review.update(reviewer='Synthetic test operator; no real clinical review',
        reviewed_utc=datetime.now(timezone.utc).isoformat(),
        sheets_checked=[s['file'] for s in manifest['sheets']], identifying_text_observed=False)
    path = folder / 'technical-review.json'
    preparation.write_json(path, review)
    return folder, path


def test_native_pixels_and_no_automatic_approval(source, tmp_path):
    folder = tmp_path / 'render'
    manifest = preparation.render_review(*source, folder)
    template = preparation.read_json(folder / 'review-template.json')
    assert template['identifying_text_observed'] is None and template['sheets_checked'] == []
    assert [f['file'] for f in manifest['source_snapshot']['files']] == ['0.dcm', '1.dcm', '2.dcm']
    ds = pydicom.dcmread(source[0] / '0.dcm')
    values = ds.pixel_array.astype(float)
    expected = np.rint((values - values.min()) / (values.max() - values.min()) * 255).astype('uint8')
    actual = np.asarray(Image.open(folder / 'sheet_01.png'))[:2, :3]
    np.testing.assert_array_equal(actual, expected)
    with pytest.raises(ValueError, match='Explicit complete'):
        preparation.prepare_reviewed(*source, folder, folder / 'review-template.json', tmp_path / 'no-output', 'TEST')
    assert not (tmp_path / 'no-output').exists()


@pytest.mark.parametrize('value', ['2026-10-14T15:19:17.9887760Z', '2026-10-14T23:19:17.9887760+08:00'])
def test_windows_timestamp_precision(value):
    assert preparation.review_time(value).astimezone(timezone.utc).isoformat() == '2026-10-14T15:19:17.988776+00:00'


@pytest.mark.parametrize('field,value', [
    ('PatientID', 'WRONG-PATIENT'), ('StudyInstanceUID', '2.25.101'),
    ('SeriesInstanceUID', '2.25.102'), ('ImageCount', 2), ('LicenseURI', 'unverified')])
def test_source_record_must_match_actual_series(source, tmp_path, field, value):
    record = preparation.read_json(source[1])
    record['source'][field] = value
    preparation.write_json(source[1], record)
    with pytest.raises(ValueError):
        preparation.render_review(*source, tmp_path / 'rejected')
    assert not (tmp_path / 'rejected').exists()


@pytest.mark.parametrize('change', ['source_bytes', 'source_record', 'sheet', 'missing_sheet', 'coverage', 'old_time', 'text_found'])
def test_stale_incomplete_or_wrong_review_is_rejected_before_derivative(source, tmp_path, change):
    folder, review_path = reviewed(source, tmp_path)
    if change == 'source_bytes':
        ds = pydicom.dcmread(source[0] / '0.dcm')
        ds.PixelData = (ds.pixel_array + 1).astype('<i2').tobytes()
        ds.save_as(source[0] / '0.dcm', enforce_file_format=True)
    elif change == 'source_record':
        source[1].write_bytes(source[1].read_bytes() + b' ')
    elif change == 'sheet':
        (folder / 'sheet_01.png').write_bytes(b'replaced')
    else:
        review = preparation.read_json(review_path)
        if change == 'missing_sheet':
            review['sheets_checked'] = []
        elif change == 'coverage':
            path = folder / 'render-manifest.json'
            render = preparation.read_json(path)
            render['sheets'][0]['source_files'] = ['0.dcm'] * 3
            preparation.write_json(path, render)
            review['render_manifest_sha256'] = preparation.sha(path.read_bytes())
        elif change == 'old_time':
            review['reviewed_utc'] = '2020-01-01T00:00:00+00:00'
        else:
            review['identifying_text_observed'] = True
        preparation.write_json(review_path, review)
    with pytest.raises(ValueError):
        preparation.prepare_reviewed(*source, folder, review_path, tmp_path / 'blocked', 'TEST')
    assert not (tmp_path / 'blocked').exists()


def test_v2_bundle_is_relocatable_and_pixel_preserving(source, tmp_path):
    folder, review = reviewed(source, tmp_path)
    before = {p.name: preparation.sha(p.read_bytes()) for p in source[0].glob('*.dcm')}
    output = tmp_path / 'prepared'
    report = preparation.prepare_reviewed(*source, folder, review, output, 'SYNTHETIC')
    assert report['format_version'] == 2 and report['status'] == 'prepared_and_verified'
    manifest = preparation.read_json(output / 'derivative-manifest.json')
    for row in manifest['instances']:
        original = pydicom.dcmread(source[0] / row['original_filename'])
        derived = pydicom.dcmread(output / 'instances' / row['derived_filename'])
        np.testing.assert_array_equal(original.pixel_array, derived.pixel_array)
        assert original.ImagePositionPatient == derived.ImagePositionPatient
        assert str(original.SOPInstanceUID) != str(derived.SOPInstanceUID)
    relocated = tmp_path / 'relocated'
    shutil.copytree(output, relocated)
    preparation.validate_prepared_review(relocated, manifest, report)
    assert before == {p.name: preparation.sha(p.read_bytes()) for p in source[0].glob('*.dcm')}
    assert report['clinical_deidentification_certified'] is False and report['ai_activation'] is False


def test_import_checks_bundled_pixel_review_before_any_archive_write(source, tmp_path, archive):
    folder, review = reviewed(source, tmp_path)
    output = tmp_path / 'derived' / 'v2'
    report = preparation.prepare_reviewed(*source, folder, review, output, 'SYNTHETIC')
    manifest = preparation.read_json(output / 'derivative-manifest.json')
    bundled_review = output / 'review-evidence' / 'technical-review.json'
    row = dict(candidate_id='b'*64, label='Synthetic v2', directory=str(output), review_record=str(bundled_review),
        manifest_sha256=preparation.sha((output/'derivative-manifest.json').read_bytes()),
        report_sha256=preparation.sha((output/'preparation-report.json').read_bytes()), review_sha256=preparation.sha(bundled_review.read_bytes()),
        instance_count=3, study_uid=manifest['study_uid'], series_uid=manifest['series_uid'],
        collection_doi=report['collection_doi'], license_url=report['license_url'])
    pacs_import.write_json(Path(pacs_import.settings.PACS_IMPORT_REGISTRY_FILE), dict(format_version=1, items=[row]))
    pacs_import.checked_candidate(row, load_config())
    assert submit(row).json()['data']['stored_new'] == 3
    archive['posts'] = 0
    (output/'review-evidence'/'sheet_01.png').write_bytes(b'changed')
    response = submit(row)
    assert response.status_code == 409 and archive['posts'] == 0
