import io
import numpy as np
import pydicom
import pytest
from test_dicom_conversion import files_fixture
from app.services.dicom_viewing_derivative import make_derivative


def sample(tmp_path):
    _, _, files, _ = files_fixture(tmp_path)
    return pydicom.dcmread(next(iter(files.values()))['path'])


def test_derivative_preserves_pixels_geometry_and_remaps_identity(tmp_path):
    source = sample(tmp_path)
    source.PatientName = 'REMOVE_ME'
    source.InstitutionName = 'REMOVE_INSTITUTION'
    source.StudyDate = '20000101'
    source.add_new((0x0011, 0x1010), 'LO', 'REMOVE_PRIVATE')
    mapping = {}
    raw = make_derivative(source, patient_id='BF-PACS-001', uid_map=mapping)
    result = pydicom.dcmread(io.BytesIO(raw))
    assert np.array_equal(result.pixel_array, source.pixel_array)
    assert result.ImagePositionPatient == source.ImagePositionPatient
    assert result.ImageOrientationPatient == source.ImageOrientationPatient
    assert result.PixelSpacing == source.PixelSpacing
    assert result.PatientName == 'BF-PACS-001'
    assert result.StudyDate == ''
    assert 'InstitutionName' not in result
    assert not any(e.tag.is_private for e in result)
    assert result.SOPInstanceUID != source.SOPInstanceUID
    assert result.file_meta.MediaStorageSOPInstanceUID == result.SOPInstanceUID
    assert b'REMOVE_' not in raw
    # Reusing one map preserves series/frame identities across instances.
    again = pydicom.dcmread(io.BytesIO(make_derivative(source, patient_id='BF-PACS-001', uid_map=mapping)))
    assert again.SeriesInstanceUID == result.SeriesInstanceUID


def test_unknown_burned_annotation_does_not_become_false_certainty(tmp_path):
    source = sample(tmp_path)
    del source.BurnedInAnnotation
    result = pydicom.dcmread(io.BytesIO(make_derivative(source, patient_id='BF-PACS-001', uid_map={})))
    assert 'BurnedInAnnotation' not in result


@pytest.mark.parametrize('kind', ['mosaic', 'burned', 'missing_geometry', 'multiframe'])
def test_unsupported_source_rejected(tmp_path, kind):
    source = sample(tmp_path)
    if kind == 'mosaic': source.ImageType = ['ORIGINAL', 'PRIMARY', 'MOSAIC']
    elif kind == 'burned': source.BurnedInAnnotation = 'YES'
    elif kind == 'missing_geometry': del source.ImagePositionPatient
    else: source.NumberOfFrames = 2
    with pytest.raises(ValueError):
        make_derivative(source, patient_id='BF-PACS-001', uid_map={})
