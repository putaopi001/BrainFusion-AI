"""Strict classic single-frame MR transport, without registration/resampling/AI."""
import math
import hashlib
import json
import re
from email import policy
from email.message import Message
from email.parser import BytesParser
from uuid import uuid4

import httpx
from app.services.pacs_client import fail, metadata_uid, validate_uid

MR_CLASS = '1.2.840.10008.5.1.4.1.1.4'
EXPLICIT_LE = '1.2.840.10008.1.2.1'
MAX_FRAME_BYTES = 32 * 1024 * 1024
HEADER_BUDGET = 16384


def metadata_revision(item):
    clean={tag:value for tag,value in item.items() if tag!='7FE00010'}
    return hashlib.sha256(json.dumps(clean,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def instance_path(study, series, instance):
    return '/dicom-web/studies/' + validate_uid(study) + '/series/' + validate_uid(series) + '/instances/' + validate_uid(instance)


def values(item, tag, vr, count=None, optional=False):
    attr = item.get(tag)
    if attr is None and optional:
        return None
    if (not isinstance(attr, dict) or attr.get('vr') != vr or set(attr) != {'vr', 'Value'}
            or not isinstance(attr.get('Value'), list) or not attr['Value']
            or (count is not None and len(attr['Value']) != count)):
        fail('invalid_geometry_metadata', '实例的空间或像素元数据缺失、VR或值格式错误。', 502)
    return attr['Value']


def numbers(item, tag, vr, count=1, optional=False, integer=False):
    raw = values(item, tag, vr, count, optional)
    if raw is None:
        return None
    try:
        result = [float(v) for v in raw if not isinstance(v, bool)]
        if len(result) != len(raw) or not all(math.isfinite(v) for v in result):
            raise ValueError()
        if integer and not all(v.is_integer() for v in result):
            raise ValueError()
        return [int(v) for v in result] if integer else result
    except (ValueError, TypeError, OverflowError):
        fail('invalid_geometry_metadata', '实例含非有限或不合法的空间/像素数值。', 502)


def checked_metadata(archive, study, series, instance):
    raw = archive._json(instance_path(study, series, instance) + '/metadata')
    if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
        fail('invalid_metadata', '单实例 WADO 元数据必须恰好包含一个实例。', 502)
    return checked_metadata_item(archive.config, raw[0], study, series, instance)


def checked_metadata_item(config, item, study, series, instance):
    """Reuse exactly the single-frame guard for whole-series metadata."""
    if not isinstance(item, dict):
        fail('invalid_metadata', '实例 WADO 元数据格式错误。', 502)
    for tag, expected in [('0020000D', study), ('0020000E', series), ('00080018', instance)]:
        values(item, tag, 'UI', 1)
        if metadata_uid(item, tag) != expected:
            fail('uid_mismatch', 'WADO 实例 UID 与请求的检查/序列/实例不一致。', 502)
    values(item, '00080016', 'UI', 1)
    if metadata_uid(item, '00080016') != MR_CLASS or values(item, '00080060', 'CS', 1) != ['MR']:
        fail('unsupported_sop_class', '当前像素读取仅支持经典单帧 MR Image Storage。', 422)
    image_type = values(item, '00080008', 'CS')
    if len(image_type) > 16 or not all(isinstance(v,str) and re.fullmatch(r'[A-Z0-9_ ]{1,64}',v) for v in image_type):
        fail('invalid_geometry_metadata', 'MR ImageType 格式错误，无法确认支持的图像布局。', 502)
    if any('MOSAIC' in v for v in image_type):
        fail('unsupported_mosaic', '当前未支持MOSAIC拼块图像，不能将其作为普通空间切片读取或输入模型。', 422)
    frames = numbers(item, '00280008', 'IS', optional=True, integer=True)
    if frames is not None and frames != [1]:
        fail('unsupported_multiframe', '当前读取未支持多帧实例，请保留原检查待处理。', 422)
    values(item, '00200052', 'UI', 1); metadata_uid(item, '00200052')
    position = numbers(item, '00200032', 'DS', 3)
    orientation = numbers(item, '00200037', 'DS', 6)
    spacing = numbers(item, '00280030', 'DS', 2)
    if any(v <= 0 for v in spacing):
        fail('invalid_geometry_metadata', 'PixelSpacing 必须为有限正毫米数。', 502)
    a, b = orientation[:3], orientation[3:]
    if (abs(sum(v*v for v in a)-1) > 1e-4 or abs(sum(v*v for v in b)-1) > 1e-4
            or abs(sum(x*y for x,y in zip(a,b))) > 1e-4):
        fail('invalid_geometry_metadata', 'ImageOrientationPatient 必须为正交单位方向，未自动校正。', 502)
    # Preserve original DICOM DS values and ordering, including oblique/negative directions.
    rows = numbers(item, '00280010', 'US', integer=True)[0]
    cols = numbers(item, '00280011', 'US', integer=True)[0]
    samples = numbers(item, '00280002', 'US', integer=True)[0]
    allocated = numbers(item, '00280100', 'US', integer=True)[0]
    stored = numbers(item, '00280101', 'US', integer=True)[0]
    high = numbers(item, '00280102', 'US', integer=True)[0]
    representation = numbers(item, '00280103', 'US', integer=True)[0]
    photo = values(item, '00280004', 'CS', 1)
    if (rows <= 0 or cols <= 0 or samples != 1 or allocated not in (8,16) or not 1 <= stored <= allocated
            or high != stored-1 or representation not in (0,1) or photo[0] not in ('MONOCHROME1','MONOCHROME2')):
        fail('unsupported_pixel_layout', '当前仅支持单通道8/16位、低位对齐的单色 MR 像素，未转换不支持的布局。', 422)
    expected = rows * cols * (allocated // 8)
    if expected > MAX_FRAME_BYTES:
        fail('frame_too_large', '单帧像素超过32MiB读取上限。', 413)
    required = ['00080008','00080016','00080018','00080060','0020000D','0020000E','00200052','00200032','00200037',
                '00280030','00280010','00280011','00280002','00280004','00280100','00280101','00280102','00280103']
    result = {tag: item[tag] for tag in required}
    result['00280008'] = {'vr':'IS','Value':[1]}
    # Optional numeric presentation values are allowed; names, private tags and external URLs are not.
    for tag, vr, positive in [('00180050','DS',True),('00180088','DS',False),('00281052','DS',False),
                               ('00281053','DS',False),('00281050','DS',False),('00281051','DS',True)]:
        if tag not in item:
            continue
        vals = numbers(item, tag, vr, count=None, optional=True)
        if len(vals) > 16 or (positive and any(v <= 0 for v in vals)) or (tag == '00281053' and (len(vals) != 1 or vals[0] == 0)):
            fail('invalid_geometry_metadata', '实例的窗值、层厚或强度缩放参数不合法。', 502)
        if tag not in ('00281050','00281051') and len(vals) != 1:
            fail('invalid_geometry_metadata', '实例缩放/层厚参数必须为单值。', 502)
        result[tag] = item[tag]
    if config.allow_pixel_read:
        result['7FE00010'] = {'vr':'OW' if allocated == 16 else 'OB', 'BulkDataURI':
            '/pacs/studies/' + study + '/series/' + series + '/instances/' + instance + '/frames/1'}
    return result, expected


def frame_bytes(archive, study, series, instance, expected):
    accept = 'multipart/related; type="application/octet-stream"; transfer-syntax=' + EXPLICIT_LE
    path = instance_path(study, series, instance) + '/frames/1'
    try:
        with archive.http.stream('GET', path, headers={'Accept':accept,'Accept-Encoding':'identity'}) as response:
            if response.status_code == 404:
                fail('not_found', '指定实例的帧不存在。', 404)
            if response.status_code in (401,403):
                fail('authentication_failed', '本地 PACS 服务端凭据未通过鉴权。')
            if response.status_code != 200:
                fail('upstream_error', '归档没有返回完整的单帧像素。', 502)
            if response.headers.get('content-encoding','identity').lower() != 'identity':
                fail('unsupported_frame_encoding', '当前帧传输不接受额外HTTP内容压缩。', 502)
            mime = response.headers.get('content-type','')
            if len(mime) > 512 or any(c in mime for c in '\r\n') or any(ord(c) > 127 for c in mime):
                fail('invalid_frame_response', '像素响应 MIME 头不合法。', 502)
            body = bytearray()
            for chunk in response.iter_bytes(chunk_size=65536):
                body.extend(chunk)
                if len(body) > expected + HEADER_BUDGET:
                    fail('frame_response_too_large', '像素响应超出预期帧及头部上限。', 502)
    except httpx.HTTPError:
        fail('unavailable', '读取本地归档像素失败，请重试或检查服务。')
    header = Message(); header['Content-Type'] = mime
    boundary = header.get_param('boundary')
    parameters = [key.lower() for key,_ in header.get_params()[1:]]
    # Orthanc DICOMweb 1.24 includes transfer-syntax inside the quoted type
    # parameter. Parse that media type independently instead of rejecting a
    # valid uncompressed response or stripping parameters indiscriminately.
    media_type = header.get_param('type')
    inner = Message()
    inner['Content-Type'] = media_type if isinstance(media_type, str) else ''
    inner_parameters = [key.lower() for key,_ in inner.get_params()[1:]]
    if (header.get_content_type() != 'multipart/related' or inner.get_content_type() != 'application/octet-stream'
            or any(key != 'transfer-syntax' for key in inner_parameters)
            or len(inner_parameters) != len(set(inner_parameters))
            or inner.get_param('transfer-syntax') not in (None, EXPLICIT_LE)
            or not isinstance(boundary,str) or not re.fullmatch(r"[a-zA-Z0-9'()+_,./:=? -]{1,70}",boundary)
            or boundary.endswith(' ') or len(parameters) != len(set(parameters))
            or header.get_param('transfer-syntax') not in (None,EXPLICIT_LE)):
        fail('unsupported_frame_encoding', '当前只接受单帧未压缩Little Endian的WADO multipart响应。', 502)
    parsed = BytesParser(policy=policy.default).parsebytes(('Content-Type: '+mime+'\r\n\r\n').encode('ascii') + body)
    parts = list(parsed.iter_parts()) if parsed.is_multipart() else []
    if parsed.defects or len(parts) != 1 or parts[0].defects:
        fail('invalid_frame_response', 'WADO multipart必须完整且恰好包含一个像素帧。', 502)
    part = parts[0]
    if (part.get_content_type() != 'application/octet-stream' or part.get_param('transfer-syntax') not in (None,EXPLICIT_LE)
            or len(part.get_all('Content-Type',[])) != 1 or len(part.get_all('Content-Transfer-Encoding',[])) > 1
            or part.get('Content-Transfer-Encoding') not in (None,'binary')):
        fail('unsupported_frame_encoding', '像素帧编码不符合请求的未压缩Little Endian契约。', 502)
    pixels = part.get_payload(decode=True)
    if not isinstance(pixels,bytes) or len(pixels) != expected:
        fail('frame_length_mismatch', '像素长度与Rows/Columns/BitsAllocated不一致，未截断或补齐。', 502)
    return pixels


def multipart_response(pixels):
    boundary = 'brainfusion_' + uuid4().hex
    while boundary.encode() in pixels:
        boundary = 'brainfusion_' + uuid4().hex
    content = (('--'+boundary+'\r\nContent-Type: application/octet-stream; transfer-syntax='+EXPLICIT_LE+'\r\n\r\n').encode()
               + pixels + ('\r\n--'+boundary+'--\r\n').encode())
    return content, 'multipart/related; type="application/octet-stream"; transfer-syntax='+EXPLICIT_LE+'; boundary='+boundary
