# WORKSPACE-ISSUE-046 — Runtime package metadata drifted from executable baseline

Status: FIX_IMPLEMENTED_TEST_EXECUTION_DEFERRED_BY_USER

## Problem

The STEP092 package contained an executable Runtime baseline at 2.76.0 while `okcanvas-agent-runtime/pyproject.toml` still declared 2.75.0. Static current-document identity checks did not cover the Python package metadata file.

## Correction

STEP093 sets both the executable Runtime baseline and `pyproject.toml` to 2.77.0. `validate_step093_static_contract.py` verifies both independently.

## Rule

A Runtime Step is not identity-consistent unless executable baseline, package metadata, project catalog, current Workspace SOT and current documents all agree.
