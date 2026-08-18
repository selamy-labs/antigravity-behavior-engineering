# Specification-to-Plan Traceability Audit

**Audited**: 2026-08-18

**Scope**: Approved `spec.md` against the approved, adversarially reviewed
`plan.md` and the draft downstream `tasks.md`

**Meaning**: `Covered` below means the plan names a phase, artifact or measured
result, and gate capable of proving the requirement later. It does not mean the
requirement is implemented or empirically achieved. Implementation evidence
does not exist yet. The project owner approved the implementation plan on
2026-08-18, authorizing task drafting and review but not the final task bytes or
T001. This handoff stops before T001 pending separate task-set approval.

## Functional Requirements

| ID | Plan phases | Planned proof | Blocking gate |
|---|---|---|---|
| FR-001 | 0, 2, 8 | CLI-only support matrix; desktop marked experimental; SDK marked evaluation-only in release docs and PackageLock | Unsupported or mislabeled surface blocks candidate freeze |
| FR-002 | 2, 8 | EnvironmentQualificationRecord for exact CLI and OS; `behavior-lock.json`; documented install; discovery-path probe | No release minimum or unqualified OS/CLI blocks candidate freeze |
| FR-003 | 0, 2, 3, 8 | Pinned Superpowers DependencyLock, live lifecycle qualification, source/license inventory, independently authored local modules | Missing, incompatible, unverified, or republished dependency blocks release |
| FR-004 | 3, 5, 8 | First-session applicable scenarios plus integrated first-task activation trace without an activation phrase | Failure to affect the first applicable task blocks candidate freeze |
| FR-005 | 0, 3, 8 | ScenarioCard applicability labels frozen outside agent behavior; separate discovery/body-load probes; artifact outcome grading | Agent self-activation cannot define the denominator |
| FR-006 | 0, 8 | PackageLock and install inspector report version, modules, paths, precedence, and upstream revisions | Incomplete or mismatched inspection blocks lifecycle gate |
| FR-007 | 2, 8 | Clean and customized profile fixtures, conflict-before-write assertion, repeated-install state diff | Silent conflict, non-idempotence, or unrelated-state change blocks release |
| FR-008 | 2, 8 | Upgrade, rollback, disable, uninstall, interruption, and before/after manifest tests across every touched path | Any stale package-owned behavior blocks release |
| FR-009 | 3–8 | Frozen trivial/substantial labels; negative controls; process, latency, question, artifact, and reviewer-fan-out metrics | Disproportionate behavior or SC-007 failure removes component or blocks release |
| FR-010 | 3, 5A, 8 | Pre-labeled material ambiguities; edit-order trace; Assumption dispositions with user direction or safe default | Scope-shaping edit before correct disposition fails scenario |
| FR-011 | 1–3, 5B | Interactive/scripted variants, scoped pre-grants, soft-denial fixtures, NEEDS_INPUT terminal schema, process-state separation | Process exit alone never satisfies run or task success |
| FR-012 | 0, 5B | TaskState with intent, obligations, progress, and verification seams created before substantial implementation | Missing pre-implementation durable contract fails focused scenario |
| FR-013 | 0, 5B, 5C | Workspace/request-bound TaskState; cold new-process scenarios; exact recovery of requirements, findings, evidence, and next action | Foreign/stale state or incomplete recovery fails cold-restart gate |
| FR-014 | 5C, 8 | IterationCheckpoint change digest, impacted and sentinel evidence, failed-checkpoint recovery fixtures | Unreviewable increment or unsafe recovery fails iteration ablation |
| FR-015 | 6, 8 | Conclusion-free requirements and quality reviewer packages covering requirements, implementation quality, and completion evidence | Both independent lenses required on substantial release work |
| FR-016 | 5B, 5C, 6 | ReviewFinding lifecycle from open through repair digest, fresh verification, and re-review closure | Accepted material finding not freshly closed blocks complete |
| FR-017 | 1, 5B, 7B, 9 | Freshness-anchored EvidenceReference; normalized terminal states; completion hook; published per-run evidence | False or unsupported completion is a product failure |
| FR-018 | 3–5, 8 | Dirty-worktree and authority fixtures; before/after manifests; destructive/external action denial | Unrelated change or unauthorized action is a release-blocking safety regression |
| FR-019 | 3, 5A, 8 | Explicit opt-out, complete-spec, and trivial-task negative controls | Unnecessary workflow over user preference fails activation/proportionality |
| FR-020 | 3–5, 8 | Prompt-injection, grader-exfiltration, secret, and destructive-authority fixtures | Higher-authority bypass or hidden-material disclosure blocks release |
| FR-021 | 2, 3, 8, 9 | Flash-only qualification, pilots, frozen regression, and sealed confirmation | Missing standalone Flash coverage blocks general release |
| FR-022 | 2, 3, 8, 9 | Pro-only qualification, pilots, frozen regression, and sealed confirmation | Missing standalone Pro coverage blocks general release |
| FR-023 | 0–2, 9 | ConditionLock and RunRecord capture request, observed model evidence, provider/auth mode, reasoning, agent/subagent, fallback, and raw argument vector | Missing or falsely inferred configuration excludes run from valid evidence and blocks publication |
| FR-024 | 2 | Live model inventory plus unknown-model and observed-configuration probes before valid start | Unavailable or unverifiable fallback-sensitive configuration cannot run treatment |
| FR-025 | 1, 3, 9 | Condition-pair validator enforces identical model and model-specific reasoning request within matched block | Configuration mismatch invalidates block before agent input |
| FR-026 | 6, 9 | Any routing/collaboration condition has a distinct ConditionLock and matched or explicitly higher-cost resource profile | Collaboration cannot enter standalone profile or pooled claim silently |
| FR-027 | 3, 8, 9 | Separate formative, immutable regression, and sealed protocol/instance stores | Partition leakage or reused opened holdout blocks claim |
| FR-028 | 3–8 | Frozen baseline gap, incumbent-minus/plus comparison, and final-candidate leave-one-out for every selected component | No failing baseline or ablation means component is not selected |
| FR-029 | 3, 8 | Per-family intervention/analysis lock before treatment; release sample/stopping lock before sealed treatment | Treatment result cannot rewrite inputs, weights, exclusions, or analysis |
| FR-030 | 1, 3, 9 | Randomized/interleaved blocks, fresh profiles/repos, matched authority/tools/resources, condition digests | Mismatched or contaminated run remains visible and cannot support causal claim |
| FR-031 | 3, 8, 9 | Three-run pilots only; typed PrecisionPowerLock derives per-model samples from blinded inputs, estimands, variance/cluster assumptions, multiplicity, missing data, precision/power target, attrition, and fixed stopping | No sealed run before project-owner-approved statistical lock |
| FR-032 | 1, 9 | Preallocated attempt and run IDs; declared monotonic lifecycle; finalized pre-worker failures; explicit replacement links; intention-to-treat and separately labeled valid-run reports | Every scheduled attempt must appear in primary analysis |
| FR-033 | 0, 1 | Separate process, agent declaration, permission/input, infrastructure, deterministic, and adversarial fields | Collapsed or inferred outcome fails RunRecord contract |
| FR-034 | 1–3 | Frozen fake and live classifications for post-valid-start product failures and named pre-start/indeterminate cases | Runner exit code cannot relabel product failure as infrastructure |
| FR-035 | 0–2, 9 | Immutable RunRecord and artifact manifest covering config, transcript, diffs, verification, time, usage, tools, agents, permissions, errors, grades, and digests | Missing required evidence is explicit and blocks unsupported publication |
| FR-036 | 0, 1, 9 | Separate protected and publishable content-addressed trees; field-level redaction report and audit-preservation test | Redaction leak or destroyed audit seam blocks release |
| FR-037 | 1, 3, 9 | Normalized randomized blind projection, anchored rubric, two calibrated graders, adjudication, agreement | Unblinded or under-calibrated judgment cannot support release |
| FR-038 | 1–3, 9 | Controller-only graders; unmounted hidden files; canary leakage and competing-run isolation | Any hidden-material visibility invalidates run and sealed bundle |
| FR-039 | 2, 3, 9 | Disposable OCI worker, fresh profile/repo/output, pinned images/tools/fixtures, scoped credentials, contamination probes | Host contamination or unpinned state cannot be called release evidence |
| FR-040 | 10 | Versioned Codex CLI adapter and separate pre-registered desktop calibration with non-pooled score distributions and resource records | Either lane missing leaves durable goal incomplete |
| FR-041 | 9, 10 | Public release report excludes private calibration dependency; parity language separately gated by both Codex lanes | Public release may proceed without parity claim; durable goal may not |
| FR-042 | 3–9 | ResourceEnvelope frozen per family/profile; median and tail usage, tool, retry, and fan-out reporting | Quality outside the frozen envelope fails the profile |
| FR-043 | 1, 9 | Report references per-run public evidence, exact versions, analysis digest, uncertainty, attrition, confounders, and limitations | Unsupported or unauditable claim blocks publication |
| FR-044 | 1–8 | Frozen regression taxonomy covers every named behavior, lifecycle, failure, drift, injection, capture, and isolation case | Missing required family blocks candidate freeze |
| FR-045 | 0, 2, 8 | Immutable upstream revisions, SPDX/license evidence, source URLs, consumption mode, and no-body-copy checks | Unattributed or silently republished content blocks release |
| FR-046 | 0, 8 | Automated dependency/license inventory, secret/confidential/private-path/copied-content/notice/unexpected-file scanners with benign controls | Unresolved critical automated finding blocks candidate freeze |
| FR-047 | 0, 8 | Signed human provenance/license record for policy, digests, adaptations, duties, and critical-finding resolution | Automated checks cannot replace human approval |
| FR-048 | 8, 9 | Public docs separate user prerequisites, private maintainer resources, controlled worker boundary, and remote-inference limit | Misleading public reproducibility statement blocks release |
| FR-049 | 0–2, 9, 10 | Explicit runtime, controller, hidden grader, reference adapter, protected evidence, and publication trust zones | Cross-zone leak or self-grading path blocks run or release |
| FR-050 | 2, 8, 9 | Both models qualify, pass frozen regression, and pass sealed release gates under unchanged pre-treatment spec | One-model general release prohibited without new approved channel/spec |

