"""Minimal classic-MR metadata derivative for local research viewing.

Original pixels and geometry are preserved. This deliberately limited profile
is neither a PS3.15 conformance claim nor a pixel anonymizer/clinical converter.
Do not use it to generate or confirm AI modality roles.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
from app.core.storage import is_supported_storage_path

import numpy as np
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, MRImageStorage, generate_uid

PROFILE = 'classic-mr-local-viewing-metadata-v1'
# Retain only numeric/structural presentation, geometry, pixels and MR signals.
# No arbitrary text, sequences, original UIDs, private attributes or dates.
KEEP = {
    'Modality', 'SamplesPerPixel', 'PhotometricInterpretation', 'Rows', 'Columns',
    'BitsAllocated', 'BitsStored', 'HighBit', 'PixelRepresentation', 'PixelData',
    'PixelSpacing', 'ImagePositionPatient', 'ImageOrientationPatient',
    'SliceThickness', 'SpacingBetweenSlices', 'InstanceNumber',
    'RescaleIntercept', 'RescaleSlope', 'WindowCenter', 'WindowWidth',
    'NumberOfFrames', 'MRAcquisitionType', 'ScanningSequence', 'SequenceVariant',
    'ScanOptions', 'RepetitionTime', 'EchoTime', 'InversionTime',
    'EchoTrainLength', 'FlipAngle', 'MagneticFieldStrength',
    'PixelBandwidth', 'NumberOfAverages', 'ImagingFrequency',
    'AcquisitionMatrix', 'InPlanePhaseEncodingDirection',
}
REQUIRED = {'Modality', 'SamplesPerPixel', 'PhotometricInterpretation', 'Rows',
    'Columns', 'BitsAllocated', 'BitsStored', 'HighBit', 'PixelRepresentation',
    'PixelData', 'PixelSpacing', 'ImagePositionPatient', 'ImageOrientationPatient'}
IDENTITY = {'SOPClassUID', 'SOPInstanceUID', 'StudyInstanceUID', 'SeriesInstanceUID',
    'FrameOfReferenceUID', 'ImageType', 'PatientName', 'PatientID',
    'PatientBirthDate', 'PatientSex', 'StudyDate', 'StudyTime', 'AccessionNumber',
    'ReferringPhysicianName', 'StudyID', 'SeriesNumber', 'PatientIdentityRemoved',
    'DeidentificationMethod', 'BurnedInAnnotation'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def make_derivative(source, *, patient_id, uid_map):
    if source.SOPClassUID != MRImageStorage or source.Modality != 'MR':
        raise ValueError('Only classic single-frame MR is supported')
    if int(source.get('NumberOfFrames', 1)) != 1:
        raise ValueError('Multiframe is not supported')
    if any('MOSAIC' in str(v) for v in source.get('ImageType', [])):
        raise ValueError('MOSAIC is not supported')
    if str(source.get('BurnedInAnnotation', '')) == 'YES':
        raise ValueError('Source declares burned-in annotations; pixels are not anonymized here')
    if not REQUIRED.issubset({e.keyword for e in source}):
        raise ValueError('Required pixel/geometry fields are missing')
    if int(source.BitsAllocated) not in (8, 16) or int(source.SamplesPerPixel) != 1:
        raise ValueError('Unsupported pixel layout')
    if not source.file_meta.TransferSyntaxUID.is_little_endian or source.file_meta.TransferSyntaxUID.is_compressed:
        raise ValueError('Only uncompressed little-endian pixels are supported')
    if not patient_id or len(patient_id) > 50 or not all(c.isalnum() or c == '-' for c in patient_id):
        raise ValueError('Invalid local pseudonym')

    def mapped(uid):
        key = str(uid)
        if not key:
            raise ValueError('Missing source UID')
        if key not in uid_map:
            uid_map[key] = generate_uid(prefix='2.25.')
        return uid_map[key]

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = MRImageStorage
    meta.MediaStorageSOPInstanceUID = mapped(source.SOPInstanceUID)
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = '2.25.2894238358473455782324668983293812276'
    meta.ImplementationVersionName = 'BFVIEW1'
    result = FileDataset(None, {}, file_meta=meta, preamble=b'\0' * 128)
    for element in source:
        if element.keyword in KEEP:
            if element.tag.is_private or element.VR == 'SQ':
                raise ValueError('Unsupported retained field')
            result.add(copy.deepcopy(element))
    result.SOPClassUID = MRImageStorage
    result.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    result.StudyInstanceUID = mapped(source.StudyInstanceUID)
    result.SeriesInstanceUID = mapped(source.SeriesInstanceUID)
    result.FrameOfReferenceUID = mapped(source.FrameOfReferenceUID)
    result.ImageType = ['DERIVED', 'SECONDARY', 'LOCAL_VIEWING']
    result.PatientName = patient_id
    result.PatientID = patient_id
    result.PatientBirthDate = ''
    result.PatientSex = ''
    result.StudyDate = ''
    result.StudyTime = ''
    result.AccessionNumber = ''
    result.ReferringPhysicianName = ''
    result.StudyID = ''
    result.SeriesNumber = 1
    result.PatientIdentityRemoved = 'YES'
    result.DeidentificationMethod = PROFILE
    # Preserve only an existing NO declaration. Missing does not become NO.
    if str(source.get('BurnedInAnnotation', '')) == 'NO':
        result.BurnedInAnnotation = 'NO'
    buffer = io.BytesIO()
    pydicom.dcmwrite(buffer, result, enforce_file_format=True)
    raw = buffer.getvalue()
    reopened = pydicom.dcmread(io.BytesIO(raw))
    if reopened.PixelData != source.PixelData or not np.array_equal(reopened.pixel_array, source.pixel_array):
        raise ValueError('Derivative pixel values changed')
    if not all(str(reopened[k].value) == str(source[k].value) for k in REQUIRED - {'PixelData'}):
        raise ValueError('Derivative geometry or layout changed')
    if not {e.keyword for e in reopened}.issubset(KEEP | IDENTITY):
        raise ValueError('Unexpected derivative metadata')
    if any(e.tag.is_private or e.VR == 'SQ' for e in reopened):
        raise ValueError('Private/sequence metadata remained')
    if not all(not str(e.value) for e in reopened if e.VR in ('DA', 'DT', 'TM')):
        raise ValueError('Original dates remained')
    return raw


def prepare_series(source_dir, output_dir, patient_id):
    source_dir, output_dir = Path(source_dir).resolve(strict=True), Path(output_dir).resolve()
    if not is_supported_storage_path(source_dir) or not is_supported_storage_path(output_dir):
        raise ValueError('Source and output must use supported absolute local paths')
    if output_dir == source_dir or output_dir.is_relative_to(source_dir):
        raise ValueError('Derivative must be separate from originals')
    paths = sorted(source_dir.glob('*.dcm'))
    if not 2 <= len(paths) <= 512:
        raise ValueError('Expected 2–512 classic MR instances')
    if output_dir.exists():
        raise FileExistsError('Fresh derivative output required')
    output_dir.mkdir(parents=True)
    instances = output_dir / 'instances'
    instances.mkdir()
    uid_map, records = {}, []
    try:
        sources = []
        for path in paths:
            if path.stat().st_size > 64 * 1024 * 1024:
                raise ValueError('Source file exceeds profile limit')
            raw = path.read_bytes()
            sources.append((path, raw, pydicom.dcmread(io.BytesIO(raw))))
        if len({(str(ds.StudyInstanceUID), str(ds.SeriesInstanceUID), str(ds.FrameOfReferenceUID))
                for _, _, ds in sources}) != 1:
            raise ValueError('Mixed study/series/frame; use separate derivatives')
        if len({str(ds.SOPInstanceUID) for _, _, ds in sources}) != len(sources):
            raise ValueError('Duplicate SOP UID')
        for index, (path, raw, ds) in enumerate(sources):
            new = make_derivative(ds, patient_id=patient_id, uid_map=uid_map)
            target = instances / f'{index + 1:04d}.dcm'
            target.write_bytes(new)
            records.append({'original_filename': path.name, 'source_sha256': digest(raw),
                'derived_filename': target.name, 'derived_sha256': digest(new),
                'derived_sop_uid': uid_map[str(ds.SOPInstanceUID)],
                'pixel_sha256': digest(ds.PixelData)})
        for path, raw, _ in sources:
            if digest(path.read_bytes()) != digest(raw):
                raise ValueError('Source changed during preparation')
        first = sources[0][2]
        manifest = {'profile': PROFILE, 'patient_id': patient_id, 'instance_count': len(records),
            'study_uid': uid_map[str(first.StudyInstanceUID)],
            'series_uid': uid_map[str(first.SeriesInstanceUID)],
            'frame_uid': uid_map[str(first.FrameOfReferenceUID)],
            'original_pixels_and_geometry_preserved': True, 'metadata_whitelist_applied': True,
            'clinical_deidentification_certified': False, 'pixel_anonymization_performed': False,
            'data_role': 'public-clinical-derived-local-viewing-only', 'instances': records}
        (output_dir / 'private-uid-map.json').write_text(json.dumps(uid_map, indent=2), encoding='utf-8')
        (output_dir / 'derivative-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        return manifest
    except Exception:
        (output_dir / 'FAILED.txt').write_text('Incomplete preparation: not importable. Preserve for diagnosis.', encoding='utf-8')
        raise
