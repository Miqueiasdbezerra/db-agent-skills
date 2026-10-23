# Validation and compatibility

WebOps Secretary 1.0.0 was reviewed locally and its source published with explicit owner approval on 2026-10-23. Original project files use the owner-approved MIT license, with the copyright holder Miqueias Durans Bezerra. Source publication does not itself mean a tagged GitHub Release exists.

## What was actually run

| Evidence | Result | Boundary |
|---|---|---|
| Skill unit/integration suite | 73 tests: 70 passed, 3 skipped, 0 failures/errors on Windows/Python 3.15.0rc3 | Covers deterministic helpers and simulator, not a live model's behavior |
| Loopback HTTP demo suite | 12 tests passed, no skips | Real HTTP requests through urllib; distinct from browser operation |
| Current Codex host + Chrome | Live information lookup, form create/edit, file chooser/upload, committed-save error recovery, new-tab resumption and duplicate prevention passed | Current host supplied browser tools and an executable Python |
| Claude Code CLI 2.1.302 | Actual Skill invocation, private memory, fresh-session recovery and real loopback form/edit/multipart upload passed | Service adapter, not a Claude browser test; explicit invocation only |
| Codex CLI 0.162.0-alpha.17.2 | Official app-server enumerated enabled repo skill; two model sessions read its entrypoint/references | Installed Python could not execute in this Windows workspace-write sandbox; helper success is not claimed for that CLI |
| Initial hosted CI, Python 3.10 | Ubuntu: 102 tests run, 100 passed, 2 Windows-only junction skips; Windows: failed on temporary-path fixture comparisons | Run [39975784159](https://github.com/Miqueiasdbezerra/db-agent-skills/actions/runs/39975784159); see the targeted correction below and current workflow results |

The repository suite passed all 17 tests locally (14 installer boundary/rollback tests and 3 license-integrity tests), with no skips. Across the three distinct local suites, 102 tests ran: 99 passed, 3 skipped, no failures/errors. The license tests reject missing or mismatched standalone terms, altered owner/terms and inconsistent catalog metadata, and accept matching approved terms with normal line-ending conversion.

The first hosted Windows run exposed a fixture portability issue: temporary paths could use Windows 8.3 spelling while the guarded helper returned the resolved spelling. The [targeted correction](https://github.com/Miqueiasdbezerra/db-agent-skills/commit/dc9f3ca72129b056ea122d67ac4e5bbaf82e4906) resolves the temporary fixture roots in the tests. It leaves the runtime filesystem guards unchanged. The initial run remains recorded as failed; check the [live workflow results](https://github.com/Miqueiasdbezerra/db-agent-skills/actions/workflows/validate.yml) for subsequent runs rather than inferring a pass from the correction.

The [subsequent hosted run](https://github.com/Miqueiasdbezerra/db-agent-skills/actions/runs/39976614858) passed all 73 skill tests on Windows Server 2025/Python 3.10.11, including the three actual symlink and two actual junction cases. It then exposed the same temporary-path spelling issue in one installer fixture. That fixture now also resolves its temporary root before installing metadata mocks. No runtime guard or assertion was weakened. This hosted Windows evidence is distinct from the three skips on the original local Windows machine.

## Reproduce without accounts or dependencies

From the repository root:

```powershell
python -B -m unittest discover -s skills/webops-secretary/tests -v
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s examples/local-demo -p test_server.py -v
python -B scripts/review_publication.py
```

Start the [local demo](../examples/local-demo/README.md) with a private state directory outside this checkout. Install a project-local skill into a separate Git test project with [the installer](../scripts/install_skill.py). Each actual host session must discover/load the skill, inspect the current interface or supported service, and invoke the real helper. File existence and a generic model summary are insufficient evidence.

Use distinct synthetic references per host. Keep journals and raw runtime traces private; do not record CSRF values, cookies, authentication responses or real personal data. The demo offers an independent synthetic state listing for reconciliation.

## Real-browser findings

The first Chrome form submission was rejected because auto-translation changed selector labels that the demo had incorrectly used as implicit values. No row was present after reloading the list. The demo was fixed to use stable explicit values, a Portuguese-label regression passed, and a new observed attempt succeeded.

A deliberately committed save then returned HTTP 503. The private journal remained unknown/paused. The tab was closed; a new tab and reopened journal reconciled the already-existing request before edit and upload. A controlled duplicate reference submission returned the existing row. Independent state inspection confirmed one record, one attachment and three effective operations for that reference.

An expanded Windows HTTP check exposed an intermittent connection reset when the demo rejected a 65537-byte body without consuming it. The demo now drains at most the fixed boundary-plus-one amount under an absolute ten-second deadline before rejection. Regression checks assert the exact rejection and unchanged stored state; repeated runs and the final suite passed without retrying or masking the failing request.

Claude completed its separately scoped service journey in fresh real CLI sessions. Exactly one record with version 2, Facilities category, one note and three effective operations remained. No production account or third-party administrative system was changed.

## Three symlink skips and alternatives

The original local Windows host does not grant ordinary symbolic-link creation to these tests. Its three real-link cases remain explicitly skipped. Two actual Windows junction checks pass locally; six portable tests inject symlink/reparse metadata and verify the refusal paths without requiring OS link-creation privilege. Those alternatives validate the logic but do not count as real symlink execution. In the initial hosted Ubuntu job, the actual symlink cases passed and two Windows-only junction cases were skipped. These are distinct platform results; Linux skips do not replace or erase the three local Windows skips.

## Remaining limits and release gates

- Claude's browser integration and implicit skill selection have not been validated. A tested HTTP adapter does not prove UI automation.
- Standalone Codex CLI needs a supported executable Python environment under normal host controls before helper compatibility can be declared for that sandbox. No control was bypassed to force a pass.
- Browser tools, service permissions and model runtimes are provided by the host. The skill is not an autonomous browser engine.
- SQLite is unencrypted, with inherited Windows ACLs; existing POSIX directory permissions need separate review. No cross-device sync or automatic retention is supplied.
- Credential/file/link checks are conservative heuristics, not complete prevention of personal-data disclosure or malicious concurrent filesystem changes.
- Local journaling cannot guarantee exactly-once remote effects. Use supported remote idempotency and reconcile uncertain results.
- MIT is applied to original files. The owner explicitly approved initial publication; new account operations and materially different publication actions still need applicable authority. See the [licensing record](LICENSE-PROPOSAL.md).

Detailed skill instructions and evidence distinctions: [host validation](../skills/webops-secretary/references/host-validation.md).
