"""Frozen task-family scenario materialization."""

from __future__ import annotations

import copy
from typing import Any, Literal, Mapping, TypeAlias

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract


Partition: TypeAlias = Literal["formative", "regression", "sealed"]
TaskFamilyProtocol: TypeAlias = Mapping[str, Any]
ScenarioCard: TypeAlias = dict[str, object]

PARTITIONS = frozenset({"formative", "regression", "sealed"})
_RAW_HIDDEN_FIELD_NAMES = frozenset(
    {
        "rawCanary",
        "canaryValue",
        "hiddenCanary",
        "referenceSolution",
        "graderInstruction",
        "sealedInstance",
        "sealedScenario",
        "postTreatmentGeneratorInput",
        "postTreatmentResult",
    }
)
_RAW_HIDDEN_TEXT_MARKERS = (
    "ABE_HIDDEN_",
    "RAW_CANARY_",
    "REFERENCE_SOLUTION:",
    "GRADER_INSTRUCTION:",
)
_VARIANT_RULES = {
    "schemaVersion": 1,
    "generatorInputs": ["familyId", "partition", "seedCommitment"],
    "postTreatmentInputsAllowed": False,
    "labelsEditableByTreatment": False,
    "equivalentConditionInputs": True,
}


def _fail(reason_code: str, path: str) -> None:
    raise ContractValidationError(reason_code, path)


def _require_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("scenario.invalid_protocol", path)
    return copy.deepcopy(value)


def _require_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("scenario.invalid_protocol", path)
    return value


