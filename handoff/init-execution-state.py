#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path


APPROVAL_SENTENCE = (
    "I approve the final reviewed 46-task set in "
    "specs/001-improve-antigravity-behavior/tasks.md and authorize jump-box "
    "Codex to begin T001 only under AGENTS.md and "
    "handoff/codex-execution-contract.md."
)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def task_state() -> dict[str, object]:
    return {
        "status": "not_started",
        "branch": None,
        "prUrl": None,
        "headCommit": None,
        "mergeCommit": None,
        "attemptCount": 0,
        "sameFailureCount": 0,
        "infrastructureRetryCount": 0,
        "reviewRepairCount": 0,
        "noProgressCount": 0,
        "lastEvidenceDigest": None,
        "blocker": None,
    }


def sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def approval_record_digest(record: object) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(record)).hexdigest()}"


def load_task_set_approval(path: Path, base_commit: str, task_set_digest: str) -> dict[str, object]:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"invalid task-set approval record: {error}") from error

    required = {
        "schemaVersion": 1,
        "gate": "task_set",
        "repositoryId": "antigravity-behavior-engineering",
        "baseBranch": "main",
        "baseCommit": base_commit,
        "taskSetDigest": task_set_digest,
        "decision": "approved",
        "ownerApprovalSentence": APPROVAL_SENTENCE,
    }
    for key, expected in required.items():
        if record.get(key) != expected:
            raise SystemExit(
                f"task-set approval record does not bind current {key}: "
                f"expected {expected!r}"
            )
    if not record.get("approver"):
        raise SystemExit("task-set approval record lacks approver")
    if not isinstance(record.get("signature"), dict) or not record["signature"]:
        raise SystemExit("task-set approval record lacks signature")
    if not record.get("approvedAt"):
        raise SystemExit("task-set approval record lacks approvedAt")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--task-set-approval-record", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()

    repo = args.repo.resolve()
    state_dir = args.state_dir.resolve()
    target = state_dir / "state.json"
    if target.exists():
        raise SystemExit(f"refusing to overwrite existing execution state: {target}")
    if git(repo, "status", "--short"):
        raise SystemExit("execution state initialization requires a clean checkout")

    base_commit = git(repo, "rev-parse", "HEAD")
    task_path = repo / "specs/001-improve-antigravity-behavior/tasks.md"
    task_digest = sha256_file(task_path)
    approval = load_task_set_approval(
        args.task_set_approval_record.resolve(), base_commit, task_digest
    )
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    payload = json.loads((repo / "handoff/execution-state.example.json").read_text())
    payload.update(
        {
            "runId": f"abe-{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}",
            "initializationStatus": "ready",
            "baseCommit": base_commit,
            "taskSetDigest": task_digest,
            "tasks": {f"T{number:03d}": task_state() for number in range(1, 47)},
            "lastUpdatedAt": now.isoformat().replace("+00:00", "Z"),
        }
    )
    payload["humanGates"]["taskSet"] = {
        "status": "approved",
        "recordDigest": approval_record_digest(approval),
        "approvedCommit": base_commit,
        "approvedTaskSetDigest": task_digest,
    }

    state_dir.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="state.json.", suffix=".tmp", dir=state_dir
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    print(target)


if __name__ == "__main__":
    main()
