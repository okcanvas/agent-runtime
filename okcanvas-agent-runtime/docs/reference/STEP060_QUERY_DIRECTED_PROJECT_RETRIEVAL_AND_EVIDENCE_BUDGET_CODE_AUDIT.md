# STEP060 Code Audit — Query-directed Project Retrieval and Evidence Budget

## Accepted predecessor

The user reported complete STEP059B actual-SDK acceptance and one real Windows/OpenAI Tool run. SDK
wiring is therefore accepted. The real run used 8,086 tokens and returned PARTIAL for a simple Health
API location question, so relevance and token efficiency remained open.

## Inspected Product path

- `src/okcanvas_agent_runtime/workspace/read_only_project.py`
- `src/okcanvas_agent_runtime/function_tools/models.py`
- `src/okcanvas_agent_runtime/function_tools/implementations.py`
- `src/okcanvas_agent_runtime/function_tools/factories.py`
- `src/okcanvas_agent_runtime/execution/openai_gateway.py`
- `specs/tools/project-readonly-inspect/*`
- `specs/agents/project-readonly-coding-agent/*`
- `tests/test_project_readonly_inspection.py`
- `scripts/run_step059_acceptance.py`
- user-reported STEP059B real Artifact and Event sequence

## Confirmed pre-STEP060 behavior

`openai_gateway.py` intentionally sends only an opaque execution instruction to the first model call;
the original user request remains server-side and is passed to the Tool as protected text. The Tool
therefore owns retrieval relevance.

The prior inspector:

- extracted up to 12 raw tokens, including Korean request phrases;
- read every allowed file up to the existing 3,000-file/32-MiB boundary;
- gave root documents and common filenames a positive priority;
- scored broad whole-file token counts, so common `api` occurrences dominated;
- selected 12 evidence files;
- chose the first line containing any keyword;
- returned up to 40 lines and 4,000 characters per file.

Running the user's exact Korean question against the packaged repository reproduced 1,126 files and
4,307,466 bytes considered. The first evidence was `clients/okcanvas-agent-cli/src/api-client.ts`,
while the actual registration was `src/okcanvas_agent_runtime/control_api/app.py:485-486`.

## Implemented correction

The query profile keeps only meaningful bounded terms (`health`, `api` for the observed question),
uses corpus document frequency to down-weight common terms, and scores the best five-line window in
each file. Route registration patterns such as FastAPI decorators and router method calls receive a
structural bonus only when aligned with query terms. Default ranking prefers implementation source
and excludes tests/docs from the selected pool unless the user explicitly targets them.

Evidence is reduced to at most four files, 16 lines and 1,600 characters per file, and 5,000 aggregate
characters. The observed repository now ranks `control_api/app.py` first with the adjacent
`@app.get("/healthz")` and `async def health` lines. The total selected evidence is 2,706 characters
in the code-audit reproduction rather than the prior 12-file bundle.

Agent instructions now require a narrow direct answer, implementation-source preference, exact
relative file/line first, at most three findings, PASS when the requested fact is directly found, and
no unrelated architecture/security/history/readiness audit.

## Preserved boundaries

The Tool still reads one server-configured root, follows no symlinks, excludes dependency/generated/
local-state/immutable Reference directories, reads text candidates only, writes nothing, runs no
process, uses no network, persists no raw Tool arguments/results, and returns relative paths only.
The installed SDK import/output corrections from STEP059A/B remain unchanged.
