#!/usr/bin/env python3
"""Loopback-only, fictional HTTP office used for controlled browser validation.

Python 3.10+, standard library only. This is a disposable test fixture, not a
production application. Request data lives in --state, outside this repository.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
import hashlib
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit
import uuid

MAX_BODY = 64 * 1024
MAX_NOTE = 4 * 1024
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
CATEGORIES = ("Administration", "Facilities", "Research")


class InputError(Exception):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_state():
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "state")))
    return base / "WebOpsSecretary" / "phase2-demo"


def check_state_path(path):
    resolved = Path(path).expanduser().resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise ValueError("--state must be outside the repository")
    return resolved


class DemoServer(HTTPServer):
    def __init__(self, address, state_dir):
        if address[0] != "127.0.0.1":
            raise ValueError("This fixture must bind only to 127.0.0.1")
        self.state_dir = check_state_path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.state_dir / "demo.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS requests (
              id INTEGER PRIMARY KEY, reference TEXT NOT NULL UNIQUE,
              title TEXT NOT NULL, category TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS operations (
              op_key TEXT PRIMARY KEY, kind TEXT NOT NULL, request_id INTEGER NOT NULL,
              payload_digest TEXT NOT NULL,
              FOREIGN KEY(request_id) REFERENCES requests(id));
            CREATE TABLE IF NOT EXISTS notes (
              id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL, filename TEXT NOT NULL,
              content BLOB NOT NULL, digest TEXT NOT NULL, created_at TEXT NOT NULL,
              UNIQUE(request_id, filename, digest),
              FOREIGN KEY(request_id) REFERENCES requests(id));
        """)
        self.csrf = secrets.token_urlsafe(32)
        self.fail_next_save = False
        super().__init__(address, DemoHandler)

    @property
    def origin(self):
        return "http://127.0.0.1:%d" % self.server_port

    def server_close(self):
        try:
            super().server_close()
        finally:
            self.db.close()


class DemoHandler(BaseHTTPRequestHandler):
    server: DemoServer
    server_version = "WebOpsDemo/1.0"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, fmt, *args):
        # Do not log form values, tokens, request URLs, or uploaded contents.
        return

    def send_page(self, status, title, body):
        doc = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s | WebOps Demo Office</title><style>
