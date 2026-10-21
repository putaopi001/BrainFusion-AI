"""Explicit synthetic source/role/grid versions and read-only CLI behavior."""
import copy
import hashlib
import itertools
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import nibabel as nib
import numpy as np
import pytest

from app.services.dicom_series import validate_series
from app.services.dicom_input_plan import ROLES, ROLE_SIGNALS, plan_report, validate_plan, metadata_semantic_digest
from app.services.study_validation import validate_sequences, validate_model_geometry
from test_dicom_series import items, STUDY, FRAME, tag


def inputs(change=None):
    sources = []
    assignments = []
    for i, role in enumerate(ROLES):
        series = '2.25.' + str(800+i)
        raw = []
        count = 129 if change == 'large' else 3
        for k in reversed(range(count)):
            item = items()[0]
            item['0020000E'] = tag(series)
            item['00080018'] = tag('2.25.'+str(10000+i*1000+k))
            item['00200013'] = tag(999-k, 'IS')  # Must not determine physical sort.
            item['00200037'] = tag([1,0,0,0,1,0], 'DS')
            item['00200032'] = tag([10,20,30+k], 'DS')
            item['00280030'] = tag([1,1], 'DS')
            item['00180088'] = tag(1, 'DS')
            item['0008103E'] = tag('ALL_HAVE_MISLEADING_FLAIR_NAME', 'LO')
            if change == 'spacing':
                item['00280030'] = tag([1,1.2], 'DS')
            elif change == 'oblique':
                item['00200037'] = tag([.6,.8,0,0,0,1], 'DS')
                item['00200032'] = tag([10+.8*k,20-.6*k,30], 'DS')
            elif change == 'frame' and i == 2:
                item['00200052'] = tag('2.25.999')
            elif change == 'origin' and i == 2:
                item['00200032'] = tag([10.1,20,30+k], 'DS')
            elif change == 'shape' and i == 2:
                item['00280011'] = tag(4, 'US')
            elif change == 'large':
                item['00280010'] = tag(512, 'US'); item['00280011'] = tag(512, 'US')
            elif change == 'mosaic' and i == 0:
                item['00080008'] = tag(['ORIGINAL','PRIMARY','MOSAIC'], 'CS')
            raw.append(item)
        if change == 'mosaic' and i == 0:
            # Cannot create a checked manifest for an unsupported layout.
            source = {'format':'dicom-series-view-manifest-v1','study_uid':STUDY,'series_uid':series,
                      'instance_count':len(raw),'instances':[{'instance_uid':r['00080018']['Value'][0],
                      'metadata':r,'metadata_sha256':'0'*64} for r in raw],'metadata_sha256':'0'*64,'geometry':{}}
        else:
            source = validate_series(SimpleNamespace(allow_pixel_read=False), raw, STUDY, series,
                                     [r['00080018']['Value'][0] for r in raw])
        source.update(source_case_id=17, archive_id='SYNTHETIC-plan', archive_fingerprint='1'*64)
        weighting, phase, attenuated = ROLE_SIGNALS[role]
        assignments.append({'role':role,'study_uid':STUDY,'series_uid':series,
            'series_metadata_sha256':source['metadata_sha256'], 'evidence':{
            'weighting':weighting,'contrast_phase':phase,'fluid_attenuated':attenuated,
            'basis':'local_manual_review','evidence_sha256':'2'*64,
            'evidence_reference':'SYNTHETIC.fixture-only','reviewer_reference':'SYNTHETIC-not-a-doctor',
            'confirmed_at':'2026-10-13T06:15:00+08:00'}})
        sources.append(source)
    proposal = {'format':'dicom-model-input-proposal-v1','data_role':'synthetic-fixture','case_id':17,
                'archive_id':'SYNTHETIC-plan','archive_fingerprint':'1'*64,'assignments':assignments}
    return proposal, {'format':'dicom-series-snapshot-bundle-v1','data_role':'synthetic-fixture','series':sources}


