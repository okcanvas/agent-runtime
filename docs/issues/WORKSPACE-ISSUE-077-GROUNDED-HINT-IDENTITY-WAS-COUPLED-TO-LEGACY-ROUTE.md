# WORKSPACE-ISSUE-077 — Grounded Hint Identity Was Coupled to Legacy Route

Status: FIXED_IN_R12R4_STEP096BR1R2

## Evidence

R12R3 Windows Live showed `interpretation.context.prepared` with all Organization hints `UNAVAILABLE` and zero specialist requests/MCP calls. Code audit found `RunSubmissionBoundaryService.preflight()` created `DelegatedMCPIdentity` only when the legacy route had already selected an MCP requiring delegated identity. Natural grounded turns classified by legacy route as `ANSWER` therefore entered the Root with no delegated identity.

## Correction

An explicit grounded structured-delegation Session marker plus an authenticated ownership transition now materializes protected delegated tenant/principal/role identity independently of legacy child selection. Existing selected MCPs continue normal access binding; Hint MCP and admitted child MCP bind later at their own boundaries. Runtime does not pre-bind every possible MCP.

## Recurrence rule

Grounded interpretation must never depend on legacy capability selection for authenticated principal identity, and this identity change must never be widened into blanket connector authorization.
