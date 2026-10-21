"""Synthetic engineering-only mechanics tests; never real DICOM/clinical evidence."""
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.database import SessionLocal
from app.main import app
from app.models.analysis_run import AnalysisRun
from app.models.annotation import MRIAnnotation
from app.models.case import Case
from app.models.mri import MRI
from app.models.patient import Patient
from app.models.report import Report
from app.services.local_auth import require_doctor
from test_dicom_conversion_registry import registered


def _make_approval(item, monkeypatch):
    import app.api.pacs as api
    from app.services import dicom_conversion_role_review as review
    from app.services.dicom_conversion_registry import load_index
    entry=load_index()[0]; view=review.describe(entry)
    identity={'format':'local-account-review-v1','id':'d'*32,'username':'synthetic-activation-test',
              'display_name':'SYNTHETIC test only','role':'doctor','authentication_method':'test_dependency_override',
              'professional_credential_verified':False}
    source={'status':'matched_at_check','data_role':'dicom-metadata-snapshot','plan_revision':view['plan_revision'],
            'report_sha256':entry.report_sha256,'archive_id':entry.archive_id,
            'archive_fingerprint':entry.archive_fingerprint,'completed_utc':'2026-10-17T00:00:00+00:00',
            'instances_checked':12,'roles_checked':['t1c','t1n','t2w','t2f'],'raw_byte_passes':2,
            'live_archive_reconciled':True,'total_raw_bytes_observed':1000}
    review.record(entry,'approve',view['plan_revision'],view['assignment_set_sha256'],
                  {'user':identity,'authentication_method':'test_dependency_override'},source)
    monkeypatch.setattr(api,'check_archive_entry',lambda *_:dict(source))
    app.dependency_overrides[require_doctor]=lambda:identity
    return entry,view,identity


def test_requires_current_role_digest_before_any_activation(registered,monkeypatch):
    import app.api.pacs as api
    item=registered
    identity={'id':'e'*32,'username':'synthetic-test','role':'doctor'}
    app.dependency_overrides[require_doctor]=lambda:identity
    monkeypatch.setattr(api,'inspect_entry',lambda *_:pytest.fail('stale role digest must fail before file inspection'))
    try:
        client=TestClient(app)
        url=f"/pacs/cases/{item['case_id']}/conversions/test-version/activate-model-input"
        response=client.post(url,json={'plan_revision':'0'*64,'assignment_set_sha256':'1'*64,'confirm_activation':True})
        assert response.status_code==409
        assert response.json()['detail']['reason']=='conversion_role_review_stale'
        with SessionLocal() as db: assert db.query(MRI).filter_by(case_id=item['case_id']).count()==0
    finally: app.dependency_overrides.pop(require_doctor,None)


def test_engineering_resampling_is_never_released_as_model_input():
    import app.api.pacs as api
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        api._reject_engineering_resampling_activation({'resampling': {'interpolation': 'linear'}})
    assert error.value.status_code == 409
    assert error.value.detail['reason'] == 'resampled_model_input_not_released'
    # The existing strict-grid path remains eligible for the normal review gates.
    api._reject_engineering_resampling_activation({'resampling': None})


