from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

IGNORE_SENTINELS = {
    "okcanvas-agent-runtime/.env.local": True,
    "okcanvas-agent-runtime/.env.local.example": False,
    "okcanvas-agent-runtime/.local/product.sqlite3": True,
    "okcanvas-agent-runtime/clients/cli/dist/api-client.js": False,
    "okcanvas-agent-runtime/docs/evidence/step091d-runtime-full-suite-partitions/partition-01.log": False,
    "okcanvas-agent-runtime/okcanvas_agent_runtime/application/artifacts/service.py": False,
    "okcanvas-agent-runtime/reference/upstream/openai-agents-python-0.19.0/.vscode/settings.json": False,
    "okcanvas-agent-runtime/artifacts/blob.bin": True,
    ".vscode/settings.json": True,
    "okcanvas-agent-cli/dist/index.js": True,
    "okcanvas-connectors/groupware-mcp-server/dist/pkg.js": True,
    "node_modules/x/index.js": True,
    "local-run.log": True,
}

ATTRIBUTE_SENTINELS = {
    "sh_run_workspace_step008_acceptance.cmd": {"text": "set", "eol": "lf"},
    "okcanvas-agent-runtime/sh_run_step086_acceptance.cmd": {"text": "set", "eol": "crlf"},
    "okcanvas-agent-runtime/sh_run_step086r2_acceptance.cmd": {"text": "set", "eol": "crlf"},
    "okcanvas-agent-runtime/sh_run_step088r1_acceptance.cmd": {"text": "set", "eol": "crlf"},
    "okcanvas-agent-runtime/sh_run_step090r1_acceptance.cmd": {"text": "set", "eol": "crlf"},
    "okcanvas-agent-runtime/okcanvas_agent_runtime/__init__.py": {"text": "set", "eol": "lf"},
    "docs/evidence/sample.json": {"text": "set", "eol": "lf"},
    "docs/evidence/sample.png": {"text": "unset"},
}


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False
    )


def _copy_policy_files(destination: Path) -> None:
    shutil.copy2(ROOT / ".gitignore", destination / ".gitignore")
    shutil.copy2(ROOT / ".gitattributes", destination / ".gitattributes")
    runtime = destination / "okcanvas-agent-runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "okcanvas-agent-runtime/.gitignore", runtime / ".gitignore")


def _touch_sentinels(destination: Path) -> None:
    for relative in sorted(set(IGNORE_SENTINELS) | set(ATTRIBUTE_SENTINELS)):
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".png":
            path.write_bytes(b"\x89PNG\r\n\x1a\n")
        else:
            path.write_text("sentinel\n", encoding="utf-8", newline="\n")


def _check_ignore(repo: Path, relative: str) -> tuple[bool, str]:
    # `git check-ignore -v` returns a matching negation rule as a successful
    # lookup even when that rule makes the path trackable. Use quiet mode for
    # the actual ignored/not-ignored decision and verbose mode only for provenance.
    decision = _run(repo, "git", "check-ignore", "--no-index", "-q", "--", relative)
    if decision.returncode not in (0, 1):
        raise RuntimeError(decision.stderr.strip() or f"git check-ignore failed for {relative}")
    provenance = _run(repo, "git", "check-ignore", "--no-index", "-v", "--", relative)
    if provenance.returncode not in (0, 1):
        raise RuntimeError(provenance.stderr.strip() or f"git check-ignore -v failed for {relative}")
    return decision.returncode == 0, provenance.stdout.strip()


def _check_attrs(repo: Path, relative: str) -> dict[str, str]:
    result = _run(repo, "git", "check-attr", "text", "eol", "--", relative)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git check-attr failed for {relative}")
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split(": ", 2)
        if len(parts) == 3:
            _, key, value = parts
            values[key] = value
    return values


def main() -> int:
    if shutil.which("git") is None:
        payload = {
            "schema_version": "okcanvas-git-repository-policy-validation-v1",
            "state": "FAILED",
            "errors": ["git executable not found"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    errors: list[str] = []
    observed_ignore: dict[str, dict[str, object]] = {}
    observed_attributes: dict[str, dict[str, str]] = {}

    with tempfile.TemporaryDirectory(prefix="okcanvas-git-policy-") as temp:
        repo = Path(temp)
        _copy_policy_files(repo)
        _touch_sentinels(repo)
        init = _run(repo, "git", "init", "-q")
        if init.returncode != 0:
            raise RuntimeError(init.stderr.strip() or "git init failed")

        for relative, expected_ignored in IGNORE_SENTINELS.items():
            actual_ignored, rule = _check_ignore(repo, relative)
            observed_ignore[relative] = {"ignored": actual_ignored, "rule": rule}
            if actual_ignored != expected_ignored:
                errors.append(
                    f"ignore mismatch for {relative}: expected {expected_ignored}, observed {actual_ignored}"
                )

        for relative, expected in ATTRIBUTE_SENTINELS.items():
            actual = _check_attrs(repo, relative)
            observed_attributes[relative] = actual
            for key, value in expected.items():
                if actual.get(key) != value:
                    errors.append(
                        f"attribute mismatch for {relative} {key}: expected {value}, observed {actual.get(key)}"
                    )

    payload = {
        "schema_version": "okcanvas-git-repository-policy-validation-v1",
        "state": "PASSED" if not errors else "FAILED",
        "checks": {
            "ignore_sentinels": len(IGNORE_SENTINELS),
            "attribute_sentinels": len(ATTRIBUTE_SENTINELS),
            "runtime_retained_cli_dist_trackable": not bool(
                observed_ignore.get("okcanvas-agent-runtime/clients/cli/dist/api-client.js", {}).get("ignored")
            ),
            "durable_evidence_log_trackable": not bool(
                observed_ignore.get(
                    "okcanvas-agent-runtime/docs/evidence/step091d-runtime-full-suite-partitions/partition-01.log",
                    {},
                ).get("ignored")
            ),
            "local_environment_ignored": bool(
                observed_ignore.get("okcanvas-agent-runtime/.env.local", {}).get("ignored")
            ),
            "environment_example_trackable": not bool(
                observed_ignore.get("okcanvas-agent-runtime/.env.local.example", {}).get("ignored")
            ),
            "product_artifact_package_trackable": not bool(
                observed_ignore.get("okcanvas-agent-runtime/okcanvas_agent_runtime/application/artifacts/service.py", {}).get("ignored")
            ),
            "retained_upstream_vscode_trackable": not bool(
                observed_ignore.get("okcanvas-agent-runtime/reference/upstream/openai-agents-python-0.19.0/.vscode/settings.json", {}).get("ignored")
            ),
            "runtime_root_artifacts_ignored": bool(
                observed_ignore.get("okcanvas-agent-runtime/artifacts/blob.bin", {}).get("ignored")
            ),
            "workspace_root_vscode_ignored": bool(
                observed_ignore.get(".vscode/settings.json", {}).get("ignored")
            ),
        },
        "observed_ignore": observed_ignore,
        "observed_attributes": observed_attributes,
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
