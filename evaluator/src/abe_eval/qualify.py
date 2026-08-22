"""CLI helpers for Antigravity environment qualification."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from abe_eval.antigravity import AntigravityWorkerHandle, qualify_environment, run_matrix
from abe_eval.canonical import canonical_bytes
from abe_eval.contracts import parse_contract


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("qualify.expected_json_object")
    return value


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def command_qualify(
    *,
    protocol_path: Path,
    scope: str,
    cli_artifact: Path,
    output_path: Path,
) -> dict[str, object]:
    protocol = parse_contract("QualificationProtocol", load_json(protocol_path))
    if protocol["customizationScope"] != scope:
        raise ValueError("qualify.scope_mismatch")
    output_path = output_path.resolve()
    output_root = (output_path.parent / (output_path.stem + "-artifacts")).resolve()
    request_path = output_root / "request.txt"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.write_text("Reply with exactly OK and no extra prose.\n", encoding="utf-8")
    auth_home = Path(os.environ.get("ABE_ANTIGRAVITY_AUTH_HOME", os.environ.get("HOME", str(output_root / "profile")))).resolve()
    result = qualify_environment(
        AntigravityWorkerHandle(
            cli_path=cli_artifact,
            request_path=request_path,
            output_root=output_root,
            cwd=output_root,
            env={
                "HOME": str(auth_home),
                "XDG_CACHE_HOME": str(output_root / "profile" / ".cache"),
            },
            timeout_seconds=45,
        ),
        protocol,
    )
    write_json(output_path, result.raw)
    return result.raw


def command_run_matrix(*, matrix_path: Path, qualification_path: Path) -> tuple[dict[str, object], ...]:
    matrix = load_json(matrix_path)
    qualification = load_json(qualification_path)
    if "environmentQualification" in qualification:
        qualification = qualification["environmentQualification"]  # type: ignore[assignment]
    return run_matrix(matrix, qualification)


__all__ = ["command_qualify", "command_run_matrix", "load_json", "write_json"]
