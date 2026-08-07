# STEP012 Reference Adoption

`/reference` was actively inspected and remained immutable. Runtime code imports only installed packages and project-owned modules.

| Decision | Reference path | Application |
|---|---|---|
| ADOPT | `reference/upstream/openai-agents-python-0.19.0/src/agents/result.py` | Preserve the structured final-output boundary represented by `RunResult.final_output` / `final_output_as`, while consuming the product-owned final-output Artifact rather than recreating an SDK object. |
| ADAPT | `reference/upstream/openai-agents-python-0.19.0/src/agents/usage.py` | Reconstruct deterministic usage metrics from product Run totals and completion Event evidence, with equality checks. |
| ADAPT | `reference/upstream/openai-agents-python-0.19.0/.agents/references/run-item-lifecycle.md` | Keep provider output, public result, persistence, and replay views separate. Product evaluation reads canonical Events and Artifact bytes, not provider or replay objects. |
| REJECT | Direct import or deserialization of upstream `RunResult` | `/reference` is source evidence only; SDK runtime objects are not the durable product record. |
| DEFER | Hosted model judge and automatic release gate | STEP012 remains deterministic and creates no model call. |
