# STEP036B — Sub-Agent invocation and workspace isolation constitution

## Status

`CODE_AUDITED_PLAN_COMPLETE_STEP036_WINDOWS_LIVE_ACCEPTED_BINDING_FOR_STEP040`

This is a planning addendum to STEP036A. It did not implement STEP037 or change the then-current executable Runtime baseline. STEP036 is now Windows live accepted; this constitution remains binding before
executable P0 work.

## 1. Code-derived finding

The retained OpenAI Agents SDK does **not** create an isolated folder merely because execution moves
to another Agent.

- Native Handoff transfers control and selected input/history to another Agent inside the same SDK
  Run. `HandoffInputData` contains input history and Run items, not a filesystem lease.
- `Agent.as_tool()` starts a nested `Runner` and, unless a specific nested `run_config` is supplied,
  inherits the parent Tool context's `run_config`. That is deliberate SDK composition, not workspace
  isolation.
- The SDK Sandbox creates isolation only when the caller explicitly creates a separate
  `SandboxSession` and supplies it through `RunConfig(sandbox=SandboxRunConfig(session=...))`.
- Sandbox `Manifest`, snapshot, mount, capability, and session state are separate product concepts;
  they must not be inferred from an Agent ID or dynamically selected by model output.

Therefore sub-Agent isolation is an OKCanvas Runtime responsibility.

## 2. Three distinct isolation layers

### 2.1 Definition isolation — always mandatory

Every Agent, including a handoff target or Agent-as-Tool child, has an independent immutable
specification directory:

```text
specs/agents/<agent-id>/
├─ definition.json
├─ instructions.md
├─ output.schema.json
├─ policy.yaml
└─ evals/
```

The existing `AgentDefinitionCatalog` already enforces:

- one directory per Agent ID;
- no symbolic Agent directories or definition files;
- no path escape from `specs/agents`;
- definition ID equal to directory name;
- deterministic definition SHA.

A sub-Agent must never be an anonymous prompt fragment constructed dynamically by its parent.

### 2.2 Invocation isolation — always mandatory

Every execution of a child Agent receives its own immutable invocation identity and state namespace,
even when no filesystem is available.

Required identity:

```text
parent_run_id
parent_invocation_id | null
invocation_id
agent_definition_id
agent_definition_sha256
runtime_binding_sha256
invocation_kind = ROOT | HANDOFF | AGENT_AS_TOOL
nesting_depth
```

Required rules:

- a child invocation cannot write lifecycle state using the parent's invocation ID;
- nested Agent usage, Events, interruptions, and terminal result are attributable to one invocation;
- Handoff and Agent-as-Tool use different invocation kinds;
- nested depth and Handoff count are bounded;
- an invocation cannot resolve an Agent outside the closed definition graph;
- generation fencing and terminal-state write barriers apply to child invocations as well as roots.

### 2.3 Filesystem workspace isolation — mandatory only for file-capable invocations

An Agent with `workspace_access=none` receives no physical workspace and no filesystem capability.
Creating empty folders for these Agents would not add security.

When an Agent is allowed to inspect or change files, every invocation receives a separately allocated
workspace or Sandbox session. A parent and child must never share the same writable root by default.

Canonical logical layout:

```text
<runtime-local-state>/workspaces/
└─ <parent-run-id>/
   ├─ <root-invocation-id>/
   ├─ <handoff-invocation-id>/
   └─ <agent-tool-invocation-id>/
```

The path is Runtime-generated from opaque IDs. Model output, prompt text, Agent name, Tool arguments,
and user-supplied relative paths never select the host workspace root.

## 3. Workspace transfer contract

Sub-Agents communicate through explicit contracts, not shared mutable folders.

Allowed transfer forms:

1. typed Agent input;
2. filtered Handoff history;
3. immutable Artifact reference;
4. immutable input snapshot or manifest;
5. explicitly declared read-only mount;
6. bounded exported child result.

Forbidden by default:

- direct parent writable-folder sharing;
- sibling workspace access;
- parent access to unexported child scratch files;
- implicit current-working-directory inheritance;
- symlink, junction, reparse-point, or path-traversal escape;
- environment-secret copying into a workspace;
- model-selected host mounts;
- treating Session history as workspace state;
- treating workspace persistence as conversational memory.

A child that needs the parent's files receives an immutable snapshot or a declared read-only mount.
A child that produces changes exports a reviewable patch or Artifact. The parent must not consume
unbounded mutable child state.

