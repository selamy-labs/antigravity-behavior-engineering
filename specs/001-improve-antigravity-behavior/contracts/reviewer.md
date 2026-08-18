# Reviewer Contract

## Invocation Package

The worker invokes a reviewer with a content-addressed package containing only:

```text
review-input/
├── review-pair-envelope.json
├── review-request.json
├── approved-obligations.json
├── artifact-or-diff.patch
├── artifact-manifest.json
├── verification-interface.json
└── authority.json
```

`review-pair-envelope.json` is role-neutral and binds the shared artifact,
obligation, verification-interface, authority, and common-file manifest
digests. Exactly two separately content-addressed `review-request.json` objects
derive from it, one naming `requirements` and one naming `quality`. Each request
binds the parent-envelope digest and its own role-specific package manifest. The
packages exclude the implementer's conclusion, scratch reasoning, expected
defect count, hidden grader material, other reviewer output, and competing runs.
The shared manifest excludes the envelope/request/verdict files; each
role-visible package manifest includes the parent envelope but excludes its own
request and verdict. The request then binds that manifest and hashes canonically
excluding only its `reviewRequestDigest`, so no digest depends on itself.

The reviewer's model is `inherit` for the primary standalone condition. Its tool
list is validated by `agy agents` and a no-op invocation before any behavioral
run. Review authority is read-only except for writing its verdict artifact.

The production `reviewer-package.mjs` builder creates the role-neutral parent
once and each role-specific tree under a distinct content-addressed root,
rejects symlink/path escape, and returns both canonical request digests. A
reviewer never receives a caller-assembled ad hoc package or the sibling role's
request/output.

## Verdict Output

The reviewer writes one JSON object conforming to ReviewerVerdict. A finding is:

```json
{
  "schemaVersion": 1,
  "id": "Q-1",
  "severity": "important",
  "claim": "The rendered table omits the required total row.",
  "evidence": [
    {
      "schemaVersion": 1,
      "kind": "observation",
      "locator": "evidence/shoplist-show.txt",
      "digest": "sha256:…",
      "observedAt": "2026-08-18T00:00:00Z",
      "afterChangeDigest": "sha256:…",
      "result": "fail"
    }
  ],
  "affectedObligationIds": ["O-2"],
  "suggestedFalsification": "Run the real show command and assert one TOTAL row with the fixture sum."
}
```

The verdict may contain zero findings. Finding count is not a score. Every
finding needs inspected evidence and a falsifiable claim; style preferences
without an obligation, defect, regression, safety issue, or maintainability
hazard are rejected by schema or downstream triage.

## Worker Handling

The worker validates the verdict role, exact role-specific review-request
digest, shared review-pair-envelope digest, and artifact, obligation,
verification-interface, and authority digests before using it. Any missing,
stale, replayed, timed-out, permission-blocked, or mismatched verdict becomes
indeterminate review evidence, never a pass.
Accepted material findings become TaskState repair work. Completion requires a
repair digest, fresh focused verification, and a review closure record.

The production `reviewer-join.mjs` first applies that validator independently to
each role, requires distinct correctly typed ReviewRequests whose shared fields
match the same exact ReviewPairEnvelope, proves the two invocation packages
contain no competing verdict, and emits a closed ReviewJoinRecord binding both
request digests. It performs only a role-tagged mechanical union of finding
references. It never averages verdicts, deduplicates semantic claims, or
converts an invalid or missing role into pass.

Requirements and quality reviewers do not communicate during paired review.
Their outputs are joined only after both finish.
