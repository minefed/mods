#!/usr/bin/env python3
"""Verify and package the recorded Minefed JAR baseline (Python stdlib only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = "inventory/mods.lock.json"
CHUNK_SIZE = 1024 * 1024
ARTIFACT_DIRS = (".cache/server-mods", "artifacts/local", "vendor/jars", "vendor/local")


class ModError(Exception):
    """A failed precondition that must not silently change the baseline."""


def safe_path(root: Path, value: str) -> Path:
    """Accept portable repository-relative paths; reject escapes and link parents."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise ModError(f"Invalid repository path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).drive:
        raise ModError(f"Absolute path is forbidden: {value}")
    parts = value.split("/")
    if any(part in ("", ".", "..") or re.search(r'[<>:"|?*\x00-\x1f]', part)
           or part.endswith((" ", ".")) for part in parts):
        raise ModError(f"Unsafe repository path: {value}")
    current = root.resolve()
    for part in parts:
        if re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part):
            raise ModError(f"Reserved filename: {value}")
        current = current / part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ModError(f"Linked paths are forbidden: {value}")
    resolved = current.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ModError(f"Path leaves repository: {value}")
    return resolved


def output_path(root: Path, value: str) -> Path:
    result = safe_path(root, value)
    if len(PurePosixPath(value).parts) < 2 or PurePosixPath(value).parts[0] != "build":
        raise ModError("Output must be a path strictly beneath build/")
    return result


def validate_source(root: Path, source: dict, name: str) -> None:
    if not isinstance(source, dict):
        raise ModError(f"Invalid source record: {name}")
    safe_path(root, source.get("path"))
    if not re.fullmatch(r"[0-9a-fA-F]{40}", str(source.get("commit", ""))):
        raise ModError(f"Source needs a full commit hash: {name}")
    if not source.get("url") or not source.get("ref"):
        raise ModError(f"Source needs url and ref: {name}")


def load_manifest(root: Path, value: str = DEFAULT_MANIFEST) -> dict:
    path = safe_path(root, value)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ModError(f"Cannot read manifest {value}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ModError("Expected manifest schemaVersion 1")
    if data.get("minecraftVersion") != "1.20.4" or data.get("loader") != "fabric":
        raise ModError("This preparation baseline requires Minecraft 1.20.4 / Fabric")
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ModError("Manifest must contain a nonempty entries array")
    names, paths = set(), set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ModError("Manifest entries must be objects")
        name = entry.get("fileName")
        safe_path(root, name)
        if "/" in name or not name.lower().endswith(".jar"):
            raise ModError(f"Expected a plain JAR filename: {name}")
        if name.casefold() in names:
            raise ModError(f"Duplicate filename: {name}")
        names.add(name.casefold())
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(entry.get("sha256", ""))):
            raise ModError(f"Missing or invalid SHA-256: {name}")
        if type(entry.get("size")) is not int or entry["size"] <= 0:
            raise ModError(f"Missing or invalid byte size: {name}")
        if type(entry.get("included")) is not bool:
            raise ModError(f"included must be a boolean: {name}")
        if not entry["included"] and not entry.get("exclusionReason"):
            raise ModError(f"Excluded artifact needs an exclusionReason: {name}")
        if entry.get("management") not in ("submodule", "binary"):
            raise ModError(f"Invalid management policy: {name}")
        artifact = entry.get("artifact")
        if not isinstance(artifact, dict):
            raise ModError(f"Missing artifact record: {name}")
        artifact_path = safe_path(root, artifact.get("path"))
        if artifact_path.name != name:
            raise ModError(f"artifact.path filename differs from fileName: {name}")
        path_key = str(artifact_path).casefold()
        if path_key in paths:
            raise ModError(f"Duplicate artifact path: {name}")
        paths.add(path_key)
        if artifact.get("redistribution") not in ("allowed", "modpack-only", "local-only"):
            raise ModError(f"Unknown redistribution policy: {name}")
        source = entry.get("source")
        if entry["management"] == "submodule" and not isinstance(source, dict):
            raise ModError(f"Submodule needs a source record: {name}")
        if source is not None:
            validate_source(root, source, name)
    extras = data.get("sourceRepositories", [])
    if not isinstance(extras, list):
        raise ModError("sourceRepositories must be an array")
    for source in extras:
        validate_source(root, source, "sourceRepositories")
    return data


def file_digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(CHUNK_SIZE):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def check_bytes(path: Path, entry: dict) -> None:
    if not path.is_file():
        raise ModError(f"Missing artifact: {entry['fileName']} ({path})")
    digest, size = file_digest(path)
    if size != entry["size"] or digest != entry["sha256"].lower():
        raise ModError(f"Artifact size/SHA-256 mismatch: {entry['fileName']}; file left unchanged")


