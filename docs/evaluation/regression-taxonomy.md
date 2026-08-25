# Immutable regression taxonomy

This portfolio keeps formative development, frozen regression, and sealed confirmation
as distinct evaluation partitions. T033 materializes only the regression partition.
It neither opens sealed instances nor promotes formative examples into release evidence.

## Frozen sources and materialization

The registry binds the T017 task-family protocols and scenario generator at
commit `448bcfa4d3b2ed2a33a4a94329b31d6795c54ec3`, and the T018 analysis locks at
commit `a351146384d66554a03f79b426552989179dc353`. Their canonical and file digests
are recorded under `sourceLocks` in `evals/regression/registry.json`.

Each frozen protocol has one positive and one relevant-negative regression
variant. The role-to-reserved-commitment assignment is fixed before replay.
The commitment string is supplied as the generator's opaque seed input; no
outcome, treatment output, hidden grader, or sealed instance influences
the semantic protocol or seed assignment. The original registry's claimed
concrete scenario bytes were synthetic and are unavailable. Under the T033
scope amendment, an independent evaluation context materialized the real
private 28-case bundle after the candidate causality freeze and before any
protected outcome was observed. The public registry contains only the resulting
fixture, starting-state, controller, and aggregate protected-material digests.
Its `concreteBindingCorrection` records the original registry digest, private
manifest digest, candidate freeze, qualification, and amendment bindings.
Candidate mutation remains forbidden after an outcome is observed.

The third reserved commitment remains unused. It is retained for the frozen
protocol rather than consumed after treatment.

## Coverage and evidence seams

The `coverage` table maps every directly covered behavior and failure family to
its frozen protocol families, positive and relevant-negative variant IDs,
analysis locks, classification policies, and artifact-first evidence seams.
Public scenario cards use opaque case identifiers plus canonical digests;
protected path resolution remains exclusively in the private controller
manifest.

The frozen suite directly covers hook and tool failures, but it does not
directly cover lifecycle behavior or subagent failure. T032 package-lifecycle
evidence and T029 review-topology evidence are checkpoint context, not causal
regression variants. The registry preserves the frozen hook/tool variants while
recording lifecycle and the subagent aspect as uncovered and ineligible for
T034 selection or release claims. New direct cases may be
diagnostic/noncausal only.

At the registry top level, `uncoveredFamilies` names only wholly uncovered
families (`lifecycle`), while `partiallyUncoveredFamilies` names the exact
uncovered aspect of an otherwise directly covered family (`subagent_failure`
within `hook_tool_subagent_failure`). Both claims and
`causalCoverageComplete` are derived from and checked against the detailed
coverage table.

The correction record retains the superseded bundle-time qualification digest
as `sourceQualificationDigest` and binds the sole eligible replacement
qualification plus its immutable amendment digest for downstream replay.
That replacement explicitly binds the structured stream boundary: the sole
`init` event must be first and the sole `result` event must be last. The prior
replacement qualification remains preserved but is ineligible because its
capture-boundary digest declared only relative ordering.

## Replay and interpretation

Replay uses the T018 cohorts and analysis locks without alteration. The bare
baseline and integrated full package are evaluated separately for
`gemini-3.1-pro-high` and `gemini-3.7-flash-high`. Classification follows the
recorded policy digest for each variant. Resource ceilings, failures,
classification disputes, and protected raw evidence remain in the protected
evidence store; the public registry contains only commitments, digests, and
reproducible projections.

Hidden canaries stay outside both scenario cards and public scenarios. The
regression, formative, and sealed partition identifiers are intentionally
different even when given the same family and commitment.

## Post-treatment diagnostics

Any case whose generator or protocol is introduced after treatment belongs in
`diagnostic-registry.json` as diagnostic/noncausal evidence. Such a case
cannot support T034 selection, a causal treatment claim, or a release claim.
The diagnostic registry starts empty and binds the immutable regression
registry digest so later additions cannot be mistaken for preregistered cases.
