from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_public_viewing_patient_can_preserve_unknown_clinical_age():
    response = client.post('/patients/', json={
        'name': 'public-viewing-only', 'age': None, 'gender': 'unknown'})
    assert response.status_code == 200
    patient = response.json()['data']
    assert patient['age'] is None
    assert patient['gender'] == 'unknown'
    saved = client.get('/patients/').json()['data']
    assert next(row for row in saved if row['id'] == patient['id'])['age'] is None


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


def test_doctor_opinion_round_trip_and_survival_unavailable():
    patient_id = client.post('/patients/', json={'name': 'Opinion test', 'age': 50, 'gender': 'male'}).json()['data']['id']
    created = client.post('/cases/create', json={'patient_id': patient_id, 'description': 'Opinion validation'})
    assert created.status_code == 200, created.text
    case_id = created.json()['data']['case_id']
    response = client.put(f'/cases/{case_id}/doctor-opinion', json={'author': 'Reviewer', 'content': 'Reviewed engineering sample'})
    assert response.status_code == 200
    opinion = client.get(f'/cases/{case_id}/doctor-opinion').json()['data']
    assert opinion['author'] == 'Reviewer' and opinion['content'] == 'Reviewed engineering sample'
    assert client.get(f'/cases/{case_id}/survival').status_code == 503


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
