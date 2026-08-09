# WORKSPACE-ISSUE-071 — Current Runtime README retained STEP096A narrative under STEP096B identity

Status: FIXED_IN_R12R1
STEP: STEP096BR1 / Workspace R12R1

## Observed

The current-document identity markers in `okcanvas-agent-runtime/README.md` already pointed at
Workspace R12 / Runtime STEP096B, but the body still said that STEP096A was the current candidate and
that STEP096B was the next implementation step.

## Why it matters

ZIP-only continuation can pass marker-only identity checks while still presenting stale operational
instructions in the document body. A later conversation could therefore implement an already-completed
STEP or misunderstand which Live gate is pending.

## Fix

R12R1 rewrites the current Runtime README/HANDOFF/PLANS and Productization Master Plan narrative so the
current Product is STEP096B/2.80.0 and the pending gate is STEP096BR1 focused Windows/OpenAI Live.

## Recurrence gate

Current-document validation remains necessary but not sufficient. Successor Workspace static validation
must additionally require the current Runtime README/HANDOFF/PLANS to name the pending BR1 Live gate and
must reject retained `STEP096B will ...` / `STEP096A ... current candidate` successor text.
