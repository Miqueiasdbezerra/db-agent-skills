# Validation record ? WebOps Secretary 1.0.0

Phase 2 date: 2026-10-23. This release candidate has been exercised against a real loopback HTTP service and Chrome, as well as actual Claude Code and Codex CLI sessions. See [host-validation.md](references/host-validation.md) for the evidence matrix and host restrictions.

## Reproducible local checks

Run from the skill directory, with Python 3.10+:

```powershell
python -B -m unittest discover -s tests -v
python -B examples/simulated_browser.py
python -B scripts/package_skill.py check
```

The current skill suite has 73 tests: 70 passed, 3 skipped, no failures/errors on the validation Windows environment with Python 3.15.0rc3. The skips require real symlink creation privilege. Two real Windows junction checks and six portable metadata/guard alternatives passed. There are no installed Python dependencies. Initial phase-1 baseline was 63 tests; phase 2 added ten security/portability regressions.

The exact-file release allowlist contains 21 files, including the owner-approved MIT LICENSE. Markdown links, entrypoint metadata, Python source syntax, and package membership are validated by the standard-library suite. The optional installed skill-creator quick validator requires absent PyYAML; no dependency was installed for it.

## Coverage and observed results

- Fresh page observations, form validation, uploads, navigation recovery and changed interfaces in the simulator.
- Actual Chrome navigation, information lookup, form creation, persisted edit and fictional text-file upload in a local demonstration service.
- Deliberate HTTP 503 after commit, unknown journal state, closed browser tab and fresh-tab reconciliation before continuing.
- One persisted record after a controlled same-reference create; one note and three effective server operations for the completed main browser journey.
- Actual CLI skill invocation/loading, private SQLite memory, draft versus validated playbooks and fresh-session recovery, with the exact differences between hosts documented separately.
- Stable operation keys, immutable terminal outcomes, scoped recall, confidence/date maintenance and stale-procedure handling.
- Private-root checks, credential/JSON-input regressions, safe filename handling, link/junction refusal, exact release allowlist and deterministic ZIP/hash verification.

## Practical limits

No production account or external administrative site was changed. Claude's observed web actions used a narrow HTTP service adapter, not a browser. Codex CLI's restricted Windows sandbox could read the skill but could not run the installed Python; that limitation was preserved instead of bypassed. A real workflow in the current Codex browser host does not establish access for another installation.

No distributed exactly-once guarantee, encryption, cross-device memory sync, automatic retention or independent consent verification is supplied. Windows ACLs are inherited. Heuristic scans cannot certify the absence of every secret or personal detail. Private evidence remains outside this package, and MIT is applied to original project material; final publication approval remains pending.

Further host evaluation: [MANUAL-AGENT-EVAL.md](tests/MANUAL-AGENT-EVAL.md).
