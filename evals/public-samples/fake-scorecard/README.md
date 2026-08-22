# Fake scorecard sample

This directory describes the deterministic evaluator-conformance sample used by `abe-eval fake-matrix`, `abe-eval grade`, and `abe-eval report`.

The sample contains no target-model run, no live Antigravity invocation, and no hidden grading content. It exercises the protected evaluator pipeline with synthetic worker outcomes so that the published scorecard can be recomputed from immutable raw evidence.

Run the sample from the repository root:

```sh
uv run --project evaluator abe-eval fake-matrix --matrix evals/formative/evaluator-conformance/matrix.json --raw-root evidence/raw/formative/evaluator-conformance
uv run --project evaluator abe-eval grade --analysis evals/formative/evaluator-conformance/analysis.json --raw-root evidence/raw/formative/evaluator-conformance
uv run --project evaluator abe-eval report --analysis evals/formative/evaluator-conformance/analysis.json --raw-root evidence/raw/formative/evaluator-conformance --output evidence/publishable/reports/evaluator-conformance
```

Expected headline metrics are 14 intention-to-treat attempts, 2 valid-run attempts, and a 0.5 valid-run success rate. The two valid runs are `success` and `ordinary_artifact_failure`; only `success` receives a passing fake grade.

To audit without trusting CLI summaries, read each immutable raw run at `evidence/raw/formative/evaluator-conformance/runs/*/run.json`, pair it with its grade at `evidence/raw/formative/evaluator-conformance/runs/*/grades/*/grade.json`, and recompute the scorecard written to `evidence/publishable/reports/evaluator-conformance/scorecard.json`.
