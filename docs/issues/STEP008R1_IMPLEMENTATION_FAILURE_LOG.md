# STEP008R1 Implementation Failure Log

## F001 — Windows deterministic execution was initially mistaken for Live acceptance

- **Observed:** `sh_run_workspace_step008_acceptance.cmd` passed 21/21 on Windows, but its evidence explicitly reported `live_openai_model_called=false`; no STEP008 Live launcher existed.
- **Incorrect conclusion withdrawn:** A process running on Windows is not itself a Windows Live OpenAI acceptance.
- **Correction:** STEP008R1 adds an explicit opt-in Live launcher and actual OpenAI full-process harness. Deterministic and Live states remain separate promotion conditions.
- **Recurrence gate:** A promotion statement must cite `actual_openai_model_called=true` from a current-step Live evidence file; `execution_platform=windows` is insufficient.

## F002 — Reusing STEP007R1 Live exposed a same-name ModelBehaviorError but did not test short routing

- **Observed:** The existing STEP007R1 harness called `gpt-4.1`, the Connector and Node Example. Turn 1 succeeded; Turn 2 completed `resolve_organization_context` and then failed with `SDK_RUN_FAILED`, `detail_type=ModelBehaviorError`. Final result was 19/24.
- **Evidence limit:** Raw provider error, Tool arguments and Tool results were intentionally not persisted, so the exact output-contract violation is not proven. The prompts also contained explicit `조직 문맥` text and therefore did not exercise STEP008's hint-free route.
- **Correction:** STEP008R1 owns four exact short utterances, preflights their request hints and records bounded per-turn Agent/Run failure diagnostics. No model-output correction is guessed before the new harness reproduces the failing case.
- **Recurrence gate:** Live failure evidence must identify the exact utterance, run status, model event counts, Agent/Tool completion counts, expected Tool and safe `code/detail_type/retryable` fields without persisting raw sensitive payloads.

## F003 — Live CLI output decoding must reuse the Workspace Windows decoder

- **Observed:** The retained STEP007R1 Live log showed locale-garbled CLI text, while the harness searched Korean completion text directly.
- **Correction:** STEP008R1 uses `workspace_process.decode_process_output`, which tries UTF-8 first, then the platform-preferred encoding and CP949 on Windows.
- **Recurrence gate:** Live subprocess evidence records the selected stdout/stderr encoding and never decodes captured bytes with a single hard-coded codec.

## F004 — Foreground integrated acceptance exceeded the container command window

- **Observed:** Two foreground executions were terminated by the orchestration command limit before final JSON was emitted. No incomplete run was accepted.
- **Correction:** Execute the same unmodified acceptance as a managed shell child, poll its stage log, and require an explicit exit-code file plus final evidence JSON. The completed run returned 0 and 24/24.
- **Recurrence gate:** A timeout without final evidence is neither pass nor product failure; promotion requires the acceptance process exit code and parsed final state.

## F005 — Direct Connector debugging mutated retained parent evidence

- **Observed:** Running the Connector acceptance in its source directory rewrote `CONNECTOR_ORGANIZATION_CONTEXT_STEP002R2_ACCEPTANCE.json`, breaking parent byte identity.
- **Correction:** Restore the exact parent byte from the STEP008 package. Integrated Workspace acceptance continues to execute Connector acceptance only from a temporary project copy.
- **Recurrence gate:** Parent acceptance debugging must use a copy or an explicit external output path; immutable parent project trees are never run in-place when their default evidence output is included in the parent manifest.
