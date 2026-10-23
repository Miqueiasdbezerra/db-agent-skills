"""Publication safety invariants using isolated fictional package fixtures."""

import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zipfile


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "package_skill.py"
SPEC = importlib.util.spec_from_file_location("webops_package", SOURCE)
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        # Match validate()'s canonical paths even when Windows TEMP uses an
        # 8.3 alias, so path-specific metadata mocks exercise the real guards.
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "skill"
        self.root.mkdir()
        self.names = ["SKILL.md", "package-manifest.json", "examples/form.md"]
        (self.root / "examples").mkdir()
        (self.root / "SKILL.md").write_text("# Fictional skill\n[Form](examples/form.md)\n", encoding="utf-8")
        (self.root / "examples/form.md").write_text("Contact: demo@example.test\n", encoding="utf-8")
        self.write_manifest()

    def write_manifest(self):
        (self.root / "package-manifest.json").write_text(json.dumps({
            "name": "webops-secretary", "version": "1.0.0", "files": self.names
        }), encoding="utf-8")

    def reject(self):
        with self.assertRaises(PACKAGE.ValidationError):
            PACKAGE.validate(self.root)

    def test_allowlist_build_is_deterministic_and_hash_verified(self):
        first, second = self.base / "first.zip", self.base / "second.zip"
        result = PACKAGE.build(self.root, first)
        PACKAGE.build(self.root, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(result["files"], 3)
        with zipfile.ZipFile(first) as archive:
            self.assertEqual(archive.testzip(), None)
            self.assertEqual(set(archive.namelist()), {"webops-secretary/" + name for name in self.names})
            for name in self.names:
                self.assertEqual(archive.read("webops-secretary/" + name), (self.root / name).read_bytes())

    def test_unlisted_file_is_rejected(self):
        (self.root / "unreviewed.txt").write_text("Fictional content", encoding="utf-8")
        self.reject()

    def test_environment_file_is_rejected_even_if_allowlisted(self):
        self.names.append(".env")
        self.write_manifest()
        (self.root / ".env").write_text("Fictional content", encoding="utf-8")
        self.reject()

    def test_nested_sensitive_data_is_rejected(self):
        (self.root / "examples/private-memory").mkdir()
        (self.root / "examples/private-memory/task.json").write_text("{}", encoding="utf-8")
        self.names.append("examples/private-memory/task.json")
        self.write_manifest()
        self.reject()

    def test_credential_literal_rejected_without_echoing_value(self):
        value = "gh" + "p_" + "A" * 35
        (self.root / "examples/form.md").write_text(value, encoding="utf-8")
        with self.assertRaises(PACKAGE.ValidationError) as context:
            PACKAGE.validate(self.root)
        self.assertNotIn(value, str(context.exception))

    def test_quoted_credential_assignment_is_rejected(self):
        assignment = '"api_' + 'key": "' + 'X' * 24 + '"'
        (self.root / "examples/form.md").write_text(assignment, encoding="utf-8")
        self.reject()

    def test_short_credentials_and_json_session_identifiers_are_rejected(self):
        for field in ('pass'+'word','coo'+'kies','session_'+'id','to'+'ken'):
            for content in ('"'+field+'": "'+'x7'+'"',field+'='+'x7'):
                with self.subTest(field=field,quoted=content.startswith('"')):
                    (self.root / "examples/form.md").write_text(content,encoding="utf-8")
                    self.reject()

    def test_sensitive_filename_is_rejected_without_echoing_value(self):
        name = 'examples/'+'gh'+'p_'+'a'*30+'.txt'
        (self.root/name).write_text('Fictional',encoding='utf-8')
        for listed in (False,True):
            with self.subTest(listed=listed):
                if listed:
                    self.names.append(name)
                    self.write_manifest()
                with self.assertRaises(PACKAGE.ValidationError) as caught:
                    PACKAGE.validate(self.root)
                self.assertNotIn(name,str(caught.exception))

    def test_cookie_and_signed_url_are_rejected(self):
        for content in ('"coo'+'kie": "'+'synthetic-session-value'+'"', 'https://portal.example.test/download?'+'X-Amz-Signature='+'synthetic-value'):
            (self.root / "examples/form.md").write_text(content, encoding="utf-8")
            self.reject()

    def test_unquoted_secret_assignments_are_rejected(self):
        for field in ('refresh_'+'token','client_'+'secret','pass'+'word'):
            value = 'fictional-value-for-rejection-check'
            (self.root / "examples/form.md").write_text(field+'='+value, encoding="utf-8")
            with self.assertRaises(PACKAGE.ValidationError) as caught:
                PACKAGE.validate(self.root)
            self.assertNotIn(value,str(caught.exception))

    def test_nonfictional_email_and_home_path_are_rejected(self):
        for content in ("operator" + "@company.invalid", "C:" + "\\Users\\" + "fictional-person\\draft.txt"):
            with self.subTest(content_type="email" if "@" in content else "home path"):
                (self.root / "examples/form.md").write_text(content, encoding="utf-8")
                self.reject()

    def test_private_key_block_is_rejected(self):
        marker = "-----BEGIN " + "PRIVATE KEY-----"
        (self.root / "examples/form.md").write_text(marker, encoding="utf-8")
        self.reject()

    def test_manifest_traversal_and_case_collision_are_rejected(self):
        for name in ("../outside.txt", "examples/../outside.txt", "C:/outside.txt", "skill.md"):
            with self.subTest(name=name):
                self.names.append(name)
                self.write_manifest()
                self.reject()
                self.names.pop()

    def test_missing_required_file_is_rejected(self):
        (self.root / "examples/form.md").unlink()
        self.reject()

    def test_link_outside_or_missing_link_is_rejected(self):
        for link in ("../outside.md", "missing.md", "file:///outside.md"):
            with self.subTest(link=link):
                (self.root / "SKILL.md").write_text(f"[Bad]({link})", encoding="utf-8")
                self.reject()

    def test_symlink_is_rejected(self):
        external = self.base / "external.md"
        external.write_text("Fictional", encoding="utf-8")
        candidate = self.root / "examples/form.md"
        candidate.unlink()
        try:
            candidate.symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("Host does not allow symlink creation")
        self.reject()

    def test_directory_link_is_rejected(self):
        external = self.base / "external"
        external.mkdir()
        link = self.root / "linked-directory"
        try:
            link.symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Host does not allow symlink creation")
        self.reject()

    def test_portable_link_metadata_detection(self):
        # Metadata injection is portable coverage, not a real OS symlink test.
        for mode, attributes, expected in (
            (stat.S_IFLNK,0,True),
            (stat.S_IFDIR,0x400,True),
            (stat.S_IFREG,0,False),
        ):
            with self.subTest(mode=mode,attributes=attributes):
                info = SimpleNamespace(st_mode=mode,st_file_attributes=attributes)
                with patch.object(Path,'lstat',return_value=info):
                    self.assertEqual(PACKAGE._is_link(self.root),expected)

    def test_portable_file_link_metadata_blocks_packaging(self):
        candidate = self.root/'examples/form.md'
        original = Path.lstat
        for mode, attributes in ((stat.S_IFLNK,0),(stat.S_IFREG,0x400)):
            def metadata(path,*args,**kwargs):
                if path == candidate:
                    return SimpleNamespace(st_mode=mode,st_file_attributes=attributes)
                return original(path,*args,**kwargs)
            with self.subTest(mode=mode):
                with patch.object(Path,'lstat',metadata):
                    self.reject()

    def test_portable_directory_link_metadata_blocks_packaging(self):
        candidate = self.root/'linked-directory'
        candidate.mkdir()
        original = Path.lstat
        for mode, attributes in ((stat.S_IFLNK,0),(stat.S_IFDIR,0x400)):
            def metadata(path,*args,**kwargs):
                if path == candidate:
                    return SimpleNamespace(st_mode=mode,st_file_attributes=attributes)
                return original(path,*args,**kwargs)
            with self.subTest(mode=mode):
                with patch.object(Path,'lstat',metadata):
                    self.reject()

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_windows_junction_is_rejected(self):
        import _winapi

        external = self.base / "external-junction-target"
        external.mkdir()
        link = self.root / "junction-directory"
        try:
            _winapi.CreateJunction(str(external), str(link))
        except (OSError, AttributeError):
            self.skipTest("Host does not support junction creation")
        try:
            self.assertTrue(PACKAGE._is_link(link))
            self.reject()
        finally:
            # Remove only the junction, retaining the target directory.
            link.rmdir()
        self.assertTrue(external.exists())

    def test_generated_bytecode_is_ignored(self):
        cache = self.root / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-310.pyc").write_bytes(b"generated bytecode")
        self.assertEqual(len(PACKAGE.validate(self.root)), 3)

    def test_unknown_file_in_cache_is_rejected(self):
        cache = self.root / "__pycache__"
        cache.mkdir()
        (cache / "unreviewed.txt").write_text("Fictional", encoding="utf-8")
        self.reject()

    def test_output_inside_skill_is_rejected(self):
        with self.assertRaises(PACKAGE.ValidationError):
            PACKAGE.build(self.root, self.root / "release.zip")

    def test_existing_archive_is_preserved(self):
        archive = self.base / "existing.zip"
        archive.write_bytes(b"existing file")
        with self.assertRaises(PACKAGE.ValidationError):
            PACKAGE.build(self.root, archive)
        self.assertEqual(archive.read_bytes(), b"existing file")


if __name__ == "__main__":
    unittest.main()
