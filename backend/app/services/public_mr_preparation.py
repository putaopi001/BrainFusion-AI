"""Source-bound technical review; no publisher signature or clinical certification."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
from app.core.storage import is_supported_storage_path
import re
import shutil
from types import SimpleNamespace

import numpy as np
import pydicom
from PIL import Image, ImageDraw

from app.services.dicom_series import validate_series
from app.services.dicom_viewing_derivative import make_derivative, prepare_series

LICENSE = 'https://creativecommons.org/licenses/by/4.0/'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Review/source record exceeds limit')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def local(path):
    path = Path(path).resolve(strict=True)
    if not is_supported_storage_path(path):
        raise ValueError('Source and review materials must use supported absolute local paths')
    return path


def review_time(value):
    # Windows emits seven fractional digits; Python 3.10 only accepts three or
    # six. Parse bounded RFC3339 explicitly, retaining microsecond precision.
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})', value)
    if not match:
        raise ValueError('Review requires a timezone-aware RFC3339 timestamp')
    return datetime.fromisoformat(match[1] + '.' + (match[2] or '').ljust(6, '0')[:6] + match[3].replace('Z', '+00:00'))


def inspect_source(source_dir, source_record):
    folder, record_path = local(source_dir), local(source_record)
    record = read_json(record_path)
    source = record['source']
    if (source.get('LicenseURI') != LICENSE or not record.get('collection')
            or source.get('Collection') != record['collection'] or source.get('Modality') != 'MR'
            or not re.fullmatch(r'10\.\d{4,9}/\S+', record.get('collection_doi', ''))):
        raise ValueError('A consistent public MR source record and CC BY 4.0 license are required')
    paths = sorted(folder.glob('*.dcm'))
    if (not 2 <= len(paths) <= 512 or len(paths) != source.get('ImageCount')
            or len(paths) != record.get('expected_instances')):
        raise ValueError('Source instance count differs from the recorded series')
    rows, metadata, total, mapping = [], [], 0, {}
    for path in paths:
        if path.is_symlink() or path.resolve().parent != folder or path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('Unsupported source file/path')
        raw = path.read_bytes()
        total += len(raw)
        if total > 256 * 1024 * 1024:
            raise ValueError('Source series exceeds 256 MiB limit')
        ds = pydicom.dcmread(io.BytesIO(raw))
        if (str(ds.StudyInstanceUID) != source['StudyInstanceUID']
                or str(ds.SeriesInstanceUID) != source['SeriesInstanceUID']
                or str(ds.PatientID) != source['PatientID']
                or str(ds.file_meta.MediaStorageSOPInstanceUID) != str(ds.SOPInstanceUID)):
            raise ValueError('Source patient/study/series/SOP differs from the recorded source')
        # Exercise the real supported profile; retain no generated DICOM here.
        make_derivative(ds, patient_id='TECHNICAL-REVIEW', uid_map=mapping)
        if int(ds.Rows) > 1024 or int(ds.Columns) > 1024:
            raise ValueError('Native review tiles exceed 1024 pixels per dimension')
        rows.append(dict(file=path.name, sha256=sha(raw), bytes=len(raw), sop_uid=str(ds.SOPInstanceUID)))
        del ds.PixelData
        metadata.append(ds.to_json_dict())
    validate_series(SimpleNamespace(allow_pixel_read=False), metadata,
                    source['StudyInstanceUID'], source['SeriesInstanceUID'], [r['sop_uid'] for r in rows])
    return record, dict(source_record_sha256=sha(record_path.read_bytes()), files=rows)


def render_review(source_dir, source_record, output_dir):
    source_dir, source_record = local(source_dir), local(source_record)
    _, snapshot = inspect_source(source_dir, source_record)
    output = Path(output_dir).resolve()
    if not is_supported_storage_path(output) or output.exists() or output.is_relative_to(source_dir):
        raise ValueError('A fresh, separate E: review directory is required')
    output.mkdir(parents=True)
    first = pydicom.dcmread(source_dir / snapshot['files'][0]['file'])
    def scalar(value):
        return float(value[0] if isinstance(value, pydicom.multival.MultiValue) else value)
    if 'WindowCenter' in first and 'WindowWidth' in first:
        center, width = scalar(first.WindowCenter), scalar(first.WindowWidth)
        method = 'common first-source DICOM window after per-instance rescale'
    else:
        values = first.pixel_array.astype(float) * float(first.get('RescaleSlope', 1)) + float(first.get('RescaleIntercept', 0))
        center, width = float((values.min() + values.max()) / 2), max(1., float(values.max() - values.min()))
        method = 'common first-source full intensity range after per-instance rescale'
    if not np.isfinite([center, width]).all() or width <= 0:
        raise ValueError('Invalid source review window')
    height, tile_width = int(first.Rows), int(first.Columns)
    sheets = []
    for start in range(0, len(snapshot['files']), 32):
        group = snapshot['files'][start:start + 32]
        canvas = Image.new('L', (tile_width * 8, (height + 18) * ((len(group) + 7) // 8)))
        draw = ImageDraw.Draw(canvas)
        for i, row in enumerate(group):
            raw = (source_dir / row['file']).read_bytes()
            if sha(raw) != row['sha256']:
                raise ValueError('Source changed during review rendering')
            ds = pydicom.dcmread(io.BytesIO(raw))
            pixels = ds.pixel_array.astype(float) * float(ds.get('RescaleSlope', 1)) + float(ds.get('RescaleIntercept', 0))
            gray = np.rint(np.clip((pixels - (center - width / 2)) / width, 0, 1) * 255).astype('uint8')
            if ds.PhotometricInterpretation == 'MONOCHROME1':
                gray = 255 - gray
            x, y = (i % 8) * tile_width, (i // 8) * (height + 18)
            canvas.paste(Image.fromarray(gray), (x, y))
            draw.text((x, y + height), str(start + i + 1), fill=255)
        name = f'sheet_{len(sheets) + 1:02d}.png'
        canvas.save(output / name)
        sheets.append(dict(file=name, sha256=sha((output / name).read_bytes()),
                           source_files=[r['file'] for r in group]))
    if inspect_source(source_dir, source_record)[1] != snapshot:
        raise ValueError('Source changed during review rendering')
    manifest = dict(format_version=1, rendered_utc=datetime.now(timezone.utc).isoformat(),
                    source_snapshot=snapshot, native_tile_shape=[height, tile_width],
                    window=dict(method=method, center=center, width=width),
                    metadata_overlay=False, source_dicom_modified=False, sheets=sheets)
    write_json(output / 'render-manifest.json', manifest)
    write_json(output / 'review-template.json', dict(format_version=1, reviewer='', reviewed_utc='',
        render_manifest_sha256=sha((output / 'render-manifest.json').read_bytes()),
        sheets_checked=[], identifying_text_observed=None, clinical_deidentification_certified=False,
        scope='Technical observation of native pixels at one recorded window; not clinical certification'))
    return manifest


def validate_review(review_dir, review_record, snapshot):
    root, review_path = local(review_dir), local(review_record)
    render_path = root / 'render-manifest.json'
    manifest, review = read_json(render_path), read_json(review_path)
    if (manifest.get('format_version') != 1 or manifest.get('source_snapshot') != snapshot
            or manifest.get('metadata_overlay') is not False or manifest.get('source_dicom_modified') is not False):
        raise ValueError('Pixel review does not bind the current source bytes')
    names, covered = [], []
    for sheet in manifest['sheets']:
        name = sheet['file']
        if Path(name).name != name or not re.fullmatch(r'sheet_\d{2}\.png', name):
            raise ValueError('Invalid review sheet path')
        path = root / name
        if path.is_symlink() or sha(path.read_bytes()) != sheet['sha256']:
            raise ValueError('Reviewed sheet changed')
        names.append(name)
        covered.extend(sheet['source_files'])
    if (not names or len(set(names)) != len(names)
            or covered != [r['file'] for r in snapshot['files']]):
        raise ValueError('Pixel review does not cover every source instance exactly once')
    if (review.get('format_version') != 1 or not isinstance(review.get('reviewer'), str)
            or not 1 <= len(review['reviewer'].strip()) <= 256
            or review.get('render_manifest_sha256') != sha(render_path.read_bytes())
            or review.get('sheets_checked') != names or review.get('identifying_text_observed') is not False
            or review.get('clinical_deidentification_certified') is not False
            or not isinstance(review.get('scope'), str) or not 1 <= len(review['scope'].strip()) <= 2000
            or not isinstance(review.get('reviewed_utc'), str)):
        raise ValueError('Explicit complete technical review is required; a template is not approval')
    reviewed = review_time(review['reviewed_utc'])
    rendered = review_time(manifest['rendered_utc'])
    if reviewed.tzinfo is None or rendered.tzinfo is None or reviewed < rendered or reviewed > datetime.now(timezone.utc):
        raise ValueError('Review requires an actual timezone-aware time after rendering')
    return manifest, review


def validate_prepared_review(root, manifest, report):
    """Check bundled proof without requiring external source paths to exist."""
    root = Path(root) / 'review-evidence'
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Invalid preparation review directory')
    hashes = report['review_evidence_sha256']
    expected = {'source-record.json', 'render-manifest.json', 'technical-review.json'}
    render = read_json(root / 'render-manifest.json')
    expected.update(s['file'] for s in render['sheets'])
    if set(hashes) != expected or {p.name for p in root.iterdir()} != expected:
        raise ValueError('Incomplete preparation review bundle')
    for name, expected_hash in hashes.items():
        path = root / name
        if Path(name).name != name or path.is_symlink() or sha(path.read_bytes()) != expected_hash:
            raise ValueError('Preparation review bundle changed')
    snapshot = render['source_snapshot']
    if (snapshot['source_record_sha256'] != sha((root / 'source-record.json').read_bytes())
            or snapshot['source_record_sha256'] != report['public_source_record_sha256']):
        raise ValueError('Source record differs from the reviewed record')
    validate_review(root, root / 'technical-review.json', snapshot)
    actual = [(r['original_filename'], r['source_sha256']) for r in manifest['instances']]
    if actual != [(r['file'], r['sha256']) for r in snapshot['files']]:
        raise ValueError('Derivative inputs differ from the reviewed source bytes')
    source = read_json(root / 'source-record.json')
    if (source['source']['LicenseURI'] != report['license_url'] or source['collection_doi'] != report['collection_doi']
            or len(actual) != source['expected_instances'] or len(actual) != source['source']['ImageCount']):
        raise ValueError('Preparation source attribution differs')


def prepare_reviewed(source_dir, source_record, review_dir, review_record, output_dir, patient_id):
    provenance, snapshot = inspect_source(source_dir, source_record)
    render, review = validate_review(review_dir, review_record, snapshot)
    manifest = prepare_series(source_dir, output_dir, patient_id)
    output = Path(output_dir)
    try:
        if inspect_source(source_dir, source_record)[1] != snapshot:
            raise ValueError('Source changed during preparation')
        evidence = output / 'review-evidence'
        evidence.mkdir()
        shutil.copyfile(source_record, evidence / 'source-record.json')
        shutil.copyfile(Path(review_dir) / 'render-manifest.json', evidence / 'render-manifest.json')
        shutil.copyfile(review_record, evidence / 'technical-review.json')
        for sheet in render['sheets']:
            shutil.copyfile(Path(review_dir) / sheet['file'], evidence / sheet['file'])
        metadata = []
        for path in sorted((output / 'instances').glob('*.dcm')):
            ds = pydicom.dcmread(path)
            del ds.PixelData
            metadata.append(ds.to_json_dict())
        geometry = validate_series(SimpleNamespace(allow_pixel_read=False), metadata,
            manifest['study_uid'], manifest['series_uid'], [r['derived_sop_uid'] for r in manifest['instances']])
        report = dict(format_version=2, status='prepared_and_verified', profile=manifest['profile'],
            instance_count=manifest['instance_count'], public_source_record_sha256=snapshot['source_record_sha256'],
            collection_doi=provenance['collection_doi'], license_url=LICENSE, geometry=geometry['geometry'],
            pixels_preserved=True, clinical_deidentification_certified=False, pacs_imported=False,
            pixel_review_type=review['scope'], ai_activation=False,
            review_evidence_sha256={p.name: sha(p.read_bytes()) for p in evidence.iterdir()})
        validate_prepared_review(output, manifest, report)
        write_json(output / 'preparation-report.json', report)
        return report
    except Exception:
        (output / 'FAILED.txt').write_text('Preparation review failed; preserve for diagnosis.', encoding='utf-8')
        raise
