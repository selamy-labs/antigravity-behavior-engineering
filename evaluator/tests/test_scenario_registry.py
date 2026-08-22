from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract
from abe_eval.scenario import materialize_scenario, public_scenario


PROTOCOL_REGISTRY = Path("evals/protocols/task-families.json")
FORMATIVE_REGISTRY = Path("evals/formative/registry.json")
REGRESSION_REGISTRY = Path("evals/regression/registry.json")
PARTITIONS = ("formative", "regression", "sealed")
FR044_BEHAVIORS = {
    "interrogation",
    "proportionality",
    "durable_intent",
    "root_cause_debugging",
    "verification_honesty",
    "defect_review",
    "defect_free_review",
    "repair",
    "cold_restart",
    "preferences",
    "dirty_worktrees",
    "prompt_injection",
    "permission_soft_denial",
    "missing_input",
    "hook_failure",
    "tool_failure",
    "model_drift",
    "quota_drift",
    "truncated_capture",
    "grader_leakage",
    "state_isolation",
}
REQUIRED_WORKFLOW_TIERS = {
    "interactive_user_direction",
    "scoped_pregrant_success",
    "unattended_safe_default",
    "explicit_needs_input",
    "headless_soft_denial",
}
COMPONENTS = ("skill", "hook", "agent", "rule")
RAW_HIDDEN_FIELD_NAMES = {
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
RAW_HIDDEN_TEXT_MARKERS = (
    "ABE_HIDDEN_",
    "RAW_CANARY_",
    "REFERENCE_SOLUTION:",
    "GRADER_INSTRUCTION:",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _protocols() -> list[dict[str, Any]]:
    return copy.deepcopy(_load(PROTOCOL_REGISTRY)["protocols"])


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _text_blob(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _assert_no_worker_readable_hidden_material(value: Any) -> None:
    for node in _walk(value):
        assert RAW_HIDDEN_FIELD_NAMES.isdisjoint(node), sorted(RAW_HIDDEN_FIELD_NAMES & set(node))
    blob = _text_blob(value)
    for marker in RAW_HIDDEN_TEXT_MARKERS:
        assert marker not in blob


def _assert_digest(value: str) -> None:
    assert value.startswith("sha256:")
    assert len(value) == 71
    assert value[7:] == value[7:].lower()


def test_task_family_registry_freezes_pre_treatment_protocols_not_instances():
    registry = _load(PROTOCOL_REGISTRY)
    protocols = registry["protocols"]

    assert registry["schemaVersion"] == 1
    assert registry["behaviorTaxonomy"] == sorted(FR044_BEHAVIORS)
    assert len(protocols) >= 12
    assert len({protocol["familyId"] for protocol in protocols}) == len(protocols)
    assert set().union(*(set(protocol["behaviors"]) for protocol in protocols)) == FR044_BEHAVIORS
    assert {protocol["workflowTier"] for protocol in protocols} >= REQUIRED_WORKFLOW_TIERS
    assert registry["hiddenMaterialPolicy"] == {
        "schemaVersion": 1,
        "storage": "commitments_only",
        "workerReadableRawHiddenMaterial": False,
        "sealedInstancesCommitted": False,
    }

    controls_by_component = {
        component: {protocol["componentControls"][component] for protocol in protocols}
        for component in COMPONENTS
    }
    assert controls_by_component["skill"] >= {"positive", "negative"}
    assert controls_by_component["hook"] >= {"positive", "negative"}
    assert controls_by_component["agent"] >= {"positive", "negative"}
    assert controls_by_component["rule"] >= {"negative"}
    assert all(control in {"positive", "negative"} for controls in controls_by_component.values() for control in controls)

    for protocol in protocols:
        assert protocol["schemaVersion"] == 1
        assert protocol["variantRules"] == {
            "schemaVersion": 1,
            "generatorInputs": ["familyId", "partition", "seedCommitment"],
            "postTreatmentInputsAllowed": False,
            "labelsEditableByTreatment": False,
            "equivalentConditionInputs": True,
        }
        assert protocol["preTreatmentLabels"]["workflowTier"] == protocol["workflowTier"]
        assert protocol["preTreatmentLabels"]["applicability"] == protocol["applicability"]
        assert protocol["preTreatmentLabels"]["evidenceSeams"]
        assert protocol["preTreatmentLabels"]["authorityTier"]
        assert isinstance(protocol["weight"], int)
        assert protocol["weight"] >= 1
        assert isinstance(protocol["exclusions"], list)
        assert protocol["exclusions"]
        assert protocol["hiddenCheckCommitments"]
        assert all(set(check) == {"checkId", "canaryCommitment"} for check in protocol["hiddenCheckCommitments"])
        for check in protocol["hiddenCheckCommitments"]:
            _assert_digest(check["canaryCommitment"])
        _assert_no_worker_readable_hidden_material(protocol)


def test_partition_registries_reserve_seeds_and_record_contamination_without_instances():
    registries = {
        "formative": _load(FORMATIVE_REGISTRY),
        "regression": _load(REGRESSION_REGISTRY),
    }
    protocol_ids = {protocol["familyId"] for protocol in _protocols()}
    partition_commitments: dict[str, set[str]] = {}

    for partition, registry in registries.items():
        assert registry["schemaVersion"] == 1
        assert registry["partition"] == partition
        assert registry["sealedInstancesCommitted"] is False
        assert set(registry["familyIds"]).issubset(protocol_ids)
        assert registry["familyIds"]
        assert registry["reservedSeedCommitments"]
        assert registry["contaminationHistory"]
        assert all(entry["source"] == "pre_treatment_registry" for entry in registry["contaminationHistory"])
        assert all(entry["event"] in {"registry_created", "contamination_check"} for entry in registry["contaminationHistory"])
        assert "scenarioId" not in _text_blob(registry)
        assert "agentInput" not in _text_blob(registry)
        assert '"partition":"sealed"' not in _text_blob(registry)
        _assert_no_worker_readable_hidden_material(registry)
        partition_commitments[partition] = set(registry["reservedSeedCommitments"])
        for commitment in registry["reservedSeedCommitments"]:
            _assert_digest(commitment)

    task_family_registry = _load(PROTOCOL_REGISTRY)
    sealed_commitments = set(task_family_registry["reservedSeedCommitments"]["sealed"])
    assert sealed_commitments
    assert partition_commitments["formative"].isdisjoint(partition_commitments["regression"])
    assert sealed_commitments.isdisjoint(partition_commitments["formative"])
    assert sealed_commitments.isdisjoint(partition_commitments["regression"])
    assert '"partition":"sealed"' not in _text_blob(task_family_registry)


def test_materialize_scenario_is_deterministic_partitioned_and_contract_valid():
    protocol = _protocols()[0]

    first = materialize_scenario(protocol, "t017-seed-alpha", "formative")
    repeated = materialize_scenario(copy.deepcopy(protocol), "t017-seed-alpha", "formative")
    different_seed = materialize_scenario(protocol, "t017-seed-beta", "formative")
    partitioned = {partition: materialize_scenario(protocol, "t017-seed-alpha", partition) for partition in PARTITIONS}

    assert first == repeated
    assert first != different_seed
    assert len({card["scenarioId"] for card in partitioned.values()}) == len(PARTITIONS)
    assert len({card["fixtureDigest"] for card in partitioned.values()}) == len(PARTITIONS)
    assert {card["partition"] for card in partitioned.values()} == set(PARTITIONS)

    parsed = parse_contract("ScenarioCard", first)
    assert parsed == first
    assert first["family"] == protocol["familyId"]
    assert first["applicability"] == protocol["applicability"]
    assert first["materialAmbiguities"] == protocol["materialAmbiguityLabels"]
    assert first["weight"] == protocol["weight"]
    assert first["variantProtocolDigest"] == sha256_digest(
        canonical_bytes(
            {
                "schemaVersion": 1,
                "familyId": protocol["familyId"],
                "partition": "formative",
                "seedCommitment": sha256_digest(b"t017-seed-alpha"),
                "protocolDigest": sha256_digest(canonical_bytes(protocol)),
            }
        )
    )
    assert first["agentInput"].startswith("protected/scenarios/formative/")
    assert canonical_contract_digest("AuthorityManifest", first["authorityManifest"])
    assert canonical_contract_digest("ResourceEnvelope", first["resourceEnvelope"])
    assert all(parse_contract("CheckLock", check) == check for check in first["checks"])
    _assert_no_worker_readable_hidden_material(first)


def test_materialized_public_projection_and_worker_surface_hide_controller_material():
    protocol = _protocols()[2]
    card = materialize_scenario(protocol, "t017-seed-public-projection", "regression")
    public = public_scenario(card, protocol)
    variant_token = card["scenarioId"].rsplit("-", 1)[1]

    assert parse_contract("PublicScenario", public) == public
    assert public["hiddenMaterialDigest"] == "none"
    assert public["familyId"] == protocol["familyId"]
    assert public["request"] == protocol["agentInputTemplate"].format(variantToken=variant_token)
    assert public["fixtureDigest"] == card["fixtureDigest"]
    assert public["authorityManifestDigest"] == canonical_contract_digest("AuthorityManifest", card["authorityManifest"])
    assert public["resourceEnvelopeDigest"] == canonical_contract_digest("ResourceEnvelope", card["resourceEnvelope"])

    worker_visible = {
        "agentInput": card["agentInput"],
        "applicability": card["applicability"],
        "authorityManifest": card["authorityManifest"],
        "resourceEnvelope": card["resourceEnvelope"],
        "publicScenario": public,
    }
    worker_blob = _text_blob(worker_visible)
    assert "checks" not in worker_blob
    assert "hiddenCheckCommitments" not in worker_blob
    assert "classificationPolicy" not in worker_blob
    assert "grader" not in worker_blob.lower()
    _assert_no_worker_readable_hidden_material(worker_visible)
