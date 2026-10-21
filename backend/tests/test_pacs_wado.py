"""Synthetic MR JSON and TCP MIME transport. Never a real DICOM/Orthanc claim."""
import copy
import json
import struct
import pytest

from test_pacs import archive, client, tag, STUDY, SERIES, INSTANCE, FRAME, SECRET
from app.services.pacs_wado import EXPLICIT_LE

PATH = f'/pacs/studies/{STUDY}/series/{SERIES}/instances/{INSTANCE}'
SAMPLES = [-1000,0,1024,30000,-2,2573]  # Final LE bytes CRLF must be preserved.
PIXELS = struct.pack('<6h', *SAMPLES)


def multipart(pixels, boundary='SYNTHETIC-fixture-boundary', part_type='application/octet-stream', syntax=None, extra=b''):
    content_type = f'multipart/related; type="application/octet-stream"; boundary="{boundary}"'
    if syntax: content_type += '; transfer-syntax=' + syntax
    body = ('--'+boundary+'\r\nContent-Type: '+part_type+'\r\n\r\n').encode() + pixels + b'\r\n' + extra + ('--'+boundary+'--\r\n').encode()
    return body, content_type


@pytest.fixture
def wado(archive):
    item = {'00080008':tag(['ORIGINAL','PRIMARY'],'CS'),'0020000D':tag(STUDY),'0020000E':tag(SERIES),'00080018':tag(INSTANCE),
            '00080016':tag('1.2.840.10008.5.1.4.1.1.4'),'00080060':tag('MR','CS'),'00200052':tag(FRAME),
            '00200032':tag([10.,20.,-30.],'DS'),'00200037':tag([0.,-1.,0.,1.,0.,0.],'DS'),
            '00280030':tag([3.25,2.0],'DS'),'00280010':tag(2,'US'),'00280011':tag(3,'US'),
            '00280002':tag(1,'US'),'00280004':tag('MONOCHROME2','CS'),'00280100':tag(16,'US'),
            '00280101':tag(16,'US'),'00280102':tag(15,'US'),'00280103':tag(1,'US'),
            '00281052':tag(-10.0,'DS'),'00281053':tag(2.,'DS'),'00281050':tag([40.,80.],'DS'),'00281051':tag([400.,800.],'DS'),
            '00100010':{'vr':'PN','Value':[{'Alphabetic':'PRIVATE-SYNTHETIC-DO-NOT-FORWARD'}]},
            '00100020':tag('PRIVATE-SYNTHETIC-ID','LO'),'0008103E':tag('t1 name is not role proof','LO'),
            '00110010':tag('PRIVATE CREATOR','LO'),'7FE00010':{'vr':'OW','BulkDataURI':'https://external.invalid/'+SECRET}}
    archive['metadata'] = [item]
    archive['frame_body'],archive['frame_type'] = multipart(PIXELS)
    archive['config']['allow_pixel_read'] = True
    archive['path'].write_text(json.dumps(archive['config']),encoding='utf-8')
    return archive


def extract_response_pixels(response):
    # Independent delimiter extraction, rather than the implementation's MIME parser.
    return response.content.split(b'\r\n\r\n',1)[1].rsplit(b'\r\n--',1)[0]


@pytest.mark.parametrize('syntax,expected_status', [
    (EXPLICIT_LE, 200), ('1.2.840.10008.1.2.2', 502), ('1.2.840.10008.1.2.4.50', 502)])
def test_orthanc_124_nested_type_transfer_syntax(wado, syntax, expected_status):
    wado['frame_body'], _ = multipart(PIXELS,
        part_type='application/octet-stream; transfer-syntax=' + EXPLICIT_LE)
    wado['frame_type'] = ('multipart/related; type="application/octet-stream; transfer-syntax='
        + syntax + '"; boundary="SYNTHETIC-fixture-boundary"')
    response = client.get(PATH + '/frames/1')
    assert response.status_code == expected_status
    if expected_status == 200:
        assert extract_response_pixels(response) == PIXELS


