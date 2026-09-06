#!/usr/bin/env python3
"""Build audited source recipes and assemble a private Minefed Fabric modpack."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

import mods

ROOT = Path(__file__).resolve().parents[1]
RECIPES = "inventory/build-recipes.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_digest(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load_plan(root: Path) -> tuple[dict, dict]:
    manifest = mods.load_manifest(root)
    plan = read_json(mods.safe_path(root, RECIPES))
    if plan.get("schemaVersion") != 1 or plan.get("minecraftVersion") != manifest["minecraftVersion"] or plan.get("loader") != "fabric":
        raise mods.ModError("Build recipes must match the inventory schema and Minecraft version")
    selected = {e["modId"]: e for e in manifest["entries"] if e["included"]}
    if len(selected) != sum(e["included"] for e in manifest["entries"]):
        raise mods.ModError("Duplicate included mod ID in baseline")
    recipes = plan.get("entries")
    if not isinstance(recipes, list) or len(recipes) != len(selected):
        raise mods.ModError("Build recipes must cover every included inventory entry exactly once")
    ids = set()
    for recipe in recipes:
        identity = recipe.get("modId")
        if not isinstance(identity, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", identity) or identity not in selected or identity in ids:
            raise mods.ModError(f"Unknown or duplicate recipe: {identity}")
        ids.add(identity)
        entry = selected[identity]
        if recipe.get("mode") not in ("source", "binary") or not recipe.get("reason"):
            raise mods.ModError(f"Recipe needs an explicit source/binary choice and reason: {identity}")
        if recipe["mode"] == "source":
            if not entry.get("source") or recipe.get("sourcePath") != entry["source"]["path"]:
                raise mods.ModError(f"Source recipe differs from the locked submodule: {identity}")
            if recipe.get("java") not in (8, 17, 21):
                raise mods.ModError(f"Recipe needs an explicit supported JDK: {identity}")
            phases = recipe.get("phases", [recipe.get("tasks")])
            if not phases or any(not isinstance(p, list) or not p or
                                 any(not isinstance(t, str) or not re.fullmatch(r"[\w:.-]+", t) or t.startswith('-') for t in p)
                                 for p in phases):
                raise mods.ModError(f"Invalid Gradle tasks: {identity}")
            globs = recipe.get("artifactGlobs")
            if not isinstance(globs, list) or not globs:
                raise mods.ModError(f"Source recipe needs explicit runtime JAR globs: {identity}")
            for pattern in globs:
                # Validate the path without interpreting wildcard characters as filenames.
                mods.safe_path(root, pattern.replace("*", "x").replace("?", "x"))
                if not pattern.endswith('.jar') or 'build/' not in pattern:
                    raise mods.ModError(f"Runtime JAR must come from a build output: {pattern}")
            if not isinstance(recipe.get("args", []), list) or any(not isinstance(a, str) for a in recipe.get("args", [])):
                raise mods.ModError(f"Invalid Gradle arguments: {identity}")
            if not isinstance(recipe.get("env", {}), dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                                for k, v in recipe.get("env", {}).items()):
                raise mods.ModError(f"Invalid recipe environment: {identity}")
    return manifest, plan


def run_path(root: Path, run: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run):
        raise mods.ModError("Invalid build run identifier")
    return mods.output_path(root, f"build/modpack-work/{run}")


def java_version(home: Path) -> int | None:
    release = home / "release"
    executable = home / "bin" / ("java.exe" if os.name == "nt" else "java")
    if not release.is_file() or not executable.is_file():
        return None
    match = re.search(r'JAVA_VERSION="(?:1\.)?(\d+)', release.read_text(encoding="utf-8"))
    return int(match[1]) if match else None


def local_config(root: Path) -> dict:
    path = root / "build.local.json"
    return read_json(path) if path.is_file() else {}


def java_home(root: Path, version: int) -> Path:
    config = local_config(root)
    candidates = [os.environ.get(f"MINEFED_JAVA{version}_HOME"), config.get(f"java{version}Home"),
                  os.environ.get(f"JAVA_HOME_{version}"), os.environ.get("JAVA_HOME")]
    for parent in (Path.home() / ".gradle" / "jdks", Path.home() / ".jdks", root / ".cache" / "jdks"):
        if parent.is_dir():
            candidates.extend(str(p.parent) for p in parent.glob("*/release"))
            candidates.extend(str(p.parent) for p in parent.glob("*/*/release"))
    for value in candidates:
        if value and java_version(Path(value)) == version:
            return Path(value).resolve()
    raise mods.ModError(f"JDK {version} not found; set MINEFED_JAVA{version}_HOME or java{version}Home in build.local.json")


def source_state(root: Path, entry: dict) -> dict:
    source = entry["source"]
    directory = mods.safe_path(root, source["path"])
    commit = mods.git(directory, "rev-parse", "HEAD")
    if commit != source["commit"]:
        raise mods.ModError(f"Source HEAD differs from inventory: {source['path']}; commit and update its source pin first")
    # Include new source files as well as tracked edits, excluding ignored outputs.
    names = subprocess.run(["git", "-C", str(directory), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                           check=True, capture_output=True).stdout.decode("utf-8").split("\0")
    digest = hashlib.sha256()
    for name in sorted(set(filter(None, names))):
        target = directory / name
        digest.update(name.encode("utf-8") + b"\0")
        if target.is_file():
            digest.update(bytes.fromhex(mods.file_digest(target)[0]))
        elif target.is_dir():
            if mods.git(target, "status", "--porcelain"):
                raise mods.ModError(f"Nested source has local changes: {source['path']}/{name}; commit and pin it first")
            digest.update(mods.git(target, "rev-parse", "HEAD").encode())
        else:
            digest.update(b"missing")
    return {"path": source["path"], "commit": commit, "treeSha256": digest.hexdigest(),
            "workingTreeStatus": mods.git(directory, "status", "--porcelain", "--untracked-files=normal")}


def prepare(root: Path, run: str) -> None:
    manifest, plan = load_plan(root)
    directory = run_path(root, run)
    if directory.exists():
        raise mods.ModError(f"Build run already exists: {run}; start a new Gradle invocation")
    for version in sorted({r["java"] for r in plan["entries"] if r["mode"] == "source"}):
        print(f"JDK {version}: {java_home(root, version)}", flush=True)
    binary_ids = {r["modId"] for r in plan["entries"] if r["mode"] == "binary"}
    binaries = [e for e in manifest["entries"] if e["included"] and e["modId"] in binary_ids]
    mods.hydrate(root, {"entries": binaries})
    for entry in binaries:
        mods.check_artifact(root, entry)
    write_json(directory / "run.json", {"run": run, "planSha256": canonical_digest(plan),
               "inventorySha256": canonical_digest(manifest), "preparedAt": datetime.now(timezone.utc).isoformat()})
    print(f"Prepared {len(plan['entries']) - len(binaries)} source builds and {len(binaries)} binary JARs", flush=True)


def check_run(root: Path, run: str, manifest: dict, plan: dict) -> Path:
    directory = run_path(root, run)
    record = read_json(directory / "run.json")
    if record.get("run") != run or record.get("planSha256") != canonical_digest(plan) or record.get("inventorySha256") != canonical_digest(manifest):
        raise mods.ModError("Build plan/inventory changed during this run; start a new Gradle invocation")
    return directory


def fabric_metadata(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        entries = [i for i in archive.infolist() if i.filename == "fabric.mod.json"]
        if len(entries) != 1 or entries[0].file_size > mods.CHUNK_SIZE:
            raise mods.ModError(f"Expected one Fabric metadata file: {path}")
        data = json.loads(archive.read(entries[0]).decode("utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get('id'), str) or not isinstance(data.get('version'), str) or '${' in data['version']:
            raise mods.ModError(f"Invalid/unexpanded Fabric metadata: {path}")
        return data


def version_satisfies(version: str, requirements) -> bool:
    """Evaluate numeric Minecraft/Java release predicates used by Fabric metadata."""
    if isinstance(requirements, list):
        return any(version_satisfies(version, item) for item in requirements)
    if requirements is None or requirements in ("*", ""):
        return True
    if not isinstance(requirements, str):
        raise mods.ModError(f"Invalid version predicate: {requirements!r}")
    if '||' in requirements:
        return any(version_satisfies(version, item.strip()) for item in requirements.split('||'))
    actual_parts = [int(n) for n in version.split('.')]
    actual = tuple((actual_parts + [0] * 4)[:4])
    for term in requirements.split():
        if term == '*':
            continue
        match = re.fullmatch(r'(>=|<=|>|<|=|~|\^)?(\d+(?:\.(?:\d+|[xX*]))*)(?:-([^+ ]*))?(?:\+[^ ]+)?', term)
        if not match:
            raise mods.ModError(f"Unrecognized Minecraft/Java version predicate: {term!r}")
        op, wanted, prerelease = match.groups()
        parts = wanted.split('.')
        numeric = []
        for part in parts:
            if part in ('x', 'X', '*'):
                break
            numeric.append(int(part))
        target = tuple((numeric + [0] * 4)[:4])
        comparison = (actual > target) - (actual < target)
        if comparison == 0 and prerelease is not None:
            comparison = 1  # A stable release sorts after its prereleases.
        if len(numeric) != len(parts):
            if op not in (None, '='):
                raise mods.ModError(f"Unsupported wildcard comparator: {term!r}")
            passed = actual[:len(numeric)] == tuple(numeric)
        elif op in ('~', '^'):
            upper = list(target)
            position = min(len(numeric) - 1, 1) if op == '~' else next((i for i, p in enumerate(numeric) if p), len(numeric) - 1)
            upper[position] += 1
            upper[position + 1:] = [0] * (3 - position)
            passed = comparison >= 0 and actual < tuple(upper)
        else:
            passed = {None: comparison == 0, '=': comparison == 0, '>': comparison > 0,
                      '>=': comparison >= 0, '<': comparison < 0, '<=': comparison <= 0}[op]
        if not passed:
            return False
    return True


def check_runtime_metadata(metadata: dict, minecraft: str = '1.20.4', java: int = 17) -> None:
    dependencies = metadata.get('depends', {})
    for identity, version in [('minecraft', minecraft), ('java', str(java))]:
        if not version_satisfies(version, dependencies.get(identity)):
            raise mods.ModError(f"{metadata['id']} {metadata['version']} requires {identity} {dependencies[identity]!r}; target is {version}")
    if metadata.get('environment', '*') not in ('*', 'client', 'server'):
        raise mods.ModError(f"Invalid Fabric environment: {metadata['id']}")


def select_runtime_jar(directory: Path, recipe: dict) -> tuple[Path, dict]:
    found = {}
    for pattern in recipe["artifactGlobs"]:
        for candidate in directory.glob(pattern):
            if candidate.is_file() and not re.search(r"-(?:sources|javadoc|dev|dev-shadow)(?:\.|-)", candidate.name):
                mods.safe_path(directory, candidate.relative_to(directory).as_posix())
                try:
                    meta = fabric_metadata(candidate)
                except (KeyError, mods.ModError):
                    continue
                if meta["id"] == recipe["modId"]:
                    found[candidate.resolve()] = meta
    if len(found) != 1:
        raise mods.ModError(f"Expected exactly one runtime JAR for {recipe['modId']}, found {len(found)}: " + ', '.join(str(p) for p in found))
    artifact, metadata = next(iter(found.items()))
    check_runtime_metadata(metadata)
    if recipe.get('expectedVersion') and metadata['version'] != recipe['expectedVersion']:
        raise mods.ModError(f"Unexpected source version for {recipe['modId']}: {metadata['version']} != {recipe['expectedVersion']}; review and update the recipe")
    return artifact, metadata


def wrapper_command(root: Path, source: Path, work: Path, recipe: dict) -> list[str]:
    home = java_home(root, recipe["java"])
    wrapper_relative = recipe.get("wrapperPath", "gradle/wrapper")
    wrapper = root / "gradle" / "wrapper" if recipe.get("wrapperFromRoot") else mods.safe_path(source, wrapper_relative)
    properties = wrapper / "gradle-wrapper.properties"
    if not properties.is_file():
        raise mods.ModError(f"Missing upstream Gradle distribution: {properties}")
    # Some upstream repositories omit the bootstrap JAR. Use the root's tracked
    # bootstrap JAR with the upstream distribution properties, without editing it.
    bootstrap = wrapper / "gradle-wrapper.jar"
    if not bootstrap.is_file():
        bootstrap = root / "gradle" / "wrapper" / "gradle-wrapper.jar"
    launch = work / "wrapper"
    launch.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bootstrap, launch / "gradle-wrapper.jar")
    shutil.copyfile(properties, launch / "gradle-wrapper.properties")
    project = mods.safe_path(source, recipe["sourceWorkDir"]) if recipe.get("sourceWorkDir") not in (None, ".") else source
    return [str(home / "bin" / ("java.exe" if os.name == "nt" else "java")), "-Xmx64m", "-Dfile.encoding=UTF-8", "-cp",
            str(launch / "gradle-wrapper.jar"), "org.gradle.wrapper.GradleWrapperMain", "--project-dir", str(project)]


@contextmanager
def _file_lock(path: Path, waiting_message: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if path.stat().st_size == 0:
            stream.write(b'0')
            stream.flush()
        waiting = False
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (11, 13, 35, 36):
                    raise
                if not waiting:
                    print(waiting_message, flush=True)
                    waiting = True
                time.sleep(0.5)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def source_lock(root: Path, identity: str):
    """Serialize the same source across independent Gradle invocations."""
    if not re.fullmatch(r'[a-z][a-z0-9_-]{1,63}', identity):
        raise mods.ModError('Invalid source identity')
    path = mods.output_path(root, f'build/source-locks/{identity}.lock')
    with _file_lock(path, f'Waiting for another build of {identity}'):
        yield


def gradle_user_home(root: Path) -> Path:
    path = Path(os.environ.get('GRADLE_USER_HOME', str(Path.home() / '.gradle'))).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


@contextmanager
def gradle_cache_lock(root: Path):
    """Older Loom versions rebuild shared Minecraft caches without a global lock."""
    path = gradle_user_home(root) / 'minefed-modpack-loom.lock'
    with _file_lock(path, 'Waiting for another Gradle build to release the shared Minecraft cache'):
        yield


def build_source(root: Path, run: str, identity: str) -> None:
    with source_lock(root, identity):
        _build_source(root, run, identity)


def tool_fingerprint(root: Path, plan: dict, recipe: dict) -> dict:
    """Inputs shared by cache keys, build completion and final receipt validation."""
    tool_inputs = {}
    for relative in ('scripts/build_modpack.py', 'scripts/mods.py', 'scripts/source-repositories.gradle',
                     'gradle/wrapper/gradle-wrapper.jar', 'gradle/wrapper/gradle-wrapper.properties'):
        path = root / relative
        tool_inputs[relative] = mods.file_digest(path)[0] if path.is_file() else None
    for version in sorted({r['java'] for r in plan['entries'] if r['mode'] == 'source'}):
        release = java_home(root, version) / 'release'
        tool_inputs[f'jdk{version}Release'] = mods.file_digest(release)[0] if release.is_file() else None
    gradle_home = gradle_user_home(root)
    user_properties = gradle_home / 'gradle.properties'
    tool_inputs['userGradleProperties'] = mods.file_digest(user_properties)[0] if user_properties.is_file() else None
    init_files = [gradle_home / 'init.gradle', gradle_home / 'init.gradle.kts']
    if (gradle_home / 'init.d').is_dir():
        init_files.extend((gradle_home / 'init.d').glob('*.gradle*'))
    tool_inputs['userInitScripts'] = {str(p.relative_to(gradle_home)): mods.file_digest(p)[0]
                                     for p in sorted(init_files) if p.is_file()}
    for variable in ('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS'):
        tool_inputs[variable] = os.environ.get(variable)
    # MTR's website is compiled by the host Node/npm, rather than a downloaded
    # version pinned by an upstream Gradle Node plugin (as BlueMap uses).
    if recipe['sourcePath'] == 'Minecraft-Transit-Railway':
        node = shutil.which('node')
        npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
        if not node or not npm:
            raise mods.ModError('MTR website compilation requires Node.js 22 and npm on PATH')
        tool_inputs['nodeVersion'] = subprocess.run([node, '--version'], check=True, capture_output=True, text=True).stdout.strip()
        npm_command = ['cmd.exe', '/d', '/c', 'npm', '--version'] if os.name == 'nt' else [npm, '--version']
        tool_inputs['npmVersion'] = subprocess.run(npm_command, check=True, capture_output=True, text=True).stdout.strip()
    return tool_inputs


def check_tool_fingerprint(root: Path, plan: dict, recipe: dict, expected: dict) -> None:
    if tool_fingerprint(root, plan, recipe) != expected:
        raise mods.ModError(f"Build tools changed for {recipe['modId']}; start a new Gradle invocation")


def _build_source(root: Path, run: str, identity: str) -> None:
    manifest, plan = load_plan(root)
    work = check_run(root, run, manifest, plan)
    recipe = next((r for r in plan["entries"] if r["modId"] == identity and r["mode"] == "source"), None)
    if recipe is None:
        raise mods.ModError(f"No source recipe: {identity}")
    entry = next(e for e in manifest["entries"] if e["included"] and e["modId"] == identity)
    state = source_state(root, entry)
    source = mods.safe_path(root, recipe["sourcePath"])
    output = work / "sources" / identity
    output.mkdir(parents=True, exist_ok=True)
    receipt = output / "result.json"
    if receipt.exists():
        raise mods.ModError(f"Source already built in this run: {identity}")
    tool_inputs = tool_fingerprint(root, plan, recipe)
    gradle_home = gradle_user_home(root)
    cache_key = canonical_digest({'source': state, 'recipe': recipe, 'tools': tool_inputs})
    cache = mods.output_path(root, 'build/source-cache/' + cache_key)
    cached_record = cache / 'result.json'
    if cached_record.is_file() and os.environ.get('MINEFED_REBUILD_SOURCES') != '1':
        cached = read_json(cached_record)
        if (cached.get('cacheKey') != cache_key or cached.get('source') != state or
                cached.get('recipeSha256') != canonical_digest(recipe) or cached.get('buildTools') != tool_inputs):
            raise mods.ModError(f'Invalid source cache receipt: {identity}')
        cached_artifact = mods.safe_path(root, cached['artifactPath'])
        if not cached_artifact.is_relative_to(cache):
            raise mods.ModError(f'Source cache artifact leaves its cache entry: {identity}')
        mods.check_bytes(cached_artifact, {'fileName': cached_artifact.name, 'sha256': cached['sha256'], 'size': cached['size']})
        destination = output / cached_artifact.name
        shutil.copyfile(cached_artifact, destination)
        cached.update(run=run, artifactPath=destination.relative_to(root).as_posix(), cacheHit=True)
        check_tool_fingerprint(root, plan, recipe, tool_inputs)
        write_json(receipt, cached)
        print(f"Reused verified source build {identity} {cached['metadata']['version']}", flush=True)
        return
    # A successful task with an outdated recipe must never select a leftover JAR.
    # Preserve prior matching outputs for recovery, then force Gradle to reproduce
    # the selected artifact. Other build products and all source files stay intact.
    previous = set()
    for pattern in recipe["artifactGlobs"]:
        previous.update(candidate for candidate in source.glob(pattern) if candidate.is_file())
    for candidate in sorted(previous):
        relative = candidate.relative_to(source).as_posix()
        checked = mods.safe_path(source, relative)
        backup = output / "previous" / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(checked, backup)
        checked.unlink()
    command = wrapper_command(root, source, output, recipe)
    environment = dict(os.environ)
    environment.update(recipe.get("env", {}))
    environment["JAVA_HOME"] = str(java_home(root, recipe["java"]))
    environment["GRADLE_USER_HOME"] = str(gradle_home)
    environment["GRADLE_OPTS"] = "-Dfile.encoding=UTF-8"
    phases = recipe.get("phases", [recipe.get("tasks")])
    homes = [str(java_home(root, v)) for v in sorted({r["java"] for r in plan["entries"] if r["mode"] == "source"})]
    common = ["--no-daemon", "--max-workers=1", "--console=plain", "-Dorg.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8",
              "-Dfabric.loom.ci=true",
              "--init-script", str(root / "scripts" / "source-repositories.gradle"),
              "-Porg.gradle.java.installations.paths=" + ','.join(homes)] + recipe.get("args", [])
    commands = []
    # Protect shared Loom caches across mods and across Minefed checkouts.
    # Keep resource generation and compilation in the same critical section.
    with gradle_cache_lock(root):
        check_tool_fingerprint(root, plan, recipe, tool_inputs)
        for number, phase in enumerate(phases, 1):
            invocation = command + common + phase
            commands.append(invocation)
            print(f"Building {recipe['sourcePath']} ({number}/{len(phases)}): {' '.join(phase)}", flush=True)
            with (output / f"gradle-{number}.log").open('w', encoding='utf-8') as log:
                result = subprocess.run(invocation, cwd=source, env=environment, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                tail = (output / f"gradle-{number}.log").read_text(encoding='utf-8', errors='replace').splitlines()[-65:]
                print('\n'.join(tail), file=sys.stderr)
                raise mods.ModError(f"Source build failed: {identity}; no binary fallback. Full log: {output / f'gradle-{number}.log'}")
    artifact, metadata = select_runtime_jar(source, recipe)
    destination = output / artifact.name
    shutil.copyfile(artifact, destination)
    digest, size = mods.file_digest(destination)
    if mods.file_digest(artifact) != (digest, size):
        raise mods.ModError(f"Source output changed during collection: {identity}")
    final_state = source_state(root, entry)
    if state["treeSha256"] != final_state["treeSha256"]:
        raise mods.ModError(f"Source changed while building: {identity}")
    check_tool_fingerprint(root, plan, recipe, tool_inputs)
    result_record = {"run": run, "compiledRun": run, "modId": identity, "mode": "source", "source": state,
                        "artifactPath": destination.relative_to(root).as_posix(), "sha256": digest, "size": size,
                        "metadata": metadata, "java": recipe["java"], "tasks": phases, "args": recipe.get("args", []),
                        "recipeSha256": canonical_digest(recipe), "cacheKey": cache_key, "cacheHit": False,
                        "buildTools": tool_inputs}
    write_json(receipt, result_record)
    cache.mkdir(parents=True, exist_ok=True)
    cache_artifact = cache / destination.name
    shutil.copyfile(destination, cache_artifact)
    write_json(cached_record, {**result_record, 'artifactPath': cache_artifact.relative_to(root).as_posix()})
    print(f"Built {identity} {metadata['version']}: {artifact.name}", flush=True)


def collect_entries(root: Path, run: str, manifest: dict, plan: dict) -> tuple[list[dict], list[dict]]:
    work = check_run(root, run, manifest, plan)
    entries, provenance = [], []
    originals = {e["modId"]: e for e in manifest["entries"] if e["included"]}
    for recipe in plan["entries"]:
        entry = copy.deepcopy(originals[recipe["modId"]])
        if recipe["mode"] == "binary":
            mods.check_artifact(root, entry)
            provenance.append({"modId": entry["modId"], "mode": "binary", "reason": recipe["reason"],
                               "sha256": entry["sha256"], "version": entry["version"]})
        else:
            receipt_path = work / "sources" / recipe["modId"] / "result.json"
            if not receipt_path.is_file():
                raise mods.ModError(f"Missing successful source build in this run: {recipe['modId']}")
            receipt = read_json(receipt_path)
            if receipt.get("run") != run or receipt.get("recipeSha256") != canonical_digest(recipe):
                raise mods.ModError(f"Stale source build receipt: {recipe['modId']}")
            if receipt["source"] != source_state(root, entry):
                raise mods.ModError(f"Source changed after compilation: {recipe['modId']}")
            check_tool_fingerprint(root, plan, recipe, receipt.get('buildTools'))
            artifact = mods.safe_path(root, receipt["artifactPath"])
            if not artifact.is_relative_to(work):
                raise mods.ModError(f"Build artifact is outside this run: {artifact}")
            entry.update(fileName=artifact.name, sha256=receipt["sha256"], size=receipt["size"],
                         version=receipt["metadata"]["version"], environment=receipt["metadata"].get("environment", "*"))
            entry["artifact"] = {"path": receipt["artifactPath"], "redistribution": entry["artifact"]["redistribution"],
                                 "url": None, "builtFromSource": True}
            entry["compatibility"] = {"dependencies": receipt["metadata"].get("depends", {})}
            mods.check_artifact(root, entry)
            provenance.append(receipt)
        check_runtime_metadata(fabric_metadata(mods.safe_path(root, entry["artifact"]["path"])))
        entries.append(entry)
    names = [e["fileName"].casefold() for e in entries]
    if len(names) != len(set(names)):
        raise mods.ModError("Output JAR filenames collide; correct the recipes before packaging")
    return entries, provenance


def assemble(root: Path, run: str) -> Path:
    manifest, plan = load_plan(root)
    entries, provenance = collect_entries(root, run, manifest, plan)
    work = run_path(root, run)
    produced = copy.deepcopy(manifest)
    produced["entries"] = entries
    produced["build"] = {"run": run, "sourceCompilation": True, "runtimeValidated": False,
                         "sourceCount": sum(r["mode"] == "source" for r in plan["entries"]),
                         "binaryCount": sum(r["mode"] == "binary" for r in plan["entries"])}
    staged = f"build/modpack-work/{run}/pack.zip"
    # The baseline packer rechecks exact bytes while writing and retains all legal notices.
    mods.pack(root, produced, staged, private=True)
    temporary = mods.safe_path(root, staged)
    with zipfile.ZipFile(temporary, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BUILD-PROVENANCE.json", json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("inventory/build-recipes.json", json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise mods.ModError("Generated ZIP failed CRC validation")
        for entry in entries:
            actual = hashlib.sha256(archive.read("mods/" + entry["fileName"])).hexdigest()
            if actual != entry["sha256"]:
                raise mods.ModError(f"Generated ZIP hash mismatch: {entry['fileName']}")
    output = mods.output_path(root, f"build/distributions/minefed-{manifest['minecraftVersion']}-{run}.zip")
    output.parent.mkdir(parents=True, exist_ok=True)
    mods.publish_new(temporary, output)
    digest, size = mods.file_digest(output)
    (output.parent / (output.name + ".sha256")).write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    summary = {**produced["build"], "path": output.relative_to(root).as_posix(), "sha256": digest,
               "size": size, "artifactCount": len(entries), "private": True}
    write_json(work / "result.json", summary)
    write_json(output.parent / "latest.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan")
    for name in ("prepare", "source", "assemble"):
        command = commands.add_parser(name)
        command.add_argument("--run", required=True)
        if name == "source":
            command.add_argument("--id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            _, plan = load_plan(ROOT)
            for recipe in plan["entries"]:
                print(f"{recipe['mode']:6} {recipe['modId']}: {recipe['reason']}")
        elif args.command == "prepare":
            prepare(ROOT, args.run)
        elif args.command == "source":
            build_source(ROOT, args.run, args.id)
        else:
            assemble(ROOT, args.run)
        return 0
    except (mods.ModError, OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
