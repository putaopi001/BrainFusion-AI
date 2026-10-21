"""Whole-series classic MR geometry, without resampling or inferred model roles."""
import hashlib
import json
import math
from datetime import datetime, timezone
from time import perf_counter
from app.services.pacs_client import fail, metadata_uid, validate_uid
from app.services.pacs_wado import checked_metadata_item, numbers, metadata_revision

MAX_INSTANCES = 512
MAX_VOLUME_BYTES = 256 * 1024 * 1024
ORIENTATION_TOL = 1e-5
POSITION_TOL_MM = 1e-3
SPACING_ABS_TOL_MM = 1e-3
SPACING_REL_TOL = 1e-4


def dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def close(a, b):
    return abs(a-b) <= max(SPACING_ABS_TOL_MM,SPACING_REL_TOL*max(abs(a),abs(b)))


def archive_instance_uids(archive, study, series):
    result, seen, offset = [], set(), 0
    while True:
        page = archive.query('instances',study,series,limit=100,offset=offset)
        for item in page:
            uid = validate_uid(item['instance_uid'])
            if uid in seen:
                fail('duplicate_series_uid','归档分页重复，无法确认完整序列。',409)
            seen.add(uid); result.append(uid)
            if len(result)>MAX_INSTANCES:
                fail('series_too_large','序列超过512实例读取上限。',413)
        if len(page)<100: return result
        offset += 100


