"""Local quarantine custody only: no PACS upload, clinical approval or business DB."""
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.services.dicom_preflight import MAX_FILE_BYTES, SourceManifest, audit_dicom
from app.core.storage import is_supported_storage_path

QUARANTINE_ROOT = Path(settings.DICOM_QUARANTINE_DIR)
FORMAT = 'dicom-quarantine-custody-v1'


class CustodyError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _root(path):
    root = Path(path).resolve()
    base = QUARANTINE_ROOT.resolve()
    if root == base or not root.is_relative_to(base):
        raise CustodyError('quarantine_path_not_supported')
    root.mkdir(parents=True, exist_ok=True)
    marker = root / 'custody-format.txt'
    if marker.is_symlink():
        raise CustodyError('quarantine_link_not_supported')
    if not marker.exists() and any(root.iterdir()):
        raise CustodyError('quarantine_directory_not_owned')
    try:
        with marker.open('x', encoding='ascii') as handle:
            handle.write(FORMAT)
    except FileExistsError:
        if marker.read_text(encoding='ascii') != FORMAT:
            raise CustodyError('quarantine_format_mismatch')
    for name in ('objects', 'pending'):
        folder = root / name
        folder.mkdir(exist_ok=True)
        if folder.resolve() != folder:
            raise CustodyError('quarantine_link_not_supported')
    if (root / 'custody.sqlite3').is_symlink():
        raise CustodyError('quarantine_link_not_supported')
    return root


def _connect(root):
    db = sqlite3.connect(root / 'custody.sqlite3', timeout=30)
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA synchronous=FULL')
    db.executescript("""
        CREATE TABLE IF NOT EXISTS instances (
            sop_uid TEXT PRIMARY KEY, study_uid TEXT NOT NULL, series_uid TEXT NOT NULL,
            source_sha256 TEXT NOT NULL, source_bytes INTEGER NOT NULL,
            object_name TEXT NOT NULL, first_received_utc TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS series (
            series_uid TEXT PRIMARY KEY, study_uid TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id TEXT PRIMARY KEY, sop_uid TEXT NOT NULL, received_utc TEXT NOT NULL,
            disposition TEXT NOT NULL, manifest_json TEXT NOT NULL,
            audit_json TEXT NOT NULL, audit_sha256 TEXT NOT NULL,
            FOREIGN KEY(sop_uid) REFERENCES instances(sop_uid));
    """)
    return db


