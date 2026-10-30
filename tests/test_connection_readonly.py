from pathlib import Path
from app.config import Settings
from app.legacy.connection import AccessConnectionFactory


def test_open_database_explicitly_read_only(monkeypatch):
    calls = []
    class Builder:
        def __init__(self, path): calls.append(('path', path))
        def setReadOnly(self, flag): calls.append(('read_only', flag)); return self
        def open(self): return 'database'
    monkeypatch.setattr('app.legacy.connection.jpype.JClass',
                        lambda name: Builder if name.endswith('DatabaseBuilder') else str)
    factory=AccessConnectionFactory(Settings(bridge_service_token='test'))
    monkeypatch.setattr(factory, '_start_jvm', lambda: None)
    assert factory._open_database(Path('/db/SGO.accdb')) == 'database'
    assert calls == [('path','/db/SGO.accdb'),('read_only',True)]
