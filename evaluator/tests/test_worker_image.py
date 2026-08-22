from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import pytest

from abe_eval.contracts import canonical_contract_digest, parse_contract


IMAGE_TAG = os.environ.get("ABE_WORKER_IMAGE", "antigravity-behavior-worker:test")
PLATFORM = os.environ.get("ABE_WORKER_PLATFORM", "linux/amd64")
WORKER_UID = 10001
WORKER_GID = 10001
AGY_VERSION = os.environ.get("ABE_AUTHORIZED_CLI_VERSION", "1.1.17")

ROOT = Path(__file__).resolve().parents[2]
POLICY_ROOT = ROOT / "environments" / "controller"
MOUNT_POLICY = POLICY_ROOT / "mount-policy.json"
NETWORK_POLICY = POLICY_ROOT / "network-policy.json"
FIXTURE_PATH = ROOT / "tests" / "contract" / "fixtures" / "evaluation-contracts.json"

FORBIDDEN_INPUT_KEYS = {
    "attemptId",
    "conditionId",
    "conditionPairId",
    "blockId",
    "blockIndex",
    "conditionName",
    "conditionLabel",
    "hiddenScenarioLabel",
    "randomizationSeed",
    "randomizationProof",
    "scheduledAttempt",
    "controllerPath",
    "graderPath",
    "referenceSolutionPath",
}

FORBIDDEN_PATHS = [
    "/controller",
    "/var/run/docker.sock",
    "/root/.gemini",
    "/root/.config/gemini",
    "/root/.config/antigravity",
    "/home/abe/.gemini",
    "/home/abe/.config/gemini",
    "/home/abe/.config/antigravity",
    "/workspace/.gemini",
    "/workspace/hidden",
    "/workspace/competing-runs",
    "/workspace/input/scheduled-attempt.json",
    "/workspace/input/condition.json",
    "/workspace/input/block.json",
    "/workspace/input/randomization.json",
    "/workspace/input/hidden-label.txt",
    "/workspace/input/grader.md",
    "/workspace/input/reference-solution.md",
]


def _run(argv: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, **kwargs)