def _seed_commitment(seed: str) -> str:
    try:
        return sha256_digest(seed.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ContractValidationError("scenario.invalid_seed", "$seed") from exc


def _assert_no_raw_hidden_material(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _RAW_HIDDEN_FIELD_NAMES:
                _fail("scenario.hidden_material_exposed", path + "." + key)
            _assert_no_raw_hidden_material(item, path + "." + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_raw_hidden_material(item, path + "[" + str(index) + "]")
    elif isinstance(value, str):
        if any(marker in value for marker in _RAW_HIDDEN_TEXT_MARKERS):
            _fail("scenario.hidden_material_exposed", path)


def _variant_record(protocol: Mapping[str, Any], seed: str, partition: str) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "familyId": _require_string(protocol.get("familyId"), "$.familyId"),
        "partition": partition,
        "seedCommitment": _seed_commitment(seed),
        "protocolDigest": sha256_digest(canonical_bytes(protocol)),
    }


def _variant_digest(protocol: Mapping[str, Any], seed: str, partition: str) -> str:
    return sha256_digest(canonical_bytes(_variant_record(protocol, seed, partition)))


def _variant_token(protocol: Mapping[str, Any], seed: str, partition: str) -> str:
    return _variant_digest(protocol, seed, partition)[7:19]


def _digest_template(
    *,
    family_id: str,
    partition: str,
    seed: str,
    variant_token: str,
    template_name: str,
    template: object,
) -> str:
    return sha256_digest(
        canonical_bytes(
            {
                "schemaVersion": 1,
                "familyId": family_id,
                "partition": partition,
                "seedCommitment": _seed_commitment(seed),
                "variantToken": variant_token,
                template_name: template,
            }
        )
    )


def _materialize_authority(protocol: Mapping[str, Any], family_id: str, variant_token: str) -> dict[str, object]:
    authority = _require_mapping(protocol.get("authorityManifestTemplate"), "$.authorityManifestTemplate")
    authority["schemaVersion"] = 1
    authority["manifestId"] = family_id + "-" + variant_token + "-authority"
    authority.setdefault("credentialGrantDigests", [])
    authority.setdefault("expiresAt", "not_applicable")
    return parse_contract("AuthorityManifest", authority)


def _materialize_resource(protocol: Mapping[str, Any], family_id: str, variant_token: str) -> dict[str, object]:
    resource = _require_mapping(protocol.get("resourceEnvelopeTemplate"), "$.resourceEnvelopeTemplate")
    resource["schemaVersion"] = 1
    resource["envelopeId"] = family_id + "-" + variant_token + "-resources"
    return parse_contract("ResourceEnvelope", resource)


def _materialize_checks(protocol: Mapping[str, Any], variant_token: str) -> list[dict[str, object]]:
    checks = protocol.get("checkTemplates")
    if not isinstance(checks, list) or not checks:
        _fail("scenario.invalid_protocol", "$.checkTemplates")
    materialized: list[dict[str, object]] = []
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            _fail("scenario.invalid_protocol", "$.checkTemplates[" + str(index) + "]")
        value = copy.deepcopy(check)
        value["schemaVersion"] = 1
        value["checkId"] = str(value["checkId"]) + "-" + variant_token
        materialized.append(parse_contract("CheckLock", value))
    return materialized


def _classification_policy_digest(protocol: Mapping[str, Any]) -> str:
    policy = _require_mapping(protocol.get("classificationPolicyTemplate"), "$.classificationPolicyTemplate")
    policy["schemaVersion"] = 1
    body = copy.deepcopy(policy)
    body.pop("policyDigest", None)
    policy["policyDigest"] = sha256_digest(canonical_bytes(body))
    return parse_contract("ClassificationPolicy", policy)["policyDigest"]


def _validate_protocol(protocol: Mapping[str, Any]) -> None:
    if protocol.get("schemaVersion") != 1:
        _fail("scenario.invalid_protocol", "$.schemaVersion")
    _require_string(protocol.get("familyId"), "$.familyId")
    if not isinstance(protocol.get("behaviors"), list) or not protocol["behaviors"]:
        _fail("scenario.invalid_protocol", "$.behaviors")
    if protocol.get("variantRules") != _VARIANT_RULES:
        _fail("scenario.invalid_protocol", "$.variantRules")
    if not isinstance(protocol.get("applicability"), dict) or not protocol["applicability"]:
        _fail("scenario.invalid_protocol", "$.applicability")
    if not isinstance(protocol.get("componentControls"), dict) or not protocol["componentControls"]:
        _fail("scenario.invalid_protocol", "$.componentControls")
    labels = _require_mapping(protocol.get("preTreatmentLabels"), "$.preTreatmentLabels")
    if labels.get("workflowTier") != protocol.get("workflowTier"):
        _fail("scenario.invalid_protocol", "$.preTreatmentLabels.workflowTier")
    if labels.get("applicability") != protocol.get("applicability"):
        _fail("scenario.invalid_protocol", "$.preTreatmentLabels.applicability")
    if not isinstance(protocol.get("weight"), int) or protocol["weight"] < 1:
        _fail("scenario.invalid_protocol", "$.weight")
    if not isinstance(protocol.get("exclusions"), list) or not protocol["exclusions"]:
        _fail("scenario.invalid_protocol", "$.exclusions")
    if not isinstance(protocol.get("materialAmbiguityLabels"), list):
        _fail("scenario.invalid_protocol", "$.materialAmbiguityLabels")
    commitments = protocol.get("hiddenCheckCommitments")
    if not isinstance(commitments, list) or not commitments:
        _fail("scenario.invalid_protocol", "$.hiddenCheckCommitments")
    _assert_no_raw_hidden_material(protocol)


def materialize_scenario(protocol: TaskFamilyProtocol, seed: str, partition: Partition) -> ScenarioCard:
    """Return a deterministic ScenarioCard from a frozen TaskFamily protocol.

    The generator consumes only the protocol, a caller-held seed, and the
    immutable partition. It does not read treatment output, hidden graders, or
    sealed instances from the public repository.
    """

    protocol_copy = _require_mapping(protocol, "$protocol")
    if partition not in PARTITIONS:
        _fail("scenario.invalid_partition", "$partition")
    if not isinstance(seed, str) or not seed:
        _fail("scenario.invalid_seed", "$seed")
    _validate_protocol(protocol_copy)

    family_id = _require_string(protocol_copy["familyId"], "$.familyId")
    variant_token = _variant_token(protocol_copy, seed, partition)
    scenario_id = partition + "-" + family_id + "-" + variant_token
    card = {
        "schemaVersion": 1,
        "scenarioId": scenario_id,
        "family": family_id,
        "partition": partition,
        "variantProtocolDigest": _variant_digest(protocol_copy, seed, partition),
        "fixtureDigest": _digest_template(
            family_id=family_id,
            partition=partition,
            seed=seed,
            variant_token=variant_token,
            template_name="fixtureTemplate",
            template=protocol_copy["fixtureTemplate"],
        ),
        "startingStateDigest": _digest_template(
            family_id=family_id,
            partition=partition,
            seed=seed,
            variant_token=variant_token,
            template_name="startingStateTemplate",
            template=protocol_copy["startingStateTemplate"],
        ),
        "agentInput": "protected/scenarios/" + partition + "/" + family_id + "/" + variant_token + "/agent-input.md",
        "applicability": copy.deepcopy(protocol_copy["applicability"]),
        "materialAmbiguities": copy.deepcopy(protocol_copy["materialAmbiguityLabels"]),
        "authorityManifest": _materialize_authority(protocol_copy, family_id, variant_token),
        "resourceEnvelope": _materialize_resource(protocol_copy, family_id, variant_token),
        "checks": _materialize_checks(protocol_copy, variant_token),
        "classificationPolicyDigest": _classification_policy_digest(protocol_copy),
        "weight": protocol_copy["weight"],
    }
    return parse_contract("ScenarioCard", card)


def public_scenario(card: Mapping[str, Any], protocol: TaskFamilyProtocol) -> dict[str, object]:
    """Return the public worker/reference projection for a materialized card."""

    parsed_card = parse_contract("ScenarioCard", dict(card))
    protocol_copy = _require_mapping(protocol, "$protocol")
    _validate_protocol(protocol_copy)
    if parsed_card["family"] != protocol_copy["familyId"]:
        _fail("scenario.protocol_mismatch", "$protocol.familyId")
    variant_token = str(parsed_card["scenarioId"]).rsplit("-", 1)[1]
    public = {
        "schemaVersion": 1,
        "publicScenarioId": "public-" + str(parsed_card["scenarioId"]),
        "familyId": parsed_card["family"],
        "request": _require_string(protocol_copy.get("agentInputTemplate"), "$.agentInputTemplate").format(
            variantToken=variant_token
        ),
        "fixtureDigest": parsed_card["fixtureDigest"],
        "authorityManifestDigest": canonical_contract_digest("AuthorityManifest", parsed_card["authorityManifest"]),
        "resourceEnvelopeDigest": canonical_contract_digest("ResourceEnvelope", parsed_card["resourceEnvelope"]),
        "hiddenMaterialDigest": "none",
    }
    _assert_no_raw_hidden_material(public)
    return parse_contract("PublicScenario", public)


__all__ = ["Partition", "ScenarioCard", "TaskFamilyProtocol", "materialize_scenario", "public_scenario"]
