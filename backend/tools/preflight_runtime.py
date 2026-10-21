"""Read-only dependency/file/SQLite/lineage preflight, before app import/migration."""
import argparse
import importlib.metadata
import importlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.core.config import settings


def private_runtime_configuration_errors():
    errors = []
    try:
        from app.services.local_auth import accounts
        users, _ = accounts()
        if not any(not user['disabled'] for user in users):
            errors.append('Local review-account configuration has no usable accounts')
    except Exception:
        errors.append('Local review-account configuration is invalid or missing')
    try:
        from app.services.pacs_client import load_config
        load_config()
    except Exception:
        errors.append('Local PACS configuration is invalid or missing')
    return errors


def check():
    errors, warnings, versions = private_runtime_configuration_errors(), [], {}
    for package, module in [('fastapi','fastapi'), ('sqlalchemy','sqlalchemy'), ('numpy','numpy'),
                            ('nibabel','nibabel'), ('SimpleITK','SimpleITK'), ('Pillow','PIL'),
                            ('scipy','scipy'), ('httpx','httpx'), ('pydicom','pydicom'),
                            ('torch','torch'), ('monai','monai'),
                            ('scikit-learn','sklearn'), ('joblib','joblib')]:
        try:
            importlib.import_module(module); versions[package] = importlib.metadata.version(package)
        except Exception as error: errors.append(f'Dependency {package}: {error}')
    configured = {name: str(getattr(settings,name)) for name in ['UPLOAD_DIR','FEATURE_JOBS_DIR','MODEL_DIR',
                   'RESEARCH_DIR','DATASET_DIR','RADIOMICS_COMPATIBILITY','RADIOMICS_PYTHON']}
    for key, value in configured.items():
        path = Path(value)
        if not path.exists(): errors.append(f'Missing {key}: {path}')
        if path.drive and path.drive.upper() != 'E:': errors.append('Runtime path is not on E: ' + key)
    for key in ['UPLOAD_DIR','FEATURE_JOBS_DIR']:
        if not os.access(configured[key], os.W_OK): errors.append('Runtime directory is not writable: ' + key)
    required = [Path(settings.MODEL_DIR) / name for name in ['models/model.pt','configs/inference.json','configs/metadata.json','source.json']]
    required += [Path(settings.DATASET_DIR) / 'downloads' / name for name in ['1_0_clinical_molecular_data.csv','4_radiomics_preop.csv']]
    for path in required:
        if not path.is_file(): errors.append('Required artifact missing: ' + str(path))
    segmentation_model = None
    try:
        from app.research.dataset import sha256
        source = json.loads((Path(settings.MODEL_DIR) / 'source.json').read_text(encoding='utf-8'))
        segmentation_model = {'revision': source.get('sha'), 'source_id': source.get('id'),
                              'weights_sha256': sha256(Path(settings.MODEL_DIR) / 'models/model.pt')}
    except Exception as error: errors.append('Segmentation model provenance: ' + str(error))
    if not (BACKEND.parent / 'frontend/node_modules/vite/bin/vite.js').is_file(): errors.append('Frontend Vite dependency missing')
    research = None
    try:
        from app.services.research_service import current_bundle
        from app.services.feature_jobs import compatibility
        summary, bundle = current_bundle(); research = summary['run_id']
        compatibility(summary, bundle)
    except Exception as error: errors.append('Research model/reproduction gate: ' + str(error))
    worker = None
    if Path(settings.RADIOMICS_PYTHON).is_file():
        code = "import sys,json,numpy,SimpleITK,radiomics;print(json.dumps({'python':sys.version.split()[0],'numpy':numpy.__version__,'radiomics':radiomics.__version__,'SimpleITK':SimpleITK.Version_VersionString()}))"
        try:
            finished = subprocess.run([settings.RADIOMICS_PYTHON,'-B','-c',code], capture_output=True,text=True,timeout=30)
            if finished.returncode: raise ValueError(finished.stderr[-1200:])
            worker = json.loads(finished.stdout)
        except Exception as error: errors.append('Isolated CPU feature worker import: ' + str(error))
    database, checked_models = {}, []
    try:
        if not settings.DATABASE_URL.startswith('sqlite:///'): raise ValueError('Local startup preflight expects explicit SQLite')
        path = Path(settings.DATABASE_URL[len('sqlite:///'):]).resolve()
        if path.drive and path.drive.upper() != 'E:': raise ValueError('Database must stay on E:')
        database['path'] = str(path)
        if path.exists():
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
                db.row_factory = sqlite3.Row
                if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('SQLite integrity failed')
                from app.services.artifact_integrity import analysis_problem
                for row in db.execute("SELECT * FROM mris WHERE segmentation_source='model' AND analysis_run_id IS NOT NULL"):
                    run = db.execute('SELECT * FROM analysis_runs WHERE id=?',(row['analysis_run_id'],)).fetchone()
                    if run and run['state'] == 'succeeded':
                        problem = analysis_problem(SimpleNamespace(**dict(row)),SimpleNamespace(**dict(run)))
                        if problem: errors.append(f'Current model case {row["case_id"]}: {problem}')
                        else: checked_models.append(row['case_id'])
                database['integrity'] = 'ok'
        elif not path.parent.is_dir(): raise ValueError('New database parent directory does not exist')
        else: database['new_database'] = True
    except Exception as error: errors.append('Database preflight: ' + str(error))
    gpu = None
    if 'torch' in versions:
        import torch
        gpu = {'cuda_available': torch.cuda.is_available(), 'cuda_build': torch.version.cuda,
               'budget_mb': settings.GPU_BUDGET_MB, 'no_inference_performed': True}
    if worker and worker['python'].startswith('3.9.'):
        warnings.append('Current archived Python3.9 worker is still in use; E4 supported-environment migration remains outstanding.')
    return {'status': 'passed' if not errors else 'failed', 'errors':errors, 'warnings':warnings,
            'main_python':sys.version.split()[0], 'versions':versions, 'cpu_feature_worker':worker,
            'configured_paths':configured, 'database':database, 'healthy_current_model_cases':checked_models,
            'research_run_id':research, 'segmentation_model':segmentation_model, 'gpu':gpu,
            'scope':'Dependency imports, model/research checksums and gate, all current model file lineage, SQLite integrity and configured files. No app.main import/migration/inference.'}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--strict',action='store_true'); args=parser.parse_args()
    result=check(); print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.strict and result['status'] != 'passed': sys.exit(2)
