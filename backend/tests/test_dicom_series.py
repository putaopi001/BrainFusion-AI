"""Explicit SYNTHETIC geometry and TCP/API completeness checks, not clinical data."""
import copy
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.services import dicom_series as service
from app.services.pacs_client import PacsConfig
from test_pacs import archive,client,STUDY,SERIES,FRAME,tag


def items():
    result=[]
    for index in [2,0,1]:  # Archive order and InstanceNumber deliberately disagree.
        uid='2.25.'+str(500+index)
        result.append({
            '00080008':tag(['ORIGINAL','PRIMARY'],'CS'),'00080016':tag('1.2.840.10008.5.1.4.1.1.4'),
            '00080018':tag(uid),'00080060':tag('MR','CS'),'0020000D':tag(STUDY),'0020000E':tag(SERIES),
            '00200052':tag(FRAME),'00200013':tag(100-index,'IS'),
            '00200032':tag([10+index*2,20-index*1.5,30],'DS'),
            '00200037':tag([.6,.8,0,0,0,1],'DS'),'00280030':tag([3.25,2],'DS'),
            '00280010':tag(2,'US'),'00280011':tag(3,'US'),'00280002':tag(1,'US'),
            '00280004':tag('MONOCHROME2','CS'),'00280100':tag(16,'US'),'00280101':tag(16,'US'),
            '00280102':tag(15,'US'),'00280103':tag(1,'US'),'00180050':tag(9,'DS'), # Not interslice spacing.
            '00180088':tag(2.5,'DS'),'00100010':tag('PRIVATE_NAME_NEVER_EXPOSE','PN'),
            '7FE00010':{'vr':'OW','BulkDataURI':'https://external.invalid/NEVER_FOLLOW'},
        })
    return result


def validate(data=None,expected=None):
    data=items() if data is None else data
    ids=[row['00080018']['Value'][0] for row in data] if expected is None else expected
    return service.validate_series(SimpleNamespace(allow_pixel_read=True),data,STUDY,SERIES,ids)


def test_oblique_lps_sort_row_column_units_and_no_rewriting():
    data=items();before=copy.deepcopy(data)
    result=validate(data)
    assert [row['instance_uid'] for row in result['instances']]==['2.25.500','2.25.501','2.25.502']
    geo=result['geometry']
    assert geo['dimensions']==[3,2,3] and geo['spacing_xyz_mm']==pytest.approx([2,3.25,2.5])
    assert geo['origin_lps_mm']==[10,20,30] and geo['unit_normal_for_sorting']==pytest.approx([.8,-.6,0])
    # Independently hand-calculated voxel(column2,row1,slice2) in this known fixture.
    a,b=geo['image_orientation_patient'][:3],geo['image_orientation_patient'][3:]
    world=[geo['origin_lps_mm'][d]+2*2*a[d]+3.25*b[d]+2*2.5*geo['unit_normal_for_sorting'][d] for d in range(3)]
    assert world==pytest.approx([16.4,20.2,33.25])
    assert data==before and not geo['geometry_corrected'] and not geo['registration_or_resampling']
    assert result['uncompressed_pixel_bytes']==36 and not result['model_input_eligible']
    assert not result['dicom_view_accepted'] and not result['original_pixel_bytes_retrieved']
    assert all('00100010' not in row['metadata'] and row['metadata']['7FE00010']['BulkDataURI'].startswith('/pacs/')
               for row in result['instances'])


@pytest.mark.parametrize('change,reason',[
    ('frame','mixed_frame_of_reference'),('orientation','mixed_series_orientation'),
    ('pixel_spacing','mixed_pixel_spacing'),('layout','mixed_series_pixel_layout'),
    ('same_plane','duplicate_slice_position'),('drift','non_rectilinear_series'),
    ('gap','non_uniform_slice_spacing'),('declared_mixed','inconsistent_declared_slice_spacing'),
    ('duplicate_uid','duplicate_series_uid'),('missing','series_instance_set_mismatch'),
    ('single','single_plane_volume_unavailable'),('mosaic','unsupported_mosaic'),
    ('multiframe','unsupported_multiframe'),('uid_parent','uid_mismatch'),
])
def test_unsupported_series_explicitly_refused(change,reason):
    data=items();expected=[r['00080018']['Value'][0] for r in data]
    if change=='frame':data[0]['00200052']=tag('2.25.999')
    elif change=='orientation':data[0]['00200037']=tag([-.6,-.8,0,0,0,1],'DS')
    elif change=='pixel_spacing':data[0]['00280030']=tag([3.25,2.2],'DS')
    elif change=='layout':data[0]['00280011']=tag(4,'US')
    elif change=='same_plane':data[0]['00200032']=copy.deepcopy(data[1]['00200032'])
    elif change=='drift':data[0]['00200032']['Value'][2]+=1
    elif change=='gap':data[0]['00200032']=tag([16,15.5,30],'DS')
    elif change=='declared_mixed':data[0]['00180088']=tag(9,'DS')
    elif change=='duplicate_uid':data[0]['00080018']=copy.deepcopy(data[1]['00080018'])
    elif change=='missing':data.pop()
    elif change=='single':data=data[:1];expected=expected[:1]
    elif change=='mosaic':data[0]['00080008']=tag(['ORIGINAL','PRIMARY','MOSAIC'],'CS')
    elif change=='multiframe':data[0]['00280008']=tag(2,'IS')
    else:data[0]['0020000D']=tag('2.25.999')
    with pytest.raises(HTTPException) as caught:validate(data,expected)
    assert caught.value.detail['reason']==reason