body{font:18px/1.5 system-ui,sans-serif;max-width:850px;margin:32px auto;padding:0 24px;color:#17232c;background:#fafbfc}
nav{display:flex;gap:24px;padding:12px 0 22px;border-bottom:2px solid #d5dfe6}
a{color:#064aa8}label{display:block;font-weight:600;margin-top:18px}
input,select,button{font:inherit;padding:9px;margin:5px 0 12px;max-width:100%%;box-sizing:border-box}
input[type=text]{width:100%%}button{background:#124b73;color:white;border:0;border-radius:4px;cursor:pointer}
table{border-collapse:collapse;width:100%%}th,td{text-align:left;border-bottom:1px solid #cbd5dc;padding:10px}
.notice{background:#e4f1f8;border-left:4px solid #124b73;padding:12px}.warning{background:#fff1d9;padding:12px}
small{color:#445461}pre{white-space:pre-wrap;overflow-wrap:anywhere}fieldset{margin:24px 0;border:1px solid #b8c6d0}
</style></head><body><header><strong>WebOps Demo Office</strong>
<p><small>Local fictional test data only. No real accounts or external submissions.</small></p>
<nav aria-label="Main navigation"><a href="/">Home</a><a href="/info">Office information</a><a href="/requests">Requests</a><a href="/requests/new">New request</a></nav></header>
<main><h1>%s</h1>%s</main></body></html>""" % (escape(title), escape(title), body)
        self.send_bytes(status, doc.encode("utf-8"), "text/html; charset=utf-8")

    def send_bytes(self, status, data, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def host_ok(self):
        return self.headers.get("Host") == "127.0.0.1:%d" % self.server.server_port

    def hidden(self, operation=True):
        fields = '<input type="hidden" name="csrf" value="%s">' % escape(self.server.csrf)
        if operation:
            fields += '<input type="hidden" name="operation_key" value="%s">' % uuid.uuid4().hex
        return fields

    def request_row(self, rid):
        return self.server.db.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()

    def do_GET(self):
        if not self.host_ok():
            return self.send_page(400, "Invalid host", "<p>Use the displayed loopback URL.</p>")
        parts = urlsplit(self.path)
        path = parts.path
        if parts.query or parts.fragment:
            return self.send_page(400, "Invalid URL", "<p>Query parameters are not used here.</p>")
        if path == "/":
            return self.send_page(200, "Welcome", '<p>Practice authorized administrative work with fictional requests.</p><p><a href="/info">Locate office hours</a> or <a href="/requests/new">create a test request</a>.</p>')
        if path == "/info":
            return self.send_page(200, "Office information", "<dl><dt>Office hours</dt><dd>09:00-17:00</dd><dt>Fictional office</dt><dd>North Star Demo Office</dd><dt>Reference convention</dt><dd>DEMO- followed by letters, digits, or hyphens</dd></dl>")
        if path == "/api/requests":
            records = []
            for row in self.server.db.execute("SELECT * FROM requests ORDER BY id"):
                item = dict(row)
                item["notes"] = [dict(n) for n in self.server.db.execute("SELECT id,filename,digest,created_at FROM notes WHERE request_id=? ORDER BY id", (row["id"],))]
                item["operation_count"] = self.server.db.execute("SELECT count(*) FROM operations WHERE request_id=?", (row["id"],)).fetchone()[0]
                records.append(item)
            data = json.dumps({"count": len(records), "requests": records}, indent=2).encode()
            return self.send_bytes(200, data, "application/json; charset=utf-8")
        if path == "/requests":
            rows = self.server.db.execute("SELECT * FROM requests ORDER BY id").fetchall()
            listing = "".join('<tr><td><a href="/requests/%d">%s</a></td><td>%s</td><td>%s</td><td>%s</td></tr>' % (r["id"], escape(r["reference"]), escape(r["title"]), escape(r["category"]), r["version"]) for r in rows)
            body = '<p id="request-count">%d request(s)</p><p><a href="/requests/new">Create a new request</a></p>' % len(rows)
            body += '<table><thead><tr><th>Reference</th><th>Title</th><th>Category</th><th>Version</th></tr></thead><tbody>%s</tbody></table>' % listing
            return self.send_page(200, "Requests", body)
        if path == "/requests/new":
            return self.send_page(200, "New request", self.request_form(None) + self.failure_form())
        match = re.fullmatch(r"/requests/([1-9][0-9]*)(/edit)?", path)
        if match:
            row = self.request_row(int(match[1]))
            if row is None:
                return self.send_page(404, "Request not found", "<p>Check the requests list.</p>")
            if match[2]:
                return self.send_page(200, "Edit request", self.request_form(row) + self.failure_form())
            return self.detail(row)
        self.send_page(404, "Page not found", '<p><a href="/requests">Recover using the requests list</a>.</p>')

    def request_form(self, row):
        title = escape(row["title"] if row else "", quote=True)
        reference = escape(row["reference"] if row else "", quote=True)
        # Explicit values stay stable if a browser translates the visible label.
        options = "".join('<option value="%s"%s>%s</option>' % (escape(c, quote=True), ' selected' if row and row["category"] == c else "", escape(c)) for c in CATEGORIES)
        action = "/requests/%d/edit" % row["id"] if row else "/requests"
        reference_field = '<p>Reference: <strong>%s</strong></p>' % reference if row else '<label for="reference">Reference</label><input id="reference" name="reference" type="text" required pattern="DEMO-[A-Za-z0-9-]+" maxlength="48" placeholder="DEMO-ALPHA-01">'
        return '<form action="%s" method="post">%s%s<label for="title">Title</label><input id="title" name="title" type="text" required maxlength="120" value="%s"><label for="category">Category</label><select id="category" name="category">%s</select><p><button type="submit">%s</button></p></form>' % (action, self.hidden(), reference_field, title, options, "Save changes" if row else "Create request")

    def failure_form(self):
        armed = self.server.fail_next_save
        return '<fieldset><legend>Controlled recovery test</legend><p>Failure status: <strong>%s</strong></p><p>The next create or edit will commit successfully, then return HTTP 503. Verify the list before retrying.</p><form action="/control/fail-next-save" method="post">%s<button type="submit">Fail next save</button></form></fieldset>' % ("armed" if armed else "not armed", self.hidden(False))

    def detail(self, row):
        notes = self.server.db.execute("SELECT * FROM notes WHERE request_id=? ORDER BY id", (row["id"],)).fetchall()
        body = '<dl><dt>Reference</dt><dd>%s</dd><dt>Title</dt><dd>%s</dd><dt>Category</dt><dd>%s</dd><dt>Version</dt><dd>%d</dd></dl><p><a href="/requests/%d/edit">Edit request</a> | <a href="/requests">Return to requests</a></p>' % (escape(row["reference"]), escape(row["title"]), escape(row["category"]), row["version"], row["id"])
        body += '<h2>Uploaded notes (%d)</h2>' % len(notes)
        for note in notes:
            body += '<article><h3>%s</h3><pre>%s</pre></article>' % (escape(note["filename"]), escape(bytes(note["content"]).decode("utf-8")))
        body += '<form action="/requests/%d/upload" method="post" enctype="multipart/form-data">%s<label for="note">Fictional text note (.txt, up to 4096 bytes)</label><input id="note" name="note" type="file" accept=".txt,text/plain" required><p><button type="submit">Upload note</button></p></form>' % (row["id"], self.hidden())
        return self.send_page(200, "Request details", body)

    def read_body(self, count):
        # Bound the whole read, not merely the pause between individual packets.
        deadline = time.monotonic() + 10
        chunks = []
        remaining = count
        try:
            while remaining:
                seconds = deadline - time.monotonic()
                if seconds <= 0:
                    raise InputError("Request body timed out.")
                self.connection.settimeout(seconds)
                try:
                    chunk = self.rfile.read1(min(8192, remaining))
                except TimeoutError:
                    raise InputError("Request body timed out.")
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
        finally:
            self.connection.settimeout(10)
        return b"".join(chunks)

    def parse_form(self):
        if self.headers.get("Transfer-Encoding"):
            raise InputError("Transfer encoding is not supported.")
        raw_length = self.headers.get("Content-Length", "")
        if len(raw_length) > 6 or not re.fullmatch(r"[0-9]+", raw_length) or int(raw_length) == 0:
            raise InputError("Body must be between 1 and 65536 bytes.")
        length = int(raw_length)
        # Consume at most one byte beyond the accepted size. In particular this
        # fully drains the boundary+1 request before replying: closing a Windows
        # TCP connection with those unread body bytes can reset it before the
        # client receives the rejection. Never drain an arbitrarily large body.
        # An absolute 10-second deadline also bounds slow/incomplete body waits.
        data = self.read_body(min(length, MAX_BODY + 1))
        if length > MAX_BODY:
            raise InputError("Body must be between 1 and 65536 bytes.")
        if len(data) != length:
            raise InputError("Incomplete request body.")
        ctype = self.headers.get("Content-Type", "")
        fields, files = {}, {}
        if ctype.startswith("application/x-www-form-urlencoded"):
            try:
                values = parse_qs(data.decode("utf-8"), keep_blank_values=True, max_num_fields=16, encoding="utf-8", errors="strict")
            except (ValueError, UnicodeError):
                raise InputError("Invalid form encoding.")
            for key, values_for_key in values.items():
                if len(values_for_key) != 1:
                    raise InputError("Repeated fields are not supported.")
                fields[key] = values_for_key[0]
        elif ctype.startswith("multipart/form-data"):
            try:
                msg = BytesParser(policy=policy.default).parsebytes(b"Content-Type: " + ctype.encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + data)
                if not msg.is_multipart() or msg.defects:
                    raise InputError("Invalid multipart form.")
                parts = list(msg.iter_parts())
                if len(parts) > 16:
                    raise InputError("Too many fields.")
                for part in parts:
                    key = part.get_param("name", header="content-disposition")
                    if not key or key in fields or key in files or part.is_multipart() or part.defects:
                        raise InputError("Invalid or repeated multipart field.")
                    payload = part.get_payload(decode=True) or b""
                    filename = part.get_filename()
                    if filename is None:
                        fields[key] = payload.decode("utf-8", "strict")
                    else:
                        files[key] = (filename, payload)
            except (ValueError, UnicodeError):
                raise InputError("Invalid multipart form encoding.")
        else:
            raise InputError("Unsupported content type.")
        if not secrets.compare_digest(fields.get("csrf", "").encode("utf-8"), self.server.csrf.encode("utf-8")):
            raise InputError("CSRF token is missing or invalid. Reload the form.")
        return fields, files

    def do_POST(self):
        # Browsers supply Origin for cross-origin form posts. Missing Origin is
        # accepted for CLI tests only when the unguessable CSRF token is valid.
        origin = self.headers.get("Origin")
        if not self.host_ok() or (origin is not None and origin != self.server.origin) or self.headers.get("Sec-Fetch-Site") == "cross-site":
            return self.send_page(403, "Request blocked", "<p>Only same-origin loopback forms are accepted.</p>")
        if "?" in self.path or "#" in self.path:
            return self.send_page(400, "Invalid URL", "<p>Use the displayed form.</p>")
        try:
            fields, files = self.parse_form()
            if self.path == "/control/fail-next-save":
                self.server.fail_next_save = True
                return self.redirect("/requests/new")
            if self.path == "/requests":
                return self.save_request(fields, None)
            match = re.fullmatch(r"/requests/([1-9][0-9]*)/(edit|upload)", self.path)
            if match:
                rid = int(match[1])
                if self.request_row(rid) is None:
                    return self.send_page(404, "Request not found", "<p>Check the list before continuing.</p>")
                if match[2] == "edit":
                    return self.save_request(fields, rid)
                return self.upload(fields, files, rid)
            return self.send_page(404, "Action not found", "<p>No mutation was performed.</p>")
        except InputError as exc:
            return self.send_page(400, "Form rejected", "<p>%s</p>" % escape(str(exc)))

    def op_key(self, fields):
        key = fields.get("operation_key", "")
        if not re.fullmatch(r"[a-f0-9]{32}", key):
            raise InputError("Invalid operation key. Reload the form.")
        return key

    def known_operation(self, key, kind, rid, digest):
        op = self.server.db.execute("SELECT * FROM operations WHERE op_key=?", (key,)).fetchone()
        if op is not None:
            if op["kind"] != kind or (rid is not None and op["request_id"] != rid) or op["payload_digest"] != digest:
                raise InputError("Operation key was already used for different data. Reconcile before continuing.")
            return op["request_id"]
        return None

    def save_request(self, fields, rid):
        title, category = fields.get("title", "").strip(), fields.get("category", "")
        if not title or len(title) > 120 or any(ord(c) < 32 for c in title) or category not in CATEGORIES:
            raise InputError("A title of 1-120 printable characters and an available category are required.")
        reference = fields.get("reference", "").strip() if rid is None else self.request_row(rid)["reference"]
        if not re.fullmatch(r"DEMO-[A-Za-z0-9-]{1,43}", reference):
            raise InputError("Use a fictional reference starting with DEMO- (maximum 48 characters).")
        key = self.op_key(fields)
        digest = hashlib.sha256(json.dumps([reference, title, category]).encode()).hexdigest()
        kind = "create" if rid is None else "edit"
        known = self.known_operation(key, kind, rid, digest)
        if known is not None:
            return self.redirect("/requests/%d" % known)
        db = self.server.db
        now = utc_now()
        if rid is None:
            existing = db.execute("SELECT * FROM requests WHERE reference=?", (reference,)).fetchone()
            if existing:
                if existing["title"] == title and existing["category"] == category:
                    return self.redirect("/requests/%d" % existing["id"])
                return self.send_page(409, "Reference already exists", '<p>No duplicate was created. <a href="/requests/%d">Inspect the existing request</a>.</p>' % existing["id"])
            with db:
                cursor = db.execute("INSERT INTO requests(reference,title,category,created_at,updated_at) VALUES (?,?,?,?,?)", (reference, title, category, now, now))
                rid = cursor.lastrowid
                db.execute("INSERT INTO operations VALUES (?,?,?,?)", (key, kind, rid, digest))
        else:
            with db:
                db.execute("UPDATE requests SET title=?,category=?,version=version+1,updated_at=? WHERE id=?", (title, category, now, rid))
                db.execute("INSERT INTO operations VALUES (?,?,?,?)", (key, kind, rid, digest))
        if self.server.fail_next_save:
            self.server.fail_next_save = False
            return self.send_page(503, "Controlled failure after save", '<p class="warning">The save was committed, but the success response was deliberately interrupted. Verify the requests list before attempting another save.</p><p><a href="/requests">Verify requests list</a></p>')
        return self.redirect("/requests/%d" % rid)

    def upload(self, fields, files, rid):
        if set(files) != {"note"}:
            raise InputError("Choose exactly one fictional .txt note.")
        filename, payload = files["note"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,75}\.txt", filename) or ".." in filename:
            raise InputError("Use a plain .txt filename without directory components or consecutive dots.")
        if not 0 < len(payload) <= MAX_NOTE:
            raise InputError("Notes must be between 1 and 4096 bytes.")
        try:
            content = payload.decode("utf-8", "strict")
        except UnicodeError:
            raise InputError("Notes must contain UTF-8 text.")
        if any(ord(c) < 32 and c not in "\n\r\t" for c in content):
            raise InputError("Notes must contain plain text.")
        key = self.op_key(fields)
        content_hash = hashlib.sha256(payload).hexdigest()
        digest = hashlib.sha256((filename + ":" + content_hash).encode()).hexdigest()
        if self.known_operation(key, "upload", rid, digest) is not None:
            return self.redirect("/requests/%d" % rid)
        with self.server.db as db:
            db.execute("INSERT OR IGNORE INTO notes(request_id,filename,content,digest,created_at) VALUES (?,?,?,?,?)", (rid, filename, payload, content_hash, utc_now()))
            db.execute("INSERT INTO operations VALUES (?,?,?,?)", (key, "upload", rid, digest))
        return self.redirect("/requests/%d" % rid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--state", type=Path, default=default_state())
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        server = DemoServer(("127.0.0.1", args.port), args.state)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print("READY %s (fictional data only)" % server.origin, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
