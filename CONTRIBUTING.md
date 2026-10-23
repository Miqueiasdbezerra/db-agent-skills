# Contributing

This is an MIT-licensed public repository. Preserve the license and copyright notices for original material and record the terms of third-party contributions.

## Scope

Each skill should solve a concrete authorized workflow, state when it should trigger, and make its capabilities and limits inspectable. Keep instructions compatible with their stated hosts, supporting files discoverable, examples fictional, and private runtime memory outside the source tree.

Preserve normal host permissions. Do not add automatic credential capture, global settings changes, permission-bypassing flags, undisclosed telemetry, background jobs, or tools that circumvent authentication.

## Changes and evidence

Explain the user-visible problem, intended behavior, authorization boundary, and evidence for the change. Add meaningful regression tests when a behavior or safety invariant changes. A test must establish the boundary or outcome; reproducing the implementation line by line is insufficient.

Use the [root README](README.md#run-the-checks) to run the local suites. Keep the skill's `package-manifest.json` synchronized when adding or removing public files. The package checker must accept the final source. Update the [validation record](docs/validation.md) when a claim changes.

Host evaluation must distinguish discovery, actual skill invocation, helper execution, API actions, and browser actions. Preserve meaningful skips and explain their cause. A simulated or mocked test must not be reported as a real browser or filesystem run.

## Content and provenance

Use reserved fictional domains, synthetic files, and sanitized examples. Never add live task journals, private playbooks, raw agent transcripts, session identifiers, screenshots of real accounts, secrets, or personal paths. If a failure involves real data, reproduce it privately and publish only a fictional regression.

Record external code, assets, and their applicable notices before including them. Do not copy third-party skills into the catalog without confirming rights. New licensing proposals belong in a clearly marked review document until the owner approves an effective license.

## Review and publication

Review file membership, Markdown links, operational assumptions, security limits, and relevant tests together. Public evidence should state what ran, where it ran, and what remains untested. Do not commit fabricated badges, certification claims, customer claims, or benchmark figures.

The owner explicitly approved the initial publication. Future changes still require the maintainer's review and applicable publication authority; preparing a local change does not itself authorize a push, release, repository creation, or visibility change.
