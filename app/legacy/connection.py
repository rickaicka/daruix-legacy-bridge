from contextlib import contextmanager
from glob import glob
from pathlib import Path

import jaydebeapi

from app.config import Settings


class LegacyDatabaseUnavailable(RuntimeError):
    pass


class AccessConnectionFactory:
    DRIVER = "net.ucanaccess.jdbc.UcanaccessDriver"

    def __init__(self, settings: Settings):
        self.settings = settings

    def validate(self) -> Path:
        path = self.settings.legacy_db_path.resolve()
        if not path.is_file():
            raise LegacyDatabaseUnavailable(f"Banco Access não encontrado: {path}")
        return path

    @contextmanager
    def connect(self):
        path = self.validate()
        password = self.settings.legacy_db_password.get_secret_value()
        jars = sorted(glob(self.settings.ucanaccess_classpath))
        if not jars:
            raise LegacyDatabaseUnavailable("Drivers UCanAccess não encontrados.")
        url = f"jdbc:ucanaccess://{path};readonly=true;memory=false"
        if password:
            url += f";password={password}"
        try:
            connection = jaydebeapi.connect(
                self.DRIVER,
                url,
                jars=jars,
            )
        except Exception as error:
            raise LegacyDatabaseUnavailable("Não foi possível abrir o banco Access legado.") from error
        try:
            yield connection
        finally:
            connection.close()
