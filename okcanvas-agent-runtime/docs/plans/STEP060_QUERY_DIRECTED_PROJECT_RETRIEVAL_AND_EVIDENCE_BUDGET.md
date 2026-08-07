# STEP060 — Query-directed Project Retrieval and Evidence Budget

## Baseline

- Project: `okcanvas-agent-runtime`
- Version: `2.40.0`
- STEP: `STEP060_QUERY_DIRECTED_PROJECT_RETRIEVAL_AND_EVIDENCE_BUDGET`
- State: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_REAL_OPENAI_RERUN_PENDING`

## Why this STEP

STEP059B is Windows-live accepted: installed `openai-agents==0.19.0` constructed the Product Tools
and a real Node CLI/OpenAI run completed the full model → Tool → model lifecycle. The real user
question was narrow—locate the Health API registration—but the Tool returned a broad 12-file bundle,
the Agent produced unrelated findings, the Artifact was PARTIAL, and total usage was 8,086 tokens.

Code audit proved the cause was Product retrieval, not the model or SDK. The inspector read every
bounded text file, scored whole files with broad tokens such as `api`, selected up to 12 files, and
used the first matching line in each file with excerpts up to 4,000 characters. Root documents,
clients and tests could outrank the exact implementation decorator.

## Product scope

1. Keep one server-owned read-only project root and the existing `project_readonly_inspect` Tool.
2. Reduce Korean/English query text to bounded meaningful terms and discard request phrasing.
3. Weight rare terms across the candidate corpus and score the best line window in each file.
4. Recognize route-registration and definition-location code structure without executing code.
5. Prefer implementation source by default; prefer tests/docs/client only when explicitly requested.
6. Return at most four evidence files, 16 lines/1,600 characters per excerpt, and 5,000 aggregate
   evidence characters.
7. Require the Agent to answer only the exact question, name the precise file/line first, prefer
   implementation source, emit no more than three findings, and suppress unrelated audits.
8. Preserve all STEP059 filesystem, symlink, exclusion, persistence and authority boundaries.

## Explicit exclusions

No file write, Shell, process, Git command, network, web, MCP, Approval, Handoff, Agent-as-Tool,
Guardrail, Session, embedding index, vector database, persistent repository index, AST parser,
language server, test execution, multi-workspace selection or Sandbox.

## Acceptance

The exact Korean Health API question runs against a fixture containing the implementation decorator,
a client call, a test, a repeated legacy document, unrelated authentication text and an excluded
`node_modules` sentinel. The implementation source must be first, the exact decorator and handler
must be in the primary line window, unrelated document/auth evidence must be absent, all evidence
budgets must hold, the answer must be direct, Product counts must remain `1/1/1/1/12/1/0`, the
workspace must remain byte-identical, payload cleanup must complete, and References must remain
unchanged.

Windows closure additionally requires one real OpenAI rerun of the same question with the exact
implementation file/line in the answer, Artifact PASS, no unrelated audit, and total usage at or
below 5,000 tokens. STEP061 is blocked until both deterministic and real Windows evidence pass.
