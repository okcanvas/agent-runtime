# STEP008R4R9A implementation failure log

## R9A-F1 — focused relation Live launcher used the wrong Python environment

- Observed on actual Windows after `sh_setup_workspace.cmd`.
- Symptom: import of `run_workspace_step008_live_acceptance.py` failed at `import uvicorn`.
- Root cause: the STEP093 relation launcher used `.workspace-venv` or system `py -3`; Workspace setup creates the Runtime `.venv`, not `.workspace-venv`.
- Correction: use `okcanvas-agent-runtime\.venv\Scripts\python.exe` and `workspace_python_bytecode_isolation.py`, matching the proven base Live launcher.
- Product Runtime source changes: 0.
- Acceptance status: focused relation Live must be re-run; do not treat this corrective package as Live accepted based on static validation.
- Durable issue: `WORKSPACE-ISSUE-047-STEP093-RELATION-LIVE-LAUNCHER-BYPASSED-RUNTIME-VENV.md`.
