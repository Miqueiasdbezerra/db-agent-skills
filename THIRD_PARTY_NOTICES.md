# Provenance and third-party notices

## Authored material

The WebOps Secretary candidate, supporting Python helpers, fictional examples, tests, and repository documentation were newly authored for this project. No third-party skill collection or vendored Python package is intentionally included. This is a provenance statement, not a license grant or a legal certification of rights.

The owner explicitly confirmed Copyright (c) 2026 Miqueias Durans Bezerra and authorized [MIT](LICENSE) for original project files. The licensing record separates that attestation from the observable component audit; see [licensing and provenance](docs/LICENSE-PROPOSAL.md).

## Runtime and service dependencies

Bundled Python code uses only Python's standard library, including SQLite through `sqlite3`. Python and its associated runtime components are installed separately and retain their own licenses; their source or binaries are not vendored here.

OpenAI Codex, Claude Code, browser software, connectors, and GitHub are separate tools or services. They are not included in this repository and remain subject to their own terms, licenses, account controls, and charges. Naming them describes intended compatibility and does not imply endorsement or affiliation.

The prepared GitHub Actions workflow refers to GitHub-maintained checkout and Python setup actions. Those actions run separately in a future CI environment and retain their own notices. No remote CI run is claimed by the workflow's inclusion.

| External CI action | Pinned revision | License and retained copyright notice |
| --- | --- | --- |
| `actions/checkout` | `11d5960a326750d5838078e36cf38b85af677262` | [MIT, exact revision](https://github.com/actions/checkout/blob/11d5960a326750d5838078e36cf38b85af677262/LICENSE), Copyright (c) 2018 GitHub, Inc. and contributors |
| `actions/setup-python` | `a26af69be951a213d495a4c3e4e4022e16d87065` | [MIT, exact revision](https://github.com/actions/setup-python/blob/a26af69be951a213d495a4c3e4e4022e16d87065/LICENSE), Copyright (c) 2018 GitHub, Inc. and contributors |

These action implementations are fetched by GitHub Actions when CI runs; they are not bundled in the skill or repository ZIPs. The project's MIT notice does not replace the actions' notices or the licenses of separately installed runtimes.

## Documentation references

- [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills).
- [Anthropic: Extend Claude with skills](https://code.claude.com/docs/en/skills).
- [Open Source Initiative: MIT license text](https://opensource.org/license/mit), used for the standard MIT terms applied to original material.

Links are references, not redistributed host documentation. Future additions must record copied code, assets, or adapted material and their required notices before distribution.
