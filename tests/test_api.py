import os

os.environ.setdefault("BRIDGE_SERVICE_TOKEN", "test-token")
os.environ.setdefault("BRIDGE_ALLOWED_CLIENTS", "testclient")

from fastapi.testclient import TestClient

from app.dependencies import get_repository
from app.legacy.repository import (
    COMMERCIAL_TABLES,
    catalog_legacy_key,
    client_legacy_key,
)
from app.main import app


class FakeRepository:
    def ping(self): pass
    def authenticate(self, username, password):
        return {"authenticated": username == "ricardo" and password == "secret", "detail": None}
    def list_clients(self, search, limit):
        return [{
            "name": "Cliente A",
            "document": "12.345.678/0001-90",
            "legacy_key": client_legacy_key("Cliente A", "12.345.678/0001-90"),
        }]
    def list_works(self, client_name, client_document, search, limit):
        return [{"legacy_work_id": 575, "legacy_proposal_id": 8082, "cost_center": "PC26006", "work_name": "OBRA A", "client_name": "Cliente A", "client_document": "12.345.678/0001-90", "attention_to_suggestion": "Renato", "delivery_address": "Rua A", "delivery_phone": "11999999999"}]
    def get_work(self, work_id):
        return self.list_works("", "", "", 1)[0] if work_id == 575 else None
    def list_commercial_tables(self):
        return []
    def list_commercial_table(
        self,
        resource,
        offset,
        limit,
        search="",
        filter_column="",
        filter_value="",
    ):
        return {
            "resource": resource,
            "table_name": "Cadastro de Proposta",
            "columns": [
                {"name": "propostaID", "type": "LONG"},
                {"name": "PC", "type": "TEXT"},
            ],
            "items": [{"propostaID": 8082, "PC": "PC26085"}],
            "offset": offset,
            "limit": limit,
            "has_more": False,
            "next_offset": None,
        }
    def list_business_segments(self):
        return [{
            "legacy_id": None,
            "legacy_key": catalog_legacy_key(
                "business-segments", legacy_id=None, name="Construção civil"
            ),
            "name": "Construção civil",
        }]
    def list_company_types(self):
        return [{
            "legacy_id": 2,
            "legacy_key": catalog_legacy_key(
                "company-types", legacy_id=2, name="Construtora"
            ),
            "name": "Construtora",
        }]


app.dependency_overrides[get_repository] = lambda: FakeRepository()
client = TestClient(app)
headers = {"Authorization": "Bearer test-token"}


def test_rejects_missing_token():
    assert client.get("/v1/clients").status_code == 401


def test_lists_clients():
    response = client.get("/v1/clients", headers=headers)
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Cliente A"
    assert len(response.json()[0]["legacy_key"]) == 64


def test_lists_full_client_catalog():
    response = client.get("/v1/clients/catalog", headers=headers)
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Cliente A"


def test_gets_work_and_returns_404():
    assert client.get("/v1/works/575", headers=headers).status_code == 200
    assert client.get("/v1/works/999", headers=headers).status_code == 404


def test_authentication_contract():
    response = client.post("/v1/authenticate", headers=headers, json={"username": "ricardo", "password": "secret"})
    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_lists_commercial_catalogs():
    segments = client.get("/v1/business-segments", headers=headers)
    company_types = client.get("/v1/company-types", headers=headers)
    assert segments.status_code == 200
    assert segments.json()[0]["legacy_id"] is None
    assert len(segments.json()[0]["legacy_key"]) == 64
    assert company_types.status_code == 200
    assert company_types.json()[0]["legacy_id"] == 2
    assert len(company_types.json()[0]["legacy_key"]) == 64


def test_lists_paginated_commercial_proposal_data():
    response = client.get(
        "/v1/commercial/proposals?limit=20",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["resource"] == "proposals"
    assert response.json()["items"][0]["propostaID"] == 8082


def test_commercial_filter_requires_column_and_value():
    response = client.get(
        "/v1/commercial/proposals?filter_column=PC",
        headers=headers,
    )

    assert response.status_code == 422


def test_catalog_legacy_key_is_stable_for_name_variations():
    first = catalog_legacy_key(
        "business-segments", legacy_id=None, name="Instalações Elétricas"
    )
    second = catalog_legacy_key(
        "business-segments", legacy_id=None, name="  INSTALACOES   ELETRICAS "
    )
    assert first == second


def test_catalog_keys_are_namespaced_by_resource():
    segment_key = catalog_legacy_key(
        "business-segments", legacy_id=None, name="Construtora"
    )
    company_type_key = catalog_legacy_key(
        "company-types", legacy_id=None, name="Construtora"
    )
    assert segment_key != company_type_key


def test_commercial_discovery_contains_proposal_resources():
    assert "proposals" in COMMERCIAL_TABLES
    assert "proposal-requested-services" in COMMERCIAL_TABLES
    assert "proposal-contacts" in COMMERCIAL_TABLES
    assert "proposal-payment-installments" in COMMERCIAL_TABLES
    assert "proposal-payment-plans" in COMMERCIAL_TABLES
    assert "proposal-types" in COMMERCIAL_TABLES
    assert "divisions" in COMMERCIAL_TABLES
    assert "departments" in COMMERCIAL_TABLES
    assert "projects" in COMMERCIAL_TABLES
    assert "works" in COMMERCIAL_TABLES
    assert "users" in COMMERCIAL_TABLES
