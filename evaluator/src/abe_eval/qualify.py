"""CLI helpers for Antigravity environment qualification."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from abe_eval.antigravity import AntigravityWorkerHandle, qualify_environment, run_matrix
from abe_eval.bare_condition import MATRIX_TYPE, run_bare_pilot_matrix
from abe_eval.canonical import canonical_bytes
from abe_eval.contracts import parse_contract
from abe_eval.paired_incumbent import MATRIX_TYPE as PAIRED_INCUMBENT_MATRIX_TYPE
from abe_eval.paired_incumbent import run_paired_incumbent_matrix
from abe_eval.skill_ablation import MATRIX_TYPE as SKILL_ABLATION_MATRIX_TYPE
from abe_eval.skill_ablation import run_skill_ablation_matrix


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


def command_run_matrix(
    *,
    matrix_path: Path,
    qualification_path: Path,
    condition: str | None = None,
    condition_pair: tuple[str, str] | None = None,
    raw_root: Path | None = None,
) -> object:
    matrix = load_json(matrix_path)
    qualification = load_json(qualification_path)
    if "environmentQualification" in qualification:
        qualification = qualification["environmentQualification"]  # type: ignore[assignment]
    if matrix.get("matrixType") == MATRIX_TYPE:
        if condition != "bare":
            raise ValueError("bare_condition.condition_mismatch")
        if raw_root is None:
            raise ValueError("bare_condition.raw_root_required")
        return run_bare_pilot_matrix(matrix, qualification, raw_root)
    if matrix.get("matrixType") == PAIRED_INCUMBENT_MATRIX_TYPE:
        if condition_pair != ("bare", "superpowers"):
            raise ValueError("paired_incumbent.condition_pair_mismatch")
        if raw_root is None:
            raise ValueError("paired_incumbent.raw_root_required")
        return run_paired_incumbent_matrix(matrix, qualification, raw_root)
    if matrix.get("matrixType") == SKILL_ABLATION_MATRIX_TYPE:
        if raw_root is None:
            raise ValueError("skill_ablation.raw_root_required")
        return run_skill_ablation_matrix(
            matrix,
            qualification,
            raw_root,
            condition=condition,
            condition_pair=condition_pair,
        )
    return run_matrix(matrix, qualification)


__all__ = ["command_qualify", "command_run_matrix", "load_json", "write_json"]
