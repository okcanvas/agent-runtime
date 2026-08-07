# STEP061 — OpenAI Agents SDK Examples Coverage Matrix and Next Scope Selection

## Status

`IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

- Project: `okcanvas-agent-runtime`
- Version: `2.41.0`
- STEP: `STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX_AND_NEXT_SCOPE_SELECTION`
- Predecessor: STEP060 Windows live accepted from user-reported deterministic and real OpenAI evidence.

## Objective

Freeze a complete file-level decision for every OpenAI Agents SDK 0.19.0 capability example before
adding another Runtime capability. The matrix must be sufficient for a future conversation to
reconstruct why a capability is already present, narrowed, deferred, or rejected without relying on
chat history.

## Scope

1. Recount the immutable SDK `examples` tree.
2. Classify exactly 212 capability/example Python files across 15 areas as `ADOPT`, `ADAPT`,
   `DEFER`, or `REJECT`.
3. Record every source file SHA-256, line count, observed SDK symbols, product evidence, target
   track, and priority.
4. Close STEP060 documentation with the user-reported Windows evidence.
5. Select exactly one next implementation STEP from current code gaps.
6. Add deterministic acceptance that fails on source drift, missing classification, count drift,
   invalid evidence paths, or next-step ambiguity.

## Outputs

- `docs/reference/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX.json`;
- `docs/reference/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX.md`;
- `docs/reference/STEP061_OPENAI_AGENTS_EXAMPLES_COVERAGE_MATRIX_AND_NEXT_SCOPE_SELECTION_CODE_AUDIT.md`;
- `docs/evidence/STEP060_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`;
- `scripts/run_step061_acceptance.py`;
- `sh_run_step061_acceptance.cmd`;
- updated baseline, handoff, roadmap, README, and constitution.

## Decisions

The matrix is authoritative at file level. Summary counts are:

```text
ADOPT  16
ADAPT  16
DEFER 171
REJECT  9
TOTAL 212
```

The next implementation STEP is fixed as:

```text
STEP062_BOUNDED_MULTI_AGENT_ORCHESTRATION_FOUNDATION
```

## Explicit exclusions

No orchestration implementation, new Agent, model call, Tool, MCP transport, Session backend,
provider, hosted Tool, multimodal input, prompt mutation, Sandbox, shell, filesystem write,
Realtime, or Voice capability is added in STEP061.

## Acceptance

The deterministic acceptance must prove:

1. the immutable example tree contains 216 Python files;
2. the four exact root support files are excluded;
3. the matrix contains 212 unique entries and 15 exact areas;
4. all file SHA-256 values match the immutable source;
5. every entry has one allowed decision and one target track;
6. decision counts are exactly `16/16/171/9`;
7. current-product evidence paths exist for every ADOPT/ADAPT entry that declares evidence;
8. key policy examples have exact expected decisions;
9. all 71 Sandbox examples are deferred to the independent Sandbox track;
10. STEP060 closure evidence records 20/20, Artifact PASS, `app.py:485-487`, and 2,688 tokens;
11. STEP062 is the single selected next implementation scope;
12. References remain unchanged.

No live model call is required because STEP061 changes no executable Agent capability.
