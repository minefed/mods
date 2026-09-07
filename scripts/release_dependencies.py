"""Check selected JAR dependency fields, not the full Fabric SAT resolver or game startup."""
from __future__ import annotations

import base64
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

import build_modpack as builder
import mods

LOADER_VERSION = '0.18.4'
LOADER_URL = 'https://maven.fabricmc.net/net/fabricmc/fabric-loader/0.18.4/fabric-loader-0.18.4.jar'
# Verified against the official Maven .jar.sha256 and the actual published JAR.
LOADER_SHA256 = 'ea300b841949a290641db8c137e3da205462a089a7472d8f1657179fd23bcf4a'
SCOPE = 'Actual selected top-level/nested Fabric metadata; depends, breaks and candidate intersections. Not a full SAT resolution, Java class linkage check or Minecraft startup.'


def pinned_loader(root: Path) -> Path:
    cache = mods.safe_path(root, '.cache/release-dependencies')
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f'fabric-loader-{LOADER_VERSION}.jar'
    def verified(path):
        if mods.file_digest(path)[0] != LOADER_SHA256:
            raise mods.ModError('Fabric predicate library SHA-256 mismatch; existing file preserved')
    if target.exists():
        verified(target)
        return target
    gradle_cache = builder.gradle_user_home(root) / f'caches/modules-2/files-2.1/net.fabricmc/fabric-loader/{LOADER_VERSION}'
    candidates = list(gradle_cache.glob(f'*/fabric-loader-{LOADER_VERSION}.jar'))
    with tempfile.NamedTemporaryFile(dir=cache, suffix='.part', delete=False) as output:
        temporary = Path(output.name)
        try:
            if candidates:
                verified(candidates[0])
                with candidates[0].open('rb') as source:
                    shutil.copyfileobj(source, output, mods.CHUNK_SIZE)
            else:
                with mods.download(LOADER_URL) as response:
                    shutil.copyfileobj(response, output, mods.CHUNK_SIZE)
        except BaseException:
            output.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        verified(temporary)
        try:
            mods.publish_new(temporary, target)
        except mods.ModError:
            if not target.exists():
                raise
            verified(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def evaluate_predicates(root: Path, pairs: set[tuple[str, str]]) -> dict:
    if not pairs:
        return {}
    loader = pinned_loader(root)
    java_home = builder.java_home(root, 17)
    source = Path(__file__).with_name('ReleaseVersionPredicates.java')
    source_hash = mods.file_digest(source)[0]
    cache = mods.safe_path(root, '.cache/release-dependencies')
    # Compile into a private invocation directory; no Gradle daemon/global cache
    # mutation and no shared partially compiled helper class.
    with tempfile.TemporaryDirectory(prefix='predicate-', dir=cache) as work:
        executable = '.exe' if os.name == 'nt' else ''
        result = subprocess.run([str(java_home / 'bin' / ('javac' + executable)), '-encoding', 'UTF-8', '--release', '17',
                                 '-classpath', str(loader), '-d', work, str(source)], capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            raise mods.ModError('Cannot compile Fabric predicate helper: ' + result.stderr)
        ordered = sorted(pairs)
        encoded = lambda value: base64.b64encode(value.encode('utf-8')).decode('ascii')
        query = ''.join(encoded(version) + '\t' + encoded(predicate) + '\n' for version, predicate in ordered)
        result = subprocess.run([str(java_home / 'bin' / ('java' + executable)), '-Xmx64m', '-classpath',
                                 work + os.pathsep + str(loader), 'ReleaseVersionPredicates'], input=query,
                                capture_output=True, text=True, encoding='utf-8')
        answers = result.stdout.splitlines()
        if result.returncode or len(answers) != len(ordered) or any(a not in ('true', 'false') for a in answers):
            raise mods.ModError('Fabric rejected a version predicate: ' + result.stderr + result.stdout)
        if mods.file_digest(source)[0] != source_hash:
            raise mods.ModError('Fabric predicate helper changed while running')
        return {pair: answer == 'true' for pair, answer in zip(ordered, answers)}


def scan_metadata(root: Path, archive, origin: str, profiles: dict, active=frozenset(('server', 'client')), depth=0):
    if depth > 16:
        raise mods.ModError('Excessive nested JAR depth: ' + origin)
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if 'fabric.mod.json' not in names:
        return []
    if names.count('fabric.mod.json') != 1:
        raise mods.ModError('Duplicate Fabric metadata: ' + origin)
    info = archive.getinfo('fabric.mod.json')
    if info.file_size > mods.CHUNK_SIZE:
        raise mods.ModError('Oversized Fabric metadata: ' + origin)
    metadata = json.loads(archive.read(info).decode('utf-8-sig'))
    if not isinstance(metadata, dict) or not isinstance(metadata.get('id'), str) or not isinstance(metadata.get('version'), str):
        raise mods.ModError('Invalid nested Fabric metadata: ' + origin)
    environment = metadata.get('environment', '*')
    if environment not in ('*', 'server', 'client'):
        raise mods.ModError('Invalid nested Fabric environment: ' + origin)
    active = active & (frozenset(('server', 'client')) if environment == '*' else frozenset((environment,)))
    record = {'origin': origin, 'metadata': metadata, 'profiles': profiles, 'activeEnvironments': sorted(active), 'topLevel': depth == 0}
    records = [record]
    for item in metadata.get('jars', []):
        name = item['file']
        mods.safe_path(root, name)
        if names.count(name) != 1:
            raise mods.ModError('Missing or duplicate declared nested JAR: ' + origin + '!/' + name)
        with tempfile.TemporaryFile(dir=root / '.cache') as temporary:
            with archive.open(name) as source:
                shutil.copyfileobj(source, temporary, mods.CHUNK_SIZE)
            temporary.seek(0)
            with zipfile.ZipFile(temporary) as nested:
                records.extend(scan_metadata(root, nested, origin + '!/' + name, profiles, active, depth + 1))
    return records


def predicates(value):
    values = value if isinstance(value, list) else [value]
    if not values or any(not isinstance(v, str) for v in values):
        raise mods.ModError('Fabric dependency predicates must be strings or nonempty string arrays')
    return values


def analyze(records: list[dict], runtime_loader: str, evaluator) -> dict:
    records = list(records)
    for identity, version in [('minecraft', '1.20.4'), ('java', '17'), ('fabricloader', runtime_loader)]:
        records.append({'origin': 'target-runtime', 'metadata': {'id': identity, 'version': version},
                        'profiles': {'server': True, 'client': True}, 'activeEnvironments': ['server', 'client'], 'topLevel': True})
    providers = defaultdict(list)
    for record in records:
        metadata = record['metadata']
        aliases = metadata.get('provides', [])
        if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
            raise mods.ModError('Invalid Fabric provides aliases')
        for identity in [metadata['id'], *aliases]:
            providers[identity].append(record)
    pairs = set()
    for record in records:
        for kind in ('depends', 'breaks'):
            requirements = record['metadata'].get(kind, {})
            if not isinstance(requirements, dict):
                raise mods.ModError('Invalid Fabric dependency map')
            for identity, requirement in requirements.items():
                for predicate in predicates(requirement):
                    # Validate predicate syntax even when the named dependency is missing.
                    pairs.add(('0', predicate))
                    for candidate in providers[identity]:
                        pairs.add((candidate['metadata']['version'], predicate))
    answers = evaluator(pairs)
    matches = lambda record, requirement: any(answers[(record['metadata']['version'], p)] for p in predicates(requirement))
    environments = {}
    for side in ('server', 'client'):
        present = lambda r: r['profiles'][side]
        enabled = lambda r: present(r) and side in r['activeEnvironments']
        missing, softened, breaks, empty = [], [], [], []
        positive, negative = defaultdict(list), defaultdict(list)
        def candidates(identity):
            values = [p for p in providers[identity] if enabled(p)]
            required = [p for p in values if p['topLevel']]
            return required or values
        for record in records:
            if not enabled(record):
                continue
            metadata = record['metadata']
            for identity, requirement in metadata.get('depends', {}).items():
                values = candidates(identity)
                edge = {'from': metadata['id'], 'origin': record['origin'], 'to': identity, 'predicate': requirement}
                if any(matches(p, requirement) for p in values):
                    positive[identity].append((edge, requirement))
                elif metadata.get('schemaVersion', 1) < 2 and not values and any(matches(p, requirement) for p in providers[identity] if present(p) and not enabled(p)):
                    # Fabric Loader ModResolver softens legacy positive constraints
                    # only when a matching mod is present but environment-disabled.
                    softened.append(edge)
                else:
                    missing.append({**edge, 'availableVersions': sorted({p['metadata']['version'] for p in values})})
            for identity, requirement in metadata.get('breaks', {}).items():
                values = candidates(identity)
                edge = {'from': metadata['id'], 'origin': record['origin'], 'to': identity, 'predicate': requirement}
                if values:
                    negative[identity].append((edge, requirement))
                    if any(p['topLevel'] and matches(p, requirement) for p in values) or all(matches(p, requirement) for p in values):
                        breaks.append(edge)
        for identity in set(positive) | set(negative):
            values = candidates(identity)
            if values and not any(all(matches(p, requirement) for _, requirement in positive[identity]) and
                                  all(not matches(p, requirement) for _, requirement in negative[identity]) for p in values):
                empty.append({'modId': identity, 'depends': [e for e, _ in positive[identity]], 'breaks': [e for e, _ in negative[identity]]})
        environments[side] = {'missingOrIncompatibleDependencies': missing, 'environmentDisabledDependenciesSoftened': softened,
                              'unavoidableBreaks': breaks, 'candidateVersionIntersectionEmpty': empty,
                              'activeMetadataCount': sum(enabled(r) for r in records)}
    return {'scope': SCOPE, 'runtimeValidated': False, 'runtimeFabricLoader': runtime_loader,
            'predicateLibraryVersion': LOADER_VERSION, 'predicateLibrarySha256': LOADER_SHA256,
            'metadataRecordCount': len(records) - 3, 'environments': environments}


def check_selected(root: Path, selected: list, runtime_loader: str) -> dict:
    (root / '.cache').mkdir(exist_ok=True)
    records = []
    for record, path, entry in selected:
        mods.check_bytes(path, entry)
        with zipfile.ZipFile(path) as archive:
            records.extend(scan_metadata(root, archive, record['path'], {side: record[side] for side in ('server', 'client')}))
        mods.check_bytes(path, entry)
    report = analyze(records, runtime_loader, lambda pairs: evaluate_predicates(root, pairs))
    errors = {side: {kind: value for kind, value in result.items() if kind in
                    ('missingOrIncompatibleDependencies', 'unavoidableBreaks', 'candidateVersionIntersectionEmpty') and value}
              for side, result in report['environments'].items()}
    if any(errors.values()):
        raise mods.ModError('Selected release dependencies are incompatible:\n' + json.dumps(errors, ensure_ascii=False, indent=2))
    return report
