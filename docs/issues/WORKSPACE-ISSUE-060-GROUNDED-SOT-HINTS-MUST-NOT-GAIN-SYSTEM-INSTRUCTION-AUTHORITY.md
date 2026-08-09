# WORKSPACE-ISSUE-060 — Grounded Sot Hints Must Not Gain System Instruction Authority

## Status

FIXED_IN_STEP096A

## STEP

STEP096A

## Observation

Projected Organization SOT hints were initially appended to Root system instructions.

## Correction / recurrence gate

Turn-local `call_model_input_filter` user-role context; Root contract treats all hint text as untrusted data, never instructions.
