from contextlib import contextmanager
from glob import glob
from pathlib import Path
from threading import Lock
import logging

import jpype
import jpype.imports

from app.config import Settings


logger = logging.getLogger(__name__)


class LegacyDatabaseUnavailable(RuntimeError):
    pass


class AccessConnectionFactory:
    """Abre o Access diretamente com Jackcess, sem JDBC, SQL ou HSQLDB."""

    _jvm_lock = Lock()

    def __init__(self, settings: Settings):
        self.settings = settings

    def validate(self) -> Path:
        path = self.settings.legacy_db_path.resolve()

        if not path.is_file():
            raise LegacyDatabaseUnavailable(
                f"Banco Access não encontrado: {path}"
            )

        return path

    def _start_jvm(self) -> None:
        if jpype.isJVMStarted():
            return

        # O nome da configuração foi preservado para evitar uma alteração
        # simultânea em Settings. Agora o glob deve apontar para os JARs do
        # Jackcess e suas dependências, não para o UCanAccess.
        jars = sorted(glob(self.settings.ucanaccess_classpath))
        if not jars:
            raise LegacyDatabaseUnavailable(
                "Drivers Jackcess não encontrados."
            )

        with self._jvm_lock:
            if not jpype.isJVMStarted():
                logger.info(
                    "Iniciando JVM com %d arquivo(s) JAR do Jackcess.",
                    len(jars),
                )
                jpype.startJVM(classpath=jars, convertStrings=True)

    @contextmanager
    def connect(self):
        path = self.validate()
        database = None

        try:
            self._start_jvm()

            DatabaseBuilder = jpype.JClass(
                "com.healthmarketscience.jackcess.DatabaseBuilder"
            )
            File = jpype.JClass("java.io.File")

            builder = DatabaseBuilder(File(str(path)))
            builder.setReadOnly(True)
            builder.setAutoSync(False)

            password = self.settings.legacy_db_password.get_secret_value()
            if password:
                try:
                    CryptCodecProvider = jpype.JClass(
                        "com.healthmarketscience.jackcess.crypt.CryptCodecProvider"
                    )
                except Exception as error:
                    raise LegacyDatabaseUnavailable(
                        "O banco possui senha, mas jackcess-encrypt não está disponível."
                    ) from error
                builder.setCodecProvider(CryptCodecProvider(password))

            logger.info("Abrindo banco Access legado em %s com Jackcess.", path)
            database = builder.open()
            yield database

        except LegacyDatabaseUnavailable:
            raise
        except Exception as error:
            logger.exception(
                "Falha ao abrir ou utilizar o banco Access legado em %s.",
                path,
            )
            raise LegacyDatabaseUnavailable(
                "Não foi possível abrir o banco Access legado."
            ) from error

        finally:
            if database is not None:
                try:
                    database.close()
                except Exception:
                    logger.exception(
                        "Falha ao fechar o banco Access legado."
                    )