from contextlib import nullcontext

from app.legacy.repository import LegacyRepository


class FakeAccessFactory:
    def connect(self):
        return nullcontext(object())


def test_legacy_auth_returns_access_user_group(monkeypatch):
    repository = LegacyRepository(FakeAccessFactory())
    monkeypatch.setattr(repository, "_rows", lambda db, table: [
        {"usuNome": "test", "usuSenha": "pass", "usuNomeCompleto": "Test", "usuGrupo": "ENGENHARIA"}
    ])
    payload = repository.authenticate("test", "pass")
    assert payload["authenticated"] is True
    assert payload["groups"] == [{"name": "ENGENHARIA", "legacy_name": "ENGENHARIA"}]


def test_legacy_auth_does_not_disclose_group_for_wrong_password(monkeypatch):
    repository = LegacyRepository(FakeAccessFactory())
    monkeypatch.setattr(repository, "_rows", lambda db, table: [
        {"usuNome": "test", "usuSenha": "pass", "usuGrupo": "DIRETORIA"}
    ])
    payload = repository.authenticate("test", "wrong")
    assert payload["authenticated"] is False
    assert "groups" not in payload
