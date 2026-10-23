#!/usr/bin/env python3
"""Reproduce a fictional HTTP workflow with private, disposable operational memory.

Python 3.10+, standard library only. This exercises services and the skill's
memory library; it does not operate a browser or invoke an AI coding agent.
"""
from __future__ import annotations

import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
REFERENCE = "DEMO-REPRO-01"
MAX_RESPONSE = 128 * 1024


def require(condition):
    if not condition:
        raise RuntimeError("Demonstration verification failed")


def memory_store_class():
    source = REPO_ROOT / "skills" / "webops-secretary" / "scripts" / "memory.py"
    spec = importlib.util.spec_from_file_location("webops_demo_memory", source)
    require(spec is not None and spec.loader is not None)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Store


class LocalRedirect(HTTPRedirectHandler):
    def __init__(self, origin):
        self.origin = origin

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        require(parsed.scheme + "://" + parsed.netloc == self.origin)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, origin):
        self.origin = origin
        # Ignore system proxy settings and reject redirects away from loopback.
        self.opener = build_opener(ProxyHandler({}), LocalRedirect(origin))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.opener.close()

    def http(self, path, data=None, headers=None, timeout=5):
        parts = urlsplit(path)
        require(path.startswith("/") and not path.startswith("//"))
        require(not parts.scheme and not parts.netloc and not parts.query and not parts.fragment)
        request = Request(self.origin + path, data=data, headers=headers or {})
        try:
            response = self.opener.open(request, timeout=timeout)
        except HTTPError as error:
            response = error
        with response:
            body = response.read(MAX_RESPONSE + 1)
            require(len(body) <= MAX_RESPONSE)
            return response.status, body

    def form(self, path):
        status, body = self.http(path)
        require(status == 200)
        return {
            name: html.unescape(value)
            for name, value in re.findall(
                r'<input type="hidden" name="([^"]+)" value="([^"]*)">',
                body.decode("utf-8"),
            )
        }

    def post(self, path, fields):
        return self.http(path, urlencode(fields).encode("utf-8"), {
            "Content-Type": "application/x-www-form-urlencoded", "Origin": self.origin,
        })

    def records(self):
        status, body = self.http("/api/requests")
        require(status == 200)
        return json.loads(body)

    def upload(self, path, fields, filename, payload):
        boundary = "webops-repro-fixed-boundary"
        require(boundary.encode() not in payload)
        chunks = []
        for name, value in fields.items():
            chunks.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                           % (boundary, name, value)).encode("utf-8"))
        chunks.append(("--%s\r\nContent-Disposition: form-data; name=\"note\"; "
                       "filename=\"%s\"\r\nContent-Type: text/plain\r\n\r\n"
                       % (boundary, filename)).encode("utf-8"))
        chunks.extend([payload, ("\r\n--%s--\r\n" % boundary).encode("ascii")])
        return self.http(path, b"".join(chunks), {
            "Content-Type": "multipart/form-data; boundary=" + boundary,
            "Origin": self.origin,
        })


