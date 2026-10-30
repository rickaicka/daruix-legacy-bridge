from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_repository
from app.legacy.repository import LegacyTableNotFound


class Repository:
    def list_material_requisition_tables(self):
        return [{"resource": "requests", "expected_table_names": [], "available": False}]

    def list_material_requisition_table(self, **kwargs):
        if kwargs['resource'] != 'requests':
            raise LegacyTableNotFound('Não configurado')
        return dict(resource='requests', table_name='TEST_RM', columns=[], items=[],
                    offset=kwargs['offset'], limit=kwargs['limit'], has_more=False,
                    next_offset=None)


def test_rm_contract():
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_repository] = lambda: Repository()
    try:
        client = TestClient(app)
        auth = {'Authorization': 'Bearer test-token'}
        assert client.get('/v1/material-requisitions/tables').status_code == 401
        assert client.get('/v1/material-requisitions/tables', headers=auth).json()[0]['available'] is False
        assert client.get('/v1/material-requisitions/requests', headers=auth).status_code == 200
        assert client.get('/v1/material-requisitions/request-items', headers=auth).status_code == 404
        assert client.get('/v1/material-requisitions/requests?limit=501', headers=auth).status_code == 422
        assert client.get('/v1/material-requisitions/requests?offset=-1', headers=auth).status_code == 422
        assert client.get('/v1/material-requisitions/requests?filter_column=PC', headers=auth).status_code == 422
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_repository_mapping_is_closed_and_unconfigured_is_error():
    from types import SimpleNamespace
    from app.legacy.repository import LegacyRepository, LegacyResourceNotFound
    import pytest
    repo = LegacyRepository(SimpleNamespace(settings=SimpleNamespace(
        material_requisition_tables={'requests': ('REAL_RM',), 'users': ('T_Usuario',)})))
    assert repo._material_requisition_tables() == {
        'requests': ('REAL_RM',), 'request-items': ()}
    with pytest.raises(LegacyResourceNotFound):
        repo.list_material_requisition_table('users', 0, 2)
    with pytest.raises(LegacyTableNotFound):
        repo.list_material_requisition_table('request-items', 0, 2)


def test_bff_to_bridge_http_contract():
    import importlib.util
    import io
    from pathlib import Path
    from urllib.error import HTTPError
    path = Path(__file__).resolve().parents[2] / 'bff/budgeting/services/legacy_material_requisitions.py'
    spec = importlib.util.spec_from_file_location('rm_integration_client', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    http = TestClient(app)

    class Opener:
        def open(self, request, timeout):
            from urllib.parse import urlsplit
            url = urlsplit(request.full_url)
            response = http.get(url.path + ('?' + url.query if url.query else ''),
                                headers=dict(request.header_items()))
            if response.status_code >= 400:
                raise HTTPError(request.full_url, response.status_code, '', {}, None)
            return io.BytesIO(response.content)

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_repository] = lambda: Repository()
    try:
        bff = module.LegacyMaterialRequisitionClient(base_url='http://testserver',
                                                     token='test-token', opener=Opener())
        assert bff.list_tables()[0]['available'] is False
        assert list(bff.iter_resource('requests')) == []
        import pytest
        with pytest.raises(module.LegacyRequisitionError) as error:
            list(bff.iter_resource('request-items'))
        assert error.value.status_code == 404
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