def test_four_explicit_roles_and_independent_ras_corner_no_conversion_or_ai():
    proposal,bundle = inputs(); before = copy.deepcopy((proposal,bundle))
    result = validate_plan(proposal,bundle)
    assert result['status']=='metadata_plan_ready' and result['metadata_geometry_contract_passed']
    assert not result['model_input_eligible'] and not result['conversion_performed']
    assert not result['archive_case_binding_independently_verified'] and not result['source_dicom_bytes_verified']
    assert 'not_authenticated' in result['role_confirmation_status']
    matrix=np.array(result['sources']['t1c']['expected_source_ijk_to_ras_mm'])
    assert matrix @ [2,1,2,1] == pytest.approx([-12,-21,32,1])
    assert (proposal,bundle)==before
    output=json.dumps(result)
    assert 'PRIVATE_NAME_NEVER_EXPOSE' not in output and 'FLAIR_NAME' not in output and 'external.invalid' not in output
    assert len(result['sources'])==4 and len(result['plan_revision'])==64


def test_numeric_json_spelling_is_only_normalized_for_file_semantic_comparison():
    proposal,bundle=inputs()
    item=copy.deepcopy(bundle['series'][0]['instances'][0]['metadata'])
    original=metadata_semantic_digest(item)
    item['00200032']['Value']=[str(v)+'.0' for v in item['00200032']['Value']]
    assert metadata_semantic_digest(item)==original
    item['00200032']['Value'][0]='10.1'
    assert metadata_semantic_digest(item)!=original


@pytest.mark.parametrize('change,reason',[
    ('missing','invalid_proposal'),('duplicate_role','four_distinct_roles_required'),
    ('same_series','distinct_series_required'),('different_study','cross_study_not_supported'),
    ('role_signal','role_evidence_conflict'),('bool_string','invalid_proposal'),
    ('no_evidence','invalid_proposal'),('no_timezone','invalid_proposal'),
    ('extra_private','invalid_proposal'),('invalid_uid','invalid_proposal'),('case_bool','invalid_proposal')])
def test_no_automatic_roles_or_unreviewed_declaration(change,reason):
    proposal,bundle=inputs(); row=proposal['assignments'][0]
    if change=='missing':proposal['assignments'].pop()
    elif change=='duplicate_role':row['role']='t1n'
    elif change=='same_series':row['series_uid']=proposal['assignments'][1]['series_uid']
    elif change=='different_study':row['study_uid']='2.25.999'
    elif change=='role_signal':row['evidence']['contrast_phase']='pre'
    elif change=='bool_string':row['evidence']['fluid_attenuated']='false'
    elif change=='no_evidence':row.pop('evidence')
    elif change=='no_timezone':row['evidence']['confirmed_at']='2026-10-13T06:15:00'
    elif change=='extra_private':row['PatientName']='PRIVATE_INPUT_NEVER_LOG'
    elif change=='invalid_uid':row['series_uid']='https://external.invalid'
    else:proposal['case_id']=True
    result=plan_report(proposal,bundle)
    assert result['status']=='rejected' and result['reason']==reason
    assert not result['model_input_eligible'] and 'PRIVATE_INPUT' not in json.dumps(result)


@pytest.mark.parametrize('change,reason',[
    ('case','source_context_mismatch'),('archive','source_context_mismatch'),
    ('fingerprint','source_context_mismatch'),('missing_source','four_source_snapshots_required'),
    ('duplicate_source','duplicate_source_snapshot'),('source_set','source_set_mismatch'),
    ('instance_revision','instance_snapshot_revision_mismatch'),
    ('series_revision','series_snapshot_revision_mismatch'),
    ('geometry','snapshot_geometry_mismatch'),('instance_missing','invalid_snapshot'),
    ('count_bool','invalid_snapshot')])
