import os

os.environ.setdefault("BRIDGE_SERVICE_TOKEN", "test-token")
os.environ.setdefault("BRIDGE_ALLOWED_CLIENTS", "testclient")

from fastapi.testclient import TestClient

from app.dependencies import get_repository
from app.main import app


class FakeRepository:
    def ping(self): pass
    def authenticate(self, username, password):
        return {"authenticated": username == "ricardo" and password == "secret", "detail": None}
    def list_clients(self, search, limit):
        return [{"name": "Cliente A", "document": "12.345.678/0001-90"}]
    def list_works(self, client_name, client_document, search, limit):
        return [{"legacy_work_id": 575, "legacy_proposal_id": 8082, "cost_center": "PC26006", "work_name": "OBRA A", "client_name": "Cliente A", "client_document": "12.345.678/0001-90", "attention_to_suggestion": "Renato", "delivery_address": "Rua A", "delivery_phone": "11999999999"}]
    def get_work(self, work_id):
        return self.list_works("", "", "", 1)[0] if work_id == 575 else None


app.dependency_overrides[get_repository] = lambda: FakeRepository()
client = TestClient(app)
headers = {"Authorization": "Bearer test-token"}


def test_rejects_missing_token():
    assert client.get("/v1/clients").status_code == 401


def test_lists_clients():
    response = client.get("/v1/clients", headers=headers)
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Cliente A"


def test_gets_work_and_returns_404():
    assert client.get("/v1/works/575", headers=headers).status_code == 200
    assert client.get("/v1/works/999", headers=headers).status_code == 404


def test_authentication_contract():
    response = client.post("/v1/authenticate", headers=headers, json={"username": "ricardo", "password": "secret"})
    assert response.status_code == 200
    assert response.json()["authenticated"] is True

