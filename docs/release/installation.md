# Installation and removal

Antigravity CLI is the only release-gating product surface for version one.
The supported environment is Antigravity CLI 1.1.18 or newer on Linux x64 with
Node.js 22 through 24. Desktop/IDE is experimental. SDK use is evaluation-only.

Use a disposable profile for qualification. Never point lifecycle tests at an
ordinary user profile. Validate and install the local release candidate with:

```bash
agy plugin validate plugin
agy plugin install plugin
agy plugin list
```

The package lock identifies Superpowers at revision
`b36e0829c6d0140e93cfef2ca599b1b07d4a7797`. It remains an independently
attributed upstream dependency. A user-owned Superpowers installation is
verified in place and is never copied into, upgraded by, or removed with this
package. A missing optional research dependency is reported as absent; a
required or revision-mismatched dependency fails before installation.
Verification does not trust a dependency marker by itself. The recorded source,
revision, ownership, and artifact digest must match the descriptor-safely read
installed directory, its embedded revision record, and its discovery entry.
The customized qualification fixture uses the qualified Superpowers 6.3.0 pin;
marker-only, missing, drifted, undiscovered, or ownership-mismatched artifacts
fail closed. The verified artifact and discovery record must remain byte-for-byte
unchanged after the lifecycle run.

The release lifecycle runner uses a new disposable profile, exercises repeated
installation, disablement, enablement, upgrade, rollback, and removal, and
records timing outside Git:

```bash
node packages/plugin-tooling/bin/lifecycle-test.mjs \
  --plugin plugin --profile-fixture clean \
  --record-timing evidence/raw/lifecycle/clean-timing.json
node packages/plugin-tooling/bin/lifecycle-test.mjs \
  --plugin plugin --profile-fixture customized \
  --record-timing evidence/raw/lifecycle/customized-timing.json
```

The counted interval is local validation, installation, and package inspection.
The authentication and dependency download intervals are recorded as separate excluded
intervals and cannot be hidden inside the counted result. The counted interval
must remain below ten minutes. The runner enforces that limit with a shared
monotonic deadline for validation, installation, and inspection. Every spawned
CLI command is bounded to at most the same limit, combined standard output and
error capture has a one-mebibyte ceiling, and a timeout or bounded output
failure terminates the command process group instead of producing a timing pass.

To remove the package, first use the supported CLI command:

```bash
agy plugin uninstall antigravity-behavior-engineering
```

Antigravity CLI 1.1.x may leave inert import or explicit enablement metadata.
The lifecycle runner records that CLI residue and restores only the two
package-owned metadata files to their exact pre-test bytes. It also removes the
package installation directory. The same cleanup runs after an interrupted command
or any later lifecycle failure, and a failed exact-baseline comparison
is surfaced as a cleanup failure. It never rewrites a user-owned dependency or
unrelated setting. For a release check, capture the
strict pre-install and post-removal profile manifests and require an empty diff:

```bash
node packages/plugin-tooling/bin/compare-profile.mjs \
  --before evidence/profile-before.json \
  --after evidence/profile-after.json
```

An empty diff, no package directory, no package import, and no package config
entry are all required. Cache and CLI-runtime directories are the only accepted
volatile path exclusions; configuration and import manifests are inspected and
must not conceal stale package behavior.