def test_metadata_identifies_geometry_without_private_fields_or_external_urls(wado):
    response = client.get(PATH+'/metadata')
    assert response.status_code == 200, response.text
    assert response.headers['content-type'].startswith('application/dicom+json')
    assert response.headers['cache-control'] == 'no-store'
    item = response.json()[0]
    assert item['00200032']['Value'] == [10.,20.,-30.]
    assert item['00200037']['Value'] == [0.,-1.,0.,1.,0.,0.]
    assert item['00280030']['Value'] == [3.25,2.]
    assert item['00281050']['Value'] == [40.,80.]
    assert item['7FE00010']['BulkDataURI'] == PATH+'/frames/1'
    assert all(t not in item for t in ('00100010','00100020','00110010','0008103E'))
    assert SECRET not in response.text and 'external.invalid' not in response.text
    assert wado['requests'][-1]['path'].endswith('/metadata')


def test_actual_tcp_frame_bit_exact_little_endian_and_intensity_scale(wado):
    response = client.get(PATH+'/frames/1',headers={'Authorization':'browser-secret','Cookie':'browser-cookie'})
    assert response.status_code == 200, response.text
    pixels = extract_response_pixels(response)
    assert pixels == PIXELS and struct.unpack('<6h',pixels) == tuple(SAMPLES)
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['content-type'].startswith('multipart/related')
    assert EXPLICIT_LE in response.headers['content-type']
    assert [v*2.-10. for v in struct.unpack('<6h',pixels)] == [-2010.,-10.,2038.,59990.,-14.,5136.]
    assert all(r['cookie'] is None for r in wado['requests'])
    assert EXPLICIT_LE in wado['requests'][-1]['accept']
    assert [r['path'] for r in wado['requests']] == ['/system','/system',PATH.replace('/pacs','/dicom-web')+'/metadata',PATH.replace('/pacs','/dicom-web')+'/frames/1']


def test_unsigned_eight_bit_monochrome_one_no_implicit_inversion(wado):
    item = wado['metadata'][0]
    item['00280100'] = tag(8,'US'); item['00280101'] = tag(8,'US'); item['00280102'] = tag(7,'US')
    item['00280103'] = tag(0,'US'); item['00280004'] = tag('MONOCHROME1','CS')
    pixels = bytes([0,7,127,128,254,255])
    wado['frame_body'], wado['frame_type'] = multipart(pixels,syntax=EXPLICIT_LE)
    response = client.get(PATH+'/frames/1')
    assert response.status_code == 200, response.text
    assert extract_response_pixels(response) == pixels
    metadata = client.get(PATH+'/metadata').json()[0]
    assert metadata['00280004']['Value'] == ['MONOCHROME1'] and metadata['7FE00010']['vr'] == 'OB'


def test_default_closed_before_archive_request_and_metadata_has_no_bulk_uri(wado):
    del wado['config']['allow_pixel_read']
    wado['path'].write_text(json.dumps(wado['config']),encoding='utf-8')
    response = client.get(PATH+'/frames/1')
    assert response.status_code == 503 and response.json()['detail']['reason'] == 'pixel_read_disabled'
    assert wado['requests'] == []
    assert client.get('/pacs/status').json()['data']['pixel_read_enabled'] is False
    assert '7FE00010' not in client.get(PATH+'/metadata').json()[0]


@pytest.mark.parametrize('mode,reason', [('parent','uid_mismatch'),('instance','uid_mismatch'),('missing_uid','invalid_geometry_metadata'),
    ('orientation','invalid_geometry_metadata'),('spacing','invalid_geometry_metadata'),('position','invalid_geometry_metadata'),
    ('vr','invalid_geometry_metadata'),('bulk_numeric','invalid_geometry_metadata'),('multiframe','unsupported_multiframe'),
    ('enhanced','unsupported_sop_class'),('bits','unsupported_pixel_layout'),('color','unsupported_pixel_layout'),
    ('highbit','unsupported_pixel_layout'),('huge','frame_too_large'),('slope','invalid_geometry_metadata'),('two','invalid_metadata'),
    ('mosaic','unsupported_mosaic'),('missing_image_type','invalid_geometry_metadata')])
