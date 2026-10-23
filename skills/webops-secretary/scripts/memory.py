#!/usr/bin/env python3
"""Private operational memory and crash-safe action ledger. Python 3.10+, stdlib.

This ledger records evidence; it neither operates a browser nor grants permission.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from urllib.parse import urlsplit
import uuid

VERSION = "1.0.0"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RISK_LEVELS = ("routine", "financial", "destructive", "public", "sensitive")
SECRET = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|\b(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|cookies?|session[_-]?id|token)[\"']?\s*[:=]\s*\S+"
    r"|\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"
    r"|https?://[^\s]*[?#][^\s]+", re.I
)
EMAIL = re.compile(r"[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})", re.I)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text(value, label="text", limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label}: supply nonempty text of at most {limit} characters")
    if SECRET.search(value) or any(m.group(1).lower() not in {"example.test", "example.com"} for m in EMAIL.finditer(value)):
        raise ValueError(f"{label}: possible secret, personal email or query-bearing URL; use a minimal sanitized summary")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError(f"{label}: control characters are not allowed")
    return value.strip()


def identifier(value, label="identifier"):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", value):
        raise ValueError(f"{label}: use 1-80 lowercase letters, digits, hyphens or underscores")
    if SECRET.search(value):
        raise ValueError(f"{label}: possible secret; use an opaque non-sensitive reference")
    return value


def origin_only(value):
    value = text(value, "origin", 250)
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("origin must be an http(s) scheme and host only, without credentials, path, query or fragment")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("invalid origin port") from exc
    return f"{parsed.scheme}://{parsed.netloc.lower()}"


def is_link(path):
    # One non-following metadata read also covers Windows junctions. The fallback
    # flag keeps this check testable on systems without Windows stat extensions.
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def private_root(root=None, public_roots=()):
    if root is None:
        configured = os.environ.get("WEBOPS_MEMORY_HOME")
        root = Path(configured) if configured else (Path(os.environ.get("LOCALAPPDATA", Path.home()/"AppData/Local"))/"WebOpsSecretary/private" if os.name == "nt" else Path.home()/".local/state/webops-secretary")
    raw = Path(root).expanduser().absolute()
    for part in (raw, *raw.parents):
        if is_link(part):
            raise PermissionError("memory path must not traverse symbolic links or junctions")
    resolved = raw.resolve()
    for forbidden in [PACKAGE_ROOT, *(Path(p).expanduser().resolve() for p in public_roots)]:
        if resolved == forbidden or forbidden in resolved.parents:
            raise PermissionError("memory must stay outside the skill and every public repository root")
    for part in (resolved, *resolved.parents):
        if (part/".git").exists():
            raise PermissionError("memory cannot be stored inside a Git working tree")
    resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
    return resolved


class Store:
    def __init__(self, root=None, public_roots=()):
        self.root = private_root(root, public_roots)
        db_path = self.root/"memory.sqlite3"
        for name in ("memory.sqlite3", "memory.sqlite3-journal", "memory.sqlite3-wal", "memory.sqlite3-shm"):
            if is_link(self.root/name):
                raise PermissionError("memory database files must not be links")
        self.db = sqlite3.connect(db_path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.close()
            raise ValueError("unsupported memory schema; do not overwrite or auto-migrate")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY, scope TEXT NOT NULL, origin TEXT NOT NULL,
              objective TEXT NOT NULL, status TEXT NOT NULL, summary TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS actions (
              task_id TEXT NOT NULL REFERENCES tasks(id), action_key TEXT NOT NULL,
              description TEXT NOT NULL, risk TEXT NOT NULL, state TEXT NOT NULL,
              approval_ref TEXT, evidence TEXT NOT NULL, updated_at TEXT NOT NULL,
              PRIMARY KEY(task_id,action_key));
            CREATE TABLE IF NOT EXISTS events (
              sequence INTEGER PRIMARY KEY AUTOINCREMENT,
              task_id TEXT NOT NULL REFERENCES tasks(id), action_key TEXT,
              kind TEXT NOT NULL, summary TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS playbooks (
              scope TEXT NOT NULL, origin TEXT NOT NULL, playbook_key TEXT NOT NULL,
              procedure TEXT NOT NULL, interface_version TEXT NOT NULL,
              confidence TEXT NOT NULL, status TEXT NOT NULL,
              last_validated_at TEXT, evidence TEXT NOT NULL,
              validation_count INTEGER NOT NULL, updated_at TEXT NOT NULL,
              PRIMARY KEY(scope,origin,playbook_key));
            PRAGMA user_version=1;
        """)
        if os.name != "nt":
            db_path.chmod(0o600)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.rollback()
            raise
        else:
            self.db.commit()

    def _task(self, task_id):
        identifier(task_id, "task id")
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError("unknown task")
        return dict(row)

    def _action(self, task_id, key):
        self._task(task_id)
        identifier(key, "action key")
        row = self.db.execute("SELECT * FROM actions WHERE task_id=? AND action_key=?", (task_id, key)).fetchone()
        if row is None:
            raise KeyError("unknown action")
        return dict(row)

    def _event(self, task_id, key, kind, summary):
        self.db.execute("INSERT INTO events(task_id,action_key,kind,summary,created_at) VALUES(?,?,?,?,?)", (task_id,key,kind,summary,now()))
        self.db.execute("UPDATE tasks SET updated_at=? WHERE id=?", (now(),task_id))

    def create_task(self, scope, origin, objective):
        scope, origin, objective = identifier(scope, "scope"), origin_only(origin), text(objective,"objective")
        task_id = uuid.uuid4().hex
        with self.transaction():
            self.db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?)", (task_id,scope,origin,objective,"active","Task created",now(),now()))
            self._event(task_id,None,"created",objective)
        return task_id

    def plan(self, task_id, key, description, risk="routine"):
        key, description = identifier(key,"action key"), text(description,"description")
        if risk not in RISK_LEVELS:
            raise ValueError("unsupported risk level")
        with self.transaction():
            task = self._task(task_id)
            old = self.db.execute("SELECT * FROM actions WHERE task_id=? AND action_key=?",(task_id,key)).fetchone()
            if old:
                if old["description"] != description or old["risk"] != risk:
                    raise ValueError("action key already describes a different operation")
                return dict(old)
            if task["status"] != "active":
                raise ValueError("task must be active before planning")
            self.db.execute("INSERT INTO actions VALUES(?,?,?,?,?,?,?,?)", (task_id,key,description,risk,"planned",None,"",now()))
            self._event(task_id,key,"planned",description)
        return self._action(task_id,key)

    def start(self, task_id, key, approval_ref=None):
        if approval_ref is not None:
            approval_ref = text(approval_ref,"approval reference",250)
        with self.transaction():
            action = self._action(task_id,key)
            if self._task(task_id)["status"] != "active" or action["state"] != "planned":
                raise ValueError("only a planned action in an active task can start; reconcile uncertain results without resubmission")
            if self.db.execute("SELECT 1 FROM actions WHERE task_id=? AND state IN ('in_flight','unknown') LIMIT 1",(task_id,)).fetchone():
                raise ValueError("reconcile the task's uncertain action before starting another operation")
            if action["risk"] != "routine" and not approval_ref:
                raise PermissionError("record the user's explicit approval reference before a consequential action")
            self.db.execute("UPDATE actions SET state='in_flight',approval_ref=?,updated_at=? WHERE task_id=? AND action_key=?",(approval_ref,now(),task_id,key))
            self._event(task_id,key,"in_flight","Intent persisted before browser or service action")
        return self._action(task_id,key)

    def resolve(self, task_id, key, outcome, evidence):
        evidence = text(evidence,"evidence")
        if outcome not in {"verified","failed","unknown"}:
            raise ValueError("outcome must be verified, failed or unknown")
        with self.transaction():
            action = self._action(task_id,key)
            if action["state"] not in {"in_flight","unknown"}:
                raise ValueError("only in-flight or unknown actions can be reconciled; verified and failed results are immutable")
            self.db.execute("UPDATE actions SET state=?,evidence=?,updated_at=? WHERE task_id=? AND action_key=?",(outcome,evidence,now(),task_id,key))
            self._event(task_id,key,outcome,evidence)
        return self._action(task_id,key)

    def resume(self, task_id):
        # A read transaction keeps the task, actions and checkpoint mutually consistent.
        with self.transaction():
            task = self._task(task_id)
            actions = [dict(r) for r in self.db.execute("SELECT * FROM actions WHERE task_id=? ORDER BY rowid",(task_id,))]
            last = self.db.execute("SELECT * FROM events WHERE task_id=? AND kind='verified' ORDER BY sequence DESC LIMIT 1",(task_id,)).fetchone()
            history = [dict(r) for r in self.db.execute("SELECT * FROM events WHERE task_id=? ORDER BY sequence",(task_id,))]
        return {"task":task,"actions":actions,
                "completed":[a for a in actions if a["state"]=="verified"],
                "pending":[a for a in actions if a["state"]=="planned"],
                "uncertain":[a for a in actions if a["state"] in {"in_flight","unknown"}],
                "failed":[a for a in actions if a["state"]=="failed"],
                "last_confirmed":dict(last) if last else None,"history":history,
                "next_step":"Inspect the current authorized site and reconcile every uncertain action before any new submission"}

    def checkpoint(self, task_id, status, summary):
        summary = text(summary,"summary")
        if status not in {"active","paused","complete"}:
            raise ValueError("status must be active, paused or complete")
        with self.transaction():
            old = self._task(task_id)
            if old["status"] == "complete":
                raise ValueError("completed task cannot be reopened; create a new task")
            if status == "complete":
                states = [r[0] for r in self.db.execute("SELECT state FROM actions WHERE task_id=?",(task_id,))]
                if any(s in {"planned","in_flight","unknown"} for s in states) or (states and "verified" not in states):
                    raise ValueError("cannot mark task complete with pending/uncertain actions or without any verified outcome")
            self.db.execute("UPDATE tasks SET status=?,summary=?,updated_at=? WHERE id=?",(status,summary,now(),task_id))
            self._event(task_id,None,status,summary)
        return self._task(task_id)

    def save_playbook(self, scope, origin, key, procedure, interface_version, confidence="low", validated=False, evidence=""):
        scope, origin, key = identifier(scope,"scope"), origin_only(origin), identifier(key,"playbook key")
        procedure, interface_version = text(procedure,"procedure",12000), text(interface_version,"interface version",120)
        if confidence not in {"low","medium","high"}:
            raise ValueError("confidence must be low, medium or high")
        if validated:
            evidence = text(evidence,"validation evidence")
        elif evidence:
            evidence = text(evidence,"evidence")
        with self.transaction():
            old = self.db.execute("SELECT * FROM playbooks WHERE scope=? AND origin=? AND playbook_key=?",(scope,origin,key)).fetchone()
            count = (old["validation_count"] if old else 0) + int(validated)
            # A changed/unvalidated procedure must not inherit the prior validation.
            stamp = now() if validated else None
            status = "validated" if validated else "draft"
            self.db.execute("INSERT OR REPLACE INTO playbooks VALUES(?,?,?,?,?,?,?,?,?,?,?)",(scope,origin,key,procedure,interface_version,confidence,status,stamp,evidence,count,now()))
        return dict(self.db.execute("SELECT * FROM playbooks WHERE scope=? AND origin=? AND playbook_key=?",(scope,origin,key)).fetchone())

    def recall(self, scope, origin, query=""):
        scope, origin = identifier(scope,"scope"), origin_only(origin)
        query = text(query,"query",250) if query else ""
        return [dict(r) for r in self.db.execute("SELECT * FROM playbooks WHERE scope=? AND origin=? AND (instr(lower(procedure),lower(?))>0 OR instr(lower(playbook_key),lower(?))>0) ORDER BY updated_at DESC,playbook_key LIMIT 20",(scope,origin,query,query))]

    def invalidate_playbook(self, scope, origin, key, reason):
        scope, origin, key = identifier(scope,"scope"), origin_only(origin), identifier(key,"playbook key")
        reason = text(reason,"reason")
        with self.transaction():
            cursor = self.db.execute("UPDATE playbooks SET status='stale',confidence='low',evidence=?,updated_at=? WHERE scope=? AND origin=? AND playbook_key=?",(reason,now(),scope,origin,key))
            if not cursor.rowcount:
                raise KeyError("unknown playbook")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--public-root", type=Path, action="append", default=[])
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("init")
    p = subs.add_parser("create")
    p.add_argument("--scope",required=True); p.add_argument("--origin",required=True); p.add_argument("--objective",required=True)
    for name in ("plan","start","resolve"):
        p = subs.add_parser(name); p.add_argument("task_id"); p.add_argument("key")
        if name == "plan":
            p.add_argument("--description",required=True); p.add_argument("--risk",choices=RISK_LEVELS,default="routine")
        elif name == "start":
            p.add_argument("--approval-ref")
        else:
            p.add_argument("--outcome",choices=("verified","failed","unknown"),required=True); p.add_argument("--evidence",required=True)
    p = subs.add_parser("resume"); p.add_argument("task_id")
    p = subs.add_parser("checkpoint"); p.add_argument("task_id"); p.add_argument("--status",choices=("active","paused","complete"),required=True); p.add_argument("--summary",required=True)
    for name in ("remember","recall","invalidate"):
        p = subs.add_parser(name); p.add_argument("--scope",required=True); p.add_argument("--origin",required=True)
        if name == "recall":
            p.add_argument("--query",default="")
        else:
            p.add_argument("--key",required=True)
            if name == "invalidate":
                p.add_argument("--reason",required=True)
            else:
                p.add_argument("--procedure",required=True); p.add_argument("--interface-version",required=True)
                p.add_argument("--confidence",choices=("low","medium","high"),default="low"); p.add_argument("--validated",action="store_true"); p.add_argument("--evidence",default="")
    args = vars(parser.parse_args())
    command, root, public_roots = args.pop("command"), args.pop("root"), args.pop("public_root")
    try:
        with Store(root,public_roots) as store:
            if command == "init":
                result = {"version":VERSION,"schema":1,"ready":True,"note":"Private local storage; OS account permissions apply. Not encrypted."}
            else:
                method = {"create":"create_task","remember":"save_playbook","invalidate":"invalidate_playbook"}.get(command,command)
                result = getattr(store,method)(**args)
                if command == "create": result = {"task_id":result}
                if command == "invalidate": result = {"status":"stale"}
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError, PermissionError, KeyError, sqlite3.Error) as exc:
        # SQLite errors may include input values: never print the exception text.
        message = "Database operation failed; inspect private storage permissions and schema" if isinstance(exc,sqlite3.Error) else str(exc)
        parser.exit(2, f"Memory operation refused: {message}\n")


if __name__ == "__main__":
    main()
