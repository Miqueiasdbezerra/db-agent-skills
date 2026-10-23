# First publication plan — commands for review, not execution

These commands describe the owner's intended publication after approval. Nothing in this document authorizes execution. Run the repository commands from the root of `db-agent-skills`; keep the separate reviewed profile at `../drafts/PROFILE-README.md`.

## Approval gates

1. Completed locally: the owner confirmed `Copyright (c) 2026 Miqueias Durans Bezerra` and authorized MIT for original project material. The component audit found no conflicting bundled license; it relies on the owner's authorship statement rather than independent legal title verification.
2. Completed locally: apply the confirmed MIT to root `LICENSE`, `skills/webops-secretary/LICENSE` and the canonical skill source; update both allowlists, documentation and catalog; regenerate licensed archives and hashes. The delivery manifest identifies the resulting bytes.
3. Pending: review those licensed bytes and hashes and obtain explicit approval for creating the public repository, pushing those files and replacing the profile README. License authorization does not authorize these public actions.
4. Verify GitHub authentication, commit attribution and repository name immediately before the approved action. If anything differs from the approved snapshot or account, stop and review it. No visibility change to an existing repository is planned.

The GitHub CLI (`gh`) was not available during preparation. It must be installed from its official distribution and authenticated through the normal browser/device flow before the following plan can run. This prerequisite has not been performed. Do not put a token in a command, file or log.

After that separately reviewed installation, normal interactive authentication would use:

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

`gh repo create` fails if the name is unavailable; do not fall back to modifying an existing repository. The command-specific credential helper uses the already authenticated CLI without changing the global Git configuration or printing a token. Local draft preparation has made no commit and created no remote.

## Profile README — separate approved public change

The reviewed profile already contains the intended library and validation URLs. They are prospective links in a local preview, not evidence that the repository is public. Only after those URLs exist and the exact profile bytes are approved, copy that unchanged preview:

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
