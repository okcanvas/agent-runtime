# STEP033_AGENT_RUNTIME_BINDING_FINGERPRINT

## Goal

Bind executable Agent Runtime behavior to the governed submission confirmation fingerprint and fail closed when the Runtime changes before execution.

## Confirmed defect

The prior submission fingerprint did not bind output-contract Runtime behavior, SDK version, MCP executable definitions, controlled local Tool policy/implementation, or the common execution engine. A package or policy replacement could therefore alter post-confirmation behavior without changing the Agent definition SHA.

## Scope

- introduce a product-owned `AgentRuntimeBindingCatalog`;
- fingerprint the selected output-contract Runtime;
- fingerprint exact MCP declarations and implementation modules;
- fingerprint controlled local Tool policy and implementation modules;
- fingerprint the selected execution engine and expected installed SDK version;
- persist the binding SHA in the request fingerprint, SQLite ledger, protected payload, and prepared execution state;
- verify the current binding before generic execution and local Tool preparation;
- fail before Product state or external execution on any mismatch;
- add deterministic and Windows acceptance paths;
- record STEP031 and STEP032 Windows live closure.

## Non-goals

- no new business domain function;
- no dynamic plugin registry;
- no new Tool/MCP/write authority;
- no automatic migration of old pending submissions;
- no Session, Handoff, distributed worker, or automatic running-Run restart recovery;
- no direct `/reference` import.

## Acceptance

Require all checks true:

- the current Coding, read-only MCP, and controlled local Tool bindings are distinct;
- SDK, output contract, MCP definition/module, Tool policy/implementation, and engine are bound;
- Runtime binding SHA is present in the submission ledger and encrypted payload;
- Runtime binding participates in the confirmation fingerprint;
- output-contract Runtime drift conflicts on idempotent replay and blocks confirmation;
- MCP definition drift blocks confirmation;
- local Tool policy drift blocks preparation;
- all drift cases create zero Task/Run/approval state and call no scheduler, model, MCP, or Tool;
- binding material contains no credential;
- References are unchanged;
- cleanup is `COMPLETED`.

## Windows closure gate

Run `sh_run_step033_acceptance.cmd` from the packaged project and require `state=PASSED`, all 20 checks true, `binding_count=3`, all three drift failures exact, no Product or external-call state, and cleanup `COMPLETED`.
