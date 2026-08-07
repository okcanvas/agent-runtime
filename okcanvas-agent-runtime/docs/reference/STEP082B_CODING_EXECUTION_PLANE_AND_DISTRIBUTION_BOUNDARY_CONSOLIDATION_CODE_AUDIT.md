# STEP082B Code Audit

## Examined execution paths

### Product path

`okcanvas_agent_runtime.bootstrap.application.create_app` constructs `GenericAgentExecutionService`. Service/Admin transport routes use the Generic Runtime's catalog-bound Task/Run/Event/Artifact lifecycle.

### Legacy language path

`AgentRuntimeService` owns the fixed `coding-agent` envelope. It is language-only, uncataloged, and does not provide Product Tool/MCP/Session/Workspace authority. It remains for developer compatibility only.

### Codex paths

`CodexReadOnlyService`, `CodexWriteService`, and `CodexWriteApprovalService` have real read/write/approval behavior, but their `specs/agents/codex-*` and `specs/tools/codex*` directories do not contain Generic catalog `definition.json` files. They therefore remain development CLI runtimes, not Product Agents or Function Tools.

## Enforced Product boundary

`specs/runtime/product-execution-plane-policy.json` requires `GenericAgentExecutionService` and forbids Product bootstrap/transport references to the legacy and Codex service classes. `scripts/validate_step082b_execution_plane.py` verifies the imports, the policy, catalog sizes and Coding read/write/approval constraints.

Observed validator result before packaging:

```text
state PASSED
checks 13/13
Product control plane generic-agent-runtime
Agent definitions 27
Function Tool definitions 4
```

## Distribution startup experiment

An isolated wheel was built and installed. Application startup was then tested with different selected Product roots.

```text
full source root                              PASS
installed wheel only                         FAIL CLOSED: Product Session policy missing
installed wheel + specs                      FAIL CLOSED: pinned SDK Reference integrity mismatch
installed wheel + specs + reference          PASS
```

The successful composite startup imported Runtime code from the installed wheel, while loading Product configuration and immutable Reference sources from the composite Product root. This proves that importability and CLI `--help` are not equivalent to full Product startup.

## File and residue decision

STEP082A found no file whose deletion was proven safe. STEP082B therefore defines artifact ownership and packagers but performs no bulk deletion. Historical acceptance evidence, Reference sources and launchers are candidates for separate distribution artifacts, not unverified deletion.

## Architecture continuity

The physical architecture manifest remains a STEP081D relocation artifact. STEP082B updates hashes only for changed canonical Product modules and validates current Product identity separately. The route topology remains Admin 48, Service 33, Other 5, total HTTP 86, with no missing or duplicate routes. Source movement remains prohibited.

## Known deferred work

- migrate or explicitly retire the legacy language runtime after consumer inventory;
- expose Codex capabilities through the Generic catalog only after Product-owned approval/recovery contracts exist;
- physically publish the logical distribution artifacts in a release pipeline;
- implement Organization Assistant request/action routing in STEP083.

## Deterministic validation closure

```text
Architecture                         40/40 PASS
Execution-plane validator            13/13 PASS
Distribution startup validator       14/14 PASS
Integrated acceptance                12/12 PASS
Windows subprocess portability        9/9 PASS
Python regression                    231 files, 927/927 PASS
Node                                  14/14 PASS
Reference                              4/4 PASS
Direct Reference imports                 0
npm pack                               23 entries PASS
Installation                          16/16 PASS
Compliance                            15/15 PASS
Preliminary Fresh ZIP                 13/13 PASS
Fresh Python                          231 files, 927/927 PASS
```

The implementation exposed OR-ISSUE-057 through OR-ISSUE-062 during regression and Fresh validation. Each exact failure, root cause, correction and recurrence gate is retained in `docs/issues`.
