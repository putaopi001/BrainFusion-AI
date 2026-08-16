import os
from pathlib import Path

# 必须在导入 app 之前设置，切换到独立测试库，避免污染开发库
TEST_DB = Path(__file__).resolve().parents[1] / "test_brainfusion.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = "sqlite:///./test_brainfusion.db"

import pytest
from fastapi.testclient import TestClient

from app.database import engine
from app.main import app


client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["version"] == "0.1.0"


def test_debug_system():
    resp = client.get("/debug/system")
    assert resp.status_code == 200
    assert resp.json()["data"]["version"]


def test_create_patient_and_case():
    resp = client.post("/patients/", json={"name": "测试患者", "age": 50, "gender": "male"})
    assert resp.status_code == 200
    patient_id = resp.json()["data"]["id"]

    resp = client.post("/cases/create", json={"patient_id": patient_id, "description": "测试病例"})
    assert resp.status_code == 200
    case_id = resp.json()["data"]["case_id"]
    assert case_id > 0


def test_get_cases():
    resp = client.get("/cases/")
    assert resp.status_code == 200
    assert resp.json()["code"] == 200


def test_mri_not_found_unified_error():
    resp = client.get("/mri/999999")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 404
    assert "detail" in body


def test_delete_all_annotations():
    from app.database import SessionLocal
    from app.models.mri import MRI

    resp = client.post("/patients/", json={"name": "标注测试患者", "age": 40, "gender": "female"})
    patient_id = resp.json()["data"]["id"]
    resp = client.post("/cases/create", json={"patient_id": patient_id, "description": "标注测试病例"})
    case_id = resp.json()["data"]["case_id"]

    db = SessionLocal()
    mri = MRI(case_id=case_id, filename="test.nii", filepath="uploads/case_test/test.nii", status="preview_ready")
    db.add(mri)
    db.commit()
    db.refresh(mri)
    db.close()

    base = "/mri/" + str(case_id) + "/annotations"
    client.post(base, json={"view": "axial", "slice_index": 0, "tool": "point", "x": 0.1, "y": 0.2})
    client.post(base, json={"view": "axial", "slice_index": 0, "tool": "rectangle", "x": 0.3, "y": 0.4, "width": 0.2, "height": 0.1})

    resp = client.delete(base)
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] == 2

    resp = client.get(base)
    assert resp.json()["data"] == []
