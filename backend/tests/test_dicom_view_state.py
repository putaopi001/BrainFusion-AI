"""Explicit synthetic archive; actual API/SQLite view versions and restore copy."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from app.database import SessionLocal, engine
from app.models.dicom_view_state import DICOMViewState
from test_dicom_measurements import archive, case_ids, linked
from test_pacs import client
from test_dicom_series import tag
from test_world_measurements import view_payload


def payload_for(linked):
    body=view_payload(linked[2]['context'])
    return dict(context=body['context'],client_uid=body['client_uid'],cameras=body['cameras'],
                window_ranges=body['window_ranges']['legacy'])


def endpoint_for(linked):
    return linked[1].replace('/measurements','/view-state')


def test_versions_retry_exact_restore_and_history(archive,linked):
    endpoint=endpoint_for(linked);body=payload_for(linked)
    assert client.get(endpoint).json()['data']['saved'] is None
    response=client.post(endpoint,json=body)
    assert response.status_code==200,response.text
    first=response.json()['data']
    assert response.headers['cache-control']=='no-store'
    assert client.post(endpoint,json=body).json()['data']==first
    changed=copy.deepcopy(body);changed['cameras']['axial']['parallel_scale']=16
    assert client.post(endpoint,json=changed).status_code==409
    changed['client_uid']='new-view-version'
    second=client.post(endpoint,json=changed).json()['data']
    assert second['id']!=first['id'] and second['current']
    assert client.get(endpoint).json()['data']['saved']==second
    with SessionLocal() as db:
        assert db.query(DICOMViewState).filter_by(case_id=linked[0]).count()==2
    archive['series_metadata'][0]['00281050']=tag(321,'DS')
    stale=client.get(endpoint).json()['data']
    assert not stale['saved']['current'] and stale['saved']['state']==second['state']
    assert client.post(endpoint,json=changed).status_code==409


@pytest.mark.parametrize('kind',['missing_camera','normal','position','scale','window','window_count','nifti_role','mask','stale'])
def test_invalid_or_stale_view_never_creates_a_version(linked,kind):
    endpoint=endpoint_for(linked);body=payload_for(linked)
    if kind=='missing_camera':del body['cameras']['coronal']
    elif kind=='normal':body['cameras']['axial']['view_up']=[0,0,1]
    elif kind=='position':body['cameras']['axial']['position']=[1e7,1e7,1e7]
    elif kind=='scale':body['cameras']['axial']['parallel_scale']=0
    elif kind=='window':body['window_ranges'][0]['upper']=body['window_ranges'][0]['lower']
    elif kind=='window_count':body['window_ranges']=body['window_ranges'][:2]
    elif kind=='nifti_role':body['sequence']='t1c'
    elif kind=='mask':body['segmentation_visible']=True
    else:body['context']['metadata_sha256']='e'*64
    response=client.post(endpoint,json=body)
    assert response.status_code==(409 if kind=='stale' else 422),response.text
    assert client.get(endpoint).json()['data']['saved'] is None


def test_wrong_case_or_archive_pin_cannot_save(archive,case_ids,linked):
    endpoint=endpoint_for(linked);body=payload_for(linked)
    other=endpoint.replace('/cases/'+str(linked[0])+'/', '/cases/'+str(case_ids[1])+'/')
    assert client.post(other,json=body).status_code==409
    archive['system_extra']['DatabaseServerIdentifier']='CHANGED'
    assert client.post(endpoint,json=body).status_code==409


def test_existing_backup_restores_new_view_table_exactly(linked,tmp_path):
    endpoint=endpoint_for(linked)
    response=client.post(endpoint,json=payload_for(linked))
    assert response.status_code==200,response.text
    item_id=response.json()['data']['id']
    source=Path(engine.url.database).resolve();output=tmp_path/'snapshot'
    subprocess.run([sys.executable,str(Path(__file__).parents[1]/'tools/snapshot_database.py'),
        '--source',str(source),'--output',str(output)],check=True,capture_output=True,text=True)
    def row(path):
        with sqlite3.connect(path) as db:
            return db.execute('select * from dicom_view_states where id=?',(item_id,)).fetchone()
    assert row(source)==row(output/'snapshot.db')==row(output/'restored-validation.db')
