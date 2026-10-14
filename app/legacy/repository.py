import hashlib
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
    "supply-groups": (
        "tblGrupoDeMaterial",
    ),
    "service-compositions": ("tblComposicaoDeServico",),
    # O primeiro nome foi informado no requisito. O segundo é o nome que
    # aparece no catálogo real do Access enviado para análise.
    "service-composition-items": (
        "tblItemComposicaoDeServico",
        "tblItemDaComposicaoDeServico",
    ),
    "budget-sheets": ("tblPlanilhaDeOrcamento",),

    # Catálogos que alimentam as etapas no legado.
    # Permanecem separados no bridge para preservar a origem dos dados.
    "work-cost-centers": (
        "tblCentroDeCustoObra",
    ),
    "administrative-cost-centers": (
        "tblCentroDeCustoAdm",
    ),

    # Possível estrutura de itens vinculados ao centro de custo.
    "cost-center-compositions": (
        "tblComposicaoDoCentroDeCusto",
    ),
    "cost-center-composition-items": (
        "tblItemDaComposicaoDoCentroDeCusto",
    ),
    "cost-center-items": (
        "tblItemDoCentroDeCusto",
    ),

    # Catálogo reutilizável de etapas.
    "stages": ("tblEtapaDaObra",),

    # Itens cadastrados originalmente para uma etapa.
    "stage-items": ("tblitemDaEtapaDaObra",),

    # Etapas efetivamente selecionadas em cada planilha.
    "budget-sheet-stages": (
        "tblitemDaPlanilhaDeOrcamento",
    ),

    # Itens efetivamente incluídos na etapa da planilha.
    "budget-sheet-stage-items": (
        "tblSubitemDaPlanilhaDeOrcamento",
    ),

    "measurement-units": ("tblUnidadeDeMedida",),
}

COMMERCIAL_TABLES: dict[str, tuple[str, ...]] = {
    "business-segments": (
        "Ramo Empresarial",
        "RamoEmpresarial",
        "Cadastro Ramo Empresarial",
        "tblRamoEmpresarial",
        "tblRamoDeAtividade",
    ),
    "company-types": (
        "Tipo de Empresa",
        "Tipo Empresa",
        "Tipo Cliente",
        "Tipo_Cliente",
        "tblTipoDeEmpresa",
        "tblTipoCliente",
        # No banco atual não existe uma tabela mestre própria para tipos.
        # Os valores distintos vêm da coluna Tipo_Empresa do cadastro de clientes.
        "tblCadastroDeCliente",
    ),
    "clients": (
        "tblCadastroDeCliente",
        "Cadastro de Cliente",
        "Cadastro de Cliente1",
        "Cadastro de Cliente2",
    ),
    # Recursos abaixo são inicialmente usados para descoberta controlada do
    # esquema de propostas. O catálogo retorna o nome real, colunas e tabelas
    # semelhantes sem permitir que o consumidor informe nomes arbitrários.
    "proposals": (
        "tblCadastroDeProposta",
        "tblCadastroDePropostas",
        "tblProposta",
        "tblPropostas",
        "Cadastro de Proposta",
        "Cadastro de Propostas",
        "Cadastro Proposta",
        "Cadastro Propostas",
        "Proposta",
        "Propostas",
    ),
    "proposal-requested-services": (
        "tblProjetoProposta",
        "tblServicoSolicitadoDaProposta",
        "tblServicosSolicitadosDaProposta",
        "tblPropostaServico",
        "tblPropostaServicos",
        "Serviços Solicitados",
        "Servicos Solicitados",
        "Serviços Solicitados Proposta",
        "Servicos Solicitados Proposta",
    ),
    "proposal-contacts": (
        "tblContatoProposta",
        "tblContatosProposta",
        "Contato Proposta",
        "Contatos Proposta",
    ),
    "proposal-payment-installments": (
        "tblPagamentoParceladoProjetos",
        "tblPlanoDePagamentoProjeto",
        "tblPlanoDePagamentoProjetos",
        "tblParcelaDaProposta",
        "tblParcelasDaProposta",
        "Plano de Pagamento Projetos",
        "Plano Pagamento Projetos",
        "Parcelas da Proposta",
    ),
    "proposal-payment-plans": (
        "plano_pagamento",
        "tblPlanoPagamento",
        "tblPlanosPagamento",
        "Plano de Pagamento",
        "Planos de Pagamento",
    ),
    "proposal-types": (
        "tblTipoDeProposta",
        "tblTiposDeProposta",
        "Tipo de Proposta",
        "Tipos de Proposta",
        "Proposta Tipo",
    ),
    "divisions": (
        "tblDivisao",
        "tblDivisoes",
        "Divisão",
        "Divisao",
        "Divisões",
        "Divisoes",
    ),
    "departments": (
        "tblDepartamento",
        "tblDepartamentos",
        "Departamento",
        "Departamentos",
    ),
    "projects": (
        "tblProjeto",
        "tblProjetos",
        "Cadastro de Projeto",
        "Cadastro de Projetos",
        "Projeto",
        "Projetos",
    ),
    "works": (WORK_TABLE,),
    "users": (USER_TABLE,),
}
CLIENT_TABLE = "tblCadastroDeCliente"

