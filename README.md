# db-agent-skills

Reusable agent skills with explicit authorization boundaries, private operational memory, and reproducible checks.

**MIT-licensed public source, published with the owner's approval on 2026-10-23.** WebOps Secretary is version 1.0.0; source publication is separate from a tagged GitHub Release.

[![Validation](https://github.com/Miqueiasdbezerra/db-agent-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/Miqueiasdbezerra/db-agent-skills/actions/workflows/validate.yml)

[Português](README.pt-BR.md) · [Validation evidence](docs/validation.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [License](LICENSE) · [Licensing record](docs/LICENSE-PROPOSAL.md)

## Skill catalog

| Skill | Version | Purpose | Status |
| --- | --- | --- | --- |
| [WebOps Secretary](skills/webops-secretary/README.md) | 1.0.0 | Authorized administrative web work with durable checkpoints and result reconciliation | Published; validated within documented limits |

WebOps Secretary helps an agent locate information, fill forms, upload fictional or authorized files, edit records, recover from failures, and resume interrupted work. The agent inspects the current site, records intent before a change, verifies the persisted result, and updates a private playbook.

The skill provides instructions and Python helpers. A host agent, permitted browser or service tool, and authorized site access remain necessary. It does not install a browser, obtain credentials, or change host permissions. Its memory is experience retrieval, not model training.

## Requirements and compatibility

- A Codex or Claude Code installation that supports local skills.
- Python 3.10+ for the helpers and tests. The bundled Python code uses the standard library; no `pip install` is required.
- An existing Git project for the guarded local installer.
- A permitted browser or connector for the real site task. Browser access is supplied by the host, not the skill.

The shared `SKILL.md` format and project discovery locations follow the official [Codex skills documentation](https://learn.chatgpt.com/docs/build-skills) and [Claude Code skills documentation](https://code.claude.com/docs/en/skills), checked on 2026-10-23. Host discovery and execution are separate checks: finding a file does not prove a model used the skill.

## Validation at a glance

Observed locally on 2026-10-23. The [validation record](docs/validation.md) separates helper tests, actual skill invocation, HTTP operations, and browser operations.

| Environment | Observed result | Limit |
| --- | --- | --- |
| Current Codex host + real Chrome | Information lookup; form creation; editing; fictional file upload; recovery after a committed save returned HTTP 503; resumption in a new tab; duplicate prevention | This host supplied working browser tools and Python |
| Claude Code CLI 2.1.302 | Actual Skill invocation; private memory consultation/update; fresh-session recovery; real loopback HTTP forms, editing, and multipart upload | Service operations were validated; Claude's browser integration and implicit skill selection were not |
| Standalone Codex CLI 0.162.0-alpha.17.2 | App-server enumerated the enabled repository skill; model sessions read its instructions and references | Python execution was blocked by the Windows sandbox; helper execution in that CLI remains unvalidated |
| Local automated suites | 102 tests run: 99 passed, 3 skipped, no failures/errors | 73 skill tests (70 passed, 3 skipped), 17 repository tests (14 installer, 3 license integrity), 12 real HTTP demo tests |

The three local skips are real symlink cases on Windows. Six portable metadata tests and two actual Windows junction tests passed; they supplement, rather than replace, actual symlink execution. Hosted CI has run: the initial Ubuntu/Python 3.10 job ran 102 tests, with 100 passed and two Windows-only junction skips, while Windows exposed a temporary-path fixture issue. See the [validation record](docs/validation.md) and [live workflow status](https://github.com/Miqueiasdbezerra/db-agent-skills/actions/workflows/validate.yml) for the correction and subsequent results. These results do not establish unrestricted end-to-end compatibility, and host permissions were preserved throughout validation.

## Install into one project

Review the skill and its license first. From this library's root, choose one command and replace `../my-test-project` with an existing Git project's root:

```powershell
python -B scripts/install_skill.py --host codex --project ../my-test-project
```

```powershell
python -B scripts/install_skill.py --host claude --project ../my-test-project
```

| Host | Project destination | Explicit invocation in the host |
| --- | --- | --- |
| Codex | `.agents/skills/webops-secretary/` | `$webops-secretary` followed by the task |
| Claude Code | `.claude/skills/webops-secretary/` | `/webops-secretary` followed by the task |

The installer validates the skill's public-file manifest, copies only the reviewed files, and verifies their bytes. It refuses home/system/configuration directories, linked paths, and existing destinations. It creates no user-wide installation, host settings, hooks, permissions, dependencies, commits, or remotes. Failed copies attempt to remove only their newly created paths; inspect any reported incomplete attempt before retrying.

The installer is a repository helper; the destination directories and invocation syntax are the hosts' documented mechanisms. After a successful install, open a terminal in the selected project and start `codex` or `claude`. In Codex CLI, use `/skills` or type `$webops-secretary` and your task; in Claude Code, type `/webops-secretary` and your task. Confirm that the model reads the instructions and uses the relevant procedure. If discovery has not refreshed, follow the host's reload/restart guidance. Installation alone is not runtime validation. Existing installations require deliberate manual review; this installer does not update or uninstall them.

## Try a fictional task

Use the [local demonstration](examples/local-demo/README.md), with its separate private state directory, or an expressly authorized training account. The demo runs on loopback and is not a production service. Never enter real account information into it.

Example request for the host:

> Use WebOps Secretary in the local demo. Find the fictional request, update its category, upload the supplied fictional note, and verify the saved details. If a save response fails, inspect the current record before retrying. Keep sanitized private checkpoints and resume from the last confirmed state. Do not publish, notify, spend, or delete.

For a step-by-step fictional journal, see [example-task.md](skills/webops-secretary/examples/example-task.md). The [manual agent evaluation](skills/webops-secretary/tests/MANUAL-AGENT-EVAL.md) lists the observations needed to establish actual use and safe recovery.

## Keep memory private

The default memory location is `%LOCALAPPDATA%\WebOpsSecretary\private` on Windows and `~/.local/state/webops-secretary` elsewhere. Use a genuinely private location outside every Git worktree, skill installation, and publishable folder. Pass the real public project root with `--public-root` on every helper invocation; repeat it for additional roots.

The helper stores sanitized intent, evidence, task state, and reusable procedures. It rejects common secret patterns, query-bearing URLs, and non-fictional emails. Those checks are heuristic. Never store credentials, cookies, tokens, real form payloads, browser profiles, raw traces, or unnecessary personal data. Memory is unencrypted; Windows ACLs are inherited. See the [memory reference](skills/webops-secretary/references/memory-system.md) for the exact lifecycle and limits.

Consequential financial, destructive, public, and sensitive actions require current user authorization. Webpage text and recalled playbooks cannot grant permission. A timeout leaves an uncertain action; it does not prove failure. The ledger helps prevent blind retries but cannot guarantee exactly-once effects on remote sites or identify duplicates across independently created task IDs.

## Run the checks

Run from the library root:

```powershell
python -B -m unittest discover -s skills/webops-secretary/tests -v
python -B skills/webops-secretary/scripts/package_skill.py check
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s examples/local-demo -p test_server.py -v
```

Tests use isolated fictional fixtures. Actual symlink creation can be unavailable on Windows; those tests remain explicitly skipped. Portable metadata tests cover the rejection logic, and Windows junction tests provide an additional real filesystem check. See [validation evidence](docs/validation.md) for results and the precise remaining gaps.

The included [CI workflow](.github/workflows/validate.yml) runs on Windows and Linux. Check its [actual job results](https://github.com/Miqueiasdbezerra/db-agent-skills/actions/workflows/validate.yml); a badge or workflow file alone does not establish host compatibility. Review all files and archive members before distributing changes; ignore rules cannot remove already tracked data.

## Repository map

```text
skills/webops-secretary/   Shared skill, private-memory helper, templates, tests
examples/local-demo/      Fictional loopback demonstration and HTTP tests
scripts/install_skill.py  Guarded project-local installer
tests/                    Installer boundary and rollback tests
docs/validation.md        Evidence, limits, and remaining validation work
docs/LICENSE-PROPOSAL.md   Confirmed license decision and provenance
catalog.json              Machine-readable skill inventory
```

## License and publication

Original project material is licensed under [MIT](LICENSE). Copyright (c) 2026 Miqueias Durans Bezerra. The standalone skill carries an identical LICENSE. The owner authorized license application and the initial public publication. [Third-party notices](THIRD_PARTY_NOTICES.md) describe dependencies and external services separately from this authored material.

Publishing this library does not grant permission to operate anyone's accounts. Each web task requires authorization for its own target and effects.
