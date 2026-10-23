# WebOps Secretary

**Version 1.0.0** · A reusable skill for authorized administrative web work in OpenAI Codex and Claude Code.

WebOps Secretary guides an agent through navigation, record changes, form filling, uploads, account organization, queries, and outcome verification. It combines current page inspection with private operational memory, durable action intent, and reconciliation after interruptions.

## What is included

- Tool-agnostic instructions for service connectors and browser tools available in the host agent.
- Safe autonomy inside the user's scope, with explicit authorization for financial, destructive, public, and sensitive actions.
- Private SQLite task journals, action history, reusable procedures, confidence levels, and validation dates.
- Recovery that distinguishes confirmed, pending, failed, and uncertain operations to avoid blind duplicate submissions.
- Fictional examples, reusable private templates, reproducible local tests, and a guarded package builder.

The skill is instructions plus local helpers, not a standalone browser agent. It does not bundle a browser, hosting service, login bypass, model runtime, or external dependencies. It never authorizes CAPTCHA, authentication, MFA, or permission bypasses. Operational memory is experience retrieval and procedure maintenance, not model retraining.

## Requirements

- OpenAI Codex or Claude Code with skill support.
- Authorized access to the target website or system.
- A capable browser or connected-service tool supplied by the host for real web actions.
- Python 3.10+ for the memory helper, local tests, and packaging. All bundled Python code uses the standard library; no `pip install` is needed.

Memory is not captured automatically. The agent must invoke the helper and independently inspect real results. The host's permissions, sandbox, and organizational policies continue to apply.

## Observed host compatibility

Controlled validation on 2026-10-23 confirmed real skill loading in Claude Code and Codex CLI, plus a real Chrome form/edit/upload/recovery journey in the current Codex host. The standalone Codex CLI discovered and read the skill but could not execute the installed Python interpreter inside this machine's Windows sandbox. Claude Code's local memory and HTTP service workflow were exercised; its browser integration was not tested. See [host validation](references/host-validation.md) for the exact evidence and remaining limits. Do not interpret a shared file format as a guarantee that every host supplies browser or shell access.

## Install locally

Copy the complete `webops-secretary` folder, including its supporting files, into one supported discovery location. The source folder can stay in the `db-agent-skills/skills/` library; installing a copy is a separate optional step.

| Host and scope | Destination |
| --- | --- |
| Codex, current repository | `<repository>/.agents/skills/webops-secretary/` |
| Codex, user | `~/.agents/skills/webops-secretary/` |
| Claude Code, current repository | `<repository>/.claude/skills/webops-secretary/` |
| Claude Code, user | `~/.claude/skills/webops-secretary/` |

