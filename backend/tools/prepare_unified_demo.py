"""Create the persistent, isolated unified-demo copy from the reviewed RC sample.

The source database and uploads are read-only. Existing targets with a verified
manifest are reused without reset; an unverified partial target is rejected
unless it matches the exact recoverable two-item copy shape created here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from datetime import datetime, timezone


SOURCE_ROOT = Path(r"E:\BrainFusion-Runtime\release-candidate\brainfusion-rc-20261021")
DEFAULT_TARGET = Path(r"E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo")
MARKER = "demo-copy-manifest.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def sqlite_uri(path: Path, mode: str) -> str:
    return path.resolve().as_uri() + f"?mode={mode}"


def database_counts(connection: sqlite3.Connection) -> dict[str, int]:
    result = {}
    for table in ("cases", "mris", "analysis_runs", "reports"):
        result[table] = int(connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])
    return result


def prepare(target: Path) -> dict:
    source_db = SOURCE_ROOT / "runtime" / "brainfusion.db"
    source_uploads = SOURCE_ROOT / "runtime" / "uploads"
    target = target.resolve()
    target_db = target / "runtime" / "brainfusion.db"
    target_uploads = target / "runtime" / "uploads"
    marker = target / MARKER

    if not source_db.is_file() or not source_uploads.is_dir():
        raise RuntimeError("Reviewed release-candidate sample database or uploads are missing")
    if source_db.drive.upper() != "E:" or target.drive.upper() != "E:":
        raise RuntimeError("The isolated demo runtime must stay on E:")

    if marker.is_file():
        manifest = json.loads(marker.read_text(encoding="utf-8"))
        database_changed = verify(target, manifest)
        return {"status": "EXISTS_VERIFIED_WITH_RUNTIME_CHANGES" if database_changed else "EXISTS_VERIFIED", "manifest": str(marker),
                "cases": manifest["database_counts"]["cases"],
                "upload_files": len(manifest["upload_files"])}
    resuming_generated_partial = False
    if target.exists() and any(target.iterdir()):
        # Recover only the exact two-part partial produced by this initializer:
        # a backup of the known source DB and a byte-identical uploads tree.
        root_items = {item.name for item in target.iterdir()}
        runtime_items = {item.name for item in (target / "runtime").iterdir()} if (target / "runtime").is_dir() else set()
        if root_items != {"runtime"} or runtime_items != {"brainfusion.db", "uploads"}:
            raise RuntimeError(f"Target is nonempty without a verified marker; refusing overwrite: {target}")
        if not target_db.is_file() or not target_uploads.is_dir():
            raise RuntimeError("Partial demo copy is incomplete; refusing overwrite")
        partial = sqlite3.connect(sqlite_uri(target_db, "ro"), uri=True)
        source = sqlite3.connect(sqlite_uri(source_db, "ro"), uri=True)
        try:
            if database_counts(partial) != database_counts(source):
                raise RuntimeError("Partial demo database does not match source aggregate counts")
            if not partial.execute("SELECT 1 FROM cases WHERE mri_path LIKE '/app/runtime/uploads/%' LIMIT 1").fetchone():
                raise RuntimeError("Partial demo database does not carry the expected source-path marker")
        finally:
            partial.close()
            source.close()
        resuming_generated_partial = True

    target.mkdir(parents=True, exist_ok=True)
    upload_files = []
    for path in source_uploads.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"Source uploads contain a symlink; refusing copy: {path.relative_to(source_uploads)}")
        if path.is_file():
            relative = path.relative_to(source_uploads)
            upload_files.append({"path": relative.as_posix(), "bytes": path.stat().st_size,
                                 "sha256": digest(path)})

    source_hash_before = digest(source_db)
    target_db.parent.mkdir(parents=True, exist_ok=True)
    target_uploads.mkdir(parents=True, exist_ok=resuming_generated_partial)
    shutil.copytree(source_uploads, target_uploads, dirs_exist_ok=True)

    src = sqlite3.connect(sqlite_uri(source_db, "ro"), uri=True)
    dst = sqlite3.connect(target_db)
    try:
        src.backup(dst)
        dst.execute("PRAGMA foreign_keys=ON")
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"Copied database integrity check failed: {integrity}")
        foreign_key_errors = dst.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise RuntimeError("Copied database has foreign-key violations")
        old = "/app/runtime/uploads"
        # Forward slashes are accepted by pathlib on Windows and remain valid
        # inside JSON strings stored in SQLite (backslashes would be escapes).
        new = target_uploads.as_posix()
        for table_row in dst.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall():
            table = table_row[0]
            columns = dst.execute(f'PRAGMA table_info("{table}")').fetchall()
            for column in columns:
                name, kind = column[1], str(column[2]).upper()
                if not (kind.startswith("TEXT") or kind.startswith("VARCHAR") or kind.startswith("CHAR") or kind.startswith("CLOB")):
                    continue
                dst.execute(
                    f'UPDATE "{table}" SET "{name}" = replace("{name}", ?, ?) '
                    f'WHERE typeof("{name}") = \'text\' AND instr("{name}", ?) > 0',
                    (old, new, old),
                )
        dst.commit()
        residuals = []
        for table_row in dst.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall():
            table = table_row[0]
            columns = dst.execute(f'PRAGMA table_info("{table}")').fetchall()
            for column in columns:
                name = column[1]
                found = dst.execute(
                    f'SELECT 1 FROM "{table}" WHERE typeof("{name}") = \'text\' '
                    f'AND instr("{name}", ?) > 0 LIMIT 1', (old,),
                ).fetchone()
                if found:
                    residuals.append(f"{table}.{name}")
        if residuals:
            raise RuntimeError("Unremapped container upload paths remain: " + ", ".join(residuals))
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Remapped database integrity check failed")
    finally:
        dst.close()
        src.close()

    if digest(source_db) != source_hash_before:
        raise RuntimeError("Source RC database changed during read-only copy")

    for entry in upload_files:
        copied = target_uploads / Path(entry["path"])
        if not copied.is_file() or copied.stat().st_size != entry["bytes"] or digest(copied) != entry["sha256"]:
            raise RuntimeError(f"Copied upload failed integrity verification: {entry['path']}")

    check = sqlite3.connect(sqlite_uri(target_db, "ro"), uri=True)
    try:
        counts = database_counts(check)
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        fk_errors = check.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        check.close()
    if integrity != "ok" or fk_errors:
        raise RuntimeError("Final isolated database verification failed")

    manifest = {
        "format_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": "reviewed isolated RC-20261021 engineering sample; copied read-only",
        "source_database_sha256": source_hash_before,
        "database_copy_sha256": digest(target_db),
        "database_counts": counts,
        "database_integrity": integrity,
        "foreign_key_errors": 0,
        "upload_files": upload_files,
        "upload_root": str(target_uploads),
        "path_remap": {"source_prefix": "/app/runtime/uploads", "target_prefix": target_uploads.as_posix(),
                       "storage_format": "absolute Windows-compatible path with forward slashes; JSON-safe"},
    }
    marker.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"status": "CREATED_AND_VERIFIED", "manifest": str(marker),
            "cases": counts["cases"], "upload_files": len(upload_files)}


def verify(target: Path, manifest: dict) -> bool:
    db = target / "runtime" / "brainfusion.db"
    uploads = target / "runtime" / "uploads"
    if manifest.get("format_version") != 1 or not db.is_file() or not uploads.is_dir():
        raise RuntimeError("Existing isolated demo copy is incomplete")
    database_changed = digest(db) != manifest.get("database_copy_sha256")
    # Repair only this initializer's former path remap in the isolated copy.
    # Never touch the source RC database or any other database.
    windows_prefix = str(uploads)
    portable_prefix = uploads.as_posix()
    if windows_prefix != portable_prefix:
        connection = sqlite3.connect(db)
        try:
            for table_row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall():
                table = table_row[0]
                for column in connection.execute(f'PRAGMA table_info("{table}")').fetchall():
                    name, kind = column[1], str(column[2]).upper()
                    if not (kind.startswith("TEXT") or kind.startswith("VARCHAR") or kind.startswith("CHAR") or kind.startswith("CLOB")):
                        continue
                    connection.execute(
                        f'UPDATE "{table}" SET "{name}" = replace("{name}", ?, ?) '
                        f'WHERE typeof("{name}") = \'text\' AND instr("{name}", ?) > 0',
                        (windows_prefix, portable_prefix, windows_prefix),
                    )
            connection.commit()
        finally:
            connection.close()
    for item in manifest.get("upload_files", []):
        path = uploads / Path(item["path"])
        if not path.is_file() or path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise RuntimeError(f"Existing demo upload changed; refusing to reset: {item['path']}")
    db_conn = sqlite3.connect(sqlite_uri(db, "ro"), uri=True)
    try:
        if db_conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Existing demo database failed integrity_check")
        if db_conn.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Existing demo database failed foreign_key_check")
    finally:
        db_conn.close()
    manifest["database_runtime_changed"] = database_changed
    manifest["database_runtime_sha256"] = digest(db)
    manifest["path_remap"] = {
        "source_prefix": "/app/runtime/uploads",
        "target_prefix": portable_prefix,
        "storage_format": "absolute Windows-compatible path with forward slashes; JSON-safe",
    }
    temporary = target / (MARKER + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target / MARKER)
    return database_changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()
    print(json.dumps(prepare(args.target), ensure_ascii=False))


if __name__ == "__main__":
    main()
