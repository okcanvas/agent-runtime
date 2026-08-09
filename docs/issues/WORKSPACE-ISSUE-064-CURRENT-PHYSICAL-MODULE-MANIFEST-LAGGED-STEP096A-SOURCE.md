# WORKSPACE-ISSUE-064 — Current physical module manifest lagged STEP096A source

## Status

FIXED_IN_STEP096A

## STEP

STEP096A / Workspace R11

## Observation

The architecture gate detected that the current STEP081 physical module manifest and RuntimeInfo expected field count still described the parent tree after STEP096A added canonical modules and capability fields.

## Correction / recurrence gate

Historical STEP081 source/relocation evidence remains immutable. Only the current physical module manifest is regenerated from canonical source, and the exact RuntimeInfo field count is updated. Run the STEP081 architecture gate after every Product module/RuntimeInfo surface change.