def check_artifact(root: Path, entry: dict) -> None:
    path = safe_path(root, entry["artifact"]["path"])
    check_bytes(path, entry)
    try:
        with zipfile.ZipFile(path) as jar:
            metas = [item for item in jar.infolist() if item.filename == "fabric.mod.json"]
            if not metas:
                if entry.get("modId") is not None:
                    raise ModError(f"No Fabric metadata for recorded modId: {entry['fileName']}")
                return  # For example, the separately inventoried TCPShield plugin.
            if len(metas) != 1 or metas[0].file_size > CHUNK_SIZE:
                raise ModError(f"Invalid Fabric metadata entry: {entry['fileName']}")
            metadata = json.loads(jar.read(metas[0]).decode("utf-8-sig"))
            if not isinstance(metadata, dict):
                raise ModError(f"Fabric metadata must be an object: {entry['fileName']}")
            expected = (entry.get("modId"), entry.get("version"), entry.get("environment"))
            actual = (metadata.get("id"), metadata.get("version"), metadata.get("environment", "*"))
            if actual != expected:
                raise ModError(f"Fabric id/version/environment mismatch: {entry['fileName']}: {actual!r} != {expected!r}")
    except (OSError, ValueError, zipfile.BadZipFile, UnicodeError) as exc:
        raise ModError(f"Cannot inspect JAR {entry['fileName']}: {exc}") from exc


def git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(root), *args], check=True,
                                capture_output=True, text=True, encoding="utf-8")
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        raise ModError(f"Git verification failed: {detail.strip()}") from exc


def check_sources(root: Path, entries: list[dict], extras: list[dict] = ()) -> None:
    modules = safe_path(root, ".gitmodules")
    if not modules.is_file():
        raise ModError("Missing .gitmodules")
    records = git(root, "config", "--file", str(modules), "--get-regexp", r"^submodule\..*\.path$")
    configured = {}
    for record in records.splitlines():
        key, path = record.split(None, 1)
        safe_path(root, path)
        if path in configured:
            raise ModError(f"Duplicate .gitmodules path: {path}")
        configured[path] = git(root, "config", "--file", str(modules), "--get", key[:-4] + "url")
    checked = {}
    sources = [entry["source"] for entry in entries if entry.get("source")] + list(extras)
    for source in sources:
        path, commit = source["path"], source["commit"].lower()
        identity = (commit, source["url"])
        if path in checked:
            if checked[path] != identity:
                raise ModError(f"Conflicting source records: {path}")
            continue
        checked[path] = identity
        source_path = safe_path(root, path)
        if configured.get(path) != source["url"]:
            raise ModError(f".gitmodules URL/path differs from lock: {path}")
        index = git(root, "ls-files", "--stage", "--", path)
        wanted = f"160000 {commit} 0\t{path}"
        if index != wanted:
            raise ModError(f"Index gitlink differs from lock: {path}")
        if not (source_path / ".git").exists():
            raise ModError(f"Submodule is not initialized: {path}")
        if git(source_path, "rev-parse", "HEAD").lower() != commit:
            raise ModError(f"Submodule HEAD differs from lock: {path}")
        if git(source_path, "status", "--porcelain"):
            raise ModError(f"Submodule has local changes: {path}")
    unrecorded = set(configured) - set(checked)
    if unrecorded:
        raise ModError("Unrecorded .gitmodules paths: " + ", ".join(sorted(unrecorded)))


def verify(root: Path, manifest: dict, sources: bool = False) -> int:
    errors = []
    for entry in manifest["entries"]:
        try:
            check_artifact(root, entry)
        except (ModError, OSError) as exc:
            errors.append(str(exc))
    if sources:
        try:
            check_sources(root, manifest["entries"], manifest.get("sourceRepositories", []))
        except ModError as exc:
            errors.append(str(exc))
    if errors:
        raise ModError("\n".join(errors))
    return len(manifest["entries"])


def included_entries(root: Path, manifest: dict) -> list[dict]:
    entries = [entry for entry in manifest["entries"] if entry["included"]]
    if not entries:
        raise ModError("No artifacts are selected for the baseline")
    ids = {}
    for entry in entries:
        mod_id = entry.get("modId")
        if not isinstance(mod_id, str) or not mod_id:
            raise ModError(f"Included artifact is not a Fabric mod: {entry['fileName']}")
        if mod_id in ids:
            raise ModError(f"Duplicate included modId {mod_id}: {ids[mod_id]} and {entry['fileName']}")
        ids[mod_id] = entry["fileName"]
        check_artifact(root, entry)
    return entries


def publish_new(temp: Path, destination: Path) -> None:
    """Atomic no-clobber publication on the same filesystem (including Windows)."""
    try:
        os.link(temp, destination)
    except FileExistsError as exc:
        raise ModError(f"Output already exists; left unchanged: {destination}") from exc
    except OSError as exc:
        raise ModError(f"Cannot atomically create output {destination}: {exc}") from exc


