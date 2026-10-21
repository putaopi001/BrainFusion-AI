"""Oblique anisotropic synthetic source, real HTTP + isolated SQLite writes."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest
from app.database import SessionLocal
from app.models.dicom_measurement import DICOMWorldMeasurement
from test_pacs import archive, case_ids, client, STUDY, SERIES
from test_dicom_series import tag
from test_dicom_view_source import prepare
from app.api import pacs
from app.services.pacs_client import load_config


@pytest.fixture
def linked(archive, case_ids):
    case_id=case_ids[0]
    endpoint=prepare(archive,case_id)+'/measurements'
    data=client.get(endpoint)
    assert data.status_code==200,data.text
    payload=dict(context=data.json()['data']['context'],client_uid='SYNTHETIC-AXIAL',view='axial',
        points_lps=[[10,20,30],[11.2,21.6,30]],view_plane_normal=[0,0,1],view_up=[0,-1,0])
    return case_id,endpoint,payload


def test_persist_idempotence_independent_physical_distance_and_delete(linked):
    case_id,endpoint,payload=linked
    saved=client.post(endpoint,json=payload)
    assert saved.status_code==200,saved.text
    item=saved.json()['data']
    # Exactly one column of the known fixture: 2 mm, despite anisotropic
    # row/slice spacing and oblique acquisition axes.
    assert item['length_mm']==pytest.approx(2,abs=1e-8)
    assert client.post(endpoint,json=payload).json()['data']['id']==item['id']
    assert saved.headers['cache-control']=='no-store'
    with SessionLocal() as db:
        row=db.get(DICOMWorldMeasurement,item['id'])
        assert row.case_id==case_id and json.loads(row.points_lps)==payload['points_lps']
    listing=client.get(endpoint).json()['data']
    assert len(listing['items'])==1 and listing['items'][0]['current']
    bad=copy.deepcopy(payload);bad['points_lps'][1]=[10.6,20.8,30]
    assert client.post(endpoint,json=bad).status_code==409
    removed=client.request('DELETE',endpoint+'/'+str(item['id']),json=dict(context=payload['context']))
    assert removed.status_code==200 and client.get(endpoint).json()['data']['items']==[]


@pytest.mark.parametrize('kind',['outside','plane','normal','view','zero','unknown_context','nifti_role'])
def test_invalid_coordinates_or_context_never_write(linked,kind):
    _,endpoint,payload=linked
    if kind=='outside':payload['points_lps'][1]=[100,100,30]
    elif kind=='plane':payload['points_lps'][1][2]=31
    elif kind=='normal':payload['view_up']=[0,0,1]
    elif kind=='view':payload['view']='sagittal'
    elif kind=='zero':payload['points_lps'][1]=payload['points_lps'][0]
    elif kind=='unknown_context':payload['context']['metadata_sha256']='f'*64
    else:payload['reference_sequence']='t1c'
    response=client.post(endpoint,json=payload)
    assert response.status_code==(409 if kind=='unknown_context' else 422),response.text
    assert client.get(endpoint).json()['data']['items']==[]


def test_changed_series_retains_history_and_refuses_stale_save_delete(archive,linked):
    _,endpoint,payload=linked
    item=client.post(endpoint,json=payload).json()['data']
    archive['series_metadata'][0]['00281050']=tag(123,'DS')
    data=client.get(endpoint).json()['data']
    assert not data['items'][0]['current'] and data['items'][0]['id']==item['id']
    assert client.post(endpoint,json=payload).status_code==409
    assert client.request('DELETE',endpoint+'/'+str(item['id']),json=dict(context=payload['context'])).status_code==409
    assert client.request('DELETE',endpoint+'/'+str(item['id']),json=dict(context=data['context'])).status_code==409


def test_case_binding_and_archive_pin_are_required(archive,linked,case_ids):
    _,endpoint,payload=linked
    other=endpoint.replace('/cases/'+str(linked[0])+'/', '/cases/'+str(case_ids[1])+'/')
    assert client.get(other).status_code==409
    archive['system_extra']['DatabaseServerIdentifier']='CHANGED'
    assert client.post(endpoint,json=payload).status_code==409


def test_changed_during_read_and_pixel_permission_refuse(archive,linked):
    _,endpoint,payload=linked
    archive['series_metadata_reads']=0
    archive['series_mode']='changed_geometry'
    assert client.post(endpoint,json=payload).status_code==409
    archive['series_mode']='normal'
    archive['config']['allow_pixel_read']=False
    archive['path'].write_text(json.dumps(archive['config']),encoding='utf-8')
    assert client.get(endpoint).status_code==409


def test_permission_revoked_during_metadata_check_is_rejected(linked,monkeypatch):
    _,endpoint,payload=linked
    original=load_config()
    calls=[]
    def changing_config():
        calls.append(True)
        return original if len(calls)==1 else original.model_copy(update={'allow_pixel_read':False})
    monkeypatch.setattr(pacs,'load_config',changing_config)
    response=client.post(endpoint,json=payload)
    assert response.status_code==409 and response.json()['detail']['reason']=='dicom_measurement_source_changed'


def test_existing_database_backup_preserves_new_table_and_measurement_rows(linked,tmp_path):
    from app.database import engine
    _,endpoint,payload=linked
    ids=[]
    for i in range(3):
        body=copy.deepcopy(payload);body['client_uid']+='-'+str(i)
        response=client.post(endpoint,json=body)
        assert response.status_code==200,response.text
        ids.append(response.json()['data']['id'])
    source=Path(engine.url.database).resolve()
    output=tmp_path/'database-backup'
    subprocess.run([sys.executable,str(Path(__file__).parents[1]/'tools/snapshot_database.py'),
        '--source',str(source),'--output',str(output)],check=True,capture_output=True,text=True)
    def records(path):
        with sqlite3.connect(path) as db:
            return [db.execute('select * from dicom_world_measurements where id=?',(i,)).fetchone() for i in ids]
    assert records(source)==records(output/'snapshot.db')==records(output/'restored-validation.db')