COMMERCIAL_COLUMN_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "business-segments": {
        "legacy_id": (
            "ramoEmpresarialID",
            "ramoID",
            "idRamo",
        ),
        "name": (
            "Ramo Empresarial",
            "Ramo  Empresarial",
            "ramoEmpresarialNome",
            "ramoNome",
            "ramoEmpresarial",
            "descricao",
            "nome",
            "ramo",
        ),
    },
    "company-types": {
        "legacy_id": (
            "tipoEmpresaID",
            "tipoClienteID",
            "idTipoEmpresa",
            "idTipoCliente",
        ),
        "name": (
            "Tipo de Empresa",
            "Tipo  de Empresa",
            "tipoEmpresaNome",
            "tipoClienteNome",
            "tipoEmpresa",
            "tipoCliente",
            "tipo_empresa",
            "tipo_cliente",
            "descricao",
        ),
    },
}

# Subconjunto que pode devolver linhas brutas para o importador do BFF. A
# tabela T_Usuario fica deliberadamente fora desta lista porque contém senha
# legada. Ela participa apenas da descoberta de metadados.
PROPOSAL_TABLES: dict[str, tuple[str, ...]] = {
    resource: COMMERCIAL_TABLES[resource]
    for resource in (
        "proposals",
        "proposal-requested-services",
        "proposal-contacts",
        "proposal-payment-installments",
        "proposal-payment-plans",
        "proposal-types",
        "departments",
        "projects",
    )
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


def repair_legacy_text(value: Any) -> str:
    value = display_text(value)

    if not value:
        return ""

    # O Access possui dados misturados: alguns já estão Unicode corretos
    # e outros são UTF-8 interpretados como Latin-1/Windows-1252.
    # Só tenta reparar quando existem sinais típicos de mojibake.
    markers = (
        "Ã",
        "Â",
        "â€",
        "â€™",
        "â€œ",
        "â€\x9d",
        "�",
    )

    if not any(marker in value for marker in markers):
        return value

    candidates = [value]

    for encoding in ("latin1", "cp1252"):
        try:
            candidates.append(
                value.encode(encoding).decode("utf-8")
            )
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    def score(candidate: str) -> tuple[int, int]:
        mojibake_count = sum(
            candidate.count(marker)
            for marker in markers
        )

        replacement_count = candidate.count("�")

        return mojibake_count, replacement_count

    return min(candidates, key=score)

def normalized_document(value: Any) -> str:
    digits = document_key(value)

    if len(digits) not in (11, 14):
        return ""

    return digits


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


def catalog_legacy_key(
    resource: str,
    *,
    legacy_id: int | None,
    name: str,
) -> str:
    """Identidade técnica estável; nunca é usada como FK no Hub."""
    identity = (
        f"id:{legacy_id}"
        if legacy_id is not None
        else f"name:{normalize_company_name(name)}"
    )
    return hashlib.sha256(f"{resource}|{identity}".encode("utf-8")).hexdigest()


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
        group_name = repair_legacy_text(user.get("usuGrupo"))
        groups = ([{"name": group_name, "legacy_name": group_name}]
                  if group_name else [])

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
            "groups": groups,
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

    def _collect_clients(self, search: str = "") -> list[dict[str, str]]:
        search = search.strip()
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
                identity = (
                    f"document:{normalized_document}"
                    if normalized_document
                    else f"name:{normalized_name}"
                )

                existing_client = unique_clients.get(identity)
                if existing_client is None:
                    unique_clients[identity] = {
                        "name": name,
                        "document": document,
                    }
                    continue

                if document and not existing_client.get("document"):
                    existing_client["document"] = document

        return sorted(
            unique_clients.values(),
            key=lambda item: (normalize_company_name(item["name"]), document_key(item["document"])),
        )

    def list_clients(
        self,
        search: str,
        limit: int,
    ) -> list[dict]:
        search = search.strip()
        catalog = self.list_client_catalog()

        if search:
            catalog = [
                client
                for client in catalog
                if (
                    contains(client["name"], search)
                    or contains(client["trade_name"], search)
                    or contains(client["document"], search)
                )
            ]

        return [
            {"name": client["name"], "document": client["document"]}
            for client in catalog[:limit]
        ]

    def list_client_catalog(self) -> list[dict]:
        clients: list[dict] = []

        with self.factory.connect() as database:
            table = database.getTable(CLIENT_TABLE)

            for row in table:
                legacy_id = integer(
                    row.get("clienteID")
                )

                name = (
                        repair_legacy_text(
                            row.get("RAZAOSOCIAL")
                        )
                        or repair_legacy_text(
                    row.get("nome fantasia")
                )
                )

                document_raw = (
                        display_text(row.get("CNPJ/CPF"))
                        or display_text(row.get("cnpj"))
                        or display_text(row.get("cpff"))
                )

                document = normalized_document(
                    document_raw
                )

                company_type_name = repair_legacy_text(
                    row.get("Tipo_Empresa")
                )

                business_segment_name = repair_legacy_text(
                    row.get("Ramo Empresarial c")
                )

                if legacy_id is None or not name:
                    continue

                trade_name = repair_legacy_text(
                    row.get("nome fantasia")
                )

                address = repair_legacy_text(
                    row.get("Endereco")
                )

                district = repair_legacy_text(
                    row.get("Bairro")
                )

                city = repair_legacy_text(
                    row.get("Cidade")
                )

                state = repair_legacy_text(
                    row.get("Estado")
                )

                postal_code = repair_legacy_text(
                    row.get("CEP")
                )

                phone = repair_legacy_text(
                    row.get("Telefone")
                )

                email = repair_legacy_text(
                    row.get("Email empresarial")
                )

                website = repair_legacy_text(
                    row.get("Homepage")
                )

                clients.append(
                    {
                        "legacy_id": legacy_id,
                        "legacy_key": catalog_legacy_key(
                            "clients",
                            legacy_id=legacy_id,
                            name=name,
                        ),
                        "name": name,
                        "trade_name": trade_name,
                        "document": document,
                        "company_type_name": company_type_name,
                        "business_segment_name": business_segment_name,
                        "address": address,
                        "district": district,
                        "city": city,
                        "state": state,
                        "postal_code": postal_code,
                        "phone": phone,
                        "email": email,
                        "website": website,
                        "legacy_payload": {
                            "document_raw": document_raw,
                            "proprietario": repair_legacy_text(
                                row.get("Proprietario")
                            ),
                            "ie_rg": repair_legacy_text(
                                row.get("IE/RG")
                            ),
                            "newsletter": json_value(
                                row.get("Newsletter")
                            ),
                            "pendencias": json_value(
                                row.get("Pendencias")
                            ),
                            "indicado_por": repair_legacy_text(
                                row.get("Indicado por")
                            ),
                            "address": address,
                            "district": district,
                            "city": city,
                            "state": state,
                            "postal_code": postal_code,
                            "phone": phone,
                            "email": email,
                        },
                    }
                )

        clients.sort(
            key=lambda item: (
                normalize_company_name(
                    item["name"]
                ),
                item["legacy_id"],
            )
        )

        return clients

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

    def list_budget_stage_catalog(self) -> list[dict]:
        """
        Unifica os centros de custo operacionais e administrativos
        utilizados como etapas de orçamento no legado.

        A identidade legada é composta por origem + ID. O BFF criará
        suas próprias PKs para os relacionamentos internos.
        """
        source_definitions = (
            {
                "resource": "work-cost-centers",
                "legacy_source": "WORK_COST_CENTER",
                "category": "OPERATIONAL",
                "id_column": "id",
                "code_column": "codigocc",
                "name_column": "nomecc",
            },
            {
                "resource": "administrative-cost-centers",
                "legacy_source": "ADMINISTRATIVE_COST_CENTER",
                "category": "ADMINISTRATIVE",
                "id_column": "CentroDeCustoAdmID",
                "code_column": None,
                "name_column": "CentroDeCustoNome",
            },
        )

        stages: list[dict] = []

        with self.factory.connect() as database:
            available_names = self._table_names(database)

            for definition in source_definitions:
                resource = definition["resource"]
                expected_names = LEGACY_TABLES[resource]

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

                for row in table:
                    legacy_id = integer(
                        row.get(definition["id_column"])
                    )
                    name = repair_legacy_text(
                        row.get(definition["name_column"])
                    )

                    code_column = definition["code_column"]
                    code = (
                        repair_legacy_text(row.get(code_column))
                        if code_column
                        else ""
                    )

                    if legacy_id is None or not name:
                        continue

                    stages.append(
                        {
                            "legacy_id": legacy_id,
                            "legacy_key": catalog_legacy_key(
                                resource,
                                legacy_id=legacy_id,
                                name=name,
                            ),
                            "legacy_source": definition["legacy_source"],
                            "code": code or None,
                            "name": name,
                            "category": definition["category"],
                            "is_active": True,
                            "legacy_payload": {
                                "table_name": table_name,
                                "legacy_id": legacy_id,
                                "code": code or None,
                                "name": name,
                            },
                        }
                    )

        stages.sort(
            key=lambda stage: (
                stage["category"],
                normalized_search(stage["name"]),
                stage["legacy_id"],
            )
        )

        return stages

    def list_budgeting_tables(self) -> list[dict]:
        """Descreve as tabelas de orçamento permitidas e informa quais existem."""
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

    def list_commercial_tables(self) -> list[dict]:
        """Descreve somente os catálogos comerciais permitidos."""
        with self.factory.connect() as database:
            return self._table_catalog(database, COMMERCIAL_TABLES)

    def list_business_segments(self) -> list[dict]:
        return self._list_commercial_catalog("business-segments")

    def list_company_types(self) -> list[dict]:
        return self._list_commercial_catalog("company-types")

    def _list_commercial_catalog(self, resource: str) -> list[dict]:
        expected_names = COMMERCIAL_TABLES[resource]
        aliases = COMMERCIAL_COLUMN_ALIASES[resource]

        with self.factory.connect() as database:
            available_names = self._table_names(database)
            table_name = self._resolve_table_name(available_names, expected_names)
            if table_name is None:
                similar = self._similar_table_names(available_names.values(), expected_names)
                suffix = f" Tabelas semelhantes: {', '.join(similar)}." if similar else ""
                raise LegacyTableNotFound(
                    "Nenhuma das tabelas Access esperadas foi encontrada: "
                    + ", ".join(expected_names)
                    + suffix
                )

            table = database.getTable(table_name)
            column_names = [column["name"] for column in self._column_metadata(table)]
            id_column = self._resolve_column_alias(column_names, aliases["legacy_id"])
            name_column = self._resolve_column_alias(column_names, aliases["name"])

            if name_column is None:
                raise LegacyColumnNotFound(
                    f"Não foi possível mapear a coluna de nome da tabela {table_name}. "
                    f"Colunas disponíveis: {', '.join(column_names)}"
                )

            by_name: dict[str, dict] = {}
            for row in table:
                name = repair_legacy_text(row.get(name_column))
                if not name:
                    continue
                normalized_name = normalize_company_name(name)
                if not normalized_name:
                    continue
                legacy_id = integer(row.get(id_column)) if id_column else None
                item = {
                    "legacy_id": legacy_id,
                    "legacy_key": catalog_legacy_key(
                        resource,
                        legacy_id=legacy_id,
                        name=name,
                    ),
                    "name": name,
                }
                existing = by_name.get(normalized_name)
                if existing is None or (
                    existing["legacy_id"] is None and legacy_id is not None
                ):
                    by_name[normalized_name] = item

        return sorted(
            by_name.values(),
            key=lambda item: normalized_search(item["name"]),
        )

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
        return self._list_allowed_table(
            allowed_tables=LEGACY_TABLES,
            resource=resource,
            offset=offset,
            limit=limit,
            search=search,
            filter_column=filter_column,
            filter_value=filter_value,
        )

    def list_commercial_table(
        self,
        resource: str,
        offset: int,
        limit: int,
        search: str = "",
        filter_column: str = "",
        filter_value: str = "",
    ) -> dict:
        """Lê dados de propostas permitidos para o importador do BFF."""
        return self._list_allowed_table(
            allowed_tables=PROPOSAL_TABLES,
            resource=resource,
            offset=offset,
            limit=limit,
            search=search,
            filter_column=filter_column,
            filter_value=filter_value,
        )

    def _list_allowed_table(
        self,
        *,
        allowed_tables: dict[str, tuple[str, ...]],
        resource: str,
        offset: int,
        limit: int,
        search: str = "",
        filter_column: str = "",
        filter_value: str = "",
    ) -> dict:
        expected_names = allowed_tables.get(resource)
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

    def list_measurement_units(self) -> list[dict]:
        result = self.list_budgeting_table(
            resource="measurement-units",
            offset=0,
            limit=500,
        )

        units: list[dict] = []

        for row in result["items"]:
            legacy_id = integer(
                row.get("unidadeDeMedidaId")
            )
            name = display_text(
                row.get("unidadeDeMedidaNome")
            )
            abbreviation = display_text(
                row.get("unidadeDeMedidaSigla")
            )

            if legacy_id is None or not abbreviation:
                continue

            units.append(
                {
                    "legacy_id": legacy_id,
                    "name": name,
                    "abbreviation": abbreviation,
                }
            )

        units.sort(
            key=lambda unit: normalized_search(
                unit["abbreviation"]
            )
        )

        return units

    def list_supply_groups(self) -> list[dict]:
        groups_by_name: dict[str, dict] = {}

        name_aliases = {
            "DIVERSOS": "Diversos",
            "EPI S": "EPIs",
            "MTERIAL BASICO": "Material Básico",
            "PINTURA": "Pintura",
        }

        with self.factory.connect() as database:
            for row in self._rows(
                    database,
                    "tblGrupoDeMaterial",
            ):
                legacy_id = integer(
                    row.get("grupoDeMaterialID")
                )
                original_name = display_text(
                    row.get("grupoDeMaterialNome")
                )

                if legacy_id is None or not original_name:
                    continue

                original_key = normalize_company_name(
                    original_name
                )

                name = name_aliases.get(
                    original_key,
                    original_name,
                )

                normalized_name = normalize_company_name(name)
                existing = groups_by_name.get(normalized_name)

                if existing is None:
                    groups_by_name[normalized_name] = {
                        "legacy_id": legacy_id,
                        "name": name,
                    }
                    continue

                # Quando a tabela possui dois cadastros com
                # o mesmo nome, utiliza o menor ID.
                if legacy_id < existing["legacy_id"]:
                    existing["legacy_id"] = legacy_id
                    existing["name"] = name

        groups = list(groups_by_name.values())

        groups.sort(
            key=lambda group: group["legacy_id"]
        )

        return groups

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

    @classmethod
    def _table_catalog(
        cls,
        database: Any,
        resources: dict[str, tuple[str, ...]],
    ) -> list[dict]:
        available_names = cls._table_names(database)
        catalog: list[dict] = []
        for resource, expected_names in resources.items():
            resolved_name = cls._resolve_table_name(available_names, expected_names)
            if resolved_name is None:
                catalog.append({
                    "resource": resource,
                    "expected_table_names": list(expected_names),
                    "table_name": None,
                    "available": False,
                    "row_count": None,
                    "columns": [],
                    "similar_table_names": cls._similar_table_names(
                        available_names.values(), expected_names
                    ),
                })
                continue
            table = database.getTable(resolved_name)
            catalog.append({
                "resource": resource,
                "expected_table_names": list(expected_names),
                "table_name": resolved_name,
                "available": True,
                "row_count": int(table.getRowCount()),
                "columns": cls._column_metadata(table),
                "similar_table_names": [],
            })
        return catalog

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
    def _resolve_column_alias(
        column_names: list[str],
        aliases: tuple[str, ...],
    ) -> str | None:
        names_by_key = {
            normalize_company_name(column_name): column_name
            for column_name in column_names
        }
        for alias in aliases:
            resolved = names_by_key.get(normalize_company_name(alias))
            if resolved is not None:
                return resolved
        return None

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

        if requested_document and work_document:
            return requested_document == work_document

        if name:
            return (
                    normalize_company_name(name)
                    == normalize_company_name(
                work["client_name"]
            )
            )

        return True

    def list_all_tables(self) -> list[str]:
        with self.factory.connect() as database:
            available_names = self._table_names(database)

            return sorted(
                available_names.values(),
                key=str.casefold,
            )