class Fixture:
    def __init__(self, state):
        self.state = state
        self.process = None
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.origin = "http://127.0.0.1:%d" % self.port

    def start(self):
        require(self.process is None)
        self.process = subprocess.Popen(
            [sys.executable, "-B", str(HERE / "server.py"), "--port", str(self.port),
             "--state", str(self.state)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 10
            with Client(self.origin) as probe:
                while time.monotonic() < deadline:
                    require(self.process.poll() is None)
                    try:
                        if probe.http("/", timeout=0.25)[0] == 200:
                            return
                    except (URLError, OSError):
                        pass
                    time.sleep(0.05)
            raise RuntimeError("Fixture did not become ready")
        except BaseException:
            self.stop()
            raise

    def stop(self):
        if self.process is None:
            return
        process, self.process = self.process, None
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        finally:
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()


def run():
    Store = memory_store_class()
    with (HERE / "fictional-note.txt").open("rb") as note:
        payload = note.read(4097)
    require(0 < len(payload) <= 4096)
    expected_digest = hashlib.sha256(payload).hexdigest()

    # Temporary state is outside public source and is removed even on failure.
    with tempfile.TemporaryDirectory(prefix="webops-reproduce-") as temporary:
        private = Path(temporary)
        fixture = Fixture(private / "service")
        try:
            fixture.start()
            with Client(fixture.origin) as client, Store(private / "memory", [REPO_ROOT]) as memory:
                require(client.http("/")[0] == 200)
                status, info = client.http("/info")
                require(status == 200 and b"09:00-17:00" in info)
                require(client.http("/missing")[0] == 404)
                require(client.http("/requests")[0] == 200)
                require(not memory.recall("local-demo", fixture.origin))
                task = memory.create_task("local-demo", fixture.origin,
                                          "Complete the fictional DEMO-REPRO-01 service workflow")
                for key, description in (
                    ("create", "Create fictional reference DEMO-REPRO-01"),
                    ("edit", "Change the fictional request category to Facilities"),
                    ("upload", "Attach the supplied fictional text note"),
                ):
                    memory.plan(task, key, description)
                fields = client.form("/requests/new")
                fields.update(reference=REFERENCE, title="Fictional room practice", category="Administration")
                require(client.post("/control/fail-next-save", {"csrf": fields["csrf"]})[0] == 200)
                memory.start(task, "create")
                require(client.post("/requests", fields)[0] == 503)
                memory.resolve(task, "create", "unknown",
                               "HTTP 503 after save; inspect the reference before another submission")
                memory.checkpoint(task, "paused", "Create result uncertain; edit and upload remain pending")

            # Close and reopen server, client and memory. No old form is trusted.
            fixture.stop()
            fixture.start()
            with Client(fixture.origin) as client, Store(private / "memory", [REPO_ROOT]) as memory:
                restored = memory.resume(task)
                require([a["action_key"] for a in restored["uncertain"]] == ["create"])
                require([a["action_key"] for a in restored["pending"]] == ["edit", "upload"])
                records = client.records()
                require(records["count"] == 1)
                record = records["requests"][0]
                require(record["reference"] == REFERENCE and record["version"] == 1)
                require(record["category"] == "Administration" and record["operation_count"] == 1)
                record_path = "/requests/%d" % record["id"]
                fresh = client.form("/requests/new")
                require(fresh["csrf"] != fields["csrf"])
                require(client.post("/requests", fields)[0] == 400)
                memory.resolve(task, "create", "verified",
                               "Reconciled DEMO-REPRO-01 as one committed record after restart")
                memory.checkpoint(task, "active", "Create reconciled; continue with the pending edit and upload")
                try:
                    memory.start(task, "create")
                except ValueError:
                    pass
                else:
                    raise RuntimeError("Verified create was incorrectly allowed to start again")

                edit = client.form(record_path + "/edit")
                edit.update(title="Fictional room practice updated", category="Facilities")
                memory.start(task, "edit")
                require(client.post(record_path + "/edit", edit)[0] == 200)
                require(client.post(record_path + "/edit", edit)[0] == 200)
                edited = client.records()["requests"][0]
                require(edited["category"] == "Facilities" and edited["version"] == 2)
                require(edited["operation_count"] == 2)
                memory.resolve(task, "edit", "verified",
                               "Facilities at version two; replay left the version and operation count unchanged")

                upload = client.form(record_path)
                memory.start(task, "upload")
                for _ in range(2):
                    require(client.upload(record_path + "/upload", upload,
                                          "fictional-note.txt", payload)[0] == 200)
                uploaded = client.records()["requests"][0]
                require(len(uploaded["notes"]) == 1)
                require(uploaded["notes"][0]["digest"] == expected_digest)
                require(uploaded["notes"][0]["filename"] == "fictional-note.txt")
                require(payload in client.http(record_path)[1])
                memory.resolve(task, "upload", "verified",
                               "One fictional note; independent SHA-256 matches the uploaded bytes")

                # A new form and key cannot duplicate the same existing reference.
                duplicate = client.form("/requests/new")
                duplicate.update(reference=REFERENCE, title=edited["title"], category="Facilities")
                require(client.post("/requests", duplicate)[0] == 200)
                final = client.records()
                require(final["count"] == 1)
                record = final["requests"][0]
                require(record["reference"] == REFERENCE and record["category"] == "Facilities")
                require(record["version"] == 2 and len(record["notes"]) == 1)
                require(record["operation_count"] == 3)
                memory.checkpoint(task, "complete", "One request, one verified note, three effective operations")
                memory.save_playbook(
                    "local-demo", fixture.origin, "recover-save",
                    "After an uncertain save, reopen the service, reconcile the unique fictional reference, "
                    "then fetch a fresh form before continuing pending actions.",
                    "WebOps Demo Office 1.0", confidence="medium", validated=True,
                    evidence="Controlled HTTP workflow reconciled a committed save after server and client restart",
                )

            with Store(private / "memory", [REPO_ROOT]) as memory:
                finished = memory.resume(task)
                require(finished["task"]["status"] == "complete")
                require(len(finished["completed"]) == 3 and not finished["pending"] and not finished["uncertain"])
                recalled = memory.recall("local-demo", fixture.origin, "uncertain save")
                require(len(recalled) == 1 and recalled[0]["status"] == "validated")
                require(recalled[0]["last_validated_at"] is not None)
            return {
                "success": True, "reference": REFERENCE, "record_count": 1,
                "category": "Facilities", "version": 2, "note_count": 1,
                "effective_operations": 3, "reconciled_after_failure": True,
                "memory_restored": True, "playbook_recalled": True,
                "stale_form_rejected": True, "upload_digest_verified": True,
            }
        finally:
            fixture.stop()


def main():
    try:
        result = run()
    except KeyboardInterrupt:
        print(json.dumps({"error": "demonstration_interrupted", "success": False}, sort_keys=True))
        return 130
    except Exception:
        # Failure diagnostics must not leak local paths, live tokens or runtime IDs.
        print(json.dumps({"error": "demonstration_failed", "success": False}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