def validate_series(config, raw, study, series, expected_uids):
    validate_uid(study); validate_uid(series)
    if (not isinstance(raw,list) or not raw or len(raw)>MAX_INSTANCES
            or not expected_uids or len(expected_uids)>MAX_INSTANCES):
        fail('invalid_series_metadata','序列元数据为空或超过支持范围。',502)
    if len(set(expected_uids))!=len(expected_uids):
        fail('duplicate_series_uid','实例集合含重复UID。',409)
    rows,seen,total_bytes = [],set(),0
    for item in raw:
        uid = metadata_uid(item,'00080018') if isinstance(item,dict) else None
        if uid is None: fail('invalid_series_metadata','实例元数据缺失。',502)
        if uid in seen: fail('duplicate_series_uid','序列元数据含重复实例UID。',409)
        seen.add(uid)
        metadata,size = checked_metadata_item(config,item,study,series,uid)
        total_bytes += size
        if total_bytes>MAX_VOLUME_BYTES:
            fail('series_too_large','未压缩像素超过256MiB阅片上限。',413)
        rows.append({'instance_uid':uid,'metadata':metadata,'metadata_sha256':metadata_revision(metadata)})
    if seen!=set(expected_uids):
        fail('series_instance_set_mismatch','QIDO实例集合与序列元数据不一致，拒绝不完整加载。',409)
    if len(rows)<2:
        fail('single_plane_volume_unavailable','单层实例不能建立三维序列，至少需要两层。',422)
    # Stable reference when the archive changes response order within tolerances.
    first=min(rows,key=lambda row:row['instance_uid'])['metadata']
    orientation=numbers(first,'00200037','DS',6)
    a,b=orientation[:3],orientation[3:]
    cross=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    magnitude=math.sqrt(dot(cross,cross))
    normal=[v/magnitude for v in cross]  # Projection only; original IOP is retained.
    frame=metadata_uid(first,'00200052')
    spacing=numbers(first,'00280030','DS',2)
    layout=['00280010','00280011','00280002','00280004','00280100','00280101','00280102','00280103']
    for row in rows:
        item=row['metadata']
        if metadata_uid(item,'00200052')!=frame:
            fail('mixed_frame_of_reference','序列包含不同FrameOfReference，未自动配准。',422)
        current=numbers(item,'00200037','DS',6)
        if any(abs(x-y)>ORIENTATION_TOL for x,y in zip(current,orientation)):
            fail('mixed_series_orientation','切片方向不一致，未自动校正。',422)
        if any(not close(x,y) for x,y in zip(numbers(item,'00280030','DS',2),spacing)):
            fail('mixed_pixel_spacing','切片像素间距不一致，未重采样。',422)
        if any(item[tag]['Value']!=first[tag]['Value'] for tag in layout):
            fail('mixed_series_pixel_layout','序列像素矩阵或位布局不一致。',422)
        row['position_lps_mm']=numbers(item,'00200032','DS',3)
        row['projection_mm']=dot(row['position_lps_mm'],normal)
    rows.sort(key=lambda row:row['projection_mm'])  # Never InstanceNumber/filename.
    origin=rows[0]['position_lps_mm']; start=rows[0]['projection_mm']
    for row in rows:
        delta=[x-y for x,y in zip(row['position_lps_mm'],origin)]
        along=row['projection_mm']-start
        if math.sqrt(sum((x-along*n)**2 for x,n in zip(delta,normal)))>POSITION_TOL_MM:
            fail('non_rectilinear_series','层位含面内偏移，未支持剪切或自动校正。',422)
    gaps=[r['projection_mm']-l['projection_mm'] for l,r in zip(rows,rows[1:])]
    if any(gap<=POSITION_TOL_MM for gap in gaps):
        fail('duplicate_slice_position','重复或过近层位，可能含多时相/回波，未自动分组。',422)
    spacing_z=gaps[0]
    if any(not close(gap,spacing_z) for gap in gaps):
        fail('non_uniform_slice_spacing','层间距不均匀或可能缺层，未插值补层。',422)
    for row in rows:
        declared=numbers(row['metadata'],'00180088','DS',optional=True)
        if declared is not None and not close(abs(declared[0]),spacing_z):
            fail('declared_slice_spacing_mismatch','SpacingBetweenSlices与实测层间距不一致。',422)
    # pixel(row,column) = IPP + column*a*columnSpacing + row*b*rowSpacing.
    geometry={'coordinate_system':'DICOM_LPS_mm',
              'dimensions':[int(first['00280011']['Value'][0]),int(first['00280010']['Value'][0]),len(rows)],
              'pixel_spacing_row_column_mm':spacing,'spacing_xyz_mm':[spacing[1],spacing[0],spacing_z],
              'origin_lps_mm':origin,'image_orientation_patient':orientation,
              'unit_normal_for_sorting':normal,'measured_slice_gaps_mm':gaps,'frame_of_reference_uid':frame,
              'geometry_corrected':False,'registration_or_resampling':False}
    geometry['validation_tolerances']={'orientation_component':ORIENTATION_TOL,
        'in_plane_drift_mm':POSITION_TOL_MM,'spacing_absolute_mm':SPACING_ABS_TOL_MM,
        'spacing_relative':SPACING_REL_TOL}
    source_metadata=[{tag:val for tag,val in row['metadata'].items() if tag!='7FE00010'} for row in rows]
    digest=hashlib.sha256(json.dumps(source_metadata,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'format':'dicom-series-view-manifest-v1','study_uid':study,'series_uid':series,
            'instance_count':len(rows),'instances':rows,'geometry':geometry,
            'sorting_method':'ascending_IPP_projection_on_IOP_normal','metadata_sha256':digest,
            'uncompressed_pixel_bytes':total_bytes,'completeness_scope':'current_archive_UID_set_not_original_acquisition',
            'pixel_read_enabled':config.allow_pixel_read,'dicom_view_accepted':False,'model_input_eligible':False,
            'sequence_role':'unconfirmed','original_pixel_bytes_retrieved':False}


def series_manifest(archive, study, series):
    begin=perf_counter()
    uids=archive_instance_uids(archive,study,series)
    raw=archive._json('/dicom-web/studies/'+validate_uid(study)+'/series/'+validate_uid(series)+'/metadata')
    manifest=validate_series(archive.config,raw,study,series,uids)
    if set(archive_instance_uids(archive,study,series))!=set(uids):
        fail('series_changed_during_check','核对期间实例集合变化，请重新读取。',409)
    again=validate_series(archive.config,archive._json(
        '/dicom-web/studies/'+study+'/series/'+series+'/metadata'),study,series,uids)
    if again['metadata_sha256']!=manifest['metadata_sha256']:
        fail('series_changed_during_check','核对期间实例空间或呈现元数据变化，请重新读取。',409)
    system=archive._json('/system',dicom=False)
    pin=archive.config.expected_database_server_identifier
    if not isinstance(system,dict) or system.get('Version')!=archive.version:
        fail('series_changed_during_check','核对期间归档系统信息变化或不完整。',409)
    if pin is not None and system.get('DatabaseServerIdentifier')!=pin:
        fail('archive_identity_mismatch','核对期间归档服务标识变化。',409)
    manifest.update(archive_id=archive.config.archive_id,archive_fingerprint=archive.config.endpoint_fingerprint,
                    archive_server_identity_pinned=archive.config.expected_database_server_identifier is not None,
                    observed_utc=datetime.now(timezone.utc).isoformat(),
                    metadata_read_and_check_ms=(perf_counter()-begin)*1000)
    return manifest
