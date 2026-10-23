"""Isolated project-local installer checks; no real host or user installation."""
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("db_skill_installer", ROOT / "scripts" / "install_skill.py")
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="db-install-test-")
        self.addCleanup(self.temporary.cleanup)
        # Match install()'s resolved project paths when Windows TEMP uses an
        # 8.3 alias, so path-specific metadata mocks intercept the destination.
        self.base = Path(self.temporary.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / ".git").mkdir()
        self.source = self.base / "source"
        self.source.mkdir()
        (self.source / "examples").mkdir()
        self.names = ["SKILL.md", "examples/form.md", "package-manifest.json"]
        (self.source / "SKILL.md").write_text("# Fictional fixture\n[Example](examples/form.md)\n", encoding="utf-8")
        (self.source / "examples/form.md").write_text("Fictional demo@example.test\n", encoding="utf-8")
        self.write_manifest()

    def write_manifest(self):
        (self.source / "package-manifest.json").write_text(json.dumps({
            "name": "webops-secretary", "version": "1.0.0", "files": self.names
        }), encoding="utf-8")

    def destination(self, host):
        return self.project / INSTALL.HOST_FOLDERS[host] / "skills" / "webops-secretary"

    def test_codex_installs_only_manifest_bytes_in_project(self):
        cache = self.source / "__pycache__"
        cache.mkdir()
        (cache / "generated.pyc").write_bytes(b"generated")
        result = INSTALL.install("codex", self.project, self.source)
        destination = self.destination("codex")
        copied = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
        self.assertEqual(copied, set(self.names))
        for name in self.names:
            self.assertEqual((destination / name).read_bytes(), (self.source / name).read_bytes())
        self.assertEqual(result["scope"], "project")
        self.assertFalse((self.project / ".claude").exists())

    def test_claude_uses_its_own_project_discovery_folder(self):
        INSTALL.install("claude", self.project, self.source)
        self.assertTrue((self.destination("claude") / "SKILL.md").is_file())
        self.assertFalse((self.project / ".agents").exists())

    def test_existing_installation_is_preserved(self):
        destination = self.destination("codex")
        destination.mkdir(parents=True)
        original = destination / "owner-note.md"
        original.write_bytes(b"keep existing content")
        with self.assertRaises(INSTALL.InstallError):
            INSTALL.install("codex", self.project, self.source)
        self.assertEqual(original.read_bytes(), b"keep existing content")
        self.assertFalse((destination / "SKILL.md").exists())

    def test_second_install_cannot_silently_replace_first(self):
        INSTALL.install("codex", self.project, self.source)
        original = (self.destination("codex") / "SKILL.md").read_bytes()
        with self.assertRaises(INSTALL.InstallError):
            INSTALL.install("codex", self.project, self.source)
        self.assertEqual((self.destination("codex") / "SKILL.md").read_bytes(), original)

    def test_home_directory_is_not_an_install_target(self):
        with patch.object(Path, "home", return_value=self.project):
            with self.assertRaises(INSTALL.InstallError):
                INSTALL.install("codex", self.project, self.source)
        self.assertFalse((self.project / ".agents").exists())

    def test_filesystem_root_is_not_an_install_target(self):
        with self.assertRaises(INSTALL.InstallError):
            INSTALL.install("codex", Path(self.project.anchor), self.source)

    def test_non_git_directory_is_rejected_before_writes(self):
        other = self.base / "not-a-git-project"
        other.mkdir()
        with self.assertRaises(INSTALL.InstallError):
            INSTALL.install("codex", other, self.source)
        self.assertEqual(list(other.iterdir()), [])

    def test_worktree_git_file_is_supported(self):
        (self.project / ".git").rmdir()
        (self.project / ".git").write_text("gitdir: fixture-metadata\n", encoding="utf-8")
        INSTALL.install("claude", self.project, self.source)
        self.assertTrue((self.destination("claude") / "SKILL.md").exists())

    def test_agent_configuration_directory_is_not_a_project(self):
        other = self.project / ".agents" / "nested-project"
        (other / ".git").mkdir(parents=True)
        with self.assertRaises(INSTALL.InstallError):
            INSTALL.install("codex", other, self.source)
        self.assertFalse((other / ".agents").exists())

    def test_unknown_host_is_rejected(self):
        with self.assertRaises(INSTALL.InstallError):
            INSTALL.install("unknown", self.project, self.source)
        self.assertEqual({p.name for p in self.project.iterdir()}, {".git"})

    def test_reparse_metadata_blocks_destination_before_writes(self):
        candidate = self.project / ".agents"
        original = Path.lstat
        def metadata(path, *args, **kwargs):
            if path == candidate:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", metadata):
            with self.assertRaises(INSTALL.InstallError):
                INSTALL.install("codex", self.project, self.source)
        self.assertFalse(candidate.exists())

    def test_unlisted_private_file_blocks_installation(self):
        (self.source / ".env").write_text("Fictional fixture", encoding="utf-8")
        with self.assertRaises(INSTALL.InstallError):
            INSTALL.install("codex", self.project, self.source)
        self.assertFalse((self.project / ".agents").exists())

    def test_manifest_traversal_blocks_installation(self):
        self.names.append("../outside.md")
        self.write_manifest()
        with self.assertRaises(INSTALL.InstallError):
            INSTALL.install("codex", self.project, self.source)
        self.assertFalse((self.project / ".agents").exists())

    def test_partial_write_rolls_back_only_new_paths(self):
        parent = self.project / ".agents" / "skills"
        parent.mkdir(parents=True)
        sentinel = parent / "existing-owner-file.md"
        sentinel.write_bytes(b"preserve")
        write = INSTALL._write_new
        calls = []
        def interrupted(path, data, created):
            calls.append(path)
            if len(calls) == 2:
                write(path, b"partial new write", created)
                raise OSError("Synthetic interrupted write")
            return write(path, data, created)
        with patch.object(INSTALL, "_write_new", interrupted):
            with self.assertRaises(OSError):
                INSTALL.install("codex", self.project, self.source)
        self.assertFalse(self.destination("codex").exists())
        self.assertEqual(sentinel.read_bytes(), b"preserve")
        self.assertEqual(list(parent.iterdir()), [sentinel])


if __name__ == "__main__":
    unittest.main()