@pytest.mark.parametrize(('declared','measured','thickness'),[(1,3,3), (1,.9,.9)])
def test_regular_slice_centers_override_consistent_declared_spacing_but_preserve_qc(declared,measured,thickness):
    data=items()
    for row in data:
        index=int(row['00080018']['Value'][0].split('.')[-1])-500
        row['00200032']=tag([10+measured*index*.8,20-measured*index*.6,30],'DS')
        row['00180088']=tag(declared,'DS')
        row['00180050']=tag(thickness,'DS')
    result=validate(data)
    geometry=result['geometry']; qc=geometry['spacing_qc']
    assert geometry['spacing_xyz_mm'][2]==pytest.approx(measured)
    assert qc['geometry_source'].startswith('ImagePositionPatient')
    assert qc['measured_slice_center_spacing_mm']==pytest.approx(measured)
    assert qc['declared_spacing_between_slices_mm']==pytest.approx(declared)
    assert qc['declared_spacing_absolute_difference_mm']==pytest.approx(abs(declared-measured))
    assert qc['declared_spacing_matches_measured_centers'] is False
    assert qc['slice_thickness_values_mm']==[thickness]
    assert qc['declaration_used_for_geometry'] is False
    assert geometry['measured_slice_gaps_mm']==pytest.approx([measured,measured])
    assert [row['instance_uid'] for row in result['instances']]==['2.25.500','2.25.501','2.25.502']


def test_inconsistent_declared_spacing_is_still_refused():
    data=items()
    data[0]['00180088']=tag(1,'DS')
    with pytest.raises(HTTPException) as caught:
        validate(data)
    assert caught.value.status_code==422
    assert caught.value.detail['reason']=='inconsistent_declared_slice_spacing'


def test_masked_out_pixels_and_metadata_revision_stable_under_archive_reordering():
    data=items()
    result=service.validate_series(SimpleNamespace(allow_pixel_read=False),data,STUDY,SERIES,
                                   [r['00080018']['Value'][0] for r in data])
    assert all('7FE00010' not in row['metadata'] for row in result['instances'])
    assert result['metadata_sha256']==validate(list(reversed(data)))['metadata_sha256']


def test_negative_orientation_preserves_physical_sort():
    data=items()
    for item in data:item['00200037']=tag([-.6,-.8,0,0,0,1],'DS')
    result=validate(data)
    assert [r['instance_uid'] for r in result['instances']]==['2.25.502','2.25.501','2.25.500']
    assert result['geometry']['origin_lps_mm']==[14,17,30]


def test_volume_budget_refused_before_render(monkeypatch):
    monkeypatch.setattr(service,'MAX_VOLUME_BYTES',35)
    with pytest.raises(HTTPException) as caught:validate()
    assert caught.value.status_code==413 and caught.value.detail['reason']=='series_too_large'


def test_instance_count_and_cross_page_duplicates(monkeypatch):
    class Pages:
        def query(self,*_args,**kwargs):
            offset=kwargs['offset']
            return [{'instance_uid':'2.25.'+str(1000+n)} for n in range(offset,min(offset+100,103))]
    assert len(service.archive_instance_uids(Pages(),STUDY,SERIES))==103
    class Repeated:
        def query(self,*_args,**_kwargs):
            return [{'instance_uid':'2.25.'+str(1000+n)} for n in range(100)]
    with pytest.raises(HTTPException) as caught:service.archive_instance_uids(Repeated(),STUDY,SERIES)
    assert caught.value.detail['reason']=='duplicate_series_uid'
    monkeypatch.setattr(service,'MAX_INSTANCES',102)
    with pytest.raises(HTTPException) as caught:service.archive_instance_uids(Pages(),STUDY,SERIES)
    assert caught.value.detail['reason']=='series_too_large'


def setup_tcp(archive):
    archive['series_metadata']=items()
    archive['series_instances']=[
        {'0020000D':tag(STUDY),'0020000E':tag(SERIES),'00080018':row['00080018'],
         '00080016':row['00080016'],'00200052':row['00200052']} for row in items()]


def test_real_tcp_api_whole_series_transport_redaction_no_pixels(archive):
    setup_tcp(archive)
    response=client.get(f'/pacs/studies/{STUDY}/series/{SERIES}/view-manifest')
    assert response.status_code==200,response.text
    result=response.json()['data']
    assert [r['instance_uid'] for r in result['instances']]==['2.25.500','2.25.501','2.25.502']
    assert response.headers['cache-control']=='no-store' and not result['pixel_read_enabled']
    assert 'PRIVATE_NAME_NEVER_EXPOSE' not in response.text and 'external.invalid' not in response.text
    assert not any(r['path'].endswith('/frames/1') for r in archive['requests'])
    assert sum(r['path'].endswith('/metadata') for r in archive['requests'])==2


@pytest.mark.parametrize('mode',['changed_instance_set','changed_geometry'])
def test_mid_read_changes_refused(archive,mode):
    setup_tcp(archive)
    archive['series_mode']=mode
    response=client.get(f'/pacs/studies/{STUDY}/series/{SERIES}/view-manifest')
    assert response.status_code==409,response.text
    assert response.json()['detail']['reason']=='series_changed_during_check'


def test_bad_requested_uid_before_archive(archive):
    response=client.get('/pacs/studies/1.02.3/series/2.25.4/view-manifest')
    assert response.status_code==422 and archive['requests']==[]