def test_bad_geometry_refuses_before_pixel_request(wado,mode,reason):
    item = wado['metadata'][0]
    if mode == 'parent': item['0020000E'] = tag('1.2.3.888')
    if mode == 'instance': item['00080018'] = tag('1.2.3.888')
    if mode == 'missing_uid': del item['00080018']
    if mode == 'orientation': item['00200037'] = tag([1.,0.,0.,1.,0.,0.],'DS')
    if mode == 'spacing': item['00280030'] = tag([0.,2.],'DS')
    if mode == 'position': item['00200032'] = tag(['NaN',20.,30.],'DS')
    if mode == 'vr': item['00280010']['vr'] = 'DS'
    if mode == 'bulk_numeric': item['00280030'] = {'vr':'DS','BulkDataURI':'https://external.invalid'}
    if mode == 'multiframe': item['00280008'] = tag(2,'IS')
    if mode == 'enhanced': item['00080016'] = tag('1.2.840.10008.5.1.4.1.1.4.1')
    if mode == 'bits': item['00280100'] = tag(32,'US')
    if mode == 'color': item['00280004'] = tag('RGB','CS')
    if mode == 'highbit': item['00280102'] = tag(14,'US')
    if mode == 'huge': item['00280010'] = tag(65535,'US'); item['00280011'] = tag(65535,'US')
    if mode == 'slope': item['00281053'] = tag(0,'DS')
    if mode == 'two': wado['metadata'] *= 2
    if mode == 'mosaic': item['00080008'] = tag(['ORIGINAL','PRIMARY','M','ND','MOSAIC'],'CS')
    if mode == 'missing_image_type': del item['00080008']
    response = client.get(PATH+'/frames/1')
    assert response.status_code in (413,422,502), response.text
    assert response.json()['detail']['reason'] == reason
    assert not any(r['path'].endswith('/frames/1') for r in wado['requests'])


@pytest.mark.parametrize('mode,reason', [('truncated','frame_length_mismatch'),('extra','frame_length_mismatch'),
    ('jpeg','unsupported_frame_encoding'),('big_endian','unsupported_frame_encoding'),('base64','unsupported_frame_encoding'),
    ('two_parts','invalid_frame_response'),('missing_close','invalid_frame_response'),('oversized','frame_response_too_large'),
    ('redirect','upstream_error'),('html','unsupported_frame_encoding'),('duplicate_mime','unsupported_frame_encoding')])
def test_invalid_frame_transport_never_succeeds(wado,mode,reason):
    if mode == 'truncated': wado['frame_body'],wado['frame_type'] = multipart(PIXELS[:-1])
    if mode == 'extra': wado['frame_body'],wado['frame_type'] = multipart(PIXELS+b'x')
    if mode == 'jpeg': wado['frame_body'],wado['frame_type'] = multipart(PIXELS,part_type='image/jpeg')
    if mode == 'big_endian': wado['frame_body'],wado['frame_type'] = multipart(PIXELS,syntax='1.2.840.10008.1.2.2')
    if mode == 'base64': wado['frame_body'] = wado['frame_body'].replace(b'\r\n\r\n',b'\r\nContent-Transfer-Encoding: base64\r\n\r\n',1)
    if mode == 'two_parts':
        extra = b'--SYNTHETIC-fixture-boundary\r\nContent-Type: application/octet-stream\r\n\r\n'+PIXELS+b'\r\n'
        wado['frame_body'],wado['frame_type'] = multipart(PIXELS,extra=extra)
    if mode == 'missing_close': wado['frame_body'] = wado['frame_body'].rsplit(b'--SYNTHETIC-fixture-boundary--',1)[0]
    if mode == 'oversized': wado['frame_body'] = b'x' * 20000
    if mode == 'redirect': wado['frame_status'] = 302
    if mode == 'html': wado['frame_type'] = 'text/html'
    if mode == 'duplicate_mime': wado['frame_body'] = wado['frame_body'].replace(b'\r\n\r\n',b'\r\nContent-Type: image/jpeg\r\n\r\n',1)
    response = client.get(PATH+'/frames/1')
    assert response.status_code == 502, response.text
    assert response.json()['detail']['reason'] == reason
    assert SECRET not in response.text


def test_only_frame_one_and_valid_uid_allowed_without_upstream(wado):
    for frame in ['0','2','abc']:
        assert client.get(PATH+'/frames/'+frame).status_code == 422
    assert client.get(PATH.replace(INSTANCE,'1.02.3')+'/metadata').status_code == 422
    assert wado['requests'] == []


def test_pixel_enable_requires_boolean_config(wado):
    wado['config']['allow_pixel_read'] = 'true'
    wado['path'].write_text(json.dumps(wado['config']),encoding='utf-8')
    assert client.get(PATH+'/frames/1').json()['detail']['reason'] == 'invalid_config'
    assert wado['requests'] == []
