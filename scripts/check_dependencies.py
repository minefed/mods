#!/usr/bin/env python3
"""Report the latest compatible stable dependencies from Modrinth; never install them."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import mods

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = "inventory/dependency-policy.json"
DEFAULT_MANIFEST = "inventory/dependencies.lock.json"
API_ROOT = "https://api.modrinth.com/v2"


def load_policy(root: Path, manifest: dict) -> dict:
    try:
        policy = json.loads(mods.safe_path(root, DEFAULT_POLICY).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise mods.ModError(f"Cannot read dependency policy: {exc}") from exc
    validate_policy(policy, manifest)
    return policy


def validate_policy(policy: dict, manifest: dict) -> None:
    if not isinstance(policy, dict) or policy.get("schemaVersion") != 1:
        raise mods.ModError("Expected dependency policy schemaVersion 1")
    if (policy.get("minecraftVersion"), policy.get("loader"), policy.get("channel")) != ("1.20.4", "fabric", "release"):
        raise mods.ModError("Dependency policy requires Minecraft 1.20.4 / Fabric / release")
    if any(policy[key] != manifest.get(key) for key in ("minecraftVersion", "loader")):
        raise mods.ModError("Dependency policy runtime differs from the baseline")
    entries = policy.get("entries")
    if not isinstance(entries, list) or not entries:
        raise mods.ModError("Dependency policy needs a nonempty entries array")
    mod_ids, project_ids = set(), set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise mods.ModError("Dependency policy entries must be objects")
        mod_id, project_id = entry.get("modId"), entry.get("projectId")
        if not isinstance(mod_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", mod_id):
            raise mods.ModError(f"Invalid dependency modId: {mod_id!r}")
        if not isinstance(project_id, str) or not re.fullmatch(r"[A-Za-z0-9]+", project_id):
            raise mods.ModError(f"Invalid Modrinth projectId: {project_id!r}")
        if mod_id in mod_ids or project_id in project_ids:
            raise mods.ModError(f"Duplicate dependency modId or projectId: {mod_id}")
        mod_ids.add(mod_id)
        project_ids.add(project_id)
        matches = [item for item in manifest["entries"] if item.get("modId") == mod_id]
        if len(matches) != 1:
            raise mods.ModError(f"Dependency needs exactly one baseline entry: {mod_id}")
        artifact = matches[0].get("artifact")
        if not isinstance(artifact, dict) or not isinstance(artifact.get("publishedRelease"), dict):
            raise mods.ModError(f"Baseline has no published artifact provenance: {mod_id}")
        release = artifact["publishedRelease"]
        if (release.get("provider"), release.get("projectId")) != ("modrinth", project_id):
            raise mods.ModError(f"Dependency project differs from baseline provenance: {mod_id}")
        if not isinstance(release.get("versionId"), str) or not re.fullmatch(r"[A-Za-z0-9]+", release["versionId"]):
            raise mods.ModError(f"Baseline has no valid Modrinth versionId: {mod_id}")
        if not isinstance(artifact.get("sha512"), str) or not re.fullmatch(r"[0-9a-fA-F]{128}", artifact["sha512"]):
            raise mods.ModError(f"Baseline has no valid SHA-512: {mod_id}")


def fetch_versions(project_id: str, minecraft: str, loader: str) -> list:
    query = urlencode({"game_versions": json.dumps([minecraft]), "loaders": json.dumps([loader]), "include_changelog": "false"})
    request = Request(f"{API_ROOT}/project/{project_id}/version?{query}", headers={
        "User-Agent": "minefed-mods/dependency-check (https://github.com/minefed/mods)", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except (OSError, URLError, ValueError) as exc:
        raise mods.ModError(f"Cannot query Modrinth project {project_id}: {exc}") from exc
    if not isinstance(result, list):
        raise mods.ModError(f"Modrinth returned a non-array version response: {project_id}")
    return result


def published_at(version: dict) -> datetime:
    try:
        value = datetime.fromisoformat(version["date_published"].replace("Z", "+00:00"))
        if value.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value.astimezone(timezone.utc)
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise mods.ModError(f"Invalid release publication date: {version.get('id')}") from exc


def latest_release(versions: list, project_id: str, minecraft: str, loader: str) -> dict:
    if not isinstance(versions, list) or any(not isinstance(item, dict) for item in versions):
        raise mods.ModError("Modrinth versions must be an array of objects")
    eligible = [item for item in versions if item.get("project_id") == project_id
                and isinstance(item.get("game_versions"), list) and minecraft in item["game_versions"]
                and isinstance(item.get("loaders"), list) and loader in item["loaders"]
                and item.get("version_type") == "release" and item.get("status", "listed") == "listed"]
    if not eligible:
        raise mods.ModError(f"No listed stable release for {project_id} / Minecraft {minecraft} / {loader}")
    ids = [item.get("id") for item in eligible]
    if any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]+", value) for value in ids) or len(set(ids)) != len(ids):
        raise mods.ModError(f"Invalid or duplicate release IDs: {project_id}")
    # Publication time is authoritative; version labels need not use SemVer.
    latest = max(eligible, key=lambda item: (published_at(item), item["id"]))
    files = latest.get("files")
    if not isinstance(files, list) or any(not isinstance(item, dict) for item in files):
        raise mods.ModError(f"Invalid release file list: {latest['id']}")
    jars = [item for item in files if isinstance(item.get("filename"), str) and item["filename"].lower().endswith(".jar")]
    primary = [item for item in jars if item.get("primary") is True]
    if len(primary) == 1:
        artifact = primary[0]
    elif len(jars) == 1:
        artifact = jars[0]
    else:
        raise mods.ModError(f"Cannot choose one primary JAR: {latest['id']}")
    hashes = artifact.get("hashes")
    if not isinstance(hashes, dict) or not isinstance(hashes.get("sha512"), str) or not re.fullmatch(r"[0-9a-fA-F]{128}", hashes["sha512"]):
        raise mods.ModError(f"Release JAR has no valid SHA-512: {latest['id']}")
    url = artifact.get("url")
    if not isinstance(url, str) or urlparse(url).scheme != "https" or not urlparse(url).hostname:
        raise mods.ModError(f"Release JAR has no HTTPS download URL: {latest['id']}")
    if not isinstance(latest.get("version_number"), str) or not isinstance(latest.get("dependencies"), list):
        raise mods.ModError(f"Invalid release version or dependency metadata: {latest['id']}")
    return {"versionId": latest["id"], "version": latest["version_number"],
            "publishedAt": published_at(latest).isoformat(), "versionUrl": f"https://modrinth.com/version/{latest['id']}",
            "gameVersions": latest["game_versions"], "loaders": latest["loaders"],
            "fileName": artifact["filename"], "downloadUrl": url, "hashes": hashes,
            "dependencies": latest["dependencies"]}


def check(policy: dict, manifest: dict, selected: list[str] | None = None) -> dict:
    validate_policy(policy, manifest)
    configured = {item["modId"]: item for item in policy["entries"]}
    unknown = set(selected or []) - configured.keys()
    if unknown:
        raise mods.ModError("Unknown dependency id: " + ", ".join(sorted(unknown)))
    baseline = {item.get("modId"): item for item in manifest["entries"]}
    entries = []
    for mod_id, entry in configured.items():
        if selected and mod_id not in selected:
            continue
        latest = latest_release(fetch_versions(entry["projectId"], policy["minecraftVersion"], policy["loader"]),
                                entry["projectId"], policy["minecraftVersion"], policy["loader"])
        locked = baseline[mod_id]
        current = {"versionId": locked["artifact"]["publishedRelease"]["versionId"], "version": locked.get("version"),
                   "fileName": locked["fileName"], "sha512": locked["artifact"]["sha512"]}
        if current["versionId"] != latest["versionId"]:
            status = "update-available"
        elif current["sha512"].lower() != latest["hashes"]["sha512"].lower():
            status = "artifact-changed"
        else:
            status = "current"
        entries.append({"modId": mod_id, "projectId": entry["projectId"], "status": status, "current": current, "latest": latest})
    return {"schemaVersion": 1, "checkedAt": datetime.now(timezone.utc).isoformat(),
            "minecraftVersion": policy["minecraftVersion"], "loader": policy["loader"], "channel": policy["channel"],
            "baselineChanged": False, "runtimeValidated": False, "entries": entries}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", action="append", dest="ids", help="Check one policy modId; repeat for several")
    parser.add_argument("--output", help="Optional JSON report strictly beneath build/")
    args = parser.parse_args(argv)
    try:
        destination = mods.output_path(ROOT, args.output) if args.output else None
        manifest = mods.load_manifest(ROOT, DEFAULT_MANIFEST)
        report = check(load_policy(ROOT, manifest), manifest, args.ids)
        if destination:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for entry in report["entries"]:
            print(f"{entry['modId']}: {entry['status']} ({entry['current']['version']} -> {entry['latest']['version']})")
        if destination:
            print(f"Report: {args.output}")
        return int(any(entry["status"] == "artifact-changed" for entry in report["entries"]))
    except (mods.ModError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
