"""Capture minimal read-only lineage evidence for engineering figures, not statistics."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.request import urlopen

PROJECT = Path(__file__).resolve().parents[2]
SOURCES = [
    'backend/app/services/analysis_jobs.py', 'backend/app/services/feature_jobs.py',
    'backend/app/services/artifact_integrity.py', 'backend/app/services/current_report.py',
    'backend/app/services/case_research_input.py', 'backend/app/research/feature_contract.py',
    'backend/app/ai/imaging/monai_segmenter.py', 'backend/app/api/analysis.py',
    'backend/app/api/cases.py', 'backend/app/api/reports.py',
    'backend/app/models/mri.py', 'backend/app/models/report.py',
    'backend/app/models/case_research_input.py', 'frontend/src/views/Report.vue',
]


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def representative_reading(mask_path):
    # Match the existing viewer's LPS_DISPLAY_V1 transform, without resampling.
    import nibabel as nib
    import numpy as np
    image = nib.load(mask_path)
    transform = nib.orientations.ornt_transform(nib.orientations.io_orientation(image.affine), nib.orientations.axcodes2ornt(('L', 'P', 'S')))
    mask = image.as_reoriented(transform).get_fdata(dtype=np.float32).transpose(2, 1, 0)
    voxels = np.argwhere(mask > 0)
    assert len(voxels) > 0, 'An empty predicted mask has no positive overlay demonstration'
    axial = int(np.argmax(np.bincount(voxels[:, 0], minlength=mask.shape[0])))
    candidates = voxels[voxels[:, 0] == axial]
    point = candidates[np.argmin(np.sum((candidates - candidates.mean(axis=0)) ** 2, axis=1))]
    indices = dict(zip(['axial', 'coronal', 'sagittal'], map(int, point)))
    counts = {view: int(np.count_nonzero(np.take(mask, indices[view], axis=axis))) for axis, view in enumerate(indices)}
    assert all(value > 0 for value in counts.values())
    return dict(coordinate_contract='LPS_DISPLAY_V1', indices_zero_based=indices, positive_mask_voxels_by_plane=counts,
                selection_rule='Maximum predicted-WT axial area; nearest positive voxel to that plane centroid sets other planes. Deterministic illustrative display, not a segmentation-quality evaluation; no MRI/mask modification.')


def database_signature(path):
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as database:
        names = [row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        result = {}
        for name in names:
            rows = database.execute('SELECT * FROM "' + name.replace('"', '""') + '" ORDER BY 1').fetchall()
            result[name] = dict(rows=len(rows), sha256=hashlib.sha256(json.dumps(rows, ensure_ascii=False, default=str).encode()).hexdigest())
        assert database.execute("SELECT count(*) FROM analysis_runs WHERE state IN ('queued','running')").fetchone()[0] == 0
    return result


def api(base, path):
    with urlopen(base.rstrip('/') + path, timeout=30) as response:
        assert response.status == 200
        return json.load(response)['data']


def capture(config, base, case_id):
    raw = json.loads(config.read_text(encoding='utf-8'))['paths']
    paths = {key: (Path(value) if Path(value).is_absolute() else config.parent / value).resolve() for key, value in raw.items()}
    before = database_signature(paths['DATABASE_PATH'])
    detail = api(base, f'/cases/{case_id}/detail')
    clinical = api(base, f'/research/cases/{case_id}/clinical-input')
    feature = api(base, f'/research/cases/{case_id}/features')
    report = api(base, f'/reports/{case_id}')
    analysis = detail['analysis']
    assert analysis['state'] == feature['state'] == 'succeeded'
    assert not analysis['stale'] and not feature['stale']
    assert analysis['id'] == feature['analysis_run_id'] == report['analysis_run_id']
    assert clinical['version'] == feature['clinical_input_version']
    assert feature['clinical_input'] == {'age': clinical['age'], 'female': clinical['female']}
    assert detail['mri']['doctor_verified'] and detail['mri']['verified_run_id'] == analysis['id']
    result = analysis['result']
    job_directory = paths['FEATURE_JOBS_DIR'] / str(case_id) / analysis['id'] / feature['id']
    request = json.loads((job_directory / 'request.json').read_text(encoding='utf-8'))
    assert request['expected_input_sha256'] == result['input_sha256'] == feature['result']['input_sha256']
    assert request['expected_mask_sha256'] == result['mask_sha256'] == feature['result']['mask_sha256']
    assert {key: digest(Path(path)) for key, path in request['sequences'].items()} == result['input_sha256']
    assert digest(Path(request['mask_path'])) == result['mask_sha256']
    gate = json.loads(paths['RADIOMICS_COMPATIBILITY'].read_text(encoding='utf-8'))
    assert gate['status'] == 'passed' and request['gate']['worker_provenance_sha256'] == digest(paths['RADIOMICS_PYTHON'].parent / 'source.json')
    assert feature['result']['contract_sha256'] == request['contract_sha256'] == gate['contract_sha256']
    assert request['model_sha256'] == gate['model_sha256']
    assert len(feature['result']['selected_features']) == len(request['selected_features']) == 20
    assert feature['result']['feature_source'] == 'automatic model mask' and feature['result']['device'] == 'cpu'
    assert feature['result']['versions']['python'] == '3.11.17'
    source = json.loads((paths['MODEL_DIR'] / 'source.json').read_text(encoding='utf-8'))
    assert source['sha'] == result['revision']
    assert digest(paths['MODEL_DIR'] / 'models/model.pt') == result['checkpoint_sha256']
    for relative in ['backend/app/services/analysis_jobs.py', 'backend/app/services/feature_jobs.py']:
        assert 'ThreadPoolExecutor(max_workers=1)' in (PROJECT / relative).read_text(encoding='utf-8')
    after = database_signature(paths['DATABASE_PATH'])
    assert before == after
    return dict(status='passed', captured_utc=datetime.now(timezone.utc).isoformat(),
                scope='Existing public engineering case, not a new patient, segmentation, extraction, experiment, PDF report, or statistical sample.',
                service_urls=dict(api=base, frontend='http://127.0.0.1:5179'),
                database_table_signatures=before, database_unchanged_by_capture=True,
                public_case=dict(case_id=case_id, analysis_id=analysis['id'], feature_job_id=feature['id'],
                                 clinical_input_version=clinical['version'], clinical_input=feature['clinical_input'],
                                 research_run_id=feature['research_run_id'], confirmed_analysis_id=detail['mri']['verified_run_id']),
                representative_reading=representative_reading(request['mask_path']),
                segmentation=dict(model=result['model'], revision=result['revision'], checkpoint_sha256=result['checkpoint_sha256'],
                                  input_sha256=result['input_sha256'], mask_sha256=result['mask_sha256']),
                research=dict(target=feature['result']['target'], feature_source=feature['result']['feature_source'],
                              device='cpu', selected_feature_count=20, worker_versions=feature['result']['versions'],
                              contract_sha256=gate['contract_sha256'], model_sha256=gate['model_sha256'],
                              worker_provenance_sha256=gate['worker_provenance_sha256'],
                              probabilities=feature['result']['probabilities'],
                              limitation=feature['result']['disclaimer']),
                implementation_sources=[dict(path=relative, sha256=digest(PROJECT / relative)) for relative in SOURCES],
                graph_contract=dict(serial_local_executors=2, cpu_feature_subprocess=True, pdf_export='frontend html2pdf.js with pre/post-render current-version checks',
                                    research_written_to_diagnostic_report=False, doctor_opinion='independent case opinion; not feature output',
                                    geometry='requires same input grid; no automatic registration', docker='not validated'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-config', type=Path, required=True)
    parser.add_argument('--api', default='http://127.0.0.1:8012')
    parser.add_argument('--case-id', type=int, default=17)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    evidence = capture(args.runtime_config.resolve(strict=True), args.api, args.case_id)
    (output / 'engineering-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(status=evidence['status'], source_files=len(SOURCES), database_unchanged=True, case_id=args.case_id)))


if __name__ == '__main__':
    main()
