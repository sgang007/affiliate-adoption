import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Point the app at a throwaway sqlite db BEFORE anything imports settings.
_tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["ADMIN_EMAIL"] = "admin@test.local"
os.environ["ADMIN_PASSWORD"] = "admin-test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post(
        "/api/auth/login", json={"email": "admin@test.local", "password": "admin-test"}
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}
