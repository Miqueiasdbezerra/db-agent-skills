"""Validate the publication allowlist and create a deterministic ZIP (stdlib only).

This scanner is a conservative heuristic. Passing it does not establish that all
secrets, personal data, or licensing concerns have been discovered. Review the
selected files before publication. Private operational memory is never included.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = "package-manifest.json"
LIMITATION = "Heuristic scan only; manually review secrets, personal data, and rights before publication."


class ValidationError(ValueError):
    """The selected directory is not safe to package under this contract."""


def _is_link(path: Path) -> bool:
    """Detect POSIX links and Windows junctions/reparse points without following."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _safe_name(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return bool(name) and "\\" not in name and ":" not in name and not name.startswith("/") and all(
        part not in {"", ".", ".."} for part in name.split("/")
    ) and str(PurePosixPath(name)) == name and bool(parts)


def _sensitive_name(name: str) -> bool:
    for part in PurePosixPath(name).parts:
        value = part.lower()
        if value == ".env" or value.startswith(".env."):
            return True
        if value in {"private-memory", "task-journals", "sessions", "uploads", "downloads", "logs", "memory.json", "memory.jsonl", "journal.json", "journal.jsonl", "state.json", "history.json"}:
            return True
        if value.startswith(("cookies", "credentials", "secrets")):
            return True
        if Path(value).suffix in {".sqlite", ".sqlite3", ".db", ".log", ".pem", ".key", ".p12", ".pfx", ".har"}:
            return True
    return False


SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:[A-Z0-9 ]* )?PRIVATE KEY-----")),
    ("provider credential", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b")),
    ("bearer credential", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I)),
    ("credential assignment", re.compile(r'''(?im)["']?\b(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|cookies?|session[_-]?id|token)["']?\s*[:=]\s*["']([^"'\r\n]+)["']''')),
    ("unquoted credential assignment", re.compile(r'''(?im)\b(?:(?:password|passwd|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|cookies?|session[_-]?id)\s*[:=]|token\s*=)\s*([A-Za-z0-9_./+~-]+)''')),
    ("sensitive URL query", re.compile(r"https?://[^\s<>\"']*[?&](?:token|key|signature|x-amz-signature|access_token|code|session)=[^\s<>\"']+", re.I)),
    ("personal home path", re.compile(r"(?i)(?:[A-Z]:[\\/](?:Users|Documents and Settings)[\\/](?![<$%{])[A-Za-z0-9_. -]+|/(?:Users|home)/(?![<$%{])[A-Za-z0-9_.-]+)")),
)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b")
PLACEHOLDER_VALUES = {"example", "redacted", "placeholder", "not-a-secret", "<redacted>", "<provided-at-runtime>"}


def _scan_content(name: str, content: str) -> list[str]:
    issues = []
    for label, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(content):
            if label == "credential assignment":
                value = match.group(1)
                # Documentation placeholders and dynamically computed expressions
                # are not literal credentials. This intentionally remains heuristic.
                if value.lower() in PLACEHOLDER_VALUES or value.startswith(("${", "<", "os.environ")):
                    continue
            line = content.count("\n", 0, match.start()) + 1
            issues.append(f"{name}:{line}: possible {label}; value omitted")
    for match in EMAIL_PATTERN.finditer(content):
        if match.group(1).lower() not in {"example.com", "example.test"}:
            line = content.count("\n", 0, match.start()) + 1
            issues.append(f"{name}:{line}: non-fictional email address; value omitted")
    return issues


def _markdown_targets(text: str):
    # Mask fenced/inline code: examples of Markdown syntax are not active links.
    text = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text)
    text = re.sub(r"`[^`\n]*`", "", text)
    for match in re.finditer(r"!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[\"'][^\n]*?[\"'])?\s*\)", text):
        yield match.group(1).strip("<>")
    for match in re.finditer(r"(?m)^\s*\[[^\]\n]+\]:\s*(<[^>]+>|\S+)", text):
        yield match.group(1).strip("<>")


def _check_links(root: Path, name: str, text: str) -> list[str]:
    issues = []
    for target in _markdown_targets(text):
        try:
            parsed = urlsplit(target)
        except ValueError:
            issues.append(f"{name}: invalid Markdown link")
            continue
        if parsed.scheme in {"https", "http", "mailto"}:
            continue
        if not parsed.path and not parsed.scheme and not parsed.netloc:
            continue
        if parsed.scheme or parsed.netloc:
            issues.append(f"{name}: unsupported or absolute Markdown link")
            continue
        relative = unquote(parsed.path)
        candidate = (root / name).parent / relative
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root)
        except (ValueError, OSError):
            issues.append(f"{name}: Markdown link escapes the skill")
            continue
        if "\\" in relative or relative.startswith("/") or not resolved.exists():
            issues.append(f"{name}: missing or invalid local Markdown link")
    return issues


