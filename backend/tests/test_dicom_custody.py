"""Quarantine persistence/conflict checks using explicitly synthetic Part10."""
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from app.services import dicom_custody as custody
from test_dicom_preflight import candidate, save


@pytest.fixture
def store():
    return custody.QUARANTINE_ROOT / ('SYNTHETIC-test-' + uuid4().hex)


def retain(candidate, store):
    path, _, source, review = candidate
    return custody.retain_candidate(path, source, store, review)


def counts(store):
    with sqlite3.connect(store / 'custody.sqlite3') as db:
        return tuple(db.execute('SELECT (SELECT COUNT(*) FROM instances),(SELECT COUNT(*) FROM receipts)').fetchone())


def test_restart_duplicate_and_original_bytes(candidate, store):
    path, _, source, _ = candidate
    first = retain(candidate, store)
    second = retain(candidate, store)
    assert first['disposition'] == 'quarantined'
    assert second['disposition'] == 'duplicate_quarantined'
    assert first['receipt_id'] != second['receipt_id']
    assert counts(store) == (1, 2)
    assert custody.inspect_custody(store)['integrity'] == 'verified'
    assert (store / 'objects' / (source['sha256'] + '.dcm')).read_bytes() == path.read_bytes()
    assert not first['archive_eligible'] and not first['archive_imported']
    assert first['preflight_decision'] == 'engineering_fixture_pass'
    assert not any((store / 'pending').iterdir())


def test_same_sop_different_bytes_refused(candidate, store):
    path, ds, source, review = candidate
    first = retain(candidate, store)
    ds.PixelData = b'\x01' * 12
    source['sha256'] = save(path, ds); review['source_sha256'] = source['sha256']
    with pytest.raises(custody.CustodyError, match='sop_uid_content_or_parent_conflict'):
        retain(candidate, store)
    assert counts(store) == (1, 1)
    assert custody.inspect_custody(store)['integrity'] == 'verified'
    assert len(list((store / 'objects').iterdir())) == 1
    assert first['source_sha256'] != source['sha256']


def test_series_cannot_change_study(candidate, store):
    path, ds, source, review = candidate
    retain(candidate, store)
    ds.StudyInstanceUID = source['study_uid'] = '2.25.123'
    ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID = source['sop_uid'] = '2.25.124'
    source['sha256'] = save(path, ds); review['source_sha256'] = source['sha256']
    with pytest.raises(custody.CustodyError, match='series_study_uid_conflict'):
        retain(candidate, store)
    assert counts(store) == (1, 1)


def test_claimed_uid_cannot_pollute_ledger(candidate, store):
    _, _, source, _ = candidate
    source['sop_uid'] = '2.25.999'
    with pytest.raises(custody.CustodyError, match='candidate_uid_binding_failed'):
        retain(candidate, store)
    assert not (store / 'custody.sqlite3').exists()


def test_recursive_privacy_rejection_still_quarantined_never_approved(candidate, store):
    path, ds, source, review = candidate
    ds.add_new((0x0011,0x1010), 'LO', 'PRIVATE_TEXT_NEVER_LOG')
    source['sha256'] = save(path, ds); review['source_sha256'] = source['sha256']
    receipt = retain(candidate, store)
    assert receipt['preflight_decision'] == 'rejected' and not receipt['archive_eligible']
    assert 'PRIVATE_TEXT_NEVER_LOG' not in json.dumps(receipt)
    with sqlite3.connect(store / 'custody.sqlite3') as db:
        assert 'PRIVATE_TEXT_NEVER_LOG' not in db.execute('SELECT audit_json FROM receipts').fetchone()[0]


def test_concurrent_retries_one_object_many_receipts(candidate, store):
    retain(candidate, store)  # Initialize the owned store before concurrency.
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: retain(candidate, store), range(8)))
    assert {r['disposition'] for r in results} == {'duplicate_quarantined'}
    assert counts(store) == (1, 9)
    assert len(list((store / 'objects').iterdir())) == 1
    assert custody.inspect_custody(store)['receipts'] == 9


@pytest.mark.parametrize('mode', ['missing', 'changed'])
def test_duplicate_checks_existing_object_integrity(candidate, store, mode):
    receipt = retain(candidate, store)
    obj = store / 'objects' / (receipt['source_sha256'] + '.dcm')
    if mode == 'missing':
        obj.unlink()
        reason = 'custody_object_missing'
    else:
        data = bytearray(obj.read_bytes()); data[-1] ^= 1; obj.write_bytes(data)
        reason = 'custody_object_integrity_failed'
    with pytest.raises(custody.CustodyError, match=reason):
        retain(candidate, store)
    assert counts(store) == (1, 1)


