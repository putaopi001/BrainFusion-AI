"""Case/target/revision gates with synthetic TCP, isolated DB, no clinical data."""
import json
from uuid import uuid4
import pytest
from test_pacs import archive,case_ids,client,STUDY,SERIES
from test_dicom_series import setup_tcp
from app.services.pacs_wado import multipart_response


def prepare(archive,case_id,linked=True):
    setup_tcp(archive)
    archive['config'].update(archive_id='SYNTHETIC-view-'+uuid4().hex[:8],
                             allow_pixel_read=True,expected_database_server_identifier='SYNTHETIC-A')
    archive['system_extra']={'DatabaseServerIdentifier':'SYNTHETIC-A','OverwriteInstances':False,
                             'IngestTranscoding':'','ReadOnly':False}
    archive['path'].write_text(json.dumps(archive['config']),encoding='utf-8')
    if linked:
        response=client.post(f'/pacs/cases/{case_id}/links',json={'study_uid':STUDY,'acknowledge_case_match':True})
        assert response.status_code==200,response.text
    return f'/pacs/cases/{case_id}/studies/{STUDY}/series/{SERIES}'


def test_bound_manifest_and_original_frame_bytes(archive,case_ids):
    prefix=prepare(archive,case_ids[0])
    response=client.get(prefix+'/view-manifest')
    assert response.status_code==200,response.text
    data=response.json()['data']
    assert data['source_case_id']==case_ids[0] and data['transport_enabled']
    assert not data['model_input_eligible'] and data['saved_dicom_annotations_available']
    assert data['dicom_view_state_available']
    row=data['instances'][0]
    uri=row['metadata']['7FE00010']['BulkDataURI']
    assert uri.startswith(prefix) and row['metadata_sha256'] in uri and data['archive_fingerprint'] in uri
    archive['metadata']=[row['metadata']]
    raw=b'\x01\x00'*6
    archive['frame_body'],archive['frame_type']=multipart_response(raw)
    frame=client.get(uri)
    assert frame.status_code==200 and raw in frame.content
    assert frame.headers['cache-control']=='no-store'


@pytest.mark.parametrize('mode,reason',[
    ('unlinked','case_archive_link_required'),('other_case','case_archive_link_required'),
    ('disabled','pixel_read_disabled'),('unpinned','archive_identity_unpinned'),
    ('overwrite','archive_overwrite_enabled')])
def test_no_wrong_case_or_unapproved_target_transport(archive,case_ids,mode,reason):
    prefix=prepare(archive,case_ids[0],linked=mode not in ('unlinked','unpinned'))
    if mode=='other_case':prefix=prefix.replace('/cases/'+str(case_ids[0])+'/','/cases/'+str(case_ids[1])+'/')
    elif mode=='disabled':archive['config']['allow_pixel_read']=False
    elif mode=='unpinned':archive['config'].pop('expected_database_server_identifier')
    elif mode=='overwrite':archive['system_extra']['OverwriteInstances']=True
    archive['path'].write_text(json.dumps(archive['config']),encoding='utf-8')
    result=client.get(prefix+'/view-manifest')
    if mode=='unpinned':
        linked=client.post(f'/pacs/cases/{case_ids[0]}/links',json={'study_uid':STUDY,'acknowledge_case_match':True})
        assert linked.status_code==200,linked.text
        result=client.get(prefix+'/view-manifest')
    assert result.status_code in (409,503),result.text
    assert result.json()['detail']['reason']==reason
    assert not any(r['path'].endswith('/frames/1') for r in archive['requests'])


@pytest.mark.parametrize('mode,reason',[('geometry','instance_revision_mismatch'),('fingerprint','archive_revision_mismatch')])
def test_old_source_revision_never_reaches_pixels(archive,case_ids,mode,reason):
    prefix=prepare(archive,case_ids[0])
    data=client.get(prefix+'/view-manifest').json()['data']
    row=data['instances'][0]
    uri=row['metadata']['7FE00010']['BulkDataURI']
    archive['metadata']=[row['metadata']]
    if mode=='geometry':
        archive['metadata'][0]['00200032']['Value'][0]+=1
    else:
        uri=uri.replace(data['archive_fingerprint'],'0'*64)
    result=client.get(uri)
    assert result.status_code==409 and result.json()['detail']['reason']==reason
    assert not any(r['path'].endswith('/frames/1') for r in archive['requests'])
