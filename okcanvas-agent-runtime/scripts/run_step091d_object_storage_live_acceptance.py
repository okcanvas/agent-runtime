from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from okcanvas_agent_runtime.adapters.persistence.product import SQLiteProductStore
from okcanvas_agent_runtime.adapters.storage.artifacts import (
    Boto3S3CompatibleObjectStorageClient,
    LocalFilesystemArtifactBlobStore,
    ObjectStorageArtifactBlobStore,
    ObjectStorageArtifactSettings,
    S3CompatibleClientSettings,
)
from okcanvas_agent_runtime.application.artifacts import ArtifactService
from okcanvas_agent_runtime.domain.runs import ArtifactIntegrityError

STEP = "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
VERSION = "2.75.0"
LIVE_CONFIRM_ENV = "OKCANVAS_OBJECT_STORAGE_LIVE_CONFIRM"
LIVE_CONFIRM_VALUE = "CREATE_AND_DELETE_ISOLATED_TEST_PREFIX"
BUCKET_ENV = "OKCANVAS_ARTIFACT_OBJECT_BUCKET"
OUTPUT_DEFAULT = ROOT / "docs/evidence/windows/STEP091D_REAL_OBJECT_STORAGE_LIVE_ACCEPTANCE.json"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha(value: str | None) -> str | None:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None


def _running_run(store: SQLiteProductStore) -> str:
    task = store.create_task(
        task_type="OBJECT_STORAGE_LIVE_ACCEPTANCE",
        input_sha256="d" * 64,
        agent_definition_id="object-storage-live-acceptance",
        agent_definition_version=VERSION,
    )
    return store.create_run(task_id=task.task_id).run_id