def _docker(argv: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return _run(["docker", *argv], **kwargs)


def _require_docker() -> None:
    if _run(["sh", "-c", "command -v docker"]).returncode != 0:
        pytest.skip("Docker is required for the worker image boundary test")
    if _docker(["ps"]).returncode != 0:
        pytest.skip("Docker daemon is not available for the worker image boundary test")


def _authorized_cli_path() -> Path:
    raw = os.environ.get("ABE_AUTHORIZED_CLI_PATH")
    if not raw:
        pytest.skip("Set ABE_AUTHORIZED_CLI_PATH to the approved Linux Antigravity CLI artifact")
    path = Path(raw).resolve()
    if not path.is_file():
        pytest.skip(f"Approved CLI artifact is missing: {path}")
    return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _image_digest() -> str:
    inspected = _docker(["image", "inspect", IMAGE_TAG, "--format", "{{.Id}}"])
    assert inspected.returncode == 0, (
        "Build the disposable worker image first with: "
        "docker buildx build --tag antigravity-behavior-worker:test --load environments/worker\n"
        + inspected.stderr
    )
    return inspected.stdout.strip()


def _case_value(name: str) -> dict[str, object]:
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["validCases"]
    return next(json.loads(json.dumps(case["value"])) for case in cases if case["name"] == name)


def _digest(char: str) -> str:
    return "sha256:" + char * 64


def _environment_qualification(cli_digest: str, image_digest: str) -> tuple[dict[str, object], str]:
    qualification = _case_value("EnvironmentQualificationRecord")
    qualification["qualificationId"] = "env-qual-worker-image-001"
    qualification["scope"] = "cli_core"
    qualification["cliVersion"] = AGY_VERSION
    qualification["cliDigest"] = cli_digest
    qualification["imageDigest"] = image_digest
    qualification["platform"] = {"schemaVersion": 1, "os": "linux", "architecture": "x64"}
    qualification["pluginLifecycleEvidence"] = "not_applicable"
    qualification["customizationConformanceEvidence"] = "not_applicable"
    qualification["supportDecision"] = "qualified"
    qualification["limitations"] = ["T012 validates the worker boundary; live model qualification is T013."]
    qualification["qualifiedAt"] = "2026-08-22T00:00:00Z"
    parsed = parse_contract("EnvironmentQualificationRecord", qualification)
    return parsed, canonical_contract_digest("EnvironmentQualificationRecord", parsed)


def _worker_invocation(cli_digest: str, qualification_digest: str) -> dict[str, object]:
    invocation = _case_value("WorkerInvocation")
    invocation["invocationId"] = "worker-invocation-t012"
    invocation["runId"] = "run-t012-visible-only"
    invocation["requestDigest"] = _digest("a")
    invocation["fixtureDigest"] = _digest("b")
    invocation["authorityManifestDigest"] = _digest("c")
    invocation["toolPermissionProjection"] = {
        "schemaVersion": 1,
        "allowedTools": ["shell-readonly"],
        "network": "deny_except_inference",
    }
    invocation["cliDigest"] = cli_digest
    invocation["environmentQualificationDigest"] = qualification_digest
    return parse_contract("WorkerInvocation", invocation)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _prepare_worker_case(tmp_path: Path, case_name: str, cli_digest: str, image_digest: str) -> dict[str, Path | str]:
    case_root = tmp_path / case_name
    input_root = case_root / "input"
    repo_root = case_root / "repo"
    profile_root = case_root / "profile"
    output_root = case_root / "output"
    controller_root = case_root / "controller-hidden"
    for directory in (input_root, repo_root, profile_root, output_root, controller_root):
        directory.mkdir(parents=True)

    qualification, qualification_digest = _environment_qualification(cli_digest, image_digest)
    invocation = _worker_invocation(cli_digest, qualification_digest)
    lock = {
        "schemaVersion": 1,
        "environmentQualification": qualification,
        "environmentQualificationDigest": qualification_digest,
        "expectedRuntime": {
            "uid": WORKER_UID,
            "gid": WORKER_GID,
            "platform": "linux/x64",
            "cliPath": "/opt/antigravity/bin/agy",
            "cliDigest": cli_digest,
            "cliVersion": AGY_VERSION,
            "imageDigest": image_digest,
            "noNewPrivileges": True,
            "capabilities": "none",
        },
        "forbiddenInputKeys": sorted(FORBIDDEN_INPUT_KEYS),
        "forbiddenPaths": FORBIDDEN_PATHS,
        "requiredReadOnlyPaths": [
            "/workspace/input/worker-invocation.json",
            "/workspace/input/qualification-lock.json",
            "/workspace/input/request.txt",
            "/opt/antigravity/bin/agy",
        ],
        "requiredWritableRoots": [
            "/workspace/output",
            "/workspace/profile",
            "/workspace/repo",
            "/tmp",
        ],
    }
    _write_json(input_root / "qualification-lock.json", lock)
    _write_json(input_root / "worker-invocation.json", invocation)
    (input_root / "request.txt").write_text(f"visible request for {case_name}\n", encoding="utf-8")
    (repo_root / f"{case_name}-visible-canary.txt").write_text(case_name + "\n", encoding="utf-8")
    (controller_root / f"{case_name}-hidden-canary.txt").write_text(
        f"controller-only hidden canary for {case_name}\n", encoding="utf-8"
    )
    return {
        "input": input_root,
        "repo": repo_root,
        "profile": profile_root,
        "output": output_root,
        "controller": controller_root,
        "qualificationDigest": qualification_digest,
    }


def _worker_run_options(case: dict[str, Path | str], cli_path: Path, image_digest: str) -> list[str]:
    return [
        "run",
        "--rm",
        "--platform",
        PLATFORM,
        "--init",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=64m",
        "--env",
        "HOME=/workspace/profile",
        "--env",
        "XDG_CONFIG_HOME=/workspace/profile/.config",
        "--env",
        "XDG_CACHE_HOME=/workspace/profile/.cache",
        "--env",
        "ABE_WORKER_IMAGE_DIGEST=" + image_digest,
        "--mount",
        f"type=bind,source={case['input']},target=/workspace/input,readonly",
        "--mount",
        f"type=bind,source={case['repo']},target=/workspace/repo",
        "--mount",
        f"type=bind,source={case['profile']},target=/workspace/profile",
        "--mount",
        f"type=bind,source={case['output']},target=/workspace/output",
        "--mount",
        f"type=bind,source={cli_path},target=/opt/antigravity/bin/agy,readonly",
    ]


def _worker_run_args(case: dict[str, Path | str], cli_path: Path, image_digest: str) -> list[str]:
    return [
        *_worker_run_options(case, cli_path, image_digest),
        IMAGE_TAG,
    ]


def _run_worker(case: dict[str, Path | str], cli_path: Path, image_digest: str) -> dict[str, object]:
    result = _docker(
        [
            *_worker_run_args(case, cli_path, image_digest),
            "--invocation",
            "/workspace/input/worker-invocation.json",
        ],
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    output = Path(case["output"])
    return json.loads((output / "worker-result.json").read_text(encoding="utf-8"))


def test_worker_image_is_disposable_and_receives_only_visible_projection():
    _require_docker()
    cli_path = _authorized_cli_path()
    cli_digest = _sha256_file(cli_path)
    image_digest = _image_digest()
    tmp_path = Path(tempfile.mkdtemp(prefix=".worker-image-", dir=ROOT))

    try:
        mount_policy = json.loads(MOUNT_POLICY.read_text(encoding="utf-8"))
        network_policy = json.loads(NETWORK_POLICY.read_text(encoding="utf-8"))
        assert mount_policy["authorizedCli"]["containerPath"] == "/opt/antigravity/bin/agy"
        assert mount_policy["authorizedCli"]["readOnly"] is True
        assert mount_policy["authorizedCli"]["bakedIntoImage"] is False
        assert mount_policy["workerUser"] == {"uid": WORKER_UID, "gid": WORKER_GID, "name": "abe"}
        assert network_policy["behaviorRuns"]["packageManagerNetwork"] == "deny"
        assert network_policy["behaviorRuns"]["hostNetwork"] == "deny"

        bare_image = _docker(
            [
                "run",
                "--rm",
                "--platform",
                PLATFORM,
                "--entrypoint",
                "/bin/sh",
                IMAGE_TAG,
                "-c",
                'test "$(id -u)" = "10001" && test "$HOME" = "/workspace/profile" && test ! -e /opt/antigravity/bin/agy',
            ],
            timeout=20,
        )
        assert bare_image.returncode == 0, bare_image.stdout + bare_image.stderr

        first = _prepare_worker_case(tmp_path, "first", cli_digest, image_digest)
        second = _prepare_worker_case(tmp_path, "second", cli_digest, image_digest)

        direct_verify = _docker(
            [
                *_worker_run_options(first, cli_path, image_digest),
                "--entrypoint",
                "node",
                IMAGE_TAG,
                "/opt/abe/verify-image.mjs",
                "--expected",
                "/workspace/input/qualification-lock.json",
            ],
            timeout=45,
        )
        assert direct_verify.returncode == 0, direct_verify.stdout + direct_verify.stderr

        first_result = _run_worker(first, cli_path, image_digest)
        second_result = _run_worker(second, cli_path, image_digest)

        for result, case_name in ((first_result, "first"), (second_result, "second")):
            assert result["schemaVersion"] == 1
            assert result["runtime"]["uid"] == WORKER_UID
            assert result["runtime"]["gid"] == WORKER_GID
            assert result["runtime"]["home"] == "/workspace/profile"
            assert result["runtime"]["noNewPrivileges"] is True
            assert result["runtime"]["capEff"] == "0000000000000000"
            assert result["runtime"]["pid1Comm"] in {"docker-init", "init"}
            assert result["invocation"]["keys"] == [
                "authorityManifestDigest",
                "cliDigest",
                "cliPath",
                "environmentQualificationDigest",
                "fixtureDigest",
                "invocationId",
                "outputPath",
                "requestDigest",
                "requestPath",
                "resourceCaps",
                "runId",
                "schemaVersion",
                "toolPermissionProjection",
            ]
            assert result["invocation"]["forbiddenKeysPresent"] == []
            assert result["qualification"]["digestMatchesInvocation"] is True
            assert result["cli"] == {
                "path": "/opt/antigravity/bin/agy",
                "digest": cli_digest,
                "version": AGY_VERSION,
                "regularFile": True,
                "symlink": False,
                "writableByWorker": False,
            }
            assert result["paths"]["forbiddenVisible"] == []
            assert result["paths"]["readOnlyFailures"] == []
            assert result["paths"]["writableFailures"] == []
            assert case_name in result["visibleRequest"]
            assert case_name in result["repoCanaries"]

        first_text = json.dumps(first_result, sort_keys=True)
        second_text = json.dumps(second_result, sort_keys=True)
        assert "second-hidden-canary" not in first_text
        assert "first-hidden-canary" not in second_text
        assert "controller-only hidden canary" not in first_text + second_text

        npm_denied = _docker(
            [
                *_worker_run_options(first, cli_path, image_digest),
                "--entrypoint",
                "/usr/bin/timeout",
                IMAGE_TAG,
                "8",
                "npm",
                "view",
                "is-sorted",
                "version",
                "--fetch-timeout=1000",
                "--fetch-retries=0",
                "--registry=https://registry.npmjs.org",
            ],
            timeout=25,
        )
        assert npm_denied.returncode != 0

        history = _docker(["history", "--no-trunc", IMAGE_TAG], timeout=20)
        assert history.returncode == 0, history.stderr
        forbidden_history = [
            "agy-linux",
            str(cli_path),
            "_".join(("GITHUB", "TOKEN")),
            "_".join(("GOOGLE", "APPLICATION", "CREDENTIALS")),
            "_".join(("GEMINI", "API", "KEY")),
            "_".join(("ANTIGRAVITY", "AUTH")),
        ]
        assert not [needle for needle in forbidden_history if needle in history.stdout]

        container = _docker(["create", "--platform", PLATFORM, IMAGE_TAG], timeout=20)
        assert container.returncode == 0, container.stderr
        container_id = container.stdout.strip()
        export_path = tmp_path / "worker-fs.tar"
        try:
            with export_path.open("wb") as stream:
                exported = subprocess.run(["docker", "export", container_id], stdout=stream, stderr=subprocess.PIPE)
            assert exported.returncode == 0, exported.stderr.decode()
        finally:
            _docker(["rm", "-f", container_id])
        with tarfile.open(export_path) as archive:
            names = set(archive.getnames())
        assert "opt/antigravity/bin/agy" not in names
        assert not any(name.endswith("/.gemini") or "/.gemini/" in name for name in names)
        assert not any("credentials" in name.lower() or "credential" in name.lower() for name in names)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
