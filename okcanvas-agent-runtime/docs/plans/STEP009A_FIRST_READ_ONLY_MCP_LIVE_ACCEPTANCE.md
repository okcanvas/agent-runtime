# STEP009A — First read-only MCP live acceptance

## Objective

Convert the deterministic STEP009 implementation into a live-accepted capability using the installed MCP SDK, a real local stdio subprocess and a real OpenAI Agent model call.

## Evidence

- acceptance ID: `20260728T230639Z-75152cc6`;
- state: `PASSED`;
- all twelve live checks true;
- Agent total tokens: 2,785;
- two MCP Tools called;
- four canonical MCP Events recorded;
- all Reference trees unchanged.

## Acceptance boundary

Accepted: local read-only stdio MCP and real Agent Tool use.

Not accepted: write MCP, remote MCP, ERP/ESS/PlanVM, OpenAI Trace export, Handoffs, Sessions or UI.

## Reference policy

The inspected upstream implementation was used as design evidence only. Runtime imports installed dependencies and product-owned adapters, never files under `/reference`.
