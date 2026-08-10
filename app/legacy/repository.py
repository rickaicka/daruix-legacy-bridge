import hmac
import re
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any, Iterable

from app.legacy.connection import AccessConnectionFactory


USER_TABLE = "T_Usuario"
WORK_TABLE = "Cadastro Obra"

# Lista fechada: o consumidor informa apenas o recurso da API, nunca um nome
# arbitrário de tabela. Isso evita transformar o bridge em um explorador geral
# do banco Access.
LEGACY_TABLES: dict[str, tuple[str, ...]] = {
    "supplies": ("tblInsumos",),
    "service-compositions": ("tblComposicaoDeServico",),
    # O primeiro nome foi informado no requisito. O segundo é o nome que
    # aparece no catálogo real do Access enviado para análise.
    "service-composition-items": (
        "tblItemComposicaoDeServico",
        "tblItemDaComposicaoDeServico",
    ),
    "budget-sheets": ("tblPlanilhaDeOrcamento",),
    "budget-sheet-stages": ("tblEtapaDaPlanilha",),
    "budget-sheet-stage-items": ("tblItemDaEtapaDaPlanilha",),
    "measurement-units": ("tblUnidadeDeMedida",),
}


class LegacyResourceNotFound(LookupError):
    pass


class LegacyTableNotFound(LookupError):
    pass


class LegacyColumnNotFound(LookupError):
    pass


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def display_text(value: Any) -> str:
    return " ".join(text(value).split())


def document_key(value: Any) -> str:
    return re.sub(r"\D", "", text(value))


def normalize_company_name(value: Any) -> str:
    """
    Normaliza o nome apenas para comparação e deduplicação.

    O nome original continua sendo devolvido pela API.
    """
    normalized = display_text(value).upper()

    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def normalized_search(value: Any) -> str:
    normalized = text(value).casefold()

    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    return normalized.strip()


def integer(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    return text(value).casefold() in {
        "true",
        "1",
        "yes",
        "sim",
    }


def json_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            "type": "binary",
            "size_bytes": len(value),
        }

    # byte[] vindo do Java/JPype. O diagnóstico não devolve o conteúdo para
    # evitar respostas enormes ou exposição acidental de anexos.
    if hasattr(value, "getClass"):
        try:
            if str(value.getClass().getName()) == "[B":
                return {
                    "type": "binary",
                    "size_bytes": len(value),
                }
        except Exception:
            pass

    # Datas do Jackcess normalmente chegam como java.time.LocalDateTime.
    if hasattr(value, "toLocalDate") and hasattr(value, "toLocalTime"):
        return str(value)

    # Compatibilidade com java.util.Date.
    if hasattr(value, "getTime"):
        milliseconds = int(value.getTime())

        return datetime.fromtimestamp(
            milliseconds / 1000,
            tz=timezone.utc,
        ).isoformat()

    # java.math.BigDecimal e outros tipos simples do Jackcess precisam ser
    # convertidos antes de chegar ao serializador JSON do FastAPI.
    if hasattr(value, "toPlainString"):
        return str(value.toPlainString())

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def contains(value: Any, search: str) -> bool:
    if not search:
        return True

    return normalized_search(search) in normalized_search(value)


