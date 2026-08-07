# STEP071_PRODUCT_SKILL_DOCUMENT_REVIEW_LIVE_ACCEPTANCE_V1

## Baseline

- predecessor: STEP070 / 2.50.0 / Windows live accepted 30/30;
- implementation version: 2.51.0;
- immutable Skill package remains `document-review-v1` version `1.0.0`;
- package SHA-256 remains `60fbfca861141837d4486499687fde4257b83bcb68362b6b0a0b6f40b8df07b5`.

## Code-audit finding

STEP070 proved package integrity, explicit Agent binding, deterministic effective instructions,
Runtime-binding identity and metadata-only service discovery without a model call. It did not prove
that a real service-client workflow can upload a visible document, invoke the Skill-enabled Agent,
produce the strict result contract and persist only bounded evidence.

The existing code already contains the complete production path. STEP071 therefore adds a live
acceptance harness and does not mutate the Skill package or add a new capability.

## Selected scope

1. load `.env.local` as configuration data through `windows_entrypoint.py` without executing it;
2. require `OPENAI_API_KEY` and the current attachment-policy model `gpt-4.1`;
3. generate one deterministic valid one-page PDF with visible reference, amount, due date,
   unapproved decision, illegible approver and an embedded untrusted instruction;
4. use only `/v1/service/**` APIs for Skill metadata, Agent metadata, attachment upload, governed
   preflight, exact confirmation, Run polling, persisted Events and verified Artifacts;
5. make one actual OpenAI model call through `skill-document-review-agent`;
6. validate `LocalDocumentReviewResult`, required visible facts, `unverified` handling, positive
   token usage and absence of undeclared Tool/MCP/Hosted Tool/Handoff activity;
7. verify raw attachment bytes and API Key are absent from persisted acceptance files;
8. keep all live evidence under ignored `docs/evidence/step071-live/**`.

## Explicit exclusions

- no change to `document-review-v1` instructions, resources, manifest, version or hashes;
- no second Skill package;
- no user Skill upload, marketplace, executable Skill code, Shell or dependency installation;
- no final independent `agent-cli`, `agent-web` or `agent-desktop` implementation;
- no claim of Windows live acceptance until the complete Windows output is received.

## Windows command

From a freshly extracted project root with `.env.local` containing the two required values:

```cmd
sh_run_step071_live_acceptance.cmd
```

The current policy requires:

```text
OKCANVAS_AGENT_MODEL=gpt-4.1
```

A different model fails readiness before any provider call.


## Windows closure

The user ran both commands on Windows. Deterministic acceptance passed 28/28 and live acceptance
passed 28/28 with `gpt-4.1`, one model call, 1,145 total tokens, terminal status `SUCCEEDED`, exact
fixture facts, prompt-injection resistance, no undeclared capability Events, no persisted API Key or
raw PDF, deleted successful payload and cleanup `COMPLETED`. Compact evidence is retained in
`docs/evidence/STEP071_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json`.

A trailing non-fatal SDK `Tracing client error 400` was observed after the successful JSON and became
the code-audited trigger for STEP072.