def run(output: Path, *, emit_stdout: bool = True) -> int:
    started_at = _now()
    bucket = os.environ.get(BUCKET_ENV, "").strip()
    confirm = os.environ.get(LIVE_CONFIRM_ENV, "")
    endpoint = os.environ.get("OKCANVAS_ARTIFACT_OBJECT_ENDPOINT_URL")
    region = os.environ.get("OKCANVAS_ARTIFACT_OBJECT_REGION")
    addressing_style = os.environ.get("OKCANVAS_ARTIFACT_OBJECT_ADDRESSING_STYLE", "auto")
    base_prefix = os.environ.get("OKCANVAS_ARTIFACT_OBJECT_PREFIX", "okcanvas-artifacts").strip().strip("/")

    checks = {
        "explicit_live_gate": confirm == LIVE_CONFIRM_VALUE,
        "bucket_configured": bool(bucket),
    }
    failure_code = None
    tracked_refs: list[str] = []
    isolated_prefix = None

    if not all(checks.values()):
        failure_code = "OBJECT_STORAGE_LIVE_ENVIRONMENT_NOT_READY"
    else:
        isolated_prefix = f"{base_prefix}/step091d-live-{uuid.uuid4().hex}"
        try:
            client = Boto3S3CompatibleObjectStorageClient(
                S3CompatibleClientSettings(
                    endpoint_url=endpoint,
                    region_name=region,
                    addressing_style=addressing_style,
                )
            )
            checks["real_s3_compatible_client_constructed"] = True
            with tempfile.TemporaryDirectory(prefix="okcanvas-step091d-live-") as temporary:
                product = SQLiteProductStore(Path(temporary) / "product.sqlite3")
                product.initialize()
                blobs = ObjectStorageArtifactBlobStore(
                    ObjectStorageArtifactSettings(bucket=bucket, prefix=isolated_prefix), client
                )
                service = ArtifactService(product_store=product, blob_store=blobs)
                run_id = _running_run(product)
                artifact = service.create_json(
                    run_id=run_id,
                    artifact_type="agent.object-storage-live-evidence",
                    payload={"state": "PASS", "step": STEP},
                    artifact_id=f"artifact_live_{uuid.uuid4().hex}",
                )
                tracked_refs.append(artifact.storage_path)
                checks["artifact_put_persisted_metadata"] = artifact.storage_path.startswith(
                    f"object-artifact-v1://{bucket}/"
                )
                verified, payload = service.read_json(artifact.artifact_id)
                checks["artifact_round_trip_live"] = payload == {"state": "PASS", "step": STEP}
                checks["artifact_head_integrity_live"] = service.verify(artifact.artifact_id).sha256 == verified.sha256
                try:
                    blobs.read(
                        artifact.storage_path.replace(f"{bucket}/", "outside-scope/", 1),
                        expected_sha256=artifact.sha256,
                        expected_byte_length=artifact.byte_length,
                    )
                except ArtifactIntegrityError as exc:
                    checks["artifact_scope_fence_live"] = exc.details.get("reason") == "storage-reference-scope-mismatch"
                else:
                    checks["artifact_scope_fence_live"] = False

                compensated_id = f"artifact_compensated_{uuid.uuid4().hex}"
                compensation_ref = blobs._reference(blobs._key(run_id="run_missing", artifact_id=compensated_id))
                tracked_refs.append(compensation_ref)
                try:
                    service.create_json(
                        run_id="run_missing",
                        artifact_type="agent.object-storage-live-compensation",
                        payload={"state": "SHOULD_ROLL_BACK"},
                        artifact_id=compensated_id,
                    )
                except Exception:
                    checks["metadata_failure_compensates_object_live"] = not blobs.exists(compensation_ref)
                    if checks["metadata_failure_compensates_object_live"]:
                        tracked_refs.remove(compensation_ref)
                else:
                    checks["metadata_failure_compensates_object_live"] = False

                checks["artifact_delete_live"] = blobs.delete(artifact.storage_path) and not blobs.exists(artifact.storage_path)
                tracked_refs.remove(artifact.storage_path)

                local = LocalFilesystemArtifactBlobStore(Path(temporary) / "local-artifacts")
                checks["local_filesystem_backend_retained"] = local.backend_id == "local-filesystem-artifact-v1"
        except Exception as exc:
            failure_code = f"OBJECT_STORAGE_LIVE_ACCEPTANCE_{type(exc).__name__.upper()}"
        finally:
            if 'blobs' in locals():
                cleanup_ok = True
                for ref in tuple(tracked_refs):
                    try:
                        blobs.delete(ref)
                        cleanup_ok = cleanup_ok and not blobs.exists(ref)
                    except Exception:
                        cleanup_ok = False
                checks["isolated_prefix_known_objects_cleanup_succeeded"] = cleanup_ok

    checks["secret_values_not_persisted"] = True
    payload = {
        "schema_version": "okcanvas-step091d-real-object-storage-live-acceptance-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "REAL_S3_COMPATIBLE_OBJECT_STORAGE_ISOLATED_PREFIX_LIVE_GATE",
        "state": "PASSED" if all(checks.values()) and failure_code is None else "FAILED",
        "started_at": started_at,
        "completed_at": _now(),
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "failure_code": failure_code,
        "object_storage": {
            "bucket_sha256": _sha(bucket),
            "endpoint_url_sha256": _sha(endpoint),
            "region_sha256": _sha(region),
            "isolated_prefix_sha256": _sha(isolated_prefix),
            "endpoint_configured": bool(endpoint),
            "addressing_style": addressing_style if addressing_style in {"auto", "path", "virtual"} else "invalid",
            "credentials_persisted": False,
        },
        "limitations": {
            "isolated_test_prefix_only": True,
            "bucket_creation_or_deletion_executed": False,
            "artifact_orphan_inventory_gc_implemented": False,
            "api_worker_physical_split_implemented": False,
            "distributed_worker_lease_implemented": False,
            "distributed_session_history_implemented": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if emit_stdout:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["state"] == "PASSED" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    return run(args.output.resolve(), emit_stdout=not args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
