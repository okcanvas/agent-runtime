# STEP086R1 — Groupware Sub-agent and external MCP boundary alignment

## Identity

- Step: `STEP086R1_GROUPWARE_SUBAGENT_AND_EXTERNAL_MCP_BOUNDARY_ALIGNMENT`
- Version: `2.66.1`
- Parent: STEP086 Windows deterministic accepted 14/14

## Purpose

Correct the STEP086 implementation claim without removing its accepted routing, delegated identity or V3 MCP client binding. Make the internal Sub-agent/external provider boundary executable and give the read Agent a contract that cannot represent write actions.

## Implemented scope

- Product-owned internal `groupware-read-agent` retained and runtime-bound.
- dedicated `GroupwareReadResult` registered and schema-bound.
- exact internal/external deployment boundary contract.
- exact external provider Tool/delegated-identity contract.
- three deterministic provider fixtures, explicitly not a server.
- future writes fixed to a separate Agent/MCP/credential design.
- RuntimeInfo full-vertical overclaim removed.
- OR-ISSUE-092 and OR-ISSUE-093 recurrence gates.

## Explicit non-scope

- no actual Groupware MCP server;
- no vendor Groupware REST/Graph/API adapter;
- no real endpoint or secret;
- no OAuth refresh;
- no external Tool call or network-live validation;
- no Groupware write Agent or Tool.
