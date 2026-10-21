"""Build a bounded source/official-lock handoff; no binary/data redistribution."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.bootstrap_cpu_delivery import digest, read, validate_lock, verify_bundle
from tools.prepare_source_delivery import scan, build


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--accepted-cpu-run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=args.project.resolve(strict=True)
    root.relative_to(Path('E:/').resolve())
    accepted=args.accepted_cpu_run.resolve(strict=True)
    value=read(accepted/'final-validation.json');live=read(accepted/'live-final-validation.json')
    plan=read(accepted/'cpu-plan/plan.json');installed=read(accepted/'cpu-install/validation.json')
    if value['status']!='accepted_independent_windows_cpu_candidate_not_live_deployment' or live['status']!='passed_windows_cpu_live_trial_and_cuda_rollback' or not value['final_installed_metadata_matches_plan'] or digest(accepted/'cpu-plan/plan.json')!=installed['plan_sha256']:
        raise ValueError('Accepted CPU source/model/live gates required')
    lock=dict(python=plan['python'],platform=plan['platform'],packages=plan['packages'],conda_bootstrap=plan['conda_packages'],excluded_optional=plan['excluded_optional'],prior_source_plan_sha256=digest(accepted/'cpu-plan/plan.json'),scope='Independent Windows CPU main interpreter only; feature-worker setup, external data/models, Node dependencies and runtime artifacts are not embedded. Legacy CUDA installation provenance remains unknown.')
    validate_lock(lock)
    output=args.output.resolve();output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(parents=True,exist_ok=False)
    source=output/'source';source.mkdir()
    audit=scan(root)
    (source/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    source_result=build(root,source,audit)
    (source/'validation.json').write_text(json.dumps(source_result,indent=2),encoding='utf-8')
    payload={
        'bootstrap_cpu_delivery.py':(root/'backend/tools/bootstrap_cpu_delivery.py').read_bytes(),
        'brainfusion-source-candidate.zip':(source/'brainfusion-source-candidate.zip').read_bytes(),
        'source-audit.json':(source/'audit.json').read_bytes(),
        'cpu-source-lock.json':json.dumps(lock,ensure_ascii=False,indent=2).encode(),
        'main-conda-explicit.txt':('@EXPLICIT\n'+'\n'.join(p['url']+'#sha256:'+p['sha256'] for p in lock['conda_bootstrap'])+'\n').encode(),
        'CPU_DELIVERY_BOOTSTRAP.md':(root/'docs/CPU_DELIVERY_BOOTSTRAP.md').read_bytes(),
        'accepted-cpu-install-model-validation.json':(accepted/'final-validation.json').read_bytes(),
        'accepted-cpu-live-validation.json':(accepted/'live-final-validation.json').read_bytes(),
    }
    entries=[dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for name,raw in sorted(payload.items())]
    manifest=dict(format_version=1,created_utc=datetime.now(timezone.utc).isoformat(),files=entries,source_files=len(audit['files']),scope='Internal source/locks/evidence only, not a model/data/binary/Node dependency archive, new-machine acceptance or redistribution license certification',accepted_model_scope='Prior single-case CPU reproduction and five-development-patient probability reproduction, not scientific accuracy')
    archive=output/'brainfusion-cpu-source-locks.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as stream:
        for name,raw in payload.items():stream.writestr(name,raw)
        stream.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode())
    archive_sha=digest(archive)
    verify_bundle(archive,archive_sha)
    result=dict(status='verified_source_lock_bundle_not_new_machine_deployment',bundle_path=str(archive),bundle_sha256=archive_sha,bundle_bytes=archive.stat().st_size,source_files=len(audit['files']),source_bytes=audit['total_bytes'],source_zip_sha256=source_result['archive_sha256'],payload_files=len(payload),no_data_models_environment_binaries_or_node_dependencies=True,accepted_previous_run=str(accepted),current_source_comparison_pending_after_tests=True)
    (output/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
