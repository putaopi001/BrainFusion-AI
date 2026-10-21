"""Single-process loopback account sessions for manual DICOM review, not medical credentials."""
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from pathlib import Path

from fastapi import HTTPException, Request
from app.core.config import settings
from app.core.storage import is_supported_storage_path

COOKIE = 'bf_local_session'
ITERATIONS = 600_000
SESSION_SECONDS = 8 * 60 * 60
_sessions = {}
_failures = {}
_lock = threading.RLock()
_DUMMY = 'pbkdf2_sha256$600000$' + '00'*16 + '$' + '00'*32

def hash_password(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError('Password must contain 12 to 128 characters')
    salt = secrets.token_bytes(16)
    value = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${value.hex()}'

def verify_password(password, encoded):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        return False
    try:
        algorithm, iterations, salt, expected = encoded.split('$')
        if algorithm != 'pbkdf2_sha256' or iterations != str(ITERATIONS) or len(salt) != 32 or len(expected) != 64:
            return False
        value = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), ITERATIONS)
        return hmac.compare_digest(value, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False

def accounts(source=None):
    try:
        path = Path(settings.LOCAL_AUTH_FILE if source is None else source).resolve()
        if not is_supported_storage_path(path):
            raise ValueError('Account file must use the configured local runtime storage')
        if not path.exists():
            return [], None
        raw = path.read_bytes()
        if len(raw) > 128 * 1024:
            raise ValueError('Oversized accounts')
        data = json.loads(raw.decode('utf-8-sig'))
        assert data['format_version'] == 1 and isinstance(data['users'], list) and len(data['users']) <= 100
        identifiers, usernames = set(), set()
        for user in data['users']:
            assert re.fullmatch(r'[a-zA-Z0-9_.-]{3,64}', user['username'])
            assert re.fullmatch(r'[a-f0-9]{32}', user['id'])
            assert user['role'] in ('doctor', 'researcher') and isinstance(user['disabled'], bool)
            assert isinstance(user['display_name'], str) and 1 <= len(user['display_name'].strip()) <= 120
            assert re.fullmatch(r'pbkdf2_sha256\$600000\$[a-f0-9]{32}\$[a-f0-9]{64}', user['password_hash'])
            assert user['id'] not in identifiers and user['username'] not in usernames
            identifiers.add(user['id']); usernames.add(user['username'])
        return data['users'], hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError, KeyError, TypeError, AssertionError):
        raise HTTPException(503, '本地账户配置不可用，请由本机维护者核对。') from None

def check_origin(request):
    origin = request.headers.get('origin')
    if origin and origin not in settings.cors_origin_list:
        raise HTTPException(403, '请求来源未获允许。')

def public_user(user):
    return {key: user[key] for key in ('id', 'username', 'display_name', 'role')}

def _key(token):
    return hashlib.sha256(token.encode()).hexdigest()

def _prune(now):
    for key in list(_sessions):
        if _sessions[key]['expires'] <= now:
            del _sessions[key]
    for peer in list(_failures):
        if _failures[peer]['until'] <= now:
            del _failures[peer]

def login(request, username, password):
    check_origin(request)
    users, fingerprint = accounts()
    if fingerprint is None:
        raise HTTPException(503, '尚未配置本地账户，请先运行本机账户工具。')
    now = time.time(); peer = request.client.host if request.client else 'local'
    with _lock:
        _prune(now)
        if _failures.get(peer, {}).get('count', 0) >= 5:
            raise HTTPException(429, '登录失败次数过多，请一分钟后重试。', headers={'Retry-After': '60'})
    user = next((u for u in users if u['username'] == username), None)
    valid = verify_password(password, user['password_hash'] if user else _DUMMY)
    if not valid or user is None or user['disabled']:
        with _lock:
            entry = _failures.setdefault(peer, dict(count=0, until=now+60))
            entry['count'] += 1
        raise HTTPException(401, '账户或密码不正确。')
    with _lock:
        _failures.pop(peer, None)
        _sessions.pop(_key(request.cookies.get(COOKIE, '')), None)
        if len(_sessions) >= 256:
            raise HTTPException(503, '本地会话数量已达上限。')
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        _sessions[_key(token)] = dict(user=public_user(user), fingerprint=fingerprint, csrf=csrf, expires=now+SESSION_SECONDS)
    return token

def session(request):
    token = request.cookies.get(COOKIE, '')
    if len(token) > 128:
        return None
    with _lock:
        _prune(time.time())
        record = _sessions.get(_key(token))
        record = dict(record) if record else None
    if record:
        _, fingerprint = accounts()
        if record['fingerprint'] != fingerprint:
            with _lock: _sessions.pop(_key(token), None)
            return None
    return record

def require_session(request: Request):
    check_origin(request)
    record = session(request)
    if not record:
        raise HTTPException(401, '请先登录本地账户；会话过期或服务重启后需重新登录。')
    if not hmac.compare_digest(request.headers.get('x-bf-csrf', ''), record['csrf']):
        raise HTTPException(403, '会话校验失败，请刷新登录状态。')
    return record

def require_doctor(request: Request):
    record = require_session(request)
    if record['user']['role'] != 'doctor':
        raise HTTPException(403, '当前研究员账户不能保存医生角色复核。')
    return dict(format='local-account-review-v1', **record['user'], authentication_method='local_password_session',
                professional_credential_verified=False)

def logout(request):
    require_session(request)
    with _lock: _sessions.pop(_key(request.cookies.get(COOKIE, '')), None)
