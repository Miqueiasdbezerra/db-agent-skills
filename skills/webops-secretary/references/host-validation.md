# Observed host validation — 2026-10-23

This is a bounded compatibility record for version 1.0.0 before publication. Browser capabilities, permissions and runtime access are supplied by the host; this skill does not install or unlock them.

| Environment | Observed evidence | Limit |
|---|---|---|
| Codex CLI 0.162.0-alpha.17.2 | Official local app-server `skills/list` returned this repo-scoped skill enabled. Two actual model sessions read its entrypoint and references. | The Windows workspace-write sandbox could not invoke Python through PATH or an explicitly supplied existing interpreter. No private-memory success is claimed for that CLI sandbox. |
| Current Codex host + real Chrome | Read the skill; executed information lookup, form creation, edit, real text upload, deliberate committed-save failure and reconciliation in a new tab; private SQLite journal and playbook updated. | This host has a documented browser tool and executable Python. Its access is not evidence of standalone CLI capability. |
| Claude Code CLI 2.1.302 | `Skill` tool returned success; actual helper calls persisted and recovered memory in fresh CLI sessions. Real loopback HTTP form/create/edit/upload calls were independently reconciled. | A narrow service adapter was used. No Claude browser integration or automatic implicit selection was validated. |

All mutations targeted a loopback-only demonstration service with synthetic data. Exactly one record per tested reference and one attachment per record remained after reconciliation. Test-only server idempotency strengthens the fixture, not arbitrary remote systems.

## What changed after real use

- A translated demo selector submitted translated labels because it lacked explicit option values. The demo was corrected to use stable values; a regression test and a real translated-browser journey passed. The rejected attempt was recorded as failed only after confirming no record existed.
- A deliberately committed save returned HTTP 503. The journal preserved an unknown outcome; the browser tab was closed. A new tab and reopened memory reconciled the existing record before edit and upload. No blind resubmission occurred.
- Narrow Claude command approval initially did not match the emitted command. A reviewable invocation using the exact scoped helper prefix succeeded with normal permissions. This does not justify broad shell approval.
- Codex CLI discovery succeeded but runtime execution remained restricted even with the installed interpreter's absolute path. No bypass or component installation was attempted.

## Symbolic links and portable alternatives

Three tests require OS privilege to create real symbolic links. They remain explicitly skipped on this Windows installation. Two actual Windows junction tests exercise reparse-point rejection. Six additional portable tests inject symlink/reparse metadata and check refusal of real helper/packaging flows without relying on link-creation privilege. These alternatives test guard behavior; they do not turn an unavailable real-symlink test into a pass. The prepared Linux CI workflow is configured to run the actual symlink cases when the runner permits them; no hosted CI execution is claimed.

Memory remains local and unencrypted, with inherited Windows ACLs. Input screening is heuristic. Filesystem link checks do not provide race-proof isolation against a malicious concurrent writer. Host sandboxing and account permissions remain necessary.

## Evidence and reproducibility

Raw CLI traces, task IDs, private journals, machine-specific harnesses and screenshot evidence are retained privately outside the public package. The public repository's validation guide describes a repeatable local demo without embedding them. Tests of helpers, HTTP service, model invocation and browser journeys are distinct evidence categories; none is a substitute for another.

Official installation and runtime references: [Codex skills](https://learn.chatgpt.com/docs/build-skills), [Codex app-server](https://learn.chatgpt.com/docs/app-server), [Claude skills](https://code.claude.com/docs/en/skills), [Claude CLI execution](https://code.claude.com/docs/en/headless).
