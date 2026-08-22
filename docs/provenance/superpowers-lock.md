# Superpowers upstream lock

T021 qualifies Superpowers as an upstream incumbent for formative comparison
only. The Superpowers skill bodies are not vendored into this repository or
republished under `plugin/`; this project records an external pin and verifies
that Antigravity can resolve a local checkout of that exact upstream source.

## External pin

- Source: https://github.com/obra/superpowers
- Revision: `b36e0829c6d0140e93cfef2ca599b1b07d4a7797`
- Version metadata: `6.3.0`
- License: MIT
- Public tree file count at the pin: 195
- Public tree root digest: `sha256:a89f1095b9170551686c36a85efb811bfffa6f925c6b757d17b4dcd540a6ea00`

Pinned file fingerprints:

- `LICENSE`: `sha256:a37e0e9697144819e1d965176ac4ae5bc3fa02d11e7812036bbcadf6dafe2400`
- `.codex-plugin/plugin.json`: `sha256:d7ac84a700062e865715f75626945a2a3324778c68dba1a543c7ed41e48def10`
- `gemini-extension.json`: `sha256:3200d324e4ce3c47edf5cf4b251878febb9c32f64ec33bb9eb58c06d96c8e3b9`
- `GEMINI.md`: `sha256:0823da8b7277f8b623746d57c0bee75fda02e4c832fe57843e644d0fe633abbc`
- `hooks/session-start`: `sha256:88a060272ca8047e0d1cd73a016e1cebba8396807a44be1e296d7c02dcbb9934`

## Reproducible resolution

Antigravity did not expose a source-SHA install primitive in the public CLI
surface under test. The reproducible external pin mechanism is therefore:

```sh
git init superpowers-pin
git -C superpowers-pin fetch --depth 1 https://github.com/obra/superpowers.git b36e0829c6d0140e93cfef2ca599b1b07d4a7797
git -C superpowers-pin checkout --detach b36e0829c6d0140e93cfef2ca599b1b07d4a7797
agy plugin validate superpowers-pin
agy plugin install superpowers-pin
```

The local checkout must be verified against the root digest and file digests
above before use. Failure to resolve, validate, install, discover, enable,
disable, session-start, or uninstall the pinned checkout is a visible
qualification failure; it is not grounds to copy upstream bodies into this
repository.

## Public/private boundary

The public repository may contain this lock record, aggregate formative analysis,
and lifecycle tests. Protected raw streams, per-attempt Antigravity profiles, and
the `BlindedBaselineInput` live under `evidence/raw/formative/incumbent-baseline`
and remain uncommitted.