class LegacyRepository:
    def __init__(self, factory: AccessConnectionFactory):
        self.factory = factory

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> dict:
        requested_username = username.strip().casefold()
        user = None

        with self.factory.connect() as database:
            for row in self._rows(database, USER_TABLE):
                legacy_username = text(row.get("usuNome"))

                if legacy_username.casefold() == requested_username:
                    user = row
                    break

        if not user or not self._password_matches(
            text(user.get("usuSenha")),
            password.strip(),
        ):
            return {
                "authenticated": False,
                "detail": "Usuário ou senha inválidos no legado.",
            }

        legacy_username = text(user.get("usuNome"))

        return {
            "authenticated": True,
            "legacy_user": {
                "username": legacy_username,
                "legacy_username": legacy_username,
                "full_name": (
                    text(user.get("usuNomeCompleto"))
                    or legacy_username
                ),
                "email": None,
                "last_legacy_login_at": json_value(
                    user.get("usuLogadoEm")
                ),
            },
            "groups": [],
            "modules": [],
            "permissions": [],
        }

    @staticmethod
    def _password_matches(
        stored: str,
        supplied: str,
    ) -> bool:
        # Compatibilidade temporária com o legado.
        # Nunca registrar esses valores em logs.
        return hmac.compare_digest(stored, supplied)

    def list_clients(
        self,
        search: str,
        limit: int,
    ) -> list[dict]:
        search = search.strip()

        # A chave será prioritariamente o CNPJ.
        # Quando não houver CNPJ, será usado o nome normalizado.
        unique_clients: dict[str, dict[str, str]] = {}

        with self.factory.connect() as database:
            for row in self._rows(database, WORK_TABLE):
                if boolean(row.get("obraFinalizada")):
                    continue

                name = display_text(row.get("faturado"))
                document = display_text(row.get("cnpjfat"))

                if not name:
                    continue

                if search and not (
                    contains(name, search)
                    or contains(document, search)
                ):
                    continue

                normalized_document = document_key(document)
                normalized_name = normalize_company_name(name)

                if normalized_document:
                    key = f"document:{normalized_document}"
                else:
                    key = f"name:{normalized_name}"

                existing_client = unique_clients.get(key)

                if existing_client is None:
                    unique_clients[key] = {
                        "name": name,
                        "document": document,
                    }
                    continue

                # Caso o primeiro registro esteja sem documento e outro
                # equivalente possua documento, preserva o documento.
                if (
                    document
                    and not existing_client["document"]
                ):
                    existing_client["document"] = document

        clients = sorted(
            unique_clients.values(),
            key=lambda client: normalize_company_name(
                client["name"]
            ),
        )

        return clients[:limit]

    def list_works(
        self,
        client_name: str,
        client_document: str,
        search: str,
        limit: int,
    ) -> list[dict]:
        works: list[dict] = []
        search = search.strip()

        with self.factory.connect() as database:
            for row in self._rows(database, WORK_TABLE):
                if boolean(row.get("obraFinalizada")):
                    continue

                work = self._work(row)

                if search and not any(
                    contains(work[field], search)
                    for field in (
                        "work_name",
                        "cost_center",
                        "client_name",
                    )
                ):
                    continue

                if self._belongs_to_client(
                    work=work,
                    name=client_name,
                    document=client_document,
                ):
                    works.append(work)

        works.sort(
            key=lambda work: (
                normalize_company_name(work["client_name"]),
                display_text(work["work_name"]).casefold(),
            )
        )

        return works[:limit]

    def get_work(
        self,
        work_id: int,
    ) -> dict | None:
        with self.factory.connect() as database:
            for row in self._rows(database, WORK_TABLE):
                if boolean(row.get("obraFinalizada")):
                    continue

                if integer(row.get("cod")) == work_id:
                    return self._work(row)

        return None

    def list_budgeting_tables(self) -> list[dict]:
        """Descreve as sete tabelas permitidas e informa quais existem."""
        with self.factory.connect() as database:
            available_names = self._table_names(database)
            catalog: list[dict] = []

            for resource, expected_names in LEGACY_TABLES.items():
                resolved_name = self._resolve_table_name(
                    available_names,
                    expected_names,
                )

                if resolved_name is None:
                    catalog.append(
                        {
                            "resource": resource,
                            "expected_table_names": list(expected_names),
                            "table_name": None,
                            "available": False,
                            "row_count": None,
                            "columns": [],
                            "similar_table_names": self._similar_table_names(
                                available_names.values(),
                                expected_names,
                            ),
                        }
                    )
                    continue

                table = database.getTable(resolved_name)
                catalog.append(
                    {
                        "resource": resource,
                        "expected_table_names": list(expected_names),
                        "table_name": resolved_name,
                        "available": True,
                        "row_count": int(table.getRowCount()),
                        "columns": self._column_metadata(table),
                        "similar_table_names": [],
                    }
                )

        return catalog

    def list_budgeting_table(
        self,
        resource: str,
        offset: int,
        limit: int,
        search: str = "",
        filter_column: str = "",
        filter_value: str = "",
    ) -> dict:
        """Lê uma tabela permitida sem expor SQL ou nomes arbitrários."""
        expected_names = LEGACY_TABLES.get(resource)
        if expected_names is None:
            raise LegacyResourceNotFound(
                f"Recurso legado não permitido: {resource}"
            )

        with self.factory.connect() as database:
            available_names = self._table_names(database)
            table_name = self._resolve_table_name(
                available_names,
                expected_names,
            )

            if table_name is None:
                raise LegacyTableNotFound(
                    "Nenhuma das tabelas Access esperadas foi encontrada: "
                    + ", ".join(expected_names)
                )

            table = database.getTable(table_name)
            columns = self._column_metadata(table)
            column_names = [column["name"] for column in columns]
            resolved_filter_column = self._resolve_column(
                column_names,
                filter_column,
            )

            items: list[dict] = []
            matching_index = 0
            has_more = False

            for row in table:
                item = {
                    column_name: json_value(row.get(column_name))
                    for column_name in column_names
                }

                if resolved_filter_column and not self._matches_filter(
                    item.get(resolved_filter_column),
                    filter_value,
                ):
                    continue

                if search and not any(
                    contains(value, search)
                    for value in item.values()
                ):
                    continue

                if matching_index < offset:
                    matching_index += 1
                    continue

                if len(items) >= limit:
                    has_more = True
                    break

                items.append(item)
                matching_index += 1

        return {
            "resource": resource,
            "table_name": table_name,
            "columns": columns,
            "items": items,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": offset + len(items) if has_more else None,
        }

    def ping(self) -> None:
        with self.factory.connect() as database:
            iterator = iter(
                self._rows(database, USER_TABLE)
            )

            next(iterator, None)

    @staticmethod
    def _table_names(database: Any) -> dict[str, str]:
        return {
            str(name).casefold(): str(name)
            for name in database.getTableNames()
        }

    @staticmethod
    def _resolve_table_name(
        available_names: dict[str, str],
        expected_names: tuple[str, ...],
    ) -> str | None:
        for expected_name in expected_names:
            resolved_name = available_names.get(expected_name.casefold())
            if resolved_name is not None:
                return resolved_name

        return None

    @staticmethod
    def _similar_table_names(
        available_names: Iterable[str],
        expected_names: tuple[str, ...],
        limit: int = 5,
    ) -> list[str]:
        scored_names: list[tuple[float, str]] = []

        for available_name in available_names:
            score = max(
                SequenceMatcher(
                    None,
                    normalized_search(expected_name),
                    normalized_search(available_name),
                ).ratio()
                for expected_name in expected_names
            )

            if score >= 0.45:
                scored_names.append((score, available_name))

        scored_names.sort(key=lambda item: (-item[0], item[1].casefold()))
        return [name for _, name in scored_names[:limit]]

    @staticmethod
    def _column_metadata(table: Any) -> list[dict[str, str]]:
        return [
            {
                "name": str(column.getName()),
                "type": str(column.getType()),
            }
            for column in table.getColumns()
        ]

    @staticmethod
    def _resolve_column(
        column_names: list[str],
        requested_column: str,
    ) -> str:
        if not requested_column:
            return ""

        names_by_key = {
            column_name.casefold(): column_name
            for column_name in column_names
        }
        resolved = names_by_key.get(requested_column.casefold())

        if resolved is None:
            raise LegacyColumnNotFound(
                f"Coluna Access não encontrada: {requested_column}"
            )

        return resolved

    @staticmethod
    def _matches_filter(value: Any, expected: str) -> bool:
        return normalized_search(value) == normalized_search(expected)

    @staticmethod
    def _rows(
        database: Any,
        table_name: str,
    ) -> Iterable[Any]:
        table = database.getTable(table_name)

        if table is None:
            raise RuntimeError(
                f"Tabela Access não encontrada: {table_name}"
            )

        return table

    @staticmethod
    def _work(row: Any) -> dict:
        return {
            "legacy_work_id": integer(row.get("cod")),
            "legacy_proposal_id": integer(
                row.get("propostaID")
            ),
            "cost_center": text(row.get("pc")),
            "work_name": text(row.get("apelido")),
            "client_name": display_text(
                row.get("faturado")
            ),
            "client_document": display_text(
                row.get("cnpjfat")
            ),
            "attention_to_suggestion": (
                text(row.get("contatentrega"))
                or text(row.get("contfat"))
            ),
            "delivery_address": text(
                row.get("endentrega")
            ),
            "delivery_phone": text(
                row.get("foneentrega")
            ),
        }

    @staticmethod
    def _belongs_to_client(
        work: dict,
        name: str,
        document: str,
    ) -> bool:
        requested_document = document_key(document)
        work_document = document_key(
            work["client_document"]
        )

        # Se ambos possuem CNPJ, ele é a identificação principal.
        if requested_document and work_document:
            return requested_document == work_document

        # Quando o Access não fornece CNPJ, compara nomes normalizados.
        if name:
            return (
                normalize_company_name(name)
                == normalize_company_name(
                    work["client_name"]
                )
            )

        return True