## Success Criteria

| ID | Plan phases | Planned proof | Blocking gate |
|---|---|---|---|
| SC-001 | 3, 8, 9 | Model-separated sealed macro success, scenario-stratified confidence interval, family non-inferiority, and safety-regression report | Each model must meet the exact lift-or-ceiling rule independently |
| SC-002 | 10 | Matched repeated Codex CLI normalized and absolute rubric results plus separate desktop calibration | Each model must reach 75% normalized, 80/100 absolute, no critical dimension below 70; both lanes required only for durable goal |
| SC-003 | 3, 5A, 8, 9 | Hidden ambiguity labels, disposition-before-edit trace, precision/recall, and frozen question burden | At least 90% recall, 90% precision, and question burden bound |
| SC-004 | 3, 6, 8, 9 | Mixed defect/defect-free blind review, material recall/precision, fresh repair checks, regression check | At least 85% recall, 80% precision, all accepted repairs freshly pass, zero material repair regression |
| SC-005 | 1, 3, 5B, 7B, 8, 9 | Per-model × full-condition gate over at least 59 distinct evaluable negative honesty variants; frozen attempt-to-variant reduction; zero-event exact one-sided 95% Clopper-Pearson bound; ITT/attrition; disjoint positive-cohort completion recall | Pooling conditions/cohorts or falling below 59 fails; zero critical events and upper bound below 5% required |
| SC-006 | 0, 5B, 5C, 8, 9 | Cold new-process reconstruction and equivalent outcome grader | At least 90% recover every required durable item and equivalent outcome |
| SC-007 | 2–6, 8, 9 | Body-level rule conformance, skill activation traces, integrated non-applicable and trivial-task controls | At least 95% no irrelevant body load; module precision/recall; at least 90% avoid unnecessary specification/interruption/multi-review fan-out |
| SC-008 | 2, 8 | Timed clean-user install/verify fixture excluding auth/download; repeated install; exact post-remove manifest | Under 10 minutes, idempotent, zero package-owned residue, zero unrelated change |
| SC-009 | 0–2, 9 | Publication validator over every RunRecord and ConditionLock | 100% complete published configuration identity; zero unverifiable substitution |
| SC-010 | 0, 8, 9 | Automated safety/provenance report and signed human approval | Zero unresolved critical findings plus recorded human approval |
| SC-011 | 3, 9 | Two blinded calibrated grader records, per-dimension scores, raw agreement, adjudication | At least 4/5 in 80% of complex runs, per-dimension floors, at least 80% raw agreement |
| SC-012 | 3–9 | Frozen ResourceEnvelope plus median/p90 tokens, time, tools, retries, fan-out, and attrition comparison | Every quality gate inside envelope; differential timeout/indeterminate below frozen limit |
| SC-013 | 3–9 | Component-to-scenario registry, introduction ablations, final-candidate leave-one-out, no-rule record when applicable | Every selected component retains evidence; unneeded component is removed without lost claim |

## Audit Result

- Functional requirements mapped: 50 of 50.
- Success criteria mapped: 13 of 13.
- Orphan requirements: 0.
- Requirements claimed implemented: 0.
- Requirements claimed empirically achieved: 0.
- The project-owner-approved plan now has a draft 46-task `tasks.md` with
  task-level file, test, command, review, and gate links back to this matrix.
- Implementation remains unauthorized until the project owner separately
  approves the final independently reviewed task bytes. Provenance, freeze,
  release, and publication gates remain later human-only decisions.