def test_orphan_complete_object_adopted_after_interrupted_commit(candidate, store):
    receipt = retain(candidate, store)
    with sqlite3.connect(store / 'custody.sqlite3') as db:
        db.execute('DELETE FROM receipts'); db.execute('DELETE FROM instances'); db.execute('DELETE FROM series')
    obj = store / 'objects' / (receipt['source_sha256'] + '.dcm')
    timestamp = obj.stat().st_mtime_ns
    assert retain(candidate, store)['disposition'] == 'quarantined'
    assert obj.stat().st_mtime_ns == timestamp
    assert custody.inspect_custody(store)['instances'] == 1


def test_hash_mismatch_before_store_creation(candidate, store):
    _, _, source, _ = candidate
    source['sha256'] = '0' * 64
    with pytest.raises(custody.CustodyError, match='candidate_manifest_hash_mismatch'):
        retain(candidate, store)
    assert not store.exists()


def test_unowned_directory_not_modified(candidate, store):
    store.mkdir(parents=True); (store / 'user.txt').write_text('keep')
    with pytest.raises(custody.CustodyError, match='quarantine_directory_not_owned'):
        retain(candidate, store)
    assert sorted(p.name for p in store.iterdir()) == ['user.txt']


def test_audit_tampering_detected(candidate, store):
    retain(candidate, store)
    with sqlite3.connect(store / 'custody.sqlite3') as db:
        db.execute("UPDATE receipts SET audit_json='{}'")
    with pytest.raises(custody.CustodyError, match='custody_audit_integrity_failed'):
        custody.inspect_custody(store)


def test_cross_process_retries_and_read_only_restart(candidate, store):
    path, _, source, _ = candidate
    retain(candidate, store)
    manifest = path.with_suffix('.source.json')
    manifest.write_text(json.dumps(source), encoding='utf-8')
    tool = Path(__file__).resolve().parents[1] / 'tools/retain_dicom_candidate.py'
    cmd = [sys.executable, str(tool), '--store', str(store), '--input', str(path),
           '--source-manifest', str(manifest)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(lambda _: subprocess.run(cmd, capture_output=True, text=True), range(4)))
    assert all(p.returncode == 0 and not p.stderr for p in outputs)
    assert all(json.loads(p.stdout)['disposition'] == 'duplicate_quarantined' for p in outputs)
    restarted = subprocess.run([sys.executable, str(tool), '--store', str(store), '--inspect'],
                               capture_output=True, text=True)
    assert restarted.returncode == 0 and json.loads(restarted.stdout)['receipts'] == 5
    assert counts(store) == (1, 5)


@pytest.mark.parametrize('mode', ['manifest','audit_binding','parent','missing_receipt','object_name'])
def test_metadata_corruption_detected(candidate, store, mode):
    retain(candidate, store)
    with sqlite3.connect(store / 'custody.sqlite3') as db:
        if mode == 'manifest':
            source = dict(candidate[2]); source['sop_uid'] = '2.25.888'
            db.execute('UPDATE receipts SET manifest_json=?', (json.dumps(source),))
        elif mode == 'audit_binding':
            audit = json.loads(db.execute('SELECT audit_json FROM receipts').fetchone()[0])
            audit['archive_eligible'] = True
            text = json.dumps(audit)
            db.execute('UPDATE receipts SET audit_json=?,audit_sha256=?', (text, hashlib.sha256(text.encode()).hexdigest()))
        elif mode == 'parent':
            db.execute("UPDATE series SET study_uid='2.25.888'")
        elif mode == 'missing_receipt':
            db.execute('DELETE FROM receipts')
        else:
            db.execute("UPDATE instances SET object_name='../outside.dcm'")
    with pytest.raises(custody.CustodyError):
        custody.inspect_custody(store)


def test_restore_snapshot_in_fresh_owned_store(candidate, store):
    import shutil
    retain(candidate, store)
    retain(candidate, store)
    restored = custody.QUARANTINE_ROOT / ('SYNTHETIC-restore-' + uuid4().hex)
    shutil.copytree(store, restored)
    assert custody.inspect_custody(restored) == custody.inspect_custody(store)
    assert retain(candidate, restored)['disposition'] == 'duplicate_quarantined'
    assert counts(store) == (1, 2) and counts(restored) == (1, 3)
