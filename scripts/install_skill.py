#!/usr/bin/env python3
"""Install reviewed WebOps Secretary files into one existing Git project.

Only project-local discovery folders are supported. No host settings, global
skills, dependencies, Git commits, or remote services are changed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat


REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY / "skills" / "webops-secretary"
VALIDATOR = SOURCE / "scripts" / "package_skill.py"
HOST_FOLDERS = {"codex": ".agents", "claude": ".claude"}
CONFIG_FOLDERS = {".agents", ".claude", ".codex"}


class InstallError(ValueError):
    """The installation does not satisfy the project-local contract."""


def _is_link(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _unlinked(path: Path) -> None:
    if any(_is_link(part) for part in (path, *path.parents)):
        raise InstallError("Installation paths must not traverse links, junctions, or reparse points")


def _project(path: Path) -> Path:
    project = Path(path).expanduser().absolute()
    _unlinked(project)
    if not project.is_dir():
        raise InstallError("Choose an existing Git project directory")
    project = project.resolve()
    home = Path.home().absolute().resolve()
    if project == home or project in home.parents or project == Path(project.anchor):
        raise InstallError("A home directory, its ancestors, or a filesystem root is not a project target")
    if any(part.name.lower() in CONFIG_FOLDERS for part in (project, *project.parents)):
        raise InstallError("Global and existing agent configuration directories are not project targets")
    reserved = [Path(p) for p in ("/etc", "/usr", "/bin", "/sbin", "/System", "/Library")]
    if os.name == "nt":
        reserved = [Path(os.environ[key]) for key in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)") if os.environ.get(key)]
    if any(project == base.absolute() or base.absolute() in project.parents for base in reserved):
        raise InstallError("System and application installation directories are not project targets")
    marker = project / ".git"
    _unlinked(marker)
    if not marker.is_dir() and not marker.is_file():
        raise InstallError("The project root must contain a .git directory or worktree file")
    return project


def _payload(source: Path) -> dict[str, bytes]:
    # Execute only the repository's own reviewed validator, never an arbitrary
    # script selected from a supplied source fixture or downloaded skill.
    _unlinked(VALIDATOR.absolute())
    if not VALIDATOR.is_file():
        raise InstallError("Bundled publication validator is missing")
    spec = importlib.util.spec_from_file_location("webops_install_validator", VALIDATOR)
    if spec is None or spec.loader is None:
        raise InstallError("Bundled publication validator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.validate(source)
    except (ValueError, OSError) as error:
        raise InstallError("Source failed publication validation; inspect the skill with its package checker") from error


def _write_new(path: Path, data: bytes, created: list[Path]) -> None:
    with path.open("xb") as handle:
        created.append(path)
        handle.write(data)
    if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(data).digest():
        raise InstallError("Installed file verification failed")


def install(host: str, project: Path, source: Path = SOURCE) -> dict:
    if host not in HOST_FOLDERS:
        raise InstallError("Host must be codex or claude")
    project = _project(project)
    destination = project / HOST_FOLDERS[host] / "skills" / "webops-secretary"
    _unlinked(destination)
    if destination.exists():
        raise InstallError("Destination already exists; review it manually before any update")
    payload = _payload(Path(source))
    created_directories = []
    created_files = []
    try:
        for directory in (destination.parent.parent, destination.parent, destination):
            _unlinked(directory)
            if directory == destination or not directory.exists():
                directory.mkdir(mode=0o755)
                created_directories.append(directory)
            elif not directory.is_dir():
                raise InstallError("An installation parent is not a directory")
        for relative, data in sorted(payload.items()):
            target = destination / relative
            missing_parents = []
            parent = target.parent
            while parent != destination and not parent.exists():
                missing_parents.append(parent)
                parent = parent.parent
            for directory in reversed(missing_parents):
                _unlinked(directory)
                directory.mkdir(mode=0o755)
                created_directories.append(directory)
            _unlinked(target)
            # Exclusive creation records ownership before the first write;
            # rollback never deletes a file whose exclusive open was refused.
            if target.exists():
                raise InstallError("Unexpected destination file; refusing replacement")
            _write_new(target, data, created_files)
    except BaseException:
        # Roll back only files/directories created by this invocation, never a
        # recursive tree or preexisting project content. Concurrent hostile
        # filesystem mutation is outside this helper's protection boundary.
        for target in reversed(created_files):
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    return {"host": host, "scope": "project", "destination": str(destination), "files": len(payload), "version": "1.0.0"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, choices=tuple(HOST_FOLDERS))
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = install(args.host, args.project)
    except (InstallError, OSError):
        # Avoid disclosing input paths or operating-system exception contents.
        print("Installation refused or incomplete. Check the existing project, unlinked paths, source validation, and destination; no overwrite is supported.")
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
