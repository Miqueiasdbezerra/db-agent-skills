# First publication procedure — historical checklist

The owner explicitly approved the initial public publication, completed on 2026-10-23. The initial library commit is [abc35f5](https://github.com/Miqueiasdbezerra/db-agent-skills/commit/abc35f516c4c5b11f584792b955e4d00c876dc63); the separately approved profile update is [dcc0b61](https://github.com/Miqueiasdbezerra/MiqueiasdBezerra/commit/dcc0b61). No existing repository visibility was changed.

The commands below retain the reviewed first-publication procedure as a historical checklist, not a verbatim execution transcript or a procedure to rerun on the now-published repository. They assume the original unpublished local state; the repository and remotes now exist. Nothing in this document grants authority for a new publication or account operation.

## Approval gates

1. Completed locally: the owner confirmed `Copyright (c) 2026 Miqueias Durans Bezerra` and authorized MIT for original project material. The component audit found no conflicting bundled license; it relies on the owner's authorship statement rather than independent legal title verification.
2. Completed locally: apply the confirmed MIT to root `LICENSE`, `skills/webops-secretary/LICENSE` and the canonical skill source; update both allowlists, documentation and catalog; regenerate licensed archives and hashes. The delivery manifest identifies the resulting bytes.
3. Completed: the owner reviewed the licensed package and explicitly authorized creating the public library, pushing the approved files and replacing the profile README. License authorization alone was not treated as authority for those public actions.
4. Completed: verify GitHub authentication, commit attribution and repository name immediately before the approved action. The intended account was used; no existing repository visibility was changed.

The GitHub CLI (`gh`) was initially unavailable. The official CLI and normal browser/device authentication were subsequently used; the user completed GitHub authorization. Do not put a token in a command, file or log.

The reviewed normal interactive authentication command was:

```powershell
gh auth login --hostname github.com --git-protocol https --web
```

The user completes any browser authorization or MFA. Authentication setup is not permission to create the repository or push files.

## Local preflight

```powershell
$ErrorActionPreference = 'Stop'
function Check-Exit {
    if ($LASTEXITCODE -ne 0) { throw 'Previous command failed; stop publication' }
}

Get-Command git, gh, python -ErrorAction Stop
gh auth status --active --hostname github.com
Check-Exit
$account = gh api user --jq '{id: .id, login: .login}' | ConvertFrom-Json
Check-Exit
if ($account.login -cne 'Miqueiasdbezerra') { throw 'Unexpected GitHub account' }

python -B scripts/review_publication.py
Check-Exit
python -B -m unittest discover -s skills/webops-secretary/tests
Check-Exit
python -B -m unittest discover -s tests
Check-Exit
python -B -m unittest discover -s examples/local-demo -p test_server.py
Check-Exit
python -B examples/local-demo/reproduce.py
Check-Exit
if (-not (Test-Path -LiteralPath LICENSE -PathType Leaf)) { throw 'Approved MIT license is not applied' }
if (-not (Test-Path -LiteralPath skills/webops-secretary/LICENSE -PathType Leaf)) { throw 'Standalone skill license is missing' }

$existingRemotes = @(git remote)
Check-Exit
if ($existingRemotes.Count -ne 0) { throw 'Review existing remotes before first publication' }
if ((git branch --show-current) -ne 'main') { throw 'Unexpected local branch' }
Check-Exit
$approvedFiles = @((Get-Content -LiteralPath release-files.json -Raw | ConvertFrom-Json).files)
if ($approvedFiles -notcontains 'LICENSE' -or $approvedFiles -notcontains 'skills/webops-secretary/LICENSE') {
    throw 'Publication allowlist does not include the approved licenses'
}
git --literal-pathspecs add -- $approvedFiles
Check-Exit
$stagedFiles = @(git diff --cached --name-only)
Check-Exit
if (@(Compare-Object ($approvedFiles | Sort-Object) ($stagedFiles | Sort-Object)).Count -ne 0) {
    throw 'Staged paths differ from the reviewed allowlist'
}
git diff --cached --check
Check-Exit
git diff --cached --stat
Check-Exit
```

The licensed delivery manifest contains the current per-file and ZIP SHA-256 values. Compare actual source/archive bytes and the profile against that approved snapshot before proceeding. Never reuse a pre-license review hash as approval for modified files. Git may normalize line endings according to `.gitattributes`; approval of the delivered bytes must precede staging, and any other content change requires renewed review.

## Repository creation and push — only after explicit approval

The account's ID/login form a GitHub `noreply` address so a private address is not placed in commit metadata. Confirm that attribution before committing; these options apply to this command only.

```powershell
$commitEmail = ('{0}+{1}' -f $account.id, $account.login) + [char]64 + 'users.noreply.github.com'
git -c user.name='Miqueias Durans Bezerra' -c user.email="$commitEmail" commit -m 'Release WebOps Secretary 1.0.0'
Check-Exit
gh repo create Miqueiasdbezerra/db-agent-skills --public --source . --remote origin --description 'Reusable agent skills for verified web operations and private operational memory'
Check-Exit
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push --set-upstream origin main
Check-Exit
gh repo view Miqueiasdbezerra/db-agent-skills --json nameWithOwner,visibility,url
Check-Exit
git ls-remote origin refs/heads/main
Check-Exit
```

`gh repo create` fails if the name is unavailable; do not fall back to modifying an existing repository. The command-specific credential helper uses the already authenticated CLI without changing the global Git configuration or printing a token. The initial publication created the new library remote and pushed its approved initial commit.

## Profile README — separate approved public change

The approved profile contained the intended library and validation URLs. Those URLs now point to the public library. The following retained checklist required verifying those destinations and the exact approved profile bytes before copying the preview:

```powershell
gh repo clone Miqueiasdbezerra/MiqueiasdBezerra ../profile-publication
Check-Exit
if ((git -C ../profile-publication branch --show-current) -ne 'main') { throw 'Unexpected profile branch' }
Check-Exit
Copy-Item -LiteralPath ../drafts/PROFILE-README.md -Destination ../profile-publication/README.md
git -C ../profile-publication diff -- README.md
Check-Exit
git -C ../profile-publication --literal-pathspecs add -- README.md
Check-Exit
git -C ../profile-publication diff --cached --check
Check-Exit
git -C ../profile-publication -c user.name='Miqueias Durans Bezerra' -c user.email="$commitEmail" commit -m 'Present verified agent workflow project'
Check-Exit
git -C ../profile-publication -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin main
Check-Exit
```

An existing clone destination, unexpected branch, concurrent remote change or failed push requires review; no forced push or unrelated file change is included.

## Official references

- [GitHub CLI repository creation](https://cli.github.com/manual/gh_repo_create).
- [Authentication status](https://cli.github.com/manual/gh_auth_status).
- [Commit email and privacy](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address).
- [Confirmed MIT decision and provenance](LICENSE-PROPOSAL.md).
