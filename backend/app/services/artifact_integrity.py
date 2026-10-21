"""Read-only lineage checks; never rewrite historical successful records."""
import hashlib
import json
import re
from pathlib import Path
from app.research.dataset import sha256
from app.core.storage import is_supported_storage_path


def checked_digest(path):
    # A metadata-keyed digest cache can miss same-size edits with a restored mtime.
    # These checks gate whether model-derived results remain current, so hash bytes on every check.
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise OSError('Artifact is not a regular file')
    return sha256(path)


def analysis_problem(mri, run):
    if (not mri or not run or mri.analysis_run_id != run.id or run.case_id != mri.case_id
            or run.mri_id != mri.id):
        return 'Analysis does not belong to the current case MRI.'
    if run.state != 'succeeded' or mri.segmentation_source != 'model':
        return 'A current successful model analysis is required.'
    try:
        result = json.loads(run.result_json)
        if Path(mri.segmentation_path).resolve() != Path(result['mask_path']).resolve():
            return 'Current mask path no longer belongs to this analysis; rerun analysis.'
        problem = feature_input_problem(mri, result)
        if problem:
            return problem.replace('feature extraction', 'the saved analysis')
    except (OSError, ValueError, KeyError, TypeError) as error:
        return 'Analysis files or lineage are unavailable: ' + str(error)
    return None


def current_analysis(mri, run):
    from app.services.analysis_jobs import serialize
    if run is None:
        return None
    try:
        data = serialize(run)
    except (ValueError, TypeError):
        data = {'id': run.id, 'case_id': run.case_id, 'state': run.state, 'result': None,
                'error': 'Analysis result metadata is invalid.'}
    problem = analysis_problem(mri, run) if run.state == 'succeeded' else None
    if run.case_id != mri.case_id or run.mri_id != mri.id:
        problem = 'Analysis does not belong to the current case MRI.'
    return {**data, 'stale': bool(problem), 'stale_reason': problem, 'current': not bool(problem),
            'result': None if problem else data['result'], 'error': problem or data['error']}


def activated_conversion_input_hashes(mri, paths):
    """Require activated DICOM inputs to remain byte-identical to reviewed NIfTI outputs."""
    if getattr(mri, 'input_source', None) != 'dicom-conversion':
        return None
    try:
        provenance = json.loads(mri.source_provenance_json or '')
        roles = provenance.get('roles')
        required = {'t1c', 't1n', 't2w', 't2f'}
        if (provenance.get('format') != 'dicom-mri-input-lineage-v1'
                or not isinstance(roles, dict) or set(roles) != required
                or not isinstance(paths, dict) or set(paths) != required):
            raise ValueError()
        expected = {}
        for role in sorted(required):
            digest = roles[role].get('nifti_sha256') if isinstance(roles[role], dict) else None
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise ValueError()
            path = Path(paths[role]).resolve(strict=True)
            if not is_supported_storage_path(path) or not path.is_file():
                raise ValueError()
            observed = hashlib.sha256()
            with path.open('rb') as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b''):
                    observed.update(block)
            if observed.hexdigest() != digest:
                raise ValueError()
            expected[role] = digest
        return expected
    except Exception:
        raise ValueError('Activated DICOM conversion inputs no longer match their reviewed hashes; review and reactivate the source.') from None


def feature_input_problem(mri, result):
    try:
        paths = json.loads(mri.sequences_json)
        expected = result['input_sha256']
        if not isinstance(paths, dict) or set(paths) != {'t1c', 't1n', 't2w', 't2f'} or set(expected) != set(paths):
            return 'MRI sequence lineage is incomplete; recompute after a valid analysis.'
        if mri.segmentation_source != 'model':
            return 'Current segmentation is not a model result.'
        if checked_digest(mri.segmentation_path) != result['mask_sha256']:
            return 'Segmentation file changed after feature extraction; rerun analysis and features.'
        for key, path in paths.items():
            if checked_digest(path) != expected[key]:
                return f'MRI sequence {key} changed after feature extraction; rerun analysis and features.'
    except (OSError, ValueError, KeyError, TypeError) as error:
        return 'Feature input files or lineage are unavailable: ' + str(error)
    return None

