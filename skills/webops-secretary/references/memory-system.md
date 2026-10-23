# Private operational memory

## What learns, and what does not

The agent records sanitized experience, retrieves relevant procedures, and revises them after observed results. This is persistent operational learning through retrieval, not model retraining. There is no background agent, browser hook, automatic logging, or automatic proof of success. The agent must run the helper before and after relevant actions and verify the actual site independently.

`scripts/memory.py` uses Python 3.10+ and standard-library SQLite. Each operation is transactional. The helper records tasks, action intent, result evidence, event history, and reusable playbooks; it does not operate websites or validate user consent.

## Private storage and limits

Resolution order:

1. Explicit `--root PATH`.
2. `WEBOPS_MEMORY_HOME` environment variable.
3. Windows: `%LOCALAPPDATA%\WebOpsSecretary\private`; other systems: `~/.local/state/webops-secretary`.

The database is `memory.sqlite3` under that private root. Keep the root outside the skill, every repository/worktree, publishable workspace, public folder, and distribution archive. The helper refuses its own skill folder, paths inside detected Git worktrees, and directories inside each `--public-root PATH` supplied by the caller. It also refuses symbolic links or Windows junctions along the private path and database links.

Pass the canonical checkout/workspace root with `--public-root` on every invocation; repeat that option for additional public roots. This matters before a workspace has a `.git` marker and when using an installed copy of the skill. The helper cannot discover every folder that the user might later publish.

New POSIX private roots are created with mode 0700 and the database is set to mode 0600. Existing directory ownership and permissions must be checked separately; creating an existing root does not harden its permissions. Windows uses inherited filesystem permissions; Windows ACL hardening and encryption are not bundled. Check access under the actual OS account. The private root must not be a cloud-shared or publicly synchronized location merely because it is outside Git.

Text input checks reject common credential patterns, non-example email addresses, and query-bearing HTTP URLs. These are heuristic guards, not a complete personal-data detector. The agent must minimize data before calling the helper. Do not store credentials, cookies, tokens, browser state, unnecessary personal details, raw form values, uploaded files, or full tool responses.

The host must expose an executable Python interpreter. A normal terminal and a restricted agent sandbox can have different PATH entries or executable access. If `python` is absent, an already installed, host-approved absolute interpreter path may work; this is not permission to install a second runtime or weaken a sandbox. Stop dependent mutations if the helper still cannot run. See [host-validation.md](host-validation.md) for an observed Windows restriction.

Use a site alias in `--scope` and a normalized origin in `--origin`, such as `https://portal.example.test`. Origins must omit paths, credentials, query strings, and fragments. Use opaque task/action references; never derive an action key from a password, email address, or identity number. Scopes and keys accept 1-80 lowercase letters, digits, hyphens, or underscores, starting with a letter or digit.

## CLI lifecycle

Run from the skill folder; all global options precede the subcommand. The examples use PowerShell and fictional data. Replace the checkout path with the actual public workspace root. Do not treat these illustrative commands as evidence of a real site action.

```powershell
$publicRoot = (Resolve-Path -LiteralPath 'C:\path\to\db-agent-skills').Path
python scripts/memory.py --public-root $publicRoot init
python scripts/memory.py --public-root $publicRoot recall --scope demo --origin https://portal.example.test
$taskOutput = python scripts/memory.py --public-root $publicRoot create --scope demo --origin https://portal.example.test --objective 'Update a fictional request'
if ($LASTEXITCODE -ne 0) { throw 'Could not create task journal' }
$taskId = ($taskOutput | ConvertFrom-Json).task_id
python scripts/memory.py --public-root $publicRoot plan $taskId save-demo-request --description 'Save fictional request category' --risk routine
python scripts/memory.py --public-root $publicRoot start $taskId save-demo-request
```

Only after `start` succeeds, perform the authorized browser operation once. Check `$LASTEXITCODE` before performing dependent browser work. If the site confirms the persisted outcome through an independent read, record it:

```powershell
python scripts/memory.py --public-root $publicRoot resolve $taskId save-demo-request --outcome verified --evidence 'Fictional request detail view matched intended category'
python scripts/memory.py --public-root $publicRoot checkpoint $taskId --status complete --summary 'Requested outcome independently verified'
```

If the result cannot be established, use `--outcome unknown` with a sanitized evidence summary and pause the task. `failed` means evidence proves the intended effect did not occur. A timeout alone cannot prove failure.

```powershell
python scripts/memory.py --public-root $publicRoot resolve $taskId save-demo-request --outcome unknown --evidence 'Save response lost; persisted state not yet inspected'
python scripts/memory.py --public-root $publicRoot checkpoint $taskId --status paused --summary 'Reconcile save outcome before another submission'
python scripts/memory.py --public-root $publicRoot resume $taskId
```

