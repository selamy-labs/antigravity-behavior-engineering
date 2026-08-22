"""Protected-to-public run redaction."""

from __future__ import annotations

from pathlib import Path

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract


_FIELD_DISPOSITIONS = {
    "agentDeclaredState": "kept",
    "artifactManifestDigest": "transformed",
    "attemptId": "withheld",
    "attemptQualification": "transformed",
    "classification": "kept",
    "conditionDigest": "withheld",
    "consumption": "kept",
    "environmentQualificationDigest": "transformed",
    "eventStreamDigest": "transformed",
    "infrastructureValidity": "kept",
    "inputPermissionState": "kept",
    "observedModel": "withheld",
    "processState": "kept",
    "rawEvidenceLocator": "withheld",
    "redactedEvidenceLocator": "transformed",
    "runId": "transformed",
    "scenarioDigest": "transformed",
    "schemaVersion": "kept",
    "transcriptDigest": "transformed",
}


def _digest_token(prefix: str, seed: object, value: object) -> str:
    digest = sha256_digest(canonical_bytes({"seed": seed, "value": value}))
    return prefix + "-" + digest.removeprefix("sha256:")[:16]


def _require_digest_list(value: object, reason: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.startswith("sha256:") for item in value):
        raise TypeError(reason)
    return sorted(value)


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_bytes(canonical_bytes(value) + b"\n")


def redact_run(record: dict[str, object], policy: dict[str, object]) -> dict[str, object]:
    """Write a separate publishable tree and return its protected RedactedRun."""

    run = parse_contract("RunRecord", record)
    if not isinstance(policy, dict):
        raise TypeError("redaction.invalid_policy")
    public_root_value = policy.get("publicRoot")
    scenario_family_id = policy.get("scenarioFamilyId")
    public_configuration_digest = policy.get("publicConfigurationDigest")
    policy_id = policy.get("policyId", "redaction-policy")
    if not isinstance(public_root_value, str) or not public_root_value:
        raise TypeError("redaction.invalid_public_root")
    if not isinstance(scenario_family_id, str) or not scenario_family_id:
        raise TypeError("redaction.invalid_scenario_family")
    if not isinstance(public_configuration_digest, str) or not public_configuration_digest.startswith("sha256:"):
        raise TypeError("redaction.invalid_public_configuration_digest")
    grade_digests = _require_digest_list(policy.get("gradeDigests", []), "redaction.invalid_grade_digests")
    source_run_digest = canonical_contract_digest("RunRecord", run)
    public_run_id = _digest_token("public-run", policy_id, run["runId"])
    protected_mapping_digest = sha256_digest(canonical_bytes({"publicRunId": public_run_id, "rawRunId": run["runId"]}))
    report = {
        "schemaVersion": 1,
        "publicRunId": public_run_id,
        "sourceRunDigest": source_run_digest,
        "protectedMappingDigest": protected_mapping_digest,
        "fieldDispositions": dict(sorted(_FIELD_DISPOSITIONS.items())),
        "retainedAuditDigests": {
            "artifactManifestDigest": run["artifactManifestDigest"],
            "eventStreamDigest": run["eventStreamDigest"],
            "transcriptDigest": run["transcriptDigest"],
        },
        "limitations": [],
    }
    report_digest = sha256_digest(canonical_bytes(report))
    manifest = {
        "schemaVersion": 1,
        "publicRunId": public_run_id,
        "sourceRunDigest": source_run_digest,
        "entries": [
            {
                "path": "reports/" + str(policy_id) + "/" + public_run_id + "-redaction-report.json",
                "digest": report_digest,
                "mediaType": "application/json",
                "redactionDisposition": "kept",
            },
        ],
    }
    manifest_digest = sha256_digest(canonical_bytes(manifest))
    redacted = parse_contract(
        "RedactedRun",
        {
            "schemaVersion": 1,
            "publicRunId": public_run_id,
            "publicConfigurationDigest": public_configuration_digest,
            "scenarioFamilyId": scenario_family_id,
            "processState": run["processState"],
            "classification": run["classification"],
            "consumption": run["consumption"],
            "artifactManifestDigest": manifest_digest,
            "gradeDigests": grade_digests,
            "redactionReportDigest": report_digest,
            "limitations": [],
        },
    )
    public_root = Path(public_root_value)
    public_run_dir = public_root / "runs" / public_run_id
    artifact_dir = public_run_dir / "artifacts"
    report_dir = public_root / "reports" / str(policy_id)
    artifact_dir.mkdir(parents=True, exist_ok=False)
    report_dir.mkdir(parents=True, exist_ok=False)
    _write_json(report_dir / (public_run_id + "-redaction-report.json"), report)
    _write_json(artifact_dir / "artifact-manifest.json", manifest)
    _write_json(public_run_dir / "run.json", redacted)
    for canary in policy.get("canaries", []):
        if not isinstance(canary, str):
            raise TypeError("redaction.invalid_canary")
        for path in public_root.rglob("*"):
            if path.is_file() and canary in path.read_text(encoding="utf-8"):
                raise ValueError("redaction.canary_leak")
    return redacted


__all__ = ["redact_run"]
