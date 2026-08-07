# STEP071 code audit

## Audited package

- STEP070 final ZIP SHA-256:
  `9b0a19eada75d25a11296eb66a863e2ffe5362601b8ceb93fdd52be08fe4c0d6`;
- user-reported Windows STEP070 result: 30/30 PASS;
- Skill package SHA-256:
  `60fbfca861141837d4486499687fde4257b83bcb68362b6b0a0b6f40b8df07b5`.

## Confirmed execution path

1. `service_clients/routes.py` accepts authenticated local attachment bytes at
   `POST /v1/service/local-attachments` and records principal ownership of the encrypted slot.
2. `POST /v1/service/run-submissions/preflight` verifies ownership and delegates to the existing
   governed Submission boundary.
3. Preflight binds the attachment to the Submission and removes the reusable slot.
4. `POST /v1/service/run-submissions/{id}/confirm` schedules the existing governed execution.
5. `execution/openai_gateway.py` resolves `skill-document-review-agent`, composes effective
   instructions through `resolve_effective_instructions()`, and sends one data-URL PDF input to the
   pinned OpenAI Responses provider.
6. `MultimodalModelPolicyCatalog` permits exactly `gpt-4.1` for local PDF/image input.
7. Product Run Events and Artifacts are exposed to the same principal through `/v1/service/runs/**`.
8. Raw attachment bytes are excluded from Product Events and Artifacts; only the encrypted temporary
   store and a bounded attachment-evidence Artifact are used.

## Existing Skill boundary retained

`document-review-v1` remains an immutable static package. It requires no Tool, MCP server, Hosted
Tool, Session, child Agent, workspace, Shell, network permission or executable code. STEP071 does not
change its files because changing content under the same immutable Skill version would violate the
STEP070 package identity contract.

## Live acceptance design

The fixture is a structurally valid one-page PDF with visible text. It contains exact high-entropy
facts, one explicitly unresolved approver and one instruction-looking sentence inside the document.
The review request names only the classes of facts to extract; it does not disclose the fixture
reference, amount, date, decision, or unresolved approver text. It tells the reviewer to treat document
instructions as untrusted content. The acceptance checks the strict output contract, exact facts,
unresolved approver handling, one observed model start/completion pair, positive token usage and zero
undeclared capability events.

## Security findings

- `.env.local` is parsed as data and never `call`ed or sourced by the launcher;
- the API Key is never added to JSON output and persisted files are scanned for its bytes;
- live evidence is ignored from source packaging;
- failure evidence is retained in the isolated acceptance workspace without packaging it;
- provider network access is required for the intended OpenAI model execution; exact HTTP request
  count is not claimed because the current Runtime does not instrument transport requests. The
  persisted `model.started`/`model.completed` pair is the authoritative model-invocation evidence.
