# Antigravity Behavior Engineering

This repository is a specification-only handoff for a public Antigravity
behavior-engineering plugin and its protected evaluator. It contains no plugin,
evaluator, worker, evaluation portfolio, or release-pipeline implementation.
Implementation is blocked until the project owner explicitly approves the final
reviewed 46-task set.

The approved objective is to improve Gemini 3.7 Flash and Gemini 3.1 Pro on deep
problem understanding, iterative implementation, verification, and adversarial
review by using the smallest empirically justified combination of rules, skills,
custom agents, hooks, and plugin packaging. Public upstream skill libraries stay
upstream; confidential material and private evaluation data stay out of Git.

## Start Here

1. Read [AGENTS.md](AGENTS.md).
2. Read [handoff/current-state.md](handoff/current-state.md).
3. Validate the checkout with `./handoff/validate-handoff.sh`.
4. Follow [handoff/bootstrap.md](handoff/bootstrap.md).
5. Stop at the task-set approval gate. After the exact owner approval sentence
   is recorded outside Git, initialize Ralph state and execute exactly one
   approved task from [tasks.md](specs/001-improve-antigravity-behavior/tasks.md)
   per PR, beginning with T001.

The architecture is summarized in
[docs/architecture/overview.md](docs/architecture/overview.md). The loop contract
and resumable state format are in
[handoff/ralph-execution-contract.md](handoff/ralph-execution-contract.md).

## Authority and Gates

The specification and implementation plan are approved. The final 46-task set is
not approved and does not authorize T001. Task-set approval, provenance approval,
candidate freeze, public-release approval, and publication authority are
separate human-only gates. Automation must not issue or infer any of them.

## Publication Status

The authorized public target is `pselamy/antigravity-behavior-engineering`.
Publication is deferred until the committed handoff passes validation and
working GitHub credentials/access for that target are available. Do not search
for or expose credentials.
