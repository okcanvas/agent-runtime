# STEP003B finding

The second Windows STEP003 run proved that all ten functional acceptance checks passed again, while
cleanup still ended as `PASSED_WITH_CLEANUP_WARNING` because Windows refused deletion of
`fixture-repo/src/inventory/__pycache__` after eight attempts.

Code inspection confirmed the asymmetry:

- the independent pytest validator sets `PYTHONDONTWRITEBYTECODE=1`;
- the Codex read-only and workspace-write subprocess environments did not set it;
- Codex reported direct Python execution in the workspace, which imported `inventory` and created the
  observed bytecode directory.

STEP003B adds `PYTHONDONTWRITEBYTECODE=1` to both Codex child environments. It does not broaden the
write scope, enable arbitrary shell, or connect an external repository.
