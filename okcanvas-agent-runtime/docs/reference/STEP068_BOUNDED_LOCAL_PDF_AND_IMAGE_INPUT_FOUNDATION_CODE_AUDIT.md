# STEP068 Code Audit

## Baseline inspected

`STEP067_HOSTED_WEB_SEARCH_SOURCE_POLICY_AND_EVIDENCE_FOUNDATION`, version `2.47.0`, reported Windows
live accepted 26/26.

## Why File Search was not selected

The pinned SDK `FileSearchTool` requires `vector_store_ids`. Its example creates an OpenAI File,
creates a Vector Store and waits for indexing. This repository has no Product-owned provider-file
or Vector Store creation, ownership, retention, expiration, deletion or corpus fingerprint
lifecycle. Accepting an opaque pre-provisioned ID would not bind the corpus contents.

Pinned references inspected:

- `reference/upstream/openai-agents-python-0.19.0/examples/tools/file_search.py`
- `reference/upstream/openai-agents-python-0.19.0/src/agents/tool.py`

## Existing direct-input capability

The pinned SDK directly accepts local PDF and image data URLs without provider resource creation:

- `reference/upstream/openai-agents-python-0.19.0/examples/basic/local_file.py`
- `reference/upstream/openai-agents-python-0.19.0/examples/basic/local_image.py`

The current Product API, protected payload and execution gateway were text-only, so Product-owned
typed input and encrypted attachment ingress were required before using those SDK shapes.

## Implemented code paths

- `src/okcanvas_agent_runtime/attachments/` owns policy, signature validation, model capability and
encrypted slot/bound storage.
- `ProtectedPayloadContent` v4 binds only encrypted attachment identity and validated metadata.
- `RunSubmissionBoundaryService` consumes exactly one slot and fingerprints its metadata.
- `GovernedReadOnlyRunSubmissionService` authenticates and decrypts the bound attachment only at
execution time.
- `OpenAIGenericAgentGateway` builds the pinned SDK two-message `input_file`/`input_image` shape in
memory.
- `GenericAgentExecutionService` writes a separate metadata-only
`agent.local-attachment-evidence` Artifact.
- `GovernedExecutionLifecycleService` deletes the bound attachment with protected-payload cleanup.

## Boundaries retained

Existing text-only requests remain strings. No generic request-dict migration was introduced.
No provider File ID, URL, vector store, raw byte Event, raw byte Artifact or attachment download
surface exists. Direct `/v1/runs` cannot execute the local-document Agent because it has no governed
attachment binding.