def test_source_and_version_not_trusted_from_cached_claims(change,reason):
    proposal,bundle=inputs(); row=bundle['series'][0]
    if change=='case':row['source_case_id']=18
    elif change=='archive':row['archive_id']='SYNTHETIC-other'
    elif change=='fingerprint':row['archive_fingerprint']='3'*64
    elif change=='missing_source':bundle['series'].pop()
    elif change=='duplicate_source':bundle['series'][1]=copy.deepcopy(row)
    elif change=='source_set':row['series_uid']='2.25.999'
    elif change=='instance_revision':row['instances'][0]['metadata_sha256']='0'*64
    elif change=='series_revision':row['metadata_sha256']='0'*64
    elif change=='geometry':row['geometry']['origin_lps_mm'][0]+=100
    elif change=='instance_missing':row['instances'].pop()
    else:row['instance_count']=True
    result=plan_report(proposal,bundle)
    assert result['status']=='rejected' and result['reason']==reason


@pytest.mark.parametrize('change,reason',[
    ('spacing','model_spacing_unsupported'),('oblique','model_oblique_unsupported'),
    ('frame','model_frames_differ'),('origin','model_grids_differ'),('shape','model_grids_differ'),
    ('large','model_grid_unsupported'),('mosaic','unsupported_mosaic')])
def test_viewable_dicom_does_not_imply_model_input(change,reason):
    proposal,bundle=inputs(change)
    result=plan_report(proposal,bundle)
    assert result['status']=='rejected' and result['reason']==reason
    assert not result['registration_or_resampling'] and not result['model_input_eligible']


def test_same_sop_cannot_be_reused_and_confirms_versions_change():
    proposal,bundle=inputs()
    first=validate_plan(proposal,bundle)
    proposal['assignments'].reverse();bundle['series'].reverse()
    for snapshot in bundle['series']:snapshot['instances'].reverse()
    assert validate_plan(proposal,bundle)['plan_revision']==first['plan_revision']
    proposal['assignments'][0]['evidence']['reviewer_reference']='SYNTHETIC-different-review'
    assert validate_plan(proposal,bundle)['plan_revision']!=first['plan_revision']
    proposal,bundle=inputs()
    source=bundle['series'][1]
    source['instances'][0]['instance_uid']=bundle['series'][0]['instances'][0]['instance_uid']
    source['instances'][0]['metadata']['00080018']=tag(source['instances'][0]['instance_uid'])
    assert plan_report(proposal,bundle)['reason']=='source_instance_reused'


def test_geometry_header_check_is_equivalent_for_permutations_flips_and_is_lazy(tmp_path,monkeypatch):
    for permutation in itertools.permutations(range(3)):
        for signs in itertools.product([-1,1],repeat=3):
            affine=np.eye(4);affine[:3,:3]=np.eye(3)[:,permutation]*signs
            image=nib.Nifti1Image(np.zeros((3,4,5),np.uint8),affine)
            orientation=nib.orientations.ornt_transform(nib.orientations.io_orientation(affine),nib.orientations.axcodes2ornt(('L','P','S')))
            expected=image.as_reoriented(orientation).affine
            actual=affine @ nib.orientations.inv_ornt_aff(orientation,image.shape)
            np.testing.assert_array_equal(expected,actual)
            validate_model_geometry(image.shape,affine,image.header.get_zooms())
    path=tmp_path/'SYNTHETIC-lazy.nii.gz'
    nib.save(nib.Nifti1Image(np.arange(60,dtype=np.float32).reshape((3,4,5)),np.eye(4)),path)
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    def forbid(*_args,**_kwargs):raise AssertionError('Header validation must not read/reorient pixels')
    monkeypatch.setattr(nib.arrayproxy.ArrayProxy,'__array__',forbid)
    monkeypatch.setattr(nib.Nifti1Image,'as_reoriented',forbid)
    assert validate_sequences({role:path for role in ROLES}).shape==(3,4,5)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before