These discovery locations were checked against the official [Codex skills documentation](https://learn.chatgpt.com/docs/build-skills) and [Claude Code skills documentation](https://code.claude.com/docs/en/skills) on 2026-10-23. `~` denotes the current user's home directory. Local user skills do not automatically install into cloud sessions.

PowerShell example, run from the library root, choosing **one** host destination:

```powershell
$skillSource = (Resolve-Path -LiteralPath './skills/webops-secretary').Path
# Codex user installation:
$skillTarget = Join-Path $HOME '.agents/skills/webops-secretary'
# For Claude Code instead, replace the previous assignment with:
# $skillTarget = Join-Path $HOME '.claude/skills/webops-secretary'

if (-not (Test-Path -LiteralPath (Join-Path $skillSource 'SKILL.md') -PathType Leaf)) {
    throw 'Source SKILL.md is missing'
}
if (Test-Path -LiteralPath $skillTarget) {
    throw 'Destination already exists; review it before updating'
}
New-Item -ItemType Directory -Path (Split-Path -Parent $skillTarget) -Force | Out-Null
Copy-Item -LiteralPath $skillSource -Destination $skillTarget -Recurse
```

For repository scope, choose the corresponding path inside the intended repository as `$skillTarget`. Existing installations should be reviewed and replaced deliberately; the example refuses to overwrite them. No permission-disabling flags, hooks, or broad tool allowlists are required.

Invoke it in Codex with `$webops-secretary` or in Claude Code with `/webops-secretary`, followed by the task. It may also be selected automatically when relevant. Refresh/restart the host if it has not detected the new skill.

Example request:

> Use WebOps Secretary to update the category of fictional request DEMO-1042 in my authorized training workspace, attach the supplied fictional note, and verify the saved result. Do not publish or notify anyone. Preserve a private checkpoint if interrupted.

See [examples/example-task.md](examples/example-task.md) for a complete fictional workflow.

## Private memory setup

The default private root is `%LOCALAPPDATA%\WebOpsSecretary\private` on Windows or `~/.local/state/webops-secretary` on other systems. Override with `WEBOPS_MEMORY_HOME` or `--root` only when the chosen location is genuinely private and outside all repositories, publishable workspaces, and skill installations.

From the skill folder:

```powershell
$publicRoot = (Resolve-Path -LiteralPath '../..').Path
python -B scripts/memory.py --public-root $publicRoot init
python -B scripts/memory.py --public-root $publicRoot recall --scope demo --origin https://portal.example.test
```

The `../..` example assumes the library layout `<public-root>/skills/webops-secretary`. Set `$publicRoot` to the real canonical checkout/workspace root when using a different layout or an installed copy. Pass it on every call; repeat `--public-root` for other publishable roots. Never set `WEBOPS_MEMORY_HOME` to this skill directory or copy filled templates into it.

Read [references/memory-system.md](references/memory-system.md) for task creation, intent before mutation, outcome reconciliation, playbook updates, and CLI status semantics. Storage is local and unencrypted. Windows inherits the account's filesystem permissions; additional Windows ACL hardening is not bundled. Text screening is heuristic and cannot replace data minimization or manual review.

## Local validation

Run from the skill folder:

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/package_skill.py check
```

The automated suite exercises simulated navigation, forms, uploads, error recovery, private persistence and recall, interruption recovery, duplicate prevention, and sensitive-data/package guards. It uses fictional local fixtures and temporary storage, without contacting a live website or installing a browser. `-B` prevents Python bytecode artifacts.

These tests validate the local helpers and simulator, not a model's compliance or a real browser integration. The shared `SKILL.md` layout is designed for both hosts; successful local tests do not establish a Claude Code runtime test. Use [tests/MANUAL-AGENT-EVAL.md](tests/MANUAL-AGENT-EVAL.md) for real-agent evaluation in an authorized isolated environment. See [VALIDATION.md](VALIDATION.md) for the actual checks run on this build and their limits.

## Build a distribution archive

Keep ZIP output outside the skill source directory:

```powershell
python -B scripts/package_skill.py check
python -B scripts/package_skill.py build --output ../../webops-secretary-skill.zip
```

The builder checks the source and uses an explicit public-file manifest. Review source, staged Git changes, and archive members before any future publication. Pattern checks cannot recognize every personal detail, and `.gitignore` does not remove tracked content.

## Files

```text
webops-secretary/
  LICENSE
  SKILL.md
  README.md
  VALIDATION.md
  .gitignore
  templates/
    task-journal.md
    playbook.md
  references/
    security.md
    browser-workflows.md
    memory-system.md
  scripts/
    memory.py
    package_skill.py
  examples/
    example-task.md
    simulated_browser.py
  tests/
    MANUAL-AGENT-EVAL.md
    ... local test modules and fictional fixtures
```

## Publication and licensing

This skill's source is published in [db-agent-skills](https://github.com/Miqueiasdbezerra/db-agent-skills), with the owner's approval on 2026-10-23. Installation instructions do not themselves perform a global installation or publish user data. All supplied examples are fictional. Filled journals, real procedures, screenshots, downloads, and databases stay private and outside the repository.

Original project material is licensed under [MIT](LICENSE). Copyright (c) 2026 Miqueias Durans Bezerra. Third-party components, if added, retain their own notices and terms. Applying this license does not authorize a GitHub push or public profile change.
