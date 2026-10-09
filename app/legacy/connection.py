from contextlib import contextmanager
from glob import glob
from pathlib import Path
from threading import Lock
import logging
from typing import Any, Iterator

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

        jars = sorted(
            glob(
                self.settings.ucanaccess_classpath
            )
        )

        if not jars:
            raise LegacyDatabaseUnavailable(
                "Drivers Jackcess não encontrados."
            )

        with self._jvm_lock:
            if jpype.isJVMStarted():
                return

            logger.info(
                "Iniciando JVM com %d arquivo(s) JAR do Jackcess.",
                len(jars),
            )

            try:
                jpype.startJVM(
                    classpath=jars,
                    convertStrings=True,
                )

            except Exception as error:
                logger.exception(
                    "Falha ao iniciar JVM para acesso ao banco legado."
                )

                raise LegacyDatabaseUnavailable(
                    "Não foi possível iniciar a JVM para acessar "
                    "o banco Access legado."
                ) from error

    def _open_database(
        self,
        path: Path,
    ) -> Any:
        self._start_jvm()

        try:
            DatabaseBuilder = jpype.JClass(
                "com.healthmarketscience.jackcess.DatabaseBuilder"
            )

            File = jpype.JClass(
                "java.io.File"
            )

            return DatabaseBuilder.open(
                File(str(path))
            )

        except LegacyDatabaseUnavailable:
            raise

        except Exception as error:
            logger.exception(
                "Falha ao abrir banco Access com Jackcess em %s.",
                path,
            )

            raise LegacyDatabaseUnavailable(
                "Não foi possível abrir o banco Access legado: "
                f"{path}"
            ) from error

    @contextmanager
    def connect(
        self,
    ) -> Iterator[Any]:
        path = self.validate()

        # Apenas falhas de abertura são convertidas para
        # LegacyDatabaseUnavailable. Erros do repository durante
        # o yield atravessam normalmente até o handler correto.
        database = self._open_database(
            path
        )

        try:
            yield database

        finally:
            try:
                database.close()

            except Exception:
                logger.exception(
                    "Falha ao fechar o banco Access legado em %s.",
                    path,
                )
