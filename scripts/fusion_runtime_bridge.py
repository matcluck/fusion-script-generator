"""Submit a Fusion script to the local Codex Fusion Runner and collect JSON results."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path


HEARTBEAT_MAX_AGE_SECONDS = 8.0
SELF_HEAL_GRACE_SECONDS = 12.0
ATOMIC_WRITE_ATTEMPTS = 5
DEFAULT_TIMEOUT_SECONDS = 180.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2)
    last_error = None
    for attempt in range(ATOMIC_WRITE_ATTEMPTS):
        temporary = path.with_name(
            ".{}.{}.{}.tmp".format(
                path.name,
                os.getpid(),
                time.time_ns(),
            )
        )
        try:
            temporary.write_text(encoded, encoding="utf-8")
            os.replace(str(temporary), str(path))
            return
        except OSError as error:
            last_error = error
            try:
                temporary.unlink()
            except OSError:
                pass
            if attempt + 1 < ATOMIC_WRITE_ATTEMPTS:
                time.sleep(0.05 * (attempt + 1))
    raise last_error


def _configured_scripts_root() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    config_path = (
        Path(appdata)
        / "autodesk-fusion-script-generator"
        / "config.json"
    )
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    value = config.get("scripts_root")
    return Path(value).resolve() if isinstance(value, str) and value.strip() else None


def _scripts_root(value: str | None, script: str | None = None) -> Path:
    if value:
        return Path(value).resolve()
    configured = _configured_scripts_root()
    if configured:
        return configured
    if script:
        candidate = Path(script).resolve()
        if candidate.parent.name == candidate.stem:
            return candidate.parent.parent
    raise RuntimeError(
        "Fusion Scripts root is unknown; pass --scripts-root or save the skill preference"
    )


def _queue_paths(root: Path) -> dict[str, Path]:
    queue = root / ".codex_fusion_runner"
    return {
        "queue": queue,
        "requests": queue / "requests",
        "processing": queue / "processing",
        "results": queue / "results",
        "status": queue / "status.json",
        "runner": root / "codex_fusion_runner" / "codex_fusion_runner.py",
    }


def _runner_status(root: Path) -> dict:
    paths = _queue_paths(root)
    report = {
        "scripts_root": str(root),
        "installed": paths["runner"].is_file(),
        "active": False,
        "heartbeat_age_seconds": None,
    }
    try:
        status = json.loads(paths["status"].read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        report["message"] = "No runner heartbeat. Start Codex Fusion Runner in Fusion."
        return report

    report["runner_status"] = status
    heartbeat = status.get("heartbeat_at")
    if status.get("running") is True and isinstance(heartbeat, (int, float)):
        age = max(0.0, time.time() - float(heartbeat))
        report["heartbeat_age_seconds"] = age
        report["active"] = age <= HEARTBEAT_MAX_AGE_SECONDS
    if not report["active"]:
        report["message"] = "Runner heartbeat is stale. Start or restart the add-in in Fusion."
    return report


def _version_at_least(value: object, minimum: tuple[int, ...]) -> bool:
    try:
        parts = tuple(int(part) for part in str(value).split("."))
    except (TypeError, ValueError):
        return False
    padded = parts + (0,) * max(0, len(minimum) - len(parts))
    return padded[: len(minimum)] >= minimum


def _runner_status_with_self_heal(root: Path) -> dict:
    report = _runner_status(root)
    runner_status = report.get("runner_status") or {}
    can_self_heal = (
        report.get("installed") is True
        and runner_status.get("running") is True
        and _version_at_least(runner_status.get("runner_version"), (1, 3, 0))
    )
    if report["active"] or not can_self_heal:
        return report

    deadline = time.time() + SELF_HEAL_GRACE_SECONDS
    while time.time() < deadline:
        time.sleep(0.5)
        report = _runner_status(root)
        if report["active"]:
            report["self_healed"] = True
            return report
    report["message"] = (
        "Runner v1.3 self-heal did not restore its heartbeat. "
        "Restart the add-in in Fusion."
    )
    return report


def _validated_script(script_value: str, root: Path) -> Path:
    script = Path(script_value).resolve()
    try:
        script.relative_to(root)
    except ValueError as error:
        raise RuntimeError("Script is outside the configured Fusion Scripts root") from error
    if not script.is_file() or script.suffix.lower() != ".py":
        raise RuntimeError("Target must be an existing Python file")
    if script.parent.parent != root:
        raise RuntimeError("Target must be in a direct child folder of the Scripts root")
    if script.stem != script.parent.name:
        raise RuntimeError("Script folder and Python filename must match")
    manifest = script.with_suffix(".manifest")
    if not manifest.is_file():
        raise RuntimeError("Target has no matching Fusion manifest")
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    if (
        manifest_data.get("autodeskProduct") != "Fusion360"
        or manifest_data.get("type") != "script"
        or manifest_data.get("id") != script.stem
    ):
        raise RuntimeError("Target manifest does not match the Fusion script")
    return script


def _submit(script: Path, root: Path) -> tuple[str, Path]:
    request_id = str(uuid.uuid4())
    paths = _queue_paths(root)
    request_path = paths["requests"] / f"{request_id}.json"
    payload = {
        "request_id": request_id,
        "script": str(script),
        "script_sha256": _sha256(script),
        "submitted_at": time.time(),
    }
    _atomic_json(request_path, payload)
    return request_id, request_path


def _wait(root: Path, request_id: str, timeout: float) -> dict:
    paths = _queue_paths(root)
    result_path = paths["results"] / f"{request_id}.json"
    request_path = paths["requests"] / f"{request_id}.json"
    processing_path = paths["processing"] / f"{request_id}.json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if result_path.is_file():
            return json.loads(result_path.read_text(encoding="utf-8"))
        # Fusion runs the target on its Python main thread. A geometry-heavy
        # build can hold the GIL long enough to pause the watcher's heartbeat.
        # A processing file is authoritative proof that the runner accepted
        # the job, so wait for its result instead of treating a stale heartbeat
        # as runner death.
        if not processing_path.is_file() and not request_path.is_file():
            status = _runner_status_with_self_heal(root)
            if not status["active"]:
                raise RuntimeError(status["message"])
        time.sleep(0.25)
    raise TimeoutError(
        "Fusion did not finish request {} within {:.0f} seconds".format(
            request_id, timeout
        )
    )


def _emit(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Control the local Codex Fusion runtime-validation bridge."
    )
    parser.add_argument("--scripts-root", help="Configured Fusion Scripts directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Report runner installation and heartbeat")

    submit_parser = subparsers.add_parser("submit", help="Queue a script without waiting")
    submit_parser.add_argument("script")

    wait_parser = subparsers.add_parser("wait", help="Wait for an existing request")
    wait_parser.add_argument("request_id")
    wait_parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)

    run_parser = subparsers.add_parser("run", help="Queue a script and wait for its result")
    run_parser.add_argument("script")
    run_parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)

    args = parser.parse_args()
    try:
        script_arg = getattr(args, "script", None)
        root = _scripts_root(args.scripts_root, script_arg)

        if args.command == "status":
            report = _runner_status_with_self_heal(root)
            _emit(report)
            return 0 if report["active"] else 2

        if args.command == "submit":
            status = _runner_status_with_self_heal(root)
            if not status["active"]:
                raise RuntimeError(status["message"])
            script = _validated_script(args.script, root)
            request_id, request_path = _submit(script, root)
            _emit({"request_id": request_id, "request_path": str(request_path)})
            return 0

        if args.command == "wait":
            result = _wait(root, args.request_id, args.timeout)
            _emit(result)
            return 0 if result.get("status") == "success" else 1

        status = _runner_status_with_self_heal(root)
        if not status["active"]:
            raise RuntimeError(status["message"])
        script = _validated_script(args.script, root)
        request_id, _ = _submit(script, root)
        result = _wait(root, request_id, args.timeout)
        _emit(result)
        return 0 if result.get("status") == "success" else 1
    except BaseException as error:
        _emit(
            {
                "status": "bridge_error",
                "exception_type": type(error).__name__,
                "message": str(error),
            }
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
