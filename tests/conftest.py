import os,pytest
from fastapi.testclient import TestClient
from aisx_os.api import app

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('AISX_DB_PATH',str(tmp_path/'test.db'))
    monkeypatch.setenv('AISX_ALLOW_LOCAL_DEMO','true')
    monkeypatch.delenv('AISX_IDENTITIES_JSON',raising=False)
    with TestClient(app) as c:yield c

@pytest.fixture
def analyst():return {'Authorization':'Bearer local-analyst-key-change-me-now'}
@pytest.fixture
def approver():return {'Authorization':'Bearer local-approver-key-change-me-now'}
@pytest.fixture
def admin():return {'Authorization':'Bearer local-admin-key-change-me-now'}