def stage(root: Path, manifest: dict, output: str = "build/staged-mods") -> int:
    entries = included_entries(root, manifest)
    destination = output_path(root, output)
    expected = {entry["fileName"]: entry for entry in entries}
    if destination.exists():
        if not destination.is_dir():
            raise ModError(f"Stage output is not a directory: {output}")
        for path in destination.iterdir():
            safe_path(root, path.relative_to(root).as_posix())
            if path.name not in expected or not path.is_file():
                raise ModError(f"Unexpected stage content; left unchanged: {path}")
            check_bytes(path, expected[path.name])
    destination.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        target = destination / entry["fileName"]
        if target.exists():
            continue
        with tempfile.NamedTemporaryFile(dir=destination, suffix=".part", delete=False) as stream:
            temporary = Path(stream.name)
        try:
            shutil.copyfile(safe_path(root, entry["artifact"]["path"]), temporary)
            check_bytes(temporary, entry)
            publish_new(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return len(entries)


def license_summary(entries: list[dict], private: bool) -> str:
    lines = ["# Minefed baseline license and origin notices", "",
             "Private preparation archive." if private else "Modpack preparation archive.",
             "This archive does not grant additional rights. Preserve each author's terms.",
             "Source pins can differ from deployed JAR source versions; see lock notes.", ""]
    for entry in entries:
        lines += [f"## {entry['fileName']}", "", f"License: {entry.get('license')}",
                  f"License/permission evidence: {entry.get('licenseUrl')}",
                  f"Redistribution policy: {entry['artifact']['redistribution']}",
                  f"Artifact origin: {entry['artifact'].get('url')}"]
        if entry.get("source"):
            source = entry["source"]
            lines += [f"Managed source: {source['url']} @ {source['commit']}",
                      f"Upstream: {source.get('upstream')}"]
        lines += [f"Notes: {entry.get('notes', '')}", ""]
    return "\n".join(lines)


def is_notice(name: str) -> bool:
    path = PurePosixPath(name)
    if any(part.lower() in ("assets", "data") for part in path.parts[:-1]):
        return False
    basename = path.name.lower()
    if not re.match(r"^(?:license|licence|copying|notice)(?:$|[._\- ])", basename):
        return False
    # Mod resources can be named "notice" too. Keep legal suffix conventions such
    # as LICENSE.md_oritech, LICENSE_mcwdoors and COPYING.LESSER, but never export
    # graphics, structured game data or executable content as separate notices.
    return path.suffix.lower() not in {
        ".json", ".json5", ".mcmeta", ".class", ".java", ".kt", ".js", ".py",
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tga",
        ".ogg", ".mp3", ".wav", ".mp4", ".webm", ".ttf", ".otf", ".woff", ".woff2",
        ".jar", ".zip", ".gz", ".bin", ".nbt", ".exe", ".dll", ".so", ".dylib",
    }


def add_notices(archive: zipfile.ZipFile, root: Path, entries: list[dict]) -> None:
    seen = set()
    for entry in entries:
        jar_path = safe_path(root, entry["artifact"]["path"])
        with zipfile.ZipFile(jar_path) as jar:
            for info in jar.infolist():
                if info.is_dir() or not is_notice(info.filename):
                    continue
                safe_path(root, info.filename)  # Never allow ZIP traversal in notice names.
                if info.file_size > 20 * CHUNK_SIZE:
                    raise ModError(f"Oversized notice in {entry['fileName']}: {info.filename}")
                target = f"licenses/jars/{entry['fileName']}/{info.filename}"
                if target in seen:
                    raise ModError(f"Duplicate JAR notice path: {target}")
                archive.writestr(target, jar.read(info))
                seen.add(target)
        source = entry.get("source")
        if source:
            source_path = safe_path(root, source["path"])
            if source_path.is_dir():
                for path in source_path.iterdir():
                    if path.is_file() and is_notice(path.name):
                        safe_path(root, path.relative_to(root).as_posix())
                        target = f"licenses/sources/{source['path']}/{path.name}"
                        if target not in seen:
                            archive.write(path, target)
                            seen.add(target)
    for folder in ("inventory/notices", "inventory/licenses", "licenses"):
        notice_dir = safe_path(root, folder)
        if notice_dir.is_dir():
            for path in sorted(notice_dir.rglob("*")):
                if path.is_file():
                    relative = path.relative_to(root).as_posix()
                    safe_path(root, relative)
                    target = f"licenses/repository/{relative}"
                    archive.write(path, target)


def pack(root: Path, manifest: dict, output: str = "build/minefed-baseline.zip",
         private: bool = False) -> int:
    entries = included_entries(root, manifest)
    restricted = [entry["fileName"] for entry in entries
                  if entry["artifact"]["redistribution"] == "local-only"]
    if restricted and not private:
        raise ModError("Public packaging blocked by local-only artifacts. Use --private for a local "
                       "archive; this grants no redistribution permission:\n" + "\n".join(restricted))
    destination = output_path(root, output)
    if destination.suffix.lower() != ".zip":
        raise ModError("Pack output must end in .zip")
    if destination.exists():
        raise ModError(f"Output already exists; left unchanged: {output}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".part", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entry in entries:
                source = safe_path(root, entry["artifact"]["path"])
                # Verify the exact bytes written, even if an input changes after preflight.
                digest = hashlib.sha256()
                size = 0
                with source.open("rb") as reader, archive.open(f"mods/{entry['fileName']}", "w") as writer:
                    while block := reader.read(CHUNK_SIZE):
                        writer.write(block)
                        digest.update(block)
                        size += len(block)
                if digest.hexdigest() != entry["sha256"].lower() or size != entry["size"]:
                    raise ModError(f"Artifact changed during packing: {entry['fileName']}")
            archive.writestr("inventory/mods.lock.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            archive.writestr("LICENSES.md", license_summary(entries, private))
            add_notices(archive, root, entries)
            archive.writestr("PACK-INFO.json", json.dumps({"private": private, "artifactCount": len(entries),
                             "sourceCompilation": False, "runtimeValidated": False}, indent=2) + "\n")
        publish_new(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return len(entries)


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ModError(f"Artifact download requires a reviewed HTTPS URL: {url!r}")


class HTTPSRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url: str):
    validate_url(url)
    return build_opener(HTTPSRedirects()).open(
        Request(url, headers={"User-Agent": "minefed-mod-inventory/1"}), timeout=60)


def hydrate(root: Path, manifest: dict) -> int:
    missing = []
    manual = []
    for entry in manifest["entries"]:
        destination = safe_path(root, entry["artifact"]["path"])
        if destination.exists():
            check_bytes(destination, entry)
            continue
        relative = destination.relative_to(root).as_posix()
        if not any(relative.startswith(folder + "/") for folder in ARTIFACT_DIRS):
            raise ModError(f"Hydrate writes only to inventory artifact directories: {relative}")
        url = entry["artifact"].get("url")
        if not isinstance(url, str) or not url:
            manual.append(entry["fileName"])
            continue
        validate_url(url)
        missing.append(entry)
    for entry in missing:
        destination = safe_path(root, entry["artifact"]["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".part", delete=False) as stream:
            temporary = Path(stream.name)
            try:
                with download(entry["artifact"]["url"]) as response:
                    total = 0
                    while block := response.read(min(CHUNK_SIZE, entry["size"] - total + 1)):
                        total += len(block)
                        if total > entry["size"]:
                            raise ModError(f"Download larger than recorded size: {entry['fileName']}")
                        stream.write(block)
                stream.flush()
                os.fsync(stream.fileno())
            except Exception:
                stream.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            check_bytes(temporary, entry)
            publish_new(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    if manual:
        raise ModError(f"Restored {len(missing)} missing artifacts. Remaining manual-only artifacts have "
                       "no reviewed download URL; restore these recorded JARs manually:\n" + "\n".join(manual))
    return len(missing)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="Repository-relative lock path")
    sub = parser.add_subparsers(dest="command", required=True)
    verification = sub.add_parser("verify", help="Verify every recorded JAR, including excluded entries")
    verification.add_argument("--sources", action="store_true", help="Also verify submodule pins, HEADs and clean worktrees")
    staging = sub.add_parser("stage", help="Copy included JARs to a directory below build/")
    staging.add_argument("--output", default="build/staged-mods")
    packing = sub.add_parser("pack", help="Create a ZIP of included JARs and license/origin notices")
    packing.add_argument("--output", default="build/minefed-baseline.zip")
    packing.add_argument("--private", action="store_true", help="Allow local-only JARs in a private local archive")
    sub.add_parser("hydrate", help="Restore missing JARs from reviewed, hash-pinned HTTPS URLs")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(ROOT, args.manifest)
        if args.command == "verify":
            count = verify(ROOT, manifest, args.sources)
            print(f"Verified {count} recorded artifacts" + (" and source pins" if args.sources else ""))
        elif args.command == "stage":
            count = stage(ROOT, manifest, args.output)
            print(f"Staged {count} included artifacts in {args.output}")
        elif args.command == "pack":
            count = pack(ROOT, manifest, args.output, args.private)
            print(f"Packed {count} included artifacts in {args.output}" + (" (private)" if args.private else ""))
        else:
            count = hydrate(ROOT, manifest)
            print(f"Restored {count} missing artifacts; existing verified files left unchanged")
        return 0
    except (ModError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
