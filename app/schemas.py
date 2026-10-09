from typing import Any

from pydantic import BaseModel, Field


class AuthenticationRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=255)


class LegacyUser(BaseModel):
    username: str
    legacy_username: str
    full_name: str
    email: str | None = None
    last_legacy_login_at: str | None = None


class AuthenticationResponse(BaseModel):
    authenticated: bool
    detail: str | None = None
    legacy_user: LegacyUser | None = None
    groups: list[dict] = Field(default_factory=list)
    modules: list[dict] = Field(default_factory=list)
    permissions: list[dict] = Field(default_factory=list)


class ClientResponse(BaseModel):
    name: str
    document: str


class ClientCatalogItemResponse(BaseModel):
    legacy_id: int
    legacy_key: str = Field(min_length=64, max_length=64)
    name: str
    trade_name: str = ""
    document: str = ""
    company_type_name: str = ""
    business_segment_name: str = ""
    address: str = ""
    district: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    legacy_payload: dict[str, Any] = Field(default_factory=dict)


class WorkResponse(BaseModel):
    legacy_work_id: int | None
    legacy_proposal_id: int | None
    cost_center: str
    work_name: str
    client_name: str
    client_document: str
    attention_to_suggestion: str
    delivery_address: str
    delivery_phone: str


class LegacyTableColumnResponse(BaseModel):
    name: str
    type: str


class LegacyTableInfoResponse(BaseModel):
    resource: str
    expected_table_names: list[str]
    table_name: str | None = None
    available: bool
    row_count: int | None = None
    columns: list[LegacyTableColumnResponse] = Field(default_factory=list)
    similar_table_names: list[str] = Field(default_factory=list)


class LegacyTablePageResponse(BaseModel):
    resource: str
    table_name: str
    columns: list[LegacyTableColumnResponse]
    items: list[dict[str, Any]]
    offset: int
    limit: int
    has_more: bool
    next_offset: int | None = None


class SupplyGroupResponse(BaseModel):
    legacy_id: int | None
    name: str


class CommercialCatalogItemResponse(BaseModel):
    legacy_id: int | None = None
    legacy_key: str = Field(min_length=64, max_length=64)
    name: str

class BudgetStageCatalogItemResponse(BaseModel):
    legacy_id: int
    legacy_key: str = Field(min_length=64, max_length=64)
    legacy_source: str
    code: str | None = None
    name: str
    category: str
    is_active: bool = True
    legacy_payload: dict[str, Any] = Field(default_factory=dict)