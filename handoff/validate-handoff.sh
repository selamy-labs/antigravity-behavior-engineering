#!/usr/bin/env bash

set -euo pipefail

repo_root="$(CDPATH='' cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

for command_name in git rg shasum python3 specify; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "missing required handoff command: $command_name" >&2
    exit 1
  }
done

test "$(specify --version)" = "specify 0.16.0" || {
  echo "Spec Kit must be exactly 0.16.0 for this handoff" >&2
  exit 1
}

./.specify/scripts/bash/check-prerequisites.sh \
  --json --require-tasks --include-tasks >/dev/null

python3 handoff/validate_handoff.py

if [[ -f handoff/artifact-manifest.sha256 ]]; then
  shasum -a 256 -c handoff/artifact-manifest.sha256
fi

if [[ -n "${PUBLIC_BOUNDARY_DENYLIST_FILE:-}" ]]; then
  test -f "$PUBLIC_BOUNDARY_DENYLIST_FILE" || {
    echo "PUBLIC_BOUNDARY_DENYLIST_FILE does not name a readable file" >&2
    exit 1
  }
  if rg -n -i -f "$PUBLIC_BOUNDARY_DENYLIST_FILE" \
      --glob '!.git/**' --glob '!handoff/artifact-manifest.sha256' .; then
    echo "protected public-boundary denylist matched repository content" >&2
    exit 1
  fi
fi

echo "handoff validation passed"