def test_explicit_same_frame_resampling_policy_is_required_and_bound_to_target_grid():
    proposal,bundle=inputs('spacing')
    assert plan_report(proposal,bundle)['reason']=='model_spacing_unsupported'
    proposal['resampling']={
        'format':'dicom-model-resampling-policy-v1','reference_role':'t1c',
        'target_spacing_xyz_mm':[1,1,1],'interpolation':'linear',
        'coordinate_mapping':'same_frame_of_reference_identity','outside_value':0}
    result=validate_plan(proposal,bundle)
    assert result['metadata_geometry_contract_passed']
    assert result['registration_or_resampling']
    assert result['target_grid']['spacing_xyz_mm']==[1,1,1]
    assert result['target_grid']['dimensions']==[3,2,3]
    assert result['target_grid']['origin_lps_mm']==[10.0,20.0,30.0]
    assert result['resampling']['reference_role']=='t1c'
    assert not result['model_input_eligible'] and not result['conversion_performed']


def test_explicit_resampling_refuses_frame_mismatch_and_uncovered_source():
    proposal,bundle=inputs('frame')
    proposal['resampling']={
        'format':'dicom-model-resampling-policy-v1','reference_role':'t1c',
        'target_spacing_xyz_mm':[1,1,1],'interpolation':'linear',
        'coordinate_mapping':'same_frame_of_reference_identity','outside_value':0}
    result=plan_report(proposal,bundle)
    assert result['reason']=='model_frames_differ'
    proposal,bundle=inputs('shape')
    proposal['resampling']={
        'format':'dicom-model-resampling-policy-v1','reference_role':'t1c',
        'target_spacing_xyz_mm':[1,1,1],'interpolation':'linear',
        'coordinate_mapping':'same_frame_of_reference_identity','outside_value':0}
    # Reduce the assigned t2w volume so it cannot cover the reference target.
    t2w=next(row for row in bundle['series'] if row['series_uid']==next(
        item['series_uid'] for item in proposal['assignments'] if item['role']=='t2w'))
    for instance in t2w['instances']:
        instance['metadata']['00280011']=tag(2,'US')
    from app.services.dicom_series import validate_series
    from types import SimpleNamespace
    refreshed=validate_series(SimpleNamespace(allow_pixel_read=False),
        [row['metadata'] for row in t2w['instances']],t2w['study_uid'],t2w['series_uid'],
        [row['instance_uid'] for row in t2w['instances']])
    refreshed.update(source_case_id=t2w['source_case_id'],archive_id=t2w['archive_id'],
                     archive_fingerprint=t2w['archive_fingerprint'])
    t2w.update(refreshed)
    assignment=next(item for item in proposal['assignments'] if item['role']=='t2w')
    assignment['series_metadata_sha256']=t2w['metadata_sha256']
    result=plan_report(proposal,bundle)
    assert result['reason']=='model_resampling_geometry_invalid'


def test_real_cli_read_only_saved_receipt_rejects_overwrite_and_duplicate_keys(tmp_path):
    proposal,bundle=inputs()
    p,s,out=tmp_path/'proposal.json',tmp_path/'snapshots.json',tmp_path/'receipt.json'
    p.write_text(json.dumps(proposal),encoding='utf-8');s.write_text(json.dumps(bundle),encoding='utf-8')
    before=[hashlib.sha256(x.read_bytes()).hexdigest() for x in [p,s]]
    tool=Path(__file__).resolve().parents[1]/'tools/plan_dicom_model_input.py'
    args=[sys.executable,str(tool),'--proposal',str(p),'--snapshots',str(s),'--output',str(out)]
    result=subprocess.run(args,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    receipt=out.read_bytes();assert not json.loads(receipt)['model_input_eligible']
    assert [hashlib.sha256(x.read_bytes()).hexdigest() for x in [p,s]]==before
    retry=subprocess.run(args,capture_output=True,text=True)
    assert retry.returncode==2 and out.read_bytes()==receipt
    p.write_text('{"case_id":17,"case_id":18,"PatientName":"PRIVATE_NEVER_PRINT"}',encoding='utf-8')
    args[-1]=str(tmp_path/'duplicate-rejected.json')
    rejected=subprocess.run(args,capture_output=True,text=True)
    assert rejected.returncode==3 and 'PRIVATE_NEVER_PRINT' not in rejected.stdout+rejected.stderr
    assert json.loads(Path(args[-1]).read_text(encoding='utf-8'))['reason']=='invalid_input_files'