## 4. Workspace lifecycle

For a file-capable invocation:

```text
allocate isolated workspace
→ materialize declared snapshot/manifest
→ verify canonical root and grants
→ execute bounded capabilities
→ produce export manifest / Artifact
→ terminalize invocation
→ delete on safe success or retain on governed failure
```

Required lifecycle metadata:

- workspace ID and provider;
- invocation ID;
- workspace policy version;
- source snapshot or manifest SHA;
- writable and read-only grants;
- capability set;
- quota and timeout;
- created/terminal timestamps;
- cleanup or retention state;
- exported Artifact IDs and hashes.

The protected input payload and workspace are different stores. Deleting one does not imply that the
other was deleted.

## 5. Runtime binding closure

The following must be included in the executable binding before a workspace-capable invocation can
be confirmed:

- child Agent definition graph;
- invocation-isolation policy version;
- workspace provider implementation;
- workspace policy and capability grants;
- materialization implementation;
- manifest or snapshot identity;
- mount policy;
- export/cleanup implementation;
- nested depth and Handoff limits.

A change after preflight requires a new preflight and exact confirmation.

## 6. Relationship to SDK Sandbox

The SDK Sandbox code is adopted as a later file-execution substrate, not silently enabled for all
sub-Agents.

Adopt or adapt later:

- `agents.sandbox.Manifest` for declared materialization;
- one `SandboxSession` per file-capable invocation;
- explicit `Filesystem` and `Shell` capabilities;
- snapshot serialize/resume only under a separately governed lifecycle;
- instrumentation Events and archive/concurrency limits.

Reject:

- sharing one writable Sandbox session among unrelated child Agents;
- allowing `Agent.as_tool()` to inherit a parent Sandbox implicitly;
- automatic Sandbox resume after process loss;
- dynamic provider or mount selection by the model;
- treating Unix-local folder separation alone as a strong untrusted-code security boundary.

For arbitrary code execution, Docker or another real isolation provider is required; separate host
folders alone protect organization and accidental collision, not hostile-process containment.

## 7. Revised P0 order

Sub-Agent invocation identity must exist before native Handoff and Agent-as-Tool are productized.
The revised P0 order is:

1. STEP037 Interactive Agent Runner foundation;
2. STEP038 Generic Function Tool Runtime V1;
3. STEP039 SDK Streaming Event Adapter V1;
4. STEP040 Sub-Agent Invocation Scope Foundation;
5. STEP041 Native Handoff Runtime V1;
6. STEP042 Agent-as-Tool Runtime V1;
7. STEP043 SQLite Session Runtime V1;
8. STEP044 Native Guardrail Runtime V1;
9. STEP045 Integrated Runtime walking-skeleton acceptance.

STEP040 introduces invocation identity, parent/child evidence, bounds, and `workspace_access=none` as
the default. It must not introduce Shell or general Sandbox execution.

STEP041 and STEP042 first slices remain language-only and therefore receive logical invocation
isolation but no physical workspace.

The later Sandbox/file-execution track must allocate one separate workspace/session per invocation
and prove immutable snapshot transfer, export, cleanup, and cross-workspace denial.

## 8. Acceptance requirements for STEP040

Minimum deterministic proof:

- one root invocation and two child invocation identities;
- one HANDOFF child and one AGENT_AS_TOOL child represented without executing new SDK features;
- exact parent-child relationships;
- unique invocation IDs and state namespaces;
- nesting-depth and Handoff-count bounds;
- unresolved and self-referential child definitions rejected;
- `workspace_access=none` produces no physical workspace;
- a fixture workspace policy proves distinct generated roots without enabling model filesystem tools;
- workspace root cannot be supplied by prompt, model, or Agent definition;
- invocation and workspace policy included in Runtime binding;
- no Product Task/Run duplication and no external call in deterministic acceptance.

Actual native Handoff begins only in STEP041; actual Agent-as-Tool begins only in STEP042.

## 9. Skeleton completion gate

`BASIC_AGENT_RUNTIME_SKELETON_COMPLETE` moves from STEP044 to STEP045 and additionally requires:

- visible root/child invocation relationships;
- no writable workspace sharing between file-capable invocations;
- language-only sub-Agents proven to have no filesystem capability;
- all child outputs returned through typed result or immutable Artifact references.
