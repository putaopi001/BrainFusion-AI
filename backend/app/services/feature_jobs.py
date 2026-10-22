"""Versioned CPU extraction jobs; research transfer never edits clinical reports."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import threading
from uuid import uuid4
from fastapi import HTTPException

from app.core.config import settings
from app.database import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.feature import MRIFeature
from app.models.mri import MRI
from app.research.dataset import sha256
from app.research.feature_contract import PROTOCOL, selected_features, contract_hash, feature_matrix
from app.services.research_service import current_bundle
from app.services.study_validation import validate_sequences
from app.services import case_research_input
from app.services.worker_error import worker_failure
from app.services.artifact_integrity import feature_input_problem, analysis_problem

BACKEND = Path(__file__).resolve().parents[2]
SCRIPT = BACKEND / 'tools/extract_selected_radiomics.py'
executor = ThreadPoolExecutor(max_workers=1)
lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def save(directory, state):
    directory.resolve().relative_to(Path(settings.FEATURE_JOBS_DIR).resolve())
    state['updated_utc'] = now()
    temporary = directory / 'state.tmp'
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(directory / 'state.json')


def latest_mri(db, case_id):
    mri = db.query(MRI).filter(MRI.case_id == case_id).order_by(MRI.id.desc()).first()
    if mri is None:
        raise HTTPException(404, 'MRI not found')
    return mri


def states(case_id, analysis_id):
    root = Path(settings.FEATURE_JOBS_DIR) / str(case_id) / analysis_id
    result = [(path.parent, json.loads(path.read_text(encoding='utf-8'))) for path in root.glob('*/state.json')]
    return sorted(result, key=lambda item: item[1]['updated_utc'], reverse=True)


def persisted_feature_result(db, case_id, mri, state):
    """Resolve a job-linked SQL feature record as the API source of truth."""
    result = state.get('result')
    record_id = result.get('feature_record_id') if isinstance(result, dict) else None
    if record_id is None:
        # Preserve read access to historical file-backed jobs that predate SQL indexing.
        return state
    record = db.get(MRIFeature, record_id)
    if record is None or record.mri_id != mri.id:
        return {**state, 'result': None, 'stale': True,
                'stale_reason': 'The linked SQL feature record is unavailable for this MRI.'}
    try:
        data = json.loads(record.feature_data)
        expected_type = f'research_radiomics:{mri.analysis_run_id}:{state["id"]}'
        if (record.feature_type != expected_type or data.get('case_id') != case_id
                or data.get('mri_id') != mri.id
                or data.get('analysis_run_id') != mri.analysis_run_id
                or data.get('job_id') != state['id']
                or data.get('research_run_id') != state.get('research_run_id')
                or data.get('contract_sha256') != result.get('contract_sha256')
                or not isinstance(data.get('features'), dict)):
            raise ValueError('SQL feature lineage mismatch')
    except (ValueError, TypeError, KeyError):
        return {**state, 'result': None, 'stale': True,
                'stale_reason': 'The linked SQL feature record failed lineage validation.'}
    resolved = {**result,
                'selected_features': data['features'],
                'protocol': data.get('protocol'),
                'versions': data.get('versions'),
                'input_sha256': data.get('input_sha256'),
                'mask_sha256': data.get('mask_sha256'),
                'region_voxel_counts': data.get('region_voxel_counts'),
                'extraction_seconds': data.get('extraction_seconds'),
                'feature_record_id': record.id}
    return {**state, 'result': resolved}


def current(case_id, db):
    mri = latest_mri(db, case_id)
    items = states(case_id, mri.analysis_run_id) if mri.analysis_run_id else []
    if not items:
        return None
    directory, state = items[0]
    if state.get('state') == 'succeeded' and isinstance(state.get('result'), dict) and not state['result'].get('protocol'):
        try:
            protocol = json.loads((directory / 'request.json').read_text(encoding='utf-8')).get('protocol')
            if isinstance(protocol, dict) and protocol:
                state = {**state, 'result': {**state['result'], 'protocol': protocol}}
        except (OSError, ValueError, TypeError):
            pass
    clinical = case_research_input.current(case_id, db)
    if not case_research_input.matches(state, clinical):
        # Presentation only: keep the historical state/result file intact.
        return {**state, 'result': None, 'stale': True,
                'stale_reason': 'Clinical input changed; recompute for the current saved input version.',
                'current_clinical_input_version': clinical['version']}
    if state['state'] == 'succeeded' and state.get('result'):
        try:
            summary, _ = current_bundle()
            if state.get('research_run_id') != summary['run_id']:
                return {**state, 'result': None, 'stale': True,
                        'stale_reason': 'Research model version changed; recompute the current result.'}
        except (OSError, ImportError, ValueError, KeyError, TypeError) as error:
            return {**state, 'result': None, 'stale': True,
                    'stale_reason': 'Research model unavailable or invalid: ' + str(error)}
        run = db.get(AnalysisRun, mri.analysis_run_id) if mri.analysis_run_id else None
        problem = analysis_problem(mri, run) or feature_input_problem(mri, state['result'])
        if problem:
            return {**state, 'result': None, 'stale': True, 'stale_reason': problem}
    state = persisted_feature_result(db, case_id, mri, state)
    return {**state, 'stale': state.get('stale', False)}


def compatibility(summary, bundle):
    worker = Path(settings.RADIOMICS_PYTHON)
    if not worker.is_file():
        raise FileNotFoundError('Isolated radiomics worker is unavailable')
    audit = json.loads(Path(settings.RADIOMICS_COMPATIBILITY).read_text(encoding='utf-8'))
    expected = {'research_run_id': summary['run_id'], 'model_sha256': summary['artifact_sha256']['models.joblib'],
                'data_sha256': bundle['data_sha256'], 'contract_sha256': contract_hash(bundle),
                'worker_script_sha256': sha256(SCRIPT),
                'contract_script_sha256': sha256(BACKEND / 'app/research/feature_contract.py'),
                'worker_provenance_sha256': sha256(worker.parent / 'source.json')}
    if audit['status'] != 'passed' or any(audit[key] != value for key, value in expected.items()):
        raise ValueError('Feature reproduction gate is stale or failed; rerun verify_feature_extraction.py')
    return expected


def persist_feature_record(case_id, mri_id, analysis_run_id, job_id, result):
    """Idempotently index successful research features in the existing MRI feature table."""
    feature_type = f'research_radiomics:{analysis_run_id}:{job_id}'
    record_data = {
        'schema': 'research-radiomics-v1', 'case_id': case_id, 'mri_id': mri_id,
        'analysis_run_id': analysis_run_id, 'job_id': job_id,
        'research_run_id': result['research_run_id'], 'feature_source': result['feature_source'],
        'contract_sha256': result['contract_sha256'], 'protocol': result['protocol'],
        'versions': result['versions'], 'input_sha256': result['input_sha256'],
        'mask_sha256': result['mask_sha256'], 'region_voxel_counts': result['region_voxel_counts'],
        'features': result['selected_features'], 'extraction_seconds': result['extraction_seconds'],
    }
    with SessionLocal() as db:
        mri = db.get(MRI, mri_id)
        if mri is None or mri.case_id != case_id or mri.analysis_run_id != analysis_run_id:
            raise ValueError('MRI lineage changed before radiomics persistence')
        record = db.query(MRIFeature).filter_by(mri_id=mri_id, feature_type=feature_type).first()
        if record is None:
            record = MRIFeature(mri_id=mri_id, feature_type=feature_type,
                                feature_data=json.dumps(record_data, sort_keys=True, allow_nan=False))
            db.add(record)
            db.commit()
            db.refresh(record)
        return record.id


def submit(case_id, age, female, db):
    with lock:
        clinical = case_research_input.current(case_id, db)
        if not clinical['available'] or clinical['age'] != age or clinical['female'] != female:
            raise HTTPException(409, 'Clinical input must match the current saved case input')
        mri = latest_mri(db, case_id)
        run = db.get(AnalysisRun, mri.analysis_run_id) if mri.analysis_run_id else None
        if run is None or run.state != 'succeeded' or mri.segmentation_source != 'model':
            raise HTTPException(409, 'A current successful model segmentation is required')
        if run.case_id != case_id or run.mri_id != mri.id:
            raise HTTPException(409, 'Analysis does not belong to this case MRI')
        summary, bundle = current_bundle()
        gate = compatibility(summary, bundle)
        result = json.loads(run.result_json)
        sequences = json.loads(mri.sequences_json)
        validate_sequences(sequences)
        if str(Path(mri.segmentation_path).resolve()) != str(Path(result['mask_path']).resolve()) or sha256(result['mask_path']) != result['mask_sha256']:
            raise ValueError('Current mask differs from the successful analysis')
        inputs = {key: sha256(path) for key, path in sequences.items()}
        if inputs != result['input_sha256']:
            raise ValueError('MRI inputs changed after segmentation')
        request = {'sequences': sequences, 'mask_path': result['mask_path'], 'protocol': PROTOCOL,
                   'selected_features': selected_features(bundle), 'contract_sha256': gate['contract_sha256'],
                   'feature_source': 'automatic model mask', 'age': age, 'female': female,
                   'research_run_id': summary['run_id'], 'model_sha256': gate['model_sha256'],
                   'expected_input_sha256': inputs, 'expected_mask_sha256': result['mask_sha256'], 'gate': gate}
        request['clinical_input_version'] = clinical['version']
        request['clinical_input_source'] = clinical['source']
        cache_key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        items = states(case_id, run.id)
        if any(state['state'] in ('queued', 'running') for _, state in items):
            raise HTTPException(409, 'A feature extraction is active for this analysis')
        for directory, state in items:
            if state.get('cache_key') == cache_key and state['state'] == 'succeeded':
                state['cache_hit'] = True
                save(directory, state)
                return state
        job_id = uuid4().hex
        directory = Path(settings.FEATURE_JOBS_DIR) / str(case_id) / run.id / job_id
        directory.mkdir(parents=True)
        (directory / 'request.json').write_text(json.dumps(request, indent=2), encoding='utf-8')
        state = {'id': job_id, 'case_id': case_id, 'analysis_run_id': run.id, 'research_run_id': summary['run_id'],
                 'state': 'queued', 'created_utc': now(), 'cache_key': cache_key, 'cache_hit': False,
                 'clinical_input': {'age': age, 'female': female}, 'result': None, 'error': None}
        state['clinical_input_version'] = clinical['version']
        state['clinical_input_source'] = clinical['source']
        state['patient_id'] = clinical['patient_id']
        save(directory, state)
        executor.submit(execute, directory)
        return state


def execute(directory):
    state = json.loads((directory / 'state.json').read_text(encoding='utf-8'))
    try:
        state['state'] = 'running'
        with lock:
            save(directory, state)
        request = json.loads((directory / 'request.json').read_text(encoding='utf-8'))
        with (directory / 'worker.log').open('w', encoding='utf-8') as log:
            completed = subprocess.run([settings.RADIOMICS_PYTHON, '-B', str(SCRIPT), '--request', str(directory / 'request.json'),
                                        '--output', str(directory / 'features.json')], cwd=BACKEND, stdout=log, stderr=log, timeout=180)
        if completed.returncode:
            raise ValueError(worker_failure(directory / 'worker.log', 'Feature worker'))
        extraction = json.loads((directory / 'features.json').read_text(encoding='utf-8'))
        summary, bundle = current_bundle()
        gate = compatibility(summary, bundle)
        if gate != request['gate'] or extraction['contract_sha256'] != gate['contract_sha256']:
            raise ValueError('Research model or extraction contract changed during job')
        if extraction['input_sha256'] != request['expected_input_sha256'] or extraction['mask_sha256'] != request['expected_mask_sha256']:
            raise ValueError('Feature inputs changed during extraction')
        if not any(value is not None for value in extraction['features'].values()):
            raise ValueError('No usable selected features in the predicted regions')
        matrix = feature_matrix(bundle, extraction['features'])
        c = float(bundle['models']['clinical'].predict_proba([[request['age'], int(request['female'])]])[0, 1])
        r = float(bundle['models']['reference_mask_radiomics'].predict_proba(matrix)[0, 1])
        with SessionLocal() as db:
            mri = latest_mri(db, state['case_id'])
            if mri.analysis_run_id != state['analysis_run_id'] or mri.segmentation_source != 'model' or mri.segmentation_path != request['mask_path']:
                raise ValueError('Current MRI or segmentation version changed during extraction')
            if not case_research_input.matches(state, case_research_input.current(state['case_id'], db)):
                raise ValueError('Clinical input version changed during extraction; please retry')
            mri_id = mri.id
        feature_result = {'target': 'idh1/2=1', 'feature_source': 'automatic model mask', 'device': 'cpu',
                          'probabilities': {'clinical': c, 'automatic_mask_radiomics': r, 'average': (c + r) / 2,
                                            'fixed': .6 * c + .4 * r, 'validation_topsis': float(c * bundle['topsis_weights'][0] + r * bundle['topsis_weights'][1])},
                          'contract_sha256': gate['contract_sha256'], 'selected_features': extraction['features'],
                          'region_voxel_counts': extraction['region_voxel_counts'], 'versions': extraction['versions'],
                          'protocol': request['protocol'], 'input_sha256': extraction['input_sha256'],
                          'mask_sha256': extraction['mask_sha256'], 'extraction_seconds': extraction['seconds']}
        feature_result['feature_record_id'] = persist_feature_record(
            state['case_id'], mri_id, state['analysis_run_id'], state['id'], feature_result)
        state['state'] = 'succeeded'
        feature_result['disclaimer'] = '工程迁移实验：使用自动掩膜，但分类模型仍在参考掩膜特征上拟合；尚未重拟合、校准或独立评价，不能诊断。'
        state['result'] = feature_result
    except Exception as error:
        state['state'], state['error'], state['result'] = 'failed', str(error), None
    state['finished_utc'] = now()
    with lock:
        save(directory, state)


def recover_interrupted():
    for path in Path(settings.FEATURE_JOBS_DIR).glob('*/*/*/state.json'):
        state = json.loads(path.read_text(encoding='utf-8'))
        if state['state'] in ('queued', 'running'):
            state['state'], state['error'] = 'failed', 'Service restarted; retry the feature job'
            state['result'], state['finished_utc'] = None, now()
            save(path.parent, state)
