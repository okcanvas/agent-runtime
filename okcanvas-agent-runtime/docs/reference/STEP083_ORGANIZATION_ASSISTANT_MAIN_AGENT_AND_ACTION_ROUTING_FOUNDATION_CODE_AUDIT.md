# STEP083 Organization Assistant Main Agent and Action Routing Foundation — Code Audit

## Audited parent

The implementation starts from immutable STEP082B / 2.62.2. STEP082B fixes `GenericAgentExecutionService` as the sole Product execution plane and separates Runtime, Product Configuration and immutable Reference artifacts.

## Existing boundaries inspected

- `AgentDefinitionCatalog` and `AgentRuntimeBindingCatalog`;
- governed submission, confirmation and execution services;
- Admin and Service REST protocols/routes/use cases;
- Session, local attachment and immutable project snapshot ownership;
- hosted Web Search, local document review and read-only Sandbox Agents;
- capability topology and discovery policy;
- output runtime registry;
- launcher registry, Architecture route inventory and distribution startup matrix.

## Code findings

### No Agent-ID-free Product entrypoint existed

Existing governed preflight required an `agent_definition_id`. Users or clients had to know a Product Agent identifier before submitting a natural-language request.

### Existing capabilities could be reused

The current catalog already contained bounded capabilities for public Web search, local attachment review and immutable repository read-only analysis. STEP083 routes to these definitions and does not create duplicate Tools or execution planes.

### Organization and enterprise capabilities were absent

No organization glossary, directory, ERP, ESS, Groupware write adapter or durable automation runtime was present. The safe contract is therefore an explicit `NOT_CONFIGURED` or proposal-only result, not simulated execution.

### Admin snapshot forwarding defect

`AdminUseCases.preflight_governed_run` accepted a project snapshot in the protocol but omitted it when invoking the submission service. This was corrected and recorded as OR-ISSUE-063.

### Historical exact-count gate

The retained STEP082B execution-plane validator coupled policy preservation to an exact 27-Agent total and current STEP082B identity. STEP083 separates retained policy proof from current Product topology, recorded as OR-ISSUE-064.

### Deterministic lexicon ambiguity

The word `메일` alone caused an ordinary writing request to look like an enterprise transaction. The policy now requires transaction semantics for draft/write routing, recorded as OR-ISSUE-065.

## Implemented modules

```text
okcanvas_agent_runtime/application/assistant_routing/
  models.py
  catalog.py
  service.py

specs/assistant/routing-policy.json
specs/agents/organization-assistant-agent/
specs/agents/organization-assistant-session-agent/
```

Protocols, Service/Admin use cases and routes expose Agent-ID-free session, route and preflight APIs. `OrganizationAssistantResult` is registered in the Product output runtime.

## Fail-closed behavior

- organization knowledge and system read requests produce no governed submission when unavailable;
- write and automation requests may create only an Organization Assistant proposal run;
- response schema forbids completed actions for write/automation side-effect classes;
- instructions forbid claiming filesystem, system, MCP, Tool or Scheduler access that did not occur;
- session plus a non-composable specialist capability returns a bounded non-executable route instead of silently dropping context.

## Capability state after STEP083

```text
Agent definitions: 29
Capability bindings: 34
Function Tool definitions: 4
MCP allowlist: reference-catalog only
Tool Search runtime: disabled
Programmatic Tool calling runtime: disabled
Organization knowledge: not configured
Enterprise read/write: not configured
Durable automation: not configured
```

## Architecture continuity

The Product execution plane remains Generic Runtime. Six Assistant routes are additive. Architecture route inventory becomes Admin 51, Service 36, Other 5, total HTTP 92, with no missing or duplicate method/path pairs.
