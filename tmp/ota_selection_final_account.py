"""Temporary hardware-test account, using the project's integration-test lifecycle."""
from pathlib import Path
import json, secrets, sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from app.core.config import Settings
from app.core.security import hash_password
from app.database.connection import Database
from app.database.models import User, LoginSession
from sqlalchemy import delete
import httpx
dbase = Database(Settings(_env_file=root / 'backend/.env'))
record = root / '.runtime/ota-selection-final-account.json'
if '--cleanup' in sys.argv:
    info = json.loads(record.read_text())
    with dbase.session() as db:
        user = db.get(User, info['user_id'])
        assert user.username == info['username'] and user.username.startswith('ota_test_')
        db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
        user.active = False
        user.password_hash = hash_password(secrets.token_urlsafe(48))
        db.commit()
    session = json.loads((root / '.runtime/ota-session.json').read_text())
    assert httpx.get('http://127.0.0.1:8000/api/v1/ota', cookies=session['cookie']).status_code == 401
    (root / '.runtime/ota-test.env').unlink(missing_ok=True)
    (root / '.runtime/ota-session.json').unlink(missing_ok=True)
    print('Temporary test account disabled and its sessions revoked.')
else:
    assert not record.exists(), 'Existing account must be cleaned up first'
    username, password, final_password = 'ota_test_' + secrets.token_hex(6), secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    with dbase.session() as db:
        user = User(username=username, password_hash=hash_password(password), role='admin', must_change_password=True, active=True)
        db.add(user); db.commit()
        record.write_text(json.dumps({'user_id':user.id, 'username':username}))
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=15) as client:
        response = client.post('/api/v1/auth/login', json={'username':username, 'password':password})
        response.raise_for_status()
        csrf = response.json()['csrf_token']
        changed = client.post('/api/v1/auth/password', headers={'X-CSRF-Token':csrf}, json={'current_password':password, 'new_password':final_password})
        changed.raise_for_status()
        (root / '.runtime/ota-test.env').write_text(f'NAV_TEST_USERNAME={username}\nNAV_TEST_PASSWORD={final_password}\n')
        (root / '.runtime/ota-session.json').write_text(json.dumps({'cookie':dict(client.cookies), 'csrf':csrf}))
        print('Temporary account authenticated through normal login and password-change flow.')
        response = client.get('/api/v1/ota'); response.raise_for_status(); print(json.dumps(response.json(), indent=2))
dbase.engine.dispose()
