import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.legacy.connection import AccessConnectionFactory


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def display_text(value: Any) -> str:
    return " ".join(text(value).split())


def document_key(value: Any) -> str:
    return re.sub(r"\D", "", text(value))


def integer(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


class LegacyRepository:
    def __init__(self, factory: AccessConnectionFactory):
        self.factory = factory

    def authenticate(self, username: str, password: str) -> dict:
        with self.factory.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """SELECT usuNome, usuSenha, usuNomeCompleto, usuLogado, usuLogadoEm
                   FROM [T_Usuario]
                   WHERE LCase(Trim(usuNome)) = LCase(Trim(?))""",
                (username.strip(),),
            )
            row = cursor.fetchone()

        if not row or not self._password_matches(text(row[1]), password.strip()):
            return {"authenticated": False, "detail": "Usuário ou senha inválidos no legado."}

        legacy_username = text(row[0])
        return {
            "authenticated": True,
            "legacy_user": {
                "username": legacy_username,
                "legacy_username": legacy_username,
                "full_name": text(row[2]) or legacy_username,
                "email": None,
                "last_legacy_login_at": json_value(row[4]),
            },
            "groups": [], "modules": [], "permissions": [],
        }

    @staticmethod
    def _password_matches(stored: str, supplied: str) -> bool:
        # Compatibilidade temporária com o legado. Não registrar nenhum dos valores.
        import hmac
        return hmac.compare_digest(stored, supplied)

    def list_clients(self, search: str, limit: int) -> list[dict]:
        query = """SELECT DISTINCT faturado, cnpjfat FROM [Cadastro Obra]
                   WHERE obraFinalizada = False AND faturado IS NOT NULL
                   AND Trim(faturado) <> ''"""
        parameters: list[Any] = []
        if search:
            query += " AND (faturado LIKE ? OR cnpjfat LIKE ?)"
            parameters.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY faturado"
        rows = self._fetchall(query, parameters)

        clients: list[dict] = []
        by_document: dict[str, int] = {}
        by_name: dict[str, list[int]] = {}
        for row in rows:
            client = {"name": display_text(row[0]), "document": text(row[1])}
            name = client["name"].casefold()
            document = document_key(client["document"])
            index = by_document.get(document) if document else None
            if index is None:
                for candidate in by_name.get(name, []):
                    existing = document_key(clients[candidate]["document"])
                    if not document or not existing or document == existing:
                        index = candidate
                        break
            if index is not None:
                if document and not document_key(clients[index]["document"]):
                    clients[index]["document"] = client["document"]
                    by_document[document] = index
                continue
            index = len(clients)
            clients.append(client)
            by_name.setdefault(name, []).append(index)
            if document:
                by_document[document] = index
            if len(clients) >= limit:
                break
        return clients

    def list_works(self, client_name: str, client_document: str, search: str, limit: int) -> list[dict]:
        query = self._work_select() + " WHERE obraFinalizada = False"
        parameters: list[Any] = []
        if search:
            query += " AND (apelido LIKE ? OR pc LIKE ? OR faturado LIKE ?)"
            parameters.extend([f"%{search}%"] * 3)
        query += " ORDER BY faturado, apelido"
        works = []
        for row in self._fetchall(query, parameters):
            work = self._work(row)
            if self._belongs_to_client(work, client_name, client_document):
                works.append(work)
            if len(works) >= limit:
                break
        return works

    def get_work(self, work_id: int) -> dict | None:
        rows = self._fetchall(
            self._work_select() + " WHERE cod = ? AND obraFinalizada = False",
            [work_id],
        )
        return self._work(rows[0]) if rows else None

    def ping(self) -> None:
        self._fetchall("SELECT TOP 1 usuNome FROM [T_Usuario]", [])

    def _fetchall(self, query: str, parameters: list[Any]):
        with self.factory.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(query, tuple(parameters))
            return cursor.fetchall()

    @staticmethod
    def _work_select() -> str:
        return """SELECT cod, pc, propostaID, apelido, faturado, cnpjfat,
                  contatentrega, contfat, endentrega, foneentrega FROM [Cadastro Obra]"""

    @staticmethod
    def _work(row) -> dict:
        return {
            "legacy_work_id": integer(row[0]), "legacy_proposal_id": integer(row[2]),
            "cost_center": text(row[1]), "work_name": text(row[3]),
            "client_name": text(row[4]), "client_document": text(row[5]),
            "attention_to_suggestion": text(row[6]) or text(row[7]),
            "delivery_address": text(row[8]), "delivery_phone": text(row[9]),
        }

    @staticmethod
    def _belongs_to_client(work: dict, name: str, document: str) -> bool:
        requested_document = document_key(document)
        work_document = document_key(work["client_document"])
        if requested_document and work_document:
            return requested_document == work_document
        return not name or display_text(name).casefold() == display_text(work["client_name"]).casefold()

