# ADR-001: Start with Python

## Status
Accepted for the first vertical slice.

## Decision
Use Python for the initial Agent runtime.

## Evidence
The supplied primary source is OpenAI Agents Python 0.19.0. Its inspected source includes Runner, RunState, sessions, MCP, sandbox, and experimental Codex integration. Equivalent JS source was not supplied and therefore is not assumed.

## Consequence
The future web console communicates by API. Java/Spring services remain business systems and PlanVM remains a separate deterministic executor.
