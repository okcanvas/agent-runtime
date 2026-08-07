from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

EntityType = Literal["TERM", "DEPARTMENT", "POSITION", "EMPLOYEE", "PRODUCT", "CLIENT", "PROJECT", "SYSTEM", "CAPABILITY"]


class ContextResolveInput(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    entity_types: list[EntityType] = Field(default_factory=list, max_length=9)
    organization_unit_id: str | None = Field(default=None, min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=20)


class ContextSearchInput(StrictModel):
    query: str = Field(default="", max_length=500)
    entity_types: list[EntityType] = Field(default_factory=list, max_length=9)
    organization_unit_id: str | None = Field(default=None, min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=20)


class GetEntityInput(StrictModel):
    entity_type: EntityType
    entity_id: str = Field(min_length=1, max_length=200)


class ResolveInput(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    organization_unit_id: str | None = Field(default=None, min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=20)


class SearchInput(StrictModel):
    query: str = Field(default="", max_length=500)
    organization_unit_id: str | None = Field(default=None, min_length=1, max_length=200)
    limit: int = Field(default=20, ge=1, le=50)


class EmptyInput(StrictModel):
    pass


class GetTermInput(StrictModel):
    term_id: str = Field(min_length=1, max_length=200)


class ChangeInput(StrictModel):
    after_revision: int = Field(ge=0)
    limit: int = Field(default=100, ge=1, le=200)


class ApiPayload(BaseModel):
    model_config = ConfigDict(extra="allow")


class ToolError(StrictModel):
    error_code: str
    message: str
    retryable: bool
    request_id: str
    http_status: int | None = None


class ToolResult(StrictModel):
    result_schema_version: str
    tool_name: str
    tenant_id: str
    principal_id: str
    roles: list[str]
    organization_unit_id: str | None
    delegation_id: str
    catalog_revision: int | None
    resolved: bool | None
    ambiguous: bool | None
    records: list[dict[str, Any]]
    changes: list[dict[str, Any]]
    response_shape: str | None = None
    candidate_count: int | None = None
    returned_count: int | None = None
    truncated: bool | None = None
    request_id: str
    mutated: Literal[False] = False
