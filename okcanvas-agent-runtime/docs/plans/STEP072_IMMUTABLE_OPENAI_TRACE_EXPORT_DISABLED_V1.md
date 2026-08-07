# STEP072 — Immutable OpenAI trace export disabled V1

- version: `2.52.0`
- predecessor: STEP071 / 2.51.0 / Windows live accepted 28/28
- state: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_LIVE_RERUN_PENDING`

## Confirmed trigger

The user-reported STEP071 real Windows output ended with:

```text
[non-fatal] Tracing client error 400. Response data is redacted.
```

The Run itself had already succeeded. The pinned `openai-agents==0.19.0` source confirms that tracing
is enabled by default, `RunConfig.tracing_disabled` disables it per run, and its OpenAI trace exporter
prints this exact non-fatal 4xx diagnostic.

## Objective

Prevent the SDK from issuing an additional provider trace-export request while retaining all
Product-owned runtime evidence and local correlation identity.

## Contract

`specs/runtime/openai-trace-export-policy.json` is the only accepted policy:

```text
policy_id: local-openai-trace-export-disabled-v1
sdk_tracing_disabled: true
provider_trace_export_enabled: false
trace_include_sensitive_data: false
persist_local_trace_id: true
```

The policy file, catalog and runtime implementation are immutable Runtime-binding inputs. Drift after
preflight requires a new preflight and exact confirmation.

## Affected execution paths

Exactly seven Product-owned SDK `RunConfig` construction files are covered:

1. generic Agent execution;
2. bounded orchestration child execution;
3. legacy minimal Agent gateway;
4. Codex read-only;
5. Codex disposable write;
6. Codex approval prepare/resume;
7. governed Function Tool approval.

All continue to generate and persist Product-local `trace_id`. SDK span creation/export is disabled.

## Explicit non-goals

- no removal of Product Run Events, Artifacts, usage or local trace IDs;
- no OpenTelemetry exporter;
- no custom trace backend;
- no final service-client implementation;
- no Skill package mutation;
- no change to model routing, retry, reasoning, response-storage or provider-ID policies.

## Deterministic acceptance

```cmd
sh_run_step072_acceptance.cmd
```

It performs policy, mutation rejection, Runtime binding, all-RunConfig inventory, focused gateway,
historical Skill, compile, Node and Reference checks with zero external/model calls.

## Windows live acceptance

```cmd
sh_run_step072_live_acceptance.cmd
```

The wrapper invokes the existing STEP071 real provider workflow in a child process, captures stdout
and stderr through process shutdown and requires:

- STEP071 child 28/28 PASS;
- exactly one model call and positive token usage;
- terminal Run `SUCCEEDED`;
- no tracing client/server/request/retry diagnostic;
- API Key and raw attachment not persisted;
- acceptance workspace cleanup `COMPLETED`.
