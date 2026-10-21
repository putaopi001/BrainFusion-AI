import io
import nibabel as nib
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.storage import resolve_stored_path, public_upload_path, is_supported_storage_path
from app.database import SessionLocal
from app.models.mri import MRI
from app.api import upload


def test_storage_path_policy_preserves_windows_boundary_and_supports_absolute_posix():
    assert is_supported_storage_path('E:/BrainFusion-Runtime/local/users.json', platform='nt')
    assert not is_supported_storage_path('C:/outside/users.json', platform='nt')
    assert is_supported_storage_path('/run-config/local-users.json', platform='posix')
    assert not is_supported_storage_path('relative/local-users.json', platform='posix')


def test_relocated_namespace_and_traversal_not_public(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(tmp_path / 'runtime-images'))
    expected = tmp_path / 'runtime-images' / 'case_1' / 't2f.nii.gz'
    assert resolve_stored_path('uploads/case_1/t2f.nii.gz') == expected
    assert public_upload_path(expected) == '/uploads/case_1/t2f.nii.gz'
    assert public_upload_path('uploads/../outside.nii.gz') is None
    assert public_upload_path(tmp_path / 'elsewhere/uploads/file.nii.gz') is None


def test_single_upload_stores_relocated_absolute_path(tmp_path, monkeypatch):
    directory = tmp_path / 'runtime-images'
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(directory))
    monkeypatch.setattr(upload, 'UPLOAD_DIR', directory)
    client = TestClient(app)
    case_id = client.post('/cases/create', json={'patient_name': 'SYNTHETIC relocation', 'age': 50,
                           'gender': 'male', 'description': 'Isolated relocated upload'}).json()['data']['case_id']
    image = nib.Nifti1Image(np.ones((4, 4, 4), np.float32), np.eye(4))
    response = client.post(f'/upload/{case_id}', files={'file': ('sample.nii', image.to_bytes(), 'application/octet-stream')})
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        mri = db.query(MRI).filter_by(case_id=case_id).one()
        assert resolve_stored_path(mri.filepath).is_relative_to(directory)
        assert mri.web_path.startswith('/uploads/case_')
        assert client.get(f'/mri/{case_id}/volume').status_code == 200
        assert client.get(f'/mri/{case_id}').json()['data']['preview_urls']
