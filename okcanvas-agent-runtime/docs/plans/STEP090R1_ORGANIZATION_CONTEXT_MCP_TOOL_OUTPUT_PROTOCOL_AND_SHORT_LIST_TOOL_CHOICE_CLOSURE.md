# STEP090R1 — Organization Context MCP ToolOutput protocol and short-list Tool choice closure

## Scope

Correct the actual STEP008R2 Windows Live failures while retaining the existing Root Session Agent, stateless Child Agent, three read-only MCP Tools, and `skills=[]` on both agents.

## Implementation

1. Protocol-specific decoding for OpenAI Agents 0.19.0 MCP ToolOutput text dictionaries and lists.
2. Product-owned named Child Tool choice from admitted short-expression operation hints.
3. Fail-closed exactly-one Tool evidence normalization.
4. Bounded safe normalization failure categories.

## Explicit non-goals

No alias/helper Agent fallback, model retry, Tool retry, Tool re-execution, Tool addition, Skill addition, Entity guessing, or topology change.
