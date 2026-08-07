# ADR-004: Preserve the PlanVM Boundary

## Status
Accepted.

## Decision
The Agent runtime performs interpretation, planning, tool selection, observation, and replanning. PlanVM receives an already-constructed executable plan through a tool or MCP contract and handles deterministic execution concerns only.
