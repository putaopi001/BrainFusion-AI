"""Create a disposable loopback-demo account and print its one-run password."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.local_auth import hash_password  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_unified_demo_account.py ACCOUNT_JSON")
    target = Path(sys.argv[1]).resolve()
    if target.drive.upper() != "E:" or target.name != "local-users.json":
        raise SystemExit("demo account file must be local-users.json on E:")
    target.parent.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(24)
    record = {
        "format_version": 1,
        "users": [{
            "id": secrets.token_hex(16),
            "username": "demo-doctor",
            "display_name": "Synthetic research test doctor",
            "role": "doctor",
            "disabled": False,
            "password_hash": hash_password(password),
        }],
    }
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    print(json.dumps({"username": "demo-doctor", "password": password}, ensure_ascii=False))


if __name__ == "__main__":
    main()
