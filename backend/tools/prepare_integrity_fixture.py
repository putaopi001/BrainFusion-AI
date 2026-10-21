"""Copy authentic public-case artifacts into an owned snapshot for drift checks.

This clones a historical inference for engineering integrity testing, not a new
inference or an additional independent patient. Original files are read-only.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def owned(root, path):
    path = Path(path).resolve()
    path.relative_to(root / 'e2-fixture')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--action', choices=['prepare', 'sequence-change', 'mask-change', 'mask-missing', 'restore'], required=True)
    parser.add_argument('--source-features', type=Path)
    parser.add_argument('--source-case', type=int, default=17)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    root.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    manifest = root / 'fixture.json'
    if args.action != 'prepare':
        fixture = json.loads(manifest.read_text(encoding='utf-8'))
        import nibabel as nib
        import numpy as np
        if args.action == 'restore':
            for key, path in {**fixture['sequences'], 'mask': fixture['mask']}.items():
                shutil.copy2(owned(root, fixture['originals'][key]), owned(root, path))
        elif args.action == 'mask-missing':
            mask = owned(root, fixture['mask'])
            preserved = owned(root, root / 'e2-fixture' / ('preserved_missing_' + uuid4().hex + '.nii.gz'))
            mask.rename(preserved)
        else:
            path = owned(root, fixture['sequences']['t1c'] if args.action == 'sequence-change' else fixture['mask'])
            image = nib.load(path)
            data = np.asarray(image.dataobj).copy()
            data.flat[0] = 1 if args.action == 'mask-change' else float(data.flat[0]) + 123
            nib.save(nib.Nifti1Image(data, image.affine, image.header), path)
        print(json.dumps({'action': args.action, 'owned_artifacts_only': True}))
        return
    if manifest.exists() or (root / 'e2-fixture').exists() or (root / 'feature_jobs').exists():
        raise ValueError('Use a fresh fixture root; never overwrite an earlier attempt')
    db_path = (root / 'database-backup/restored-validation.db').resolve(strict=True)
    os.environ['DATABASE_URL'] = 'sqlite:///' + db_path.as_posix()
    os.environ['FEATURE_JOBS_DIR'] = str(root / 'feature_jobs')
    from app.database import SessionLocal
    from app.models.patient import Patient  # Register relationships.
    from app.models.case import Case
    from app.models.mri import MRI
    from app.models.analysis_run import AnalysisRun
    from app.models.report import Report
    from app.services import case_research_input
    from app.research.dataset import sha256
    from app.services.artifact_integrity import analysis_problem
    with SessionLocal() as db:
        source_case = db.get(Case, args.source_case)
        source_mri = db.query(MRI).filter_by(case_id=args.source_case).order_by(MRI.id.desc()).first()
        source_run = db.get(AnalysisRun, source_mri.analysis_run_id)
        assert not analysis_problem(source_mri, source_run), 'Source is not a current authentic result'
        source_result = json.loads(source_run.result_json)
        source_paths = json.loads(source_mri.sequences_json)
        size = sum(Path(path).stat().st_size for path in source_paths.values()) + Path(source_mri.segmentation_path).stat().st_size
        if shutil.disk_usage(root).free < size * 2 + 50 * 1024**2:
            raise ValueError('Insufficient disk space for owned copies plus restore originals')
        directory = root / 'e2-fixture'; originals = directory / 'originals'; originals.mkdir(parents=True)
        copied, original_paths = {}, {}
        for key, source in {**source_paths, 'mask': source_mri.segmentation_path}.items():
            path = directory / (key + '.nii.gz')
            shutil.copy2(source, path); shutil.copy2(source, originals / path.name)
            copied[key], original_paths[key] = str(path), str(originals / path.name)
            assert sha256(path) == sha256(source)
        shutil.copytree(args.source_features.resolve(strict=True), root / 'feature_jobs')
        candidates = list((args.source_features / str(args.source_case) / source_run.id).glob('*/state.json'))
        source_state_path = max(candidates, key=lambda p: json.loads(p.read_text(encoding='utf-8'))['updated_utc'])
        state = json.loads(source_state_path.read_text(encoding='utf-8'))
        assert state['state'] == 'succeeded' and state['result']
        case = Case(patient_id=source_case.patient_id, description='ENGINEERING COPY of public case17 historical inference; not new inference/patient', status='analyzed')
        db.add(case); db.flush()
        run_id, job_id = uuid4().hex, uuid4().hex
        sequences = {key: copied[key] for key in source_paths}
        mri = MRI(case_id=case.id, filename='ENGINEERING copied public four-sequence result', filepath=copied['t2f'],
                  web_path=source_mri.web_path, sequences_json=json.dumps(sequences), segmentation_path=copied['mask'],
                  segmentation_source='model', analysis_run_id=run_id, status='analyzed', doctor_verified=False)
        db.add(mri); db.flush()
        result = {**source_result, 'mask_path': copied['mask'], 'source_analysis_run_id': source_run.id,
                  'engineering_copy': True}
        request = json.loads(source_run.request_json); request.update(sequences=sequences, output_dir=str(directory))
        db.add(AnalysisRun(id=run_id, case_id=case.id, mri_id=mri.id, state='succeeded',
                          request_json=json.dumps(request), result_json=json.dumps(result),
                          created_time=source_run.created_time, finished_time=source_run.finished_time))
        summary = ['ENGINEERING historical result copy; no new inference.', 'Source analysis: ' + source_run.id,
                   'Analysis version: ' + run_id, 'Volumes (mL): ' + json.dumps(result['volumes_ml'])]
        db.add(Report(case_id=case.id, analysis_run_id=run_id, risk_level='unavailable',
                      summary=json.dumps(summary), recommendation='["Engineering integrity validation only."]'))
        db.commit()
        clinical = case_research_input.update(case.id, state['clinical_input']['age'], state['clinical_input']['female'], db)
        feature_request = json.loads((source_state_path.parent / 'request.json').read_text(encoding='utf-8'))
        feature_request.update(sequences=sequences, mask_path=copied['mask'], clinical_input_version=clinical['version'], clinical_input_source=clinical['source'])
        cache_key = hashlib.sha256(json.dumps(feature_request, sort_keys=True).encode()).hexdigest()
        state.update(id=job_id, case_id=case.id, analysis_run_id=run_id, clinical_input_version=clinical['version'],
                     clinical_input_source=clinical['source'], cache_key=cache_key, cache_hit=False,
                     source_feature_task=state['id'], engineering_copy=True)
        target_job = root / 'feature_jobs' / str(case.id) / run_id / job_id; target_job.mkdir(parents=True)
        (target_job / 'request.json').write_text(json.dumps(feature_request, indent=2), encoding='utf-8')
        (target_job / 'state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        assert not analysis_problem(mri, db.get(AnalysisRun, run_id))
        fixture = {'case_id': case.id, 'analysis_run_id': run_id, 'feature_id': job_id,
                   'source_case': args.source_case, 'source_analysis': source_run.id, 'source_feature': source_state_path.parent.name,
                   'sequences': sequences, 'mask': copied['mask'], 'originals': original_paths,
                   'copy_bytes': size * 2, 'created_utc': datetime.now(timezone.utc).isoformat(),
                   'scope': 'Owned copied authentic historical outputs for drift validation, not a new inference or independent patient; source download link keeps public original provenance.'}
        manifest.write_text(json.dumps(fixture, indent=2), encoding='utf-8')
        print(json.dumps({key: fixture[key] for key in ['case_id', 'analysis_run_id', 'feature_id', 'copy_bytes', 'scope']}))


if __name__ == '__main__':
    main()
