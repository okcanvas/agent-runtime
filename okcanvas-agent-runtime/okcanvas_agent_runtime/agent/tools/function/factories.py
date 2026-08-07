from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from okcanvas_agent_runtime.agent.tools.function.errors import FunctionToolExecutionError
from okcanvas_agent_runtime.agent.tools.function.implementations import local_text_fingerprint, local_text_metrics
from okcanvas_agent_runtime.agent.tools.function.models import FunctionToolRuntime, LocalTextExecutionInput, ToolExecutor


_LegacyProjectInspectExecutor = Callable[[str | Path, str], BaseModel | dict[str, Any]]
_legacy_project_inspect_executor: _LegacyProjectInspectExecutor | None = None


def install_legacy_project_inspect_executor(executor: _LegacyProjectInspectExecutor) -> None:
    """Install the pre-STEP081 synchronous project inspection compatibility adapter."""
    global _legacy_project_inspect_executor
    _legacy_project_inspect_executor = executor


def execute_product_tool(
    runtime: FunctionToolRuntime,
    protected_text: str,
    *,
    workspace_root: str | Path | None = None,
) -> BaseModel:
    if runtime.factory_id == "local_text_fingerprint_v1":
        output = local_text_fingerprint(protected_text)
    elif runtime.factory_id == "local_text_metrics_v1":
        output = local_text_metrics(protected_text)
    elif runtime.factory_id == "project_readonly_inspect_v1":
        if workspace_root is None or _legacy_project_inspect_executor is None:
            raise FunctionToolExecutionError(
                "Project inspection workspace or Adapter executor is not configured"
            )
        output = _legacy_project_inspect_executor(workspace_root, protected_text)
    else:
        raise FunctionToolExecutionError("Registered Function Tool factory is unavailable")
    try:
        return runtime.output_model.model_validate(output, strict=True)
    except ValidationError as exc:
        raise FunctionToolExecutionError("Function Tool output contract failed") from exc


def invocation_prompt(runtime: FunctionToolRuntime, execution_id: str) -> str:
    return (
        f'Invoke {runtime.tool_id} exactly once with execution_id="{execution_id}". '
        "Use only the Tool result as confirmed evidence and return the configured structured output."
    )


def build_sdk_function_tool(
    runtime: FunctionToolRuntime,
    *,
    execution_id: str,
    protected_text: str | None = None,
    executor: ToolExecutor | None = None,
    workspace_root: str | Path | None = None,
) -> Any:
    if (protected_text is None) == (executor is None):
        raise FunctionToolExecutionError(
            "Exactly one Function Tool execution source must be configured"
        )
    try:
        from agents import function_tool
        from agents.tool_context import ToolContext
    except (ImportError, ModuleNotFoundError) as exc:
        raise FunctionToolExecutionError("OpenAI Agents Function Tool SDK is unavailable") from exc

    async def raw_tool(ctx: Any, execution_id: str) -> BaseModel:
        try:
            parsed = LocalTextExecutionInput.model_validate(
                {"execution_id": execution_id}, strict=True
            )
        except ValidationError as exc:
            raise FunctionToolExecutionError("Function Tool arguments were invalid") from exc
        context_execution_id = str(ctx.context.get("execution_id", ""))
        if parsed.execution_id != context_execution_id:
            raise FunctionToolExecutionError("Function Tool execution identity mismatch")
        if executor is not None:
            raw_output = await executor()
            try:
                return runtime.output_model.model_validate(raw_output, strict=True)
            except ValidationError as exc:
                raise FunctionToolExecutionError("Function Tool output contract failed") from exc
        assert protected_text is not None
        return execute_product_tool(runtime, protected_text, workspace_root=workspace_root)

    raw_tool.__name__ = runtime.tool_id
    raw_tool.__doc__ = runtime.description
    raw_tool.__annotations__ = {
        "ctx": ToolContext[dict[str, Any]],
        "execution_id": str,
        "return": runtime.output_model,
    }
    tool = function_tool(
        name_override=runtime.tool_id,
        description_override=runtime.description,
        use_docstring_info=False,
        failure_error_function=None,
        strict_mode=runtime.strict_json_schema,
        needs_approval=runtime.approval_mode.value == "ALWAYS",
        # openai-agents 0.19.0 treats output_type and output_json_schema as
        # mutually exclusive. Keep the typed contract so the SDK generates the
        # strict output schema and validates the Tool result from one source.
        output_type=runtime.output_model,
    )(raw_tool)
    setattr(tool, "_okcanvas_function_tool_id", runtime.tool_id)
    setattr(tool, "_okcanvas_function_tool_runtime_version", runtime.runtime_version)
    return tool
