from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SearchInput(StrictModel):
    query: str = Field(default="", max_length=500)
    limit: int = Field(default=20, ge=1, le=50)


class CalendarInput(StrictModel):
    start_at: str | None = Field(default=None, max_length=64)
    end_at: str | None = Field(default=None, max_length=64)
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def _range_is_complete(self) -> "CalendarInput":
        if (self.start_at is None) != (self.end_at is None):
            raise ValueError("start_at and end_at must be supplied together")
        return self


class GroupwareApiResponse(StrictModel):
    records: list[dict[str, Any]]


class ToolResult(StrictModel):
    schema_version: Literal["okcanvas-groupware-read-provider-result-v1"] = (
        "okcanvas-groupware-read-provider-result-v1"
    )
    result_schema_version: str
    tool_name: Literal["search_notices", "search_mail", "list_calendar_events"]
    tenant_id: str
    principal_id: str
    roles: list[str]
    delegation_id: str
    mutated: Literal[False] = False
    records: list[dict[str, Any]]
    request_id: str


class ToolError(StrictModel):
    schema_version: Literal["okcanvas-groupware-mcp-error-v1"] = "okcanvas-groupware-mcp-error-v1"
    error_code: str
    message: str
    retryable: bool
    http_status: int | None = None
    request_id: str
