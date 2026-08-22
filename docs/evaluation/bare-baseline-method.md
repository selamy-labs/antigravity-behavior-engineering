# Bare-Antigravity formative baseline method

T020 records the public method for a formative bare-Antigravity pilot. The
purpose is to identify repeatable gap candidates before authoring any local
treatment language.

Run the protected materializer with:

```text
uv run --project evaluator abe-eval run-matrix \
  --matrix evals/formative/bare-pilot.matrix.json \
  --condition bare \
  --qualification evidence/raw/qualification/local/qualification.json \
  --raw-root evidence/raw/formative/incumbent-baseline/bare
```

The raw root is protected evidence. It is intentionally outside the committed
repository and remains separate from publishable reports.

## Bare condition boundary

- Fresh app/home/profile state is required for every attempt.
- The empty prior conversation boundary is required.
- The repository is a fresh fixture-only checkout.
- The extension allowlist is empty.
- No Superpowers, candidate package files, treatment hooks, treatment agents, or
  local treatment instructions are enabled.
- The only committed repository instructions are fixture instructions derived
  from the frozen task-family protocol.

The matrix covers both target model requests separately:

- `gemini-3.1-pro-high`
- `gemini-3.7-flash-high`

Each model/family cell has three bare repetitions. Model outcomes are reported
separately and are never pooled.

## Analysis boundary

The committed analysis file is a redacted aggregate. It reports variance,
ceiling, attrition, resource, artifact outcome, first-divergence, and gap
candidate summaries from protected raw evidence.

Representative failures may be reviewed directly from raw streams and
artifacts, but the review scope is gap candidates only. T020 does not authorize
candidate treatment language, prompt edits, package behavior, or Superpowers
content.