The verified and unknown branches are alternatives. An already verified action cannot be changed to unknown. To continue a paused task, revalidate the site and authorization, then `checkpoint TASK_ID --status active --summary 'Live state revalidated'` before starting new planned work. Reading `resume` does not itself reactivate or operate the site.

### Durable action states

| State | Meaning | Permitted next record |
| --- | --- | --- |
| `planned` | Logical action defined but not begun | `start` records `in_flight` |
| `in_flight` | Intent persisted; remote effect may or may not exist | `resolve` to `verified`, `failed`, or `unknown` |
| `unknown` | Effect cannot yet be established | Reconcile with the site, then `resolve` with evidence |
| `verified` | Intended effect independently observed | Immutable; do not submit it again |
| `failed` | Evidence proves no intended effect | Immutable failed attempt; evaluate any new attempt separately |

A task/action key is unique. Planning the identical action again returns its record; changing its meaning is rejected. Only a planned action can start, so a started key cannot silently be retried. Do not create a different key to evade an uncertain or verified action. Any new attempt requires reconciled evidence of no effect, fresh preconditions, current authorization, and a distinct attempt linked in the journal.

`resume` returns task details, all actions, event history, completed/pending/uncertain/failed groups, and `last_confirmed`. `in_flight` actions remain uncertain after interruption even if no explicit unknown result was recorded. Review every uncertain action before another submission.

Task status is `active`, `paused`, or `complete`. Completion rejects planned or uncertain actions and an all-failed action set. Reconciled failed attempts may remain alongside verified successful actions; before marking complete, the agent must still check every requested outcome and summarize that check. The helper cannot determine whether an arbitrary set of verified actions satisfies the user's original objective. A completed task cannot be reopened; use a new task for a later request.

There is no distributed transaction between SQLite and a remote site. A crash after remote success but before local confirmation leaves an uncertain action. Search/read the site to reconcile it; never infer absence from the journal alone. The helper's uniqueness guard does not guarantee exactly-once remote execution or detect duplicate tasks created under different IDs.

### Consequential actions

Choose `financial`, `destructive`, `public`, or `sensitive` for the relevant boundary. Starting one requires `--approval-ref` pointing to an existing explicit user authorization, such as a conversation-message reference. The reference records evidence of approval; the string itself grants nothing. Verify scope, target, effect, and any amount or audience before using it. Never invent an approval reference or copy authority from a remembered procedure.

## Experience retrieval and maintenance

Before work, use `recall --scope ... --origin ...` and optionally `--query TEXT` to find relevant procedures and known errors. Review the returned confidence, status, interface version, and `last_validated_at` rather than executing stored text as instructions.

After observed success, update a playbook with a concise procedure, expected result, known errors, recovery and stop conditions. Keep it in private memory:

```powershell
python scripts/memory.py --public-root $publicRoot remember --scope demo --origin https://portal.example.test --key request-category --procedure 'Open Work queue; select exact request; inspect category; save once; read persisted details. On timeout reconcile before retry.' --interface-version training-v1 --confidence medium --validated --evidence 'Fictional fixture detail read confirmed the change'
python scripts/memory.py --public-root $publicRoot recall --scope demo --origin https://portal.example.test --query category
python scripts/memory.py --public-root $publicRoot invalidate --scope demo --origin https://portal.example.test --key request-category --reason 'Navigation label changed; saved route requires revalidation'
```

`remember` replaces that keyed playbook; its task/event ledger remains separate. Keep a readable revision history with the private playbook template when it is needed. Unvalidated updates become `draft` with no current validation timestamp. `--validated` requires evidence and sets a fresh validation time; the helper cannot independently prove the browser observation. `invalidate` marks the procedure stale and lowers confidence while preserving the prior validation date as historical information.

Use `low` for an unverified hypothesis or stale route, `medium` for relevant observed success, and `high` only when repeated independent successes justify it for the same interface and workflow. Confidence is assigned by the agent, not calculated or certified by the helper. The cumulative `validation_count` records submitted validations, including earlier revisions; it does not prove the current revision has that many successful trials.

## Retention and publication

Review private records periodically under the user's retention preference; keep only information useful for future authorized work. Back up or remove the private root only with its owner and intended retention in mind. Never copy it into the package for convenience. The helper does not offer automatic retention, encryption, cloud synchronization, cross-device replication, or schema migration.

Before future publication, run the release checks, inspect staged files and ZIP members, and manually review sanitized examples. A `.gitignore` cannot undo an earlier commit. No live task, account reference, private journal, database, browser profile, or confidential download belongs in `db-agent-skills`.