def retain_candidate(path, source, store, pixel_review=None):
    """Retain untrusted bytes separately, and audit the exact retained snapshot.

    Source/review assertions remain unverified. All outcomes are quarantine-only.
    Identical retries create receipts without rewriting the object; conflicting
    SOP hashes or Series/Study parents fail without replacing prior custody.
    """
    pending = None
    db = None
    try:
        manifest = SourceManifest.model_validate(source)
        original = Path(path).resolve(strict=True)
        if not is_supported_storage_path(original) or not original.is_file():
            raise CustodyError('candidate_path_not_supported')
        with original.open('rb') as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise CustodyError('candidate_too_large')
        digest = hashlib.sha256(raw).hexdigest()
        if digest != manifest.sha256:
            raise CustodyError('candidate_manifest_hash_mismatch')
        root = _root(store)
        pending = root / 'pending' / (uuid4().hex + '.dcm')
        with pending.open('xb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        del raw
        audit = audit_dicom(pending, manifest.model_dump(), pixel_review)
        if audit.get('source_sha256') != digest:
            raise CustodyError('snapshot_audit_binding_failed')
        if not audit.get('source_uid_binding_verified'):
            raise CustodyError('candidate_uid_binding_failed')
        audit_text = _json(audit)
        audit_sha = hashlib.sha256(audit_text.encode('utf-8')).hexdigest()
        object_name = digest + '.dcm'
        obj = root / 'objects' / object_name
        db = _connect(root)
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute(
            'SELECT study_uid,series_uid,source_sha256,source_bytes,object_name FROM instances WHERE sop_uid=?',
            (manifest.sop_uid,)).fetchone()
        series = db.execute('SELECT study_uid FROM series WHERE series_uid=?', (manifest.series_uid,)).fetchone()
        if series and series[0] != manifest.study_uid:
            raise CustodyError('series_study_uid_conflict')
        expected = (manifest.study_uid, manifest.series_uid, digest, audit['source_bytes'], object_name)
        if previous and previous != expected:
            raise CustodyError('sop_uid_content_or_parent_conflict')
        if obj.exists():
            if obj.is_symlink() or obj.stat().st_size != audit['source_bytes']:
                raise CustodyError('custody_object_integrity_failed')
            if _hash_file(obj) != digest:
                raise CustodyError('custody_object_integrity_failed')
        elif previous:
            raise CustodyError('custody_object_missing')
        else:
            # Atomic no-replace publication on the same volume. A crash can leave
            # a complete orphan; a later retry verifies it before adoption.
            os.link(pending, obj)
        now = datetime.now(timezone.utc).isoformat()
        disposition = 'duplicate_quarantined' if previous else 'quarantined'
        if not previous:
            db.execute('INSERT OR IGNORE INTO series VALUES (?,?)', (manifest.series_uid, manifest.study_uid))
            db.execute('INSERT INTO instances VALUES (?,?,?,?,?,?,?)',
                       (manifest.sop_uid, *expected[:2], digest, audit['source_bytes'], object_name, now))
        receipt_id = uuid4().hex
        db.execute('INSERT INTO receipts VALUES (?,?,?,?,?,?,?)',
                   (receipt_id, manifest.sop_uid, now, disposition,
                    _json(manifest.model_dump()), audit_text, audit_sha))
        db.commit()
        return {'format': FORMAT, 'receipt_id': receipt_id, 'disposition': disposition,
                'study_uid': manifest.study_uid, 'series_uid': manifest.series_uid,
                'sop_uid': manifest.sop_uid, 'source_sha256': digest,
                'source_bytes': audit['source_bytes'], 'audit_sha256': audit_sha,
                'preflight_decision': audit['decision'], 'archive_imported': False,
                'archive_eligible': False, 'provenance_independently_verified': False,
                'storage_role': 'quarantine-only'}
    except CustodyError:
        raise
    except Exception:
        raise CustodyError('custody_input_or_storage_invalid') from None
    finally:
        if db is not None:
            db.close()  # Rolls back any uncommitted transaction.
        if pending is not None:
            pending.unlink(missing_ok=True)  # Only our freshly created snapshot.


def inspect_custody(store):
    """Verify persistence without exposing raw DICOM fields or source paths."""
    root = Path(store).resolve(strict=True)
    base = QUARANTINE_ROOT.resolve()
    if root == base or not root.is_relative_to(base):
        raise CustodyError('quarantine_path_not_supported')
    if (root / 'custody-format.txt').read_text(encoding='ascii') != FORMAT:
        raise CustodyError('quarantine_format_mismatch')
    if (root / 'objects').resolve() != root / 'objects':
        raise CustodyError('quarantine_link_not_supported')
    db_path = root / 'custody.sqlite3'
    if db_path.is_symlink():
        raise CustodyError('quarantine_link_not_supported')
    db = sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)
    try:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise CustodyError('custody_database_integrity_failed')
        instances = db.execute('SELECT sop_uid,study_uid,series_uid,source_sha256,source_bytes,object_name FROM instances').fetchall()
        identities = {}
        for uid, study, series, digest, size, name in instances:
            if not re.fullmatch(r'[0-9a-f]{64}', digest) or name != digest + '.dcm':
                raise CustodyError('custody_object_name_invalid')
            identities[uid] = (study, series, digest, size)
            obj = root / 'objects' / name
            if obj.is_symlink() or not obj.is_file() or obj.stat().st_size != size:
                raise CustodyError('custody_object_integrity_failed')
            if _hash_file(obj) != digest:
                raise CustodyError('custody_object_integrity_failed')
        receipts = db.execute('SELECT sop_uid,manifest_json,audit_json,audit_sha256 FROM receipts').fetchall()
        received = set()
        for uid, manifest, audit, digest in receipts:
            if hashlib.sha256(audit.encode('utf-8')).hexdigest() != digest:
                raise CustodyError('custody_audit_integrity_failed')
            source = SourceManifest.model_validate_json(manifest)
            report = json.loads(audit)
            study, series, sha, size = identities[uid]
            if ((source.sop_uid, source.study_uid, source.series_uid, source.sha256) != (uid, study, series, sha)
                    or report.get('source_sha256') != sha or report.get('source_bytes') != size
                    or report.get('archive_imported') is not False or report.get('archive_eligible') is not False
                    or report.get('source_uid_binding_verified') is not True):
                raise CustodyError('custody_receipt_binding_failed')
            received.add(uid)
        if received != set(identities):
            raise CustodyError('custody_receipt_missing')
        parents = dict(db.execute('SELECT series_uid,study_uid FROM series').fetchall())
        if any(parents.get(series) != study for study, series, _, _ in identities.values()):
            raise CustodyError('custody_parent_binding_failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise CustodyError('custody_database_integrity_failed')
        return {'format': FORMAT, 'instances': len(instances), 'receipts': len(receipts),
                'integrity': 'verified', 'archive_imported': False, 'storage_role': 'quarantine-only'}
    except CustodyError:
        raise
    except Exception:
        raise CustodyError('custody_input_or_storage_invalid') from None
    finally:
        db.close()
