#!/usr/bin/env python3
"""Real HTTP fixture checks using urllib; these do not claim browser execution."""
from __future__ import annotations

import html
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid

from server import check_state_path, REPO_ROOT


class DemoHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="webops-http-test-")
        self.state = Path(self.temp.name) / "private-state"
        self.start()

    def start(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.origin = "http://127.0.0.1:%d" % port
        self.process = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("server.py")), "--port", str(port), "--state", str(self.state)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        line = self.process.stdout.readline()
        if not line.startswith("READY "):
            self.fail("Server did not start: " + self.process.stderr.read())

    def stop(self):
        self.process.terminate()
        self.process.wait(timeout=10)
        self.process.stdout.close()
        self.process.stderr.close()

    def tearDown(self):
        self.stop()
        self.temp.cleanup()

    def http(self, path, data=None, headers=None):
        request = Request(self.origin + path, data=data, headers=headers or {})
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, response.headers, response.read()
        except HTTPError as response:
            with response:
                return response.code, response.headers, response.read()

    def form(self, path):
        status, _, body = self.http(path)
        self.assertEqual(status, 200)
        return {key: html.unescape(value) for key, value in re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', body.decode())}

    def post(self, path, fields, headers=None):
        combined = {"Content-Type": "application/x-www-form-urlencoded", "Origin": self.origin}
        combined.update(headers or {})
        return self.http(path, urlencode(fields).encode(), combined)

    def create(self, reference="DEMO-TEST-01", title="Fictional supplies request", fields=None):
        fields = fields or self.form("/requests/new")
        fields.update(reference=reference, title=title, category="Administration")
        result = self.post("/requests", fields)
        return fields, result

    def records(self):
        status, _, body = self.http("/api/requests")
        self.assertEqual(status, 200)
        return json.loads(body)

    def multipart(self, fields, filename, payload):
        boundary = "webops-" + uuid.uuid4().hex
        parts = []
        for key, value in fields.items():
            parts.extend([("--" + boundary + "\r\n").encode(), ('Content-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (key, value)).encode()])
        parts.extend([("--" + boundary + "\r\n").encode(), ('Content-Disposition: form-data; name="note"; filename="%s"\r\nContent-Type: text/plain\r\n\r\n' % filename).encode(), payload, ("\r\n--" + boundary + "--\r\n").encode()])
        return b"".join(parts), {"Content-Type": "multipart/form-data; boundary=" + boundary, "Origin": self.origin}

    def test_navigation_information_and_missing_route_recovery(self):
        self.assertEqual(self.http("/")[0], 200)
        status, _, body = self.http("/info")
        self.assertEqual(status, 200)
        self.assertIn(b"09:00-17:00", body)
        self.assertEqual(self.http("/missing")[0], 404)
        self.assertEqual(self.http("/requests")[0], 200)

    def test_create_duplicate_key_and_unique_reference(self):
        fields, result = self.create()
        self.assertEqual(result[0], 200)
        self.assertEqual(self.post("/requests", fields)[0], 200)
        self.create()
        data = self.records()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["requests"][0]["operation_count"], 1)
        _, conflict = self.create(title="Conflicting fictional title")
        self.assertEqual(conflict[0], 409)
        self.assertEqual(self.records()["count"], 1)

    def test_edit_with_idempotent_retry(self):
        self.create()
        fields = self.form("/requests/1/edit")
        fields.update(title="Updated fictional request", category="Facilities")
        self.assertEqual(self.post("/requests/1/edit", fields)[0], 200)
        self.assertEqual(self.post("/requests/1/edit", fields)[0], 200)
        row = self.records()["requests"][0]
        self.assertEqual((row["title"], row["category"], row["version"]), ("Updated fictional request", "Facilities", 2))

    def test_category_values_survive_translated_display_labels(self):
        status, _, body = self.http("/requests/new")
        self.assertEqual(status, 200)
        markup = body.decode()
        options = re.findall(r'<option value="([^"]+)"[^>]*>(.*?)</option>', markup)
        self.assertEqual(options, [("Administration", "Administration"), ("Facilities", "Facilities"), ("Research", "Research")])
        # Model what translation changes: text nodes, while explicit values remain.
        translations = {"Administration": "Administração", "Facilities": "Instalações", "Research": "Pesquisa"}
        for value, label in options:
            markup = markup.replace(">" + label + "</option>", ">" + translations[label] + "</option>")
        translated_options = re.findall(r'<option value="([^"]+)"[^>]*>(.*?)</option>', markup)
        self.assertEqual([value for value, _ in translated_options], list(translations))
        self.assertEqual([label for _, label in translated_options], list(translations.values()))
        fields = self.form("/requests/new")
        fields.update(reference="DEMO-TRANSLATED-01", title="Fictional translated display test", category=translated_options[1][0])
        self.assertEqual(self.post("/requests", fields)[0], 200)
        self.assertEqual(self.records()["requests"][0]["category"], "Facilities")

    def test_upload_text_and_prevent_duplicate_note(self):
        self.create()
        fields = self.form("/requests/1")
        body, headers = self.multipart(fields, "fictional.txt", b"A fictional note.\n")
        self.assertEqual(self.http("/requests/1/upload", body, headers)[0], 200)
        self.assertEqual(self.http("/requests/1/upload", body, headers)[0], 200)
        other_fields = self.form("/requests/1")
        body, headers = self.multipart(other_fields, "fictional.txt", b"A fictional note.\n")
        self.assertEqual(self.http("/requests/1/upload", body, headers)[0], 200)
        self.assertEqual(len(self.records()["requests"][0]["notes"]), 1)
        self.assertIn(b"A fictional note.", self.http("/requests/1")[2])

    def test_controlled_failure_commits_and_reconciles_before_retry(self):
        fields = self.form("/requests/new")
        self.assertEqual(self.post("/control/fail-next-save", {"csrf": fields["csrf"]})[0], 200)
        fields, result = self.create(fields=fields)
        self.assertEqual(result[0], 503)
        self.assertIn(b"save was committed", result[2])
        self.assertEqual(self.records()["count"], 1)
        self.assertEqual(self.post("/requests", fields)[0], 200)
        self.assertEqual(self.records()["requests"][0]["operation_count"], 1)

    def test_persistence_restart_revalidate_and_resume(self):
        old_fields, _ = self.create()
        confirmed = self.records()["requests"][0]
        self.stop()
        self.start()
        self.assertEqual(self.records()["requests"][0], confirmed)
        self.assertEqual(self.post("/requests", old_fields)[0], 400)
        # A resumed task fetches fresh state and token; same reference never creates again.
        self.create()
        self.assertEqual(self.records()["count"], 1)
        fields = self.form("/requests/1/edit")
        fields.update(title="Resumed fictional request", category="Research")
        self.assertEqual(self.post("/requests/1/edit", fields)[0], 200)
        self.assertEqual(self.records()["requests"][0]["version"], 2)

    def test_csrf_origin_and_host_enforced(self):
        self.assertEqual(self.post("/requests", {"reference": "DEMO-NO-CSRF"})[0], 400)
        fields = self.form("/requests/new")
        fields.update(reference="DEMO-CROSS-01", title="Fictional", category="Research")
        self.assertEqual(self.post("/requests", fields, {"Origin": "https://untrusted.invalid"})[0], 403)
        self.assertEqual(self.post("/requests", fields, {"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.http("/", headers={"Host": "untrusted.invalid"})[0], 400)
        self.assertEqual(self.records()["count"], 0)

    def test_limits_and_filename_traversal(self):
        self.create()
        for filename, payload in (("../secret.txt", b"fiction"), ("C:\\secret.txt", b"fiction"), ("x..txt", b"fiction"), ("oversized.txt", b"a" * 4097), ("binary.txt", b"\x00not text"), ("note.html", b"fiction")):
            with self.subTest(filename=filename):
                body, headers = self.multipart(self.form("/requests/1"), filename, payload)
                self.assertEqual(self.http("/requests/1/upload", body, headers)[0], 400)
        before = self.records()
        status, _, response = self.http("/requests", b"x" * 65537, {"Content-Type": "application/x-www-form-urlencoded", "Origin": self.origin})
        self.assertEqual(status, 400)
        self.assertIn(b"Body must be between 1 and 65536 bytes.", response)
        self.assertEqual(self.records(), before)
        self.assertEqual(len(self.records()["requests"][0]["notes"]), 0)

    def test_html_is_escaped_and_files_are_not_served(self):
        self.create(title='<script>alert("fictional")</script>')
        body = self.http("/requests/1")[2]
        self.assertIn(b"&lt;script&gt;", body)
        self.assertNotIn(b"<script>", body)
        self.assertEqual(self.http("/server.py")[0], 404)
        self.assertEqual(self.http("/../server.py")[0], 404)
        self.assertNotIn(b"csrf", self.http("/api/requests")[2])

    def test_operation_key_cannot_be_repurposed(self):
        fields, _ = self.create()
        fields["title"] = "Different data with used key"
        self.assertEqual(self.post("/requests", fields)[0], 400)
        self.assertEqual(self.records()["count"], 1)

    def test_state_rejects_repository_path(self):
        with self.assertRaises(ValueError):
            check_state_path(REPO_ROOT / "private-state")


if __name__ == "__main__":
    unittest.main(verbosity=2)