def validate(root: Path = ROOT) -> dict[str, bytes]:
    """Return the exact reviewed bytes or reject; do not emit offending values."""
    root = Path(root).absolute()
    if not root.is_dir() or any(_is_link(part) for part in (root,*root.parents)):
        raise ValidationError("Skill root must be an existing, unlinked directory")
    root = root.resolve()
    manifest_path = root / MANIFEST
    if not manifest_path.is_file() or _is_link(manifest_path):
        raise ValidationError("A regular package-manifest.json is required")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError("Manifest must be valid UTF-8 JSON") from error
    if not isinstance(manifest, dict) or manifest.get("name") != "webops-secretary" or manifest.get("version") != "1.0.0":
        raise ValidationError("Manifest must identify webops-secretary version 1.0.0")
    names = manifest.get("files")
    if not isinstance(names, list) or not names or any(not isinstance(name, str) or not _safe_name(name) for name in names):
        raise ValidationError("Manifest files must be a nonempty list of safe relative POSIX paths")
    if len(set(name.casefold() for name in names)) != len(names):
        raise ValidationError("Manifest has duplicate or case-colliding paths")
    if MANIFEST not in names or "SKILL.md" not in names:
        raise ValidationError("Manifest must include itself and SKILL.md")
    if any(_scan_content("path (redacted)", name) for name in names):
        raise ValidationError("Manifest path may contain sensitive data; values omitted")
    issues = [f"{name}: sensitive filename" for name in names if _sensitive_name(name)]
    allowed = set(names)
    discovered = set()
    for directory, directories, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for entry in list(directories):
            path = base / entry
            rel = path.relative_to(root).as_posix()
            if _scan_content("path (redacted)", rel):
                raise ValidationError("Directory path may contain sensitive data; values omitted")
            if _is_link(path):
                issues.append(f"{rel}: linked directory or reparse point")
                directories.remove(entry)
            elif entry == "__pycache__":
                # Inspect cache children for links; ignore only regular .pyc files.
                continue
            elif _sensitive_name(rel):
                issues.append(f"{rel}: sensitive directory")
        for entry in files:
            path = base / entry
            rel = path.relative_to(root).as_posix()
            if _scan_content("path (redacted)", rel):
                raise ValidationError("File path may contain sensitive data; values omitted")
            if _is_link(path) or not stat.S_ISREG(path.lstat().st_mode):
                issues.append(f"{rel}: only regular unlinked files are permitted")
                continue
            if path.suffix == ".pyc" and "__pycache__" in path.relative_to(root).parts:
                continue
            discovered.add(rel)
            if rel not in allowed:
                issues.append(f"{rel}: unlisted file; publication blocked")
            if _sensitive_name(rel):
                issues.append(f"{rel}: sensitive filename")
    for missing in sorted(allowed - discovered):
        issues.append(f"{missing}: missing required file")
    payload = {}
    for name in sorted(discovered & allowed):
        try:
            data = (root / name).read_bytes()
            content = data.decode("utf-8")
        except (OSError, UnicodeError):
            issues.append(f"{name}: files must be readable UTF-8 text")
            continue
        if b"\x00" in data:
            issues.append(f"{name}: NUL byte is not permitted in source text")
        issues.extend(_scan_content(name, content))
        if name.lower().endswith(".md"):
            issues.extend(_check_links(root, name, content))
        payload[name] = data
    if issues:
        raise ValidationError("Publication check failed:\n" + "\n".join(sorted(set(issues))))
    return payload


def build(root: Path, output: Path) -> dict:
    """Build from captured validated bytes; verify entry hashes before replacing."""
    payload = validate(root)
    root = Path(root).resolve()
    output = Path(output).absolute()
    try:
        output.resolve().relative_to(root)
    except ValueError:
        pass
    else:
        raise ValidationError("ZIP output must be outside the skill directory")
    if output.exists() or output.is_symlink():
        raise ValidationError("ZIP output already exists; choose a new output path")
    if output.suffix.lower() != ".zip" or not output.parent.is_dir():
        raise ValidationError("ZIP output needs a .zip suffix and an existing parent directory")
    expected = {"webops-secretary/" + name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".webops-package-", suffix=".tmp", dir=output.parent, delete=False) as handle:
            temporary = Path(handle.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(payload.items()):
                info = zipfile.ZipInfo("webops-secretary/" + name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(temporary, "r") as archive:
            if archive.testzip() is not None or archive.namelist() != sorted(expected):
                raise ValidationError("ZIP integrity or exact manifest membership check failed")
            for info in archive.infolist():
                if stat.S_ISLNK(info.external_attr >> 16) or hashlib.sha256(archive.read(info)).hexdigest() != expected[info.filename]:
                    raise ValidationError("ZIP member type or hash check failed")
        if output.exists() or output.is_symlink():
            raise ValidationError("ZIP output appeared during build; refusing replacement")
        os.replace(temporary, output)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"files": len(payload), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "warning": LIMITATION}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Validate exact file membership, links, and sensitive-data heuristics")
    build_parser = commands.add_parser("build", help="Validate and create a new ZIP outside the skill")
    build_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "check":
            result = {"valid": True, "files": len(validate()), "warning": LIMITATION}
        else:
            result = build(ROOT, args.output)
    except (ValidationError, OSError, zipfile.BadZipFile) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
