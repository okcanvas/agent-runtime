from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import site
import subprocess
import sys
import tempfile
import textwrap
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = ROOT / "docs/evidence/STEP082B_INSTALLATION_VALIDATION.json"
EXPECTED_PACKAGES = (
    "okcanvas_agent_runtime",
    "okcanvas_agent_protocols",
    "okcanvas_agent_clients",
)
REQUIRED_RESOURCES = (
    "okcanvas_agent_runtime/core/governance/resources/architecture_constitution.json",
    "okcanvas_agent_runtime/core/governance/resources/constitution_gate_catalog.json",
    "okcanvas_agent_clients/dev_console/assets/index.html",
    "okcanvas_agent_clients/dev_console/assets/console.css",
    "okcanvas_agent_clients/dev_console/assets/console.js",
    "okcanvas_agent_clients/dev_console/assets/persisted-sse.js",
    "okcanvas_agent_clients/dev_runner/assets/index.html",
    "okcanvas_agent_clients/dev_runner/assets/runner.css",
    "okcanvas_agent_clients/dev_runner/assets/runner.js",
    "okcanvas_agent_clients/dev_runner/assets/persisted-sse.js",
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> tuple[bool, str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return completed.returncode == 0, completed.stdout


def _package_files() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in EXPECTED_PACKAGES:
        package_root = ROOT / package
        for path in sorted(package_root.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            relative = path.relative_to(ROOT).as_posix()
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _backend_source() -> str:
    return textwrap.dedent(
        r'''
        from __future__ import annotations

        import base64
        import csv
        import hashlib
        import io
        import tomllib
        import zipfile
        from pathlib import Path

        def _config():
            root = Path.cwd()
            payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
            project = payload["project"]
            packages = tuple(payload["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"])
            return root, project, packages

        def _dist_name(name):
            return name.replace("-", "_").replace(".", "_")

        def _metadata(project):
            name = project["name"]
            version = project["version"]
            dist = _dist_name(name)
            info = f"{dist}-{version}.dist-info"
            requires = "".join(f"Requires-Dist: {item}\n" for item in project.get("dependencies", ()))
            entrypoints = "".join(
                f"{name} = {target}\n" for name, target in project.get("scripts", {}).items()
            )
            return info, {
                f"{info}/METADATA": (
                    "Metadata-Version: 2.1\n"
                    f"Name: {name}\n"
                    f"Version: {version}\n"
                    f"Requires-Python: {project.get('requires-python', '>=3.10')}\n"
                    f"{requires}\n"
                ).encode(),
                f"{info}/WHEEL": (
                    "Wheel-Version: 1.0\n"
                    "Generator: step081-test-only-hatchling-interface-shim\n"
                    "Root-Is-Purelib: true\n"
                    "Tag: py3-none-any\n"
                ).encode(),
                f"{info}/entry_points.txt": (
                    "[console_scripts]\n" + entrypoints
                ).encode(),
            }

        def _hash(data):
            encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
            return "sha256=" + encoded.decode("ascii")

        def _write_wheel(wheel_directory, *, editable):
            root, project, packages = _config()
            dist = _dist_name(project["name"])
            version = project["version"]
            filename = f"{dist}-{version}-py3-none-any.whl"
            destination = Path(wheel_directory) / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            files = []
            if editable:
                files.append((f"_{dist}_editable.pth", (str(root) + "\n").encode()))
            else:
                for package in packages:
                    for path in sorted((root / package).rglob("*")):
                        if (
                            not path.is_file()
                            or "__pycache__" in path.parts
                            or path.suffix == ".pyc"
                        ):
                            continue
                        files.append((path.relative_to(root).as_posix(), path.read_bytes()))
            info, metadata = _metadata(project)
            files.extend(metadata.items())
            rows = [(name, _hash(data), str(len(data))) for name, data in files]
            record = f"{info}/RECORD"
            rows.append((record, "", ""))
            buffer = io.StringIO(newline="")
            csv.writer(buffer, lineterminator="\n").writerows(rows)
            files.append((record, buffer.getvalue().encode()))
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, data in files:
                    item = zipfile.ZipInfo(name, (2026, 7, 31, 0, 0, 0))
                    item.compress_type = zipfile.ZIP_DEFLATED
                    item.external_attr = 0o644 << 16
                    archive.writestr(item, data)
            return filename

        def get_requires_for_build_wheel(config_settings=None):
            return []

        def get_requires_for_build_editable(config_settings=None):
            return []

        def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
            return _write_wheel(wheel_directory, editable=False)

        def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
            return _write_wheel(wheel_directory, editable=True)
        '''
    ).lstrip()


def _external_dependency_path() -> str:
    paths = [Path(item).resolve().as_posix() for item in site.getsitepackages() if Path(item).is_dir()]
    return os.pathsep.join(paths)


def validate(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    started_at = _utc_now()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    configured_backend = pyproject["build-system"]["build-backend"]
    configured_packages = tuple(
        pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    )
    project_name = pyproject["project"]["name"]
    project_version = pyproject["project"]["version"]
    expected_files = _package_files()
    external_hatchling_available = importlib.util.find_spec("hatchling") is not None

    with tempfile.TemporaryDirectory(prefix="step081-install-") as temporary:
        temp = Path(temporary)
        backend_root = temp / "backend"
        wheel_root = temp / "wheel"
        wheel_venv = temp / "wheel-venv"
        editable_venv = temp / "editable-venv"
        execution_root = temp / "execution"
        execution_root.mkdir(parents=True)
        wheel_root.mkdir(parents=True)

        backend_mode = "ACTUAL_HATCHLING"
        build_env = os.environ.copy()
        if not external_hatchling_available:
            backend_mode = "TEST_ONLY_HATCHLING_INTERFACE_SHIM"
            package = backend_root / "hatchling"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "build.py").write_text(_backend_source(), encoding="utf-8")
            build_env["PYTHONPATH"] = str(backend_root)

        wheel_build_ok, wheel_build_output = _run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "-w",
                str(wheel_root),
            ],
            cwd=ROOT,
            env=build_env,
        )
        wheels = sorted(wheel_root.glob("*.whl"))
        wheel_entries: list[str] = []
        wheel_payload_hashes: dict[str, str] = {}
        if wheel_build_ok and len(wheels) == 1:
            with ZipFile(wheels[0]) as archive:
                wheel_entries = sorted(archive.namelist())
                for name in wheel_entries:
                    if ".dist-info/" in name:
                        continue
                    wheel_payload_hashes[name] = hashlib.sha256(archive.read(name)).hexdigest()

        wheel_payload_exact = wheel_payload_hashes == expected_files
        required_resources_present = all(item in wheel_payload_hashes for item in REQUIRED_RESOURCES)
        forbidden_wheel_entries = [
            name
            for name in wheel_entries
            if name.startswith(("tests/", "docs/", "reference/", "scripts/", "clients/"))
            or "__pycache__/" in name
            or name.endswith(".pyc")
        ]

        venv_ok, venv_output = _run(
            [sys.executable, "-m", "venv", str(wheel_venv)], cwd=execution_root
        )
        wheel_python = wheel_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        wheel_entrypoint = wheel_venv / (
            "Scripts/okcanvas-agent-runtime.exe" if os.name == "nt" else "bin/okcanvas-agent-runtime"
        )
        dependency_path = _external_dependency_path()
        runtime_env = os.environ.copy()
        runtime_env["PYTHONPATH"] = dependency_path
        wheel_install_ok = False
        wheel_install_output = "wheel was not built"
        wheel_import_ok = False
        wheel_import_output = "wheel was not installed"
        wheel_entrypoint_ok = False
        wheel_entrypoint_output = "wheel was not installed"
        if venv_ok and len(wheels) == 1:
            wheel_install_ok, wheel_install_output = _run(
                [str(wheel_python), "-m", "pip", "install", "--no-deps", str(wheels[0])],
                cwd=execution_root,
            )
        if wheel_install_ok:
            wheel_import_ok, wheel_import_output = _run(
                [
                    str(wheel_python),
                    "-c",
                    (
                        "import json, okcanvas_agent_runtime, okcanvas_agent_protocols, "
                        "okcanvas_agent_clients; from importlib.resources import files; "
                        "print(json.dumps({'runtime': okcanvas_agent_runtime.__file__, "
                        "'protocols': okcanvas_agent_protocols.__file__, "
                        "'clients': okcanvas_agent_clients.__file__, "
                        "'console_asset': files('okcanvas_agent_clients.dev_console')"
                        ".joinpath('assets/index.html').is_file(), "
                        "'runner_asset': files('okcanvas_agent_clients.dev_runner')"
                        ".joinpath('assets/index.html').is_file()}))"
                    ),
                ],
                cwd=execution_root,
                env=runtime_env,
            )
            wheel_entrypoint_ok, wheel_entrypoint_output = _run(
                [str(wheel_entrypoint), "--help"],
                cwd=execution_root,
                env=runtime_env,
            )
            wheel_entrypoint_ok = wheel_entrypoint_ok and "usage: okcanvas-agent-runtime" in wheel_entrypoint_output

        editable_venv_ok, editable_venv_output = _run(
            [sys.executable, "-m", "venv", str(editable_venv)], cwd=execution_root
        )
        editable_python = editable_venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        editable_entrypoint = editable_venv / (
            "Scripts/okcanvas-agent-runtime.exe" if os.name == "nt" else "bin/okcanvas-agent-runtime"
        )
        editable_env = os.environ.copy()
        editable_env["PYTHONPATH"] = os.pathsep.join(
            item for item in (str(backend_root) if not external_hatchling_available else "", dependency_path) if item
        )
        editable_install_ok = False
        editable_install_output = "editable venv was not created"
        editable_import_ok = False
        editable_import_output = "editable install did not complete"
        editable_entrypoint_ok = False
        editable_entrypoint_output = "editable install did not complete"
        if editable_venv_ok:
            editable_install_ok, editable_install_output = _run(
                [
                    str(editable_python),
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    "--no-build-isolation",
                    "-e",
                    str(ROOT),
                ],
                cwd=execution_root,
                env=editable_env,
            )
        if editable_install_ok:
            editable_runtime_env = os.environ.copy()
            editable_runtime_env["PYTHONPATH"] = dependency_path
            editable_import_ok, editable_import_output = _run(
                [
                    str(editable_python),
                    "-c",
                    (
                        "import json, pathlib, okcanvas_agent_runtime, okcanvas_agent_protocols, "
                        "okcanvas_agent_clients; print(json.dumps({'runtime': "
                        "str(pathlib.Path(okcanvas_agent_runtime.__file__).resolve()), 'protocols': "
                        "str(pathlib.Path(okcanvas_agent_protocols.__file__).resolve()), 'clients': "
                        "str(pathlib.Path(okcanvas_agent_clients.__file__).resolve())}))"
                    ),
                ],
                cwd=execution_root,
                env=editable_runtime_env,
            )
            editable_entrypoint_ok, editable_entrypoint_output = _run(
                [str(editable_entrypoint), "--help"],
                cwd=execution_root,
                env=editable_runtime_env,
            )
            editable_entrypoint_ok = editable_entrypoint_ok and "usage: okcanvas-agent-runtime" in editable_entrypoint_output

        source_root = ROOT.resolve().as_posix()
        editable_import_payload: dict[str, Any] = {}
        wheel_import_payload: dict[str, Any] = {}
        if editable_import_ok:
            editable_import_payload = json.loads(editable_import_output.strip().splitlines()[-1])
        if wheel_import_ok:
            wheel_import_payload = json.loads(wheel_import_output.strip().splitlines()[-1])
        editable_paths_exact = editable_import_ok and editable_import_payload == {
            "runtime": f"{source_root}/okcanvas_agent_runtime/__init__.py",
            "protocols": f"{source_root}/okcanvas_agent_protocols/__init__.py",
            "clients": f"{source_root}/okcanvas_agent_clients/__init__.py",
        }
        wheel_paths_isolated = wheel_import_ok and all(
            source_root not in str(value)
            for key, value in wheel_import_payload.items()
            if key in {"runtime", "protocols", "clients"}
        )
        wheel_resources_runtime_visible = (
            wheel_import_ok
            and wheel_import_payload.get("console_asset") is True
            and wheel_import_payload.get("runner_asset") is True
        )

        checks = {
            "configured_backend_exact": configured_backend == "hatchling.build",
            "explicit_package_allowlist_exact": configured_packages == EXPECTED_PACKAGES,
            "wheel_build_completed": wheel_build_ok and len(wheels) == 1,
            "wheel_payload_exact": wheel_payload_exact,
            "wheel_required_resources_present": required_resources_present,
            "wheel_forbidden_entries_absent": not forbidden_wheel_entries,
            "wheel_fresh_venv_created": venv_ok,
            "wheel_install_completed": wheel_install_ok,
            "wheel_imports_isolated_from_source": wheel_paths_isolated,
            "wheel_resources_runtime_visible": wheel_resources_runtime_visible,
            "wheel_console_entrypoint_operational": wheel_entrypoint_ok,
            "editable_fresh_venv_created": editable_venv_ok,
            "editable_install_completed": editable_install_ok,
            "editable_imports_resolve_to_source": editable_paths_exact,
            "editable_console_entrypoint_operational": editable_entrypoint_ok,
            "test_backend_not_in_wheel": not any(name.startswith("hatchling/") for name in wheel_entries),
        }
        payload: dict[str, Any] = {
            "schema_version": "okcanvas-step082b-installation-validation-v1",
            "step": "STEP082B_CODING_EXECUTION_PLANE_AND_DISTRIBUTION_BOUNDARY_CONSOLIDATION",
            "version": project_version,
            "state": "PASSED" if all(checks.values()) else "FAILED",
            "started_at": started_at,
            "completed_at": _utc_now(),
            "checks": checks,
            "passed_checks": sum(value is True for value in checks.values()),
            "total_checks": len(checks),
            "configured_build_backend": configured_backend,
            "backend_mode": backend_mode,
            "external_hatchling_available": external_hatchling_available,
            "test_backend_product_packaged": False,
            "project_name": project_name,
            "configured_packages": list(configured_packages),
            "expected_package_file_count": len(expected_files),
            "wheel_payload_file_count": len(wheel_payload_hashes),
            "wheel_filename": wheels[0].name if len(wheels) == 1 else None,
            "wheel_sha256": hashlib.sha256(wheels[0].read_bytes()).hexdigest() if len(wheels) == 1 else None,
            "required_resources": list(REQUIRED_RESOURCES),
            "forbidden_wheel_entries": forbidden_wheel_entries,
            "wheel_payload_missing": sorted(set(expected_files) - set(wheel_payload_hashes)),
            "wheel_payload_extra": sorted(set(wheel_payload_hashes) - set(expected_files)),
            "wheel_payload_hash_mismatches": sorted(
                name
                for name in set(expected_files) & set(wheel_payload_hashes)
                if expected_files[name] != wheel_payload_hashes[name]
            ),
            "external_dependency_path_mode": "TEST_ONLY_EXISTING_VALIDATION_SITE_PACKAGES_VIA_PYTHONPATH",
            "outputs": {
                "wheel_build": wheel_build_output,
                "wheel_venv": venv_output,
                "wheel_install": wheel_install_output,
                "wheel_import": wheel_import_output,
                "wheel_entrypoint": wheel_entrypoint_output,
                "editable_venv": editable_venv_output,
                "editable_install": editable_install_output,
                "editable_import": editable_import_output,
                "editable_entrypoint": editable_entrypoint_output,
            },
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    payload = validate(args.output.resolve())
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
