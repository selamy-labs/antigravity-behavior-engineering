# Evidence Store Contract

## Protected Layout

```text
evidence/raw/
├── attempts/<attempt-id>/attempt.json
├── attempts/<attempt-id>/lifecycle.ndjson
├── runs/<run-id>/run.json
├── runs/<run-id>/artifacts/<content-addressed-files>
└── runs/<run-id>/grades/<grader-digest>/grade.json

evidence/publishable/
├── runs/<public-run-id>/run.json
├── runs/<public-run-id>/artifacts/<approved-redacted-files>
└── reports/<release-id>/
```

`attempt.json` is created first and is immutable. Lifecycle transitions append
to `lifecycle.ndjson`; they never rewrite the attempt. The runner produces an
UnclassifiedStagedAttemptOutcome, the frozen classifier produces a
StagedAttemptOutcome, and the evidence importer alone writes `run.json` inside
a temporary run directory and atomically renames it to mark finalized evidence.
A finalized run is read-only. Grades are append-only children keyed by grader
digest.

## Content Integrity

- SHA-256 digests use lowercase hexadecimal with a `sha256:` prefix.
- Text is hashed as exact UTF-8 bytes after no newline normalization.
- JSON contract objects are serialized in canonical key order without
  insignificant whitespace before hashing.
- An artifact manifest records relative path, byte length, media type, digest,
  source zone, and redaction disposition.
- Symlinks, device files, sockets, and paths outside the run root are rejected.

## Redaction

Redaction is a one-way transformation from protected raw evidence to a new
publishable tree. It removes credentials, private paths, potentially
confidential task content, hidden checks, sealed protocols, private reasoning,
and condition identifiers that would unblind pending grading. It preserves:

- public configuration identity and limitations;
- task-family and fixture digests;
- process, classification, and consumption records;
- deterministic and blind-review outcomes;
- sufficient artifact and command evidence for the public claim;
- a protected mapping from public run ID to raw run ID.

The redactor emits a machine-readable report for every field and artifact:
`kept`, `transformed`, `withheld`, or `rejected`. A public release fails if
required audit evidence would have to be removed without an acceptable public
substitute.

## Classification and Re-grading

Classification uses the policy digest frozen with the ScenarioCard. A later
policy or grader may add a new GradeRecord but cannot mutate the original
RunRecord, original grade, ScheduledAttempt, or prior lifecycle event. Reports
name the exact policy, grader, rubric, and analysis digests they aggregate.

## Access

- Worker: write-only staging for its own run and no competing evidence.
- Controller: create attempts and invoke the runner, classifier, importer, and
  deterministic graders through their closed interfaces.
- Evidence importer: sole writer of immutable `run.json` and the subsequent
  `run_finalized` lifecycle event.
- Blind reviewer: normalized single-run projection without condition or model.
- Publisher: read protected grades and write only to publishable output.
- Runtime plugin: no access to this store.
