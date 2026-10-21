import json

from app.core.config import settings
from tools.preflight_runtime import private_runtime_configuration_errors


def test_startup_gate_rejects_missing_review_accounts_and_pacs_config(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'LOCAL_AUTH_FILE', str(tmp_path / 'missing-users.json'))
    monkeypatch.setattr(settings, 'PACS_CONFIG_FILE', str(tmp_path / 'missing-pacs.json'))
    errors = private_runtime_configuration_errors()
    assert errors == [
        'Local review-account configuration has no usable accounts',
        'Local PACS configuration is invalid or missing',
    ]


def test_startup_gate_accepts_valid_nonempty_local_configs(tmp_path, monkeypatch):
    accounts = tmp_path / 'accounts.json'
    accounts.write_text(json.dumps({'format_version':1,'users':[{'id':'b'*32,'username':'reviewer',
        'role':'doctor','display_name':'Synthetic Reviewer','disabled':False,
        'password_hash':'pbkdf2_sha256$600000$'+'1'*32+'$'+'1'*64}]}),encoding='utf-8')
    pacs = tmp_path / 'pacs.json'
    pacs.write_text(json.dumps({'format_version':1,'archive_id':'synthetic','base_url':'http://127.0.0.1:8042',
        'username':'pacs-user','password':'synthetic-only'}),encoding='utf-8')
    monkeypatch.setattr(settings, 'LOCAL_AUTH_FILE', str(accounts))
    monkeypatch.setattr(settings, 'PACS_CONFIG_FILE', str(pacs))
    assert private_runtime_configuration_errors() == []
