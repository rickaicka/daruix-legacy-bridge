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