def test_approved_fixture_activates_new_input_and_keeps_history_in_isolated_db(registered,monkeypatch,tmp_path):
    """Archive reply is stubbed; this proves transaction mechanics only."""
    import app.api.pacs as api
    item=registered; entry,view,identity=_make_approval(item,monkeypatch)
    monkeypatch.setattr(api,'inspect_entry',lambda _:{'status':'verified_readonly','outputs':{
        role:{'nifti_sha256':hashlib.sha256((item['folder']/(role+'.nii.gz')).read_bytes()).hexdigest()}
        for role in ('t1c','t1n','t2w','t2f')}})
    def preview(_source,directory,_mri_id):
        target=Path(directory);target.mkdir(parents=True,exist_ok=True)
        image=target/'axial_0.png';image.write_bytes(b'SYNTHETIC preview');return [image]
    monkeypatch.setattr(api,'generate_mri_previews',preview,raising=False)
    # The actual endpoint imports the preview function locally, patch the source module.
    import app.services.mri_preview_service as previews
    monkeypatch.setattr(previews,'generate_mri_previews',preview)
    with SessionLocal() as db:
        case_id=item['case_id'];case=db.get(Case,case_id)
        old=MRI(case_id=case_id,filename='SYNTHETIC previous MRI',filepath=str(item['folder']/'t2f.nii.gz'),
            sequences_json=json.dumps({role:str(item['folder']/(role+'.nii.gz')) for role in ('t1c','t1n','t2w','t2f')}),
            status='preview_ready',input_source='nifti-upload')
        db.add(old);db.flush();old_id=old.id
        run=AnalysisRun(id='a'*32,case_id=case_id,mri_id=old_id,state='succeeded',request_json='{}',result_json='{}');db.add(run)
        report=Report(case_id=case_id,analysis_run_id=run.id,risk_level='historical',summary='[]',recommendation='[]');db.add(report)
        annotation=MRIAnnotation(mri_id=old_id,case_id=case_id,view='axial',slice_index=0,tool='line',
            x=0.1,y=0.1,width=0.2,height=0.0,coordinate_contract='LPS_DISPLAY_V1');db.add(annotation)
        db.commit();old_run_id=run.id;old_report_id=report.id;old_annotation_id=annotation.id
    client=TestClient(app);url=f"/pacs/cases/{item['case_id']}/conversions/test-version/activate-model-input"
    response=client.post(url,json={'plan_revision':view['plan_revision'],'assignment_set_sha256':view['assignment_set_sha256'],'confirm_activation':True})
    assert response.status_code==200,response.text
    result=response.json()['data']
    assert result['model_input_eligible'] and result['current_mri_replaced'] and not result['inference_performed']
    with SessionLocal() as db:
        case=db.get(Case,item['case_id']); current=db.query(MRI).filter_by(case_id=item['case_id']).order_by(MRI.id.desc()).first()
        old=db.get(MRI,old_id);run=db.get(AnalysisRun,old_run_id);report=db.get(Report,old_report_id);annotation=db.get(MRIAnnotation,old_annotation_id)
        assert current.id==result['mri_id'] and current.input_source=='dicom-conversion'
        assert case.mri_path==current.filepath
        assert json.loads(current.source_provenance_json)['conversion_version_id']=='test-version'
        assert old.filepath==str(item['folder']/'t2f.nii.gz')
        assert run.state=='succeeded' and report.analysis_run_id==old_run_id
        assert annotation.coordinate_contract=='obsolete-input'
        assert current.analysis_run_id is None and current.segmentation_path is None and not current.doctor_verified
    assert str(item['folder']) not in response.text
    case_detail=client.get(f"/cases/{item['case_id']}/detail").json()['data']
    detail=case_detail['mri']
    assert detail['input_source']=='dicom-conversion'
    assert detail['source_provenance']['conversion_version_id']=='test-version'
    assert str(item['folder']) not in json.dumps(detail)
    assert case_detail['analysis'] is None and case_detail['report'] is None
    history=client.get(f"/analysis/{item['case_id']}/history").json()['data']
    archived=next(row for row in history if row['id']==old_run_id)
    assert archived['state']=='succeeded' and archived['current'] is False
    assert client.get(f"/reports/{item['case_id']}").status_code==404

    # The analysis route consumes this exact activated MRI version and reviewed bytes.
    import app.api.analysis as analysis_api
    model_dir=tmp_path/'synthetic-model'; (model_dir/'models').mkdir(parents=True)
    (model_dir/'models'/'model.pt').write_bytes(b'SYNTHETIC checkpoint placeholder; worker is deliberately stubbed')
    monkeypatch.setattr(analysis_api.settings,'MODEL_DIR',str(model_dir))
    submitted_jobs=[]
    monkeypatch.setattr(analysis_api.executor,'submit',lambda fn,*args,**kwargs: submitted_jobs.append((fn,args,kwargs)))
    analysis_response=client.post(f"/analysis/{item['case_id']}")
    assert analysis_response.status_code==202,analysis_response.text
    analysis_id=analysis_response.json()['data']['id']
    assert len(submitted_jobs)==1 and submitted_jobs[0][1]==(analysis_id,)
    with SessionLocal() as db:
        activated=db.get(MRI,result['mri_id']); queued=db.get(AnalysisRun,analysis_id)
        request=json.loads(queued.request_json)
        expected={role:json.loads(activated.source_provenance_json)['roles'][role]['nifti_sha256']
                  for role in ('t1c','t1n','t2w','t2f')}
        assert queued.mri_id==activated.id
        assert request['sequences']==json.loads(activated.sequences_json)
        assert request['expected_input_sha256']==expected
        t1c=Path(json.loads(activated.sequences_json)['t1c'])
        # The worker is stubbed, so close only this synthetic queued job before further API assertions.
        queued.state='failed'; queued.error='Synthetic contract test; inference intentionally not run'
        activated.status='preview_ready'
        db.commit()
    original_t1c=t1c.read_bytes()
    try:
        import nibabel as nib
        import numpy as np
        image=nib.load(str(t1c)); values=np.asarray(image.dataobj).copy(); values.flat[0]+=1
        nib.save(nib.Nifti1Image(values,image.affine,image.header),str(t1c))
        drift_response=client.post(f"/analysis/{item['case_id']}")
        assert drift_response.status_code==409,drift_response.text
        assert 'reviewed hashes' in drift_response.text
        assert len(submitted_jobs)==1
    finally:
        t1c.write_bytes(original_t1c)

    # Replacing this activated MRI with ordinary NIfTI must not erase its DICOM provenance history.
    files={role:(role+'.nii.gz',(item['folder']/(role+'.nii.gz')).read_bytes(),'application/gzip')
           for role in ('t1c','t1n','t2w','t2f')}
    upload=client.post(f"/studies/{item['case_id']}",files=files)
    assert upload.status_code==200,upload.text
    with SessionLocal() as db:
        converted=db.get(MRI,result['mri_id'])
        latest=db.query(MRI).filter_by(case_id=item['case_id']).order_by(MRI.id.desc()).first()
        assert converted.input_source=='dicom-conversion'
        assert json.loads(converted.source_provenance_json)['conversion_version_id']=='test-version'
        assert latest.id!=converted.id and latest.input_source=='nifti-upload'
    app.dependency_overrides.pop(require_doctor,None)
