"""Anchored condition- and model-blind reviewer grading."""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from typing import Any, Mapping

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import ContractValidationError, parse_contract


_LEAKAGE_MARKERS = (
    "gemini-3.7-flash-high",
    "gemini-3.1-pro-high",
    "REFERENCE_SOLUTION:",
    "conditionDigest",
    "conditionId",
    "modelRequest",
)
_SEVERITY_RANK = {"none": 0, "minor": 1, "important": 2, "critical": 3}


def _fail(reason_code: str, path: str = "$") -> None:
    raise ContractValidationError(reason_code, path)


def _mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("rubric.invalid", path)
    return copy.deepcopy(value)


def _assert_no_leakage(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"conditionId", "conditionDigest", "modelRequest"}:
                _fail("rubric.blind_projection_leakage", path + "." + key)
            _assert_no_leakage(item, path + "." + str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_leakage(item, path + "[" + str(index) + "]")
    elif isinstance(value, str):
        for marker in _LEAKAGE_MARKERS:
            if marker in value:
                _fail("rubric.blind_projection_leakage", path)


def rubric_digest(rubric: Mapping[str, Any]) -> str:
    """Digest a rubric after removing its self-digest field."""

    value = _mapping(dict(rubric), "$rubric")
    value.pop("rubricDigest", None)
    return sha256_digest(canonical_bytes(value))


def _validate_rubric(rubric: Mapping[str, Any]) -> dict[str, Any]:
    value = _mapping(dict(rubric), "$rubric")
    if value.get("schemaVersion") != 1:
        _fail("rubric.invalid", "$.schemaVersion")
    if value.get("rubricDigest") != rubric_digest(value):
        _fail("rubric.digest_mismatch", "$.rubricDigest")
    if not isinstance(value.get("dimensions"), list) or not value["dimensions"]:
        _fail("rubric.invalid", "$.dimensions")
    return value


def _matching_worst_severity(dimension: Mapping[str, Any], findings: list[Mapping[str, Any]]) -> str:
    selectors = tuple(str(item) for item in dimension.get("selectors", []))
    worst = "none"
    for finding in findings:
        finding_id = str(finding.get("findingId", ""))
        severity = str(finding.get("severity", "none"))
        status = str(finding.get("status", "open"))
        if status != "open":
            continue
        if selectors and not any(selector in finding_id for selector in selectors):
            continue
        if _SEVERITY_RANK.get(severity, -1) > _SEVERITY_RANK[worst]:
            worst = severity
    return worst


def _overall(scores: Mapping[str, str]) -> str:
    if not scores:
        return "indeterminate"
    return str(min(Decimal(value) for value in scores.values()))


def grade_blind(projection: Mapping[str, Any], rubric: Mapping[str, Any]) -> dict[str, object]:
    """Apply an anchored rubric to a blind projection and return ReviewerGrade."""

    blind = _mapping(dict(projection), "$projection")
    _assert_no_leakage(blind)
    frozen = _validate_rubric(rubric)
    findings = blind.get("findings", [])
    if not isinstance(findings, list):
        _fail("rubric.invalid_projection", "$.findings")
    scores: dict[str, str] = {}
    open_findings = [finding for finding in findings if isinstance(finding, dict) and finding.get("status") == "open"]
    for dimension in frozen["dimensions"]:
        if not isinstance(dimension, dict):
            _fail("rubric.invalid", "$.dimensions")
        dimension_id = str(dimension["dimensionId"])
        severity = _matching_worst_severity(dimension, open_findings)
        scores[dimension_id] = str(dimension["scoresByWorstSeverity"][severity])
    grade = {
        "schemaVersion": 1,
        "reviewerId": str(blind.get("reviewerId", "reviewer")),
        "rubricDigest": frozen["rubricDigest"],
        "calibrationDigest": frozen["calibrationDigest"],
        "dimensionScores": scores,
        "findingIds": sorted(str(finding["findingId"]) for finding in open_findings),
        "overall": _overall(scores),
        "limitations": [],
    }
    return parse_contract("ReviewerGrade", grade)


def adjudicate_reviewer_grades(grades: list[Mapping[str, Any]], rubric: Mapping[str, Any]) -> object:
    """Return frozen adjudication metadata for reviewer disagreement."""

    frozen = _validate_rubric(rubric)
    if len(grades) < int(frozen["adjudicationPolicy"]["requiredReviewers"]):
        _fail("rubric.invalid_grades", "$grades")
    parsed = [parse_contract("ReviewerGrade", grade) for grade in grades]
    values = [Decimal(str(grade["overall"])) for grade in parsed if grade["overall"] != "indeterminate"]
    if not values:
        return "not_required"
    overall_range = max(values) - min(values)
    threshold = Decimal(str(frozen["adjudicationPolicy"]["overallDifferenceThreshold"]))
    if overall_range <= threshold:
        return "not_required"
    return {
        "schemaVersion": 1,
        "decision": "adjudication_required",
        "reason": "reviewer_disagreement",
        "reviewerIds": ",".join(sorted(str(grade["reviewerId"]) for grade in parsed)),
        "overallRange": str(overall_range),
    }


__all__ = ["adjudicate_reviewer_grades", "grade_blind", "rubric_digest"]
