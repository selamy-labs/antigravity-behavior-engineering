#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "specs/001-improve-antigravity-behavior/tasks.md"
TASK_RE = re.compile(r"^- \[ \] (T\d{3}) (.+)$", re.MULTILINE)
DEP_RE = re.compile(r"T\d{3}")
APPROVAL_SENTENCE = (
    "I approve the final reviewed 46-task set in "
    "specs/001-improve-antigravity-behavior/tasks.md and authorize Ralph to "
    "begin T001 only under AGENTS.md and handoff/ralph-execution-contract.md."
)


def fail(message: str) -> None:
    print(f"handoff validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate_json() -> None:
    for path in sorted(ROOT.rglob("*.json")):
        if ".git" in path.parts:
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            fail(f"invalid JSON {path.relative_to(ROOT)}: {error}")


def task_sections(text: str) -> list[tuple[str, str, str]]:
    matches = list(TASK_RE.finditer(text))
    sections: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1), match.group(2), text[match.end():end]))
    return sections


def validate_tasks() -> None:
    text = TASKS.read_text(encoding="utf-8")
    if "**Status**: Draft task set" not in text or "awaiting separate project-owner approval" not in text:
        fail("tasks.md must remain an unapproved draft at handoff finalization")
    if not re.search(r"did\s+not\s+approve\s+these\s+final\s+task\s+bytes\s+or\s+authorize\s+T001", text):
        fail("tasks.md must explicitly block T001 before task-set approval")
    sections = task_sections(text)
    expected = [f"T{number:03d}" for number in range(1, 47)]
    observed = [task_id for task_id, _, _ in sections]
    if observed != expected:
        fail(f"task IDs are not exactly T001..T046: {observed}")

    existing = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file()}
    created_by: dict[str, str] = {}

    for task_id, title, section in sections:
        if "**Files**:" not in section or "**Acceptance**:" not in section:
            fail(f"{task_id} lacks Files or Acceptance")
        steps = re.findall(r"^- \[ \] (?!T\d{3})", section, re.MULTILINE)
        if len(steps) != 5:
            fail(f"{task_id} has {len(steps)} execution steps, expected 5")

        dependency_line = re.search(r"^\*\*Depends on\*\*: (.+)$", section, re.MULTILINE)
        if dependency_line:
            for dependency in DEP_RE.findall(dependency_line.group(1)):
                if dependency not in expected:
                    fail(f"{task_id} names unknown dependency {dependency}")
                if int(dependency[1:]) >= int(task_id[1:]):
                    fail(f"{task_id} has non-earlier dependency {dependency}")

        file_ops = re.findall(
            r"^- (Create[^:]*|Generate[^:]*|Modify[^:]*|Test|Read protected): `([^`]+)`",
            section,
            re.MULTILINE,
        )
        if not file_ops:
            fail(f"{task_id} has no parseable file operations")
        if len(file_ops) > 10:
            fail(f"{task_id} touches {len(file_ops)} paths; split the PR")

        for operation, path in file_ops:
            if (operation.startswith("Create") or operation.startswith("Generate")) and "outside Git" not in operation:
                prior = created_by.get(path)
                if prior:
                    fail(f"{path} is created by both {prior} and {task_id}")
                created_by[path] = task_id
            if operation.startswith("Modify") and path not in created_by and path not in existing:
                fail(f"{task_id} modifies {path} before any creator or committed file")

        if not title.strip():
            fail(f"{task_id} has an empty title")

    fr_rows = re.findall(r"^\| FR-(\d{3}) \|", text, re.MULTILINE)
    sc_rows = re.findall(r"^\| SC-(\d{3}) \|", text, re.MULTILINE)
    if fr_rows != [f"{number:03d}" for number in range(1, 51)]:
        fail("functional-requirement trace rows are not exactly FR-001..FR-050")
    if sc_rows != [f"{number:03d}" for number in range(1, 14)]:
        fail("success-criterion trace rows are not exactly SC-001..SC-013")


def validate_public_boundary() -> None:
    forbidden_roots = ("plugin", "packages", "evaluator", "evals", "environments", "tests")
    present = [name for name in forbidden_roots if (ROOT / name).exists()]
    if present:
        fail(f"implementation roots exist before T001: {present}")

    text_paths = [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and ".git" not in path.parts and path.suffix not in {".png", ".jpg", ".jpeg", ".gif"}
    ]
    forbidden_patterns = {
        "absolute macOS user path": re.compile(r"(?<![A-Za-z0-9._-])/Users/[A-Za-z0-9._-]+/"),
        "absolute Linux home path": re.compile(r"(?<![A-Za-z0-9._-])/home/[A-Za-z0-9._-]+/"),
        "private key marker": re.compile("BEGIN " + r"[A-Z ]*PRIVATE KEY"),
    }
    for path in text_paths:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if re.search(r"\b(TODO|TBD|FIXME)\s*:", content):
            fail(f"unresolved placeholder in {path.relative_to(ROOT)}")
        for label, pattern in forbidden_patterns.items():
            if pattern.search(content):
                fail(f"{label} in {path.relative_to(ROOT)}")


def validate_approval_gate() -> None:
    stale_approval_patterns = (
        re.compile(r"\btask set (?:is|are) approved\b", re.IGNORECASE),
        re.compile(r"\bapproved 46-task\b", re.IGNORECASE),
        re.compile(r"\b46-task [^\n.]{0,80} approved\b", re.IGNORECASE),
        re.compile(r"\bapproved downstream `tasks\.md`\b", re.IGNORECASE),
        re.compile(r"\bimplementation-ready\b", re.IGNORECASE),
        re.compile(r"\bpublication-ready\b", re.IGNORECASE),
        re.compile(r"\bExecute exactly one approved task\b", re.IGNORECASE),
    )
    allowed_fragments = (
        "not approve these final task bytes",
        "not approved",
        "awaiting separate project-owner approval",
        "the specification and implementation-plan approvals are recorded",
    )
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.name == "validate_handoff.py":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if any(fragment in line for fragment in allowed_fragments):
                continue
            if any(pattern.search(line) for pattern in stale_approval_patterns):
                fail(f"stale task-set approval claim in {path.relative_to(ROOT)}:{line_number}")

    forbidden_records = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*approval*.json")
        if path.is_file()
        and ".git" not in path.parts
        and not path.name.endswith(".schema.json")
    ]
    if forbidden_records:
        fail(f"committed approval records are not allowed before human gates: {forbidden_records}")

    example = json.loads((ROOT / "handoff/ralph-state.example.json").read_text(encoding="utf-8"))
    task_gate = example.get("humanGates", {}).get("taskSet")
    if task_gate != {
        "status": "pending",
        "recordDigest": None,
        "approvedCommit": None,
        "approvedTaskSetDigest": None,
    }:
        fail("Ralph example state must keep task-set gate pending")

    init_script = (ROOT / "handoff/init-ralph-state.py").read_text(encoding="utf-8")
    if (
        "--task-set-approval-record" not in init_script
        or "final reviewed 46-task set" not in init_script
        or "authorize Ralph to" not in init_script
    ):
        fail("Ralph initializer must require the exact external task-set approval")


def main() -> None:
    validate_json()
    validate_tasks()
    validate_public_boundary()
    validate_approval_gate()
    print("structured task, JSON, and public-boundary checks passed")


if __name__ == "__main__":
    main()
