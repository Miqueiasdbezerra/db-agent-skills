# Controlled real-browser demo fixture

This dependency-free fixture supports reproducible WebOps Secretary validation
against a real HTTP site, with fictional data and no external account. It is not
a production application. Python 3.10 or newer is required.

## Start

For a complete repeatable service demonstration, run from the repository root:

```powershell
python -B examples/local-demo/reproduce.py
```

The command creates temporary private state outside the checkout, starts a loopback-only server, records an uncertain committed save, restarts the server/client/memory, reconciles the record, edits it and uploads a fictional note. It checks stale-form refusal, duplicate prevention, the attachment digest and recalled procedures, then closes the server and removes temporary state. No accounts or Python packages are required. It exercises real HTTP and the memory helper; it is not a browser or model-runtime test.

Expected deterministic output, shown formatted for readability:

```json
{
  "category": "Facilities",
  "effective_operations": 3,
  "memory_restored": true,
  "note_count": 1,
  "playbook_recalled": true,
  "reconciled_after_failure": true,
  "record_count": 1,
  "reference": "DEMO-REPRO-01",
  "stale_form_rejected": true,
  "success": true,
  "upload_digest_verified": true,
  "version": 2
}
```

For an interactive browser journey, start the fixture manually instead:

From this directory:

```powershell
python server.py --port 8766 --state "$env:LOCALAPPDATA\WebOpsSecretary\phase2-demo"
```

Open `http://127.0.0.1:8766/` in a real browser. Only the loopback interface is
bound. Stop the process after the controlled validation. The default state path
is `%LOCALAPPDATA%\WebOpsSecretary\phase2-demo` on Windows and
`~/.local/state/WebOpsSecretary/phase2-demo` where LOCALAPPDATA is unavailable.
State paths inside this repository are rejected. Choose a private location outside any other publishable workspace as well; the fixture cannot discover every folder that may later be published.
The SQLite file contains fictional requests, note content, operation keys and
timestamps; CSRF tokens are generated per process and are not persisted or logged.
The journal and reusable playbooks belong in the separate private skill memory
location described by the skill, not inside this fixture or public source.

## Manual controlled journey

1. Open **Office information** and locate **Office hours: 09:00-17:00**.
2. Open **New request**. Use reference `DEMO-BROWSER-01`, a fictional title and
   one of the available categories. Submit **Create request**.
3. On **Request details**, use **Upload note** to upload `fictional-note.txt`.
4. Open **Edit request**, change title or category, and submit **Save changes**.
5. Open **New request**, click **Fail next save**, then create reference
   `DEMO-RECOVERY-01`. This deliberately commits the save and returns HTTP 503.
   Follow **Verify requests list** and inspect the existing record before any
   retry. Reusing an operation key or an identical reference does not add a row.
6. Record the confirmed reference, page and pending action in private memory.
   Interrupt the agent or close the tab. Resume by reading that memory, opening
   **Requests**, reconciling the reference and fetching a fresh form. Complete
   only the pending action. A server restart preserves records, while invalidating
   stale CSRF tokens. Do not blindly replay an old form.
7. Attempt the original create again and confirm there remains one row for the
   reference. An identical upload is deduplicated by request, filename and SHA-256.

`GET /api/requests` exposes synthetic record IDs, references, title, category,
version, timestamps, note metadata and operation counts for independent result
reconciliation. Uploaded text is shown on each request's detail page and is
stored as a SQLite BLOB; arbitrary local files are never served.

## Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/`, `/info` | Navigation and information lookup |
| GET | `/requests`, `/requests/new` | List and create form |
| GET | `/requests/{id}`, `/requests/{id}/edit` | Detail, upload form and edit form |
| GET | `/api/requests` | Independent synthetic reconciliation |
| POST | `/requests` | Idempotent create with unique reference |
| POST | `/requests/{id}/edit` | Idempotent edit with version counter |
| POST | `/requests/{id}/upload` | UTF-8 text note, maximum 4096 bytes |
| POST | `/control/fail-next-save` | Arm one committed-save/503 response |

Mutations require a valid hidden CSRF token. Explicit Origin must match the
loopback server, cross-site Fetch Metadata is rejected, and Host must match
`127.0.0.1:{port}`. CLI requests without Origin still require the token. All
bodies are bounded to 65536 bytes. Filenames cannot contain paths, consecutive
dots or unsupported extensions. Text is escaped on output. There are no delete,
payment, publication, outbound network or account authentication operations.

## Automated real HTTP checks

```powershell
python -m unittest discover -s . -p test_server.py -v
```

The tests start isolated loopback server subprocesses with temporary private
state and exercise requests through urllib. They check navigation, forms,
editing, multipart upload, duplicate prevention, committed-save failure,
restart/resume, CSRF/origin/host restrictions, escaping and upload/body limits.
They do **not** prove browser interaction, agent skill discovery, or successful
execution in Claude Code or Codex. Those require separate observed runtime
evidence. No components are installed by these tests.
